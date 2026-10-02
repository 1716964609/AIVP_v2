import json
import sys
import tempfile
import unittest

from pathlib import Path

from aivp.execution.runtime import (
    Budgets,
    Runtime,
)
from aivp.telemetry.tracing import (
    TracingSession,
)


class CommandTracingTests(
    unittest.TestCase
):
    def test_command_span_is_safe_and_measured(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo = (
                root
                / "SENSITIVE_CWD_TOKEN"
            )
            repo.mkdir()

            run_dir = root / "run"
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

            runtime.command(
                [
                    sys.executable,
                    "-c",
                    (
                        "print("
                        "'SENSITIVE_SCRIPT_TOKEN'"
                        ")"
                    ),
                    "SENSITIVE_ARG_TOKEN",
                ],
                cwd=repo,
                timeout_seconds=10,
                log_stem="command-trace",
                stdin_text=(
                    "SENSITIVE_STDIN_TOKEN"
                ),
                actor="codex",
                check=True,
            )

            tracing.shutdown()

            text = (
                run_dir
                / "otel-spans.jsonl"
            ).read_text(
                encoding="utf-8"
            )

            for token in (
                "SENSITIVE_SCRIPT_TOKEN",
                "SENSITIVE_ARG_TOKEN",
                "SENSITIVE_STDIN_TOKEN",
                "SENSITIVE_CWD_TOKEN",
            ):
                self.assertNotIn(
                    token,
                    text,
                )

            rows = [
                json.loads(line)
                for line in text.splitlines()
            ]

            command = next(
                row
                for row in rows
                if row["name"] == "command"
            )

            attrs = command["attributes"]

            self.assertEqual(
                attrs["actor"],
                "codex",
            )
            self.assertEqual(
                attrs["tool"],
                "codex",
            )
            self.assertEqual(
                attrs["status"],
                "SUCCEEDED",
            )
            self.assertEqual(
                attrs["returncode"],
                0,
            )
            self.assertGreaterEqual(
                attrs["elapsed_seconds"],
                0,
            )


if __name__ == "__main__":
    unittest.main()
