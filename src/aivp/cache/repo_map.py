from __future__ import annotations

import json

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

from aivp.cache.cas import (
    ContentAddressedCache,
)
from aivp.cache.index import (
    SQLiteCacheIndex,
)
from aivp.context.repo_map import (
    RepoMapEntry,
    build_repo_map,
)
from aivp.errors import (
    StateIntegrityError,
)
from aivp.state.hashing import (
    sha256_json,
)


REPO_MAP_CACHE_VERSION = "1.0.0"
REPO_MAP_NAMESPACE = "repo-map"


@dataclass(frozen=True)
class RepoMapCacheResult:
    entries: Tuple[
        RepoMapEntry,
        ...
    ]
    cache_key: str
    object_sha256: str
    cache_hit: bool


def repo_map_cache_key(
    *,
    repo_sha: str,
) -> str:
    if (
        not isinstance(repo_sha, str)
        or not repo_sha.strip()
    ):
        raise StateIntegrityError(
            "repo_sha must be a "
            "non-empty string"
        )

    return sha256_json(
        {
            "namespace": (
                REPO_MAP_NAMESPACE
            ),
            "version": (
                REPO_MAP_CACHE_VERSION
            ),
            "repo_sha": repo_sha,
        }
    )


class RepoMapCache:
    def __init__(
        self,
        *,
        cas: ContentAddressedCache,
        index: SQLiteCacheIndex,
    ):
        self.cas = cas
        self.index = index

    def get_or_build(
        self,
        *,
        repo: Path,
        repo_sha: str,
    ) -> RepoMapCacheResult:
        cache_key = repo_map_cache_key(
            repo_sha=repo_sha
        )

        cached = self.index.get(
            namespace=(
                REPO_MAP_NAMESPACE
            ),
            cache_key=cache_key,
        )

        if cached is not None:
            self._validate_metadata(
                metadata=dict(
                    cached.metadata
                ),
                repo_sha=repo_sha,
            )

            payload_text = (
                self.cas.get_text(
                    cached.object_sha256
                )
            )

            if payload_text is not None:
                entries = (
                    self._deserialize(
                        payload_text,
                        repo_sha=repo_sha,
                    )
                )

                return RepoMapCacheResult(
                    entries=entries,
                    cache_key=cache_key,
                    object_sha256=(
                        cached
                        .object_sha256
                    ),
                    cache_hit=True,
                )

        entries = build_repo_map(
            repo
        )

        payload_text = self._serialize(
            entries=entries,
            repo_sha=repo_sha,
        )

        stored = self.cas.put_text(
            payload_text
        )

        self.index.put(
            namespace=(
                REPO_MAP_NAMESPACE
            ),
            cache_key=cache_key,
            object_sha256=(
                stored.sha256
            ),
            metadata={
                "version": (
                    REPO_MAP_CACHE_VERSION
                ),
                "repo_sha": repo_sha,
                "entry_count": len(
                    entries
                ),
            },
        )

        return RepoMapCacheResult(
            entries=entries,
            cache_key=cache_key,
            object_sha256=(
                stored.sha256
            ),
            cache_hit=False,
        )

    @staticmethod
    def _serialize(
        *,
        entries: Tuple[
            RepoMapEntry,
            ...
        ],
        repo_sha: str,
    ) -> str:
        payload = {
            "version": (
                REPO_MAP_CACHE_VERSION
            ),
            "repo_sha": repo_sha,
            "entries": [
                {
                    "path": entry.path,
                    "suffix": (
                        entry.suffix
                    ),
                    "size_bytes": (
                        entry.size_bytes
                    ),
                    "is_test": (
                        entry.is_test
                    ),
                    "is_binary": (
                        entry.is_binary
                    ),
                }
                for entry in entries
            ],
        }

        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _deserialize(
        payload_text: str,
        *,
        repo_sha: str,
    ) -> Tuple[
        RepoMapEntry,
        ...
    ]:
        try:
            payload = json.loads(
                payload_text
            )
        except json.JSONDecodeError as exc:
            raise StateIntegrityError(
                "Repo map cache payload "
                "is invalid JSON"
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise StateIntegrityError(
                "Repo map cache payload "
                "must be an object"
            )

        if (
            payload.get("version")
            != REPO_MAP_CACHE_VERSION
        ):
            raise StateIntegrityError(
                "Repo map cache version "
                "mismatch"
            )

        if (
            payload.get("repo_sha")
            != repo_sha
        ):
            raise StateIntegrityError(
                "Repo map cache repo SHA "
                "mismatch"
            )

        raw_entries = payload.get(
            "entries"
        )

        if not isinstance(
            raw_entries,
            list,
        ):
            raise StateIntegrityError(
                "Repo map cache entries "
                "must be a list"
            )

        entries = []

        for raw in raw_entries:
            if not isinstance(
                raw,
                dict,
            ):
                raise StateIntegrityError(
                    "Repo map cache entry "
                    "must be an object"
                )

            try:
                path = raw["path"]
                suffix = raw["suffix"]
                size_bytes = (
                    raw["size_bytes"]
                )
                is_test = raw[
                    "is_test"
                ]
                is_binary = raw[
                    "is_binary"
                ]
            except KeyError as exc:
                raise StateIntegrityError(
                    "Repo map cache entry "
                    "is incomplete"
                ) from exc

            if (
                not isinstance(
                    path,
                    str,
                )
                or not isinstance(
                    suffix,
                    str,
                )
                or not isinstance(
                    size_bytes,
                    int,
                )
                or isinstance(
                    size_bytes,
                    bool,
                )
                or size_bytes < 0
                or not isinstance(
                    is_test,
                    bool,
                )
                or not isinstance(
                    is_binary,
                    bool,
                )
            ):
                raise StateIntegrityError(
                    "Repo map cache entry "
                    "has invalid types"
                )

            entries.append(
                RepoMapEntry(
                    path=path,
                    suffix=suffix,
                    size_bytes=(
                        size_bytes
                    ),
                    is_test=is_test,
                    is_binary=is_binary,
                )
            )

        return tuple(
            sorted(
                entries,
                key=lambda entry: (
                    entry.path
                ),
            )
        )

    @staticmethod
    def _validate_metadata(
        *,
        metadata: Dict[
            str,
            Any,
        ],
        repo_sha: str,
    ) -> None:
        if (
            metadata.get("version")
            != REPO_MAP_CACHE_VERSION
        ):
            raise StateIntegrityError(
                "Repo map cache metadata "
                "version mismatch"
            )

        if (
            metadata.get("repo_sha")
            != repo_sha
        ):
            raise StateIntegrityError(
                "Repo map cache metadata "
                "repo SHA mismatch"
            )

        entry_count = metadata.get(
            "entry_count"
        )

        if (
            not isinstance(
                entry_count,
                int,
            )
            or isinstance(
                entry_count,
                bool,
            )
            or entry_count < 0
        ):
            raise StateIntegrityError(
                "Repo map cache metadata "
                "entry count is invalid"
            )
