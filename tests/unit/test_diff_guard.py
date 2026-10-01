import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.verification.diff_guard import (
    evaluate_diff_guard,
)


class DiffGuardTests(
    unittest.TestCase
):
    def _repo(
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

        return repo

    def test_small_safe_diff_passes(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(
                Path(tmp)
            )

            (
                repo / "safe.txt"
            ).write_text(
                "safe\n",
                encoding="utf-8",
            )

            result = evaluate_diff_guard(
                repo,
                {},
            )

            self.assertTrue(
                result["passed"]
            )

            self.assertEqual(
                result["changed_files"],
                1,
            )

            self.assertEqual(
                result["violations"],
                [],
            )

    def test_forbidden_prod_path_is_rejected(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(
                Path(tmp)
            )

            target = (
                repo
                / "infra"
                / "prod"
                / "main.tf"
            )

            target.parent.mkdir(
                parents=True
            )

            target.write_text(
                "resource {}\n",
                encoding="utf-8",
            )

            result = evaluate_diff_guard(
                repo,
                {},
            )

            self.assertFalse(
                result["passed"]
            )

            self.assertEqual(
                result[
                    "forbidden_matches"
                ][0]["path"],
                "infra/prod/main.tf",
            )

    def test_max_files_is_enforced(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(
                Path(tmp)
            )

            (
                repo / "one.txt"
            ).write_text(
                "one\n",
                encoding="utf-8",
            )

            (
                repo / "two.txt"
            ).write_text(
                "two\n",
                encoding="utf-8",
            )

            result = evaluate_diff_guard(
                repo,
                {
                    "diff_guard": {
                        "max_files": 1,
                        "forbidden_paths": [],
                    }
                },
            )

            self.assertFalse(
                result["passed"]
            )

            self.assertEqual(
                result["changed_files"],
                2,
            )

            self.assertTrue(
                any(
                    "max_files"
                    in violation
                    for violation
                    in result[
                        "violations"
                    ]
                )
            )

    def test_max_diff_lines_is_enforced(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(
                Path(tmp)
            )

            (
                repo / "base.txt"
            ).write_text(
                "\n".join(
                    f"line-{i}"
                    for i in range(20)
                )
                + "\n",
                encoding="utf-8",
            )

            result = evaluate_diff_guard(
                repo,
                {
                    "diff_guard": {
                        "max_lines": 5,
                        "forbidden_paths": [],
                    }
                },
            )

            self.assertFalse(
                result["passed"]
            )

            self.assertGreater(
                result["diff_lines"],
                5,
            )

            self.assertTrue(
                any(
                    "max_lines"
                    in violation
                    for violation
                    in result[
                        "violations"
                    ]
                )
            )


if __name__ == "__main__":
    unittest.main()
