"""Audit NHANES components and the provisional adult diagnosed-diabetes domain."""

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "processed" / "nhanes_2017_2018_merged.csv"
REPORT_DIR = ROOT / "reports" / "01_data_audit"
SURVEY_DESIGN_ROLE = "Survey design"
VARIABLES = {
    "SEQN": ("Identifier", "Survey participant ID; not a predictor"),
    "RIDAGEYR": ("Demographics", "Age; 80 represents age 80 or older"),
    "RIAGENDR": ("Demographics", "Recorded sex category"),
    "RIDRETH3": ("Demographics", "Recorded race/Hispanic origin"),
    "DMDEDUC2": ("Socioeconomic", "Education for adults 20+; codes 7/9 are refusal/don't know"),
    "INDFMPIR": ("Socioeconomic", "Family income-to-poverty ratio; top-coded at 5"),
    "RIDEXPRG": ("Cohort", "Pregnancy status released for women 20-44; blank does not universally mean unknown pregnancy"),
    "RIDSTATR": (SURVEY_DESIGN_ROLE, "Interview/examination status"),
    "WTMEC2YR": (SURVEY_DESIGN_ROLE, "Two-year MEC examination weight; zero for unexamined people"),
    "WTINT2YR": (SURVEY_DESIGN_ROLE, "Interview weight; not the primary HbA1c analysis weight"),
    "SDMVSTRA": (SURVEY_DESIGN_ROLE, "Masked variance stratum"),
    "SDMVPSU": (SURVEY_DESIGN_ROLE, "Masked PSU; use together with stratum, not alone"),
    "DIQ010": ("Cohort", "Diagnosed diabetes: 1 yes, 2 no, 3 borderline, 7 refused, 9 don't know"),
    "DID040": ("Clinical history", "Age at diagnosis; 666 below age one, 777/999 refused/don't know"),
    "DIQ050": ("Treatment", "Current insulin use; not medication adherence"),
    "DIQ070": ("Treatment", "Current diabetic pill use; nonresponse may reflect questionnaire routing"),
    "DIQ230": ("Monitoring", "Last diabetes educator/dietitian/nutritionist visit; excludes doctors"),
    "DIQ240": ("Monitoring", "One usual diabetes doctor/health professional"),
    "DID250": ("Monitoring", "Visits to that usual doctor; missing if DIQ240 is No; 7777/9999 refused/don't know"),
    "DID260": ("Monitoring", "Self/family glucose checks; 0 never, 777/999 refused/don't know; combine with units"),
    "DIQ260U": ("Monitoring", "Glucose-check frequency unit: day/week/month/year"),
    "DIQ275": ("Monitoring", "Self-reported professional A1C testing in past year"),
    "DIQ280": ("Outcome-related", "Self-reported last A1C; not measured LBXGH; avoid as a shortcut predictor"),
    "DIQ291": ("Monitoring", "Reported provider A1C goal; not a universal personalized threshold"),
    "DIQ080": ("Clinical history", "Self-reported diabetes-related retinopathy"),
    "LBXGH": ("Outcome", "Measured HbA1c in percent; keep continuous value"),
    "BMXBMI": ("Body size", "Measured body mass index"),
    "PAQ605": ("Lifestyle", "Vigorous work activity; 1 yes, 2 no, 7/9 refused/don't know"),
    "PAQ620": ("Lifestyle", "Moderate work activity"),
    "PAQ635": ("Lifestyle", "Walking/bicycling for transport"),
    "PAQ650": ("Lifestyle", "Vigorous recreational activity"),
    "PAQ665": ("Lifestyle", "Moderate recreational activity"),
    "PAQ610": ("Lifestyle", "Days of vigorous work; blank may mean PAQ605=No; 77/99 special codes"),
    "PAD615": ("Lifestyle", "Daily vigorous work minutes; 7777/9999 special codes; use with days and gate"),
    "PAD680": ("Lifestyle", "Daily sedentary minutes; zero valid, 7777/9999 refused/don't know"),
    "HUQ010": ("Health context", "Self-rated general health category"),
    "HUQ030": ("Access", "Usual healthcare place: 1 yes, 2 none, 3 more than one place"),
    "HUQ041": ("Access", "Usual healthcare setting; routed by HUQ030"),
    "HUQ051": ("Utilization", "Categorical healthcare-visit bands, not raw visit counts"),
    "HUQ071": ("Utilization", "Any overnight hospitalization in past year; not 30-day readmission"),
    "HUD080": ("Utilization", "Hospitalization count category; 6 means six or more; conditional on HUQ071"),
}


def cohort_flow(frame):
    mask = pd.Series(True, index=frame.index)
    rows = [{"step": "Demographic participant universe", "remaining": len(frame), "excluded_at_step": 0}]
    rules = [
        ("Age 20 or older", frame["RIDAGEYR"].ge(20)),
        ("Self-reported doctor-diagnosed diabetes (DIQ010=1)", frame["DIQ010"].eq(1)),
        ("Exclude known pregnancy (RIDEXPRG=1)", frame["RIDEXPRG"].ne(1)),
        ("Measured HbA1c available", frame["LBXGH"].notna()),
        ("Positive MEC examination weight", frame["WTMEC2YR"].gt(0)),
        ("Survey stratum and PSU available", frame[["SDMVSTRA", "SDMVPSU"]].notna().all(axis=1)),
    ]
    for label, condition in rules:
        before = int(mask.sum())
        mask &= condition
        remaining = int(mask.sum())
        rows.append({"step": label, "remaining": remaining, "excluded_at_step": before - remaining})
    return pd.DataFrame(rows), mask


