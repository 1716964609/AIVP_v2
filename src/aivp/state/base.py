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
