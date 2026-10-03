from __future__ import annotations

import json
import re
import sqlite3

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from aivp.errors import (
    StateIntegrityError,
)


INDEX_SCHEMA_VERSION = 1

_DIGEST_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS cache_entries(
    namespace TEXT NOT NULL,
    cache_key TEXT NOT NULL,
    object_sha256 TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(namespace, cache_key)
);

CREATE INDEX IF NOT EXISTS
idx_cache_entries_object_sha256
ON cache_entries(object_sha256);
"""


def _now_iso() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )


@dataclass(frozen=True)
class CacheIndexEntry:
    namespace: str
    cache_key: str
    object_sha256: str
    metadata: Mapping[str, Any]
    created_at: str


class SQLiteCacheIndex:
    def __init__(
        self,
        path: Path,
    ):
        self.path = (
            path.expanduser()
        )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )

        connection = sqlite3.connect(
            str(self.path)
        )

        self.connection = connection

        try:
            self.connection.row_factory = (
                sqlite3.Row
            )

            self.connection.execute(
                "PRAGMA journal_mode=WAL"
            )

            self._migrate()

        except BaseException:
            connection.close()
            raise

    def put(
        self,
        *,
        namespace: str,
        cache_key: str,
        object_sha256: str,
        metadata: Mapping[
            str,
            Any,
        ],
    ) -> CacheIndexEntry:
        self._validate_identity(
            namespace=namespace,
            cache_key=cache_key,
            object_sha256=(
                object_sha256
            ),
        )

        metadata_json = json.dumps(
            dict(metadata),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        created_at = _now_iso()

        self.connection.execute(
            """
            INSERT INTO cache_entries(
                namespace,
                cache_key,
                object_sha256,
                metadata_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(
                namespace,
                cache_key
            )
            DO UPDATE SET
                object_sha256 =
                    excluded.object_sha256,
                metadata_json =
                    excluded.metadata_json,
                created_at =
                    excluded.created_at
            """,
            (
                namespace,
                cache_key,
                object_sha256,
                metadata_json,
                created_at,
            ),
        )

        self.connection.commit()

        return CacheIndexEntry(
            namespace=namespace,
            cache_key=cache_key,
            object_sha256=(
                object_sha256
            ),
            metadata=dict(
                metadata
            ),
            created_at=created_at,
        )

    def get(
        self,
        *,
        namespace: str,
        cache_key: str,
    ) -> Optional[CacheIndexEntry]:
        self._validate_name(
            "namespace",
            namespace,
        )

        self._validate_digest(
            "cache_key",
            cache_key,
        )

        row = self.connection.execute(
            """
            SELECT
                namespace,
                cache_key,
                object_sha256,
                metadata_json,
                created_at
            FROM cache_entries
            WHERE namespace = ?
              AND cache_key = ?
            """,
            (
                namespace,
                cache_key,
            ),
        ).fetchone()

        if row is None:
            return None

        self._validate_digest(
            "object_sha256",
            row["object_sha256"],
        )

        try:
            metadata = json.loads(
                row["metadata_json"]
            )
        except (
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            raise StateIntegrityError(
                "Cache metadata JSON "
                "is invalid"
            ) from exc

        if not isinstance(
            metadata,
            dict,
        ):
            raise StateIntegrityError(
                "Cache metadata must "
                "be an object"
            )

        return CacheIndexEntry(
            namespace=row[
                "namespace"
            ],
            cache_key=row[
                "cache_key"
            ],
            object_sha256=row[
                "object_sha256"
            ],
            metadata=metadata,
            created_at=row[
                "created_at"
            ],
        )

    def delete(
        self,
        *,
        namespace: str,
        cache_key: str,
    ) -> None:
        self._validate_name(
            "namespace",
            namespace,
        )

        self._validate_digest(
            "cache_key",
            cache_key,
        )

        self.connection.execute(
            """
            DELETE FROM cache_entries
            WHERE namespace = ?
              AND cache_key = ?
            """,
            (
                namespace,
                cache_key,
            ),
        )

        self.connection.commit()

    def _migrate(self) -> None:
        version = self.connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

        if version > (
            INDEX_SCHEMA_VERSION
        ):
            raise RuntimeError(
                "Cache index schema "
                f"version {version} is "
                "newer than supported "
                f"{INDEX_SCHEMA_VERSION}"
            )

        if version < 1:
            self.connection.executescript(
                MIGRATION_1
            )

            self.connection.execute(
                "PRAGMA user_version = 1"
            )

            self.connection.commit()

    @staticmethod
    def _validate_name(
        name: str,
        value: str,
    ) -> None:
        if (
            not isinstance(
                value,
                str,
            )
            or not value.strip()
        ):
            raise StateIntegrityError(
                f"{name} must be a "
                "non-empty string"
            )

    @staticmethod
    def _validate_digest(
        name: str,
        value: str,
    ) -> None:
        if (
            not isinstance(
                value,
                str,
            )
            or _DIGEST_RE.fullmatch(
                value
            )
            is None
        ):
            raise StateIntegrityError(
                f"Invalid {name}"
            )

    @classmethod
    def _validate_identity(
        cls,
        *,
        namespace: str,
        cache_key: str,
        object_sha256: str,
    ) -> None:
        cls._validate_name(
            "namespace",
            namespace,
        )

        cls._validate_digest(
            "cache_key",
            cache_key,
        )

        cls._validate_digest(
            "object_sha256",
            object_sha256,
        )

    def close(self) -> None:
        self.connection.close()

    def __enter__(
        self,
    ) -> "SQLiteCacheIndex":
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        self.close()
