from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Dict, List

from aivp.errors import AIVPError
from aivp.repository.git import (
    capture_diff,
    changed_paths,
)


DEFAULT_MAX_FILES = 12
DEFAULT_MAX_LINES = 800

DEFAULT_FORBIDDEN_PATHS = (
    "secrets/**",
    "infra/prod/**",
    ".github/workflows/prod-*",
)


def evaluate_diff_guard(
    repo: Path,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    raw = config.get(
        "diff_guard",
        {},
    )

    if raw is None:
        raw = {}

    if not isinstance(raw, dict):
        raise AIVPError(
            "diff_guard must be an object"
        )

    try:
        max_files = int(
            raw.get(
                "max_files",
                DEFAULT_MAX_FILES,
            )
        )

        max_lines = int(
            raw.get(
                "max_lines",
                DEFAULT_MAX_LINES,
            )
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise AIVPError(
            "diff_guard limits must be integers"
        ) from exc

    if max_files < 0:
        raise AIVPError(
            "diff_guard.max_files "
            "must be >= 0"
        )

    if max_lines < 0:
        raise AIVPError(
            "diff_guard.max_lines "
            "must be >= 0"
        )

    raw_patterns = raw.get(
        "forbidden_paths",
        list(
            DEFAULT_FORBIDDEN_PATHS
        ),
    )

    if not isinstance(
        raw_patterns,
        list,
    ):
        raise AIVPError(
            "diff_guard.forbidden_paths "
            "must be an array"
        )

    patterns: List[str] = []

    for pattern in raw_patterns:
        if not isinstance(
            pattern,
            str,
        ):
            raise AIVPError(
                "diff_guard.forbidden_paths "
                "entries must be strings"
            )

        normalized = (
            pattern.strip()
        )

        if not normalized:
            raise AIVPError(
                "diff_guard.forbidden_paths "
                "entries must not be empty"
            )

        patterns.append(
            normalized
        )

    paths = changed_paths(
        repo
    )

    diff_text = capture_diff(
        repo
    )

    diff_lines = len(
        diff_text.splitlines()
    )

    forbidden_matches = []

    for path in paths:
        normalized_path = (
            path.replace(
                "\\",
                "/",
            )
        )

        for pattern in patterns:
            if fnmatchcase(
                normalized_path,
                pattern,
            ):
                forbidden_matches.append(
                    {
                        "path": path,
                        "pattern": pattern,
                    }
                )

    violations = []

    if len(paths) > max_files:
        violations.append(
            "changed files "
            f"{len(paths)} exceeds "
            f"max_files {max_files}"
        )

    if diff_lines > max_lines:
        violations.append(
            "diff lines "
            f"{diff_lines} exceeds "
            f"max_lines {max_lines}"
        )

    for match in forbidden_matches:
        violations.append(
            "forbidden path: "
            f"{match['path']} matches "
            f"{match['pattern']}"
        )

    return {
        "passed": not violations,
        "changed_files": len(paths),
        "diff_lines": diff_lines,
        "changed_paths": paths,
        "forbidden_matches": (
            forbidden_matches
        ),
        "limits": {
            "max_files": max_files,
            "max_lines": max_lines,
        },
        "forbidden_patterns": (
            patterns
        ),
        "violations": violations,
    }
