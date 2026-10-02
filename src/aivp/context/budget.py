from __future__ import annotations

import hashlib

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

from aivp.context.association import (
    TestAssociation,
)
from aivp.context.base import (
    ContextBudget,
    ContextEntry,
)
from aivp.context.imports import (
    ImportNeighbor,
)
from aivp.context.selector import (
    SelectionCandidate,
)


@dataclass(frozen=True)
class BudgetCandidate:
    path: str
    priority: int
    score: int
    reasons: Tuple[str, ...]


@dataclass(frozen=True)
class BudgetResult:
    entries: Tuple[ContextEntry, ...]
    rejected_paths: Tuple[str, ...]
    total_chars: int


def _merge_candidates(
    *,
    selected: Iterable[
        SelectionCandidate
    ],
    associations: Iterable[
        TestAssociation
    ],
    imports: Iterable[
        ImportNeighbor
    ],
) -> Tuple[
    BudgetCandidate,
    ...
]:
    merged: Dict[
        str,
        dict,
    ] = {}

    def add(
        *,
        path: str,
        priority: int,
        score: int,
        reasons: Iterable[str],
    ) -> None:
        current = merged.get(path)

        if current is None:
            merged[path] = {
                "priority": priority,
                "score": score,
                "reasons": set(reasons),
            }
            return

        current["priority"] = min(
            current["priority"],
            priority,
        )

        current["score"] = max(
            current["score"],
            score,
        )

        current["reasons"].update(
            reasons
        )

    selected_by_path = {
        candidate.path: candidate
        for candidate in selected
    }

    for candidate in selected_by_path.values():
        add(
            path=candidate.path,
            priority=0,
            score=candidate.score,
            reasons=candidate.reasons,
        )

    for association in associations:
        source = selected_by_path.get(
            association.source_path
        )

        source_score = (
            source.score
            if source is not None
            else 0
        )

        add(
            path=association.test_path,
            priority=1,
            score=source_score,
            reasons=(
                (
                    "test_association:"
                    f"{association.source_path}"
                ),
                (
                    "test_association_reason:"
                    f"{association.reason}"
                ),
            ),
        )

    for neighbor in imports:
        source = selected_by_path.get(
            neighbor.source_path
        )

        source_score = (
            source.score
            if source is not None
            else 0
        )

        add(
            path=neighbor.neighbor_path,
            priority=2,
            score=source_score,
            reasons=(
                (
                    "import_neighbor:"
                    f"{neighbor.source_path}"
                ),
                (
                    "import_neighbor_reason:"
                    f"{neighbor.reason}"
                ),
            ),
        )

    return tuple(
        sorted(
            (
                BudgetCandidate(
                    path=path,
                    priority=data[
                        "priority"
                    ],
                    score=data["score"],
                    reasons=tuple(
                        sorted(
                            data["reasons"]
                        )
                    ),
                )
                for path, data
                in merged.items()
            ),
            key=lambda item: (
                item.priority,
                -item.score,
                item.path,
            ),
        )
    )


def _content_hash(
    content: str,
) -> str:
    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def enforce_context_budget(
    *,
    repo: Path,
    selected: Iterable[
        SelectionCandidate
    ],
    associations: Iterable[
        TestAssociation
    ] = (),
    imports: Iterable[
        ImportNeighbor
    ] = (),
    budget: ContextBudget,
) -> BudgetResult:
    repo = repo.resolve()

    candidates = _merge_candidates(
        selected=selected,
        associations=associations,
        imports=imports,
    )

    entries = []
    rejected = []
    total_chars = 0

    for candidate in candidates:
        if (
            len(entries)
            >= budget.max_files
        ):
            rejected.append(
                candidate.path
            )
            continue

        absolute = (
            repo
            / candidate.path
        )

        try:
            resolved = absolute.resolve()
        except OSError:
            rejected.append(
                candidate.path
            )
            continue

        if (
            not resolved.is_relative_to(
                repo
            )
            or absolute.is_symlink()
            or not absolute.is_file()
        ):
            rejected.append(
                candidate.path
            )
            continue

        try:
            content = absolute.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            rejected.append(
                candidate.path
            )
            continue

        size_chars = len(content)

        if (
            total_chars
            + size_chars
            > budget.max_chars
        ):
            rejected.append(
                candidate.path
            )
            continue

        entries.append(
            ContextEntry(
                path=candidate.path,
                reasons=(
                    candidate.reasons
                ),
                content=content,
                size_chars=size_chars,
                content_hash=(
                    _content_hash(
                        content
                    )
                ),
            )
        )

        total_chars += size_chars

    return BudgetResult(
        entries=tuple(entries),
        rejected_paths=tuple(
            rejected
        ),
        total_chars=total_chars,
    )
