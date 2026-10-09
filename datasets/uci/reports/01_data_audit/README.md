# Step 1: Dataset Understanding and Quality Audit

## Objective

Inspect the hospital encounters before deciding how to clean the data.
The outcome of interest is recorded readmission within 30 days.
All values below describe the raw data unless a provisional cohort is explicitly named.

## Dataset Overview

| Measure | Result |
| --- | ---: |
| Hospital encounters (rows) | 101,766 |
| Variables (columns) | 50 |
| Unique patients | 71,518 |
| Patients with multiple encounters | 16,773 |
| Duplicate encounter identifiers | 0 |
| Exact duplicate rows | 0 |

An encounter is a hospital visit, not a unique patient. Repeated encounters are not automatically duplicates.

## Recorded Outcomes

| Label | Meaning | Encounters | Percent of raw encounters |
| --- | --- | ---: | ---: |
| <30 | Readmission within 30 days | 11,357 | 11.16% |
| >30 | Readmission after 30 days | 35,545 | 34.93% |
| NO | No recorded readmission | 54,864 | 53.91% |

No recorded readmission does not establish that the patient never returned to another hospital.
Readmission alone does not establish poor diabetes management.

## Provisional Study Cohort

Expired and hospice discharge categories are excluded from this provisional analysis population.
Hospice exclusion defines the study scope; it does not mean hospice patients cannot be readmitted.
- Excluded encounters: **2,423**.
- Remaining encounters: **99,343**.
- Early readmissions: **11,314**.
- Early readmission rate: **11.39%**.

| Excluded discharge code | Description |
| --- | --- |
| 11 | Expired |
| 13 | Hospice / home |
| 14 | Hospice / medical facility |
| 19 | Expired at home. Medicaid only, hospice. |
| 20 | Expired in a medical facility. Medicaid only, hospice. |
| 21 | Expired, place unknown. Medicaid only, hospice. |

The audit computes these counts only. It does not save a cleaned dataset or remove rows from the source.

## Missing Values and Cleaning Decisions to Consider

Missing means a question mark (`?`) or a blank field. Lab category `None` is preserved separately.

| Variable | Missing encounters | Missing percentage |
| --- | ---: | ---: |
| weight | 98,569 | 96.86% |
| medical_specialty | 49,949 | 49.08% |
| payer_code | 40,256 | 39.56% |
| race | 2,273 | 2.23% |
| diag_3 | 1,423 | 1.40% |
| diag_2 | 358 | 0.35% |
| diag_1 | 21 | 0.02% |

- Consider excluding weight from modeling because it is mostly missing.
- Preserve unknown specialty, payer, race, and diagnosis categories rather than inventing observations.
- `A1Cresult` and `max_glu_serum`: `None` means no test result recorded, not a normal result.
- Review `Unknown/Invalid` gender values as a separate data-quality category.
- Constant variables: examide, citoglipton. They cannot distinguish outcomes in these data.

## Numeric Fields

The middle 50% of observations lie between Q25 and Q75. The median is the middle value.
Invalid integers and negative counts are checks to investigate, not automatic deletion rules.

| Variable | Min | Q25 | Median | Q75 | Max | Invalid integers | Negative values |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| time_in_hospital | 1 | 2.0 | 4.0 | 6.0 | 14 | 0 | 0 |
| num_lab_procedures | 1 | 31.0 | 44.0 | 57.0 | 132 | 0 | 0 |
| num_procedures | 0 | 0.0 | 1.0 | 2.0 | 6 | 0 | 0 |
| num_medications | 1 | 10.0 | 15.0 | 20.0 | 81 | 0 | 0 |
| number_outpatient | 0 | 0.0 | 0.0 | 0.0 | 42 | 0 | 0 |
| number_emergency | 0 | 0.0 | 0.0 | 0.0 | 76 | 0 | 0 |
| number_inpatient | 0 | 0.0 | 0.0 | 1.0 | 21 | 0 | 0 |
| number_diagnoses | 1 | 6.0 | 8.0 | 9.0 | 16 | 0 | 0 |

## Administrative Codes

Admission and discharge identifiers represent categories, not ordered numeric measurements.
- Unmapped values in `admission_source_id`: None.
- Unmapped values in `admission_type_id`: None.
- Unmapped values in `discharge_disposition_id`: None.

## Report Files

- [column_audit.csv](column_audit.csv): one row per variable, its analytical role, distinct values, and missingness.
- [numeric_summary.csv](numeric_summary.csv): distributions and parsing checks for numeric count fields.
- [audit_summary.json](audit_summary.json): detailed counts, category frequencies, cohort definition, and source fingerprint.

### Column Audit Glossary

- `role`: intended analytical type; identifiers are not model predictors.
- `distinct_raw_values`: number of different original values, including missing markers.
- `question_mark_count` / `blank_count`: counts of the two explicit missing markers.
- `missing_percent`: percentage of raw encounters containing either missing marker.
- `literal_None_count`: count of the literal category `None`, separate from missing markers.
- `constant`: true if every encounter has the same original value.

## Next Step

Document and implement cleaning decisions, retain patient identifiers for grouped evaluation,
and save the cleaned data separately. No imputation, feature extraction, or modeling has been performed in this step.
