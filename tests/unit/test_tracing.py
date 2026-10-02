import json
import tempfile
import unittest

from pathlib import Path

from aivp.telemetry.tracing import (
    TracingSession,
)


class TracingSessionTests(
    unittest.TestCase
):
    def test_nested_spans_are_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = (
                Path(tmp)
                / "otel-spans.jsonl"
            )

            tracing = TracingSession(
                enabled=True,
                output_path=output,
            )

            with tracing.span(
                "run",
                attributes={
                    "run.id": "run-1",
                },
            ):
                with tracing.span(
                    "model.call",
                    attributes={
                        "provider": "openai",
                        "model": "test-model",
                        "input_tokens": 100,
                    },
                ):
                    pass

            tracing.shutdown()

            rows = [
                json.loads(line)
                for line
                in output.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]

            self.assertEqual(
                len(rows),
                2,
            )

            by_name = {
                row["name"]: row
                for row in rows
            }

            run = by_name["run"]
            model = by_name["model.call"]

            self.assertEqual(
                model["trace_id"],
                run["trace_id"],
            )

            self.assertEqual(
                model["parent_span_id"],
                run["span_id"],
            )

            self.assertEqual(
                model["attributes"][
                    "provider"
                ],
                "openai",
            )

    def test_sensitive_attributes_are_dropped(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            output = (
                Path(tmp)
                / "otel-spans.jsonl"
            )

            tracing = TracingSession(
                enabled=True,
                output_path=output,
            )

            with tracing.span(
                "model.call",
                attributes={
                    "provider": "openai",
                    "prompt": (
                        "SENSITIVE_PROMPT_TOKEN"
                    ),
                    "argv": (
                        "SENSITIVE_ARG_TOKEN"
                    ),
                    "cwd": (
                        "SENSITIVE_CWD_TOKEN"
                    ),
                    "stdin": (
                        "SENSITIVE_STDIN_TOKEN"
                    ),
                },
            ):
                pass

            tracing.shutdown()

            text = output.read_text(
                encoding="utf-8"
            )

            self.assertNotIn(
                "SENSITIVE_PROMPT_TOKEN",
                text,
            )
            self.assertNotIn(
                "SENSITIVE_ARG_TOKEN",
                text,
            )
            self.assertNotIn(
                "SENSITIVE_CWD_TOKEN",
                text,
            )
            self.assertNotIn(
                "SENSITIVE_STDIN_TOKEN",
                text,
            )

            row = json.loads(
                text.strip()
            )

            self.assertEqual(
                row["attributes"][
                    "provider"
                ],
                "openai",
            )

    def test_exception_message_is_not_exported(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            output = (
                Path(tmp)
                / "otel-spans.jsonl"
            )

            tracing = TracingSession(
                enabled=True,
                output_path=output,
            )

            with self.assertRaises(
                RuntimeError
            ):
                with tracing.span(
                    "command",
                    attributes={
                        "actor": "codex",
                    },
                ):
                    raise RuntimeError(
                        "SENSITIVE_EXCEPTION_TOKEN"
                    )

            tracing.shutdown()

            text = output.read_text(
                encoding="utf-8"
            )

            self.assertNotIn(
                "SENSITIVE_EXCEPTION_TOKEN",
                text,
            )

            row = json.loads(
                text.strip()
            )

            self.assertEqual(
                row["status"],
                "ERROR",
            )

    def test_disabled_tracing_writes_nothing(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            output = (
                Path(tmp)
                / "otel-spans.jsonl"
            )

            tracing = TracingSession(
                enabled=False,
                output_path=output,
            )

            with tracing.span(
                "run",
                attributes={
                    "run.id": "run-1",
                },
            ):
                pass

            tracing.shutdown()

            self.assertFalse(
                output.exists()
            )


if __name__ == "__main__":
    unittest.main()
