# Step 3: Feature Extraction

## Objective

Translate cleaned encounter records into clearly defined variables for outcome analysis.
These features summarize recorded information; they do not establish why readmission occurs.

## Output Overview

- Encounters retained: **99,343**; no additional rows excluded.
- Original cleaned columns preserved: **47**.
- Derived columns added: **15**.
- Total columns: **62**; this is not a count of independent model predictors.
- Early-readmission cases (`readmitted_30d = 1`): **11,314**.

The cleaned input is unchanged. Feature extraction uses fixed rules and no model fitting.

## Feature Dictionary

| Feature | Type | Source | Calculation and interpretation |
| --- | --- | --- | --- |
| readmitted_30d | binary_target | readmitted | 1 for <30; 0 for >30 or NO. Never use either outcome column as a predictor. |
| total_previous_visits | count | number_outpatient, number_emergency, number_inpatient | Sum of the three recorded prior visit counts; not a measure of adherence. |
| prior_acute_visits | count | number_emergency, number_inpatient | Emergency plus inpatient visit counts; excludes outpatient visits. |
| medication_burden_band | category | num_medications | Low: 0-5; Moderate: 6-14; High: 15+. Counts inpatient medications, not verified long-term polypharmacy. |
| diag_1_group | category | diag_1 | Primary diagnosis: Diabetes (250.xx), Circulatory (390-459 or 785.xx), Respiratory (460-519 or 786.xx), Other, or Unknown. |
| diag_2_group | category | diag_2 | Secondary diagnosis grouped using the same ICD-9 rules as diag_1_group. |
| diag_3_group | category | diag_3 | Third diagnosis grouped using the same ICD-9 rules as diag_1_group. |
| medication_changed | binary | change | 1 for Ch; 0 for No. General recorded regimen-change flag, not necessarily an explicit dose change. |
| any_drug_dose_changed | binary | 21 retained diabetes drug columns | 1 if any drug is Up or Down; 0 otherwise. Not interchangeable with the general change flag. |
| active_diabetes_drug_count | count | 21 retained diabetes drug columns | Count drug fields with Steady, Up, or Down. Combination-drug fields count as one field, not separate ingredients. |
| insulin_used | binary | insulin | 1 for Steady, Up, or Down; 0 for No. |
| diabetes_med_prescribed | binary | diabetesMed | 1 for Yes; 0 for No. Mirrors the recorded diabetes-medication indicator. |
| a1c_test_recorded | binary | A1Cresult | 0 for None; 1 for Norm, >7, or >8. Test documentation, not a continuous HbA1c measurement. |
| glucose_test_recorded | binary | max_glu_serum | 0 for None; 1 for Norm, >200, or >300. Does not establish glycemic control. |
| age_group | category | age | Combine recorded age bands into Under 40, 40-59, 60-79, or 80+. Exact ages are not inferred. |

## Diagnosis Grouping

ICD-9 codes remain strings in the original columns. Grouping uses the numeric part before the decimal.
For example, 250.83 becomes Diabetes, 414 becomes Circulatory, and V27 becomes Other.
Unknown codes stay Unknown; unexpected code formats stop extraction instead of silently becoming Other.
The broad groups are intentionally coarse and are not a validated comorbidity index.

## Medication Change Is Not the Same as Dose Change

**19,102 encounters** have a general change flag but no retained drug marked Up or Down.
The two indicators are retained separately; neither implies medication adherence or a treatment effect.

## Selected Distributions

These are feature frequencies, not comparisons of readmission risk.

### medication_burden_band

| Value | Encounters | Percent |
| --- | ---: | ---: |
| Low | 4,938 | 4.97% |
| High | 50,879 | 51.22% |
| Moderate | 43,526 | 43.81% |

### diag_1_group

| Value | Encounters | Percent |
| --- | ---: | ---: |
| Diabetes | 8,661 | 8.72% |
| Other | 47,047 | 47.36% |
| Circulatory | 29,681 | 29.88% |
| Respiratory | 13,934 | 14.03% |
| Unknown | 20 | 0.02% |

### age_group

| Value | Encounters | Percent |
| --- | ---: | ---: |
| Under 40 | 6,263 | 6.30% |
| 40-59 | 26,667 | 26.84% |
| 60-79 | 47,390 | 47.70% |
| 80+ | 19,023 | 19.15% |

### medication_changed

| Value | Encounters | Percent |
| --- | ---: | ---: |
| 0 | 53,221 | 53.57% |
| 1 | 46,122 | 46.43% |

### any_drug_dose_changed

| Value | Encounters | Percent |
| --- | ---: | ---: |
| 0 | 72,323 | 72.80% |
| 1 | 27,020 | 27.20% |

## Modeling Guardrails

- Use `readmitted_30d` as the target only; exclude original `readmitted` from predictors to avoid outcome leakage.
- Exclude encounter and patient identifiers from predictors; use patient identifiers to separate evaluation groups.
- Assess risk at discharge: inpatient treatments and length of stay are not admission-time inputs.
- Avoid simultaneously using total visits and all its component counts in an unregularized regression.
- Choose between original and derived versions of age, medication count, change, insulin, diabetesMed, and lab indicators as appropriate.
- Test-recorded indicators overlap with their original lab categories; they are not independent evidence.
- Dose-change and active-drug indicators overlap with original drug fields; do not treat all columns as independent measures.
- Fit encoding, scaling, imputation, and any outcome-informed selection on training data only.
- Raw diagnosis codes and grouped diagnoses are alternative representations, not additive disease counts.

## Files

- [Feature table](../../data/processed/diabetes_features.csv): original cleaned fields plus derived columns.
- [feature_dictionary.csv](feature_dictionary.csv): definitions of the 15 derived columns.
- [feature_value_counts.csv](feature_value_counts.csv): every derived feature's values and frequencies.
- [feature_summary.json](feature_summary.json): dimensions, distributions, and input fingerprint.

For pandas ingestion, preserve identifiers and diagnosis codes as strings and use `keep_default_na=False`.
CSV stores labels, not Python types; load count/binary columns using the dictionary.

## Next Step

Compare readmission rates across candidate variables, quantify uncertainty, and investigate adjusted associations.
No feature-importance ranking, statistical testing, or predictive modeling has been completed in this step.
