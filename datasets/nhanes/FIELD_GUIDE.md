# NHANES Fields Explained

## Start with the Row

One row is **one survey participant**, not a hospital visit. `SEQN` is that participant's ID.
The official components were joined using SEQN, producing 145 columns. Those are not 145 proposed predictors.
Some describe eligibility, some are follow-up questions, and some exist only to support valid survey estimates.

Each component name ends in `_J`, identifying the 2017-2018 cycle. This suffix is not part of the variable names.

| Component | What it contains |
| --- | --- |
| DEMO_J | Demographics, socioeconomic information, and survey-design fields |
| DIQ_J | Diabetes diagnosis, treatment, and monitoring questionnaire |
| GHB_J | Laboratory-measured HbA1c |
| BMX_J | Measured body size and BMI |
| PAQ_J | Physical activity questionnaire |
| HUQ_J | Healthcare access and utilization questionnaire |

## The Main Fields

| Field | Plain meaning | How to interpret it |
| --- | --- | --- |
| SEQN | Participant identifier | Join files; never treat the ID as a clinical predictor |
| RIDAGEYR | Age in years | 80 means 80 or older, not necessarily exactly 80 |
| RIAGENDR | Recorded sex category | 1 = male, 2 = female |
| RIDRETH3 | Race/Hispanic-origin category | Category codes, not a numeric severity scale |
| DMDEDUC2 | Education for adults aged 20+ | Codes 1-5 are education categories; 7/9 are special responses |
| INDFMPIR | Family income relative to poverty | 1 means the poverty threshold; 2 means twice it; 5 means 5 or more |
| DIQ010 | Reported doctor-diagnosed diabetes | 1 = yes, 2 = no, 3 = borderline; our provisional domain uses 1 |
| LBXGH | Measured HbA1c, in percent | Proposed outcome: 8.2 means 8.2%, not 0.082 |
| BMXBMI | Measured BMI | Body-size measure; not an HbA1c result |
| DIQ050 | Currently taking insulin | Treatment status, not whether insulin is taken as prescribed |
| DIQ070 | Currently taking diabetic pills | Treatment status; missing values can reflect questionnaire routing |
| DIQ240 | Has one usual diabetes doctor/professional | 1 = yes, 2 = no; a care-continuity indicator, not proof of quality |
| DID250 | Visits to that usual professional in the past year | Conditional on having that professional; not all healthcare visits |
| DID260 | Number of home glucose checks | Requires DIQ260U to know the time unit; 0 explicitly means never |
| DIQ260U | Unit for glucose-check frequency | 1 = per day, 2 = per week, 3 = per month, 4 = per year |
| DIQ275 | Reported professional A1C testing in the past year | Monitoring history, not the laboratory result |
| DIQ280 | Reported last A1C value | Recalled historical result; not interchangeable with measured LBXGH |
| DIQ230 | Last diabetes educator/dietitian/nutritionist visit | Excludes doctors; do not interpret as any specialist appointment |
| PAQ605 / PAQ620 | Vigorous/moderate activity at work | Yes/no gate questions; activity need not be paid work |
| PAQ650 / PAQ665 | Vigorous/moderate recreational activity | Yes/no gates for leisure-time activity |
| PAQ610 | Days per week of vigorous work | Follow-up to PAQ605; meaningful together with activity status |
| PAD615 | Minutes on a typical vigorous-work day | Follow-up duration, not total weekly minutes |
| PAD680 | Sedentary minutes on a typical day | 0 is a possible valid value; do not globally mark it as missing |
| HUQ030 | Usual place for healthcare | 1 = yes, 2 = none, 3 = more than one place |
| HUQ051 | Healthcare visits in the past year | A coded band: 2 means 2-3 visits; 8 means 16 or more |
| HUQ071 | Overnight hospitalization in the past year | Not a 30-day readmission label |
| HUD080 | Number of overnight hospital admissions | Conditional on hospitalization; 6 means six or more |

## Four Different Kinds of Values

### 1. A Measurement

`LBXGH = 8.2` is a laboratory measurement. `PAD615 = 30` is reported minutes.
They can be used numerically once their eligibility, missingness, and units are checked.

