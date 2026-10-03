from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from aivp.context.association import (
    find_test_associations,
)
from aivp.context.base import (
    ContextArtifact,
    ContextRequest,
)
from aivp.context.budget import (
    enforce_context_budget,
)
from aivp.context.imports import (
    find_import_neighbors,
)
from aivp.context.repo_map import (
    RepoMapEntry,
    build_repo_map,
)
from aivp.context.selector import (
    select_relevant_files,
)


COMPILER_VERSION = "1.0.0"
MANIFEST_VERSION = "1.0.0"


@dataclass(frozen=True)
class ContextCompilation:
    artifact: ContextArtifact
    manifest_json: str


def _render_context(
    entries,
) -> str:
    parts = []

    for entry in entries:
        reasons = ", ".join(
            entry.reasons
        )

        parts.append(
            "\n".join(
                [
                    (
                        "===== CONTEXT FILE: "
                        f"{entry.path} ====="
                    ),
                    (
                        "SELECTION REASONS: "
                        f"{reasons}"
                    ),
                    "",
                    entry.content,
                ]
            )
        )

    return "\n\n".join(
        parts
    )


def _canonical_json(
    payload: Dict[
        str,
        Any,
    ],
) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _manifest_hash(
    payload: Dict[
        str,
        Any,
    ],
) -> str:
    canonical = _canonical_json(
        payload
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def compile_context(
    request: ContextRequest,
    *,
    repo_map: Optional[
        Tuple[RepoMapEntry, ...]
    ] = None,
) -> ContextCompilation:
    if repo_map is None:
        repo_map = build_repo_map(
            request.repo
        )

    selected = select_relevant_files(
        repo=request.repo,
        repo_map=repo_map,
        task_text=request.task_text,
    )

    associations = (
        find_test_associations(
            repo_map=repo_map,
            selected=selected,
        )
    )

    imports = find_import_neighbors(
        repo=request.repo,
        repo_map=repo_map,
        selected=selected,
    )

    budget_result = (
        enforce_context_budget(
            repo=request.repo,
            selected=selected,
            associations=associations,
            imports=imports,
            budget=request.budget,
        )
    )

    rendered_context = (
        _render_context(
            budget_result.entries
        )
    )

    manifest_payload = {
        "version": (
            MANIFEST_VERSION
        ),
        "compiler_version": (
            COMPILER_VERSION
        ),
        "budget": {
            "max_files": (
                request.budget
                .max_files
            ),
            "max_chars": (
                request.budget
                .max_chars
            ),
        },
        "repo_map_count": len(
            repo_map
        ),
        "selected": [
            {
                "path": entry.path,
                "reasons": list(
                    entry.reasons
                ),
                "size_chars": (
                    entry.size_chars
                ),
                "content_hash": (
                    entry.content_hash
                ),
            }
            for entry
            in budget_result.entries
        ],
        "rejected_paths": list(
            budget_result
            .rejected_paths
        ),
        "selected_content_chars": (
            budget_result.total_chars
        ),
        "rendered_context_chars": len(
            rendered_context
        ),
    }

    manifest_hash = (
        _manifest_hash(
            manifest_payload
        )
    )

    manifest = {
        **manifest_payload,
        "manifest_hash": (
            manifest_hash
        ),
    }

    artifact = ContextArtifact(
        entries=(
            budget_result.entries
        ),
        rendered_context=(
            rendered_context
        ),
        total_chars=(
            budget_result.total_chars
        ),
        manifest_hash=(
            manifest_hash
        ),
        compiler_version=(
            COMPILER_VERSION
        ),
    )

    manifest_json = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"

    return ContextCompilation(
        artifact=artifact,
        manifest_json=manifest_json,
    )
