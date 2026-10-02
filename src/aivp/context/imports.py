from __future__ import annotations

import ast
import re

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

from aivp.context.repo_map import RepoMapEntry
from aivp.context.selector import SelectionCandidate


_JS_IMPORT_RE = re.compile(
    r"""
    (?:
        import
        (?:[\s\S]*?)
        from\s*
      |
        import\s*
      |
        require\s*\(
    )
    ["']
    (?P<target>\.{1,2}/[^"']+)
    ["']
    """,
    re.VERBOSE,
)

_JS_EXTENSIONS = (
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".json",
)


@dataclass(frozen=True)
class ImportNeighbor:
    source_path: str
    neighbor_path: str
    reason: str


def _repo_paths(
    repo_map: Tuple[
        RepoMapEntry,
        ...
    ],
) -> frozenset[str]:
    return frozenset(
        entry.path
        for entry in repo_map
        if not entry.is_binary
    )


def _python_module_candidates(
    module: str,
) -> Tuple[str, ...]:
    base = module.replace(
        ".",
        "/",
    )

    return (
        f"{base}.py",
        f"{base}/__init__.py",
    )


def _resolve_python_absolute(
    *,
    module: str,
    paths: frozenset[str],
) -> Tuple[str, ...]:
    matches = []

    for candidate in (
        _python_module_candidates(
            module
        )
    ):
        for path in paths:
            if (
                path == candidate
                or path.endswith(
                    "/" + candidate
                )
            ):
                matches.append(path)

    return tuple(
        sorted(
            set(matches)
        )
    )


def _resolve_python_relative(
    *,
    source_path: str,
    level: int,
    module: str | None,
    paths: frozenset[str],
) -> Tuple[str, ...]:
    source_parent = Path(
        source_path
    ).parent

    base = source_parent

    for _ in range(
        max(
            level - 1,
            0,
        )
    ):
        base = base.parent

    if module:
        base = (
            base
            / module.replace(
                ".",
                "/",
            )
        )

    candidates = (
        base.with_suffix(
            ".py"
        ).as_posix(),
        (
            base
            / "__init__.py"
        ).as_posix(),
    )

    return tuple(
        candidate
        for candidate in candidates
        if candidate in paths
    )


def _python_imports(
    *,
    source_path: str,
    content: str,
    paths: frozenset[str],
) -> Tuple[str, ...]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return ()

    neighbors = []

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                neighbors.extend(
                    _resolve_python_absolute(
                        module=alias.name,
                        paths=paths,
                    )
                )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.level:
                neighbors.extend(
                    _resolve_python_relative(
                        source_path=source_path,
                        level=node.level,
                        module=node.module,
                        paths=paths,
                    )
                )
            elif node.module:
                neighbors.extend(
                    _resolve_python_absolute(
                        module=node.module,
                        paths=paths,
                    )
                )

    return tuple(
        sorted(
            set(neighbors)
        )
    )


def _resolve_js_relative(
    *,
    source_path: str,
    target: str,
    paths: frozenset[str],
) -> Tuple[str, ...]:
    source_parent = Path(
        source_path
    ).parent

    base = (
        source_parent
        / target
    )

    candidates = []

    if base.suffix:
        candidates.append(
            base.as_posix()
        )
    else:
        for extension in (
            _JS_EXTENSIONS
        ):
            candidates.append(
                (
                    Path(
                        f"{base}{extension}"
                    )
                ).as_posix()
            )

            candidates.append(
                (
                    base
                    / f"index{extension}"
                ).as_posix()
            )

    return tuple(
        sorted(
            candidate
            for candidate in set(
                candidates
            )
            if candidate in paths
        )
    )


def _js_imports(
    *,
    source_path: str,
    content: str,
    paths: frozenset[str],
) -> Tuple[str, ...]:
    neighbors = []

    for match in (
        _JS_IMPORT_RE.finditer(
            content
        )
    ):
        neighbors.extend(
            _resolve_js_relative(
                source_path=source_path,
                target=match.group(
                    "target"
                ),
                paths=paths,
            )
        )

    return tuple(
        sorted(
            set(neighbors)
        )
    )


def find_import_neighbors(
    *,
    repo: Path,
    repo_map: Tuple[
        RepoMapEntry,
        ...
    ],
    selected: Iterable[
        SelectionCandidate
    ],
) -> Tuple[
    ImportNeighbor,
    ...
]:
    repo = repo.resolve()
    paths = _repo_paths(
        repo_map
    )

    neighbors = []

    for candidate in selected:
        if candidate.path not in paths:
            continue

        absolute = (
            repo
            / candidate.path
        )

        if (
            absolute.is_symlink()
            or not absolute.is_file()
        ):
            continue

        try:
            content = (
                absolute.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            )
        except OSError:
            continue

        suffix = (
            Path(
                candidate.path
            ).suffix.lower()
        )

        imported: Tuple[
            str,
            ...
        ]

        if suffix == ".py":
            imported = _python_imports(
                source_path=candidate.path,
                content=content,
                paths=paths,
            )

        elif suffix in {
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".mjs",
            ".cjs",
        }:
            imported = _js_imports(
                source_path=candidate.path,
                content=content,
                paths=paths,
            )

        else:
            imported = ()

        for neighbor_path in imported:
            if (
                neighbor_path
                == candidate.path
            ):
                continue

            neighbors.append(
                ImportNeighbor(
                    source_path=(
                        candidate.path
                    ),
                    neighbor_path=(
                        neighbor_path
                    ),
                    reason=(
                        "direct_import"
                    ),
                )
            )

    return tuple(
        sorted(
            set(neighbors),
            key=lambda item: (
                item.source_path,
                item.neighbor_path,
                item.reason,
            ),
        )
    )
