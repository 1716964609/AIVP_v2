import json
import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.artifacts.registry import ArtifactRegistry
from aivp.errors import InjectedCrash
from aivp.execution.runtime import Budgets, Runtime
from aivp.models.base import ModelRequest, ModelResult
from aivp.panel.orchestrator import execute_panel
from aivp.risk.engine import LegacyCompatibleRiskEngine
from aivp.state.durable import (
    DurableExecution,
    counters_from_checkpoint,
)
from aivp.state.sqlite import SQLiteStateStore


REVIEW_LOW = json.dumps(
    {
        "summary": "ok",
        "findings": [],
        "risk": "low",
        "risk_confidence": 1.0,
        "risk_reasons": [],
    }
)

RISK_LOW = json.dumps(
    {
        "risk": "low",
        "confidence": 1.0,
        "reasons": [],
    }
)

RISK_HIGH = json.dumps(
    {
        "risk": "high",
        "confidence": 1.0,
        "reasons": ["high"],
    }
)


class FakeModel:
    def __init__(
        self,
        runtime,
        actor,
        responses,
    ):
        self.runtime = runtime
        self.actor = actor
        self.responses = iter(responses)
        self.requests = []

    def invoke(
        self,
        request: ModelRequest,
    ) -> ModelResult:
        self.requests.append(request)
        self.runtime.consume(self.actor)

        value = next(self.responses)

        return ModelResult(
            provider="fake",
            model="fake",
            started_at="start",
            finished_at="end",
            raw_exit_status=0,
            last_message=value,
        )


class EditingFakeModel(FakeModel):
    def invoke(
        self,
        request: ModelRequest,
    ) -> ModelResult:
        if request.role == "generator":
            (
                request.repo
                / "generated.txt"
            ).write_text(
                "generated\n",
                encoding="utf-8",
            )

        return super().invoke(
            request
        )


class FakeVerifier:
    def __init__(
        self,
        results,
    ):
        self.results = iter(results)
        self.calls = 0

    def verify(
        self,
        *,
        repo,
        config,
        phase,
    ):
        self.calls += 1
        return next(self.results)


def passed():
    return {
        "passed": True,
        "results": [],
    }


def failed():
    return {
        "passed": False,
        "results": [
            {
                "name": "tests",
                "passed": False,
                "stdout_tail": "",
                "stderr_tail": "failed",
            }
        ],
    }


