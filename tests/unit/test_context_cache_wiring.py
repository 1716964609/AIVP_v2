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

    def test_second_compilation_hits_repo_map_cache(
        self,
    ):
        (
            first,
            first_cache,
        ) = _compile_context_with_cache(
            self.request,
            cache_root=self.cache_root,
        )

        self.assertIsNotNone(
            first_cache
        )
        self.assertFalse(
            first_cache.cache_hit
        )

        with patch(
            (
                "aivp.cache.repo_map."
                "build_repo_map"
            ),
            side_effect=AssertionError(
                "repo map builder "
                "must not run"
            ),
        ):
            (
                second,
                second_cache,
            ) = (
                _compile_context_with_cache(
                    self.request,
                    cache_root=(
                        self.cache_root
                    ),
                )
            )

        self.assertIsNotNone(
            second_cache
        )
        self.assertTrue(
            second_cache.cache_hit
        )

        self.assertEqual(
            first.artifact,
            second.artifact,
        )

        self.assertEqual(
            first.manifest_json,
            second.manifest_json,
        )

    def test_new_commit_invalidates_repo_map_cache(
        self,
    ):
        (
            _,
            first_cache,
        ) = _compile_context_with_cache(
            self.request,
            cache_root=self.cache_root,
        )

        self.assertFalse(
            first_cache.cache_hit
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
            second_cache,
        ) = _compile_context_with_cache(
            self.request,
            cache_root=self.cache_root,
        )

        self.assertFalse(
            second_cache.cache_hit
        )

        self.assertNotEqual(
            first_cache.cache_key,
            second_cache.cache_key,
        )

    def test_cache_can_be_disabled(
        self,
    ):
        (
            compilation,
            cache_result,
        ) = _compile_context_with_cache(
            self.request,
            cache_root=None,
        )

        self.assertIsNone(
            cache_result
        )

        self.assertTrue(
            compilation.artifact.entries
        )


if __name__ == "__main__":
    unittest.main()
