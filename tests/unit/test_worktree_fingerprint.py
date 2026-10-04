import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.repository.git import (
    worktree_fingerprint,
)


class WorktreeFingerprintTests(
    unittest.TestCase
):
    def make_repo(
        self,
        root: Path,
    ) -> Path:
        repo = root / "repo"
        repo.mkdir()

        subprocess.run(
            [
                "git",
                "init",
                "-q",
            ],
            cwd=repo,
            check=True,
        )

        subprocess.run(
            [
                "git",
                "config",
                "user.email",
                "test@example.com",
            ],
            cwd=repo,
            check=True,
        )

        subprocess.run(
            [
                "git",
                "config",
                "user.name",
                "Test",
            ],
            cwd=repo,
            check=True,
        )

        tracked = repo / "tracked.txt"
        tracked.write_text(
            "baseline\n",
            encoding="utf-8",
        )

        subprocess.run(
            [
                "git",
                "add",
                "tracked.txt",
            ],
            cwd=repo,
            check=True,
        )

        subprocess.run(
            [
                "git",
                "commit",
                "-qm",
                "baseline",
            ],
            cwd=repo,
            check=True,
        )

        return repo

    def test_unchanged_state_is_stable(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(
                Path(tmp)
            )

            before = worktree_fingerprint(
                repo
            )

            after = worktree_fingerprint(
                repo
            )

            self.assertEqual(
                before,
                after,
            )

    def test_tracked_change_changes_fingerprint(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(
                Path(tmp)
            )

            before = worktree_fingerprint(
                repo
            )

            (
                repo / "tracked.txt"
            ).write_text(
                "changed\n",
                encoding="utf-8",
            )

            after = worktree_fingerprint(
                repo
            )

            self.assertNotEqual(
                before,
                after,
            )

    def test_untracked_text_changes_fingerprint(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(
                Path(tmp)
            )

            before = worktree_fingerprint(
                repo
            )

            (
                repo / "new.txt"
            ).write_text(
                "hello\n",
                encoding="utf-8",
            )

            after = worktree_fingerprint(
                repo
            )

            self.assertNotEqual(
                before,
                after,
            )

    def test_large_binary_content_is_fingerprinted(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(
                Path(tmp)
            )

            binary = (
                repo / "large.bin"
            )

            binary.write_bytes(
                b"A" * 300_000
            )

            first = worktree_fingerprint(
                repo
            )

            binary.write_bytes(
                b"B" * 300_000
            )

            second = worktree_fingerprint(
                repo
            )

            self.assertNotEqual(
                first,
                second,
            )


if __name__ == "__main__":
    unittest.main()
