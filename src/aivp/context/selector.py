from __future__ import annotations

import re

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

from aivp.context.repo_map import RepoMapEntry


_TOKEN_RE = re.compile(
    r"[A-Za-z0-9]+"
)

_STOP_WORDS = frozenset(
    {
        "add",
        "and",
        "change",
        "code",
        "fix",
        "for",
        "from",
        "implement",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "update",
        "with",
    }
)


@dataclass(frozen=True)
class SelectionCandidate:
    path: str
    score: int
    reasons: Tuple[str, ...]


def _tokens(
    text: str,
) -> Tuple[str, ...]:
    result = []

    for raw in _TOKEN_RE.findall(
        text.lower()
    ):
        if len(raw) < 3:
            continue

        if raw in _STOP_WORDS:
            continue

        result.append(raw)

    return tuple(
        sorted(
            set(result)
        )
    )


def _related(
    left: str,
    right: str,
) -> bool:
    if left == right:
        return True

    if min(
        len(left),
        len(right),
    ) < 4:
        return False

    return (
        left.startswith(right)
        or right.startswith(left)
    )


def _matching_tokens(
    query_tokens: Iterable[str],
    candidate_tokens: Iterable[str],
) -> Tuple[str, ...]:
    candidate_tokens = tuple(
        candidate_tokens
    )

    matches = []

    for query in query_tokens:
        if any(
            _related(
                query,
                candidate,
            )
            for candidate in candidate_tokens
        ):
            matches.append(query)

    return tuple(matches)


def select_relevant_files(
    *,
    repo: Path,
    repo_map: Tuple[
        RepoMapEntry,
        ...
    ],
    task_text: str,
) -> Tuple[
    SelectionCandidate,
    ...
]:
    repo = repo.resolve()

    query_tokens = _tokens(
        task_text
    )

    if not query_tokens:
        return ()

    selected = []

    for entry in repo_map:
        if entry.is_binary:
            continue

        path_tokens = _tokens(
            entry.path
        )

        path_matches = (
            _matching_tokens(
                query_tokens,
                path_tokens,
            )
        )

        absolute = (
            repo
            / entry.path
        )

        if (
            absolute.is_symlink()
            or not absolute.is_file()
        ):
            continue

        try:
            content = absolute.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            continue

        content_matches = (
            _matching_tokens(
                query_tokens,
                _tokens(content),
            )
        )

        reasons = []
        score = 0

        for token in path_matches:
            reasons.append(
                f"path_token:{token}"
            )
            score += 3

        for token in content_matches:
            reasons.append(
                f"content_token:{token}"
            )
            score += 1

        if score <= 0:
            continue

        selected.append(
            SelectionCandidate(
                path=entry.path,
                score=score,
                reasons=tuple(
                    sorted(
                        set(reasons)
                    )
                ),
            )
        )

    return tuple(
        sorted(
            selected,
            key=lambda candidate: (
                -candidate.score,
                candidate.path,
            ),
        )
    )
