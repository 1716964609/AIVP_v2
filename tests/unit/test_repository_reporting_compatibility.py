import subprocess
import tempfile
import unittest

from pathlib import Path

import aivp.legacy.orchestrator_v1 as legacy

from aivp.errors import AIVPError
from aivp.panel.reporting import human_packet
from aivp.repository.git import (
    assert_clean_repo,
    assert_git_repo,
    capture_diff,
    changed_paths,
    repo_lock,
)


class RepositoryReportingCompatibilityTests(
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
                str(repo),
            ],
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
            [
                "git",
                "add",
                "base.txt",
            ],
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

    def test_git_repository_assertion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)

            assert_git_repo(repo)

            non_repo = root / "not-repo"
            non_repo.mkdir()

            with self.assertRaises(
                AIVPError
            ):
                assert_git_repo(
                    non_repo
                )

    def test_clean_repo_assertion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)

            assert_clean_repo(repo)

            (
                repo / "untracked.txt"
            ).write_text(
                "change\n",
                encoding="utf-8",
            )

            with self.assertRaises(
                AIVPError
            ):
                assert_clean_repo(repo)

    def test_diff_and_paths_match_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)

            (
                repo / "base.txt"
            ).write_text(
                "changed\n",
                encoding="utf-8",
            )

            (
                repo / "new.txt"
            ).write_text(
                "new\n",
                encoding="utf-8",
            )

            self.assertEqual(
                capture_diff(repo),
                legacy.capture_diff(repo),
            )

            self.assertEqual(
                changed_paths(repo),
                legacy.changed_paths(repo),
            )

    def test_repo_lock_rejects_second_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            with repo_lock(repo):
                with self.assertRaises(
                    AIVPError
                ):
                    with repo_lock(repo):
                        pass

            with repo_lock(repo):
                pass

    def test_human_packet_matches_legacy(self):
        kwargs = {
            "task": {
                "task": "Example task",
            },
            "verification": {
                "passed": False,
                "results": [
                    {
                        "name": "tests",
                        "passed": False,
                    }
                ],
            },
            "claude_review": {
                "risk": "medium",
                "findings": [
                    {
                        "severity": "major",
                        "file": "x.py",
                        "line": 10,
                        "reason": "broken",
                    }
                ],
            },
            "rule_risk": {
                "risk": "low",
            },
            "codex_risk": {
                "risk": "medium",
            },
            "aggregate": {
                "final": "medium",
            },
            "paths": [
                "x.py",
            ],
            "reason": "test reason",
            "metrics": {
                "codex_calls": 2,
                "claude_calls": 1,
                "fix_iterations": 1,
                "elapsed_seconds": 12.3,
            },
        }

        self.assertEqual(
            human_packet(**kwargs),
            legacy.human_packet(**kwargs),
        )


if __name__ == "__main__":
    unittest.main()
