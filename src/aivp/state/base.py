from typing import Any, Dict, Optional, Protocol


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
