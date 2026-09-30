from pathlib import Path
from typing import Any, Dict, Protocol


class Verifier(Protocol):
    def verify(
        self,
        *,
        repo: Path,
        config: Dict[str, Any],
        phase: str,
    ) -> Dict[str, Any]:
        ...
