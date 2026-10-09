# Step 5: Robustness and Predictive Importance

## Objective

Check how the findings depend on analytical assumptions and identify useful predictors in fixed models.
Predictive importance and adjusted association answer different questions. Neither establishes causation.

## Main Findings

- Leading inputs for expanded_logistic: **number_inpatient, discharge_disposition_id, medical_specialty**.
- Leading inputs for hist_gradient_boosting: **number_inpatient, discharge_disposition_id, insulin**.
- Discharge disposition describes the care setting/destination at discharge; its importance does not demonstrate outpatient care quality.
- Medication-change evidence is not consistent across choices: intervals include no association in **one_encounter_per_patient, expanded_adjustment**.
- Higher held-out performance remains exploratory and does not establish a clinically reliable decision system.

## Patient-Separated Model Comparison

Compare the original adjusted logistic model, an expanded regularized logistic model, and histogram gradient boosting.
The expanded models share the same 22 original/derived predictors so their comparison tests model form, not different input sets.
Additional inputs include secondary diagnoses, administrative categories, payer, and medical specialty.
The constant-risk baseline predicts the training prevalence for every test encounter.

Training patients: **55,992**; test patients: **13,998**.
Test encounters: **19,821**; patient overlap: **0**.
Preprocessing is fitted on training patients only. Identifiers and outcome labels are never predictors.
Model settings are fixed, without test-based hyperparameter or threshold tuning.
Histogram boosting uses 100 iterations, 15 leaves, and no random encounter-level early-stopping split.

The evaluation patients were already examined in the initial analysis. These comparisons are exploratory,
not a fresh untouched final test or external validation. Do not use the observed ranking to claim deployment readiness.

| Model | ROC-AUC | Average precision | Brier score |
| --- | ---: | ---: | ---: |
| initial_logistic | 0.626 | 0.189 | 0.0965 |
| constant_risk_baseline | 0.500 | 0.111 | 0.0990 |
| expanded_logistic | 0.657 | 0.213 | 0.0951 |
| hist_gradient_boosting | 0.668 | 0.226 | 0.0942 |

Average precision should be compared with test prevalence **0.111**.
Higher ROC-AUC/average precision and lower Brier score are preferable, but quantify different properties.

## Patient-Bootstrap Uncertainty

Resample whole test patients with replacement, retaining all encounters for each selected patient.
Use **200 draws** with seed 42 and percentile 95% intervals.
All models use the same draws for paired differences. Models are not retrained during bootstrap.
These intervals quantify held-out patient sampling uncertainty conditional on the fitted models,
not training variability, hyperparameter selection, or uncertainty across different hospital populations.

| Model | Metric | Estimate | Patient-bootstrap 95% interval |
| --- | --- | ---: | --- |
| initial_logistic | roc_auc | 0.6256 | 0.6087 to 0.6384 |
| initial_logistic | average_precision | 0.1888 | 0.1669 to 0.2079 |
| initial_logistic | brier_score | 0.0965 | 0.0926 to 0.1000 |
| constant_risk_baseline | roc_auc | 0.5000 | 0.5000 to 0.5000 |
| constant_risk_baseline | average_precision | 0.1113 | 0.1061 to 0.1165 |
| constant_risk_baseline | brier_score | 0.0990 | 0.0949 to 0.1029 |
| expanded_logistic | roc_auc | 0.6572 | 0.6418 to 0.6704 |
| expanded_logistic | average_precision | 0.2128 | 0.1915 to 0.2335 |
| expanded_logistic | brier_score | 0.0951 | 0.0914 to 0.0987 |
| hist_gradient_boosting | roc_auc | 0.6685 | 0.6536 to 0.6812 |
| hist_gradient_boosting | average_precision | 0.2262 | 0.2048 to 0.2460 |
| hist_gradient_boosting | brier_score | 0.0942 | 0.0906 to 0.0976 |

### Paired Differences

Differences are candidate minus reference. Positive ROC-AUC/AP and negative Brier differences favor the candidate.
An interval crossing zero does not clearly distinguish the models on that metric in this evaluation sample.

