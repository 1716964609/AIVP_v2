import json
import tempfile
import unittest

from unittest.mock import patch

from pathlib import Path

from aivp.errors import BudgetExceeded

from aivp.execution.runtime import (
    Budgets,
    Counters,
    Runtime,
)


class RuntimeResumeTests(
    unittest.TestCase
):
    def test_resume_preserves_events_and_counters(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)

            first = Runtime(
                run_dir,
                Budgets(),
            )

            first.consume("codex")
            first.log_event(
                "before_crash"
            )

            restored = Runtime(
                run_dir,
                Budgets(),
                resume=True,
                counters=Counters(
                    codex_calls=1,
                    claude_calls=0,
                    fix_iterations=0,
                ),
            )

            self.assertEqual(
                restored.counters.codex_calls,
                1,
            )

            self.assertEqual(
                len(restored.events),
                1,
            )

            restored.log_event(
                "after_resume"
            )

            events = json.loads(
                (
                    run_dir / "events.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                [
                    item["kind"]
                    for item in events
                ],
                [
                    "before_crash",
                    "after_resume",
                ],
            )

    def test_resume_preserves_elapsed_budget(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)

            budgets = Budgets(
                whole_run_timeout_seconds=10
            )

            with patch(
                "aivp.execution.runtime."
                "time.monotonic",
                return_value=100.0,
            ):
                restored = Runtime(
                    run_dir,
                    budgets,
                    resume=True,
                    elapsed_before_resume=7.0,
                )

            with patch(
                "aivp.execution.runtime."
                "time.monotonic",
                return_value=102.0,
            ):
                self.assertAlmostEqual(
                    restored.elapsed_seconds(),
                    9.0,
                )

                self.assertAlmostEqual(
                    restored.remaining_seconds(),
                    1.0,
                )

    def test_resume_rejects_call_when_elapsed_budget_exhausted(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)

            budgets = Budgets(
                whole_run_timeout_seconds=10
            )

            with patch(
                "aivp.execution.runtime."
                "time.monotonic",
                return_value=100.0,
            ):
                restored = Runtime(
                    run_dir,
                    budgets,
                    resume=True,
                    elapsed_before_resume=10.0,
                )

                with self.assertRaises(
                    BudgetExceeded
                ):
                    restored.consume(
                        "codex"
                    )

            self.assertEqual(
                restored.counters.codex_calls,
                0,
            )



if __name__ == "__main__":
    unittest.main()
