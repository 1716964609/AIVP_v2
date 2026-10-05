from __future__ import annotations

import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.errors import AIVPError
from aivp.maintenance.worktree_gc import (
    remove_owned_worktree,
    worktree_owned_by_repo,
)


def run_git(
    repo: Path,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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


def make_repo(
    root: Path,
    name: str,
) -> Path:
    repo = root / name
    repo.mkdir()

    run_git(
        repo,
        "init",
    )

    run_git(
        repo,
        "config",
        "user.email",
        "aivp-test@example.invalid",
    )

    run_git(
        repo,
        "config",
        "user.name",
        "AIVP Test",
    )

    tracked = repo / "tracked.txt"
    tracked.write_text(
        "baseline\n",
        encoding="utf-8",
    )

    run_git(
        repo,
        "add",
        "tracked.txt",
    )

    run_git(
        repo,
        "commit",
        "-m",
        "baseline",
    )

    return repo


def add_worktree(
    repo: Path,
    path: Path,
) -> None:
    run_git(
        repo,
        "worktree",
        "add",
        "--detach",
        str(path),
        "HEAD",
    )


class WorktreeGCTests(unittest.TestCase):
    def test_registered_worktree_is_owned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, "repo")
            worktree = root / "run-worktree"

            add_worktree(
                repo,
                worktree,
            )

            self.assertTrue(
                worktree_owned_by_repo(
                    canonical_repo=repo,
                    worktree_path=worktree,
                )
            )

    def test_normal_repo_subdirectory_is_not_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, "repo")
            subdir = repo / "ordinary-directory"
            subdir.mkdir()

            self.assertFalse(
                worktree_owned_by_repo(
                    canonical_repo=repo,
                    worktree_path=subdir,
                )
            )

    def test_foreign_worktree_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo_a = make_repo(
                root,
                "repo-a",
            )

            repo_b = make_repo(
                root,
                "repo-b",
            )

            foreign = root / "foreign-worktree"

            add_worktree(
                repo_b,
                foreign,
            )

            self.assertFalse(
                worktree_owned_by_repo(
                    canonical_repo=repo_a,
                    worktree_path=foreign,
                )
            )

            with self.assertRaises(AIVPError):
                remove_owned_worktree(
                    canonical_repo=repo_a,
                    worktree_path=foreign,
                    dry_run=False,
                )

            self.assertTrue(
                foreign.exists()
            )

    def test_canonical_repository_is_never_removable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, "repo")

            with self.assertRaises(AIVPError):
                remove_owned_worktree(
                    canonical_repo=repo,
                    worktree_path=repo,
                    dry_run=False,
                )

            self.assertTrue(
                repo.exists()
            )

    def test_dry_run_preserves_owned_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, "repo")
            worktree = root / "run-worktree"

            add_worktree(
                repo,
                worktree,
            )

            result = remove_owned_worktree(
                canonical_repo=repo,
                worktree_path=worktree,
                dry_run=True,
            )

            self.assertFalse(
                result.removed
            )

            self.assertTrue(
                result.dry_run
            )

            self.assertTrue(
                worktree.exists()
            )

            self.assertTrue(
                worktree_owned_by_repo(
                    canonical_repo=repo,
                    worktree_path=worktree,
                )
            )

    def test_clean_owned_worktree_can_be_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, "repo")
            worktree = root / "run-worktree"

            add_worktree(
                repo,
                worktree,
            )

            result = remove_owned_worktree(
                canonical_repo=repo,
                worktree_path=worktree,
                dry_run=False,
            )

            self.assertTrue(
                result.removed
            )

            self.assertFalse(
                worktree.exists()
            )

            self.assertFalse(
                worktree_owned_by_repo(
                    canonical_repo=repo,
                    worktree_path=worktree,
                )
            )

    def test_dirty_worktree_requires_explicit_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, "repo")
            worktree = root / "run-worktree"

            add_worktree(
                repo,
                worktree,
            )

            (
                worktree / "tracked.txt"
            ).write_text(
                "changed\n",
                encoding="utf-8",
            )

            with self.assertRaises(AIVPError):
                remove_owned_worktree(
                    canonical_repo=repo,
                    worktree_path=worktree,
                    dry_run=False,
                )

            self.assertTrue(
                worktree.exists()
            )

            result = remove_owned_worktree(
                canonical_repo=repo,
                worktree_path=worktree,
                dry_run=False,
                allow_dirty=True,
            )

            self.assertTrue(
                result.removed
            )

            self.assertFalse(
                worktree.exists()
            )

    def test_removal_is_idempotent_after_path_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(root, "repo")
            worktree = root / "run-worktree"

            add_worktree(
                repo,
                worktree,
            )

            first = remove_owned_worktree(
                canonical_repo=repo,
                worktree_path=worktree,
                dry_run=False,
            )

            second = remove_owned_worktree(
                canonical_repo=repo,
                worktree_path=worktree,
                dry_run=False,
            )

            self.assertTrue(
                first.removed
            )

            self.assertFalse(
                second.removed
            )

            self.assertEqual(
                second.reason,
                "worktree path is already absent",
            )


if __name__ == "__main__":
    unittest.main()
