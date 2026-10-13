from __future__ import annotations

import unittest

import pandas as pd

from src import ranker_new_feature_groups as groups


class NewFeatureGroupCatalogTest(unittest.TestCase):
    def test_catalog_keeps_production_baseline_and_excludes_bloodline(self) -> None:
        report = groups.validate_catalog()
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["baseline_count"], 86)
        self.assertEqual(report["configuration_count"], 16)
        self.assertEqual(report["bloodline_features"], [])
        self.assertTrue(set(groups.BASELINE_FEATURES).isdisjoint(
            feature for values in groups.GROUPS.values() for feature in values
        ))

    def test_configurations_are_baseline_plus_selected_groups(self) -> None:
        configurations = groups.configurations()
        self.assertEqual(configurations[0].mask, "0000")
        self.assertEqual(configurations[-1].mask, "1111")
        self.assertEqual(configurations[0].features, groups.BASELINE_FEATURES)
        self.assertEqual(
            configurations[1].features,
            groups.configuration_features("1000"),
        )
        self.assertEqual(len({config.mask for config in configurations}), 16)

    def test_quality_summary_reports_missing_and_numeric_distribution(self) -> None:
        frame = pd.DataFrame({
            "horse_course_aptitude": [0.0, 1.0, None],
            "horse_distance_aptitude": [0.0, 0.0, 0.5],
        })
        summary = groups.feature_quality_summary(frame)
        course = summary[summary["feature"] == "horse_course_aptitude"].iloc[0]
        missing = summary[summary["feature"] == "jockey_rides"].iloc[0]
        self.assertAlmostEqual(course["missing_rate"], 1 / 3)
        self.assertEqual(course["sample_count"], 2)
        self.assertFalse(missing["available"])


if __name__ == "__main__":
    unittest.main()
