# Step 4: Survey-Aware HbA1c Analysis

## Scope and Design

Analyze measured HbA1c in the 804-person primary domain, using the full 9,254-person survey design.
The initial association model uses 651 complete cases. This is cross-sectional analysis, not prediction
of future clinical events or evaluation of the UCI readmission model.

The maintained `svy` library supplies Taylor-linearized design-based means, proportions, and Gaussian
regression. The design uses WTMEC2YR, SDMVSTRA, and SDMVPSU together. Its `where` argument selects domains
without prefiltering away the full design. The design has 15 strata and 30 stratum-PSU pairs.
No finite-population correction or additional item-nonresponse weight adjustment is applied.

## Weighted Outcomes

| Outcome | Survey-weighted estimate | Design-based 95% interval |
| --- | ---: | --- |
| Mean measured HbA1c | 7.28% | 7.12% to 7.44% |
| HbA1c >=8% | 23.18% | 19.51% to 27.32% |
| HbA1c >=7% | 49.62% | 41.96% to 57.30% |

Means use Taylor variance and t-based intervals. Proportions use Taylor variance with logit-transformed
intervals. These estimates describe the selected measured-HbA1c domain with its MEC weights; they must
not be presented as fully nonresponse-adjusted estimates for every adult with diabetes.
The 72 diagnosed adults without HbA1c were not assigned normal values, but their item nonresponse may bias inference.
The >=8% and >=7% cutoffs are analytical secondary/sensitivity outcomes, not universal individual treatment goals.

The weighted mean differs from the unweighted sample mean of 7.40%. Weighting changes each participant's
representation; it does not change the actual HbA1c measurement. Descriptive estimates use 15 survey degrees of freedom.

## Group Comparisons

The group table reports means by age, BMI, poverty ratio, education, treatment, monitoring, activity,
recorded sex, and race/Hispanic origin. Group intervals are withheld for fewer than 30 sample members.
This threshold is a conservative reporting flag, not a complete NCHS estimate-reliability assessment.
Groups with missing category values do not receive an invented lowest-category value.

These are descriptive differences, not formal between-group significance tests. Overlapping or
non-overlapping separate intervals are not a substitute for a properly specified contrast test.

![Weighted HbA1c distribution and age-group means](weighted_hba1c.png)

## Prespecified Adjusted Model

Fit Gaussian survey-weighted regression with an identity link:

```text
LBXGH ~ age/10 + female + BMI/5 + income-to-poverty ratio
      + insulin use + oral diabetes medication use
      + usual diabetes professional + past-year A1C test
      + log(1 + daily-equivalent glucose checks)
      + log(1 + weekly moderate-equivalent activity minutes)
```

The model uses ten fixed slopes; no outcome-driven variable selection is performed.
Coefficients are adjusted **HbA1c percentage-point differences**, not odds ratios or changes in readmission risk.
Binary terms compare Yes versus No, recorded sex compares female versus male, age is per ten years,
and BMI is per five units. Log-transformed terms are per unit of the displayed log scale.

Age 80+ and poverty ratio 5+ retain their top-code values in this initial numeric specification.
Alternative representations remain a sensitivity task. Education, race, sedentary time, and other
omitted factors are not controlled in this compact model; it does not remove all confounding.

## Complete-Case Accounting

153 of 804 domain members lack at least one required predictor. All participants remain in the input
universe; a model-domain indicator selects the 651 complete cases. Missingness counts overlap and
must not be summed to derive exclusions.

| Predictor information | Missing domain members |
| --- | ---: |
| Age / recorded sex / insulin / diabetic pill use | 0 |
| BMI | 19 |
| Income-to-poverty ratio | 105 |
| Usual diabetes professional | 2 |
| Past-year A1C test | 34 |
| Glucose-check frequency | 5 |
| Complete activity quantity | 12 |

No learned imputation or additional response adjustment is used. Complete-case associations may
describe a selected subpopulation and may be biased when missingness relates to outcomes or covariates.

## Initial Adjusted Findings

| Term | HbA1c percentage-point coefficient | Survey 95% interval | FDR-adjusted p |
| --- | ---: | --- | ---: |
| Insulin use versus no use | 1.136 | 0.579 to 1.693 | 0.028 |
| Diabetic pill use versus no use | 0.595 | 0.266 to 0.925 | 0.028 |
| Income-to-poverty ratio, per unit | -0.130 | -0.242 to -0.018 | 0.102 |
| Age, per ten recorded years | -0.173 | -0.336 to -0.010 | 0.103 |
| Past-year A1C test versus no test | -0.258 | -0.724 to 0.208 | 0.356 |

The other terms and all unadjusted/adjusted p-values are in the coefficient CSV. Ten coefficient tests
receive Benjamini-Hochberg FDR adjustment; the intercept is excluded. Individual 95% intervals are not
multiple-comparison-adjusted. Therefore an interval may exclude zero while its FDR-adjusted p exceeds 0.05.

Positive treatment associations do **not** show that insulin or pills worsen HbA1c. More severe disease,
longer duration, treatment selection, and reverse causation can produce these differences. They are not
recommendations to stop or alter medication. The smaller/inconclusive monitoring and activity estimates
are not proof of no clinical benefit.

The full design has 15 degrees of freedom; this model's library-reported residual survey degrees of
freedom are **5** after ten slopes. This limited design information makes uncertainty and model sensitivity
important even though there are 651 participants. In-sample weighted R-squared is approximately 0.160;
it is not held-out predictive performance or clinical validation.

## Outputs and Validation

- [weighted_outcomes.csv](weighted_outcomes.csv): weighted means/proportions, standard errors, intervals, df, and sample sizes.
- [weighted_group_means.csv](weighted_group_means.csv): subgroup means and sparse-group flags.
- [adjusted_hba1c_coefficients.csv](adjusted_hba1c_coefficients.csv): all coefficients, units, design-based intervals, p-values, and FDR adjustment.
- [model_predictor_missingness.csv](model_predictor_missingness.csv): overlapping predictor missingness counts.
- [model_summary.txt](model_summary.txt): technical survey model output.
- [analysis_summary.json](analysis_summary.json): design, domains, fixed specification, degrees of freedom, source hash, and software versions.

Seven method tests check a known Taylor variance, preservation of the full design, domain missingness,
weight-scale invariance, invalid designs, agreement with independent weighted least-squares point
estimates, sparse-group reporting, and predictor leakage boundaries.
Point coefficients are cross-checked with statsmodels; that comparison does not replace the survey covariance calculation.
The analysis was verified with Python 3.13.14 and svy 0.32.1. Requirements are included through the repository installer.

## Next Step and Remaining Limitations

Check alternative adjustment sets, top-code representations, pregnancy uncertainty, missingness,
and smaller model specifications. Optional prediction needs its own design-aware evaluation plan.
No external validation, causal mechanisms, optimized thresholds, or clinical utility are established.

Sources: [NHANES survey tutorial](https://wwwn.cdc.gov/nchs/nhanes/tutorials/),
[svy estimation](https://svylab.com/docs/svy/tutorials/estimation.html),
[svy regression](https://svylab.com/docs/svy/tutorials/glm.html).