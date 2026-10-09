"""Acquire official NHANES 2017-2018 components and merge them by participant."""

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "2017-2018"
REFERENCE_DIR = ROOT / "reference" / "2017-2018"
OUTPUT = ROOT / "data" / "processed" / "nhanes_2017_2018_merged.csv"
REPORT_DIR = ROOT / "reports" / "00_data_acquisition"
BASE_URL = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles"
XPORT_ZERO_ARTIFACT = 5.397605346934028e-79
MODULES = {
    "DEMO_J": "Demographics and survey design",
    "DIQ_J": "Diabetes diagnosis, treatment, and monitoring",
    "GHB_J": "Measured glycohemoglobin (HbA1c)",
    "BMX_J": "Measured body size and BMI",
    "PAQ_J": "Physical activity and sedentary time",
    "HUQ_J": "Healthcare utilization and access",
}


def fetch_bytes(url):
    request = Request(url, headers={"User-Agent": "ChronicDiseaseManagementResearch/1.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def validate_component(frame, component):
    if frame.empty or "SEQN" not in frame:
        raise ValueError(f"{component} has no participant records or SEQN column.")
    if frame["SEQN"].isna().any() or frame["SEQN"].duplicated().any():
        raise ValueError(f"{component} does not have unique nonmissing participant IDs.")
    if not (frame["SEQN"] % 1 == 0).all():
        raise ValueError(f"{component} has noninteger participant IDs.")
    frame["SEQN"] = frame["SEQN"].astype("int64")
    return frame


def restore_transport_zeros(frame):
    artifacts = frame.eq(XPORT_ZERO_ARTIFACT)
    return frame.mask(artifacts, 0.0), int(artifacts.to_numpy().sum())


def acquire_component(component):
    path = RAW_DIR / f"{component}.xpt"
    if path.exists():
        payload = path.read_bytes()
    else:
        print(f"Downloading official {component}.xpt...", flush=True)
        payload = fetch_bytes(f"{BASE_URL}/{component}.xpt")
    parsed = pd.read_sas(io.BytesIO(payload), format="xport", encoding="utf-8")
    frame, restored_zeros = restore_transport_zeros(parsed)
    frame = validate_component(frame, component)
    if not path.exists():
        path.write_bytes(payload)
    documentation = REFERENCE_DIR / f"{component}.htm"
    if not documentation.exists():
        html = fetch_bytes(f"{BASE_URL}/{component}.htm")
        if component.encode() not in html:
            raise ValueError(f"Unexpected documentation returned for {component}.")
        documentation.write_bytes(html)
    source = {
        "component": component, "description": MODULES[component],
        "data_url": f"{BASE_URL}/{component}.xpt", "codebook_url": f"{BASE_URL}/{component}.htm",
        "raw_file": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(payload).hexdigest(),
        "codebook_sha256": hashlib.sha256(documentation.read_bytes()).hexdigest(),
        "rows": len(frame), "columns": len(frame.columns),
        "transport_zeros_restored": restored_zeros,
    }
    return frame, source


def merge_components(components):
    merged = components["DEMO_J"].copy()
    joins = []
    for name, frame in components.items():
        if name == "DEMO_J":
            continue
        overlaps = (set(frame) & set(merged)) - {"SEQN"}
        if overlaps:
            raise ValueError(f"Ambiguous shared columns in {name}: {sorted(overlaps)}")
        matched = int(merged["SEQN"].isin(frame["SEQN"]).sum())
        unmatched = int((~frame["SEQN"].isin(merged["SEQN"])).sum())
        if unmatched:
            raise ValueError(f"{name} has participants outside the demographic universe.")
        merged = merged.merge(frame, on="SEQN", how="left", validate="one_to_one")
        joins.append({"component": name, "matched_participants": matched, "participants_without_module_row": len(merged) - matched})
    if len(merged) != len(components["DEMO_J"]) or merged["SEQN"].duplicated().any():
        raise ValueError("Merging changed the demographic participant universe.")
    return merged, joins


def main():
    for directory in (RAW_DIR, REFERENCE_DIR, OUTPUT.parent, REPORT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    components = {}
    sources = []
    for component in MODULES:
        frame, source = acquire_component(component)
        components[component] = frame
        sources.append(source)
    merged, joins = merge_components(components)
    merged.to_csv(OUTPUT, index=False)
    pd.DataFrame(sources).to_csv(REPORT_DIR / "source_inventory.csv", index=False)
    pd.DataFrame(joins).to_csv(REPORT_DIR / "join_audit.csv", index=False)
    manifest = {
        "cycle": "2017-2018", "acquired_utc": datetime.now(timezone.utc).isoformat(),
        "sources": sources, "merged_rows": len(merged), "merged_columns": len(merged.columns),
        "merged_file": OUTPUT.relative_to(ROOT).as_posix(),
        "merged_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "interpretation": "One row per participant; demographic left joins retain ineligible and unmeasured records for auditing.",
        "parser_note": "Exact pandas IBM-XPORT zero artifact restored to zero; original eight-byte zero encoding verified in DIQ_J. XPT source bytes are unchanged.",
    }
    (REPORT_DIR / "acquisition_summary.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Merged {len(merged):,} participants and {len(merged.columns)} variables; no clinical cleaning performed.")
    print(f"Merged CSV: {OUTPUT}")


if __name__ == "__main__":
    main()