| Candidate versus reference | Metric | Difference | 95% interval |
| --- | --- | ---: | --- |
| hist_gradient_boosting versus expanded_logistic | roc_auc | 0.0113 | 0.0065 to 0.0169 |
| hist_gradient_boosting versus expanded_logistic | average_precision | 0.0134 | 0.0065 to 0.0210 |
| hist_gradient_boosting versus expanded_logistic | brier_score | -0.0009 | -0.0013 to -0.0006 |
| expanded_logistic versus initial_logistic | roc_auc | 0.0315 | 0.0208 to 0.0415 |
| expanded_logistic versus initial_logistic | average_precision | 0.0241 | 0.0160 to 0.0314 |
| expanded_logistic versus initial_logistic | brier_score | -0.0014 | -0.0019 to -0.0009 |
| hist_gradient_boosting versus initial_logistic | roc_auc | 0.0429 | 0.0336 to 0.0523 |
| hist_gradient_boosting versus initial_logistic | average_precision | 0.0374 | 0.0279 to 0.0468 |
| hist_gradient_boosting versus initial_logistic | brier_score | -0.0023 | -0.0028 to -0.0017 |

## Predictive Importance

Shuffle one input column across held-out encounters and measure the reduction in average precision and ROC-AUC.
Repeat **5 times** per input. Larger positive drops mean stronger reliance in that fitted model.
Zero or negative drops indicate little detectable benefit under this procedure, not proof of clinical irrelevance.
Permutation standard deviations measure shuffle variability; they are not 95% confidence intervals.
Row-wise permutations can create implausible combinations and break between-patient/within-patient structure.
Correlated inputs can substitute for one another, diluting individual importance.

![Model-specific predictive importance](predictive_importance.png)

### Top Predictors: expanded_logistic

| Predictor | Mean AP drop | Shuffle SD |
| --- | ---: | ---: |
| number_inpatient | 0.0589 | 0.0010 |
| discharge_disposition_id | 0.0350 | 0.0009 |
| medical_specialty | 0.0049 | 0.0011 |
| insulin | 0.0030 | 0.0006 |
| payer_code | 0.0017 | 0.0006 |
| diag_2_group | 0.0015 | 0.0003 |
| number_emergency | 0.0009 | 0.0002 |
| age_group | 0.0009 | 0.0006 |
| A1Cresult | 0.0009 | 0.0003 |
| medication_changed | 0.0006 | 0.0002 |

### Top Predictors: hist_gradient_boosting

| Predictor | Mean AP drop | Shuffle SD |
| --- | ---: | ---: |
| number_inpatient | 0.0677 | 0.0013 |
| discharge_disposition_id | 0.0482 | 0.0019 |
| insulin | 0.0048 | 0.0003 |
| medical_specialty | 0.0047 | 0.0008 |
| diag_1_group | 0.0045 | 0.0009 |
| payer_code | 0.0030 | 0.0006 |
| number_emergency | 0.0029 | 0.0004 |
| number_diagnoses | 0.0024 | 0.0007 |
| admission_type_id | 0.0023 | 0.0008 |
| diag_2_group | 0.0017 | 0.0004 |

### Grouped Importance

Shuffle related columns jointly using the same row permutation, preserving relationships within each group.
This reduces substitution inside a group but does not remove correlation between groups or establish a care mechanism.

| Model | Input group | Mean AP drop |
| --- | --- | ---: |
| expanded_logistic | prior_utilization | 0.0635 |
| expanded_logistic | care_context | 0.0398 |
| expanded_logistic | treatment | 0.0025 |
| expanded_logistic | clinical_burden | 0.0018 |
| expanded_logistic | demographics | 0.0013 |
| expanded_logistic | lab_results_and_testing | 0.0003 |
| hist_gradient_boosting | prior_utilization | 0.0773 |
| hist_gradient_boosting | care_context | 0.0500 |
| hist_gradient_boosting | clinical_burden | 0.0118 |
| hist_gradient_boosting | treatment | 0.0051 |
| hist_gradient_boosting | demographics | 0.0027 |
| hist_gradient_boosting | lab_results_and_testing | 0.0005 |

## Sensitivity of Adjusted Associations

