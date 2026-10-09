# Step 2: Data Cleaning

## Objective

Create a consistent study cohort for analyzing recorded 30-day readmission.
The original CSV is retained unchanged. All changes apply to a separate output file.

## Before and After

| Measure | Before | After |
| --- | ---: | ---: |
| Encounters | 101,766 | 99,343 |
| Columns | 50 | 47 |

The cleaned cohort contains **69,990 unique patients**.
There are **16,341 patients with multiple retained encounters**.

## Cleaning Decisions

1. Exclude expired/hospice discharges: codes 11, 13, 14, 19, 20, and 21.
   Hospice exclusion defines the study scope; hospice patients are not inherently unable to return.
2. Drop `weight` because 96.86% of raw encounters lack it. No weight values are imputed.
3. Drop `examide` and `citoglipton` after verifying that each is constant.
4. Replace `?` and blank categorical fields with `Unknown`.
5. Replace gender category `Unknown/Invalid` with `Unknown`; retain these encounters.
6. Group unavailable administrative categories as `Unknown`:
   admission type codes 5/6/8; admission source codes 9/15/17/20/21; discharge codes 18/25/26.
   These codes are defined as unavailable, NULL, unmapped, or unknown/invalid in the source mapping.
7. Validate numeric counts as nonnegative integers, retaining their values and extreme observations.
8. Preserve patient and encounter identifiers, ICD-9 strings, original readmission labels, and lab `None` categories.

No modal imputation, scaling, patient deduplication, or feature extraction is performed.
Transformations are fixed rules; they do not learn values from outcomes or the full dataset.

## Encounter Exclusions

| Discharge code | Excluded encounters |
| --- | ---: |
| 11 | 1,642 |
| 13 | 399 |
| 14 | 372 |
| 19 | 8 |
| 20 | 2 |

**Total excluded: 2,423 encounters.**
These are the only row exclusions. Multiple encounters for one patient are retained.

## Changed Categories

Counts below refer to retained encounters, not the entire original dataset.
One encounter may appear under more than one changed column; these counts must not be summed as excluded patients.

| Variable | Change | Affected encounters |
| --- | --- | ---: |
| admission_source_id | unavailable administrative category | 6,854 |
| admission_type_id | unavailable administrative category | 10,144 |
| diag_1 | missing category | 20 |
| diag_2 | missing category | 356 |
| diag_3 | missing category | 1,419 |
| discharge_disposition_id | unavailable administrative category | 4,680 |
| gender | invalid gender category | 3 |
| medical_specialty | missing category | 48,616 |
| payer_code | missing category | 39,398 |
| race | missing category | 2,234 |

## Outcomes in the Cleaned Cohort

| Recorded readmission label | Encounters |
| --- | ---: |
| <30 | 11,314 |
| >30 | 35,502 |
| NO | 52,527 |

The early-readmission rate is **11.39%**.
Readmission is an observed hospital outcome, not proof of a management failure.

## How to Read the Cleaned CSV

- `Unknown` indicates unavailable categorical information; it is not a measured clinical value.
- Lab `None` means no result recorded, not a normal lab result.
- Administrative IDs remain categorical code strings; `Unknown` makes these mixed-label categories explicit.
- ICD-9 codes and patient/encounter identifiers must be loaded as strings, not continuous numbers.
- Count columns can be loaded as integers. CSV itself does not store Python data types.
- With pandas, use `keep_default_na=False` to preserve literal `None` categories.
- Patient identifiers are retained for grouped evaluation, not as predictive features.

## Files and Checks

- [Cleaned dataset](../../data/processed/diabetes_cleaned.csv).
- [cleaning_changes.csv](cleaning_changes.csv): one row per changed column and reason.
- [cleaning_summary.json](cleaning_summary.json): cohort counts, unknown categories, column types, and source fingerprint.

Checks run before export: identifiers present and unique per encounter, valid outcome labels,
nonnegative integer counts, no unresolved question marks/blanks, exclusions applied,
and input/output row counts reconciled. Repeated patients are allowed.

## Next Step

Define and validate features using this cleaned cohort. Model-ready encoding and any learned
preprocessing will be fitted on training data only. Feature extraction and modeling are still pending.
