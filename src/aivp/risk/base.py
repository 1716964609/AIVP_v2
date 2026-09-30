from typing import Any, Dict, Protocol, Sequence


class RiskEngine(Protocol):
    def assess(
        self,
        *,
        config: Dict[str, Any],
        paths: Sequence[str],
        diff_text: str,
        codex_risk: Dict[str, Any],
        claude_review: Dict[str, Any],
    ) -> Dict[str, Any]:
        ...
