import sqlite3
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from aivp.cache import (
    SQLiteCacheIndex,
)
from aivp.errors import (
    StateIntegrityError,
)


class SQLiteCacheIndexTests(
    unittest.TestCase
):
    def setUp(self):
        self.tempdir = (
            tempfile.TemporaryDirectory()
        )

        self.path = (
            Path(self.tempdir.name)
            / "cache.sqlite"
        )

        self.index = (
            SQLiteCacheIndex(
                self.path
            )
        )

        self.key = "a" * 64
        self.object_sha = "b" * 64

    def tearDown(self):
        self.index.close()
        self.tempdir.cleanup()

    def test_missing_entry_is_cache_miss(
        self,
    ):
        result = self.index.get(
            namespace="repo-map",
            cache_key=self.key,
        )

        self.assertIsNone(
            result
        )

    def test_put_and_get_round_trip(
        self,
    ):
        self.index.put(
            namespace="repo-map",
            cache_key=self.key,
            object_sha256=(
                self.object_sha
            ),
            metadata={
                "repo_sha": "abc123",
                "version": "1.0.0",
            },
        )

        result = self.index.get(
            namespace="repo-map",
            cache_key=self.key,
        )

        self.assertIsNotNone(
            result
        )
        self.assertEqual(
            result.namespace,
            "repo-map",
        )
        self.assertEqual(
            result.cache_key,
            self.key,
        )
        self.assertEqual(
            result.object_sha256,
            self.object_sha,
        )
        self.assertEqual(
            result.metadata,
            {
                "repo_sha": "abc123",
                "version": "1.0.0",
            },
        )

    def test_same_logical_key_updates_mapping(
        self,
    ):
        self.index.put(
            namespace="repo-map",
            cache_key=self.key,
            object_sha256="b" * 64,
            metadata={"revision": 1},
        )

        self.index.put(
            namespace="repo-map",
            cache_key=self.key,
            object_sha256="c" * 64,
            metadata={"revision": 2},
        )

        result = self.index.get(
            namespace="repo-map",
            cache_key=self.key,
        )

        self.assertEqual(
            result.object_sha256,
            "c" * 64,
        )
        self.assertEqual(
            result.metadata,
            {"revision": 2},
        )

    def test_namespaces_are_independent(
        self,
    ):
        self.index.put(
            namespace="repo-map",
            cache_key=self.key,
            object_sha256="b" * 64,
            metadata={},
        )

        self.index.put(
            namespace="context",
            cache_key=self.key,
            object_sha256="c" * 64,
            metadata={},
        )

        repo_entry = self.index.get(
            namespace="repo-map",
            cache_key=self.key,
        )

        context_entry = self.index.get(
            namespace="context",
            cache_key=self.key,
        )

        self.assertEqual(
            repo_entry.object_sha256,
            "b" * 64,
        )
        self.assertEqual(
            context_entry.object_sha256,
            "c" * 64,
        )

    def test_delete_removes_entry(self):
        self.index.put(
            namespace="repo-map",
            cache_key=self.key,
            object_sha256=(
                self.object_sha
            ),
            metadata={},
        )

        self.index.delete(
            namespace="repo-map",
            cache_key=self.key,
        )

        self.assertIsNone(
            self.index.get(
                namespace="repo-map",
                cache_key=self.key,
            )
        )

    def test_invalid_digest_fails_closed(
        self,
    ):
        with self.assertRaises(
            StateIntegrityError
        ):
            self.index.put(
                namespace="repo-map",
                cache_key="not-a-hash",
                object_sha256=(
                    self.object_sha
                ),
                metadata={},
            )

        with self.assertRaises(
            StateIntegrityError
        ):
            self.index.put(
                namespace="repo-map",
                cache_key=self.key,
                object_sha256=(
                    "not-a-hash"
                ),
                metadata={},
            )

    def test_corrupt_metadata_fails_closed(
        self,
    ):
        self.index.put(
            namespace="repo-map",
            cache_key=self.key,
            object_sha256=(
                self.object_sha
            ),
            metadata={"ok": True},
        )

        self.index.connection.execute(
            """
            UPDATE cache_entries
            SET metadata_json = ?
            WHERE namespace = ?
              AND cache_key = ?
            """,
            (
                "{not-json",
                "repo-map",
                self.key,
            ),
        )

        self.index.connection.commit()

        with self.assertRaises(
            StateIntegrityError
        ):
            self.index.get(
                namespace="repo-map",
                cache_key=self.key,
            )

    def test_schema_version_is_set(self):
        version = (
            self.index.connection
            .execute(
                "PRAGMA user_version"
            )
            .fetchone()[0]
        )

        self.assertEqual(
            version,
            1,
        )

    def test_constructor_failure_closes_connection(
        self,
    ):
        captured = []

        real_connect = (
            sqlite3.connect
        )

        def tracking_connect(
            *args,
            **kwargs,
        ):
            connection = real_connect(
                *args,
                **kwargs,
            )

            captured.append(
                connection
            )

            return connection

        failure_path = (
            Path(self.tempdir.name)
            / "failure.sqlite"
        )

        with patch(
            (
                "aivp.cache.index."
                "sqlite3.connect"
            ),
            side_effect=(
                tracking_connect
            ),
        ):
            with patch.object(
                SQLiteCacheIndex,
                "_migrate",
                side_effect=RuntimeError(
                    "migration failed"
                ),
            ):
                with self.assertRaises(
                    RuntimeError
                ):
                    SQLiteCacheIndex(
                        failure_path
                    )

        self.assertEqual(
            len(captured),
            1,
        )

        with self.assertRaises(
            sqlite3.ProgrammingError
        ):
            captured[0].execute(
                "SELECT 1"
            )


    def test_newer_schema_is_rejected(
        self,
    ):
        other_path = (
            Path(self.tempdir.name)
            / "future.sqlite"
        )

        connection = (
            sqlite3.connect(
                str(other_path)
            )
        )

        connection.execute(
            "PRAGMA user_version = 999"
        )

        connection.close()

        with self.assertRaises(
            RuntimeError
        ):
            SQLiteCacheIndex(
                other_path
            )


if __name__ == "__main__":
    unittest.main()
