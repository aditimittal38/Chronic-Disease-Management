"""Step 1: audit the UCI diabetes data without modifying source records."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median, quantiles

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "reports" / "01_data_audit"
EXCLUDED_DISCHARGES = {"11", "13", "14", "19", "20", "21"}
NUMERIC_COLUMNS = (
	"time_in_hospital", "num_lab_procedures", "num_procedures",
	"num_medications", "number_outpatient", "number_emergency",
	"number_inpatient", "number_diagnoses",
)
ID_COLUMNS = {"encounter_id", "patient_nbr"}
ADMIN_COLUMNS = {
	"admission_type_id", "discharge_disposition_id", "admission_source_id",
}


def read_mappings(path):
	mappings = {}
	section = None
	with path.open(newline="", encoding="utf-8-sig") as handle:
		for row in csv.reader(handle):
			if not row or not row[0].strip():
				continue
			key = row[0].strip()
			if key in ADMIN_COLUMNS:
				section = key
				mappings[section] = {}
			elif section is not None:
				mappings[section][key] = row[1].strip()
	return mappings


def write_csv(path, rows):
	with path.open("w", newline="", encoding="utf-8") as handle:
		writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
		writer.writeheader()
		writer.writerows(rows)


def load_records(source):
	with source.open(newline="", encoding="utf-8-sig") as handle:
		reader = csv.DictReader(handle)
		columns = reader.fieldnames
		records = list(reader)
	if not records or columns is None:
		raise ValueError("The dataset must have a header and at least one record.")
	if any(None in record or None in record.values() for record in records):
		raise ValueError("Found records whose field count differs from the header.")
	missing_columns = (set(NUMERIC_COLUMNS) | ID_COLUMNS | ADMIN_COLUMNS | {"readmitted"}) - set(columns)
	if missing_columns:
		raise ValueError(f"Required columns are absent: {sorted(missing_columns)}")
	return columns, records


def column_role(column):
	if column in ID_COLUMNS:
		return "identifier_not_predictor"
	if column == "readmitted":
		return "outcome"
	if column in ADMIN_COLUMNS:
		return "administrative_category"
	if column.startswith("diag_"):
		return "ICD9_code_keep_as_string"
	return "numeric_count" if column in NUMERIC_COLUMNS else "categorical"


def audit_columns(columns, records):
	column_audit = []
	category_counts = {}
	for column in columns:
		counts = Counter(record[column] for record in records)
		missing = counts.get("?", 0) + counts.get("", 0)
		column_audit.append({
			"column": column,
			"role": column_role(column),
			"distinct_raw_values": len(counts),
			"question_mark_count": counts.get("?", 0),
			"blank_count": counts.get("", 0),
			"missing_percent": round(100 * missing / len(records), 4),
			"literal_None_count": counts.get("None", 0),
			"constant": len(counts) == 1,
		})
		if column not in ID_COLUMNS and column not in NUMERIC_COLUMNS:
			category_counts[column] = dict(counts)
	return column_audit, category_counts


def audit_numeric_column(column, records):
	values = []
	invalid = 0
	missing = 0
	for record in records:
		raw = record[column]
		if raw in {"?", ""}:
			missing += 1
			continue
		try:
			values.append(int(raw))
		except ValueError:
			invalid += 1
	quartiles = quantiles(values, n=4, method="inclusive") if len(values) > 1 else [None] * 3
	return {
		"column": column, "valid_count": len(values),
		"missing_count": missing, "invalid_integer_count": invalid,
		"negative_count": sum(value < 0 for value in values),
		"min": min(values) if values else None,
		"q25": quartiles[0], "median": median(values) if values else None,
		"q75": quartiles[2], "max": max(values) if values else None,
		"mean": round(mean(values), 4) if values else None,
	}


def main():
	source = DATA_DIR / "diabetic_data.csv"
	columns, records = load_records(source)
	mappings = read_mappings(DATA_DIR / "IDS_mapping.csv")
	total = len(records)
	patients = Counter(record["patient_nbr"] for record in records)
	outcome_counts = Counter(record["readmitted"] for record in records)
	unexpected_outcomes = set(outcome_counts) - {"NO", ">30", "<30"}
	if unexpected_outcomes:
		raise ValueError(f"Unexpected outcome labels: {sorted(unexpected_outcomes)}")
	column_audit, category_counts = audit_columns(columns, records)
	numeric_audit = [audit_numeric_column(column, records) for column in NUMERIC_COLUMNS]
	cohort = [record for record in records if record["discharge_disposition_id"] not in EXCLUDED_DISCHARGES]
	early_readmissions = sum(record["readmitted"] == "<30" for record in cohort)
	observed = {
		"raw_encounters": total, "total_columns": len(columns),
		"excluded_encounters": total - len(cohort),
		"eligible_encounters": len(cohort),
		"eligible_30_day_readmissions": early_readmissions,
	}
	summary = {
		"source_file": str(source.relative_to(ROOT)),
		"source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
		**observed,
		"unique_patients": len(patients),
		"patients_with_multiple_encounters": sum(count > 1 for count in patients.values()),
		"duplicate_encounter_ids": total - len({record["encounter_id"] for record in records}),
		"exact_duplicate_rows": total - len({tuple(record[column] for column in columns) for record in records}),
		"raw_outcome_counts": dict(outcome_counts),
		"raw_30_day_readmission_percent": round(100 * outcome_counts["<30"] / total, 4),
		"eligible_30_day_readmission_percent": round(100 * early_readmissions / len(cohort), 4) if cohort else None,
		"provisional_exclusion_codes": {code: mappings["discharge_disposition_id"][code] for code in sorted(EXCLUDED_DISCHARGES, key=int)},
		"unmapped_administrative_codes": {
			column: sorted({record[column] for record in records} - set(mappings[column]))
			for column in sorted(ADMIN_COLUMNS)
		},
		"constant_columns": [row["column"] for row in column_audit if row["constant"]],
		"category_counts": category_counts,
		"interpretation_notes": [
			"Audit only: no records have been cleaned, imputed, or exported as a modeling cohort.",
			"Question marks and blanks count as missing; literal None lab categories are preserved.",
			"The provisional cohort excludes expired/hospice discharges; hospice exclusion is a study-design decision.",
			"Early readmission is an observed outcome, not proof of poor disease management.",
			"Patients must not overlap between training and evaluation data.",
		],
	}
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
	write_csv(OUTPUT_DIR / "column_audit.csv", column_audit)
	write_csv(OUTPUT_DIR / "numeric_summary.csv", numeric_audit)
	with (OUTPUT_DIR / "audit_summary.json").open("w", encoding="utf-8") as handle:
		json.dump(summary, handle, indent=2)

	print(f"Raw data: {total:,} encounters, {len(columns)} columns, {len(patients):,} patients")
	print(f"Provisional eligible cohort: {len(cohort):,}; early readmissions: {early_readmissions:,}")
	print(f"Early readmission rate in provisional cohort: {summary['eligible_30_day_readmission_percent']:.2f}%")
	print(f"Duplicate encounter IDs: {summary['duplicate_encounter_ids']}; exact duplicate rows: {summary['exact_duplicate_rows']}")
	print("Missing values:")
	for row in sorted(column_audit, key=lambda item: item["missing_percent"], reverse=True):
		if row["missing_percent"]:
			print(f"  {row['column']}: {row['missing_percent']:.2f}%")
	print(f"Reports: {OUTPUT_DIR}")


if __name__ == "__main__":
	main()
