"""Use the maintained svy library for full-design domain inference."""

import numpy as np
import pandas as pd
import polars as pl
import svy
from statsmodels.stats.multitest import multipletests


DESIGN_FIELDS = ("WTMEC2YR", "SDMVSTRA", "SDMVPSU")
MODEL_PREDICTORS = (
    "age_per_10_years", "female", "bmi_per_5_units", "poverty_ratio",
    "insulin_use", "oral_diabetes_med_use", "usual_diabetes_professional",
    "a1c_test_past_year", "log1p_glucose_checks", "log1p_activity_equivalents",
)
SOURCE_PREDICTORS = {
    "age_per_10_years": "RIDAGEYR", "female": "RIAGENDR", "bmi_per_5_units": "BMXBMI",
    "poverty_ratio": "INDFMPIR", "insulin_use": "insulin_use",
    "oral_diabetes_med_use": "oral_diabetes_med_use", "usual_diabetes_professional": "usual_diabetes_professional",
    "a1c_test_past_year": "a1c_test_past_year", "log1p_glucose_checks": "glucose_checks_per_day_equivalent",
    "log1p_activity_equivalents": "activity_moderate_equivalent_minutes_week",
}


def make_sample(frame):
    if frame[list(DESIGN_FIELDS)].isna().any().any():
        raise ValueError("Missing full-universe design fields require explicit review.")
    if not np.isfinite(frame[list(DESIGN_FIELDS)].to_numpy()).all() or frame["WTMEC2YR"].lt(0).any():
        raise ValueError("Invalid survey-design information.")
    design = svy.Design(stratum="SDMVSTRA", psu="SDMVPSU", wgt="WTMEC2YR")
    return svy.Sample(data=pl.from_pandas(frame), design=design)


def domain_mean(sample, outcome="LBXGH", extra_condition=None):
    condition = svy.col("analysis_domain") == 1
    if extra_condition is not None:
        condition = condition & extra_condition
    estimate = sample.estimation.mean(outcome, where=condition, drop_nulls=True, method="taylor")
    return estimate.to_polars().to_dicts()[0]


def domain_proportion(sample, outcome):
    estimate = sample.estimation.prop(outcome, where=svy.col("analysis_domain") == 1,
                                      drop_nulls=True, method="taylor", ci_method="logit")
    return next(row for row in estimate.to_polars().to_dicts() if row[outcome] == 1)


def model_frame(frame):
    prepared = frame.copy()
    prepared["age_per_10_years"] = frame["RIDAGEYR"] / 10
    prepared["female"] = frame["RIAGENDR"].map({1: 0, 2: 1})
    prepared["bmi_per_5_units"] = frame["BMXBMI"] / 5
    prepared["poverty_ratio"] = frame["INDFMPIR"]
    prepared["log1p_glucose_checks"] = np.log1p(frame["glucose_checks_per_day_equivalent"])
    prepared["log1p_activity_equivalents"] = np.log1p(frame["activity_moderate_equivalent_minutes_week"])
    prepared["model_domain"] = (frame["analysis_domain"].eq(1) & prepared[list(MODEL_PREDICTORS)].notna().all(axis=1)).astype(int)
    return prepared


def fit_adjusted_model(frame):
    prepared = model_frame(frame)
    selected = prepared.loc[prepared["model_domain"].eq(1)]
    matrix = np.column_stack([np.ones(len(selected)), selected[list(MODEL_PREDICTORS)].to_numpy()])
    if len(selected) < 100 or np.linalg.matrix_rank(matrix) != matrix.shape[1]:
        raise ValueError("The complete-case model lacks sufficient observations or full-rank predictors.")
    sample = make_sample(prepared)
    result = sample.glm.fit(y="LBXGH", x=list(MODEL_PREDICTORS), family="gaussian", link="identity",
                            where=svy.col("model_domain") == 1, method="taylor", drop_nulls=True)
    table = result.to_polars().to_pandas()
    if not np.isfinite(table[["estimate", "std_err", "conf_low", "conf_high", "p_value"]]).all().all():
        raise ValueError("Nonfinite model uncertainty or coefficients require investigation.")
    if int(result.fitted.stats.n) != len(selected):
        raise ValueError("The survey model dropped unexpected participants.")
    table["fdr_adjusted_p"] = np.nan
    tested = table["term"].ne("_intercept_")
    table.loc[tested, "fdr_adjusted_p"] = multipletests(table.loc[tested, "p_value"], method="fdr_bh")[1]
    return result, table, prepared