"""Clean selected NHANES fields while retaining the full survey universe."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from cleaning_rules import OBSERVED, clean_frame


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "processed" / "nhanes_2017_2018_merged.csv"
REPORT_DIR = ROOT / "reports" / "02_data_cleaning"


def load_inputs():
    manifest = json.loads((ROOT / "reports" / "00_data_acquisition" / "acquisition_summary.json").read_text())
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != manifest["merged_sha256"]:
        raise ValueError("Merged input differs from its acquisition record.")
    members = {}
    for source in manifest["sources"]:
        path = ROOT / source["raw_file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"Original component changed: {path.name}")
        component = pd.read_sas(path, format="xport")
        members[source["component"]] = {"participants": set(component["SEQN"]), "variables": list(component)}
    raw = pd.read_csv(SOURCE, dtype={"SEQN": "int64"})
    if raw["SEQN"].duplicated().any():
        raise ValueError("Duplicate survey participants.")
    return raw, members, manifest


def quality_tables(raw, values, statuses, rules):
    changes = []
    for column in rules:
        for reason, count in statuses[column].value_counts().items():
            changes.append({"variable": column, "status": reason, "participants": int(count),
                            "analysis_domain_participants": int((statuses[column].eq(reason) & values["analysis_domain"].eq(1)).sum())})
    numeric = []
    for column in rules:
        preserved = np.isclose(raw[column], values[column], equal_nan=True)
        numeric.append({
            "variable": column, "raw_blank_count": int(raw[column].isna().sum()),
            "cleaned_blank_count": int(values[column].isna().sum()), "changed_values": int((~preserved).sum()),
            "valid_values_retained": int((statuses[column].eq(OBSERVED) & values[column].notna()).sum()),
        })
    dictionary = [{"variable": column, "allowed_categories": ",".join(map(str, rule.allowed or ())),
                   "minimum": rule.minimum, "maximum": rule.maximum, "integral": rule.integral,
                   "special_codes": json.dumps(rule.specials, sort_keys=True)} for column, rule in rules.items()]
    return pd.DataFrame(changes), pd.DataFrame(numeric), pd.DataFrame(dictionary)


def main():
    raw, members, manifest = load_inputs()
    values, statuses, rules = clean_frame(raw, members)
    if len(values) != len(raw) or not values["SEQN"].equals(raw["SEQN"]):
        raise ValueError("Cleaning altered the survey participant universe or order.")
    audit = json.loads((ROOT / "reports" / "01_data_audit" / "audit_summary.json").read_text())
    if int(values["analysis_domain"].sum()) != audit["provisional_cohort"]:
        raise ValueError("The primary domain unexpectedly differs from the audited cohort.")
    changes, numeric, dictionary = quality_tables(raw, values, statuses, rules)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    output = ROOT / "data" / "processed" / "nhanes_2017_2018_cleaned.csv"
    status_output = ROOT / "data" / "processed" / "nhanes_2017_2018_response_status.csv"
    values.to_csv(output, index=False)
    statuses = statuses.rename(columns={"SEQN": "identifier_status"})
    statuses.insert(0, "SEQN", values["SEQN"])
    statuses.to_csv(status_output, index=False)
    changes.to_csv(REPORT_DIR / "response_status_counts.csv", index=False)
    numeric.to_csv(REPORT_DIR / "cleaning_changes.csv", index=False)
    dictionary.to_csv(REPORT_DIR / "cleaning_rules.csv", index=False)
    summary = {
        "cycle": "2017-2018", "universe_participants": len(values), "selected_fields": len(rules),
        "cleaned_columns": len(values.columns), "analysis_domain": int(values["analysis_domain"].sum()),
        "pregnancy_uncertain_in_domain": int((values["analysis_domain"].eq(1) & values["pregnancy_uncertain"].eq(1)).sum()),
        "pregnancy_sensitivity_domain": int(values["analysis_domain_known_pregnancy_status_sensitivity"].sum()),
        "invalid_values": int(statuses.drop(columns="SEQN").eq("invalid_value").sum().sum()),
        "routing_conflicts": int(statuses.drop(columns="SEQN").eq("routing_conflict").sum().sum()),
        "input_sha256": manifest["merged_sha256"],
        "output_file": output.relative_to(ROOT).as_posix(), "status_file": status_output.relative_to(ROOT).as_posix(),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "status_sha256": hashlib.sha256(status_output.read_bytes()).hexdigest(),
        "notes": [
            "All demographic participants retained; analysis_domain identifies the measured-HbA1c domain.",
            "Selected raw numeric fields only; unselected fields remain available in the unchanged merged input.",
            "No blanket missing-to-zero replacement, learned imputation, trimming, scaling, frequency conversion, or modeling.",
            "Skips, refusal, unknown answers, intervals, top codes, and missing required units are tracked separately.",
            "Missingness explanations based on observed gates cannot fully identify every original reason for nonresponse.",
        ],
    }
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != manifest["merged_sha256"]:
        raise ValueError("Merged input changed during cleaning.")
    (REPORT_DIR / "cleaning_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Full survey universe: {len(values):,}; cleaned fields: {len(rules)}; primary domain: {summary['analysis_domain']}")
    print(f"Pregnancy-status sensitivity domain: {summary['pregnancy_sensitivity_domain']}")
    print(f"Invalid values: {summary['invalid_values']}; routing conflicts: {summary['routing_conflicts']}")
    print(f"Cleaned values: {output}")
    print(f"Response reasons: {status_output}")


if __name__ == "__main__":
    main()