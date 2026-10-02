from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from aivp.context.repo_map import RepoMapEntry
from aivp.context.selector import (
    SelectionCandidate,
)


@dataclass(frozen=True)
class TestAssociation:
    source_path: str
    test_path: str
    reason: str


def _module_key(
    path: str,
) -> str:
    name = Path(path).stem.lower()

    if name.startswith("test_"):
        name = name[5:]

    for suffix in (
        "_test",
        ".test",
        ".spec",
    ):
        if name.endswith(suffix):
            name = name[
                :-len(suffix)
            ]

    return name


def find_test_associations(
    *,
    repo_map: Tuple[
        RepoMapEntry,
        ...
    ],
    selected: Tuple[
        SelectionCandidate,
        ...
    ],
) -> Tuple[
    TestAssociation,
    ...
]:
    entries_by_path = {
        entry.path: entry
        for entry in repo_map
    }

    tests = tuple(
        entry
        for entry in repo_map
        if entry.is_test
        and not entry.is_binary
    )

    associations = []

    for candidate in selected:
        source = entries_by_path.get(
            candidate.path
        )

        if source is None:
            continue

        if source.is_test:
            continue

        source_key = _module_key(
            source.path
        )

        if not source_key:
            continue

        for test in tests:
            if (
                _module_key(
                    test.path
                )
                != source_key
            ):
                continue

            associations.append(
                TestAssociation(
                    source_path=source.path,
                    test_path=test.path,
                    reason="stem_match",
                )
            )

    return tuple(
        sorted(
            set(associations),
            key=lambda item: (
                item.source_path,
                item.test_path,
                item.reason,
            ),
        )
    )
