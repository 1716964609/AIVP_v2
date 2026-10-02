import json
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from aivp.application import _execute
from aivp.execution.runtime import (
    Budgets,
    Runtime,
)
from aivp.telemetry.tracing import (
    TracingSession,
)


class RunTracingTests(
    unittest.TestCase
):
    def test_run_is_parent_of_nested_work(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()

            run_dir = root / "run-1"
            run_dir.mkdir()

            tracing = TracingSession(
                enabled=True,
                output_path=(
                    run_dir
                    / "otel-spans.jsonl"
                ),
            )

            runtime = Runtime(
                run_dir,
                Budgets(),
                tracing=tracing,
            )

            def fake_execute_panel(
                **kwargs,
            ):
                inner_runtime = kwargs[
                    "runtime"
                ]

                with inner_runtime.tracing.span(
                    "model.call",
                    attributes={
                        "provider": "openai",
                        "model": "test-model",
                    },
                ):
                    with inner_runtime.tracing.span(
                        "command",
                        attributes={
                            "actor": "codex",
                            "tool": "codex",
                        },
                    ):
                        pass

                inner_runtime.log_event(
                    "run_end",
                    status="AUTO_FINISHED",
                )

                return inner_runtime.run_dir

            with patch(
                "aivp.application.execute_panel",
                side_effect=fake_execute_panel,
            ):
                result = _execute(
                    runtime=runtime,
                    repo=repo,
                    canonical_repo=repo,
                    task={},
                    config={
                        "codex": {},
                        "claude": {},
                    },
                    durable=None,
                )

            tracing.shutdown()

            self.assertEqual(
                result,
                run_dir,
            )

            rows = [
                json.loads(line)
                for line
                in (
                    run_dir
                    / "otel-spans.jsonl"
                ).read_text(
                    encoding="utf-8"
                ).splitlines()
            ]

            by_name = {
                row["name"]: row
                for row in rows
            }

            run = by_name["run"]
            model = by_name["model.call"]
            command = by_name["command"]

            self.assertEqual(
                run["attributes"][
                    "run.id"
                ],
                "run-1",
            )

            self.assertEqual(
                run["attributes"][
                    "status"
                ],
                "AUTO_FINISHED",
            )

            self.assertEqual(
                model["trace_id"],
                run["trace_id"],
            )

            self.assertEqual(
                model["parent_span_id"],
                run["span_id"],
            )

            self.assertEqual(
                command["trace_id"],
                run["trace_id"],
            )

            self.assertEqual(
                command[
                    "parent_span_id"
                ],
                model["span_id"],
            )


if __name__ == "__main__":
    unittest.main()
