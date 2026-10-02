import os
import tempfile
import unittest

from pathlib import Path

from aivp.context.repo_map import (
    build_repo_map,
)


class ContextRepoMapTests(
    unittest.TestCase
):
    def test_repo_map_is_sorted_and_classified(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (repo / "src").mkdir()
            (repo / "tests").mkdir()

            (
                repo
                / "src"
                / "service.py"
            ).write_text(
                "def run():\n    pass\n",
                encoding="utf-8",
            )

            (
                repo
                / "tests"
                / "test_service.py"
            ).write_text(
                "def test_run():\n    pass\n",
                encoding="utf-8",
            )

            (
                repo
                / "README.md"
            ).write_text(
                "# Example\n",
                encoding="utf-8",
            )

            entries = build_repo_map(
                repo
            )

            paths = [
                entry.path
                for entry in entries
            ]

            self.assertEqual(
                paths,
                sorted(paths),
            )

            by_path = {
                entry.path: entry
                for entry in entries
            }

            self.assertFalse(
                by_path[
                    "src/service.py"
                ].is_test
            )

            self.assertTrue(
                by_path[
                    "tests/test_service.py"
                ].is_test
            )

            self.assertEqual(
                by_path[
                    "README.md"
                ].suffix,
                ".md",
            )

    def test_repo_map_ignores_noise_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo
                / "node_modules"
            ).mkdir()

            (
                repo
                / ".git"
            ).mkdir()

            (
                repo
                / "node_modules"
                / "ignored.js"
            ).write_text(
                "ignored",
                encoding="utf-8",
            )

            (
                repo
                / ".git"
                / "ignored"
            ).write_text(
                "ignored",
                encoding="utf-8",
            )

            (
                repo
                / "app.py"
            ).write_text(
                "print('ok')\n",
                encoding="utf-8",
            )

            paths = [
                entry.path
                for entry in build_repo_map(
                    repo
                )
            ]

            self.assertEqual(
                paths,
                ["app.py"],
            )

    def test_repo_map_marks_binary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo
                / "image.bin"
            ).write_bytes(
                b"\x01\x02\x00\x03"
            )

            entry = build_repo_map(
                repo
            )[0]

            self.assertTrue(
                entry.is_binary
            )

    def test_repo_map_does_not_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo = root / "repo"
            outside = root / "outside"

            repo.mkdir()
            outside.mkdir()

            (
                outside
                / "secret.txt"
            ).write_text(
                "SENSITIVE_OUTSIDE_TOKEN",
                encoding="utf-8",
            )

            link = (
                repo
                / "outside-link"
            )

            try:
                os.symlink(
                    outside,
                    link,
                )
            except OSError:
                self.skipTest(
                    "symlink unavailable"
                )

            paths = [
                entry.path
                for entry in build_repo_map(
                    repo
                )
            ]

            self.assertEqual(
                paths,
                [],
            )

    def test_repo_map_ignores_generated_run_reports(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            reports = (
                repo / "reports"
            )

            reports.mkdir()

            (
                reports
                / "reference.md"
            ).write_text(
                "keep me\n",
                encoding="utf-8",
            )

            run_dir = (
                reports
                / "m1-exit"
                / "case"
                / "run-20261003-010000"
            )

            run_dir.mkdir(
                parents=True
            )

            (
                run_dir
                / "task.txt"
            ).write_text(
                "historical task\n",
                encoding="utf-8",
            )

            paths = [
                entry.path
                for entry
                in build_repo_map(
                    repo
                )
            ]

            self.assertIn(
                "reports/reference.md",
                paths,
            )

            self.assertNotIn(
                (
                    "reports/m1-exit/"
                    "case/"
                    "run-20261003-010000/"
                    "task.txt"
                ),
                paths,
            )


if __name__ == "__main__":
    unittest.main()
