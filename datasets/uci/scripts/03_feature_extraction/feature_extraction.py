"""Step 3: derive interpretable features from the cleaned study cohort."""

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "processed" / "diabetes_cleaned.csv"
OUTPUT = ROOT / "data" / "processed" / "diabetes_features.csv"
REPORT_DIR = ROOT / "reports" / "03_feature_extraction"
DRUG_COLUMNS = (
    "metformin", "repaglinide", "nateglinide", "chlorpropamide",
    "glimepiride", "acetohexamide", "glipizide", "glyburide", "tolbutamide",
    "pioglitazone", "rosiglitazone", "acarbose", "miglitol", "troglitazone",
    "tolazamide", "insulin", "glyburide-metformin", "glipizide-metformin",
    "glimepiride-pioglitazone", "metformin-rosiglitazone", "metformin-pioglitazone",
)
UNDER_40 = "Under 40"
AGE_GROUPS = {
    "[0-10)": UNDER_40, "[10-20)": UNDER_40, "[20-30)": UNDER_40,
    "[30-40)": UNDER_40, "[40-50)": "40-59", "[50-60)": "40-59",
    "[60-70)": "60-79", "[70-80)": "60-79", "[80-90)": "80+", "[90-100)": "80+",
}
FEATURE_DEFINITIONS = [
    ("readmitted_30d", "binary_target", "readmitted", "1 for <30; 0 for >30 or NO. Never use either outcome column as a predictor."),
    ("total_previous_visits", "count", "number_outpatient, number_emergency, number_inpatient", "Sum of the three recorded prior visit counts; not a measure of adherence."),
    ("prior_acute_visits", "count", "number_emergency, number_inpatient", "Emergency plus inpatient visit counts; excludes outpatient visits."),
    ("medication_burden_band", "category", "num_medications", "Low: 0-5; Moderate: 6-14; High: 15+. Counts inpatient medications, not verified long-term polypharmacy."),
    ("diag_1_group", "category", "diag_1", "Primary diagnosis: Diabetes (250.xx), Circulatory (390-459 or 785.xx), Respiratory (460-519 or 786.xx), Other, or Unknown."),
    ("diag_2_group", "category", "diag_2", "Secondary diagnosis grouped using the same ICD-9 rules as diag_1_group."),
    ("diag_3_group", "category", "diag_3", "Third diagnosis grouped using the same ICD-9 rules as diag_1_group."),
    ("medication_changed", "binary", "change", "1 for Ch; 0 for No. General recorded regimen-change flag, not necessarily an explicit dose change."),
    ("any_drug_dose_changed", "binary", "21 retained diabetes drug columns", "1 if any drug is Up or Down; 0 otherwise. Not interchangeable with the general change flag."),
    ("active_diabetes_drug_count", "count", "21 retained diabetes drug columns", "Count drug fields with Steady, Up, or Down. Combination-drug fields count as one field, not separate ingredients."),
    ("insulin_used", "binary", "insulin", "1 for Steady, Up, or Down; 0 for No."),
    ("diabetes_med_prescribed", "binary", "diabetesMed", "1 for Yes; 0 for No. Mirrors the recorded diabetes-medication indicator."),
    ("a1c_test_recorded", "binary", "A1Cresult", "0 for None; 1 for Norm, >7, or >8. Test documentation, not a continuous HbA1c measurement."),
    ("glucose_test_recorded", "binary", "max_glu_serum", "0 for None; 1 for Norm, >200, or >300. Does not establish glycemic control."),
    ("age_group", "category", "age", "Combine recorded age bands into Under 40, 40-59, 60-79, or 80+. Exact ages are not inferred."),
]


def diagnosis_group(code):
    if code == "Unknown":
        return "Unknown"
    if re.fullmatch(r"[EV]\d{1,3}(?:\.\d{1,2})?", code):
        return "Other"
    if not re.fullmatch(r"\d{1,3}(?:\.\d{1,2})?", code):
        raise ValueError(f"Unrecognized ICD-9 code: {code}")
    major_code = int(code.split(".")[0])
    if major_code == 250:
        return "Diabetes"
    if 390 <= major_code <= 459 or major_code == 785:
        return "Circulatory"
    if 460 <= major_code <= 519 or major_code == 786:
        return "Respiratory"
    return "Other"


def medication_band(count):
    if count < 0:
        raise ValueError("Medication count must be nonnegative.")
    if count <= 5:
        return "Low"
    return "Moderate" if count <= 14 else "High"


def checked_indicator(value, mapping, column):
    if value not in mapping:
        raise ValueError(f"Unexpected {column} category: {value}")
    return mapping[value]


