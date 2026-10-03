import unittest

from aivp.panel.prompts import (
    FIXER_STABLE_PREFIX,
    GENERATOR_STABLE_PREFIX,
    PROMPT_LAYOUT_VERSION,
    REVIEW_STABLE_PREFIX,
    RISK_STABLE_PREFIX,
    fix_prompt,
    generate_prompt,
    review_prompt,
    risk_prompt,
)


class PromptPrefixContractTests(
    unittest.TestCase
):
    def test_layout_is_versioned(
        self,
    ):
        self.assertEqual(
            PROMPT_LAYOUT_VERSION,
            "1.0.0",
        )

    def test_generator_dynamic_data_follows_stable_prefix(
        self,
    ):
        first = generate_prompt(
            "TASK_SENTINEL_A",
            context_text=(
                "CONTEXT_SENTINEL_A"
            ),
        )

        second = generate_prompt(
            "TASK_SENTINEL_B",
            context_text=(
                "CONTEXT_SENTINEL_B"
            ),
        )

        self.assertTrue(
            first.startswith(
                GENERATOR_STABLE_PREFIX
            )
        )

        self.assertTrue(
            second.startswith(
                GENERATOR_STABLE_PREFIX
            )
        )

        self.assertNotIn(
            "TASK_SENTINEL",
            GENERATOR_STABLE_PREFIX,
        )

        self.assertNotIn(
            "CONTEXT_SENTINEL",
            GENERATOR_STABLE_PREFIX,
        )

    def test_fixer_dynamic_data_follows_stable_prefix(
        self,
    ):
        first = fix_prompt(
            "TASK_SENTINEL_A",
            verification={
                "results": [],
            },
            context_text=(
                "CONTEXT_SENTINEL_A"
            ),
        )

        second = fix_prompt(
            "TASK_SENTINEL_B",
            review={
                "findings": [],
            },
            context_text=(
                "CONTEXT_SENTINEL_B"
            ),
        )

        self.assertTrue(
            first.startswith(
                FIXER_STABLE_PREFIX
            )
        )

        self.assertTrue(
            second.startswith(
                FIXER_STABLE_PREFIX
            )
        )

        self.assertNotIn(
            "TASK_SENTINEL",
            FIXER_STABLE_PREFIX,
        )

        self.assertNotIn(
            "CONTEXT_SENTINEL",
            FIXER_STABLE_PREFIX,
        )

    def test_reviewer_dynamic_data_follows_stable_prefix(
        self,
    ):
        first = review_prompt(
            "TASK_SENTINEL_A",
            "DIFF_SENTINEL_A",
            {
                "passed": True,
                "results": [],
            },
        )

        second = review_prompt(
            "TASK_SENTINEL_B",
            "DIFF_SENTINEL_B",
            {
                "passed": False,
                "results": [],
            },
        )

        self.assertTrue(
            first.startswith(
                REVIEW_STABLE_PREFIX
            )
        )

        self.assertTrue(
            second.startswith(
                REVIEW_STABLE_PREFIX
            )
        )

        self.assertNotIn(
            "TASK_SENTINEL",
            REVIEW_STABLE_PREFIX,
        )

        self.assertNotIn(
            "DIFF_SENTINEL",
            REVIEW_STABLE_PREFIX,
        )

    def test_risk_dynamic_data_follows_stable_prefix(
        self,
    ):
        first = risk_prompt(
            "TASK_SENTINEL_A",
            "DIFF_SENTINEL_A",
        )

        second = risk_prompt(
            "TASK_SENTINEL_B",
            "DIFF_SENTINEL_B",
        )

        self.assertTrue(
            first.startswith(
                RISK_STABLE_PREFIX
            )
        )

        self.assertTrue(
            second.startswith(
                RISK_STABLE_PREFIX
            )
        )

        self.assertNotIn(
            "TASK_SENTINEL",
            RISK_STABLE_PREFIX,
        )

        self.assertNotIn(
            "DIFF_SENTINEL",
            RISK_STABLE_PREFIX,
        )


if __name__ == "__main__":
    unittest.main()
