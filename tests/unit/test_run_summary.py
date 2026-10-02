import tempfile
import unittest

from pathlib import Path

from aivp.execution.runtime import (
    Budgets,
    Runtime,
)
from aivp.panel.reporting import (
    write_run_summary,
)


class RunSummaryTests(
    unittest.TestCase
):
    def test_explains_time_tokens_and_cost(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)

            runtime = Runtime(
                run_dir,
                Budgets(),
            )

            runtime.events = [
                {
                    "kind": "command_end",
                    "tool": "codex",
                    "actor": "codex",
                    "elapsed_seconds": 1.25,
                    "returncode": 0,
                    "command": (
                        "SENSITIVE_COMMAND_TOKEN"
                    ),
                },
                {
                    "kind": "command_timeout",
                    "tool": "verifier",
                    "elapsed_seconds": 2.0,
                    "cwd": (
                        "SENSITIVE_CWD_TOKEN"
                    ),
                },
            ]

            summary = write_run_summary(
                runtime=runtime,
                status="AUTO_FINISHED",
                run_id="run-1",
                pricing_version="pricing-v1",
                model_calls=[
                    {
                        "step_id": (
                            "run-1:generate"
                        ),
                        "provider": "openai",
                        "model": "model-a",
                        "input_tokens": 1000,
                        "cached_tokens": 400,
                        "output_tokens": 200,
                        "latency_ms": 1200,
                        "cost_usd": 0.003,
                        "status": "SUCCEEDED",
                        "prompt": (
                            "SENSITIVE_PROMPT_TOKEN"
                        ),
                    },
                    {
                        "step_id": (
                            "run-1:review"
                        ),
                        "provider": "anthropic",
                        "model": "model-b",
                        "input_tokens": 500,
                        "cached_tokens": 200,
                        "output_tokens": 100,
                        "latency_ms": 800,
                        "cost_usd": None,
                        "status": "SUCCEEDED",
                    },
                ],
            )

            self.assertEqual(
                summary["model_calls"][
                    "count"
                ],
                2,
            )

            self.assertEqual(
                summary["time"][
                    "model_latency_ms"
                ],
                2000,
            )

            self.assertEqual(
                summary["time"][
                    "command_elapsed_seconds"
                ],
                3.25,
            )

            self.assertEqual(
                summary["tokens"][
                    "input_tokens"
                ],
                1500,
            )

            self.assertEqual(
                summary["tokens"][
                    "cached_tokens"
                ],
                600,
            )

            self.assertEqual(
                summary["tokens"][
                    "output_tokens"
                ],
                300,
            )

            self.assertAlmostEqual(
                summary["cost"][
                    "total_usd"
                ],
                0.003,
            )

            self.assertEqual(
                summary["cost"][
                    "known_calls"
                ],
                1,
            )

            self.assertEqual(
                summary["cost"][
                    "total_calls"
                ],
                2,
            )

            self.assertTrue(
                summary["time"][
                    "nested_durations_not_additive"
                ]
            )

            text = (
                run_dir
                / "run-summary.json"
            ).read_text(
                encoding="utf-8"
            )

            self.assertNotIn(
                "SENSITIVE_COMMAND_TOKEN",
                text,
            )

            self.assertNotIn(
                "SENSITIVE_CWD_TOKEN",
                text,
            )

            self.assertNotIn(
                "SENSITIVE_PROMPT_TOKEN",
                text,
            )


if __name__ == "__main__":
    unittest.main()
