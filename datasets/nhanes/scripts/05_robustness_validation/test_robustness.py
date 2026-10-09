"""Check sensitivity selection, fixed definitions, and full-design inference."""

import unittest

import numpy as np
import pandas as pd
import statsmodels.api as sm

from robustness_validation import response_coverage, stability_table
from sensitivity_models import (
    BINOMIAL, CORE_PREDICTORS, GAUSSIAN, SCENARIOS,
    fit_scenario, prepare_sensitivity_data, scenario_domain,
)
from survey_methods import MODEL_PREDICTORS
from test_survey_analysis import regression_design


def sensitivity_fixture():
    frame = regression_design()
    frame["analysis_domain_known_pregnancy_status_sensitivity"] = 1
    frame.loc[1, "analysis_domain_known_pregnancy_status_sensitivity"] = 0
    frame["DIQ010"] = 1
    frame["RIDEXPRG"] = np.nan
    return frame


class RobustnessTests(unittest.TestCase):
    def test_reduced_same_cases_honors_original_sample(self):
        prepared = prepare_sensitivity_data(sensitivity_fixture())
        original = scenario_domain(prepared, CORE_PREDICTORS, "LBXGH", "original_complete_cases")
        self.assertTrue(original.equals(prepared["model_domain"].eq(1)))
        self.assertEqual(int(original.sum()), 149)

    def test_income_omission_changes_selection_not_imputation(self):
        prepared = prepare_sensitivity_data(sensitivity_fixture())
        predictors = tuple(column for column in MODEL_PREDICTORS if column != "poverty_ratio")
        alternative = scenario_domain(prepared, predictors, "LBXGH", "primary")
        self.assertEqual(int(alternative.sum()), 150)
        self.assertTrue(pd.isna(prepared.loc[0, "poverty_ratio"]))

    def test_pregnancy_sensitivity_uses_recorded_flag(self):
        prepared = prepare_sensitivity_data(sensitivity_fixture())
        selected = scenario_domain(prepared, MODEL_PREDICTORS, "LBXGH", "pregnancy_sensitivity")
        self.assertEqual(int(selected.sum()), 148)
        self.assertFalse(selected.loc[1])

    def test_top_code_flags_keep_unknowns_and_source_values(self):
        frame = sensitivity_fixture()
        frame.loc[1, "RIDAGEYR"] = 80
        frame.loc[1, "INDFMPIR"] = 5
        prepared = prepare_sensitivity_data(frame)
        self.assertEqual(prepared.loc[1, "age_80_plus"], 1)
        self.assertEqual(prepared.loc[1, "poverty_ratio_5_plus"], 1)
        self.assertTrue(pd.isna(prepared.loc[0, "poverty_ratio_5_plus"]))
        self.assertEqual(prepared.loc[1, "RIDAGEYR"], 80)
        self.assertEqual(prepared.loc[1, "INDFMPIR"], 5)

    def test_reduced_survey_model_matches_independent_wls_points(self):
        prepared = prepare_sensitivity_data(sensitivity_fixture())
        table, metadata = fit_scenario(prepared, "Probe", CORE_PREDICTORS, "LBXGH", GAUSSIAN, "primary")
        selected = prepared.loc[scenario_domain(prepared, CORE_PREDICTORS, "LBXGH", "primary")]
        reference = sm.WLS(selected["LBXGH"], sm.add_constant(selected[list(CORE_PREDICTORS)]), weights=selected["WTMEC2YR"]).fit()
        self.assertTrue(np.allclose(table["estimate"], reference.params, atol=1e-8))
        self.assertEqual(metadata["residual_survey_df"], 9)
        self.assertEqual(metadata["model_participants"], 149)
        self.assertEqual(len(prepared), 150)
        self.assertTrue(table["odds_ratio"].isna().all())

    def test_single_class_binary_model_is_rejected(self):
        prepared = prepare_sensitivity_data(sensitivity_fixture())
        prepared["binary_probe"] = 0
        with self.assertRaisesRegex(ValueError, "both classes"):
            fit_scenario(prepared, "Probe", MODEL_PREDICTORS, "binary_probe", BINOMIAL, "original_complete_cases")

    def test_response_coverage_does_not_change_outcome(self):
        frame = sensitivity_fixture()
        frame.loc[2, "LBXGH"] = np.nan
        original = frame.copy(deep=True)
        result = response_coverage(frame)
        expected = np.average(frame["LBXGH"].notna().astype(int), weights=frame["WTMEC2YR"])
        self.assertAlmostEqual(result.loc[0, "est"], expected)
        self.assertEqual(result.loc[0, "without_hba1c"], 1)
        pd.testing.assert_frame_equal(frame, original)

    def test_stability_does_not_mix_coefficient_scales(self):
        table = pd.DataFrame({"family": [GAUSSIAN, GAUSSIAN, BINOMIAL], "term": ["insulin_use"] * 3,
                              "estimate": [1.0, 1.2, -0.2], "conf_low": [0.5, 0.6, -0.8],
                              "conf_high": [1.5, 1.8, 0.4], "fdr_adjusted_p": [0.01, 0.02, 0.9]})
        result = stability_table(table)
        insulin = result.loc[result["parameter"].eq("insulin_use")].iloc[0]
        self.assertEqual(insulin["scenarios_with_parameter"], 2)
        self.assertTrue(insulin["all_coefficients_positive"])

    def test_fixed_models_do_not_include_outcome_or_design_predictors(self):
        excluded = {"SEQN", "LBXGH", "DIQ280", "WTMEC2YR", "SDMVSTRA", "SDMVPSU", "analysis_domain", "hba1c_at_least_8", "hba1c_at_least_7"}
        for _, predictors, _, _, _ in SCENARIOS:
            self.assertFalse(excluded & set(predictors))


if __name__ == "__main__":
    unittest.main()