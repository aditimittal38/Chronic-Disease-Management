"""Check whether adjusted associations depend on study and model assumptions."""

import csv
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from adjusted_model import MODEL_FORMULA
from data_cleaning import DROP_COLUMNS, clean_value
from feature_extraction import extract_features
from outcome_analysis import MODEL_CATEGORIES, NUMERIC_COLUMNS


ROOT = Path(__file__).resolve().parents[2]
RAW_SOURCE = ROOT / "data" / "raw" / "diabetic_data.csv"
DEATH_CODES = {"11", "19", "20", "21"}
KEY_PARAMETERS = (
    "number_inpatient", "number_emergency", "number_outpatient", "num_medications",
    "number_diagnoses", "time_in_hospital", "medication_changed",
)


def hospice_inclusive_frame():
    rows = []
    with RAW_SOURCE.open(newline="", encoding="utf-8-sig") as handle:
        for record in csv.DictReader(handle):
            if record["discharge_disposition_id"] in DEATH_CODES:
                continue
            cleaned = {column: clean_value(column, value)[0] for column, value in record.items() if column not in DROP_COLUMNS}
            rows.append(extract_features(cleaned))
    frame = pd.DataFrame(rows)
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    for column, categories in MODEL_CATEGORIES.items():
        frame[column] = pd.Categorical(frame[column], categories=categories)
    if frame[list(MODEL_CATEGORIES)].isna().any().any():
        raise ValueError("The alternative cohort has unrecognized model categories.")
    return frame


def fit_sensitivity(frame, formula, scenario):
    print(f"  Fitting sensitivity: {scenario} ({len(frame):,} encounters)...", flush=True)
    model = smf.glm(formula, data=frame, family=sm.families.Binomial(), missing="raise")
    if np.linalg.matrix_rank(model.exog) != model.exog.shape[1]:
        raise ValueError(f"Sensitivity design is not full rank: {scenario}")
    result = model.fit(maxiter=100, cov_type="cluster", cov_kwds={"groups": frame["patient_nbr"]})
    if not result.converged or int(result.nobs) != len(frame):
        raise ValueError(f"Sensitivity fit failed or dropped encounters: {scenario}")
    intervals = result.conf_int()
    rows = []
    for parameter in result.params.index:
        if parameter not in KEY_PARAMETERS and not parameter.startswith("np.log1p("):
            continue
        values = np.exp([result.params[parameter], intervals.loc[parameter, 0], intervals.loc[parameter, 1]])
        if not np.isfinite(values).all():
            raise ValueError(f"Unbounded sensitivity estimates: {scenario}, {parameter}")
        rows.append({
            "scenario": scenario, "encounters": len(frame), "patients": int(frame["patient_nbr"].nunique()),
            "parameter": parameter, "adjusted_odds_ratio": values[0], "ci_low": values[1], "ci_high": values[2],
            "clustered_p_value": float(result.pvalues[parameter]),
            "unit": "One unit in log(1 + visit count)" if parameter.startswith("np.log1p(") else "One additional recorded unit (or 0 to 1 for change flag)",
        })
    metadata = {
        "scenario": scenario, "encounters": len(frame), "patients": int(frame["patient_nbr"].nunique()),
        "early_readmissions": int(frame["readmitted_30d"].sum()), "formula": formula,
        "converged": bool(result.converged),
    }
    return rows, metadata


def run_sensitivities(frame, baseline_odds):
    selected = baseline_odds.loc[baseline_odds["parameter"].isin(KEY_PARAMETERS)].copy()
    selected["scenario"] = "baseline_adjustment"
    selected["encounters"] = len(frame)
    selected["patients"] = int(frame["patient_nbr"].nunique())
    selected["unit"] = "One additional recorded unit (or 0 to 1 for change flag)"
    rows = selected.drop(columns=["coefficient"]).to_dict("records")
    metadata = []
    one_per_patient = frame.sample(frac=1, random_state=42).drop_duplicates("patient_nbr")
    result_rows, details = fit_sensitivity(one_per_patient, MODEL_FORMULA, "one_encounter_per_patient")
    rows.extend(result_rows)
    metadata.append(details)
    nonlinear_formula = MODEL_FORMULA
    for column in ("number_inpatient", "number_emergency", "number_outpatient"):
        nonlinear_formula = nonlinear_formula.replace(column, f"np.log1p({column})")
    result_rows, details = fit_sensitivity(frame, nonlinear_formula, "log_utilization")
    rows.extend(result_rows)
    metadata.append(details)
    expanded = frame.copy()
    expanded["admission_group"] = expanded["admission_type_id"].map({"1": "Emergency", "2": "Urgent", "3": "Elective"}).fillna("Other_or_unknown")
    expanded["discharge_group"] = np.where(expanded["discharge_disposition_id"].isin(["1", "6", "8"]), "Home", "Other_or_unknown")
    expanded["specialty_recorded"] = expanded["medical_specialty"].ne("Unknown").astype(int)
    expanded["payer_recorded"] = expanded["payer_code"].ne("Unknown").astype(int)
    expanded_formula = (
        MODEL_FORMULA + " + num_lab_procedures + num_procedures + specialty_recorded + payer_recorded"
        ' + C(admission_group, Treatment(reference="Emergency"))'
        ' + C(discharge_group, Treatment(reference="Home"))'
        ' + C(diag_2_group, Treatment(reference="Other"))'
        ' + C(diag_3_group, Treatment(reference="Other"))'
    )
    result_rows, details = fit_sensitivity(expanded, expanded_formula, "expanded_adjustment")
    rows.extend(result_rows)
    metadata.append(details)
    alternative = hospice_inclusive_frame()
    result_rows, details = fit_sensitivity(alternative, MODEL_FORMULA, "hospice_included_deaths_excluded")
    rows.extend(result_rows)
    metadata.append(details)
    return pd.DataFrame(rows), metadata