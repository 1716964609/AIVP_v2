from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True)
class ContextBudget:
    max_files: int
    max_chars: int


@dataclass(frozen=True)
class ContextRequest:
    repo: Path
    task_text: str
    budget: ContextBudget


@dataclass(frozen=True)
class ContextEntry:
    path: str
    reasons: Tuple[str, ...]
    content: str
    size_chars: int
    content_hash: str


@dataclass(frozen=True)
class ContextArtifact:
    entries: Tuple[ContextEntry, ...]
    rendered_context: str
    total_chars: int
    manifest_hash: str
    compiler_version: str
