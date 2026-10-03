from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence

from aivp.risk.aggregate import normalize_risk


@dataclass(frozen=True)
class RiskRoutingDecision:
    invoke_codex_risk: bool
    mode: str
    reason: str
    deterministic_risk: str
    claude_risk: str
    claude_confidence: float | None
    blocking_findings: int
    verification_passed: bool


def _blocking_findings(
    review: Dict[str, Any],
) -> Sequence[Dict[str, Any]]:
    findings = review.get("findings", [])

    if not isinstance(findings, list):
        return []

    blockers = []

    for finding in findings:
        if not isinstance(finding, dict):
            continue

        severity = str(
            finding.get("severity", "")
        ).strip().lower()

        if severity in {
            "critical",
            "major",
        }:
            blockers.append(finding)

    return blockers


def _risk_confidence(
    review: Dict[str, Any],
) -> float | None:
    value = review.get(
        "risk_confidence"
    )

    if isinstance(value, bool):
        return None

    if isinstance(
        value,
        (int, float),
    ):
        return float(value)

    return None


def route_codex_risk(
    *,
    rule_risk: Dict[str, Any],
    claude_review: Dict[str, Any],
    verification_passed: bool,
    low_confidence_threshold: float = 0.8,
) -> RiskRoutingDecision:
    deterministic_risk = normalize_risk(
        rule_risk.get("risk")
    )

    claude_risk = normalize_risk(
        claude_review.get("risk")
    )

    confidence = _risk_confidence(
        claude_review
    )

    blockers = _blocking_findings(
        claude_review
    )

    if (
        deterministic_risk == "high"
        or claude_risk == "high"
    ):
        return RiskRoutingDecision(
            invoke_codex_risk=False,
            mode="terminal_high",
            reason=(
                "Codex risk is unnecessary because "
                "the existing aggregate contract is "
                "already forced to HIGH."
            ),
            deterministic_risk=(
                deterministic_risk
            ),
            claude_risk=claude_risk,
            claude_confidence=confidence,
            blocking_findings=len(blockers),
            verification_passed=(
                verification_passed
            ),
        )

    conservative_low = (
        verification_passed
        and deterministic_risk == "low"
        and claude_risk == "low"
        and not blockers
        and confidence is not None
        and confidence
        >= low_confidence_threshold
    )

    if conservative_low:
        return RiskRoutingDecision(
            invoke_codex_risk=False,
            mode="conservative_low",
            reason=(
                "Codex risk is skipped because "
                "deterministic risk is LOW, "
                "Claude review risk is LOW with "
                "sufficient confidence, verification "
                "passed, and no blocking findings "
                "remain."
            ),
            deterministic_risk=(
                deterministic_risk
            ),
            claude_risk=claude_risk,
            claude_confidence=confidence,
            blocking_findings=0,
            verification_passed=True,
        )

    return RiskRoutingDecision(
        invoke_codex_risk=True,
        mode="independent_judge_required",
        reason=(
            "Independent Codex risk judgment remains "
            "decision-relevant under the conservative "
            "M8 routing policy."
        ),
        deterministic_risk=(
            deterministic_risk
        ),
        claude_risk=claude_risk,
        claude_confidence=confidence,
        blocking_findings=len(blockers),
        verification_passed=(
            verification_passed
        ),
    )
