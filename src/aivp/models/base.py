from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Sequence


@dataclass(frozen=True)
class ModelRequest:
    role: str
    prompt: str
    repo: Path
    timeout_seconds: int
    log_stem: str
    output_schema: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ModelResult:
    provider: str
    model: str

    started_at: str
    finished_at: str

    raw_exit_status: int

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None

    cost_estimate_usd: Optional[float] = None

    artifact_paths: Sequence[Path] = field(
        default_factory=tuple
    )

    last_message: Optional[str] = None

    raw_metadata: Dict[str, Any] = field(
        default_factory=dict
    )


class ModelAdapter(Protocol):
    def invoke(
        self,
        request: ModelRequest,
    ) -> ModelResult:
        ...
