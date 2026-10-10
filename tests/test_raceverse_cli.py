import contextlib
import io
import unittest

from raceverse.cli import build_parser


class ProductionLevelPolicyTest(unittest.TestCase):
    def test_prediction_commands_default_to_formation(self):
        parser = build_parser()
        predict = parser.parse_args(["predict", "--date", "2026-10-10"])
        simulate = parser.parse_args(["simulate", "--race-id", "test-race"])
        self.assertEqual(predict.level, "formation")
        self.assertEqual(simulate.level, "formation")

    def test_prediction_commands_allow_pace(self):
        parser = build_parser()
        predict = parser.parse_args(["predict", "--date", "2026-10-10", "--level", "pace"])
        simulate = parser.parse_args(["simulate", "--race-id", "test-race", "--level", "pace"])
        self.assertEqual(predict.level, "pace")
        self.assertEqual(simulate.level, "pace")

    def test_full_is_not_available_for_production_predictions(self):
        parser = build_parser()
        commands = (
            ["predict", "--date", "2026-10-10", "--level", "full"],
            ["simulate", "--race-id", "test-race", "--level", "full"],
        )
        for command in commands:
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parser.parse_args(command)
