import tempfile
import unittest

from pathlib import Path

from aivp.artifacts.registry import ArtifactRegistry
from aivp.errors import PolicyDenied
from aivp.execution.runtime import Budgets, Runtime
from aivp.panel.orchestrator import (
    _invoke_edit,
    _invoke_review,
    _invoke_risk,
)
from aivp.policy.capability import (
    Capability,
    Decision,
    StaticCapabilityPolicy,
)


class RecordingModel:
    def __init__(self):
        self.requests = []

    def invoke(self, request):
        self.requests.append(request)
        raise AssertionError(
            "Model must not be invoked "
            "after policy denial"
        )


class ModelPolicyGateTests(
    unittest.TestCase
):
    def runtime_and_repo(self, root: Path):
        run_dir = root / "run"
        run_dir.mkdir()

        repo = root / "repo"
        repo.mkdir()

        runtime = Runtime(
            run_dir,
            Budgets(),
        )

        return runtime, repo

    def test_local_mutate_denial_blocks_generator(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime, repo = (
                self.runtime_and_repo(root)
            )

            model = RecordingModel()

            policy = StaticCapabilityPolicy(
                {
                    Capability.C1_LOCAL_MUTATE:
                        Decision.DENY,
                }
            )

            with self.assertRaises(
                PolicyDenied
            ):
                _invoke_edit(
                    adapter=model,
                    runtime=runtime,
                    repo=repo,
                    prompt="generate",
                    log_stem="generate",
                    role="generator",
                    policy=policy,
                )

            self.assertEqual(
                model.requests,
                [],
            )

    def test_observe_denial_blocks_reviewer(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime, repo = (
                self.runtime_and_repo(root)
            )

            model = RecordingModel()

            policy = StaticCapabilityPolicy(
                {
                    Capability.C0_OBSERVE:
                        Decision.DENY,
                }
            )

            with self.assertRaises(
                PolicyDenied
            ):
                _invoke_review(
                    adapter=model,
                    runtime=runtime,
                    artifacts=ArtifactRegistry(),
                    repo=repo,
                    task_text="task",
                    diff_text="diff",
                    verification={
                        "passed": True,
                        "results": [],
                    },
                    review_index=0,
                    policy=policy,
                )

            self.assertEqual(
                model.requests,
                [],
            )

            self.assertFalse(
                (
                    runtime.run_dir
                    / "claude-review-0.prompt.txt"
                ).exists()
            )

    def test_observe_denial_blocks_risk_judge(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime, repo = (
                self.runtime_and_repo(root)
            )

            model = RecordingModel()

            policy = StaticCapabilityPolicy(
                {
                    Capability.C0_OBSERVE:
                        Decision.DENY,
                }
            )

            with self.assertRaises(
                PolicyDenied
            ):
                _invoke_risk(
                    adapter=model,
                    runtime=runtime,
                    artifacts=ArtifactRegistry(),
                    repo=repo,
                    task_text="task",
                    diff_text="diff",
                    policy=policy,
                )

            self.assertEqual(
                model.requests,
                [],
            )


if __name__ == "__main__":
    unittest.main()
