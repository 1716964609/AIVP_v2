import json
import tempfile
import unittest

from pathlib import Path

from aivp.cache import (
    ContentAddressedCache,
    ContextSelectionCache,
    SQLiteCacheIndex,
    context_cache_identity,
)
from aivp.context import (
    COMPILER_VERSION,
    ContextBudget,
    ContextRequest,
    compile_context,
)
from aivp.errors import (
    StateIntegrityError,
)


class ContextSelectionCacheTests(
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
            self.repo / "target.py"
        ).write_text(
            "def target_function():\n"
            "    return 1\n",
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

        self.identity = (
            context_cache_identity(
                repo_sha="abc123",
                task_text=(
                    self.request.task_text
                ),
                compiler_version=(
                    COMPILER_VERSION
                ),
                max_files=(
                    self.request
                    .budget
                    .max_files
                ),
                max_chars=(
                    self.request
                    .budget
                    .max_chars
                ),
            )
        )

        self.cas = (
            ContentAddressedCache(
                self.root / "cache"
            )
        )

        self.index = (
            SQLiteCacheIndex(
                self.root
                / "cache.sqlite"
            )
        )

        self.cache = (
            ContextSelectionCache(
                cas=self.cas,
                index=self.index,
            )
        )

    def tearDown(self):
        self.index.close()
        self.tempdir.cleanup()

    def test_missing_entry_is_cache_miss(
        self,
    ):
        result = self.cache.get(
            identity=self.identity
        )

        self.assertIsNone(
            result
        )

    def test_put_and_get_round_trip(
        self,
    ):
        compilation = compile_context(
            self.request
        )

        stored = self.cache.put(
            identity=self.identity,
            compilation=compilation,
        )

        self.assertFalse(
            stored.cache_hit
        )

        cached = self.cache.get(
            identity=self.identity
        )

        self.assertIsNotNone(
            cached
        )
        self.assertTrue(
            cached.cache_hit
        )
        self.assertEqual(
            cached.compilation,
            compilation,
        )
        self.assertEqual(
            cached.object_sha256,
            stored.object_sha256,
        )

    def test_task_change_is_cache_miss(
        self,
    ):
        compilation = compile_context(
            self.request
        )

        self.cache.put(
            identity=self.identity,
            compilation=compilation,
        )

        other_identity = (
            context_cache_identity(
                repo_sha="abc123",
                task_text=(
                    "Change another thing"
                ),
                compiler_version=(
                    COMPILER_VERSION
                ),
                max_files=10,
                max_chars=20_000,
            )
        )

        self.assertIsNone(
            self.cache.get(
                identity=(
                    other_identity
                )
            )
        )

    def test_budget_change_is_cache_miss(
        self,
    ):
        compilation = compile_context(
            self.request
        )

        self.cache.put(
            identity=self.identity,
            compilation=compilation,
        )

        other_identity = (
            context_cache_identity(
                repo_sha="abc123",
                task_text=(
                    self.request.task_text
                ),
                compiler_version=(
                    COMPILER_VERSION
                ),
                max_files=9,
                max_chars=20_000,
            )
        )

        self.assertIsNone(
            self.cache.get(
                identity=(
                    other_identity
                )
            )
        )

    def test_stale_metadata_fails_closed(
        self,
    ):
        compilation = compile_context(
            self.request
        )

        stored = self.cache.put(
            identity=self.identity,
            compilation=compilation,
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
                        "identity": {
                            "stale": True
                        },
                        "manifest_hash": (
                            compilation
                            .artifact
                            .manifest_hash
                        ),
                    }
                ),
                "context-selection",
                stored.cache_key,
            ),
        )

        self.index.connection.commit()

        with self.assertRaises(
            StateIntegrityError
        ):
            self.cache.get(
                identity=self.identity
            )

    def test_stale_payload_fails_closed(
        self,
    ):
        compilation = compile_context(
            self.request
        )

        stored = self.cache.put(
            identity=self.identity,
            compilation=compilation,
        )

        stale_payload = {
            "version": "1.0.0",
            "cache_key": (
                self.identity.key
            ),
            "identity": {
                **self.identity.payload(),
                "repo_sha": "stale-sha",
            },
            "artifact": {},
            "manifest_json": "{}",
        }

        stale_object = (
            self.cas.put_text(
                json.dumps(
                    stale_payload,
                    sort_keys=True,
                    separators=(",", ":"),
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
                "context-selection",
                stored.cache_key,
            ),
        )

        self.index.connection.commit()

        with self.assertRaises(
            StateIntegrityError
        ):
            self.cache.get(
                identity=self.identity
            )

    def test_corrupt_context_content_fails_closed(
        self,
    ):
        compilation = compile_context(
            self.request
        )

        stored = self.cache.put(
            identity=self.identity,
            compilation=compilation,
        )

        original = self.cas.get_text(
            stored.object_sha256
        )

        payload = json.loads(
            original
        )

        payload[
            "artifact"
        ][
            "entries"
        ][0][
            "content"
        ] = "tampered"

        tampered = (
            self.cas.put_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
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
                tampered.sha256,
                "context-selection",
                stored.cache_key,
            ),
        )

        self.index.connection.commit()

        with self.assertRaises(
            StateIntegrityError
        ):
            self.cache.get(
                identity=self.identity
            )


if __name__ == "__main__":
    unittest.main()
