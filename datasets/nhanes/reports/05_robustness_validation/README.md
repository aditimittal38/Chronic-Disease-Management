# Step 5: NHANES Robustness Checks

## Purpose

Check whether initial adjusted HbA1c associations depend on model complexity, top-coded values,
cohort uncertainty, missingness, or outcome thresholds. These are fixed exploratory alternatives,
not a search for whichever model gives the smallest p-values.

The original features and stage-4 results are preserved. All alternative models use the same
9,254-person survey universe, MEC weights, strata, and PSUs through svy's `where` domain inference.
No prediction or external validation is performed in this stage.

## Alternative Specifications

| Scenario | Main change | Model participants | Residual survey df |
| --- | --- | ---: | ---: |
| Initial adjustment (reference) | Ten original slopes | 651 | 5 |
| Reduced adjustment | Age, sex, BMI, poverty ratio, insulin, pills | 683 | 9 |
| Reduced adjustment on original complete cases | Same six slopes; hold the original sample fixed | 651 | 9 |
| Top-code flags | Six core slopes plus age-80+ and poverty-ratio-5+ flags | 683 | 7 |
| Exclude uncertain pregnancy statuses | Original ten slopes; exclude two uncertain statuses | 649 | 5 |
| Without income adjustment | Remove the poverty-ratio term | 737 | 6 |
| HbA1c >=8% | Secondary logistic outcome on original complete cases | 651 | 5 |
| HbA1c >=7% | Sensitivity logistic outcome on original complete cases | 651 | 5 |

The same-case reduced model separates adjustment changes from changes in which participants are observed.
The broader reduced model changes both adjustment and the eligible complete-case sample.
Dropping income increases completeness but removes socioeconomic adjustment; it does not solve missingness.

Top-code indicators allow separate shifts for the 80+ and poverty-ratio-5+ categories without inventing
exact values above the published limits. They are an alternative functional form, not recovery of censored values.
The pregnancy sensitivity excludes uncertainty, not confirmed pregnancy: known pregnancy was already excluded.

## Gaussian Association Stability

Across the reference and five Gaussian alternatives:

- Insulin-use coefficients range from **1.008 to 1.196 HbA1c percentage points**.
- Diabetic-pill-use coefficients range from **0.546 to 0.605 percentage points**.
- Both retain positive directions, intervals above zero, and within-model FDR-adjusted p-values below 0.05 in all six fits.
- Poverty-ratio coefficients remain negative, but FDR-adjusted evidence is below 0.05 in only two of five applicable fits.
- Age coefficients remain negative, but FDR-adjusted evidence is below 0.05 in only two of six fits.

Stable associations do not establish medication harms. Disease severity, duration, clinician selection,
reverse causation, and omitted factors can explain treatment-group differences. Do not infer advice to change medication.
Changing a model's slopes changes its conditional interpretation; even a stable direction is not a causal result.

![Gaussian sensitivity associations](sensitivity_associations.png)

## Secondary Binary Outcomes

The cutoff models use logit links and the original 651 complete cases. Their coefficients are log-odds;
odds ratios and exponentiated confidence intervals are saved separately in the same coefficient table.
Do not compare a logistic coefficient or odds ratio numerically with a Gaussian percentage-point coefficient.
Cutoffs remain analytical choices, not each participant's appropriate clinical target.

FDR is applied to coefficient tests within each scenario, not to the entire set of models.
Repeated correlated sensitivity comparisons are exploratory, not an independently confirmed hypothesis-test family.
Individual confidence intervals are not multiple-comparison-adjusted.

## Missing HbA1c Coverage

There are **836 eligible examined adults with reported diagnosed diabetes and positive MEC weights**:
804 with measured HbA1c and 32 without. Their weighted HbA1c response coverage is **97.65%**
(Taylor 95% interval **96.49% to 98.82%**).

This is different from the 876 diagnosed adults before examination/measurement eligibility filters:
the other 40 have no positive MEC weight and cannot enter this examination-weighted coverage calculation.
High weighted coverage does not demonstrate missing-at-random data or eliminate item-nonresponse bias.
No response-weight adjustment, missing-outcome imputation, or sensitivity bounds are applied here.

## Complete-Case Composition

Compare the original 651 complete cases with the 153 domain members excluded for predictor missingness.

| Available-data weighted mean | Complete cases | Excluded cases |
| --- | ---: | ---: |
| Measured HbA1c | 7.24% | 7.46% |
| Recorded/top-coded age | 61.25 | 63.38 |
| BMI | 33.56 | 31.52 |
| Income-to-poverty ratio | 3.06 | 2.19 |

These are descriptive sample-composition comparisons, not formal significance tests or proof of selection bias.
Available sample sizes differ by variable: for excluded cases, BMI has 134 observations and income has 48,
not 153. The lower observed income mean cannot characterize those with unreported income.
Confidence intervals and library-reported degrees of freedom are retained in the CSV rather than assumed identical.

## Files and Checks

- [sensitivity_coefficients.csv](sensitivity_coefficients.csv): reference and alternative coefficients, uncertainty, FDR, and binary odds ratios.
- [scenario_inventory.csv](scenario_inventory.csv): population selection, sample sizes, family, iterations, and residual degrees of freedom.
- [coefficient_stability.csv](coefficient_stability.csv): Gaussian direction/range and evidence counts for selected parameters.
- [hba1c_response_coverage.csv](hba1c_response_coverage.csv): examined-domain response counts and weighted coverage.
- [complete_case_composition.csv](complete_case_composition.csv): available-data subgroup means and uncertainty.
- [validation_summary.json](validation_summary.json): fixed predictors, specifications, package versions, input fingerprints, and limitations.

Nine regression tests cover sample selection, same-case comparisons, income omission without imputation,
top-code semantics, pregnancy flags, weighted least-squares agreement, single-class outcomes, coverage,
separate coefficient scales, and predictor leakage. The retained stage-4 inputs are checked by fingerprint.

## What Remains

Assess broader adjustment choices, nonlinear relationships, item-nonresponse assumptions, additional
cycles, and external comparability before stronger claims. A predictive ranking or validation workflow
has not been attempted for NHANES; optional prediction requires a separate survey-aware evaluation plan.
The next planned step is a standalone research synthesis and a conceptual comparison with UCI,
not a patient-level merge or transfer of UCI's readmission outcome.