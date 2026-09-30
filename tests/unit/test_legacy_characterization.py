import unittest

from aivp.legacy.orchestrator_v1 import (
    aggregate_risk,
    blocking_findings,
    normalize_findings,
    rule_based_risk,
)


class LegacyCharacterizationTests(unittest.TestCase):
    def test_rule_based_risk_low(self):
        result = rule_based_risk(
            {
                "risk_policy": {
                    "high_risk_paths": ["auth/**"],
                    "high_risk_patterns": ["DROP TABLE"],
                }
            },
            ["username.py"],
            "+ return username.strip().lower()",
        )

        self.assertEqual(
            result,
            {
                "risk": "low",
                "reasons": ["no deterministic high-risk rule matched"],
            },
        )

    def test_rule_based_risk_high_by_path(self):
        result = rule_based_risk(
            {
                "risk_policy": {
                    "high_risk_paths": ["auth/**"],
                    "high_risk_patterns": [],
                }
            },
            ["auth/access.py"],
            "",
        )

        self.assertEqual(result["risk"], "high")
        self.assertEqual(
            result["reasons"],
            ["path matches high-risk rule: auth/access.py ~ auth/**"],
        )

    def test_aggregate_risk_large_disagreement(self):
        result = aggregate_risk(
            {"risk": "high"},
            {"risk": "high"},
            {"risk": "low"},
        )

        self.assertEqual(
            result,
            {
                "final": "high",
                "sources": {
                    "rule": "high",
                    "codex": "high",
                    "claude": "low",
                },
                "large_disagreement": True,
                "human_required": True,
            },
        )

    def test_normalize_and_block_findings(self):
        findings = normalize_findings(
            [
                {
                    "severity": "CRITICAL",
                    "category": "security",
                    "file": "auth/access.py",
                    "line": 10,
                    "reason": "unsafe",
                    "suggested_direction": "fix it",
                },
                {
                    "severity": "weird",
                    "reason": "unknown severity",
                },
            ]
        )

        self.assertEqual(findings[0]["severity"], "critical")
        self.assertEqual(findings[1]["severity"], "minor")
        self.assertEqual(len(blocking_findings({"findings": findings})), 1)


if __name__ == "__main__":
    unittest.main()
