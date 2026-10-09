# Verification of the Project Presentation

Reference: [original PDF](../../reference/Chronic%20Disease%20Management%20Analytics_%20Diabetes.pdf).
The original code and exact regression specification are unavailable.

## Verdict

The cohort counts, missingness, medication bands, descriptive rates, and listed full-encounter
hypothesis-test statistics are numerically supported. Causal interpretations and some variable
descriptions need correction. Adjusted estimates are broadly similar but not identical; the exact
original regression cannot be certified without its formula, feature definitions, and covariance method.

## Confirmed Results

- 101,766 encounters, 50 columns; 2,423 exclusions; 99,343 retained encounters.
- 11,314 early readmissions, 11.39% baseline.
- Low/Moderate/High medication bands: 4,938 / 43,526 / 50,879 encounters.
- Their rates: 7.61% / 10.28% / 12.70%.
- No prior inpatient visits: 8.59%; two or more: 22.02%; age 80+: 12.47%.
- Raw missingness: weight 96.86%, specialty 49.08%, payer 39.56%, race 2.23%, diagnoses 0.02%/0.35%/1.40%.

| PDF statistic | Direct calculation | Verdict |
| --- | ---: | --- |
| Medication bands chi-square 209.17 | 209.171043 | Matches rounding |
| Insulin chi-square 199.30 | 199.299886 | Matches rounding |
| Age chi-square 133.60 | 133.599255 | Matches ten original age bands |
| A1C chi-square 42.56 | 42.557541 | Matches rounding |
| Inpatient Mann-Whitney U 6.05 x 10^8 | 604,815,339.5 | Matches three-significant-figure rounding |
| Emergency Mann-Whitney U 5.30 x 10^8 | 529,835,396 | Matches three-significant-figure rounding |

All these original-style tests have nominal p-values below 0.001. Numerical agreement does not validate
their independent-encounter assumption: patients repeat. Current exploratory tests instead use one encounter
per patient. The inpatient p-value underflows numerically; it is not mathematically exactly zero.
The four derived age groups give chi-square 71.574371, not 133.60; grouping must be documented.

## Adjusted Estimates

| Predictor | PDF OR | Current OR | Current patient-clustered 95% CI |
| --- | ---: | ---: | --- |
| Prior inpatient visits | 1.310 | 1.309 | 1.292 to 1.327 |
| Prior emergency visits | 1.034 | 1.035 | 1.009 to 1.061 |
| Diagnosis count | 1.048 | 1.048 | 1.036 to 1.061 |
| Length of stay | 1.024 | 1.023 | 1.016 to 1.031 |
| Age 80+ | 1.219 | 1.259 | 1.131 to 1.401 |
| Age 60-79 | 1.138 | 1.170 | 1.057 to 1.294 |
| Medication changed | 0.936 | 0.941 | 0.891 to 0.994 |

PDF pseudo-R-squared is 0.0363; the current value is 0.036800. Clustering changes uncertainty;
different adjustment sets and feature definitions can change coefficients. The current emergency-visit
clustered p-value is 0.00765, not below 0.001. Do not claim exact replication of an unavailable specification.

## Corrections Required

1. OR 1.310 means 31% higher adjusted odds, not a 31% increase in probability.
2. Testing and medication-change associations do not establish protective treatment effects.
   Medication-change intervals include no association with one encounter per patient and expanded adjustment.
3. Readmission is not necessarily diabetes relapse, avoidable admission, or management failure.
4. Adherence and outpatient continuity are unmeasured; the connecting care channel is hypothetical.
5. Hospice exclusion is a study-scope choice. The death-excluded alternative cohort includes 771 hospice
   encounters and 43 hospice early readmissions. The blanket claim that hospice patients are ineligible to return is incorrect.
6. Medication counts describe inpatient treatment, not verified long-term outpatient polypharmacy.
7. The general Ch flag is not any drug Up/Down: 19,102 retained encounters have Ch without explicit dose changes.
8. Unknown specialty does not establish General Doctor. Gender is complete as a field but has three Unknown/Invalid records.
9. Regression does not eliminate all confounding. Proposed follow-up schedules and interventions are not validated effects.
10. Inventory subgroup counts are inconsistent: raw data have two identifiers, one outcome, and 47 other fields.

## Evidence

- [Numerical comparison CSV](comparison.csv)
- [Current adjusted estimates](../04_outcome_analysis/adjusted_odds_ratios.csv)
- [Sensitivity estimates](../05_robustness_validation/sensitivity_odds_ratios.csv)
- [Conclusions](../06_final_report/README.md)

This comparison is a maintained review, not a Python report-generation stage.