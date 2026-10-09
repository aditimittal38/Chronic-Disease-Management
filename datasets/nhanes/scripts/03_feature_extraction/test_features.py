"""Regression checks for missingness-aware NHANES feature definitions."""

import unittest

import numpy as np
import pandas as pd

from feature_rules import (
    ACTIVITY_FIELDS, DAYS_PER_MONTH, DAYS_PER_YEAR,
    activity_features, activity_minutes, add_demographic_features,
    binary_response, glucose_frequency,
)


def activity_fixture(count=2):
    values = pd.DataFrame(index=range(count))
    statuses = pd.DataFrame(index=range(count))
    for _, gate, days, minutes, _ in ACTIVITY_FIELDS:
        values[gate] = 2.0
        values[days] = np.nan
        values[minutes] = np.nan
        statuses[days] = "skip_no_activity"
        statuses[minutes] = "skip_no_activity"
    return values, statuses


class FeatureTests(unittest.TestCase):
    def test_glucose_units_and_explicit_never(self):
        values = pd.DataFrame({"DID260": [2, 7, DAYS_PER_MONTH, DAYS_PER_YEAR, 0, 2, np.nan],
                               "DIQ260U": [1, 2, 3, 4, np.nan, np.nan, 1]})
        statuses = pd.DataFrame({"DID260": ["observed"] * 6 + ["dont_know"]})
        frequency, reason = glucose_frequency(values, statuses)
        self.assertTrue(np.allclose(frequency.iloc[:5], [2, 1, 1, 1, 0]))
        self.assertTrue(frequency.iloc[5:].isna().all())
        self.assertEqual(reason.iloc[4:].tolist(), ["explicit_never", "missing_required_unit", "dont_know"])

    def test_activity_requires_gate_and_skip_reason(self):
        values = pd.DataFrame({"Gate": [1, 2, np.nan, 2], "Days": [3, np.nan, np.nan, np.nan], "Minutes": [30, np.nan, np.nan, np.nan]})
        statuses = pd.DataFrame({"Days": ["observed", "skip_no_activity", "gate_unknown", "routing_conflict"],
                                 "Minutes": ["observed", "skip_no_activity", "gate_unknown", "skip_no_activity"]})
        weekly = activity_minutes(values, statuses, "Gate", "Days", "Minutes")
        self.assertEqual(weekly.iloc[:2].tolist(), [90, 0])
        self.assertTrue(weekly.iloc[2:].isna().all())

    def test_missing_activity_does_not_become_partial_total(self):
        values, statuses = activity_fixture()
        values.loc[1, "PAQ650"] = np.nan
        features = activity_features(values, statuses)
        self.assertEqual(features.loc[0, "activity_total_minutes_week"], 0)
        self.assertTrue(pd.isna(features.loc[1, "activity_total_minutes_week"]))
        self.assertTrue(pd.isna(features.loc[1, "activity_at_least_150_equivalent_minutes"]))
        self.assertEqual(features["activity_complete"].tolist(), [1, 0])

    def test_vigorous_equivalence_and_150_boundary(self):
        values, statuses = activity_fixture(1)
        values.loc[0, ["PAQ605", "PAQ610", "PAD615"]] = [1, 3, 25]
        statuses.loc[0, ["PAQ610", "PAD615"]] = "observed"
        features = activity_features(values, statuses)
        self.assertEqual(features.loc[0, "activity_total_minutes_week"], 75)
        self.assertEqual(features.loc[0, "activity_met_minutes_week"], 600)
        self.assertEqual(features.loc[0, "activity_moderate_equivalent_minutes_week"], 150)
        self.assertEqual(features.loc[0, "activity_at_least_150_equivalent_minutes"], 1)

    def test_implausible_total_is_flagged_not_deleted(self):
        values, statuses = activity_fixture(1)
        for _, gate, days, minutes, _ in ACTIVITY_FIELDS:
            values.loc[0, [gate, days, minutes]] = [1, 7, 1000]
            statuses.loc[0, [days, minutes]] = "observed"
        features = activity_features(values, statuses)
        self.assertEqual(features.loc[0, "activity_total_minutes_week"], 35000)
        self.assertEqual(features.loc[0, "activity_total_exceeds_calendar_week"], 1)

    def test_adult_category_boundaries(self):
        values = pd.DataFrame({"RIDAGEYR": [19, 20, 39, 40, 60, 80], "BMXBMI": [18.5, 18.5, 25, 30, 18.4, np.nan],
                               "INDFMPIR": [0, 1, 2, 5, np.nan, 4.9], "DMDEDUC2": [np.nan, 1, 2, 3, 4, 5]})
        features = pd.DataFrame(index=values.index)
        add_demographic_features(features, values)
        self.assertTrue(pd.isna(features.loc[0, "age_group"]))
        self.assertEqual(features["age_group"].iloc[1:].astype(str).tolist(), ["20-39", "20-39", "40-59", "60-79", "80+"])
        self.assertEqual(str(features.loc[1, "bmi_group"]), "18.5 to below 25")
        self.assertEqual(str(features.loc[2, "bmi_group"]), "25 to below 30")
        self.assertEqual(str(features.loc[3, "bmi_group"]), "30 or above")
        self.assertEqual(str(features.loc[3, "poverty_ratio_group"]), "5 or above")

    def test_binary_nonresponse_stays_missing(self):
        result = binary_response(pd.Series([1, 2, np.nan]))
        self.assertEqual(result.iloc[:2].tolist(), [1, 0])
        self.assertTrue(pd.isna(result.iloc[2]))


if __name__ == "__main__":
    unittest.main()