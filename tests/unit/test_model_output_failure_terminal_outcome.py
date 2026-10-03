import json
import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.artifacts.registry import (
    ArtifactRegistry,
)
from aivp.errors import (
    ModelOutputError,
)
from aivp.execution.runtime import (
    Budgets,
    Runtime,
)
from aivp.models.base import (
    ModelResult,
)
from aivp.models.parsing import (
    extract_json_object,
)
from aivp.panel.orchestrator import (
    execute_panel,
)


class SuccessfulGenerator:
    def __init__(self):
        self.calls = 0

    def invoke(self, request):
        self.calls += 1

        return ModelResult(
            provider="openai",
            model="test-generator",
            started_at=(
                "2026-01-01T00:00:00+00:00"
            ),
            finished_at=(
                "2026-01-01T00:00:01+00:00"
            ),
            raw_exit_status=0,
            input_tokens=1,
            output_tokens=1,
            cached_tokens=0,
            artifact_paths=(),
            last_message="ok",
            raw_metadata={},
        )


class MalformedReviewer:
    def __init__(self):
        self.calls = 0

    def invoke(self, request):
        self.calls += 1

        raise ModelOutputError(
            "Could not parse JSON object "
            "from model output"
        )


class NeverModel:
    def invoke(self, request):
        raise AssertionError(
            "risk model must not be reached"
        )


class PassingVerifier:
    def verify(
        self,
        *,
        repo,
        config,
        phase,
    ):
        return {
            "passed": True,
            "results": [],
        }


class NeverRiskEngine:
    def assess(self, **kwargs):
        raise AssertionError(
            "risk assessment must not be reached"
        )


class ModelOutputFailureTerminalOutcomeTests(
    unittest.TestCase
):
    def test_parser_raises_specific_error_for_malformed_output(
        self,
    ):
        with self.assertRaises(
            ModelOutputError
        ):
            extract_json_object(
                "this is deliberately malformed"
            )

        with self.assertRaises(
            ModelOutputError
        ):
            extract_json_object("")

    def test_malformed_model_output_becomes_human_required(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo = root / "repo"
            repo.mkdir()

            subprocess.run(
                ["git", "init", "-q"],
                cwd=repo,
                check=True,
            )

            subprocess.run(
                [
                    "git",
                    "config",
                    "user.email",
                    "aivp@example.invalid",
                ],
                cwd=repo,
                check=True,
            )

            subprocess.run(
                [
                    "git",
                    "config",
                    "user.name",
                    "AIVP Test",
                ],
                cwd=repo,
                check=True,
            )

            (
                repo / "base.txt"
            ).write_text(
                "base\n",
                encoding="utf-8",
            )

            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
            )

            subprocess.run(
                [
                    "git",
                    "commit",
                    "-q",
                    "-m",
                    "base",
                ],
                cwd=repo,
                check=True,
            )

            run_dir = root / "run"
            run_dir.mkdir()

            runtime = Runtime(
                run_dir,
                Budgets(),
            )

            generator = (
                SuccessfulGenerator()
            )

            reviewer = (
                MalformedReviewer()
            )

            result = execute_panel(
                runtime=runtime,
                repo=repo,
                canonical_repo=repo,
                task={
                    "task": (
                        "Exercise malformed "
                        "review output"
                    ),
                    "acceptance": [],
                    "constraints": [],
                },
                config={
                    "risk_policy": {
                        "high_risk_paths": [],
                        "high_risk_patterns": [],
                    }
                },
                generator=generator,
                reviewer=reviewer,
                risk_judge=NeverModel(),
                verifier=PassingVerifier(),
                risk_engine=NeverRiskEngine(),
                artifacts=ArtifactRegistry(),
            )

            self.assertEqual(
                result,
                run_dir,
            )

            self.assertEqual(
                generator.calls,
                1,
            )

            self.assertEqual(
                reviewer.calls,
                1,
            )

            status = json.loads(
                (
                    run_dir
                    / "status.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                status["status"],
                "HUMAN_REQUIRED",
            )

            metrics = status[
                "metrics"
            ]

            self.assertTrue(
                metrics[
                    "model_call_failed"
                ]
            )

            self.assertTrue(
                metrics[
                    "model_output_invalid"
                ]
            )

            self.assertNotIn(
                "model_returncode",
                metrics,
            )

            summary = json.loads(
                (
                    run_dir
                    / "run-summary.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                summary["status"],
                "HUMAN_REQUIRED",
            )

            self.assertTrue(
                (
                    run_dir
                    / "human-review.md"
                ).exists()
            )

            events = json.loads(
                (
                    run_dir
                    / "events.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                events[-1]["kind"],
                "run_end",
            )

            self.assertEqual(
                events[-1]["status"],
                "HUMAN_REQUIRED",
            )


if __name__ == "__main__":
    unittest.main()
