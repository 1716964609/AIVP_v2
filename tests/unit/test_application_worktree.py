import json
import subprocess
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from aivp.application import (
    resume_run,
    run_new,
)
from aivp.models.base import ModelResult
from aivp.state.durable import (
    begin_generation,
    complete_generation,
)


class ApplicationWorktreeTests(
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

    def test_new_run_wires_execution_worktree(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            canonical_repo = (
                self.make_repo(root)
            )

            reports_root = (
                root / "reports"
            )

            run_id = "run-test"

            expected_worktree = (
                reports_root
                / run_id
                / "worktree"
            ).resolve()

            expected_result = (
                reports_root
                / run_id
            ).resolve()

            with patch(
                "aivp.application._execute",
                return_value=expected_result,
            ) as execute:
                result = run_new(
                    repo=canonical_repo,
                    task={
                        "task": "Example",
                        "acceptance": [],
                        "constraints": [],
                    },
                    config={},
                    reports_root=reports_root,
                    state_db=(
                        root / "state.sqlite3"
                    ),
                    run_id=run_id,
                )

            self.assertEqual(
                result,
                expected_result,
            )

            self.assertTrue(
                expected_worktree.exists()
            )

            kwargs = (
                execute.call_args.kwargs
            )

            self.assertEqual(
                kwargs["repo"],
                expected_worktree,
            )

            self.assertEqual(
                kwargs["canonical_repo"],
                canonical_repo.resolve(),
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


    def test_resume_reuses_surviving_execution_worktree(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            canonical_repo = (
                self.make_repo(root)
            )

            reports_root = (
                root / "reports"
            )

            state_db = (
                root / "state.sqlite3"
            )

            run_id = "run-resume-worktree"

            task = {
                "task": "Example",
                "acceptance": [],
                "constraints": [],
            }

            config = {}

            expected_run_dir = (
                reports_root / run_id
            ).resolve()

            expected_worktree = (
                expected_run_dir
                / "worktree"
            ).resolve()

            def seed_checkpoint(**kwargs):
                runtime = kwargs["runtime"]
                repo = kwargs["repo"]
                durable = kwargs["durable"]

                assert durable is not None

                (
                    runtime.run_dir
                    / "task.json"
                ).write_text(
                    json.dumps(task),
                    encoding="utf-8",
                )

                (
                    runtime.run_dir
                    / "effective-config.json"
                ).write_text(
                    json.dumps(config),
                    encoding="utf-8",
                )

                base_sha = begin_generation(
                    durable=durable,
                    repo=repo,
                )

                (
                    repo / "generated.txt"
                ).write_text(
                    "generated\n",
                    encoding="utf-8",
                )

                complete_generation(
                    durable=durable,
                    runtime=runtime,
                    repo=repo,
                    prompt="generate",
                    task=task,
                    config=config,
                    model_result=ModelResult(
                        provider="fake",
                        model="fake",
                        started_at="start",
                        finished_at="end",
                        raw_exit_status=0,
                        last_message="generated",
                    ),
                    base_sha=base_sha,
                )

                return runtime.run_dir

            with patch(
                "aivp.application._execute",
                side_effect=seed_checkpoint,
            ):
                first_result = run_new(
                    repo=canonical_repo,
                    task=task,
                    config=config,
                    reports_root=reports_root,
                    state_db=state_db,
                    run_id=run_id,
                )

            self.assertEqual(
                first_result,
                expected_run_dir,
            )

            self.assertTrue(
                expected_worktree.exists()
            )

            with patch(
                "aivp.application._execute",
                return_value=expected_run_dir,
            ) as resumed_execute:
                resumed_result = resume_run(
                    run_id=run_id,
                    state_db=state_db,
                )

            self.assertEqual(
                resumed_result,
                expected_run_dir,
            )

            kwargs = (
                resumed_execute.call_args.kwargs
            )

            self.assertEqual(
                kwargs["repo"],
                expected_worktree,
            )

            self.assertEqual(
                kwargs["canonical_repo"],
                canonical_repo.resolve(),
            )

            durable = kwargs["durable"]

            self.assertIsNotNone(
                durable
            )

            self.assertEqual(
                durable.canonical_repo_path,
                canonical_repo.resolve(),
            )

            checkpoint = (
                durable.resume_checkpoint
            )

            self.assertIsNotNone(
                checkpoint
            )

            self.assertEqual(
                checkpoint["repo_path"],
                str(expected_worktree),
            )

            self.assertEqual(
                checkpoint[
                    "canonical_repo_path"
                ],
                str(
                    canonical_repo.resolve()
                ),
            )

if __name__ == "__main__":
    unittest.main()
