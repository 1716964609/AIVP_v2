import json
import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.artifacts.registry import (
    ArtifactRegistry,
)
from aivp.execution.runtime import (
    Budgets,
    Runtime,
)
from aivp.models.base import (
    ModelResult,
)
from aivp.panel.orchestrator import (
    execute_panel,
)


class CapturingModel:
    def __init__(
        self,
        response: str = "",
    ):
        self.requests = []
        self.response = response

    def invoke(
        self,
        request,
    ):
        self.requests.append(
            request
        )

        return ModelResult(
            provider="test",
            model="test-model",
            started_at=(
                "2026-10-03T00:00:00+09:00"
            ),
            finished_at=(
                "2026-10-03T00:00:01+09:00"
            ),
            raw_exit_status=0,
            last_message=self.response,
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


class LowRiskEngine:
    def assess(
        self,
        **kwargs,
    ):
        return {
            "rule": {
                "risk": "low",
                "reasons": [
                    "test fixture"
                ],
            },
            "aggregate": {
                "final": "low",
                "sources": {
                    "rule": "low",
                    "codex": "low",
                    "claude": "low",
                },
                "large_disagreement": False,
                "human_required": False,
            },
        }


class ContextHarnessWiringTests(
    unittest.TestCase
):
    def test_generator_receives_compiled_context(
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
                repo
                / "authentication.py"
            ).write_text(
                (
                    "TIMEOUT = 30\n"
                    "def authenticate():\n"
                    "    return TIMEOUT\n"
                ),
                encoding="utf-8",
            )

            (
                repo
                / "unrelated.py"
            ).write_text(
                "PRICE = 100\n",
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
                dry_run=True,
            )

            generator = CapturingModel()

            reviewer = CapturingModel(
                json.dumps(
                    {
                        "summary": "ok",
                        "findings": [],
                        "risk": "low",
                        "risk_confidence": 1.0,
                        "risk_reasons": [],
                    }
                )
            )

            risk = CapturingModel(
                json.dumps(
                    {
                        "risk": "low",
                        "confidence": 1.0,
                        "reasons": [],
                    }
                )
            )

            execute_panel(
                runtime=runtime,
                repo=repo,
                canonical_repo=repo,
                task={
                    "task": (
                        "Fix authentication "
                        "timeout"
                    ),
                    "acceptance": [],
                    "constraints": [],
                },
                config={
                    "context": {
                        "max_files": 5,
                        "max_chars": 10_000,
                    },
                    "risk_policy": {
                        "high_risk_paths": [],
                        "high_risk_patterns": [],
                    },
                },
                generator=generator,
                reviewer=reviewer,
                risk_judge=risk,
                verifier=PassingVerifier(),
                risk_engine=LowRiskEngine(),
                artifacts=ArtifactRegistry(),
            )

            context_path = (
                run_dir / "context.txt"
            )

            manifest_path = (
                run_dir
                / "context-manifest.json"
            )

            self.assertTrue(
                context_path.exists()
            )

            self.assertTrue(
                manifest_path.exists()
            )

            context_text = (
                context_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn(
                "authentication.py",
                context_text,
            )

            self.assertNotIn(
                "PRICE = 100",
                context_text,
            )

            self.assertEqual(
                len(generator.requests),
                1,
            )

            prompt = (
                generator
                .requests[0]
                .prompt
            )

            self.assertIn(
                "COMPILED REPOSITORY CONTEXT",
                prompt,
            )

            self.assertIn(
                "TIMEOUT = 30",
                prompt,
            )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertTrue(
                manifest[
                    "manifest_hash"
                ]
            )

    def test_context_disabled_keeps_old_prompt_shape(
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
                repo / "app.py"
            ).write_text(
                "value = 1\n",
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
                dry_run=True,
            )

            generator = CapturingModel()

            execute_panel(
                runtime=runtime,
                repo=repo,
                canonical_repo=repo,
                task={
                    "task": "Update app",
                    "acceptance": [],
                    "constraints": [],
                },
                config={
                    "risk_policy": {
                        "high_risk_paths": [],
                        "high_risk_patterns": [],
                    },
                },
                generator=generator,
                reviewer=CapturingModel(),
                risk_judge=CapturingModel(),
                verifier=PassingVerifier(),
                risk_engine=LowRiskEngine(),
                artifacts=ArtifactRegistry(),
            )

            self.assertFalse(
                (
                    run_dir
                    / "context.txt"
                ).exists()
            )

            self.assertNotIn(
                "COMPILED REPOSITORY CONTEXT",
                generator.requests[0].prompt,
            )


if __name__ == "__main__":
    unittest.main()
