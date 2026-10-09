"""Define fixed NHANES sensitivity scenarios and retain the full survey design."""

import numpy as np
import pandas as pd
import svy
from statsmodels.stats.multitest import multipletests

from survey_methods import MODEL_PREDICTORS, make_sample, model_frame


CORE_PREDICTORS = MODEL_PREDICTORS[:6]
GAUSSIAN = "gaussian"
BINOMIAL = "binomial"
SCENARIOS = (
    ("reduced_adjustment", CORE_PREDICTORS, "LBXGH", GAUSSIAN, "primary"),
    ("reduced_same_complete_cases", CORE_PREDICTORS, "LBXGH", GAUSSIAN, "original_complete_cases"),
    ("top_code_flags", CORE_PREDICTORS + ("age_80_plus", "poverty_ratio_5_plus"), "LBXGH", GAUSSIAN, "primary"),
    ("exclude_uncertain_pregnancy", MODEL_PREDICTORS, "LBXGH", GAUSSIAN, "pregnancy_sensitivity"),
    ("without_income_adjustment", tuple(name for name in MODEL_PREDICTORS if name != "poverty_ratio"), "LBXGH", GAUSSIAN, "primary"),
    ("hba1c_at_least_8", MODEL_PREDICTORS, "hba1c_at_least_8", BINOMIAL, "original_complete_cases"),
    ("hba1c_at_least_7", MODEL_PREDICTORS, "hba1c_at_least_7", BINOMIAL, "original_complete_cases"),
)


def prepare_sensitivity_data(frame):
    prepared = model_frame(frame)
    prepared["age_80_plus"] = frame["RIDAGEYR"].ge(80).astype(float).where(frame["RIDAGEYR"].notna())
    prepared["poverty_ratio_5_plus"] = frame["INDFMPIR"].ge(5).astype(float).where(frame["INDFMPIR"].notna())
    return prepared


def scenario_domain(prepared, predictors, outcome, selection):
    mask = prepared["analysis_domain"].eq(1)
    if selection == "original_complete_cases":
        mask &= prepared["model_domain"].eq(1)
    elif selection == "pregnancy_sensitivity":
        mask &= prepared["analysis_domain_known_pregnancy_status_sensitivity"].eq(1)
    elif selection != "primary":
        raise ValueError(f"Unknown sensitivity selection: {selection}")
    mask &= prepared[list(predictors)].notna().all(axis=1) & prepared[outcome].notna()
    return mask


def fit_scenario(prepared, name, predictors, outcome, family, selection):
    mask = scenario_domain(prepared, predictors, outcome, selection)
    selected = prepared.loc[mask]
    matrix = np.column_stack([np.ones(len(selected)), selected[list(predictors)].to_numpy()])
    if len(selected) < 100 or np.linalg.matrix_rank(matrix) != matrix.shape[1]:
        raise ValueError(f"Insufficient/full-rank model data for {name}")
    if family == BINOMIAL and selected[outcome].nunique() != 2:
        raise ValueError(f"Binary outcome lacks both classes for {name}")
    data = prepared.copy()
    data["scenario_domain"] = mask.astype(int)
    sample = make_sample(data)
    result = sample.glm.fit(y=outcome, x=list(predictors), family=family,
                            link="logit" if family == BINOMIAL else "identity",
                            where=svy.col("scenario_domain") == 1, method="taylor", drop_nulls=True)
    table = result.to_polars().to_pandas()
    if int(result.fitted.stats.n) != len(selected):
        raise ValueError(f"Unexpected model sample loss: {name}")
    if not np.isfinite(table[["estimate", "std_err", "conf_low", "conf_high", "p_value"]]).all().all():
        raise ValueError(f"Nonfinite inference or separation requires review: {name}")
    table["scenario"] = name
    table["family"] = family
    table["outcome"] = outcome
    table["fdr_adjusted_p"] = np.nan
    tested = table["term"].ne("_intercept_")
    table.loc[tested, "fdr_adjusted_p"] = multipletests(table.loc[tested, "p_value"], method="fdr_bh")[1]
    table["odds_ratio"] = np.exp(table["estimate"]) if family == BINOMIAL else np.nan
    table["or_ci_low"] = np.exp(table["conf_low"]) if family == BINOMIAL else np.nan
    table["or_ci_high"] = np.exp(table["conf_high"]) if family == BINOMIAL else np.nan
    metadata = {
        "scenario": name, "family": family, "outcome": outcome, "selection": selection,
        "predictors": list(predictors), "model_participants": len(selected),
        "domain_excluded_for_this_specification": int(prepared["analysis_domain"].sum()) - len(selected),
        "residual_survey_df": float(table["df"].iloc[0]), "iterations": int(result.fitted.stats.iterations),
        "binary_events": int(selected[outcome].sum()) if family == BINOMIAL else None,
    }
    return table, metadata


def run_scenarios(frame):
    prepared = prepare_sensitivity_data(frame)
    tables = []
    scenarios = []
    for name, predictors, outcome, family, selection in SCENARIOS:
        print(f"  Fitting {name}...", flush=True)
        table, metadata = fit_scenario(prepared, name, predictors, outcome, family, selection)
        tables.append(table)
        scenarios.append(metadata)
    return pd.concat(tables, ignore_index=True), scenarios, prepared