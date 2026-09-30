from __future__ import annotations

from typing import Any, Mapping

from aivp.errors import StateIntegrityError


CHECKPOINT_SCHEMA_VERSION = 1


def validate_checkpoint_schema_version(
    payload: Mapping[str, Any],
) -> None:
    if (
        "checkpoint_schema_version"
        not in payload
    ):
        raise StateIntegrityError(
            "Checkpoint schema version "
            "is missing"
        )

    version = payload[
        "checkpoint_schema_version"
    ]

    if (
        isinstance(version, bool)
        or not isinstance(version, int)
    ):
        raise StateIntegrityError(
            "Checkpoint schema version "
            "must be an integer"
        )

    if version != CHECKPOINT_SCHEMA_VERSION:
        raise StateIntegrityError(
            "Unsupported checkpoint schema "
            f"version {version}; supported "
            f"version is "
            f"{CHECKPOINT_SCHEMA_VERSION}"
        )
