from __future__ import annotations

import os
import re
import sqlite3

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from aivp.errors import (
    AIVPError,
    StateIntegrityError,
)


_DIGEST_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

_TEMP_PREFIX = ".aivp-cache-"


@dataclass(frozen=True)
class CacheGCResult:
    kind: str
    resource: str
    removed: bool
    dry_run: bool
    age_seconds: Optional[float]
    reason: str


def _parse_timestamp(
    value: str,
) -> datetime:
    text = value.strip()

    if not text:
        raise StateIntegrityError(
            "Cache created_at is empty"
        )

    try:
        parsed = datetime.fromisoformat(
            text
        )
    except ValueError as exc:
        raise StateIntegrityError(
            "Cache created_at is invalid"
        ) from exc

    if parsed.tzinfo is None:
        raise StateIntegrityError(
            "Cache created_at must include timezone"
        )

    return parsed.astimezone(
        timezone.utc
    )


def _age_seconds(
    *,
    timestamp: datetime,
    now: datetime,
) -> float:
    return (
        now - timestamp
    ).total_seconds()


def _mtime_age_seconds(
    *,
    path: Path,
    now: datetime,
) -> float:
    modified = datetime.fromtimestamp(
        path.lstat().st_mtime,
        tz=timezone.utc,
    )

    return _age_seconds(
        timestamp=modified,
        now=now,
    )


def _load_entries(
    connection: sqlite3.Connection,
) -> list[sqlite3.Row]:
    try:
        rows = connection.execute(
            """
            SELECT
                namespace,
                cache_key,
                object_sha256,
                created_at
            FROM cache_entries
            ORDER BY namespace, cache_key
            """
        ).fetchall()

    except sqlite3.Error as exc:
        raise AIVPError(
            "Cannot read cache index"
        ) from exc

    for row in rows:
        digest = row[
            "object_sha256"
        ]

        if (
            not isinstance(digest, str)
            or _DIGEST_RE.fullmatch(
                digest
            )
            is None
        ):
            raise StateIntegrityError(
                "Cache index contains invalid "
                "object_sha256"
            )

        _parse_timestamp(
            str(row["created_at"])
        )

    return rows


def _scan_cas(
    cache_root: Path,
) -> tuple[
    list[tuple[str, Path]],
    list[Path],
]:
    sha_root = (
        cache_root / "sha256"
    )

    if not sha_root.exists():
        return [], []

    if sha_root.is_symlink():
        raise StateIntegrityError(
            "Cache sha256 root must not be symlink"
        )

    if not sha_root.is_dir():
        raise StateIntegrityError(
            "Cache sha256 root must be directory"
        )

    objects: list[
        tuple[str, Path]
    ] = []

    temp_files: list[Path] = []

    for prefix_dir in sha_root.iterdir():
        if prefix_dir.is_symlink():
            continue

        if not prefix_dir.is_dir():
            continue

        prefix = prefix_dir.name

        if (
            len(prefix) != 2
            or any(
                char not in "0123456789abcdef"
                for char in prefix
            )
        ):
            continue

        for path in prefix_dir.iterdir():
            if path.is_symlink():
                continue

            if not path.is_file():
                continue

            name = path.name

            if name.startswith(
                _TEMP_PREFIX
            ):
                temp_files.append(
                    path
                )
                continue

            if (
                _DIGEST_RE.fullmatch(
                    name
                )
                is None
            ):
                continue

            if name[:2] != prefix:
                continue

            objects.append(
                (
                    name,
                    path,
                )
            )

    return objects, temp_files


