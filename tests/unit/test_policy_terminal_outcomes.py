import json
import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.artifacts.registry import ArtifactRegistry
from aivp.errors import StateIntegrityError
from aivp.execution.runtime import (
    Budgets,
    Runtime,
)
from aivp.panel.orchestrator import execute_panel
from aivp.policy.capability import (
    Capability,
    Decision,
    StaticCapabilityPolicy,
)
from aivp.state.durable import DurableExecution
from aivp.state.resume import build_resume_plan
from aivp.state.sqlite import SQLiteStateStore


class NeverModel:
    def __init__(self):
        self.requests = []

    def invoke(self, request):
        self.requests.append(request)
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


class PolicyTerminalOutcomeTests(
    unittest.TestCase
):
    def _init_repo(
        self,
        repo: Path,
    ) -> None:
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

    def _exercise(
        self,
        *,
        decision: Decision,
        expected_status: str,
        expect_human_review: bool,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo = root / "repo"
            self._init_repo(repo)

            run_dir = root / "run"
            run_dir.mkdir()

            runtime = Runtime(
                run_dir,
                Budgets(),
            )

            generator = NeverModel()
            reviewer = NeverModel()
            risk_judge = NeverModel()

            policy = StaticCapabilityPolicy(
                {
                    Capability.C1_LOCAL_MUTATE:
                        decision,
                }
            )

            db_path = root / "state.db"

            with SQLiteStateStore(
                db_path
            ) as store:
                durable = DurableExecution(
                    store=store,
                    run_id="run-policy",
                    canonical_repo_path=repo,
                )

                result = execute_panel(
                    runtime=runtime,
                    repo=repo,
                    canonical_repo=repo,
                    task={
                        "task": (
                            "This task must not execute"
                        )
                    },
                    config={},
                    generator=generator,
                    reviewer=reviewer,
                    risk_judge=risk_judge,
                    verifier=NeverVerifier(),
                    risk_engine=NeverRiskEngine(),
                    artifacts=ArtifactRegistry(),
                    durable=durable,
                    policy=policy,
                )

                self.assertEqual(
                    result,
                    run_dir,
                )

                self.assertEqual(
                    generator.requests,
                    [],
                )
                self.assertEqual(
                    reviewer.requests,
                    [],
                )
                self.assertEqual(
                    risk_judge.requests,
                    [],
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
                    expected_status,
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
                    expected_status,
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

                checkpoint = store.load(
                    "run-policy"
                )

                self.assertEqual(
                    checkpoint["state"],
                    expected_status,
                )

                run = store.connection.execute(
                    """
                    SELECT current_state, status
                    FROM runs
                    WHERE run_id = ?
                    """,
                    ("run-policy",),
                ).fetchone()

                self.assertEqual(
                    run["current_state"],
                    expected_status,
                )
                self.assertEqual(
                    run["status"],
                    expected_status,
                )

                with self.assertRaises(
                    StateIntegrityError
                ):
                    build_resume_plan(
                        run_id="run-policy",
                        checkpoint=checkpoint,
                        artifact_records=list(
                            store.artifacts_for_run(
                                "run-policy"
                            )
                        ),
                    )

                self.assertEqual(
                    (
                        run_dir / "human-review.md"
                    ).exists(),
                    expect_human_review,
                )

    def test_policy_denial_becomes_durable_denied(
        self,
    ):
        self._exercise(
            decision=Decision.DENY,
            expected_status="DENIED",
            expect_human_review=False,
        )

    def test_policy_human_gate_becomes_durable_human_required(
        self,
    ):
        self._exercise(
            decision=Decision.HUMAN_REQUIRED,
            expected_status="HUMAN_REQUIRED",
            expect_human_review=True,
        )


if __name__ == "__main__":
    unittest.main()
