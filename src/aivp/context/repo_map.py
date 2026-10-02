from __future__ import annotations

import os

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


IGNORED_DIRS = frozenset(
    {
        ".git",
        ".aivp",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
    }
)


@dataclass(frozen=True)
class RepoMapEntry:
    path: str
    suffix: str
    size_bytes: int
    is_test: bool
    is_binary: bool


def _is_test_path(
    relative: Path,
) -> bool:
    parts = tuple(
        part.lower()
        for part in relative.parts
    )

    name = relative.name.lower()
    stem = relative.stem.lower()

    if any(
        part in {
            "test",
            "tests",
            "__tests__",
        }
        for part in parts
    ):
        return True

    if name.startswith("test_"):
        return True

    return (
        stem.endswith("_test")
        or stem.endswith(".test")
        or stem.endswith(".spec")
    )


def _is_binary_file(
    path: Path,
) -> bool:
    try:
        with path.open("rb") as handle:
            sample = handle.read(8192)
    except OSError:
        return True

    return b"\x00" in sample


def build_repo_map(
    repo: Path,
) -> Tuple[RepoMapEntry, ...]:
    repo = repo.resolve()

    entries = []

    for root, dirs, files in os.walk(
        repo,
        topdown=True,
        followlinks=False,
    ):
        root_path = Path(root)

        dirs[:] = sorted(
            directory
            for directory in dirs
            if (
                directory not in IGNORED_DIRS
                and not (
                    root_path
                    / directory
                ).is_symlink()
            )
        )

        for filename in sorted(files):
            absolute = (
                root_path
                / filename
            )

            if absolute.is_symlink():
                continue

            relative = absolute.relative_to(
                repo
            )

            try:
                size_bytes = (
                    absolute.stat().st_size
                )
            except OSError:
                continue

            entries.append(
                RepoMapEntry(
                    path=relative.as_posix(),
                    suffix=relative.suffix.lower(),
                    size_bytes=size_bytes,
                    is_test=_is_test_path(
                        relative
                    ),
                    is_binary=_is_binary_file(
                        absolute
                    ),
                )
            )

    return tuple(
        sorted(
            entries,
            key=lambda entry: entry.path,
        )
    )
