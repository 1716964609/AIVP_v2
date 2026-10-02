import tempfile
import unittest

from pathlib import Path

from aivp.errors import CommandFailed
from aivp.models.base import ModelRequest, ModelResult
from aivp.panel.orchestrator import _invoke_model_call
from aivp.state.durable import DurableExecution
from aivp.state.sqlite import SQLiteStateStore


class FakeAdapter:
    def invoke(
        self,
        request: ModelRequest,
    ) -> ModelResult:
        return ModelResult(
            provider="openai",
            model="test-model",
            started_at="2026-10-02T15:00:00+09:00",
            finished_at="2026-10-02T15:00:01+09:00",
            raw_exit_status=0,
            input_tokens=123,
            cached_tokens=20,
            output_tokens=45,
            cost_estimate_usd=0.0123,
            last_message="ok",
        )


class FailedAdapter:
    def invoke(
        self,
        request: ModelRequest,
    ) -> ModelResult:
        return ModelResult(
            provider="anthropic",
            model="failed-test-model",
            started_at="2026-10-02T15:00:00+09:00",
            finished_at="2026-10-02T15:00:01+09:00",
            raw_exit_status=1,
            input_tokens=2,
            cached_tokens=8257,
            output_tokens=179,
            cost_estimate_usd=0.0724634,
            last_message="provider error",
        )


class ModelCallLedgerWiringTests(unittest.TestCase):
    def test_successful_model_call_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "state.db"
            repo = root / "repo"
            repo.mkdir()

            with SQLiteStateStore(db_path) as store:
                store.begin_run(
                    run_id="run-1",
                    repo_path=repo,
                    base_sha="base",
                    current_state="GENERATING",
                )

                durable = DurableExecution(
                    store=store,
                    run_id="run-1",
                )

                result = _invoke_model_call(
                    adapter=FakeAdapter(),
                    request=ModelRequest(
                        role="generator",
                        prompt="do work",
                        repo=repo,
                        timeout_seconds=10,
                        log_stem="codex-generate",
                    ),
                    durable=durable,
                    step_id="codex-generate",
                )

                self.assertEqual(
                    result.last_message,
                    "ok",
                )

                rows = store.model_calls_for_run(
                    "run-1"
                )

                self.assertEqual(len(rows), 1)

                row = rows[0]

                self.assertEqual(
                    row["run_id"],
                    "run-1",
                )
                self.assertEqual(
                    row["step_id"],
                    "run-1:codex-generate",
                )
                self.assertEqual(
                    row["provider"],
                    "openai",
                )
                self.assertEqual(
                    row["model"],
                    "test-model",
                )
                self.assertEqual(
                    row["input_tokens"],
                    123,
                )
                self.assertEqual(
                    row["cached_tokens"],
                    20,
                )
                self.assertEqual(
                    row["output_tokens"],
                    45,
                )
                self.assertAlmostEqual(
                    row["cost_usd"],
                    0.0123,
                )
                self.assertGreaterEqual(
                    row["latency_ms"],
                    0,
                )
                self.assertEqual(
                    row["status"],
                    "SUCCEEDED",
                )


    def test_failed_model_call_is_recorded_before_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "state.db"
            repo = root / "repo"
            repo.mkdir()

            with SQLiteStateStore(
                db_path
            ) as store:
                store.begin_run(
                    run_id="run-failed",
                    repo_path=repo,
                    base_sha="base",
                    current_state="REVIEWING",
                )

                durable = DurableExecution(
                    store=store,
                    run_id="run-failed",
                )

                with self.assertRaises(
                    CommandFailed
                ) as raised:
                    _invoke_model_call(
                        adapter=FailedAdapter(),
                        request=ModelRequest(
                            role="reviewer",
                            prompt=(
                                "SENSITIVE_PROMPT_TOKEN"
                            ),
                            repo=repo,
                            timeout_seconds=10,
                            log_stem="claude-review",
                        ),
                        durable=durable,
                        step_id="claude-review-0",
                    )

                self.assertNotIn(
                    "SENSITIVE_PROMPT_TOKEN",
                    str(raised.exception),
                )

                rows = (
                    store.model_calls_for_run(
                        "run-failed"
                    )
                )

                self.assertEqual(
                    len(rows),
                    1,
                )

                row = rows[0]

                self.assertEqual(
                    row["step_id"],
                    (
                        "run-failed:"
                        "claude-review-0"
                    ),
                )

                self.assertEqual(
                    row["provider"],
                    "anthropic",
                )

                self.assertEqual(
                    row["model"],
                    "failed-test-model",
                )

                self.assertEqual(
                    row["input_tokens"],
                    2,
                )

                self.assertEqual(
                    row["cached_tokens"],
                    8257,
                )

                self.assertEqual(
                    row["output_tokens"],
                    179,
                )

                self.assertAlmostEqual(
                    row["cost_usd"],
                    0.0724634,
                )

                self.assertEqual(
                    row["status"],
                    "FAILED",
                )


if __name__ == "__main__":
    unittest.main()
