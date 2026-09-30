from __future__ import annotations

import hashlib
import json

from pathlib import Path
from typing import Any


def sha256_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


def sha256_text(
    value: str,
) -> str:
    return sha256_bytes(
        value.encode("utf-8")
    )


def sha256_json(
    value: Any,
) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return sha256_text(
        encoded
    )


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()
