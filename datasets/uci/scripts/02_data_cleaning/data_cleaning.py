"""Step 2: clean the study cohort while preserving the original dataset."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "raw" / "diabetic_data.csv"
DATA_OUTPUT = ROOT / "data" / "processed" / "diabetes_cleaned.csv"
REPORT_DIR = ROOT / "reports" / "02_data_cleaning"
EXCLUDED_DISCHARGES = {"11", "13", "14", "19", "20", "21"}
DROP_COLUMNS = {"weight", "examide", "citoglipton"}
NUMERIC_COLUMNS = {
    "time_in_hospital", "num_lab_procedures", "num_procedures",
    "num_medications", "number_outpatient", "number_emergency",
    "number_inpatient", "number_diagnoses",
}
UNKNOWN_ADMIN_CODES = {
    "admission_type_id": {"5", "6", "8"},
    "admission_source_id": {"9", "15", "17", "20", "21"},
    "discharge_disposition_id": {"18", "25", "26"},
}


def load_data():
    with SOURCE.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        records = list(reader)
    if not columns or not records:
        raise ValueError("The source dataset is empty or has no header.")
    required = DROP_COLUMNS | NUMERIC_COLUMNS | set(UNKNOWN_ADMIN_CODES) | {
        "encounter_id", "patient_nbr", "readmitted", "gender",
    }
    if not required.issubset(columns):
        raise ValueError(f"Missing required columns: {sorted(required - set(columns))}")
    if any(None in record or None in record.values() for record in records):
        raise ValueError("A source row does not match the CSV header.")
    for column in {"examide", "citoglipton"}:
        if len({record[column] for record in records}) != 1:
            raise ValueError(f"{column} is no longer constant; review its removal.")
    return columns, records


def clean_value(column, raw):
    value = raw.strip()
    if column in NUMERIC_COLUMNS:
        number = int(value)
        if number < 0:
            raise ValueError(f"Negative value in {column}: {value}")
        return str(number), "numeric_format" if value != str(number) else "unchanged"
    if value in {"?", ""}:
        return "Unknown", "missing_category"
    if column == "gender" and value == "Unknown/Invalid":
        return "Unknown", "invalid_gender_category"
    if value in UNKNOWN_ADMIN_CODES.get(column, set()):
        return "Unknown", "unavailable_administrative_category"
    return value, "trimmed_whitespace" if value != raw else "unchanged"


def clean_records(columns, records):
    kept_columns = [column for column in columns if column not in DROP_COLUMNS]
    cleaned = []
    changes = Counter()
    excluded_codes = Counter()
    for record in records:
        discharge = record["discharge_disposition_id"].strip()
        if discharge in EXCLUDED_DISCHARGES:
            excluded_codes[discharge] += 1
            continue
        cleaned_record = {}
        for column in kept_columns:
            value, reason = clean_value(column, record[column])
            cleaned_record[column] = value
            if reason != "unchanged":
                changes[(column, reason)] += 1
        cleaned.append(cleaned_record)
    return kept_columns, cleaned, changes, excluded_codes


def validate_cleaned(records):
    if not records:
        raise ValueError("Cleaning removed every encounter.")
    encounter_ids = [record["encounter_id"] for record in records]
    if len(set(encounter_ids)) != len(encounter_ids):
        raise ValueError("Duplicate encounter identifiers require review before export.")
    for record in records:
        if not record["encounter_id"].isdigit() or not record["patient_nbr"].isdigit():
            raise ValueError("Missing or invalid encounter/patient identifier.")
        if record["readmitted"] not in {"NO", ">30", "<30"}:
            raise ValueError("Unexpected readmission label.")
        if record["discharge_disposition_id"] in EXCLUDED_DISCHARGES:
            raise ValueError("An excluded discharge remained in the study cohort.")
        if any(value in {"?", ""} for value in record.values()):
            raise ValueError("An unresolved missing marker remained after cleaning.")


def write_table(path, columns, records):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)


def build_summary(raw_columns, raw_records, columns, cleaned, changes, excluded_codes):
    outcomes = Counter(record["readmitted"] for record in cleaned)
    patients = Counter(record["patient_nbr"] for record in cleaned)
    return {
        "source_file": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "cleaned_file": DATA_OUTPUT.relative_to(ROOT).as_posix(),
        "raw_encounters": len(raw_records), "cleaned_encounters": len(cleaned),
        "excluded_encounters": sum(excluded_codes.values()),
        "excluded_counts_by_discharge_code": dict(sorted(excluded_codes.items())),
        "raw_columns": len(raw_columns), "cleaned_columns": len(columns),
        "dropped_columns": sorted(DROP_COLUMNS),
        "unique_patients": len(patients),
        "patients_with_multiple_encounters": sum(count > 1 for count in patients.values()),
        "readmission_counts": dict(outcomes),
        "early_readmission_percent": round(100 * outcomes["<30"] / len(cleaned), 4),
        "unknown_category_counts": {
            column: sum(record[column] == "Unknown" for record in cleaned)
            for column in columns if column not in NUMERIC_COLUMNS
        },
        "lab_None_counts": {
            column: sum(record[column] == "None" for record in cleaned)
            for column in ("A1Cresult", "max_glu_serum")
        },
        "changes": [
            {"column": column, "reason": reason, "affected_encounters": count}
            for (column, reason), count in sorted(changes.items())
        ],
        "numeric_columns": sorted(NUMERIC_COLUMNS),
        "categorical_administrative_columns": sorted(UNKNOWN_ADMIN_CODES),
        "identifier_columns": ["encounter_id", "patient_nbr"],
    }


def main():
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    raw_columns, raw_records = load_data()
    columns, cleaned, changes, excluded_codes = clean_records(raw_columns, raw_records)
    validate_cleaned(cleaned)
    if len(cleaned) + sum(excluded_codes.values()) != len(raw_records):
        raise ValueError("Cohort counts do not reconcile with the source.")
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != source_hash:
        raise ValueError("The source changed during cleaning; rerun against a stable file.")
    summary = build_summary(raw_columns, raw_records, columns, cleaned, changes, excluded_codes)
    DATA_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    write_table(DATA_OUTPUT, columns, cleaned)
    write_table(REPORT_DIR / "cleaning_changes.csv", ["column", "reason", "affected_encounters"], summary["changes"])
    with (REPORT_DIR / "cleaning_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print(f"Cleaned cohort: {len(cleaned):,} encounters, {len(columns)} columns")
    print(f"Excluded expired/hospice encounters: {summary['excluded_encounters']:,}")
    print(f"Early readmissions: {summary['readmission_counts']['<30']:,} ({summary['early_readmission_percent']:.2f}%)")
    print(f"Cleaned data: {DATA_OUTPUT}")
    print(f"Cleaning tables: {REPORT_DIR}")


if __name__ == "__main__":
    main()