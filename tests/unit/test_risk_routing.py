import unittest

from aivp.risk.routing import (
    aggregate_terminal_high,
    route_codex_risk,
)


class RiskRoutingTests(
    unittest.TestCase
):
    def review(
        self,
        *,
        risk="low",
        confidence=0.95,
        findings=None,
    ):
        return {
            "summary": "review",
            "risk": risk,
            "risk_confidence": confidence,
            "risk_reasons": [],
            "findings": (
                []
                if findings is None
                else findings
            ),
        }

    def rule(
        self,
        risk,
    ):
        return {
            "risk": risk,
            "reasons": [],
        }

    def test_rule_high_skips_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule(
                "high"
            ),
            claude_review=self.review(
                risk="low"
            ),
            verification_passed=True,
        )

        self.assertFalse(
            decision.invoke_codex_risk
        )

        self.assertEqual(
            decision.mode,
            "terminal_high",
        )

    def test_claude_high_skips_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule(
                "low"
            ),
            claude_review=self.review(
                risk="high"
            ),
            verification_passed=True,
        )

        self.assertFalse(
            decision.invoke_codex_risk
        )

        self.assertEqual(
            decision.mode,
            "terminal_high",
        )

    def test_both_high_skip_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule(
                "high"
            ),
            claude_review=self.review(
                risk="high"
            ),
            verification_passed=True,
        )

        self.assertFalse(
            decision.invoke_codex_risk
        )

    def test_low_low_requires_independent_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule(
                "low"
            ),
            claude_review=self.review(
                risk="low",
                confidence=0.99,
            ),
            verification_passed=True,
        )

        self.assertTrue(
            decision.invoke_codex_risk
        )

        self.assertEqual(
            decision.mode,
            "independent_judge_required",
        )

    def test_low_medium_requires_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule(
                "low"
            ),
            claude_review=self.review(
                risk="medium"
            ),
            verification_passed=True,
        )

        self.assertTrue(
            decision.invoke_codex_risk
        )

    def test_medium_low_requires_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule(
                "medium"
            ),
            claude_review=self.review(
                risk="low"
            ),
            verification_passed=True,
        )

        self.assertTrue(
            decision.invoke_codex_risk
        )

    def test_high_rule_skip_does_not_depend_on_confidence(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule(
                "high"
            ),
            claude_review=self.review(
                risk="low",
                confidence=None,
            ),
            verification_passed=True,
        )

        self.assertFalse(
            decision.invoke_codex_risk
        )

    def test_blocking_finding_does_not_weaken_high_terminal(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule(
                "high"
            ),
            claude_review=self.review(
                risk="low",
                findings=[
                    {
                        "severity": "major",
                        "message": "problem",
                    }
                ],
            ),
            verification_passed=True,
        )

        self.assertFalse(
            decision.invoke_codex_risk
        )

    def test_low_low_with_blocker_still_requires_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule(
                "low"
            ),
            claude_review=self.review(
                risk="low",
                findings=[
                    {
                        "severity": "major",
                        "message": "problem",
                    }
                ],
            ),
            verification_passed=True,
        )

        self.assertTrue(
            decision.invoke_codex_risk
        )


    def test_terminal_high_aggregate_records_skipped_codex(
        self,
    ):
        aggregate = aggregate_terminal_high(
            rule_risk=self.rule(
                "high"
            ),
            claude_review=self.review(
                risk="low"
            ),
        )

        self.assertEqual(
            aggregate["final"],
            "high",
        )

        self.assertTrue(
            aggregate["human_required"]
        )

        self.assertIsNone(
            aggregate["sources"]["codex"]
        )

        self.assertEqual(
            aggregate["routing_mode"],
            "terminal_high",
        )

    def test_terminal_high_aggregate_rejects_non_high_inputs(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            aggregate_terminal_high(
                rule_risk=self.rule(
                    "low"
                ),
                claude_review=self.review(
                    risk="low"
                ),
            )



if __name__ == "__main__":
    unittest.main()
