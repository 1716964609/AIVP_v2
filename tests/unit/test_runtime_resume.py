import json
import tempfile
import unittest

from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