def cleanup_cache(
    *,
    cache_root: Path,
    older_than_seconds: float,
    dry_run: bool = True,
    now: Optional[datetime] = None,
) -> list[CacheGCResult]:
    if older_than_seconds < 0:
        raise ValueError(
            "older_than_seconds must not be negative"
        )

    current = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    if current.tzinfo is None:
        raise ValueError(
            "now must be timezone-aware"
        )

    current = current.astimezone(
        timezone.utc
    )

    cache_root = (
        cache_root
        .expanduser()
        .resolve()
    )

    if not cache_root.exists():
        return []

    if cache_root.is_symlink():
        raise StateIntegrityError(
            "Cache root must not be symlink"
        )

    if not cache_root.is_dir():
        raise StateIntegrityError(
            "Cache root must be directory"
        )

    index_path = (
        cache_root / "cache.sqlite"
    )

    if not index_path.exists():
        raise AIVPError(
            "Cache index is missing; refusing "
            "CAS garbage collection"
        )

    if index_path.is_symlink():
        raise StateIntegrityError(
            "Cache index must not be symlink"
        )

    connection = sqlite3.connect(
        str(index_path)
    )

    connection.row_factory = (
        sqlite3.Row
    )

    results: list[
        CacheGCResult
    ] = []

    try:
        entries = _load_entries(
            connection
        )

        expired_keys: list[
            tuple[str, str]
        ] = []

        surviving_digests: set[
            str
        ] = set()

        for row in entries:
            created = _parse_timestamp(
                str(row["created_at"])
            )

            age = _age_seconds(
                timestamp=created,
                now=current,
            )

            namespace = str(
                row["namespace"]
            )

            cache_key = str(
                row["cache_key"]
            )

            digest = str(
                row["object_sha256"]
            )

            if age < 0:
                surviving_digests.add(
                    digest
                )

                results.append(
                    CacheGCResult(
                        kind="index-entry",
                        resource=(
                            f"{namespace}:"
                            f"{cache_key}"
                        ),
                        removed=False,
                        dry_run=dry_run,
                        age_seconds=age,
                        reason=(
                            "cache entry timestamp is "
                            "in the future; preserve"
                        ),
                    )
                )
                continue

            if age >= older_than_seconds:
                expired_keys.append(
                    (
                        namespace,
                        cache_key,
                    )
                )

                results.append(
                    CacheGCResult(
                        kind="index-entry",
                        resource=(
                            f"{namespace}:"
                            f"{cache_key}"
                        ),
                        removed=(
                            not dry_run
                        ),
                        dry_run=dry_run,
                        age_seconds=age,
                        reason=(
                            "expired cache index entry "
                            "would be removed"
                            if dry_run
                            else
                            "expired cache index entry "
                            "removed"
                        ),
                    )
                )
            else:
                surviving_digests.add(
                    digest
                )

                results.append(
                    CacheGCResult(
                        kind="index-entry",
                        resource=(
                            f"{namespace}:"
                            f"{cache_key}"
                        ),
                        removed=False,
                        dry_run=dry_run,
                        age_seconds=age,
                        reason=(
                            "cache index entry is still "
                            "within retention"
                        ),
                    )
                )

        if not dry_run:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                for (
                    namespace,
                    cache_key,
                ) in expired_keys:
                    connection.execute(
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

                connection.commit()

            except sqlite3.Error as exc:
                connection.rollback()

                raise AIVPError(
                    "Failed to delete expired "
                    "cache index entries"
                ) from exc

            surviving_rows = (
                _load_entries(
                    connection
                )
            )

            surviving_digests = {
                str(
                    row[
                        "object_sha256"
                    ]
                )
                for row in surviving_rows
            }

        objects, temp_files = (
            _scan_cas(
                cache_root
            )
        )

        for digest, path in objects:
            if digest in surviving_digests:
                results.append(
                    CacheGCResult(
                        kind="cas-object",
                        resource=str(path),
                        removed=False,
                        dry_run=dry_run,
                        age_seconds=(
                            _mtime_age_seconds(
                                path=path,
                                now=current,
                            )
                        ),
                        reason=(
                            "CAS object is referenced "
                            "by surviving cache entry"
                        ),
                    )
                )
                continue

            age = _mtime_age_seconds(
                path=path,
                now=current,
            )

            if age < 0:
                results.append(
                    CacheGCResult(
                        kind="cas-object",
                        resource=str(path),
                        removed=False,
                        dry_run=dry_run,
                        age_seconds=age,
                        reason=(
                            "CAS object timestamp is "
                            "in the future; preserve"
                        ),
                    )
                )
                continue

            if age < older_than_seconds:
                results.append(
                    CacheGCResult(
                        kind="cas-object",
                        resource=str(path),
                        removed=False,
                        dry_run=dry_run,
                        age_seconds=age,
                        reason=(
                            "unreferenced CAS object "
                            "is still within retention"
                        ),
                    )
                )
                continue

            if not dry_run:
                path.unlink()

            results.append(
                CacheGCResult(
                    kind="cas-object",
                    resource=str(path),
                    removed=(
                        not dry_run
                    ),
                    dry_run=dry_run,
                    age_seconds=age,
                    reason=(
                        "unreferenced expired CAS "
                        "object would be removed"
                        if dry_run
                        else
                        "unreferenced expired CAS "
                        "object removed"
                    ),
                )
            )

        for path in temp_files:
            age = _mtime_age_seconds(
                path=path,
                now=current,
            )

            if age < 0:
                continue

            if age < older_than_seconds:
                continue

            if not dry_run:
                path.unlink()

            results.append(
                CacheGCResult(
                    kind="temp-file",
                    resource=str(path),
                    removed=(
                        not dry_run
                    ),
                    dry_run=dry_run,
                    age_seconds=age,
                    reason=(
                        "stale cache temp file would "
                        "be removed"
                        if dry_run
                        else
                        "stale cache temp file removed"
                    ),
                )
            )

        return results

    finally:
        connection.close()
