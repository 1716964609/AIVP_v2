from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class StepRecord:
    step_id: str
    run_id: str
    step_type: str
    attempt: int
    status: str
    input_hash: Optional[str]
    output_hash: Optional[str]
    started_at: str
    finished_at: Optional[str]
    error_class: Optional[str]
    retryable: bool


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    run_id: str
    type: str
    path: Path
    sha256: str
    size_bytes: int
    sensitive: bool
    created_at: str
