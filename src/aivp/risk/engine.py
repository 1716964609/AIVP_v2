from typing import Any, Dict, Sequence

from aivp.risk.aggregate import aggregate_risk
from aivp.risk.rules import rule_based_risk


class LegacyCompatibleRiskEngine:
    def deterministic(
        self,
        *,
        config: Dict[str, Any],
        paths: Sequence[str],
        diff_text: str,
    ) -> Dict[str, Any]:
        return rule_based_risk(
            config,
            paths,
            diff_text,
        )

    def assess(
        self,
        *,
        config: Dict[str, Any],
        paths: Sequence[str],
        diff_text: str,
        codex_risk: Dict[str, Any],
        claude_review: Dict[str, Any],
    ) -> Dict[str, Any]:
        rule = self.deterministic(
            config=config,
            paths=paths,
            diff_text=diff_text,
        )

        aggregate = aggregate_risk(
            rule,
            codex_risk,
            claude_review,
        )

        return {
            "rule": rule,
            "aggregate": aggregate,
        }