### 2. A Category Code

`DIQ010 = 1` means Yes, not one episode of diabetes. `HUQ051 = 2` means a visit band, not exactly two visits.
Category codes must be decoded using that variable's codebook.

### 3. A Special Response

The questionnaire often records Refused or Don't know as numbers:

| Field | Refused | Don't know |
| --- | ---: | ---: |
| DIQ010 | 7 | 9 |
| PAQ610 | 77 | 99 |
| DID260 | 777 | 999 |
| DID250 | 7777 | 9999 |
| PAD615 / PAD680 | 7777 | 9999 |

These are not quantities. For example, DID260=999 does not mean 999 checks.
Do not replace every 7 or 9 throughout the dataset: age 7, seven days of activity, and HbA1c 9% can be valid.

### 4. A Blank

A blank can mean the question was skipped, the person was ineligible, the component was absent,
or an answer/measurement was unavailable. These situations require different treatment.

## Why Questionnaire Skips Matter

**Activity example:** PAQ605=2 means no qualifying vigorous work activity. The person is not asked its
days and minutes, so PAQ610/PAD615 can be blank. A derived weekly vigorous-work total can be zero
because the gate explicitly says No, not because blanks always mean zero.

**Unknown activity example:** PAQ605=9 means Don't know. Blank follow-up fields cannot establish zero activity.

**Care example:** DIQ240=2 means no single usual diabetes professional, so DID250 is skipped.
That does not establish no healthcare visits or no diabetes care; preserve the reason for the skip.

**Age example:** DMDEDUC2 is released only for adults aged 20+. A child's blank adult-education field is inapplicable,
not a failure to report education. This is one reason the initial adult cohort uses age 20+.

## Why Frequency Units Matter

`DID260 = 2` can mean two checks per day or two checks per year, depending on DIQ260U.
For a later derived daily frequency:

- Per day: keep the count.
- Per week: divide by 7.
- Per month: use a documented average-days-per-month convention.
- Per year: use a documented days-per-year convention.

These would be analytical conversions, not exact observed daily behavior. If a positive count has no unit,
we cannot calculate its daily frequency. An explicit DID260=0 means Never and does not require a frequency unit.

For activity, three days per week and 30 minutes per active day imply 90 reported minutes per week.
Do not use the daily duration alone as a weekly total.

## Survey Fields Are Not Ordinary Predictors

| Field | Purpose |
| --- | --- |
| WTMEC2YR | Examination weight: how much representation the participant has in weighted estimates |
| WTINT2YR | Interview weight; not the primary weight when analyzing measured HbA1c |
| SDMVSTRA | Survey stratum |
| SDMVPSU | Survey sampling cluster; its labels repeat across strata |

Together these allow survey-aware population estimates and uncertainty calculations.
WTMEC2YR is not the participant's body weight. Body weight is a different examination variable.
Do not put survey weights, strata, or PSU identifiers into a model as clinical predictors.
Keep them attached to the data for the statistical design, including full-universe records for domain inference.

## What Cleaning Has Done

1. Keep original values available for traceability.
2. Recode each selected field's special responses using its own codebook.
3. Distinguish structural skips from unknown responses and unavailable measurements.
4. Preserve explicit valid zeros; derive a skip-based zero only when a gate justifies it.
5. Validate units, ranges, identifiers, and survey-design information.
6. Keep missing outcome measurements out of the measured-HbA1c domain, not assign them a normal outcome.

Cleaning is now implemented; [the cleaning report](reports/02_data_cleaning/README.md) explains the
selected values, response-status table, and domain flags. Frequency conversion and other derived
features are now implemented; [the feature report](reports/03_feature_extraction/README.md) documents
their formulas, handling of missing values, and interpretation. Detailed raw values are in
[cohort_value_counts.csv](reports/01_data_audit/cohort_value_counts.csv), and selected variable definitions are in
[variable_dictionary.csv](reports/01_data_audit/variable_dictionary.csv).
The authoritative meaning of each field comes from its cycle-specific CDC codebook stored under reference/2017-2018.