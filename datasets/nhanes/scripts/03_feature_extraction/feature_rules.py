"""Derive NHANES features without losing unknown responses or survey eligibility."""

import numpy as np
import pandas as pd


DAYS_PER_YEAR = 365.25
DAYS_PER_MONTH = DAYS_PER_YEAR / 12
ACTIVITY_FIELDS = (
    ("vigorous_work_minutes_week", "PAQ605", "PAQ610", "PAD615", 8),
    ("moderate_work_minutes_week", "PAQ620", "PAQ625", "PAD630", 4),
    ("transport_minutes_week", "PAQ635", "PAQ640", "PAD645", 4),
    ("vigorous_recreation_minutes_week", "PAQ650", "PAQ655", "PAD660", 8),
    ("moderate_recreation_minutes_week", "PAQ665", "PAQ670", "PAD675", 4),
)
BINARY_FIELDS = {
    "insulin_use": "DIQ050", "oral_diabetes_med_use": "DIQ070",
    "usual_diabetes_professional": "DIQ240", "a1c_test_past_year": "DIQ275",
    "hospitalized_past_year": "HUQ071",
}


def binary_response(values):
    return values.map({1: 1, 2: 0}).astype("Int64")


def activity_minutes(values, statuses, gate, days, minutes):
    result = pd.Series(np.nan, index=values.index, dtype=float)
    justified_no = values[gate].eq(2) & statuses[days].eq("skip_no_activity") & statuses[minutes].eq("skip_no_activity")
    reported_yes = values[gate].eq(1) & values[days].notna() & values[minutes].notna()
    result.loc[justified_no] = 0.0
    result.loc[reported_yes] = values.loc[reported_yes, days] * values.loc[reported_yes, minutes]
    return result


def glucose_frequency(values, statuses):
    divisor = values["DIQ260U"].map({1: 1.0, 2: 7.0, 3: DAYS_PER_MONTH, 4: DAYS_PER_YEAR})
    frequency = values["DID260"] / divisor
    frequency.loc[values["DID260"].eq(0)] = 0.0
    reason = statuses["DID260"].copy()
    reason.loc[values["DID260"].eq(0)] = "explicit_never"
    convertible = values["DID260"].gt(0) & divisor.notna()
    reason.loc[convertible] = "unit_converted"
    reason.loc[values["DID260"].gt(0) & divisor.isna()] = "missing_required_unit"
    return frequency, reason


def activity_features(values, statuses):
    features = pd.DataFrame(index=values.index)
    for name, gate, days, minutes, _ in ACTIVITY_FIELDS:
        features[name] = activity_minutes(values, statuses, gate, days, minutes)
    minute_columns = [entry[0] for entry in ACTIVITY_FIELDS]
    components = features[minute_columns]
    features["activity_complete"] = components.notna().all(axis=1).astype(int)
    features["activity_total_minutes_week"] = components.sum(axis=1, min_count=len(minute_columns))
    factors = pd.Series({name: score for name, _, _, _, score in ACTIVITY_FIELDS})
    features["activity_met_minutes_week"] = components.mul(factors).sum(axis=1, min_count=len(minute_columns))
    features["activity_moderate_equivalent_minutes_week"] = features["activity_met_minutes_week"] / 4
    equivalents = features["activity_moderate_equivalent_minutes_week"]
    features["activity_at_least_150_equivalent_minutes"] = equivalents.ge(150).astype("Int64").where(equivalents.notna())
    total = features["activity_total_minutes_week"]
    features["activity_total_exceeds_calendar_week"] = total.gt(7 * 24 * 60).astype("Int64").where(total.notna())
    return features


def add_demographic_features(features, values):
    adult = values["RIDAGEYR"].ge(20)
    features["age_group"] = pd.cut(values["RIDAGEYR"].where(adult), bins=[19, 39, 59, 79, np.inf], labels=["20-39", "40-59", "60-79", "80+"])
    features["bmi_group"] = pd.cut(values["BMXBMI"].where(adult), bins=[0, 18.5, 25, 30, np.inf], right=False,
                                   labels=["Below 18.5", "18.5 to below 25", "25 to below 30", "30 or above"])
    features["poverty_ratio_group"] = pd.cut(values["INDFMPIR"], bins=[0, 1, 2, 5, np.inf], right=False,
                                             labels=["Below 1", "1 to below 2", "2 to below 5", "5 or above"])
    features["education_group"] = values["DMDEDUC2"].map({1: "Below high school", 2: "Below high school", 3: "High school/GED", 4: "Some college/AA", 5: "College or above"})


