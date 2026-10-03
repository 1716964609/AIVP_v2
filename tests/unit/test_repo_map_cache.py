import json
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from aivp.cache import (
    ContentAddressedCache,
    RepoMapCache,
    SQLiteCacheIndex,
)
from aivp.context.repo_map import (
    build_repo_map,
)
from aivp.errors import (
    StateIntegrityError,
)


class RepoMapCacheTests(
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

        (
            self.repo / "app.py"
        ).write_text(
            "print('hello')\n",
            encoding="utf-8",
        )

        tests = (
            self.repo / "tests"
        )
        tests.mkdir()

        (
            tests / "test_app.py"
        ).write_text(
            "def test_app(): pass\n",
            encoding="utf-8",
        )

        self.cas = (
            ContentAddressedCache(
                self.root / "cache"
            )
        )

        self.index = (
            SQLiteCacheIndex(
                self.root
                / "cache-index.sqlite"
            )
        )

        self.cache = RepoMapCache(
            cas=self.cas,
            index=self.index,
        )

        self.repo_sha = "abc123"

    def tearDown(self):
        self.index.close()
        self.tempdir.cleanup()

    def test_first_call_is_miss_and_matches_builder(
        self,
    ):
        expected = build_repo_map(
            self.repo
        )

        result = (
            self.cache.get_or_build(
                repo=self.repo,
                repo_sha=(
                    self.repo_sha
                ),
            )
        )

        self.assertFalse(
            result.cache_hit
        )
        self.assertEqual(
            result.entries,
            expected,
        )

    def test_second_call_hits_and_skips_builder(
        self,
    ):
        first = (
            self.cache.get_or_build(
                repo=self.repo,
                repo_sha=(
                    self.repo_sha
                ),
            )
        )

        self.assertFalse(
            first.cache_hit
        )

        with patch(
            (
                "aivp.cache.repo_map."
                "build_repo_map"
            ),
            side_effect=AssertionError(
                "builder must not run"
            ),
        ):
            second = (
                self.cache.get_or_build(
                    repo=self.repo,
                    repo_sha=(
                        self.repo_sha
                    ),
                )
            )

        self.assertTrue(
            second.cache_hit
        )
        self.assertEqual(
            second.entries,
            first.entries,
        )
        self.assertEqual(
            second.object_sha256,
            first.object_sha256,
        )

    def test_repo_sha_change_is_miss(
        self,
    ):
        first = (
            self.cache.get_or_build(
                repo=self.repo,
                repo_sha="sha-one",
            )
        )

        second = (
            self.cache.get_or_build(
                repo=self.repo,
                repo_sha="sha-two",
            )
        )

        self.assertFalse(
            first.cache_hit
        )
        self.assertFalse(
            second.cache_hit
        )
        self.assertNotEqual(
            first.cache_key,
            second.cache_key,
        )

    def test_stale_metadata_fails_closed(
        self,
    ):
        result = (
            self.cache.get_or_build(
                repo=self.repo,
                repo_sha=(
                    self.repo_sha
                ),
            )
        )

        self.index.connection.execute(
            """
            UPDATE cache_entries
            SET metadata_json = ?
            WHERE namespace = ?
              AND cache_key = ?
            """,
            (
                json.dumps(
                    {
                        "version": (
                            "1.0.0"
                        ),
                        "repo_sha": (
                            "stale-sha"
                        ),
                        "entry_count": 2,
                    }
                ),
                "repo-map",
                result.cache_key,
            ),
        )

        self.index.connection.commit()

        with self.assertRaises(
            StateIntegrityError
        ):
            self.cache.get_or_build(
                repo=self.repo,
                repo_sha=(
                    self.repo_sha
                ),
            )

    def test_stale_payload_fails_closed(
        self,
    ):
        result = (
            self.cache.get_or_build(
                repo=self.repo,
                repo_sha=(
                    self.repo_sha
                ),
            )
        )

        stale_object = (
            self.cas.put_text(
                json.dumps(
                    {
                        "version": (
                            "1.0.0"
                        ),
                        "repo_sha": (
                            "stale-sha"
                        ),
                        "entries": [],
                    },
                    sort_keys=True,
                    separators=(
                        ",",
                        ":",
                    ),
                )
            )
        )

        self.index.connection.execute(
            """
            UPDATE cache_entries
            SET object_sha256 = ?
            WHERE namespace = ?
              AND cache_key = ?
            """,
            (
                stale_object.sha256,
                "repo-map",
                result.cache_key,
            ),
        )

        self.index.connection.commit()

        with self.assertRaises(
            StateIntegrityError
        ):
            self.cache.get_or_build(
                repo=self.repo,
                repo_sha=(
                    self.repo_sha
                ),
            )

    def test_missing_cas_object_rebuilds(
        self,
    ):
        first = (
            self.cache.get_or_build(
                repo=self.repo,
                repo_sha=(
                    self.repo_sha
                ),
            )
        )

        first_path = (
            self.cas.path_for(
                first.object_sha256
            )
        )

        first_path.unlink()

        second = (
            self.cache.get_or_build(
                repo=self.repo,
                repo_sha=(
                    self.repo_sha
                ),
            )
        )

        self.assertFalse(
            second.cache_hit
        )
        self.assertEqual(
            second.entries,
            first.entries,
        )


if __name__ == "__main__":
    unittest.main()
