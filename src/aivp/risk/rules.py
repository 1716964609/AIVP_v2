import fnmatch
from typing import Any, Dict, Sequence


def rule_based_risk(
    config: Dict[str, Any],
    paths: Sequence[str],
    diff_text: str,
) -> Dict[str, Any]:
    policy = config.get("risk_policy", {})
    high_paths = policy.get("high_risk_paths", [])
    high_patterns = policy.get("high_risk_patterns", [])
    reasons = []

    for path in paths:
        for pattern in high_paths:
            if fnmatch.fnmatch(path, pattern):
                reasons.append(
                    f"path matches high-risk rule: {path} ~ {pattern}"
                )

    for pattern in high_patterns:
        if str(pattern).lower() in diff_text.lower():
            reasons.append(
                f"diff contains high-risk pattern: {pattern}"
            )

    return {
        "risk": "high" if reasons else "low",
        "reasons": reasons or [
            "no deterministic high-risk rule matched"
        ],
    }
