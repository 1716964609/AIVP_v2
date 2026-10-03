import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from aivp.context import (
    ContextBudget,
    ContextRequest,
    compile_context,
)
from aivp.context.repo_map import (
    build_repo_map,
)


class ContextCompilerRepoMapTests(
    unittest.TestCase
):
    def setUp(self):
        self.tempdir = (
            tempfile.TemporaryDirectory()
        )

        self.repo = Path(
            self.tempdir.name
        )

        (
            self.repo / "target.py"
        ).write_text(
            "def target_function():\n"
            "    return 1\n",
            encoding="utf-8",
        )

        tests = self.repo / "tests"
        tests.mkdir()

        (
            tests / "test_target.py"
        ).write_text(
            "def test_target_function():\n"
            "    assert True\n",
            encoding="utf-8",
        )

        self.request = ContextRequest(
            repo=self.repo,
            task_text=(
                "Change target_function"
            ),
            budget=ContextBudget(
                max_files=10,
                max_chars=20_000,
            ),
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_precomputed_repo_map_matches_default(
        self,
    ):
        repo_map = build_repo_map(
            self.repo
        )

        default = compile_context(
            self.request
        )

        precomputed = compile_context(
            self.request,
            repo_map=repo_map,
        )

        self.assertEqual(
            precomputed.artifact,
            default.artifact,
        )
        self.assertEqual(
            precomputed.manifest_json,
            default.manifest_json,
        )

    def test_precomputed_repo_map_skips_builder(
        self,
    ):
        repo_map = build_repo_map(
            self.repo
        )

        with patch(
            (
                "aivp.context.compiler."
                "build_repo_map"
            ),
            side_effect=AssertionError(
                "builder must not run"
            ),
        ):
            result = compile_context(
                self.request,
                repo_map=repo_map,
            )

        self.assertTrue(
            result.artifact.entries
        )


if __name__ == "__main__":
    unittest.main()
