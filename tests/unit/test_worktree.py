import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.containment.worktree import (
    create_run_worktree,
    validate_run_worktree,
)
from aivp.errors import AIVPError
from aivp.repository.git import (
    capture_diff,
    git,
)


class RunWorktreeTests(unittest.TestCase):
    def _make_repo(
        self,
        root: Path,
    ) -> Path:
        repo = root / "repo"
        repo.mkdir()

        subprocess.run(
            ["git", "init"],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        git(
            repo,
            "config",
            "user.email",
            "aivp-test@example.invalid",
        )

        git(
            repo,
            "config",
            "user.name",
            "AIVP Test",
        )

        target = repo / "tracked.txt"
        target.write_text(
            "base\n",
            encoding="utf-8",
        )

        git(
            repo,
            "add",
            "tracked.txt",
        )

        git(
            repo,
            "commit",
            "-m",
            "base",
        )

        return repo

    def test_worktree_isolates_mutation_from_canonical_repo(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self._make_repo(root)

            worktree = create_run_worktree(
                canonical_repo=repo,
                worktree_path=(
                    root
                    / "worktrees"
                    / "run-1"
                ),
            )

            (
                worktree.path
                / "tracked.txt"
            ).write_text(
                "changed\n",
                encoding="utf-8",
            )

            self.assertEqual(
                (
                    repo
                    / "tracked.txt"
                ).read_text(
                    encoding="utf-8"
                ),
                "base\n",
            )

            self.assertNotEqual(
                capture_diff(
                    worktree.path
                ),
                "",
            )

            self.assertEqual(
                capture_diff(repo),
                "",
            )

            canonical_status = git(
                repo,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ).stdout

            self.assertEqual(
                canonical_status,
                "",
            )

    def test_existing_worktree_validates_against_base_sha(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self._make_repo(root)

            worktree = create_run_worktree(
                canonical_repo=repo,
                worktree_path=(
                    root
                    / "worktrees"
                    / "run-2"
                ),
            )

            reopened = validate_run_worktree(
                canonical_repo=repo,
                worktree_path=worktree.path,
                base_sha=worktree.base_sha,
            )

            self.assertEqual(
                reopened,
                worktree,
            )

    def test_wrong_base_sha_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self._make_repo(root)

            worktree = create_run_worktree(
                canonical_repo=repo,
                worktree_path=(
                    root
                    / "worktrees"
                    / "run-3"
                ),
            )

            with self.assertRaises(
                AIVPError
            ):
                validate_run_worktree(
                    canonical_repo=repo,
                    worktree_path=(
                        worktree.path
                    ),
                    base_sha="wrong-base",
                )


if __name__ == "__main__":
    unittest.main()
