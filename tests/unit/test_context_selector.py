import tempfile
import unittest

from pathlib import Path

from aivp.context.repo_map import (
    build_repo_map,
)
from aivp.context.selector import (
    select_relevant_files,
)


class ContextSelectorTests(
    unittest.TestCase
):
    def test_selector_ranks_path_and_content_matches(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (repo / "src").mkdir()

            (
                repo
                / "src"
                / "authentication.py"
            ).write_text(
                (
                    "def handle_timeout():\n"
                    "    pass\n"
                ),
                encoding="utf-8",
            )

            (
                repo
                / "src"
                / "session.py"
            ).write_text(
                (
                    "authentication timeout "
                    "handling\n"
                ),
                encoding="utf-8",
            )

            (
                repo
                / "src"
                / "unrelated.py"
            ).write_text(
                "def calculate_price():\n    pass\n",
                encoding="utf-8",
            )

            result = select_relevant_files(
                repo=repo,
                repo_map=build_repo_map(
                    repo
                ),
                task_text=(
                    "Fix authentication timeout"
                ),
            )

            paths = [
                item.path
                for item in result
            ]

            self.assertEqual(
                paths[0],
                "src/authentication.py",
            )

            self.assertIn(
                "src/session.py",
                paths,
            )

            self.assertNotIn(
                "src/unrelated.py",
                paths,
            )

            self.assertGreater(
                result[0].score,
                result[1].score,
            )

    def test_selector_explains_selection_reasons(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo
                / "authentication.py"
            ).write_text(
                "timeout = 30\n",
                encoding="utf-8",
            )

            result = select_relevant_files(
                repo=repo,
                repo_map=build_repo_map(
                    repo
                ),
                task_text=(
                    "authentication timeout"
                ),
            )

            candidate = result[0]

            self.assertIn(
                "path_token:authentication",
                candidate.reasons,
            )

            self.assertIn(
                "content_token:timeout",
                candidate.reasons,
            )

    def test_selector_excludes_binary_files(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo
                / "authentication.bin"
            ).write_bytes(
                b"authentication\x00timeout"
            )

            result = select_relevant_files(
                repo=repo,
                repo_map=build_repo_map(
                    repo
                ),
                task_text=(
                    "authentication timeout"
                ),
            )

            self.assertEqual(
                result,
                (),
            )

    def test_selector_is_deterministic(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo
                / "b.py"
            ).write_text(
                "timeout handling\n",
                encoding="utf-8",
            )

            (
                repo
                / "a.py"
            ).write_text(
                "timeout handling\n",
                encoding="utf-8",
            )

            repo_map = build_repo_map(
                repo
            )

            first = select_relevant_files(
                repo=repo,
                repo_map=repo_map,
                task_text="timeout",
            )

            second = select_relevant_files(
                repo=repo,
                repo_map=repo_map,
                task_text="timeout",
            )

            self.assertEqual(
                first,
                second,
            )

            self.assertEqual(
                [
                    item.path
                    for item in first
                ],
                [
                    "a.py",
                    "b.py",
                ],
            )


if __name__ == "__main__":
    unittest.main()