def audit_columns(frame, cohort, module_lookup):
    rows = []
    for column in frame:
        values = frame[column]
        group, meaning = VARIABLES.get(column, ("Unselected", "Consult component codebook before use"))
        rows.append({
            "variable": column, "component": module_lookup[column], "role": group, "meaning": meaning,
            "all_participant_missing": int(values.isna().sum()),
            "all_participant_missing_percent": float(100 * values.isna().mean()),
            "cohort_missing": int(cohort[column].isna().sum()),
            "cohort_missing_percent": float(100 * cohort[column].isna().mean()),
            "distinct_observed_values": int(values.nunique()),
        })
    return pd.DataFrame(rows)


def cohort_value_counts(cohort):
    counts = []
    for variable in VARIABLES:
        if variable in {"SEQN", "WTMEC2YR", "WTINT2YR"}:
            continue
        for value, count in cohort[variable].value_counts(dropna=False).items():
            counts.append({"variable": variable, "raw_value": "Missing" if pd.isna(value) else str(value), "participants": int(count)})
    return pd.DataFrame(counts)


def main():
    if not SOURCE.exists():
        raise FileNotFoundError("Run scripts/00_data_acquisition/download_data.py first.")
    frame = pd.read_csv(SOURCE, dtype={"SEQN": "int64"})
    if not set(VARIABLES).issubset(frame.columns):
        raise ValueError(f"Missing selected variables: {sorted(set(VARIABLES) - set(frame.columns))}")
    manifest = json.loads((ROOT / "reports" / "00_data_acquisition" / "acquisition_summary.json").read_text())
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != manifest["merged_sha256"]:
        raise ValueError("Merged data no longer match the acquisition record.")
    lookup = {"SEQN": "DEMO_J"}
    for source in manifest["sources"]:
        path = ROOT / source["raw_file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"Original component changed: {path.name}")
        component = pd.read_sas(path, format="xport")
        lookup.update({column: source["component"] for column in component if column != "SEQN"})
    flow, mask = cohort_flow(frame)
    cohort = frame.loc[mask]
    if cohort.empty or frame["SEQN"].duplicated().any():
        raise ValueError("Empty provisional cohort or duplicate participant identifiers.")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    audit_columns(frame, cohort, lookup).to_csv(REPORT_DIR / "variable_audit.csv", index=False)
    flow.to_csv(REPORT_DIR / "cohort_flow.csv", index=False)
    dictionary = [{"variable": variable, "component": lookup[variable], "role": group, "meaning": meaning} for variable, (group, meaning) in VARIABLES.items()]
    pd.DataFrame(dictionary).to_csv(REPORT_DIR / "variable_dictionary.csv", index=False)
    cohort_value_counts(cohort).to_csv(REPORT_DIR / "cohort_value_counts.csv", index=False)
    summary = {
        "cycle": "2017-2018", "participants": len(frame), "columns": len(frame.columns),
        "adult_diagnosed_diabetes_before_measurement_filters": int((frame["RIDAGEYR"].ge(20) & frame["DIQ010"].eq(1)).sum()),
        "provisional_cohort": len(cohort), "hbA1c_mean_unweighted": float(cohort["LBXGH"].mean()),
        "hbA1c_median_unweighted": float(cohort["LBXGH"].median()),
        "hbA1c_min": float(cohort["LBXGH"].min()), "hbA1c_max": float(cohort["LBXGH"].max()),
        "hbA1c_at_least_8_unweighted_count": int(cohort["LBXGH"].ge(8).sum()),
        "cohort_strata": int(cohort["SDMVSTRA"].nunique()),
        "cohort_stratum_psu_pairs": len(cohort[["SDMVSTRA", "SDMVPSU"]].drop_duplicates()),
        "pregnancy_status_3_in_cohort": int(cohort["RIDEXPRG"].eq(3).sum()),
        "merged_sha256": manifest["merged_sha256"],
        "notes": [
            "Audit only; no code recoding, imputation, feature extraction, weighted population estimates, or modeling.",
            "Missingness includes questionnaire skips, age eligibility, module absence, and item nonresponse.",
            "Refused/don't-know sentinel codes remain observed values until variable-specific cleaning.",
            "HbA1c >=8% is an exploratory analytical cutoff, not proof of failing an individualized clinical goal.",
            "Use MEC weights with strata and PSU, retaining the full survey universe for domain variance estimation.",
            "Current HbA1c cannot validate the UCI readmission model, and participants cannot be linked across datasets.",
        ],
    }
    (REPORT_DIR / "audit_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(flow.to_string(index=False))
    print(f"Provisional domain: {len(cohort):,} participants; measured HbA1c median: {summary['hbA1c_median_unweighted']:.2f}% (unweighted)")
    print(f"Audit tables: {REPORT_DIR}")


if __name__ == "__main__":
    main()