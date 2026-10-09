"""Test full-design domain inference and prespecified survey regression."""

import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import statsmodels.api as sm

from outcome_analysis import group_estimates
from survey_methods import (
    MODEL_PREDICTORS, domain_mean, fit_adjusted_model, make_sample, model_frame,
)


def small_design():
    return pd.DataFrame({
        "WTMEC2YR": [1.0] * 8, "SDMVSTRA": [1] * 4 + [2] * 4,
        "SDMVPSU": [1, 1, 2, 2] * 2, "LBXGH": [1., 2., 3., 4., 2., 3., 4., 5.],
        "analysis_domain": [1, 0, 1, 0, 1, 0, 1, 0],
    })


def regression_design():
    generator = np.random.default_rng(42)
    count = 150
    frame = pd.DataFrame({
        "WTMEC2YR": generator.uniform(1, 3, count), "SDMVSTRA": np.repeat(np.arange(1, 16), 10),
        "SDMVPSU": np.tile([1] * 5 + [2] * 5, 15), "analysis_domain": 1,
        "RIDAGEYR": generator.integers(20, 80, count), "RIAGENDR": generator.integers(1, 3, count),
        "BMXBMI": generator.uniform(20, 45, count), "INDFMPIR": generator.uniform(0, 5, count),
        "glucose_checks_per_day_equivalent": generator.uniform(0, 5, count),
        "activity_moderate_equivalent_minutes_week": generator.uniform(0, 1000, count),
    })
    for column in ("insulin_use", "oral_diabetes_med_use", "usual_diabetes_professional", "a1c_test_past_year"):
        frame[column] = generator.integers(0, 2, count)
    frame["LBXGH"] = 6 + 0.6 * frame["insulin_use"] + generator.normal(0, 0.4, count)
    frame.loc[0, "INDFMPIR"] = np.nan
    return frame


class SurveyAnalysisTests(unittest.TestCase):
    def test_domain_mean_and_taylor_se_known_example(self):
        sample = make_sample(small_design())
        result = domain_mean(sample)
        self.assertEqual(sample.data.height, 8)
        self.assertAlmostEqual(result["est"], 2.5)
        self.assertAlmostEqual(result["se"], np.sqrt(0.5))
        self.assertEqual(result["df"], 2)
        self.assertEqual(result["n"], 4)

    def test_missing_outside_domain_does_not_change_estimate(self):
        frame = small_design()
        frame.loc[frame["analysis_domain"].eq(0), "LBXGH"] = np.nan
        result = domain_mean(make_sample(frame))
        self.assertAlmostEqual(result["est"], 2.5)
        self.assertAlmostEqual(result["se"], np.sqrt(0.5))

    def test_weight_rescaling_preserves_mean_and_uncertainty(self):
        original = small_design()
        scaled = original.copy()
        scaled["WTMEC2YR"] *= 100
        baseline = domain_mean(make_sample(original))
        result = domain_mean(make_sample(scaled))
        self.assertAlmostEqual(result["est"], baseline["est"])
        self.assertAlmostEqual(result["se"], baseline["se"])

    def test_invalid_design_is_rejected(self):
        frame = small_design()
        frame.loc[0, "WTMEC2YR"] = -1
        with self.assertRaises(ValueError):
            make_sample(frame)

    def test_model_points_match_weighted_least_squares(self):
        frame = regression_design()
        result, table, prepared = fit_adjusted_model(frame)
        selected = prepared.loc[prepared["model_domain"].eq(1)]
        reference = sm.WLS(selected["LBXGH"], sm.add_constant(selected[list(MODEL_PREDICTORS)]), weights=selected["WTMEC2YR"]).fit()
        self.assertTrue(np.allclose(table["estimate"], reference.params, atol=1e-8))
        self.assertEqual(result.fitted.stats.n, 149)
        self.assertEqual(len(prepared), 150)
        self.assertTrue(np.isfinite(table["std_err"]).all())
        self.assertTrue(table.loc[table["term"].eq("_intercept_"), "fdr_adjusted_p"].isna().all())

    def test_sparse_group_has_point_but_no_interval(self):
        frame = small_design()
        frame["group"] = "Sparse"
        with patch("outcome_analysis.GROUP_VARIABLES", ("group",)):
            rows = group_estimates(frame, make_sample(frame))
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows.loc[0, "est"], 2.5)
        self.assertTrue(pd.isna(rows.loc[0, "lci"]))

    def test_model_predictors_exclude_targets_and_design(self):
        excluded = {"SEQN", "LBXGH", "DIQ280", "WTMEC2YR", "SDMVSTRA", "SDMVPSU", "hba1c_at_least_8", "hba1c_at_least_7", "analysis_domain"}
        self.assertFalse(excluded & set(MODEL_PREDICTORS))
        prepared = model_frame(regression_design())
        self.assertEqual(int(prepared["model_domain"].sum()), 149)


if __name__ == "__main__":
    unittest.main()