def extract_features(record):
    drug_states = [record[column] for column in DRUG_COLUMNS]
    if not set(drug_states).issubset({"No", "Steady", "Up", "Down"}):
        raise ValueError("Unknown drug status requires an explicit feature rule.")
    visits = [int(record[column]) for column in ("number_outpatient", "number_emergency", "number_inpatient")]
    if min(visits) < 0:
        raise ValueError("Prior visit counts must be nonnegative.")
    derived = {
        "readmitted_30d": checked_indicator(record["readmitted"], {"<30": 1, ">30": 0, "NO": 0}, "readmitted"),
        "total_previous_visits": sum(visits),
        "prior_acute_visits": visits[1] + visits[2],
        "medication_burden_band": medication_band(int(record["num_medications"])),
        "diag_1_group": diagnosis_group(record["diag_1"]),
        "diag_2_group": diagnosis_group(record["diag_2"]),
        "diag_3_group": diagnosis_group(record["diag_3"]),
        "medication_changed": checked_indicator(record["change"], {"Ch": 1, "No": 0}, "change"),
        "any_drug_dose_changed": int(any(state in {"Up", "Down"} for state in drug_states)),
        "active_diabetes_drug_count": sum(state != "No" for state in drug_states),
        "insulin_used": int(record["insulin"] != "No"),
        "diabetes_med_prescribed": checked_indicator(record["diabetesMed"], {"Yes": 1, "No": 0}, "diabetesMed"),
        "a1c_test_recorded": checked_indicator(record["A1Cresult"], {"None": 0, "Norm": 1, ">7": 1, ">8": 1}, "A1Cresult"),
        "glucose_test_recorded": checked_indicator(record["max_glu_serum"], {"None": 0, "Norm": 1, ">200": 1, ">300": 1}, "max_glu_serum"),
        "age_group": checked_indicator(record["age"], AGE_GROUPS, "age"),
    }
    return {**record, **derived}


def load_cleaned_data():
    if not SOURCE.exists():
        raise FileNotFoundError("Run scripts/02_data_cleaning/data_cleaning.py first.")
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        records = list(reader)
    if not columns or not records:
        raise ValueError("The cleaned dataset is empty.")
    if any(None in record or None in record.values() for record in records):
        raise ValueError("A cleaned row does not match its header.")
    derived_names = {definition[0] for definition in FEATURE_DEFINITIONS}
    if derived_names & set(columns):
        raise ValueError("Derived feature columns already exist in the input.")
    return columns, records


def write_csv(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest() if SOURCE.exists() else None
    columns, records = load_cleaned_data()
    features = [extract_features(record) for record in records]
    feature_names = [definition[0] for definition in FEATURE_DEFINITIONS]
    distributions = {name: dict(Counter(str(record[name]) for record in features)) for name in feature_names}
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != source_hash:
        raise ValueError("The cleaned dataset changed during feature extraction.")
    if len({record["encounter_id"] for record in features}) != len(features):
        raise ValueError("Duplicate encounter identifiers require review.")
    dictionary = [
        {"feature": name, "type": kind, "source_columns": sources, "definition": definition}
        for name, kind, sources, definition in FEATURE_DEFINITIONS
    ]
    value_counts = [
        {"feature": name, "value": value, "encounters": count, "percent": round(100 * count / len(features), 4)}
        for name, counts in distributions.items() for value, count in sorted(counts.items())
    ]
    summary = {
        "input_file": SOURCE.relative_to(ROOT).as_posix(), "input_sha256": source_hash,
        "output_file": OUTPUT.relative_to(ROOT).as_posix(),
        "encounters": len(features), "original_columns": len(columns),
        "derived_columns": len(feature_names), "total_columns": len(columns) + len(feature_names),
        "target": "readmitted_30d", "target_counts": distributions["readmitted_30d"],
        "exclude_from_predictors": ["encounter_id", "patient_nbr", "readmitted", "readmitted_30d"],
        "feature_distributions": distributions,
        "general_change_without_explicit_dose_change": sum(
            record["medication_changed"] == 1 and record["any_drug_dose_changed"] == 0 for record in features
        ),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT, columns + feature_names, features)
    write_csv(REPORT_DIR / "feature_dictionary.csv", ["feature", "type", "source_columns", "definition"], dictionary)
    write_csv(REPORT_DIR / "feature_value_counts.csv", ["feature", "value", "encounters", "percent"], value_counts)
    with (REPORT_DIR / "feature_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print(f"Feature table: {len(features):,} encounters, {summary['total_columns']} columns")
    print(f"Added features: {len(feature_names)}; early-readmission cases: {summary['target_counts'].get('1', 0):,}")
    print(f"General change without explicit drug dose change: {summary['general_change_without_explicit_dose_change']:,}")
    print(f"Feature data: {OUTPUT}")
    print(f"Feature tables: {REPORT_DIR}")


if __name__ == "__main__":
    main()