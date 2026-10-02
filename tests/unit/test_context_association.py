import tempfile
import unittest

from pathlib import Path

from aivp.context.association import (
    find_test_associations,
)
from aivp.context.repo_map import (
    build_repo_map,
)
from aivp.context.selector import (
    select_relevant_files,
)


class ContextAssociationTests(
    unittest.TestCase
):
    def test_python_source_associates_with_test_file(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (repo / "src").mkdir()
            (repo / "tests").mkdir()

            (
                repo
                / "src"
                / "authentication.py"
            ).write_text(
                "authentication timeout\n",
                encoding="utf-8",
            )

            (
                repo
                / "tests"
                / "test_authentication.py"
            ).write_text(
                "def test_authentication(): pass\n",
                encoding="utf-8",
            )

            repo_map = build_repo_map(
                repo
            )

            selected = select_relevant_files(
                repo=repo,
                repo_map=repo_map,
                task_text=(
                    "Fix authentication timeout"
                ),
            )

            associations = (
                find_test_associations(
                    repo_map=repo_map,
                    selected=selected,
                )
            )

            self.assertEqual(
                len(associations),
                1,
            )

            association = (
                associations[0]
            )

            self.assertEqual(
                association.source_path,
                "src/authentication.py",
            )

            self.assertEqual(
                association.test_path,
                "tests/test_authentication.py",
            )

            self.assertEqual(
                association.reason,
                "stem_match",
            )

    def test_typescript_dot_test_is_recognized(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo
                / "service.ts"
            ).write_text(
                "export const timeout = 30;\n",
                encoding="utf-8",
            )

            (
                repo
                / "service.test.ts"
            ).write_text(
                "test('timeout', () => {});\n",
                encoding="utf-8",
            )

            repo_map = build_repo_map(
                repo
            )

            by_path = {
                entry.path: entry
                for entry in repo_map
            }

            self.assertTrue(
                by_path[
                    "service.test.ts"
                ].is_test
            )

            selected = select_relevant_files(
                repo=repo,
                repo_map=repo_map,
                task_text="service timeout",
            )

            associations = (
                find_test_associations(
                    repo_map=repo_map,
                    selected=selected,
                )
            )

            pairs = {
                (
                    item.source_path,
                    item.test_path,
                )
                for item in associations
            }

            self.assertIn(
                (
                    "service.ts",
                    "service.test.ts",
                ),
                pairs,
            )

    def test_unrelated_test_is_not_associated(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (repo / "src").mkdir()
            (repo / "tests").mkdir()

            (
                repo
                / "src"
                / "authentication.py"
            ).write_text(
                "authentication timeout\n",
                encoding="utf-8",
            )

            (
                repo
                / "tests"
                / "test_pricing.py"
            ).write_text(
                "def test_price(): pass\n",
                encoding="utf-8",
            )

            repo_map = build_repo_map(
                repo
            )

            selected = select_relevant_files(
                repo=repo,
                repo_map=repo_map,
                task_text=(
                    "authentication timeout"
                ),
            )

            associations = (
                find_test_associations(
                    repo_map=repo_map,
                    selected=selected,
                )
            )

            self.assertEqual(
                associations,
                (),
            )

    def test_association_is_deterministic(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (repo / "src").mkdir()
            (repo / "tests").mkdir()

            (
                repo
                / "src"
                / "auth.py"
            ).write_text(
                "authentication auth\n",
                encoding="utf-8",
            )

            (
                repo
                / "tests"
                / "test_auth.py"
            ).write_text(
                "auth\n",
                encoding="utf-8",
            )

            repo_map = build_repo_map(
                repo
            )

            selected = select_relevant_files(
                repo=repo,
                repo_map=repo_map,
                task_text="auth",
            )

            first = find_test_associations(
                repo_map=repo_map,
                selected=selected,
            )

            second = find_test_associations(
                repo_map=repo_map,
                selected=selected,
            )

            self.assertEqual(
                first,
                second,
            )


if __name__ == "__main__":
    unittest.main()
