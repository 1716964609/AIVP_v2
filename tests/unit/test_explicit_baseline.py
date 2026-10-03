import subprocess
import tempfile
import unittest

from pathlib import Path
from unittest.mock import MagicMock, patch

from aivp.application import run_new
from aivp.containment.worktree import (
    RunWorktree,
    create_run_worktree,
)
from aivp.errors import AIVPError


class ExplicitBaselineTests(unittest.TestCase):
    def _git(
        self,
        repo: Path,
        *args: str,
    ) -> str:
        cp = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                *args,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        return cp.stdout.strip()

    def _repo_with_two_commits(
        self,
        root: Path,
    ):
        repo = root / "repo"

        subprocess.run(
            [
                "git",
                "init",
                "-q",
                str(repo),
            ],
            check=True,
        )

        self._git(
            repo,
            "config",
            "user.name",
            "AIVP Test",
        )
        self._git(
            repo,
            "config",
            "user.email",
            "aivp@example.invalid",
        )

        target = repo / "value.txt"

        target.write_text(
            "one\n",
            encoding="utf-8",
        )
        self._git(repo, "add", "value.txt")
        self._git(
            repo,
            "commit",
            "-q",
            "-m",
            "first",
        )

        first = self._git(
            repo,
            "rev-parse",
            "HEAD",
        )

        target.write_text(
            "two\n",
            encoding="utf-8",
        )
        self._git(repo, "add", "value.txt")
        self._git(
            repo,
            "commit",
            "-q",
            "-m",
            "second",
        )

        second = self._git(
            repo,
            "rev-parse",
            "HEAD",
        )

        return repo, first, second

    def test_worktree_can_start_from_explicit_revision(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            repo, first, second = (
                self._repo_with_two_commits(
                    root
                )
            )

            worktree_path = root / "worktree"

            result = create_run_worktree(
                canonical_repo=repo,
                worktree_path=worktree_path,
                base_revision=first,
            )

            self.assertEqual(
                result.base_sha,
                first,
            )
            self.assertEqual(
                self._git(
                    worktree_path,
                    "rev-parse",
                    "HEAD",
                ),
                first,
            )
            self.assertEqual(
                self._git(
                    repo,
                    "rev-parse",
                    "HEAD",
                ),
                second,
            )

    def test_unknown_revision_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            repo, _, _ = (
                self._repo_with_two_commits(
                    root
                )
            )

            with self.assertRaises(
                AIVPError
            ):
                create_run_worktree(
                    canonical_repo=repo,
                    worktree_path=(
                        root / "worktree"
                    ),
                    base_revision=(
                        "does-not-exist"
                    ),
                )

    def test_run_new_forwards_base_revision(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = root / "repo"
            repo.mkdir()

            reports = root / "reports"
            state_db = root / "state.db"

            fake_worktree = (
                reports
                / "run-1"
                / "worktree"
            )

            with (
                patch(
                    "aivp.application."
                    "create_run_worktree"
                ) as create_worktree,
                patch(
                    "aivp.application."
                    "SQLiteStateStore"
                ) as store_cls,
                patch(
                    "aivp.application."
                    "_pricing_catalog_from_config",
                    return_value=None,
                ),
                patch(
                    "aivp.application._execute"
                ) as execute,
            ):
                create_worktree.return_value = (
                    RunWorktree(
                        canonical_repo=(
                            repo.resolve()
                        ),
                        path=fake_worktree,
                        base_sha="abc123",
                    )
                )

                store_cls.return_value.__enter__.return_value = (
                    MagicMock()
                )

                execute.return_value = (
                    reports.resolve()
                    / "run-1"
                )

                result = run_new(
                    repo=repo,
                    task={},
                    config={},
                    reports_root=reports,
                    state_db=state_db,
                    run_id="run-1",
                    base_revision="abc123",
                )

            self.assertEqual(
                result,
                reports.resolve()
                / "run-1",
            )

            create_worktree.assert_called_once_with(
                canonical_repo=repo.resolve(),
                worktree_path=(
                    reports.resolve()
                    / "run-1"
                    / "worktree"
                ),
                base_revision="abc123",
            )

    def test_dry_run_rejects_explicit_revision(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = root / "repo"
            repo.mkdir()

            with self.assertRaises(
                AIVPError
            ):
                run_new(
                    repo=repo,
                    task={},
                    config={},
                    reports_root=(
                        root / "reports"
                    ),
                    state_db=(
                        root / "state.db"
                    ),
                    dry_run=True,
                    base_revision="abc123",
                )


if __name__ == "__main__":
    unittest.main()
