import subprocess
import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace

from aivp.execution.runtime import (
    Budgets,
    Runtime,
)
from aivp.state.durable import (
    complete_verification,
)


class RecordingStore:
    def __init__(self):
        self.calls = []

    def complete_step(
        self,
        **kwargs,
    ):
        self.calls.append(
            kwargs
        )


class DurableVerificationRoundIdentityTests(
    unittest.TestCase
):
    def test_verification_identity_includes_round(
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

            store = RecordingStore()

            durable = SimpleNamespace(
                run_id="run-1",
                attempt=1,
                store=store,
                canonical_repo_path=None,
                fault_after_state=None,
            )

            verification = {
                "passed": True,
                "results": [],
            }

            for round_index in (
                0,
                1,
            ):
                complete_verification(
                    durable=durable,
                    runtime=runtime,
                    repo=repo,
                    task={
                        "task": "test",
                        "acceptance": [],
                        "constraints": [],
                    },
                    config={},
                    verification=verification,
                    verification_round=(
                        round_index
                    ),
                )

            self.assertEqual(
                len(store.calls),
                2,
            )

            first = store.calls[0]
            second = store.calls[1]

            self.assertEqual(
                first["step_id"],
                "run-1:verify:1:0",
            )

            self.assertEqual(
                second["step_id"],
                "run-1:verify:1:1",
            )

            first_artifact = (
                first[
                    "artifacts"
                ][0]
            )

            second_artifact = (
                second[
                    "artifacts"
                ][0]
            )

            self.assertEqual(
                first_artifact[
                    "artifact_id"
                ],
                "run-1:verification:1:0",
            )

            self.assertEqual(
                second_artifact[
                    "artifact_id"
                ],
                "run-1:verification:1:1",
            )

            self.assertNotEqual(
                first_artifact[
                    "path"
                ],
                second_artifact[
                    "path"
                ],
            )

            self.assertEqual(
                first[
                    "checkpoint_payload"
                ][
                    "verification_round"
                ],
                0,
            )

            self.assertEqual(
                second[
                    "checkpoint_payload"
                ][
                    "verification_round"
                ],
                1,
            )


if __name__ == "__main__":
    unittest.main()
