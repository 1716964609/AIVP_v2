import unittest

from aivp.risk.routing import (
    route_codex_risk,
)


class RiskRoutingTests(unittest.TestCase):
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

    def rule(self, risk):
        return {
            "risk": risk,
            "reasons": [],
        }

    def test_low_low_high_confidence_skips_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule("low"),
            claude_review=self.review(
                risk="low",
                confidence=0.95,
            ),
            verification_passed=True,
        )

        self.assertFalse(
            decision.invoke_codex_risk
        )

        self.assertEqual(
            decision.mode,
            "conservative_low",
        )

    def test_low_low_threshold_is_inclusive(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule("low"),
            claude_review=self.review(
                risk="low",
                confidence=0.8,
            ),
            verification_passed=True,
        )

        self.assertFalse(
            decision.invoke_codex_risk
        )

        self.assertEqual(
            decision.mode,
            "conservative_low",
        )

    def test_low_low_low_confidence_keeps_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule("low"),
            claude_review=self.review(
                risk="low",
                confidence=0.79,
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

    def test_medium_review_keeps_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule("low"),
            claude_review=self.review(
                risk="medium",
                confidence=0.95,
            ),
            verification_passed=True,
        )

        self.assertTrue(
            decision.invoke_codex_risk
        )

    def test_medium_rule_keeps_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule("medium"),
            claude_review=self.review(
                risk="low",
                confidence=0.95,
            ),
            verification_passed=True,
        )

        self.assertTrue(
            decision.invoke_codex_risk
        )

    def test_failed_verification_keeps_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule("low"),
            claude_review=self.review(
                risk="low",
                confidence=0.95,
            ),
            verification_passed=False,
        )

        self.assertTrue(
            decision.invoke_codex_risk
        )

    def test_blocking_finding_keeps_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule("low"),
            claude_review=self.review(
                risk="low",
                confidence=0.95,
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

    def test_missing_confidence_keeps_codex(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule("low"),
            claude_review=self.review(
                risk="low",
                confidence=None,
            ),
            verification_passed=True,
        )

        self.assertTrue(
            decision.invoke_codex_risk
        )

    def test_rule_high_skips_codex_as_terminal_high(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule("high"),
            claude_review=self.review(
                risk="low",
                confidence=0.95,
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

    def test_claude_high_skips_codex_as_terminal_high(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule("low"),
            claude_review=self.review(
                risk="high",
                confidence=0.95,
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

    def test_boolean_confidence_is_not_numeric_confidence(
        self,
    ):
        decision = route_codex_risk(
            rule_risk=self.rule("low"),
            claude_review=self.review(
                risk="low",
                confidence=True,
            ),
            verification_passed=True,
        )

        self.assertTrue(
            decision.invoke_codex_risk
        )


if __name__ == "__main__":
    unittest.main()
