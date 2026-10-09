"""Extract NHANES features from verified cleaned values and response reasons."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from feature_rules import derive_features, feature_dictionary


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "03_feature_extraction"
DESIGN_COLUMNS = ("SEQN", "WTMEC2YR", "WTINT2YR", "SDMVSTRA", "SDMVPSU", "RIDSTATR")


def load_inputs():
    summary = json.loads((ROOT / "reports" / "02_data_cleaning" / "cleaning_summary.json").read_text())
    inputs = {}
    for name, file_key, hash_key in (("values", "output_file", "output_sha256"), ("statuses", "status_file", "status_sha256")):
        path = ROOT / summary[file_key]
        if hashlib.sha256(path.read_bytes()).hexdigest() != summary[hash_key]:
            raise ValueError(f"Cleaned input changed: {path.name}. Rerun cleaning first.")
        inputs[name] = pd.read_csv(path, dtype={"SEQN": "int64"})
    values, statuses = inputs["values"], inputs["statuses"]
    if values["SEQN"].duplicated().any() or statuses["SEQN"].duplicated().any():
        raise ValueError("Participant IDs must be unique.")
    if set(values["SEQN"]) != set(statuses["SEQN"]):
        raise ValueError("Cleaned values and response reasons have different participant universes.")
    statuses = statuses.set_index("SEQN").loc[values["SEQN"]].reset_index()
    statuses.index = values.index
    return values, statuses, summary


def feature_summaries(features, domain):
    rows = []
    counts = []
    for column in features:
        selected = features.loc[domain, column]
        numeric = pd.api.types.is_numeric_dtype(selected)
        rows.append({
            "feature": column, "domain_participants": len(selected), "domain_observed": int(selected.notna().sum()),
            "domain_missing": int(selected.isna().sum()), "domain_missing_percent": float(100 * selected.isna().mean()),
            "unweighted_mean": float(selected.mean()) if numeric and selected.notna().any() else np.nan,
            "unweighted_median": float(selected.median()) if numeric and selected.notna().any() else np.nan,
        })
        if numeric and selected.nunique() > 20:
            continue
        for value, count in selected.value_counts(dropna=False).items():
            counts.append({"feature": column, "value": "Missing" if pd.isna(value) else str(value), "participants": int(count)})
    return pd.DataFrame(rows), pd.DataFrame(counts)


def main():
    values, statuses, cleaning = load_inputs()
    features = derive_features(values, statuses)
    dictionary = feature_dictionary()
    if set(features) != set(dictionary["feature"]) or dictionary["feature"].duplicated().any():
        raise ValueError("The feature table and dictionary disagree.")
    if set(features) & set(values):
        raise ValueError("Derived features would replace original cleaned fields.")
    combined = pd.concat([values, features], axis=1)
    for column in (*DESIGN_COLUMNS, "LBXGH", "analysis_domain", "pregnancy_uncertain", "analysis_domain_known_pregnancy_status_sensitivity"):
        if not combined[column].equals(values[column]):
            raise ValueError(f"Protected original field changed: {column}")
    domain = combined["analysis_domain"].eq(1)
    descriptions, counts = feature_summaries(features, domain)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    output = ROOT / "data" / "processed" / "nhanes_2017_2018_features.csv"
    combined.to_csv(output, index=False)
    dictionary.to_csv(REPORT_DIR / "feature_dictionary.csv", index=False)
    descriptions.to_csv(REPORT_DIR / "feature_missingness.csv", index=False)
    counts.to_csv(REPORT_DIR / "feature_value_counts.csv", index=False)
    summary = {
        "cycle": "2017-2018", "universe_participants": len(combined), "analysis_domain": int(domain.sum()),
        "original_cleaned_columns": len(values.columns), "derived_columns": len(features.columns), "total_columns": len(combined.columns),
        "domain_activity_complete": int(combined.loc[domain, "activity_complete"].sum()),
        "domain_hba1c_at_least_8": int(combined.loc[domain, "hba1c_at_least_8"].sum()),
        "domain_hba1c_at_least_7": int(combined.loc[domain, "hba1c_at_least_7"].sum()),
        "domain_activity_exceeds_calendar_week": int(combined.loc[domain, "activity_total_exceeds_calendar_week"].sum()),
        "input_hashes": {cleaning["output_file"]: cleaning["output_sha256"], cleaning["status_file"]: cleaning["status_sha256"]},
        "output_file": output.relative_to(ROOT).as_posix(), "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "exclude_from_clinical_predictors": [*DESIGN_COLUMNS, "LBXGH", "DIQ280", "hba1c_at_least_8", "hba1c_at_least_7",
                                             "analysis_domain", "pregnancy_uncertain", "analysis_domain_known_pregnancy_status_sensitivity",
                                             "activity_complete", "activity_total_exceeds_calendar_week", "glucose_frequency_status"],
        "notes": [
            "No participant exclusions, imputation, weighted estimates, statistical tests, or fitted models in this step.",
            "Continuous LBXGH is the primary proposed outcome; cutoff flags are secondary/sensitivity targets only.",
            "Missing activity domains do not become zero; all five domains required for aggregate activity measures.",
            "Choose original versus derived representations; avoid all activity totals/components or source/flag duplicates in the same model.",
            "All summaries are unweighted sample descriptions, not national estimates or validated individual treatment goals.",
        ],
    }
    if summary["analysis_domain"] != cleaning["analysis_domain"]:
        raise ValueError("Feature extraction changed the analysis domain.")
    (REPORT_DIR / "feature_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Features: {len(combined):,} participants, {len(features.columns)} added columns, {len(combined.columns)} total columns")
    print(f"Primary domain: {summary['analysis_domain']}; complete activity data: {summary['domain_activity_complete']}")
    print(f"Secondary HbA1c >=8% cases: {summary['domain_hba1c_at_least_8']}")
    print(f"Feature output: {output}")


if __name__ == "__main__":
    main()