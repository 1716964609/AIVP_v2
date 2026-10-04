from dataclasses import dataclass


@dataclass(frozen=True)
class RepairBudgetDecision:
    allow_repair: bool
    mode: str
    reason: str
    codex_remaining: int
    claude_remaining: int
    codex_required: int
    claude_required: int
    reserved_codex_risk_calls: int


# Compatibility alias for the first M8-3 implementation.
ReviewRepairBudgetDecision = RepairBudgetDecision


def _route_repair_budget(
    *,
    codex_calls: int,
    claude_calls: int,
    codex_max_calls: int,
    claude_max_calls: int,
    reserved_codex_risk_calls: int = 1,
) -> RepairBudgetDecision:
    """
    Decide whether one more repair call can be admitted while
    preserving the downstream independent review and risk judge.

    Required capacity:
    - Codex fixer now: 1
    - Claude review after repair: 1
    - conservative Codex risk reserve: configurable, default 1

    The risk reserve remains conservative even if later routing may
    prove that the Codex risk call can safely be skipped.
    """

    if reserved_codex_risk_calls < 0:
        raise ValueError(
            "reserved_codex_risk_calls "
            "cannot be negative"
        )

    codex_remaining = max(
        0,
        codex_max_calls - codex_calls,
    )

    claude_remaining = max(
        0,
        claude_max_calls - claude_calls,
    )

    codex_required = (
        1
        + reserved_codex_risk_calls
    )

    claude_required = 1

    if codex_remaining < codex_required:
        return RepairBudgetDecision(
            allow_repair=False,
            mode="budget_denied",
            reason=(
                "insufficient Codex budget: "
                f"{codex_remaining} remaining, "
                f"{codex_required} required "
                "for fixer plus downstream "
                "risk reserve"
            ),
            codex_remaining=codex_remaining,
            claude_remaining=claude_remaining,
            codex_required=codex_required,
            claude_required=claude_required,
            reserved_codex_risk_calls=(
                reserved_codex_risk_calls
            ),
        )

    if claude_remaining < claude_required:
        return RepairBudgetDecision(
            allow_repair=False,
            mode="budget_denied",
            reason=(
                "insufficient Claude budget: "
                f"{claude_remaining} remaining, "
                f"{claude_required} required "
                "for post-repair review"
            ),
            codex_remaining=codex_remaining,
            claude_remaining=claude_remaining,
            codex_required=codex_required,
            claude_required=claude_required,
            reserved_codex_risk_calls=(
                reserved_codex_risk_calls
            ),
        )

    return RepairBudgetDecision(
        allow_repair=True,
        mode="repair_admitted",
        reason=(
            "repair admitted with downstream "
            "review and risk capacity preserved"
        ),
        codex_remaining=codex_remaining,
        claude_remaining=claude_remaining,
        codex_required=codex_required,
        claude_required=claude_required,
        reserved_codex_risk_calls=(
            reserved_codex_risk_calls
        ),
    )


def route_review_repair_budget(
    *,
    codex_calls: int,
    claude_calls: int,
    codex_max_calls: int,
    claude_max_calls: int,
    reserved_codex_risk_calls: int = 1,
) -> RepairBudgetDecision:
    return _route_repair_budget(
        codex_calls=codex_calls,
        claude_calls=claude_calls,
        codex_max_calls=codex_max_calls,
        claude_max_calls=claude_max_calls,
        reserved_codex_risk_calls=(
            reserved_codex_risk_calls
        ),
    )


def route_deterministic_repair_budget(
    *,
    codex_calls: int,
    claude_calls: int,
    codex_max_calls: int,
    claude_max_calls: int,
    reserved_codex_risk_calls: int = 1,
) -> RepairBudgetDecision:
    return _route_repair_budget(
        codex_calls=codex_calls,
        claude_calls=claude_calls,
        codex_max_calls=codex_max_calls,
        claude_max_calls=claude_max_calls,
        reserved_codex_risk_calls=(
            reserved_codex_risk_calls
        ),
    )
