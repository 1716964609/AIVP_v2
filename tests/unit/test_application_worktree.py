import subprocess
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from aivp.application import run_new


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


if __name__ == "__main__":
    unittest.main()
