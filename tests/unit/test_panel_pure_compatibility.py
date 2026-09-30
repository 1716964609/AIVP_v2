import unittest

import aivp.legacy.orchestrator_v1 as legacy

from aivp.models.parsing import (
    extract_json_object,
)
from aivp.panel.config import (
    budgets_from,
)
from aivp.panel.prompts import (
    fix_prompt,
    generate_prompt,
)
from aivp.panel.task import (
    render_task,
)
from aivp.repository.diff import (
    truncate_diff,
)


class PanelPureCompatibilityTests(
    unittest.TestCase
):
    def test_extract_json_object_matches_legacy(self):
        samples = [
            '{"risk":"low"}',
            '```json\n{"risk":"medium"}\n```',
            'prefix {"risk":"high"} suffix',
        ]

        for sample in samples:
            self.assertEqual(
                extract_json_object(
                    sample
                ),
                legacy.extract_json_object(
                    sample
                ),
            )

    def test_empty_json_error_matches_legacy(self):
        with self.assertRaises(
            legacy.AIVPError
        ) as legacy_ctx:
            legacy.extract_json_object(
                ""
            )

        with self.assertRaises(
            Exception
        ) as new_ctx:
            extract_json_object(
                ""
            )

        self.assertEqual(
            str(new_ctx.exception),
            str(legacy_ctx.exception),
        )

    def test_budgets_from_matches_legacy(self):
        config = {
            "budgets": {
                "max_fix_iterations": 5,
                "codex_max_calls": 7,
                "claude_max_calls": 4,
                "codex_timeout_seconds": 111,
                "claude_timeout_seconds": 222,
                "whole_run_timeout_seconds": 333,
            }
        }

        self.assertEqual(
            budgets_from(
                config
            ).__dict__,
            legacy.budgets_from(
                config
            ).__dict__,
        )

    def test_render_task_matches_legacy(self):
        task = {
            "task": "Implement X",
            "acceptance": [
                "A",
                "B",
            ],
            "constraints": [
                "C",
            ],
        }

        self.assertEqual(
            render_task(
                task
            ),
            legacy.render_task(
                task
            ),
        )

    def test_truncate_diff_matches_legacy(self):
        config = {
            "diff_context": {
                "max_chars": 10,
            }
        }

        diff = (
            "0123456789"
            "ABCDEFGHIJ"
        )

        self.assertEqual(
            truncate_diff(
                config,
                diff,
            ),
            legacy.truncate_diff(
                config,
                diff,
            ),
        )

    def test_generate_prompt_matches_legacy(self):
        task_text = (
            "TASK\nExample\n"
        )

        self.assertEqual(
            generate_prompt(
                task_text
            ),
            legacy.generate_prompt(
                task_text
            ),
        )

    def test_fix_prompt_verification_matches_legacy(self):
        task_text = "TASK\nExample\n"

        verification = {
            "passed": False,
            "results": [
                {
                    "name": "tests",
                    "passed": False,
                    "stdout_tail": "out",
                    "stderr_tail": "err",
                }
            ],
        }

        self.assertEqual(
            fix_prompt(
                task_text,
                verification=verification,
            ),
            legacy.fix_prompt(
                task_text,
                verification=verification,
            ),
        )

    def test_fix_prompt_review_matches_legacy(self):
        task_text = "TASK\nExample\n"

        review = {
            "findings": [
                {
                    "severity": "major",
                    "category": "correctness",
                    "file": "x.py",
                    "line": 1,
                    "reason": "broken",
                    "suggested_direction": "fix it",
                }
            ]
        }

        self.assertEqual(
            fix_prompt(
                task_text,
                review=review,
            ),
            legacy.fix_prompt(
                task_text,
                review=review,
            ),
        )


if __name__ == "__main__":
    unittest.main()
