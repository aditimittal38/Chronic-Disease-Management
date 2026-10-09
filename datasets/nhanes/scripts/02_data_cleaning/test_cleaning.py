"""Regression tests for NHANES response, routing, and cohort semantics."""

import unittest

import numpy as np
import pandas as pd

from cleaning_rules import DESIGN_COLUMNS, clean_column, clean_frame, make_rules


def sample_frame(count=2):
    frame = pd.DataFrame({column: [np.nan] * count for column in make_rules()})
    frame["SEQN"] = np.arange(1, count + 1)
    for column, value in {"RIDAGEYR": 50, "RIAGENDR": 1, "RIDRETH3": 3, "RIDSTATR": 2,
                          "WTMEC2YR": 100, "WTINT2YR": 120, "SDMVSTRA": 134, "SDMVPSU": 1,
                          "DIQ010": 1, "LBXGH": 7.0}.items():
        frame[column] = value
    return frame


class CleaningTests(unittest.TestCase):
    def test_special_codes_are_variable_specific(self):
        values, statuses = clean_column(pd.Series([0, 7, 9, 777, 999]), make_rules()["DID260"])
        self.assertEqual(values.iloc[:3].tolist(), [0, 7, 9])
        self.assertTrue(values.iloc[3:].isna().all())
        self.assertEqual(statuses.iloc[3:].tolist(), ["refused", "dont_know"])

    def test_activity_skip_is_not_unknown_or_automatic_zero(self):
        raw = sample_frame()
        raw["PAQ605"] = [2, 9]
        values, statuses, _ = clean_frame(raw, {})
        self.assertTrue(values["PAQ610"].isna().all())
        self.assertEqual(statuses["PAQ610"].tolist(), ["skip_no_activity", "gate_unknown"])

    def test_never_checks_and_missing_required_unit_are_different(self):
        raw = sample_frame()
        raw["DID260"] = [0, 2]
        values, statuses, _ = clean_frame(raw, {})
        self.assertEqual(values["DID260"].tolist(), [0, 2])
        self.assertEqual(statuses["DIQ260U"].tolist(), ["skip_never_checks_glucose", "missing_required_unit"])

    def test_no_usual_doctor_does_not_mean_zero_visits(self):
        raw = sample_frame(1)
        raw["DIQ240"] = 2
        values, statuses, _ = clean_frame(raw, {})
        self.assertTrue(pd.isna(values.loc[0, "DID250"]))
        self.assertEqual(statuses.loc[0, "DID250"], "skip_no_usual_diabetes_doctor")

    def test_routing_conflict_is_flagged(self):
        raw = sample_frame(1)
        raw["PAQ605"] = 2
        raw["PAQ610"] = 3
        values, statuses, _ = clean_frame(raw, {})
        self.assertTrue(pd.isna(values.loc[0, "PAQ610"]))
        self.assertEqual(statuses.loc[0, "PAQ610"], "routing_conflict")

    def test_missing_outcome_keeps_universe_but_not_domain(self):
        raw = sample_frame()
        raw.loc[1, "LBXGH"] = np.nan
        values, _, _ = clean_frame(raw, {})
        self.assertEqual(len(values), 2)
        self.assertEqual(values["analysis_domain"].tolist(), [1, 0])
        for column in DESIGN_COLUMNS:
            self.assertTrue(np.allclose(values[column], raw[column], equal_nan=True))

    def test_uncertain_pregnancy_has_separate_sensitivity_flag(self):
        raw = sample_frame()
        raw["RIAGENDR"] = 2
        raw["RIDAGEYR"] = 30
        raw["RIDEXPRG"] = [1, 3]
        values, statuses, _ = clean_frame(raw, {})
        self.assertEqual(values["analysis_domain"].tolist(), [0, 1])
        self.assertEqual(values["analysis_domain_known_pregnancy_status_sensitivity"].tolist(), [0, 0])
        self.assertEqual(statuses.loc[1, "RIDEXPRG"], "cannot_ascertain")

    def test_top_codes_and_interval_codes_are_not_exact_ages(self):
        raw = sample_frame()
        raw["RIDAGEYR"] = 80
        raw["DID040"] = [80, 666]
        raw["INDFMPIR"] = 5
        values, statuses, _ = clean_frame(raw, {})
        self.assertEqual(statuses["RIDAGEYR"].tolist(), ["top_coded", "top_coded"])
        self.assertEqual(statuses["DID040"].tolist(), ["top_coded", "age_below_one_interval"])
        self.assertTrue(pd.isna(values.loc[1, "DID040"]))


if __name__ == "__main__":
    unittest.main()