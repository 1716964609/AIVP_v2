from typing import Any, Dict


RISK_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
}


def normalize_risk(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text not in RISK_ORDER:
        return "medium"
    return text


def aggregate_risk(
    rule: Dict[str, Any],
    codex: Dict[str, Any],
    claude: Dict[str, Any],
) -> Dict[str, Any]:
    risks = {
        "rule": normalize_risk(rule.get("risk")),
        "codex": normalize_risk(codex.get("risk")),
        "claude": normalize_risk(claude.get("risk")),
    }

    values = [RISK_ORDER[x] for x in risks.values()]
    disagreement = max(values) - min(values) >= 2
    any_high = any(x == "high" for x in risks.values())

    final = (
        "high"
        if any_high or disagreement
        else ("medium" if "medium" in risks.values() else "low")
    )

    return {
        "final": final,
        "sources": risks,
        "large_disagreement": disagreement,
        "human_required": final == "high",
    }
