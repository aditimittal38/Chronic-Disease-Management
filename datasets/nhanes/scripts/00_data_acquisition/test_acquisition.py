"""Check component keys and safe participant merging without network access."""

import unittest

import pandas as pd

from download_data import XPORT_ZERO_ARTIFACT, merge_components, restore_transport_zeros, validate_component


class AcquisitionTests(unittest.TestCase):
    def test_transport_zero_restoration_is_specific(self):
        frame = pd.DataFrame({"Value": [XPORT_ZERO_ARTIFACT, 0.0, 7.0, 99.0, float("nan")]})
        restored, count = restore_transport_zeros(frame)
        self.assertEqual(count, 1)
        self.assertEqual(restored["Value"].iloc[:4].tolist(), [0.0, 0.0, 7.0, 99.0])
        self.assertTrue(pd.isna(restored["Value"].iloc[4]))

    def test_duplicate_participants_rejected(self):
        frame = pd.DataFrame({"SEQN": [1, 1]})
        with self.assertRaises(ValueError):
            validate_component(frame, "Probe")

    def test_left_join_preserves_unmeasured_people(self):
        components = {
            "DEMO_J": pd.DataFrame({"SEQN": [1, 2, 3], "RIDAGEYR": [20, 30, 40]}),
            "GHB_J": pd.DataFrame({"SEQN": [2], "LBXGH": [7.5]}),
        }
        merged, joins = merge_components(components)
        self.assertEqual(len(merged), 3)
        self.assertEqual(int(merged["LBXGH"].isna().sum()), 2)
        self.assertEqual(joins[0]["matched_participants"], 1)

    def test_outside_demographic_universe_rejected(self):
        components = {"DEMO_J": pd.DataFrame({"SEQN": [1]}), "GHB_J": pd.DataFrame({"SEQN": [2]})}
        with self.assertRaises(ValueError):
            merge_components(components)

    def test_ambiguous_overlapping_columns_rejected(self):
        components = {"DEMO_J": pd.DataFrame({"SEQN": [1], "Value": [1]}), "DIQ_J": pd.DataFrame({"SEQN": [1], "Value": [2]})}
        with self.assertRaises(ValueError):
            merge_components(components)

    def test_noninteger_identifier_rejected(self):
        frame = pd.DataFrame({"SEQN": [1.5]})
        with self.assertRaises(ValueError):
            validate_component(frame, "Probe")


if __name__ == "__main__":
    unittest.main()