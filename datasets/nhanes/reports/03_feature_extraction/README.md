# Step 3: NHANES Feature Extraction

## Output Overview

| Measure | Result |
| --- | ---: |
| Full survey universe retained | 9,254 participants |
| Original cleaned columns preserved | 52 |
| Derived columns added | 27 |
| Total feature-table columns | 79 |
| Primary analysis domain | 804 participants |
| Domain members with complete activity quantities | 792 |
| Domain members with incomplete activity quantities | 12 |
| HbA1c >=8% secondary-outcome cases | 218 |
| HbA1c >=7% sensitivity-outcome cases | 404 |
| Domain activity totals exceeding a calendar week | 0 |

No additional participant exclusions, learned imputation, weighted estimates, or models are performed.
The 79 columns are not 79 independent predictors: they include identifiers, survey design, outcomes,
original fields, overlapping representations, and quality flags.

## Glucose-Check Frequency

Convert DID260 using DIQ260U into an equivalent daily frequency:

| Original unit | Calculation |
| --- | --- |
| Per day | Count |
| Per week | Count / 7 |
| Per month | Count / (365.25 / 12) |
| Per year | Count / 365.25 |

The 365.25-day convention is a documented analytical approximation, not exact daily behavior.
Explicit Never (count 0) stays zero without needing a unit. A positive count without a valid unit stays missing.
`glucose_frequency_status` distinguishes conversion, explicit never, missing required units, and other response reasons.
Glucose checks measure reported monitoring, not medication adherence or a treatment effect.

## Activity Features

For each of vigorous work, moderate work, transport, vigorous recreation, and moderate recreation:

- Valid Yes with days and minutes: weekly minutes = days per week times minutes per active day.
- Valid No with recorded skip reasons for both follow-ups: weekly minutes = 0.
- Unknown gate, missing required follow-ups, or routing conflicts: weekly minutes remains missing.

Total activity is calculated only when all five domains are known. Partial known activity is not presented as a complete total.
The 12 incomplete domain members are not removed from the survey universe or primary domain.

Suggested scores from the cycle's PAQ codebook are 8 METs for vigorous work/recreation and 4 for
moderate work/recreation and transport. `activity_met_minutes_week` sums weekly minutes times these scores.
`activity_moderate_equivalent_minutes_week` divides MET-minutes by 4, so vigorous minutes receive twice the moderate weight.
The >=150-equivalent-minute flag is descriptive, not an individualized exercise prescription or a measure of all movement.
The questionnaire describes activities in bouts of at least 10 minutes.

`activity_complete` and the calendar-week exceedance flag support review, not default clinical prediction.
Large reported values are retained and flagged rather than automatically trimmed or excluded.
`sedentary_hours_day` is reported sedentary minutes divided by 60, preserving zero and missingness.

## Treatment, Monitoring, and Access

| Derived field | Interpretation |
| --- | --- |
| insulin_use / oral_diabetes_med_use | Yes=1, No=0, unavailable remains missing |
| usual_diabetes_professional | One usual diabetes professional; does not prove care quality |
| a1c_test_past_year | Reported professional testing, not the examination HbA1c result |
| diabetes_educator_past_year | Educator/dietitian/nutritionist visit within one year; excludes doctors |
| usual_healthcare_place | One or several usual places=1; no usual place=0 |
| hospitalized_past_year | Reported overnight admission in the past year; not 30-day readmission |

Do not infer adherence, prevention, or causal treatment effects from these indicators.
More intensive treatment/monitoring may reflect greater disease burden.

## Demographic and Socioeconomic Categories

- Age: 20-39, 40-59, 60-79, 80+; no invented exact ages beyond the top code.
- Adult BMI: below 18.5, 18.5 to below 25, 25 to below 30, 30 or above. Applied to age 20+ only.
- Income-to-poverty ratio: below 1, 1 to below 2, 2 to below 5, 5+. The last retains the top-code meaning.
- Education: below high school, high school/GED, some college/AA, college or above.

Missing values stay missing; they do not become the lowest category. These groupings are analytical choices,
not individualized diagnoses or evidence that demographic identity causes glycemic differences.

## Outcomes and Modeling Guardrails

Continuous measured **LBXGH** remains the primary proposed outcome. The >=8% and >=7% flags are created
only inside the primary domain; values outside it remain missing, not zero. These are not universal clinical goals.

- Exclude LBXGH and both derived cutoff targets from predictors when modeling HbA1c or its threshold.
- Avoid self-reported historical A1C (DIQ280) as a shortcut predictor in the planned management-factor analysis.
- Keep SEQN, weights, strata, and PSU for linking and survey inference, not as clinical predictors.
- Domain and quality/status flags are for selection/design/review, not default model inputs.
- Choose continuous versus grouped BMI/age/income, and original versus derived treatment/monitoring fields.
- Do not simultaneously include all activity components, totals, MET totals, and equivalent-minute summaries in an unregularized model.
- Fit any learned preprocessing and outcome-informed selection only inside training data if prediction is later attempted.

The domain is cross-sectional. These features do not establish a temporally ordered clinical mechanism.

## Files and Validation

- [Feature table](../../data/processed/nhanes_2017_2018_features.csv): all cleaned fields plus 27 derived columns.
- [feature_dictionary.csv](feature_dictionary.csv): source fields, formulas, types, and cautions.
- [feature_missingness.csv](feature_missingness.csv): primary-domain coverage and unweighted numeric summaries.
- [feature_value_counts.csv](feature_value_counts.csv): category/binary/quality frequencies; high-cardinality numeric values are summarized rather than fully enumerated.
- [feature_summary.json](feature_summary.json): dimensions, input/output fingerprints, and predictor exclusions.

Seven regression tests cover conversion units, true zeros, unknown activity, complete totals, MET weighting,
thresholds, implausible totals, adult category boundaries, and binary nonresponse.
Input hashes and participant keys are validated before extraction; response reasons are aligned by SEQN.
Survey fields, outcomes, and domain flags are preserved.

## Next Step

Implement survey-aware descriptive estimates and adjusted associations, using MEC weights, strata, and
PSUs together and retaining the full survey universe for domain variance estimation. No national estimates,
hypothesis tests, fitted models, or importance rankings have been computed for NHANES yet.