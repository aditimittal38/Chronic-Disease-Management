"""Focused regression checks for the robustness-validation methods."""

import unittest

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from threadpoolctl import threadpool_limits

from prediction_models import (
    CATEGORICAL_FEATURES, FEATURES, FEATURE_GROUPS, NUMERIC_FEATURES,
    TARGET, fit_comparison, make_models,
)
from uncertainty_importance import (
    bootstrap_metrics, grouped_importance, individual_importance,
    patient_bootstrap_weights, subgroup_metrics,
)


def toy_predictors(count=200):
    frame = pd.DataFrame({column: np.arange(count, dtype=float) for column in NUMERIC_FEATURES})
    for column in CATEGORICAL_FEATURES:
        frame[column] = np.where(np.arange(count) % 2, "Known", "Unknown")
    return frame


class ValidationTests(unittest.TestCase):
    def test_feature_groups_cover_predictors_without_leakage(self):
        grouped = [column for columns in FEATURE_GROUPS.values() for column in columns]
        self.assertCountEqual(grouped, FEATURES)
        self.assertEqual(len(grouped), len(set(grouped)))
        self.assertFalse({TARGET, "readmitted", "encounter_id", "patient_nbr"} & set(FEATURES))

    def test_bootstrap_keeps_whole_patients(self):
        patients = pd.Series(["a", "a", "b", "c", "c", "c", "d"])
        weights = patient_bootstrap_weights(patients, np.random.default_rng(42))
        by_patient = pd.DataFrame({"patient": patients, "weight": weights}).groupby("patient")["weight"]
        self.assertTrue((by_patient.nunique() == 1).all())
        self.assertEqual(by_patient.first().sum(), patients.nunique())
        self.assertTrue(np.array_equal(weights, patient_bootstrap_weights(patients, np.random.default_rng(42))))

    def test_paired_bootstrap_identical_models_have_zero_difference(self):
        outcome = np.repeat(np.arange(40) % 2, 2)
        probabilities = np.where(outcome, 0.65, 0.35)
        predictions = pd.DataFrame({
            "encounter_id": np.arange(80).astype(str), "patient_nbr": np.repeat(np.arange(40).astype(str), 2),
            TARGET: outcome, "initial_logistic": probabilities, "expanded_logistic": probabilities,
            "hist_gradient_boosting": probabilities, "constant_risk_baseline": 0.5,
        })
        intervals, differences = bootstrap_metrics(predictions, repetitions=20)
        self.assertTrue((intervals["valid_repetitions"] == 20).all())
        self.assertTrue((intervals["ci_low"] <= intervals["ci_high"]).all())
        self.assertTrue(np.allclose(differences[["difference", "ci_low", "ci_high"]], 0))

    def test_constant_predictions_have_zero_permutation_importance(self):
        predictors = toy_predictors(80)
        outcome = np.arange(80) % 2
        classifier = DummyClassifier(strategy="prior").fit(predictors, outcome)
        models = {"constant": classifier}
        individual = individual_importance(models, predictors, outcome, repetitions=2)
        grouped = grouped_importance(models, predictors, outcome, repetitions=2)
        self.assertTrue(np.allclose(individual["mean_score_drop"], 0))
        self.assertTrue(np.allclose(grouped["mean_score_drop"], 0))

    def test_subgroup_alignment_and_sparse_groups(self):
        outcome = np.arange(80) % 2
        test = pd.DataFrame({
            "encounter_id": np.arange(80).astype(str), "patient_nbr": np.arange(80).astype(str),
            "age_group": ["Main"] * 79 + ["Sparse"], "gender": "Female", "race": "Other",
        })
        predictions = test[["encounter_id", "patient_nbr"]].copy()
        predictions[TARGET] = outcome
        predictions["constant"] = 0.5
        results = subgroup_metrics(test, predictions.iloc[::-1])
        sparse = results.loc[(results["variable"] == "age_group") & (results["category"] == "Sparse")]
        self.assertEqual(int(sparse.iloc[0]["early_readmissions"]), 1)
        self.assertTrue(sparse[["roc_auc", "average_precision", "brier_score"]].isna().all().all())

    def test_preprocessing_uses_training_data_only(self):
        training = toy_predictors(200)
        held_out = toy_predictors(20)
        held_out[NUMERIC_FEATURES] = 10000.0
        held_out[CATEGORICAL_FEATURES] = "Unseen_test_category"
        with threadpool_limits(limits=2):
            for model in make_models().values():
                model.fit(training, np.arange(200) % 2)
                scaler = model.named_steps["preprocessing"].named_transformers_["numeric"]
                self.assertTrue(np.allclose(scaler.mean_, 99.5))
                self.assertTrue(np.isfinite(model.predict_proba(held_out)).all())

    def test_comparison_rejects_wrong_held_out_encounters(self):
        frame = toy_predictors(80)
        frame["encounter_id"] = np.arange(80).astype(str)
        frame["patient_nbr"] = np.repeat(np.arange(40).astype(str), 2)
        frame[TARGET] = np.arange(80) % 2
        wrong_predictions = pd.DataFrame({"encounter_id": ["not_in_dataset"]})
        with self.assertRaisesRegex(ValueError, "held-out encounters"):
            fit_comparison(frame, wrong_predictions)


if __name__ == "__main__":
    unittest.main()