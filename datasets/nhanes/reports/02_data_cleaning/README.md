# Step 2: NHANES Data Cleaning

## What Was Done

Create a cleaned, selected-field table and a separate response-reason table while retaining the
entire demographic survey universe. Missingness is not automatically converted to zero.

| Measure | Result |
| --- | ---: |
| Full participant universe retained | 9,254 |
| Selected original fields | 49 |
| Cleaned columns, including three domain/status flags | 52 |
| Primary measured-HbA1c domain | 804 |
| Uncertain pregnancy statuses in the domain | 2 |
| Domain excluding these uncertain statuses | 802 |
| Invalid values after parser correction | 0 |
| Contradictory gate/follow-up responses | 0 |

The 49 fields cover demographics, design, diagnosis, treatment, monitoring, BMI, all five activity
domains, and healthcare access/utilization. The other original fields remain in the unchanged merged input.
There is no predictor-based complete-case exclusion or saved 804-person-only survey file.

## Values Versus Reasons

The cleaned table stores valid numeric measurements and category codes. Refused, Don't know,
unavailable measurements, and unusable values are blank. The matching response table explains why.
Join these tables by SEQN, never by assumed row position alone. `identifier_status` records the ID check;
all other response columns use the original variable names.

| Status | Meaning | Example |
| --- | --- | --- |
| observed | A valid recorded value | DID260=0 remains an explicit Never response |
| refused / dont_know | Variable-specific special response | DID260=999 becomes blank plus dont_know |
| skip_no_activity | Follow-up blank after a No activity gate | PAQ605=2 with blank days/minutes |
| gate_unknown | Follow-up blank with an unavailable gate | Unknown activity status does not establish zero |
| skip_no_usual_diabetes_doctor | No usual diabetes professional | Blank DID250 does not mean no healthcare visits |
| missing_required_unit | Positive check count without its unit | Daily frequency cannot yet be derived |
| skip_never_checks_glucose | Explicit zero checks; no unit needed | DID260=0 with blank DIQ260U |
| not_age_eligible / not_released_for_group | Age or release restriction | Adult education for a child; pregnancy outside the released group |
| not_examined / no_component_record | Observed module/exam absence | Missing examination information |
| outside_diagnosed_diabetes_domain | Blank outside the selected diabetes scope | Does not universally prove the question was inapplicable |
| not_recorded | Blank without a more specific supported reason | Do not invent an answer |
| top_coded | Value represents an upper category | Age 80+, poverty ratio 5+, admissions 6+ |
| age_below_one_interval | Diagnosed below age one | DID040=666 is not an exact age of 666 or an invented exact zero |
| cannot_ascertain | Pregnancy status 3 | Included in primary domain and excluded in sensitivity domain |
| provider_did_not_specify_goal | Recorded A1C goal category 6 | A meaningful answer, not a numeric HbA1c target |
| invalid_value / routing_conflict | Requires review | None found in the current data after parser repair |

These reasons use observed eligibility and gates. They do not identify every true reason for missingness.
No clinical interpretation is attached to a missing value beyond the supported codebook meaning.

## Specific Cleaning Rules

1. Decode each variable's Refused/Don't know codes separately; preserve valid 7s, 9s, and zeros elsewhere.
2. Validate categorical domains and basic numeric ranges without trimming genuine high values.
3. Keep activity follow-ups blank when skipped; record the gate reason. Feature extraction can later
   derive zero activity only when No justifies it, not by replacing all blanks.
4. Preserve glucose-check counts and unit codes. Flag missing required units; conversion comes in Step 3.
5. Preserve valid survey design and ID fields, and retain measured LBXGH without imputation or rescaling.
6. Flag the primary domain: age 20+, reported diagnosed diabetes, no known pregnancy, measured HbA1c,
   positive MEC weight, and available stratum/PSU. Do not discard out-of-domain survey participants.
7. Preserve pregnancy uncertainty explicitly and provide the separate 802-person sensitivity flag.
8. Preserve top-coded values as categories/limits, not exact unbounded measurements.

HUQ051 remains a coded visit band. HUD080=6 remains six or more admissions.
Nothing in this stage converts these categories into exact visit counts or measures adherence.

## SAS Reader Correction

The installed pandas/NumPy combination returned `5.397605346934028e-79` for certain encoded numeric zeros.
An original DID260 record was checked at the byte level: all eight SAS numeric bytes were zero.
The acquisition parser now restores only that exact artifact to 0 and records counts by component.
Original XPT files are unchanged. The merged file and audit were refreshed before cleaning.
This is a verified file-reading correction, not a clinical imputation or replacement of real small values.

Without this correction, Never glucose checks and other valid zeros would be incorrectly flagged as invalid.
The adult diabetes domain and measured HbA1c summaries remain unchanged after the correction.

## Files

- [Cleaned selected fields](../../data/processed/nhanes_2017_2018_cleaned.csv)
- [Response reasons by participant](../../data/processed/nhanes_2017_2018_response_status.csv)
- [cleaning_rules.csv](cleaning_rules.csv): allowed codes, ranges, and special responses for every selected field.
- [cleaning_changes.csv](cleaning_changes.csv): before/after blanks and changed-value counts.
- [response_status_counts.csv](response_status_counts.csv): reasons in the full universe and primary domain.
- [cleaning_summary.json](cleaning_summary.json): dimensions, domain counts, issues, and input/output fingerprints.

## Validation and Next Step

Six acquisition tests cover safe joins and the reader correction. Eight cleaning tests cover special codes,
skips, units, genuine zeros, routing conflicts, outcome missingness, design preservation, and sensitivity flags.

Next: derive unit-aware monitoring frequencies and activity measures, define analytical categories, and
preserve the design fields for survey-aware analysis. No weighted population estimate or fitted model exists yet.