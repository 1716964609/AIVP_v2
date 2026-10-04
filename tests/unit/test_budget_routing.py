import unittest

from aivp.panel.budget_routing import (
    route_deterministic_repair_budget,
    route_review_repair_budget,
)


class BudgetRoutingTests(
    unittest.TestCase
):
    def test_default_review_budget_admits_repair(
        self,
    ):
        decision = (
            route_review_repair_budget(
                codex_calls=1,
                claude_calls=1,
                codex_max_calls=4,
                claude_max_calls=3,
            )
        )

        self.assertTrue(
            decision.allow_repair
        )

        self.assertEqual(
            decision.codex_remaining,
            3,
        )

        self.assertEqual(
            decision.codex_required,
            2,
        )

    def test_codex_risk_capacity_is_reserved(
        self,
    ):
        decision = (
            route_review_repair_budget(
                codex_calls=1,
                claude_calls=1,
                codex_max_calls=2,
                claude_max_calls=3,
            )
        )

        self.assertFalse(
            decision.allow_repair
        )

        self.assertEqual(
            decision.codex_remaining,
            1,
        )

        self.assertEqual(
            decision.codex_required,
            2,
        )

    def test_claude_rereview_capacity_is_required(
        self,
    ):
        decision = (
            route_review_repair_budget(
                codex_calls=1,
                claude_calls=1,
                codex_max_calls=4,
                claude_max_calls=1,
            )
        )

        self.assertFalse(
            decision.allow_repair
        )

        self.assertEqual(
            decision.claude_remaining,
            0,
        )

    def test_deterministic_repair_uses_same_reserve(
        self,
    ):
        decision = (
            route_deterministic_repair_budget(
                codex_calls=1,
                claude_calls=0,
                codex_max_calls=2,
                claude_max_calls=3,
            )
        )

        self.assertFalse(
            decision.allow_repair
        )

        self.assertEqual(
            decision.codex_remaining,
            1,
        )

        self.assertEqual(
            decision.codex_required,
            2,
        )


if __name__ == "__main__":
    unittest.main()
