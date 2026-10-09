# Step 1: NHANES Dataset Audit

## What Was Acquired

Six official 2017-2018 components: DEMO_J (demographics/design), DIQ_J (diabetes), GHB_J (measured HbA1c),
BMX_J (body measurements), PAQ_J (activity), and HUQ_J (utilization/access).
All components have unique, nonmissing SEQN identifiers. Demographic left joins keep participants
without measurements instead of dropping them before eligibility and missingness can be assessed.

The merged uncleaned file contains **9,254 participants and 145 variables**.
No UCI records were used or modified.

## Provisional Cohort Flow

| Rule | Remaining participants | Excluded at this step |
| --- | ---: | ---: |
| Demographic universe | 9,254 | 0 |
| Age 20+ | 5,569 | 3,685 |
| Reported diagnosed diabetes (DIQ010=1) | 876 | 4,693 |
| Exclude known pregnancy | 876 | 0 |
| Measured HbA1c available | 804 | 72 |
| Positive MEC weight | 804 | 0 |
| Survey stratum and PSU available | 804 | 0 |

This is an audit domain, not a saved cleaned clinical cohort. Its definition can still be reviewed.
Retain the full merged universe for later domain analysis.

## HbA1c in the Provisional Domain

| Sample measure | Result |
| --- | ---: |
| Mean measured HbA1c | 7.40% |
| Median measured HbA1c | 7.00% |
| Minimum / maximum | 4.1% / 16.2% |
| HbA1c >=8% | 218 participants |
| Represented strata | 15 |
| Represented stratum-PSU pairs | 30 |

These are **unweighted sample descriptions**, not national population estimates or clinical judgments.
The >=8% cutoff is exploratory and does not encode each participant's appropriate clinical target.
The 72 adults without measured HbA1c must not be assigned a normal outcome.

## Data Issues to Address Next

1. **Questionnaire routing:** blank DID250 may mean there is no usual diabetes doctor, not zero visits.
2. **Activity skips:** days/minutes can be blank when activity was reported No; use the gate question before assigning zero.
3. **Refused/don't know:** 7/9, 77/99, 777/999, or 7777/9999 have variable-specific meanings. Never recode them globally.
4. **Frequency units:** glucose-check counts require DIQ260U (day/week/month/year) before comparison.
5. **Categorical utilization:** HUQ051 is a band, not a numeric visit count; HUD080=6 means six or more admissions.
6. **Outcome confusion:** DIQ280 is self-reported past A1C, whereas LBXGH is the examination result. These are not interchangeable.
7. **Top coding:** RIDAGEYR=80 means 80+, and INDFMPIR=5 means at least 5 times the poverty threshold.
8. **Pregnancy:** RIDEXPRG is only released for women 20-44. Two domain members have status 3; missing values outside that eligibility group are structural.
9. **Treatment:** insulin/pill use measures treatment, not medication adherence or a causal effect on HbA1c.
10. **Survey design:** use MEC weights and the full strata/PSU structure. Preserve design fields throughout cleaning.

The laboratory module is eligible from age 12; PAQ is eligible from age 18; adult education is released from age 20.
Whole-universe missingness therefore includes ineligibility and absent component records as well as item nonresponse.
The audit separates universe and domain missingness but does not yet classify each missing value by cause.

## Tables and How to Read Them

- [cohort_flow.csv](cohort_flow.csv): sequential selection counts; exclusions are conditional on earlier rules.
- [variable_audit.csv](variable_audit.csv): every merged field, source module, missingness in the universe/domain, and analytical role.
- [variable_dictionary.csv](variable_dictionary.csv): selected fields with definitions and key cautions.
- [cohort_value_counts.csv](cohort_value_counts.csv): original values and frequencies in the provisional domain, including sentinel codes and blanks.
- [audit_summary.json](audit_summary.json): cohort/design counts, unweighted HbA1c descriptions, and merged-data fingerprint.
- [Component inventory](../00_data_acquisition/source_inventory.csv): official URLs, component counts, and raw hashes.
- [Join audit](../00_data_acquisition/join_audit.csv): participants present or absent in each module.

Missingness in variable_audit counts blank/NaN values only; sentinel codes remain observed until cleaning.
No imputation, survey-weighted population estimates, engineered features, hypothesis tests, or fitted models have been performed.

## Next Step

Implement variable-specific cleaning rules and explicitly distinguish skip-derived zeros, unknown answers,
and unavailable measurements. Then define features and a survey-aware outcome-analysis plan.