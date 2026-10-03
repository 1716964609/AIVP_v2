from __future__ import annotations

import json

from dataclasses import dataclass
from typing import Any, Dict, Optional

from aivp.cache.base import (
    ContextCacheIdentity,
)
from aivp.cache.cas import (
    ContentAddressedCache,
)
from aivp.cache.index import (
    SQLiteCacheIndex,
)
from aivp.context.base import (
    ContextArtifact,
    ContextEntry,
)
from aivp.context.compiler import (
    ContextCompilation,
)
from aivp.errors import (
    StateIntegrityError,
)
from aivp.state.hashing import (
    sha256_text,
)


CONTEXT_SELECTION_CACHE_VERSION = "1.0.0"
CONTEXT_SELECTION_NAMESPACE = (
    "context-selection"
)


@dataclass(frozen=True)
class ContextSelectionCacheResult:
    compilation: ContextCompilation
    cache_key: str
    object_sha256: str
    cache_hit: bool


class ContextSelectionCache:
    def __init__(
        self,
        *,
        cas: ContentAddressedCache,
        index: SQLiteCacheIndex,
    ):
        self.cas = cas
        self.index = index

    def get(
        self,
        *,
        identity: ContextCacheIdentity,
    ) -> Optional[
        ContextSelectionCacheResult
    ]:
        cached = self.index.get(
            namespace=(
                CONTEXT_SELECTION_NAMESPACE
            ),
            cache_key=identity.key,
        )

        if cached is None:
            return None

        self._validate_metadata(
            metadata=dict(
                cached.metadata
            ),
            identity=identity,
        )

        payload_text = (
            self.cas.get_text(
                cached.object_sha256
            )
        )

        if payload_text is None:
            return None

        compilation = self._deserialize(
            payload_text=payload_text,
            identity=identity,
        )

        return ContextSelectionCacheResult(
            compilation=compilation,
            cache_key=identity.key,
            object_sha256=(
                cached.object_sha256
            ),
            cache_hit=True,
        )

    def put(
        self,
        *,
        identity: ContextCacheIdentity,
        compilation: ContextCompilation,
    ) -> ContextSelectionCacheResult:
        payload_text = self._serialize(
            identity=identity,
            compilation=compilation,
        )

        stored = self.cas.put_text(
            payload_text
        )

        self.index.put(
            namespace=(
                CONTEXT_SELECTION_NAMESPACE
            ),
            cache_key=identity.key,
            object_sha256=(
                stored.sha256
            ),
            metadata={
                "version": (
                    CONTEXT_SELECTION_CACHE_VERSION
                ),
                "identity": (
                    identity.payload()
                ),
                "manifest_hash": (
                    compilation
                    .artifact
                    .manifest_hash
                ),
            },
        )

        return ContextSelectionCacheResult(
            compilation=compilation,
            cache_key=identity.key,
            object_sha256=stored.sha256,
            cache_hit=False,
        )

    @staticmethod
    def _serialize(
        *,
        identity: ContextCacheIdentity,
        compilation: ContextCompilation,
    ) -> str:
        artifact = compilation.artifact

        payload = {
            "version": (
                CONTEXT_SELECTION_CACHE_VERSION
            ),
            "cache_key": identity.key,
            "identity": identity.payload(),
            "artifact": {
                "entries": [
                    {
                        "path": entry.path,
                        "reasons": list(
                            entry.reasons
                        ),
                        "content": (
                            entry.content
                        ),
                        "size_chars": (
                            entry.size_chars
                        ),
                        "content_hash": (
                            entry.content_hash
                        ),
                    }
                    for entry
                    in artifact.entries
                ],
                "rendered_context": (
                    artifact.rendered_context
                ),
                "total_chars": (
                    artifact.total_chars
                ),
                "manifest_hash": (
                    artifact.manifest_hash
                ),
                "compiler_version": (
                    artifact.compiler_version
                ),
            },
            "manifest_json": (
                compilation.manifest_json
            ),
        }

        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def _deserialize(
        cls,
        *,
        payload_text: str,
        identity: ContextCacheIdentity,
    ) -> ContextCompilation:
        try:
            payload = json.loads(
                payload_text
            )
        except json.JSONDecodeError as exc:
            raise StateIntegrityError(
                "Context selection cache "
                "payload is invalid JSON"
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise StateIntegrityError(
                "Context selection cache "
                "payload must be an object"
            )

        if (
            payload.get("version")
            != CONTEXT_SELECTION_CACHE_VERSION
        ):
            raise StateIntegrityError(
                "Context selection cache "
                "version mismatch"
            )

        if (
            payload.get("cache_key")
            != identity.key
        ):
            raise StateIntegrityError(
                "Context selection cache "
                "key mismatch"
            )

        if (
            payload.get("identity")
            != identity.payload()
        ):
            raise StateIntegrityError(
                "Context selection cache "
                "identity mismatch"
            )

        raw_artifact = payload.get(
            "artifact"
        )

        if not isinstance(
            raw_artifact,
            dict,
        ):
            raise StateIntegrityError(
                "Context selection cache "
                "artifact must be an object"
            )

        raw_entries = raw_artifact.get(
            "entries"
        )

        if not isinstance(
            raw_entries,
            list,
        ):
            raise StateIntegrityError(
                "Context selection cache "
                "entries must be a list"
            )

        entries = []

        for raw in raw_entries:
            if not isinstance(
                raw,
                dict,
            ):
                raise StateIntegrityError(
                    "Context selection cache "
                    "entry must be an object"
                )

            try:
                entry = ContextEntry(
                    path=raw["path"],
                    reasons=tuple(
                        raw["reasons"]
                    ),
                    content=raw[
                        "content"
                    ],
                    size_chars=raw[
                        "size_chars"
                    ],
                    content_hash=raw[
                        "content_hash"
                    ],
                )
            except (
                KeyError,
                TypeError,
            ) as exc:
                raise StateIntegrityError(
                    "Context selection cache "
                    "entry is invalid"
                ) from exc

            cls._validate_entry(
                entry
            )

            entries.append(entry)

        rendered_context = (
            raw_artifact.get(
                "rendered_context"
            )
        )

        total_chars = raw_artifact.get(
            "total_chars"
        )

        manifest_hash = (
            raw_artifact.get(
                "manifest_hash"
            )
        )

        compiler_version = (
            raw_artifact.get(
                "compiler_version"
            )
        )

        if not isinstance(
            rendered_context,
            str,
        ):
            raise StateIntegrityError(
                "Cached rendered context "
                "must be a string"
            )

        if (
            not isinstance(
                total_chars,
                int,
            )
            or isinstance(
                total_chars,
                bool,
            )
            or total_chars < 0
        ):
            raise StateIntegrityError(
                "Cached total chars "
                "is invalid"
            )

        if (
            not isinstance(
                manifest_hash,
                str,
            )
            or not manifest_hash
        ):
            raise StateIntegrityError(
                "Cached manifest hash "
                "is invalid"
            )

        if (
            compiler_version
            != identity.compiler_version
        ):
            raise StateIntegrityError(
                "Cached compiler version "
                "mismatch"
            )

        manifest_json = payload.get(
            "manifest_json"
        )

        if not isinstance(
            manifest_json,
            str,
        ):
            raise StateIntegrityError(
                "Cached manifest JSON "
                "must be a string"
            )

        try:
            manifest = json.loads(
                manifest_json
            )
        except json.JSONDecodeError as exc:
            raise StateIntegrityError(
                "Cached manifest JSON "
                "is invalid"
            ) from exc

        if not isinstance(
            manifest,
            dict,
        ):
            raise StateIntegrityError(
                "Cached manifest "
                "must be an object"
            )

        if (
            manifest.get(
                "manifest_hash"
            )
            != manifest_hash
        ):
            raise StateIntegrityError(
                "Cached manifest hash "
                "does not match artifact"
            )

        if (
            manifest.get(
                "compiler_version"
            )
            != compiler_version
        ):
            raise StateIntegrityError(
                "Cached manifest compiler "
                "version mismatch"
            )

        artifact = ContextArtifact(
            entries=tuple(entries),
            rendered_context=(
                rendered_context
            ),
            total_chars=total_chars,
            manifest_hash=manifest_hash,
            compiler_version=(
                compiler_version
            ),
        )

        return ContextCompilation(
            artifact=artifact,
            manifest_json=manifest_json,
        )

    @staticmethod
    def _validate_entry(
        entry: ContextEntry,
    ) -> None:
        if (
            not isinstance(
                entry.path,
                str,
            )
            or not entry.path
        ):
            raise StateIntegrityError(
                "Cached context path "
                "is invalid"
            )

        if not all(
            isinstance(
                reason,
                str,
            )
            for reason
            in entry.reasons
        ):
            raise StateIntegrityError(
                "Cached context reasons "
                "are invalid"
            )

        if not isinstance(
            entry.content,
            str,
        ):
            raise StateIntegrityError(
                "Cached context content "
                "is invalid"
            )

        if (
            not isinstance(
                entry.size_chars,
                int,
            )
            or isinstance(
                entry.size_chars,
                bool,
            )
            or entry.size_chars < 0
        ):
            raise StateIntegrityError(
                "Cached context size "
                "is invalid"
            )

        if (
            entry.size_chars
            != len(entry.content)
        ):
            raise StateIntegrityError(
                "Cached context size "
                "does not match content"
            )

        if (
            sha256_text(
                entry.content
            )
            != entry.content_hash
        ):
            raise StateIntegrityError(
                "Cached context content "
                "hash mismatch"
            )

    @staticmethod
    def _validate_metadata(
        *,
        metadata: Dict[
            str,
            Any,
        ],
        identity: ContextCacheIdentity,
    ) -> None:
        if (
            metadata.get("version")
            != CONTEXT_SELECTION_CACHE_VERSION
        ):
            raise StateIntegrityError(
                "Context selection cache "
                "metadata version mismatch"
            )

        if (
            metadata.get("identity")
            != identity.payload()
        ):
            raise StateIntegrityError(
                "Context selection cache "
                "metadata identity mismatch"
            )

        manifest_hash = metadata.get(
            "manifest_hash"
        )

        if (
            not isinstance(
                manifest_hash,
                str,
            )
            or not manifest_hash
        ):
            raise StateIntegrityError(
                "Context selection cache "
                "metadata manifest hash "
                "is invalid"
            )
