"""Compare fixed models using training-only preprocessing and grouped evaluation."""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


TARGET = "readmitted_30d"
NUMERIC_FEATURES = [
    "number_inpatient", "number_emergency", "number_outpatient", "num_medications",
    "number_diagnoses", "time_in_hospital", "num_lab_procedures", "num_procedures",
    "medication_changed",
]
CATEGORICAL_FEATURES = [
    "age_group", "gender", "race", "diag_1_group", "diag_2_group", "diag_3_group",
    "insulin", "A1Cresult", "max_glu_serum", "admission_type_id",
    "discharge_disposition_id", "payer_code", "medical_specialty",
]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
FEATURE_GROUPS = {
    "prior_utilization": ["number_inpatient", "number_emergency", "number_outpatient"],
    "demographics": ["age_group", "gender", "race"],
    "clinical_burden": ["diag_1_group", "diag_2_group", "diag_3_group", "number_diagnoses", "time_in_hospital", "num_lab_procedures", "num_procedures"],
    "treatment": ["num_medications", "medication_changed", "insulin"],
    "lab_results_and_testing": ["A1Cresult", "max_glu_serum"],
    "care_context": ["admission_type_id", "discharge_disposition_id", "payer_code", "medical_specialty"],
}


def predictor_frame(frame):
    predictors = frame[FEATURES].copy()
    for column in NUMERIC_FEATURES:
        predictors[column] = pd.to_numeric(predictors[column], errors="raise")
    for column in CATEGORICAL_FEATURES:
        predictors[column] = predictors[column].astype(str)
    return predictors


def make_models():
    classifiers = {
        "expanded_logistic": LogisticRegression(C=1.0, max_iter=1000, random_state=42),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=100, learning_rate=0.08, max_leaf_nodes=15,
            min_samples_leaf=80, l2_regularization=5.0,
            early_stopping=False, random_state=42,
        ),
    }
    models = {}
    for name, classifier in classifiers.items():
        preprocessing = ColumnTransformer([
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
        ])
        models[name] = Pipeline([("preprocessing", preprocessing), ("classifier", classifier)], memory=None)
    return models


def metric_values(outcome, probabilities, weights=None):
    return {
        "roc_auc": float(roc_auc_score(outcome, probabilities, sample_weight=weights)),
        "average_precision": float(average_precision_score(outcome, probabilities, sample_weight=weights)),
        "brier_score": float(brier_score_loss(outcome, probabilities, sample_weight=weights)),
    }


def fit_comparison(frame, previous_predictions):
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_indices, test_indices = next(splitter.split(frame, groups=frame["patient_nbr"]))
    train = frame.iloc[train_indices]
    test = frame.iloc[test_indices]
    if set(train["patient_nbr"]) & set(test["patient_nbr"]):
        raise ValueError("Patients overlap between training and test data.")
    if set(previous_predictions["encounter_id"]) != set(test["encounter_id"]):
        raise ValueError("Step 4 predictions do not match the fixed held-out encounters.")
    predictors = predictor_frame(frame)
    training_predictors = predictors.iloc[train_indices]
    test_predictors = predictors.iloc[test_indices]
    outcome = test[TARGET].to_numpy()
    aligned = previous_predictions.set_index("encounter_id").loc[test["encounter_id"]]
    if not np.array_equal(aligned[TARGET].to_numpy(), outcome):
        raise ValueError("The original held-out labels do not match this cohort.")
    predictions = test[["encounter_id", "patient_nbr", TARGET]].copy()
    predictions["initial_logistic"] = aligned["predicted_probability"].to_numpy()
    predictions["constant_risk_baseline"] = float(train[TARGET].mean())
    models = make_models()
    for name, model in models.items():
        print(f"  Fitting {name}...", flush=True)
        model.fit(training_predictors, train[TARGET])
        predictions[name] = model.predict_proba(test_predictors)[:, 1]
    rows = [
        {"model": name, **metric_values(outcome, predictions[name].to_numpy())}
        for name in predictions.columns if name not in ("encounter_id", "patient_nbr", TARGET)
    ]
    split_summary = {
        "seed": 42, "training_encounters": len(train), "test_encounters": len(test),
        "training_patients": int(train["patient_nbr"].nunique()), "test_patients": int(test["patient_nbr"].nunique()),
        "overlapping_patients": 0, "test_prevalence": float(test[TARGET].mean()),
    }
    return models, test, test_predictors, predictions, pd.DataFrame(rows), split_summary