def derive_features(values, statuses):
    features = activity_features(values, statuses)
    features["glucose_checks_per_day_equivalent"], features["glucose_frequency_status"] = glucose_frequency(values, statuses)
    features["sedentary_hours_day"] = values["PAD680"] / 60
    for name, source in BINARY_FIELDS.items():
        features[name] = binary_response(values[source])
    features["usual_healthcare_place"] = values["HUQ030"].map({1: 1, 2: 0, 3: 1}).astype("Int64")
    educator = values["DIQ230"]
    features["diabetes_educator_past_year"] = educator.eq(1).astype("Int64").where(educator.notna())
    domain = values["analysis_domain"].eq(1)
    features["hba1c_at_least_8"] = values["LBXGH"].ge(8).astype("Int64").where(domain)
    features["hba1c_at_least_7"] = values["LBXGH"].ge(7).astype("Int64").where(domain)
    add_demographic_features(features, values)
    return features


def feature_dictionary():
    rows = []
    for name, gate, days, minutes, score in ACTIVITY_FIELDS:
        rows.append({"feature": name, "type": "numeric", "source": f"{gate}, {days}, {minutes}",
                     "rule": f"Valid Yes: days times minutes; justified No: zero; otherwise missing. Suggested MET score {score}."})
    definitions = {
        "activity_complete": ("quality_flag", "Five activity domains", "1 when all five weekly quantities can be derived; not a model predictor by default."),
        "activity_total_minutes_week": ("numeric", "Five derived activity domains", "Sum only when all five known; no partial sum or missing-as-zero."),
        "activity_met_minutes_week": ("numeric", "Five derived domains", "Sum minutes times suggested scores 8/4/4/8/4; requires all five."),
        "activity_moderate_equivalent_minutes_week": ("numeric", "activity_met_minutes_week", "MET-minutes divided by 4; vigorous minutes receive twice the moderate weight."),
        "activity_at_least_150_equivalent_minutes": ("binary", "Equivalent activity minutes", "1 for >=150/week; missing if incomplete. Descriptive threshold, not an individualized prescription."),
        "activity_total_exceeds_calendar_week": ("quality_flag", "Total activity minutes", "1 if reported weekly total exceeds 10080 minutes; flag for review, do not automatically exclude."),
        "glucose_checks_per_day_equivalent": ("numeric", "DID260, DIQ260U", "Divide by 1, 7, 365.25/12, or 365.25; explicit Never=0; positive count without unit missing."),
        "glucose_frequency_status": ("quality_reason", "DID260 status, DIQ260U", "Distinguish explicit never, unit conversion, missing unit, and original missing-response reasons."),
        "sedentary_hours_day": ("numeric", "PAD680", "Minutes divided by 60; preserve missingness and explicit zero."),
        "usual_healthcare_place": ("binary", "HUQ030", "1 for one or more usual places (codes 1/3), 0 for no place (2), missing otherwise."),
        "diabetes_educator_past_year": ("binary", "DIQ230", "1 for visit within one year (1), 0 for valid older/never categories (2-5); excludes doctors."),
        "hba1c_at_least_8": ("secondary_target", "LBXGH, analysis_domain", ">=8% flag in primary domain only; not a predictor or proven failure of individualized care."),
        "hba1c_at_least_7": ("sensitivity_target", "LBXGH, analysis_domain", ">=7% sensitivity flag in primary domain only; never a predictor."),
        "age_group": ("category", "RIDAGEYR", "Adults 20+: 20-39 / 40-59 / 60-79 / 80+; missing for younger or unavailable ages."),
        "bmi_group": ("category", "BMXBMI, RIDAGEYR", "Adult 20+ cutoffs 18.5, 25, 30; descriptive BMI bands, not pediatric or individualized categories."),
        "poverty_ratio_group": ("category", "INDFMPIR", "Below 1 / 1 to below 2 / 2 to below 5 / 5+; last group retains top-code meaning."),
        "education_group": ("category", "DMDEDUC2", "Codes 1/2 below high school; 3 high school/GED; 4 some college/AA; 5 college+; preserve unknown."),
    }
    for name, source in BINARY_FIELDS.items():
        definitions[name] = ("binary", source, "Valid Yes (1) -> 1; valid No (2) -> 0; missing stays missing. No adherence or causal-effect claim.")
    for name, (kind, source, rule) in definitions.items():
        rows.append({"feature": name, "type": kind, "source": source, "rule": rule})
    return pd.DataFrame(rows)