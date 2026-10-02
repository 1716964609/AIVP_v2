import unittest

from aivp.panel.config import (
    context_budget_from,
)
from aivp.panel.prompts import (
    fix_prompt,
    generate_prompt,
)


class ContextPromptContractTests(
    unittest.TestCase
):
    def test_context_config_absent_is_disabled(
        self,
    ):
        self.assertIsNone(
            context_budget_from({})
        )

    def test_context_config_defaults(
        self,
    ):
        budget = context_budget_from(
            {
                "context": {}
            }
        )

        self.assertEqual(
            budget.max_files,
            20,
        )

        self.assertEqual(
            budget.max_chars,
            120_000,
        )

    def test_context_can_be_disabled_explicitly(
        self,
    ):
        self.assertIsNone(
            context_budget_from(
                {
                    "context": {
                        "enabled": False,
                    }
                }
            )
        )

    def test_generate_prompt_includes_context(
        self,
    ):
        prompt = generate_prompt(
            "Fix timeout",
            context_text=(
                "===== CONTEXT FILE: "
                "service.py =====\n"
                "TIMEOUT = 30"
            ),
        )

        self.assertIn(
            "COMPILED REPOSITORY CONTEXT",
            prompt,
        )

        self.assertIn(
            "TIMEOUT = 30",
            prompt,
        )

        self.assertIn(
            "Fix timeout",
            prompt,
        )

    def test_fix_prompt_includes_context(
        self,
    ):
        prompt = fix_prompt(
            "Fix timeout",
            verification={
                "results": [],
            },
            context_text="TIMEOUT = 30",
        )

        self.assertIn(
            "COMPILED REPOSITORY CONTEXT",
            prompt,
        )

        self.assertIn(
            "TIMEOUT = 30",
            prompt,
        )

    def test_no_context_keeps_context_section_absent(
        self,
    ):
        self.assertNotIn(
            "COMPILED REPOSITORY CONTEXT",
            generate_prompt(
                "Fix timeout"
            ),
        )

        self.assertNotIn(
            "COMPILED REPOSITORY CONTEXT",
            fix_prompt(
                "Fix timeout"
            ),
        )


if __name__ == "__main__":
    unittest.main()
