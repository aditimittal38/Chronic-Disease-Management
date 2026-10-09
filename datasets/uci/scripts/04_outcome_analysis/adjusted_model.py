"""Fit a prespecified adjusted model and evaluate it with patient-separated data."""

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score, brier_score_loss, confusion_matrix, log_loss,
    precision_score, recall_score, roc_auc_score, roc_curve, precision_recall_curve,
)
from sklearn.model_selection import GroupShuffleSplit

from descriptive_analysis import add_adjusted_pvalues


TARGET = "readmitted_30d"
MODEL_FORMULA = (
    "readmitted_30d ~ number_inpatient + number_emergency + number_outpatient"
    " + num_medications + number_diagnoses + time_in_hospital"
    ' + C(age_group, Treatment(reference="Under 40"))'
    ' + C(race, Treatment(reference="Caucasian"))'
    ' + C(diag_1_group, Treatment(reference="Other"))'
    ' + C(insulin, Treatment(reference="No"))'
    ' + C(A1Cresult, Treatment(reference="None")) + medication_changed'
)


def fit_logistic(frame, clustered):
    model = smf.glm(MODEL_FORMULA, data=frame, family=sm.families.Binomial(), missing="raise")
    if np.linalg.matrix_rank(model.exog) != model.exog.shape[1]:
        raise ValueError("The adjusted design matrix is not full rank.")
    options = {"cov_type": "cluster", "cov_kwds": {"groups": frame["patient_nbr"]}} if clustered else {}
    result = model.fit(maxiter=100, **options)
    if not result.converged or not np.isfinite(result.params).all():
        raise ValueError("The logistic model did not produce a finite converged fit.")
    if int(result.nobs) != len(frame):
        raise ValueError("The model silently dropped observations.")
    return result


def fit_adjusted_model(frame):
    result = fit_logistic(frame, clustered=True)
    confidence = result.conf_int()
    odds = pd.DataFrame({
        "parameter": result.params.index, "coefficient": result.params.values,
        "adjusted_odds_ratio": np.exp(result.params.values),
        "ci_low": np.exp(confidence.iloc[:, 0].values),
        "ci_high": np.exp(confidence.iloc[:, 1].values),
        "clustered_p_value": result.pvalues.values,
    })
    odds = odds.loc[odds["parameter"] != "Intercept"].reset_index(drop=True)
    terms = result.wald_test_terms(scalar=True).table.reset_index(names="term")
    terms = terms.loc[terms["term"] != "Intercept"].rename(columns={
        "pvalue": "clustered_p_value", "df_constraint": "degrees_of_freedom",
    })
    terms["clustered_p_value"] = terms["clustered_p_value"].astype(float)
    terms = add_adjusted_pvalues(terms, "clustered_p_value")
    if not np.isfinite(odds[["adjusted_odds_ratio", "ci_low", "ci_high"]].to_numpy()).all():
        raise ValueError("Unbounded odds ratios require investigation.")
    return result, odds, terms


def threshold_metrics(outcome, probabilities, threshold):
    predicted = probabilities >= threshold
    counts = confusion_matrix(outcome, predicted, labels=[0, 1])
    return {
        "threshold": threshold, "precision": float(precision_score(outcome, predicted, zero_division=0)),
        "recall": float(recall_score(outcome, predicted, zero_division=0)),
        "true_negatives": int(counts[0, 0]), "false_positives": int(counts[0, 1]),
        "false_negatives": int(counts[1, 0]), "true_positives": int(counts[1, 1]),
    }


def evaluate_model(frame):
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_indices, test_indices = next(splitter.split(frame, groups=frame["patient_nbr"]))
    train = frame.iloc[train_indices]
    test = frame.iloc[test_indices]
    overlap = set(train["patient_nbr"]) & set(test["patient_nbr"])
    if overlap or train[TARGET].nunique() != 2 or test[TARGET].nunique() != 2:
        raise ValueError("The patient split is invalid or lacks an outcome class.")
    result = fit_logistic(train, clustered=False)
    probabilities = np.asarray(result.predict(test))
    if not np.isfinite(probabilities).all():
        raise ValueError("Nonfinite held-out predictions.")
    baseline = np.full(len(test), train[TARGET].mean())
    evaluation = {
        "seed": 42, "held_out_patient_fraction": 0.2,
        "training_encounters": len(train), "test_encounters": len(test),
        "training_patients": train["patient_nbr"].nunique(), "test_patients": test["patient_nbr"].nunique(),
        "overlapping_patients": len(overlap),
        "test_prevalence": float(test[TARGET].mean()), "training_prevalence": float(train[TARGET].mean()),
        "roc_auc": float(roc_auc_score(test[TARGET], probabilities)),
        "average_precision": float(average_precision_score(test[TARGET], probabilities)),
        "brier_score": float(brier_score_loss(test[TARGET], probabilities)),
        "baseline_brier_score": float(brier_score_loss(test[TARGET], baseline)),
        "log_loss": float(log_loss(test[TARGET], probabilities)),
        "threshold_metrics": [threshold_metrics(test[TARGET], probabilities, threshold) for threshold in (0.2, 0.5)],
    }
    predictions = test[["encounter_id", "patient_nbr", TARGET]].copy()
    predictions["predicted_probability"] = probabilities
    observed, predicted = calibration_curve(test[TARGET], probabilities, n_bins=10, strategy="quantile")
    calibration = pd.DataFrame({"mean_predicted_probability": predicted, "observed_readmission_rate": observed})
    false_positive, true_positive, _ = roc_curve(test[TARGET], probabilities)
    precision, recall, _ = precision_recall_curve(test[TARGET], probabilities)
    curves = {"false_positive": false_positive, "true_positive": true_positive, "precision": precision, "recall": recall}
    return evaluation, predictions, calibration, curves