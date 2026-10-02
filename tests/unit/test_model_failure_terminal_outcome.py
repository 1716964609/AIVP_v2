import json
import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.artifacts.registry import ArtifactRegistry
from aivp.errors import CommandFailed
from aivp.execution.runtime import Budgets, Runtime
from aivp.panel.orchestrator import execute_panel


class CommandFailingModel:
    def __init__(self):
        self.calls = 0

    def invoke(self, request):
        self.calls += 1

        raise CommandFailed(
            "Model call failed (1): anthropic",
            1,
        )


class NeverModel:
    def invoke(self, request):
        raise AssertionError(
            "model invocation must not be reached"
        )


class NeverVerifier:
    def verify(
        self,
        *,
        repo,
        config,
        phase,
    ):
        raise AssertionError(
            "verification must not be reached"
        )


class NeverRiskEngine:
    def assess(self, **kwargs):
        raise AssertionError(
            "risk assessment must not be reached"
        )


class ModelFailureTerminalOutcomeTests(
    unittest.TestCase
):
    def test_model_failure_becomes_human_required_summary(
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

            (repo / "base.txt").write_text(
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

            generator = CommandFailingModel()

            result = execute_panel(
                runtime=runtime,
                repo=repo,
                canonical_repo=repo,
                task={
                    "task": (
                        "SENSITIVE_MODEL_PROMPT_TOKEN"
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
                reviewer=NeverModel(),
                risk_judge=NeverModel(),
                verifier=NeverVerifier(),
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

            status = json.loads(
                (
                    run_dir / "status.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                status["status"],
                "HUMAN_REQUIRED",
            )

            self.assertTrue(
                status["metrics"][
                    "model_call_failed"
                ]
            )

            self.assertEqual(
                status["metrics"][
                    "model_returncode"
                ],
                1,
            )

            self.assertNotIn(
                "SENSITIVE_MODEL_PROMPT_TOKEN",
                status["reason"],
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

            self.assertIn(
                "time",
                summary,
            )

            self.assertIn(
                "tokens",
                summary,
            )

            self.assertIn(
                "cost",
                summary,
            )

            events = json.loads(
                (
                    run_dir / "events.json"
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

            self.assertNotIn(
                "reason",
                events[-1],
            )

            self.assertTrue(
                (
                    run_dir
                    / "human-review.md"
                ).exists()
            )


if __name__ == "__main__":
    unittest.main()
