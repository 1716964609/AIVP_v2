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



class FixingFakeModel(FakeModel):
    def invoke(
        self,
        request: ModelRequest,
    ) -> ModelResult:
        if request.role == "fixer":
            (
                request.repo
                / "repair.txt"
            ).write_text(
                "repaired\n",
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
                "AUTO_FINISHED",
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

            self.assertEqual(
                runtime.counters.codex_calls,
                2,
            )

            self.assertEqual(
                runtime.counters.claude_calls,
                1,
            )

    def test_budget_exceeded_writes_human_required_summary(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)

            run_dir = root / "run"
            run_dir.mkdir()

            runtime = Runtime(
                run_dir,
                Budgets(
                    codex_max_calls=0,
                ),
            )

            verifier = FakeVerifier(
                [passed()]
            )

            result = execute_panel(
                runtime=runtime,
                repo=repo,
                canonical_repo=repo,
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
                    [],
                ),
                risk_judge=FakeModel(
                    runtime,
                    "codex",
                    [],
                ),
                verifier=verifier,
                risk_engine=(
                    LegacyCompatibleRiskEngine()
                ),
                artifacts=ArtifactRegistry(),
            )

            self.assertEqual(
                result,
                run_dir,
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

            self.assertTrue(
                status["metrics"][
                    "budget_exceeded"
                ]
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

            self.assertEqual(
                summary["model_calls"][
                    "count"
                ],
                0,
            )

            self.assertEqual(
                verifier.calls,
                0,
            )


    def test_execution_repo_isolated_from_canonical_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical_repo = self.make_repo(root)

            execution_repo = (
                root / "execution"
            )

            subprocess.run(
                [
                    "git",
                    "worktree",
                    "add",
                    "--detach",
                    str(execution_repo),
                    "HEAD",
                ],
                cwd=canonical_repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            runtime = self.make_runtime(root)

            generator = EditingFakeModel(
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
                repo=execution_repo,
                canonical_repo=canonical_repo,
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

            self.assertFalse(
                (
                    canonical_repo
                    / "generated.txt"
                ).exists()
            )

            self.assertTrue(
                (
                    execution_repo
                    / "generated.txt"
                ).exists()
            )

            canonical_status = subprocess.run(
                [
                    "git",
                    "status",
                    "--short",
                ],
                cwd=canonical_repo,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout

            self.assertEqual(
                canonical_status,
                "",
            )

            self.assertEqual(
                generator.requests[0].repo,
                execution_repo.resolve(),
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


    def test_no_op_review_repair_exits_human_required(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            runtime = self.make_runtime(root)

            review_high = json.dumps(
                {
                    "summary": "blocking",
                    "findings": [
                        {
                            "severity": "major",
                            "message": "must fix",
                        }
                    ],
                    "risk": "high",
                    "risk_confidence": 1.0,
                    "risk_reasons": [
                        "blocking"
                    ],
                }
            )

            generator = FakeModel(
                runtime,
                "codex",
                [
                    "generated",
                    "fix attempted",
                ],
            )

            reviewer = FakeModel(
                runtime,
                "claude",
                [
                    review_high,
                ],
            )

            risk = FakeModel(
                runtime,
                "codex",
                [],
            )

            verifier = FakeVerifier(
                [
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
                "HUMAN_REQUIRED",
            )

            self.assertEqual(
                status["reason"],
                (
                    "review repair produced "
                    "no repository change"
                ),
            )

            self.assertEqual(
                len(reviewer.requests),
                1,
            )

            self.assertEqual(
                verifier.calls,
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

            self.assertEqual(
                risk.requests,
                [],
            )

            evidence_path = (
                run_dir
                / "no-op-review-repair-1.json"
            )

            self.assertTrue(
                evidence_path.exists()
            )

            evidence = json.loads(
                evidence_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertFalse(
                evidence[
                    "repository_changed"
                ]
            )

            self.assertEqual(
                evidence[
                    "before_fingerprint"
                ],
                evidence[
                    "after_fingerprint"
                ],
            )

    def test_changed_review_repair_preserves_rereview(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            runtime = self.make_runtime(root)

            review_high = json.dumps(
                {
                    "summary": "blocking",
                    "findings": [
                        {
                            "severity": "major",
                            "message": "must fix",
                        }
                    ],
                    "risk": "high",
                    "risk_confidence": 1.0,
                    "risk_reasons": [
                        "blocking"
                    ],
                }
            )

            generator = FixingFakeModel(
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
                [
                    review_high,
                    REVIEW_LOW,
                ],
            )

            risk = FakeModel(
                runtime,
                "codex",
                [
                    RISK_LOW,
                ],
            )

            verifier = FakeVerifier(
                [
                    passed(),
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
                len(reviewer.requests),
                2,
            )

            self.assertEqual(
                verifier.calls,
                2,
            )

            self.assertEqual(
                len(risk.requests),
                1,
            )

            self.assertTrue(
                (
                    repo / "repair.txt"
                ).exists()
            )

            self.assertFalse(
                (
                    run_dir
                    / "no-op-review-repair-1.json"
                ).exists()
            )


    def test_custom_risk_engine_preserves_independent_judge(
        self,
    ):
        class CustomRiskEngine:
            def assess(
                self,
                **kwargs,
            ):
                return {
                    "rule": {
                        "risk": "low",
                        "reasons": [
                            "custom engine"
                        ],
                    },
                    "aggregate": {
                        "final": "high",
                        "sources": {
                            "rule": "low",
                            "codex": "low",
                            "claude": "high",
                        },
                        "large_disagreement": True,
                        "human_required": True,
                    },
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            runtime = self.make_runtime(root)

            review_high = json.dumps(
                {
                    "summary": "high",
                    "findings": [],
                    "risk": "high",
                    "risk_confidence": 1.0,
                    "risk_reasons": [
                        "high"
                    ],
                }
            )

            risk = FakeModel(
                runtime,
                "codex",
                [
                    RISK_LOW,
                ],
            )

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
                    [review_high],
                ),
                risk_judge=risk,
                verifier=FakeVerifier(
                    [passed()]
                ),
                risk_engine=CustomRiskEngine(),
                artifacts=ArtifactRegistry(),
            )

            self.assertEqual(
                len(risk.requests),
                1,
            )

            routing = json.loads(
                (
                    run_dir
                    / "risk-routing.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertTrue(
                routing[
                    "invoke_codex_risk"
                ]
            )

            self.assertEqual(
                routing["mode"],
                "engine_contract_preserved",
            )

            rule = json.loads(
                (
                    run_dir
                    / "rule-risk.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                rule["reasons"],
                [
                    "custom engine"
                ],
            )


    def test_review_repair_preserves_codex_risk_budget(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)

            runtime = Runtime(
                root / "run",
                Budgets(
                    codex_max_calls=2,
                    claude_max_calls=3,
                    max_fix_iterations=2,
                ),
            )

            runtime.run_dir.mkdir()

            review_high = json.dumps(
                {
                    "summary": "blocking",
                    "findings": [
                        {
                            "severity": "major",
                            "message": "must fix",
                        }
                    ],
                    "risk": "high",
                    "risk_confidence": 1.0,
                    "risk_reasons": [
                        "blocking"
                    ],
                }
            )

            generator = FakeModel(
                runtime,
                "codex",
                [
                    "generated",
                ],
            )

            reviewer = FakeModel(
                runtime,
                "claude",
                [
                    review_high,
                ],
            )

            risk = FakeModel(
                runtime,
                "codex",
                [],
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
                "HUMAN_REQUIRED",
            )

            self.assertEqual(
                [
                    request.role
                    for request
                    in generator.requests
                ],
                [
                    "generator",
                ],
            )

            self.assertEqual(
                len(reviewer.requests),
                1,
            )

            self.assertEqual(
                risk.requests,
                [],
            )

            evidence = json.loads(
                (
                    run_dir
                    / (
                        "review-repair-budget-"
                        "1.json"
                    )
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertFalse(
                evidence["allow_repair"]
            )

            self.assertEqual(
                evidence[
                    "codex_remaining"
                ],
                1,
            )

            self.assertEqual(
                evidence[
                    "codex_required"
                ],
                2,
            )

    def test_review_repair_requires_claude_rereview_budget(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)

            runtime = Runtime(
                root / "run",
                Budgets(
                    codex_max_calls=4,
                    claude_max_calls=1,
                    max_fix_iterations=2,
                ),
            )

            runtime.run_dir.mkdir()

            review_high = json.dumps(
                {
                    "summary": "blocking",
                    "findings": [
                        {
                            "severity": "major",
                            "message": "must fix",
                        }
                    ],
                    "risk": "high",
                    "risk_confidence": 1.0,
                    "risk_reasons": [
                        "blocking"
                    ],
                }
            )

            generator = FakeModel(
                runtime,
                "codex",
                [
                    "generated",
                ],
            )

            reviewer = FakeModel(
                runtime,
                "claude",
                [
                    review_high,
                ],
            )

            run_dir = execute_panel(
                runtime=runtime,
                repo=repo,
                task=self.task(),
                config=self.config(),
                generator=generator,
                reviewer=reviewer,
                risk_judge=FakeModel(
                    runtime,
                    "codex",
                    [],
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
                [
                    request.role
                    for request
                    in generator.requests
                ],
                [
                    "generator",
                ],
            )

            self.assertEqual(
                len(reviewer.requests),
                1,
            )

            evidence = json.loads(
                (
                    run_dir
                    / (
                        "review-repair-budget-"
                        "1.json"
                    )
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertFalse(
                evidence["allow_repair"]
            )

            self.assertEqual(
                evidence[
                    "claude_remaining"
                ],
                0,
            )

            self.assertEqual(
                evidence[
                    "claude_required"
                ],
                1,
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



    def test_claude_high_skips_redundant_codex_risk(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            runtime = self.make_runtime(root)

            risk_judge = FakeModel(
                runtime,
                "codex",
                [],
            )

            review_high = json.dumps(
                {
                    "summary": "high risk",
                    "findings": [],
                    "risk": "high",
                    "risk_confidence": 1.0,
                    "risk_reasons": [
                        "high"
                    ],
                }
            )

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
                    [review_high],
                ),
                risk_judge=risk_judge,
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
                risk_judge.requests,
                [],
            )

            self.assertFalse(
                (
                    run_dir
                    / "codex-risk.json"
                ).exists()
            )

            routing = json.loads(
                (
                    run_dir
                    / "risk-routing.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertFalse(
                routing[
                    "invoke_codex_risk"
                ]
            )

            self.assertEqual(
                routing["mode"],
                "terminal_high",
            )

            aggregate = json.loads(
                (
                    run_dir
                    / "aggregate-risk.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                aggregate["final"],
                "high",
            )

            self.assertTrue(
                aggregate[
                    "human_required"
                ]
            )

            self.assertIsNone(
                aggregate["sources"][
                    "codex"
                ]
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
                    first_store.load_resume_checkpoint(
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


    def test_resume_after_verification_runs_review_only(
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

            first_store = SQLiteStateStore(
                state_db
            )

            first_generator = (
                EditingFakeModel(
                    first_runtime,
                    "codex",
                    ["generated"],
                )
            )

            first_verifier = (
                FakeVerifier(
                    [passed()]
                )
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
                        generator=(
                            first_generator
                        ),
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
                        verifier=(
                            first_verifier
                        ),
                        risk_engine=(
                            LegacyCompatibleRiskEngine()
                        ),
                        artifacts=(
                            ArtifactRegistry()
                        ),
                        durable=DurableExecution(
                            store=first_store,
                            run_id="run-verified",
                            fault_after_state=(
                                "VERIFIED"
                            ),
                        ),
                    )

                checkpoint = (
                    first_store.load_resume_checkpoint(
                        "run-verified"
                    )
                )

                self.assertIsNotNone(
                    checkpoint
                )

                self.assertEqual(
                    checkpoint["state"],
                    "VERIFIED",
                )

                self.assertEqual(
                    len(
                        first_generator
                        .requests
                    ),
                    1,
                )

                self.assertEqual(
                    first_verifier.calls,
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

            assert checkpoint is not None

            second_store = SQLiteStateStore(
                state_db
            )

            try:
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

                resumed_verifier = (
                    FakeVerifier([])
                )

                reviewer = FakeModel(
                    second_runtime,
                    "claude",
                    [REVIEW_LOW],
                )

                result_dir = execute_panel(
                    runtime=second_runtime,
                    repo=repo,
                    task=self.task(),
                    config=self.config(),
                    generator=(
                        resumed_generator
                    ),
                    reviewer=reviewer,
                    risk_judge=FakeModel(
                        second_runtime,
                        "codex",
                        [RISK_LOW],
                    ),
                    verifier=(
                        resumed_verifier
                    ),
                    risk_engine=(
                        LegacyCompatibleRiskEngine()
                    ),
                    artifacts=(
                        ArtifactRegistry()
                    ),
                    durable=DurableExecution(
                        store=second_store,
                        run_id="run-verified",
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
                    resumed_verifier.calls,
                    0,
                )

                self.assertEqual(
                    len(
                        reviewer.requests
                    ),
                    1,
                )

                self.assertEqual(
                    reviewer.requests[0].role,
                    "reviewer",
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

    def test_forbidden_prod_diff_blocks_verifier_and_is_reported(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)

            run_dir = root / "run"
            run_dir.mkdir()

            runtime = Runtime(
                run_dir,
                Budgets(
                    max_fix_iterations=0,
                ),
            )

            class ForbiddenProdModel(
                FakeModel
            ):
                def invoke(
                    self,
                    request: ModelRequest,
                ) -> ModelResult:
                    if (
                        request.role
                        == "generator"
                    ):
                        target = (
                            request.repo
                            / "infra"
                            / "prod"
                            / "main.tf"
                        )

                        target.parent.mkdir(
                            parents=True,
                            exist_ok=True,
                        )

                        target.write_text(
                            "resource {}\n",
                            encoding="utf-8",
                        )

                    return super().invoke(
                        request
                    )

            generator = ForbiddenProdModel(
                runtime,
                "codex",
                [""],
            )

            reviewer = FakeModel(
                runtime,
                "claude",
                [],
            )

            risk_judge = FakeModel(
                runtime,
                "codex",
                [],
            )

            verifier = FakeVerifier(
                [passed()]
            )

            result = execute_panel(
                runtime=runtime,
                repo=repo,
                canonical_repo=repo,
                task={
                    "task": (
                        "Attempt forbidden "
                        "production change"
                    )
                },
                config=self.config(),
                generator=generator,
                reviewer=reviewer,
                risk_judge=risk_judge,
                verifier=verifier,
                risk_engine=(
                    LegacyCompatibleRiskEngine()
                ),
                artifacts=ArtifactRegistry(),
                durable=None,
            )

            self.assertEqual(
                result,
                run_dir,
            )

            self.assertEqual(
                verifier.calls,
                0,
            )

            self.assertEqual(
                reviewer.requests,
                [],
            )

            self.assertEqual(
                risk_judge.requests,
                [],
            )

            guard_path = (
                run_dir
                / "round-0.diff-guard.json"
            )

            self.assertTrue(
                guard_path.exists()
            )

            guard = json.loads(
                guard_path.read_text(
                    encoding="utf-8"
                )
            )

            self.assertFalse(
                guard["passed"]
            )

            self.assertEqual(
                guard[
                    "forbidden_matches"
                ][0]["path"],
                "infra/prod/main.tf",
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

            self.assertIn(
                "diff guard blocked change",
                status["reason"],
            )

            self.assertIn(
                "infra/prod/main.tf",
                status["reason"],
            )



if __name__ == "__main__":
    unittest.main()
