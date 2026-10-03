from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from aivp.errors import AIVPError
from aivp.state.hashing import (
    sha256_json,
    sha256_text,
)


CACHE_KEY_VERSION = "1.0.0"


@dataclass(frozen=True)
class ContextCacheIdentity:
    repo_sha: str
    task_fingerprint: str
    compiler_version: str
    max_files: int
    max_chars: int

    def payload(self) -> Dict[str, Any]:
        return {
            "cache_key_version": (
                CACHE_KEY_VERSION
            ),
            "repo_sha": self.repo_sha,
            "task_fingerprint": (
                self.task_fingerprint
            ),
            "compiler_version": (
                self.compiler_version
            ),
            "budget": {
                "max_files": self.max_files,
                "max_chars": self.max_chars,
            },
        }

    @property
    def key(self) -> str:
        return sha256_json(
            self.payload()
        )


def context_cache_identity(
    *,
    repo_sha: str,
    task_text: str,
    compiler_version: str,
    max_files: int,
    max_chars: int,
) -> ContextCacheIdentity:
    for name, value in (
        ("repo_sha", repo_sha),
        (
            "compiler_version",
            compiler_version,
        ),
    ):
        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise AIVPError(
                f"{name} must be a "
                "non-empty string"
            )

    if max_files <= 0:
        raise AIVPError(
            "max_files must be greater "
            "than zero"
        )

    if max_chars <= 0:
        raise AIVPError(
            "max_chars must be greater "
            "than zero"
        )

    return ContextCacheIdentity(
        repo_sha=repo_sha,
        task_fingerprint=(
            sha256_text(task_text)
        ),
        compiler_version=(
            compiler_version
        ),
        max_files=max_files,
        max_chars=max_chars,
    )
