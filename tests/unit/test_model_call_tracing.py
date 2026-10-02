import json
import tempfile
import unittest

from pathlib import Path

from aivp.models.base import (
    ModelRequest,
    ModelResult,
)
from aivp.panel.orchestrator import (
    _invoke_model_call,
)
from aivp.telemetry.tracing import (
    TracingSession,
)


class FakeAdapter:
    def invoke(
        self,
        request: ModelRequest,
    ) -> ModelResult:
        return ModelResult(
            provider="openai",
            model="test-model",
            started_at=(
                "2026-10-02T00:00:00+00:00"
            ),
            finished_at=(
                "2026-10-02T00:00:01+00:00"
            ),
            raw_exit_status=0,
            input_tokens=1000,
            cached_tokens=400,
            output_tokens=200,
            cost_estimate_usd=0.003,
            last_message="ok",
        )


class ModelCallTracingTests(
    unittest.TestCase
):
    def test_model_call_span_has_safe_usage(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()

            output = (
                root
                / "otel-spans.jsonl"
            )

            tracing = TracingSession(
                enabled=True,
                output_path=output,
            )

            _invoke_model_call(
                adapter=FakeAdapter(),
                request=ModelRequest(
                    role="generator",
                    prompt=(
                        "SENSITIVE_PROMPT_TOKEN"
                    ),
                    repo=repo,
                    timeout_seconds=10,
                    log_stem="generate",
                ),
                durable=None,
                step_id="generate",
                tracing=tracing,
            )

            tracing.shutdown()

            text = output.read_text(
                encoding="utf-8"
            )

            self.assertNotIn(
                "SENSITIVE_PROMPT_TOKEN",
                text,
            )

            row = json.loads(
                text.strip()
            )

            self.assertEqual(
                row["name"],
                "model.call",
            )

            attrs = row["attributes"]

            self.assertEqual(
                attrs["step.id"],
                "generate",
            )
            self.assertEqual(
                attrs["role"],
                "generator",
            )
            self.assertEqual(
                attrs["provider"],
                "openai",
            )
            self.assertEqual(
                attrs["model"],
                "test-model",
            )
            self.assertEqual(
                attrs["status"],
                "SUCCEEDED",
            )
            self.assertEqual(
                attrs["input_tokens"],
                1000,
            )
            self.assertEqual(
                attrs["cached_tokens"],
                400,
            )
            self.assertEqual(
                attrs["output_tokens"],
                200,
            )
            self.assertAlmostEqual(
                attrs["cost_usd"],
                0.003,
            )
            self.assertGreaterEqual(
                attrs["latency_ms"],
                0,
            )


if __name__ == "__main__":
    unittest.main()
