from __future__ import annotations

from pathlib import Path

from aivp.errors import StateIntegrityError
from aivp.state.hashing import sha256_file


def validate_artifact(
    *,
    path: Path,
    expected_sha256: str,
    expected_size_bytes: int,
) -> None:
    if not path.exists():
        raise StateIntegrityError(
            f"Artifact missing: {path}"
        )

    actual_size = (
        path.stat().st_size
    )

    if actual_size != expected_size_bytes:
        raise StateIntegrityError(
            "Artifact size mismatch: "
            f"{path}"
        )

    actual_sha256 = sha256_file(
        path
    )

    if actual_sha256 != expected_sha256:
        raise StateIntegrityError(
            "Artifact hash mismatch: "
            f"{path}"
        )