class HarnessPanelTests(
    unittest.TestCase
):
    def make_repo(
        self,
        root: Path,
    ) -> Path:
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

        return repo

    def make_runtime(
        self,
        root: Path,
    ) -> Runtime:
        run_dir = root / "run"
        run_dir.mkdir()

        return Runtime(
            run_dir,
            Budgets(),
        )

    def config(self):
        return {
            "risk_policy": {
                "high_risk_paths": [],
                "high_risk_patterns": [],
            }
        }

    def task(self):
        return {
            "task": "Example",
            "acceptance": [],
            "constraints": [],
        }

    def test_auto_finished_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            runtime = self.make_runtime(root)

            generator = FakeModel(
                runtime,
                "codex",
                ["generated"],
            )

            reviewer = FakeModel(
                runtime,
                "claude",
                [REVIEW_LOW],
            )

            risk = FakeModel(
                runtime,
                "codex",
                [RISK_LOW],
            )

            run_dir = execute_panel(
                runtime=runtime,
                repo=repo,
                task=self.task(),
                config=self.config(),
                generator=generator,
                reviewer=reviewer,
                risk_judge=risk,
                verifier=FakeVerifier(
                    [passed()]
                ),
                risk_engine=(
                    LegacyCompatibleRiskEngine()
                ),
                artifacts=ArtifactRegistry(),
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
                "AUTO_FINISHED",
            )

            self.assertEqual(
                runtime.counters.codex_calls,
                2,
            )

            self.assertEqual(
                runtime.counters.claude_calls,
                1,
            )

    def test_deterministic_failure_repairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            runtime = self.make_runtime(root)

            generator = FakeModel(
                runtime,
                "codex",
                [
                    "generated",
                    "fixed",
                ],
            )

            reviewer = FakeModel(
                runtime,
                "claude",
                [REVIEW_LOW],
            )

            risk = FakeModel(
                runtime,
                "codex",
                [RISK_LOW],
            )

            verifier = FakeVerifier(
                [
                    failed(),
                    passed(),
                ]
            )

            run_dir = execute_panel(
                runtime=runtime,
                repo=repo,
                task=self.task(),
                config=self.config(),
                generator=generator,
                reviewer=reviewer,
                risk_judge=risk,
                verifier=verifier,
                risk_engine=(
                    LegacyCompatibleRiskEngine()
                ),
                artifacts=ArtifactRegistry(),
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
                "AUTO_FINISHED",
            )

            self.assertEqual(
                runtime.counters.fix_iterations,
                1,
            )

            self.assertEqual(
                [
                    request.role
                    for request
                    in generator.requests
                ],
                [
                    "generator",
                    "fixer",
                ],
            )

    def test_high_risk_requires_human(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            runtime = self.make_runtime(root)

            run_dir = execute_panel(
                runtime=runtime,
                repo=repo,
                task=self.task(),
                config=self.config(),
                generator=FakeModel(
                    runtime,
                    "codex",
                    ["generated"],
                ),
                reviewer=FakeModel(
                    runtime,
                    "claude",
                    [REVIEW_LOW],
                ),
                risk_judge=FakeModel(
                    runtime,
                    "codex",
                    [RISK_HIGH],
                ),
                verifier=FakeVerifier(
                    [passed()]
                ),
                risk_engine=(
                    LegacyCompatibleRiskEngine()
                ),
                artifacts=ArtifactRegistry(),
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

            self.assertEqual(
                status["reason"],
                (
                    "high risk or large "
                    "model/policy disagreement"
                ),
            )

            self.assertTrue(
                (
                    run_dir
                    / "human-review.md"
                ).exists()
            )


    def test_resume_after_generation_does_not_regenerate(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)

            run_dir = root / "run"
            run_dir.mkdir()

            state_db = root / "state.db"

            first_runtime = Runtime(
                run_dir,
                Budgets(),
            )

            first_store = (
                SQLiteStateStore(
                    state_db
                )
            )

            generator = EditingFakeModel(
                first_runtime,
                "codex",
                ["generated"],
            )

            try:
                with self.assertRaises(
                    InjectedCrash
                ):
                    execute_panel(
                        runtime=first_runtime,
                        repo=repo,
                        task=self.task(),
                        config=self.config(),
                        generator=generator,
                        reviewer=FakeModel(
                            first_runtime,
                            "claude",
                            [REVIEW_LOW],
                        ),
                        risk_judge=FakeModel(
                            first_runtime,
                            "codex",
                            [RISK_LOW],
                        ),
                        verifier=FakeVerifier(
                            [passed()]
                        ),
                        risk_engine=(
                            LegacyCompatibleRiskEngine()
                        ),
                        artifacts=(
                            ArtifactRegistry()
                        ),
                        durable=DurableExecution(
                            store=first_store,
                            run_id="run-1",
                            fault_after_state=(
                                "GENERATED"
                            ),
                        ),
                    )

                checkpoint = (
                    first_store.load(
                        "run-1"
                    )
                )

                self.assertIsNotNone(
                    checkpoint
                )

                self.assertEqual(
                    checkpoint["state"],
                    "GENERATED",
                )

                self.assertEqual(
                    len(
                        generator.requests
                    ),
                    1,
                )

                self.assertEqual(
                    first_runtime
                    .counters
                    .codex_calls,
                    1,
                )

            finally:
                first_store.close()

            second_store = (
                SQLiteStateStore(
                    state_db
                )
            )

            try:
                assert checkpoint is not None

                second_runtime = Runtime(
                    run_dir,
                    Budgets(),
                    resume=True,
                    counters=(
                        counters_from_checkpoint(
                            checkpoint
                        )
                    ),
                )

                resumed_generator = (
                    FakeModel(
                        second_runtime,
                        "codex",
                        [],
                    )
                )

                verifier = FakeVerifier(
                    [passed()]
                )

                result_dir = execute_panel(
                    runtime=second_runtime,
                    repo=repo,
                    task=self.task(),
                    config=self.config(),
                    generator=(
                        resumed_generator
                    ),
                    reviewer=FakeModel(
                        second_runtime,
                        "claude",
                        [REVIEW_LOW],
                    ),
                    risk_judge=FakeModel(
                        second_runtime,
                        "codex",
                        [RISK_LOW],
                    ),
                    verifier=verifier,
                    risk_engine=(
                        LegacyCompatibleRiskEngine()
                    ),
                    artifacts=(
                        ArtifactRegistry()
                    ),
                    durable=DurableExecution(
                        store=second_store,
                        run_id="run-1",
                        attempt=2,
                        resume_checkpoint=(
                            checkpoint
                        ),
                    ),
                )

                self.assertEqual(
                    resumed_generator.requests,
                    [],
                )

                self.assertEqual(
                    verifier.calls,
                    1,
                )

                self.assertEqual(
                    second_runtime
                    .counters
                    .codex_calls,
                    2,
                )

                self.assertEqual(
                    second_runtime
                    .counters
                    .claude_calls,
                    1,
                )

                status = json.loads(
                    (
                        result_dir
                        / "status.json"
                    ).read_text(
                        encoding="utf-8"
                    )
                )

                self.assertEqual(
                    status["status"],
                    "AUTO_FINISHED",
                )

            finally:
                second_store.close()


if __name__ == "__main__":
    unittest.main()
