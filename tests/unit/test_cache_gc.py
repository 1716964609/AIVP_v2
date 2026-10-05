from __future__ import annotations

import os
import tempfile
import unittest

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

from aivp.cache.cas import (
    ContentAddressedCache,
)
from aivp.cache.index import (
    SQLiteCacheIndex,
)
from aivp.maintenance.cache_gc import (
    cleanup_cache,
)
from aivp.state.hashing import (
    sha256_text,
)


NOW = datetime(
    2026,
    10,
    5,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)

CUTOFF = 7 * 24 * 60 * 60


def key(seed: str) -> str:
    return sha256_text(seed)


def set_entry_time(
    index: SQLiteCacheIndex,
    *,
    namespace: str,
    cache_key: str,
    created_at: datetime,
) -> None:
    index.connection.execute(
        """
        UPDATE cache_entries
        SET created_at = ?
        WHERE namespace = ?
          AND cache_key = ?
        """,
        (
            created_at.isoformat(),
            namespace,
            cache_key,
        ),
    )

    index.connection.commit()


def set_old_mtime(
    path: Path,
) -> None:
    timestamp = (
        NOW
        - timedelta(
            days=30
        )
    ).timestamp()

    os.utime(
        path,
        (
            timestamp,
            timestamp,
        ),
    )


class CacheGCTests(unittest.TestCase):
    def make_cache(
        self,
        root: Path,
    ):
        index = SQLiteCacheIndex(
            root / "cache.sqlite"
        )

        cas = ContentAddressedCache(
            root
        )

        return index, cas

    def test_dry_run_removes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, cas = self.make_cache(root)

            obj = cas.put_text(
                "expired"
            )

            cache_key = key(
                "expired-key"
            )

            index.put(
                namespace="context",
                cache_key=cache_key,
                object_sha256=obj.sha256,
                metadata={},
            )

            set_entry_time(
                index,
                namespace="context",
                cache_key=cache_key,
                created_at=(
                    NOW
                    - timedelta(
                        days=30
                    )
                ),
            )

            set_old_mtime(
                obj.path
            )

            index.connection.close()

            results = cleanup_cache(
                cache_root=root,
                older_than_seconds=CUTOFF,
                dry_run=True,
                now=NOW,
            )

            check = SQLiteCacheIndex(
                root / "cache.sqlite"
            )

            self.assertIsNotNone(
                check.get(
                    namespace="context",
                    cache_key=cache_key,
                )
            )

            check.connection.close()

            self.assertTrue(
                obj.path.exists()
            )

            self.assertTrue(
                any(
                    item.kind == "index-entry"
                    and not item.removed
                    for item in results
                )
            )

    def test_expired_entry_and_orphan_cas_are_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, cas = self.make_cache(root)

            obj = cas.put_text(
                "expired"
            )

            cache_key = key(
                "expired-key"
            )

            index.put(
                namespace="context",
                cache_key=cache_key,
                object_sha256=obj.sha256,
                metadata={},
            )

            set_entry_time(
                index,
                namespace="context",
                cache_key=cache_key,
                created_at=(
                    NOW
                    - timedelta(
                        days=30
                    )
                ),
            )

            set_old_mtime(
                obj.path
            )

            index.connection.close()

            cleanup_cache(
                cache_root=root,
                older_than_seconds=CUTOFF,
                dry_run=False,
                now=NOW,
            )

            check = SQLiteCacheIndex(
                root / "cache.sqlite"
            )

            self.assertIsNone(
                check.get(
                    namespace="context",
                    cache_key=cache_key,
                )
            )

            check.connection.close()

            self.assertFalse(
                obj.path.exists()
            )

    def test_surviving_reference_protects_shared_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, cas = self.make_cache(root)

            obj = cas.put_text(
                "shared"
            )

            old_key = key(
                "old"
            )

            new_key = key(
                "new"
            )

            index.put(
                namespace="context",
                cache_key=old_key,
                object_sha256=obj.sha256,
                metadata={},
            )

            index.put(
                namespace="repo-map",
                cache_key=new_key,
                object_sha256=obj.sha256,
                metadata={},
            )

            set_entry_time(
                index,
                namespace="context",
                cache_key=old_key,
                created_at=(
                    NOW
                    - timedelta(
                        days=30
                    )
                ),
            )

            set_entry_time(
                index,
                namespace="repo-map",
                cache_key=new_key,
                created_at=(
                    NOW
                    - timedelta(
                        days=1
                    )
                ),
            )

            set_old_mtime(
                obj.path
            )

            index.connection.close()

            cleanup_cache(
                cache_root=root,
                older_than_seconds=CUTOFF,
                dry_run=False,
                now=NOW,
            )

            check = SQLiteCacheIndex(
                root / "cache.sqlite"
            )

            self.assertIsNone(
                check.get(
                    namespace="context",
                    cache_key=old_key,
                )
            )

            self.assertIsNotNone(
                check.get(
                    namespace="repo-map",
                    cache_key=new_key,
                )
            )

            check.connection.close()

            self.assertTrue(
                obj.path.exists()
            )

    def test_recent_unreferenced_cas_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, cas = self.make_cache(root)

            obj = cas.put_text(
                "recent-orphan"
            )

            index.connection.close()

            cleanup_cache(
                cache_root=root,
                older_than_seconds=CUTOFF,
                dry_run=False,
                now=NOW,
            )

            self.assertTrue(
                obj.path.exists()
            )

    def test_old_unreferenced_cas_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, cas = self.make_cache(root)

            obj = cas.put_text(
                "old-orphan"
            )

            set_old_mtime(
                obj.path
            )

            index.connection.close()

            cleanup_cache(
                cache_root=root,
                older_than_seconds=CUTOFF,
                dry_run=False,
                now=NOW,
            )

            self.assertFalse(
                obj.path.exists()
            )

    def test_unexpected_cas_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, _ = self.make_cache(root)

            strange_dir = (
                root / "sha256" / "aa"
            )

            strange_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            strange = (
                strange_dir
                / "not-a-valid-digest"
            )

            strange.write_text(
                "foreign",
                encoding="utf-8",
            )

            set_old_mtime(
                strange
            )

            index.connection.close()

            cleanup_cache(
                cache_root=root,
                older_than_seconds=CUTOFF,
                dry_run=False,
                now=NOW,
            )

            self.assertTrue(
                strange.exists()
            )

    def test_stale_temp_file_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, _ = self.make_cache(root)

            prefix = (
                root / "sha256" / "aa"
            )

            prefix.mkdir(
                parents=True,
                exist_ok=True,
            )

            stale = (
                prefix
                / ".aivp-cache-interrupted"
            )

            stale.write_text(
                "partial",
                encoding="utf-8",
            )

            set_old_mtime(
                stale
            )

            index.connection.close()

            cleanup_cache(
                cache_root=root,
                older_than_seconds=CUTOFF,
                dry_run=False,
                now=NOW,
            )

            self.assertFalse(
                stale.exists()
            )

    def test_gc_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, cas = self.make_cache(root)

            obj = cas.put_text(
                "orphan"
            )

            set_old_mtime(
                obj.path
            )

            index.connection.close()

            first = cleanup_cache(
                cache_root=root,
                older_than_seconds=CUTOFF,
                dry_run=False,
                now=NOW,
            )

            second = cleanup_cache(
                cache_root=root,
                older_than_seconds=CUTOFF,
                dry_run=False,
                now=NOW,
            )

            self.assertTrue(
                any(
                    item.removed
                    for item in first
                )
            )

            self.assertFalse(
                any(
                    item.removed
                    for item in second
                )
            )


if __name__ == "__main__":
    unittest.main()