- One encounter per patient: seed-42 random selection, not the first chronological admission.
- Log utilization: replace each prior visit count with log(1 + count), retaining extreme values.
- Expanded adjustment: add labs/procedures, grouped admission/discharge context, secondary diagnoses, and documentation indicators.
- Hospice-inclusive cohort: exclude recorded deaths but retain hospice discharges; apply the same cleaning and feature rules otherwise.

All sensitivity fits use patient-clustered standard errors and keep their own explicit study population.
Selecting one encounter per patient also changes encounter weighting; it is not solely a standard-error correction.
The log-utilization odds ratio is per one-unit increase in log(1 + visits), not per additional visit.
Do not compare its magnitude directly with the raw-count odds ratio.

| Scenario | Encounters | Parameter | Adjusted OR | Clustered 95% interval |
| --- | ---: | --- | ---: | --- |
| baseline_adjustment | 99,343 | number_inpatient | 1.309 | 1.292 to 1.327 |
| baseline_adjustment | 99,343 | number_diagnoses | 1.048 | 1.036 to 1.061 |
| baseline_adjustment | 99,343 | medication_changed | 0.941 | 0.891 to 0.994 |
| one_encounter_per_patient | 69,990 | number_inpatient | 1.461 | 1.424 to 1.499 |
| one_encounter_per_patient | 69,990 | number_diagnoses | 1.054 | 1.036 to 1.071 |
| one_encounter_per_patient | 69,990 | medication_changed | 0.996 | 0.925 to 1.073 |
| log_utilization | 99,343 | np.log1p(number_inpatient) | 2.068 | 1.988 to 2.152 |
| log_utilization | 99,343 | number_diagnoses | 1.040 | 1.027 to 1.053 |
| log_utilization | 99,343 | medication_changed | 0.940 | 0.890 to 0.994 |
| expanded_adjustment | 99,343 | number_inpatient | 1.305 | 1.288 to 1.323 |
| expanded_adjustment | 99,343 | number_diagnoses | 1.047 | 1.033 to 1.061 |
| expanded_adjustment | 99,343 | medication_changed | 0.950 | 0.899 to 1.004 |
| hospice_included_deaths_excluded | 100,114 | number_inpatient | 1.308 | 1.291 to 1.325 |
| hospice_included_deaths_excluded | 100,114 | number_diagnoses | 1.047 | 1.034 to 1.060 |
| hospice_included_deaths_excluded | 100,114 | medication_changed | 0.942 | 0.892 to 0.995 |

A stable direction supports robustness within these choices, not causality. A shift or interval crossing 1 limits certainty.
An interval crossing 1 does not prove no effect; changes in precision, weighting, or adjustment can alter the evidence.
Medication-change associations must not be described as proven protective treatment effects.

## Subgroup Evaluation

Report held-out metrics by age, gender, and race in subgroup_performance.csv.
Withhold metrics for groups with fewer than 30 events or 30 nonevents. These are point estimates without subgroup bootstrap intervals.
Differences may reflect prevalence, sample size, disease burden, or documentation. They do not establish fairness or justify race-based care allocation.

## Files

- [model_comparison.csv](model_comparison.csv): held-out model metrics.
- [bootstrap_intervals.csv](bootstrap_intervals.csv): whole-patient metric uncertainty.
- [paired_model_differences.csv](paired_model_differences.csv): paired bootstrap differences.
- [predictive_importance.csv](predictive_importance.csv): all individual predictor rankings by model and metric.
- [grouped_importance.csv](grouped_importance.csv): jointly permuted input-group importance.
- [sensitivity_odds_ratios.csv](sensitivity_odds_ratios.csv): adjusted estimates for each scenario.
- [subgroup_performance.csv](subgroup_performance.csv): stratified held-out metrics and sparse-group flags.
- [held_out_predictions.csv](held_out_predictions.csv): probabilities from every compared model.
- [validation_summary.json](validation_summary.json): inputs, fixed settings, source fingerprints, versions, and sensitivity specifications.

## Interpretation Boundary

The input-output relationship is predictive and associational. The connecting care channel remains hypothesized:
adherence, lifestyle, outpatient continuity, and intervention effects are not directly observed.
No external/temporal validation, cross-split model stability, clinical utility analysis, or deployable risk thresholds have been established.
