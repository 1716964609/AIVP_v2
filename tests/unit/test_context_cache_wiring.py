import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from aivp.context import (
    ContextBudget,
    ContextRequest,
)
from aivp.panel.orchestrator import (
    _compile_context_with_cache,
)
from aivp.repository.git import git


class ContextCacheWiringTests(
    unittest.TestCase
):
    def setUp(self):
        self.tempdir = (
            tempfile.TemporaryDirectory()
        )

        self.root = Path(
            self.tempdir.name
        )

        self.repo = (
            self.root / "repo"
        )
        self.repo.mkdir()

        git(
            self.repo,
            "init",
        )

        git(
            self.repo,
            "config",
            "user.email",
            "test@example.com",
        )

        git(
            self.repo,
            "config",
            "user.name",
            "AIVP Test",
        )

        (
            self.repo / "target.py"
        ).write_text(
            "def target_function():\n"
            "    return 1\n",
            encoding="utf-8",
        )

        git(
            self.repo,
            "add",
            ".",
        )

        git(
            self.repo,
            "commit",
            "-m",
            "initial",
        )

        self.cache_root = (
            self.root / "cache"
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

    def test_second_compilation_hits_context_cache_and_skips_compiler(
        self,
    ):
        (
            first,
            first_context,
            first_repo_map,
        ) = _compile_context_with_cache(
            self.request,
            cache_root=self.cache_root,
        )

        self.assertFalse(
            first_context.cache_hit
        )

        self.assertFalse(
            first_repo_map.cache_hit
        )

        with (
            patch(
                (
                    "aivp.panel."
                    "orchestrator."
                    "compile_context"
                ),
                side_effect=AssertionError(
                    "compiler must not run"
                ),
            ),
            patch(
                (
                    "aivp.panel."
                    "orchestrator."
                    "RepoMapCache."
                    "get_or_build"
                ),
                side_effect=AssertionError(
                    "repo map cache "
                    "must not run"
                ),
            ),
        ):
            (
                second,
                second_context,
                second_repo_map,
            ) = (
                _compile_context_with_cache(
                    self.request,
                    cache_root=(
                        self.cache_root
                    ),
                )
            )

        self.assertTrue(
            second_context.cache_hit
        )

        self.assertIsNone(
            second_repo_map
        )

        self.assertEqual(
            second,
            first,
        )

    def test_task_change_misses_context_but_hits_repo_map(
        self,
    ):
        (
            _,
            first_context,
            first_repo_map,
        ) = _compile_context_with_cache(
            self.request,
            cache_root=self.cache_root,
        )

        self.assertFalse(
            first_context.cache_hit
        )

        self.assertFalse(
            first_repo_map.cache_hit
        )

        other_request = ContextRequest(
            repo=self.repo,
            task_text=(
                "Change another_function"
            ),
            budget=(
                self.request.budget
            ),
        )

        (
            _,
            second_context,
            second_repo_map,
        ) = _compile_context_with_cache(
            other_request,
            cache_root=self.cache_root,
        )

        self.assertFalse(
            second_context.cache_hit
        )

        self.assertTrue(
            second_repo_map.cache_hit
        )

    def test_new_commit_invalidates_both_cache_layers(
        self,
    ):
        (
            _,
            first_context,
            first_repo_map,
        ) = _compile_context_with_cache(
            self.request,
            cache_root=self.cache_root,
        )

        self.assertFalse(
            first_context.cache_hit
        )

        self.assertFalse(
            first_repo_map.cache_hit
        )

        (
            self.repo / "new_file.py"
        ).write_text(
            "VALUE = 2\n",
            encoding="utf-8",
        )

        git(
            self.repo,
            "add",
            ".",
        )

        git(
            self.repo,
            "commit",
            "-m",
            "change repository",
        )

        (
            _,
            second_context,
            second_repo_map,
        ) = _compile_context_with_cache(
            self.request,
            cache_root=self.cache_root,
        )

        self.assertFalse(
            second_context.cache_hit
        )

        self.assertFalse(
            second_repo_map.cache_hit
        )

        self.assertNotEqual(
            first_context.cache_key,
            second_context.cache_key,
        )

        self.assertNotEqual(
            first_repo_map.cache_key,
            second_repo_map.cache_key,
        )

    def test_cache_can_be_disabled(
        self,
    ):
        (
            compilation,
            context_result,
            repo_map_result,
        ) = _compile_context_with_cache(
            self.request,
            cache_root=None,
        )

        self.assertIsNone(
            context_result
        )

        self.assertIsNone(
            repo_map_result
        )

        self.assertTrue(
            compilation.artifact.entries
        )


if __name__ == "__main__":
    unittest.main()
