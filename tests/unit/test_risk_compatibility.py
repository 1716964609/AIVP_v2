import unittest

from aivp.legacy.orchestrator_v1 import (
    aggregate_risk as legacy_aggregate_risk,
    rule_based_risk as legacy_rule_based_risk,
)

from aivp.risk.aggregate import aggregate_risk
from aivp.risk.rules import rule_based_risk


class RiskCompatibilityTests(unittest.TestCase):
    def test_rule_engine_matches_legacy(self):
        config = {
            "risk_policy": {
                "high_risk_paths": [
                    "auth/**",
                    "security/**",
                    "db/migrations/**",
                ],
                "high_risk_patterns": [
                    "DROP TABLE",
                    "iam:PassRole",
                ],
            }
        }

        cases = [
            (["username.py"], "safe diff"),
            (["auth/access.py"], "safe diff"),
            (["pricing.py"], "+ DROP TABLE foo"),
        ]

        for paths, diff in cases:
            with self.subTest(paths=paths, diff=diff):
                self.assertEqual(
                    rule_based_risk(config, paths, diff),
                    legacy_rule_based_risk(config, paths, diff),
                )

    def test_aggregate_matches_legacy(self):
        cases = [
            ("low", "low", "low"),
            ("low", "medium", "low"),
            ("high", "high", "low"),
            ("low", "low", "high"),
            ("medium", "medium", "medium"),
        ]

        for rule, codex, claude in cases:
            with self.subTest(
                rule=rule,
                codex=codex,
                claude=claude,
            ):
                inputs = (
                    {"risk": rule},
                    {"risk": codex},
                    {"risk": claude},
                )

                self.assertEqual(
                    aggregate_risk(*inputs),
                    legacy_aggregate_risk(*inputs),
                )


if __name__ == "__main__":
    unittest.main()
