from pathlib import Path
from typing import (
    Any,
    Dict,
    Mapping,
    Optional,
    Protocol,
    Sequence,
)


class StateStore(Protocol):
    def save(
        self,
        run_id: str,
        state: Dict[str, Any],
    ) -> None:
        ...

    def load(
        self,
        run_id: str,
    ) -> Optional[Dict[str, Any]]:
        ...


class DurableStateStore(
    StateStore,
    Protocol,
):
    def begin_run(
        self,
        *,
        run_id: str,
        repo_path: Path,
        base_sha: str,
        current_state: str,
        pricing_version: Optional[str] = None,
    ) -> None:
        ...

    def record_artifact(
        self,
        *,
        artifact_id: str,
        run_id: str,
        artifact_type: str,
        path: Path,
        sha256: str,
        size_bytes: int,
        sensitive: bool = False,
    ) -> None:
        ...

    def complete_step(
        self,
        **kwargs: Any,
    ) -> None:
        ...

    def artifacts_for_run(
        self,
        run_id: str,
    ) -> Sequence[Mapping[str, Any]]:
        ...

    def record_model_call(
        self,
        *,
        call_id: str,
        run_id: str,
        step_id: str,
        provider: str,
        model: str,
        input_tokens: Optional[int],
        cached_tokens: Optional[int],
        output_tokens: Optional[int],
        latency_ms: Optional[int],
        cost_usd: Optional[float],
        status: str,
    ) -> None:
        ...

    def model_calls_for_run(
        self,
        run_id: str,
    ) -> Sequence[Mapping[str, Any]]:
        ...
