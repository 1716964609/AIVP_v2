from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet


class RunState(str, Enum):
    CREATED = "CREATED"
    PRECHECKED = "PRECHECKED"
    WORKSPACE_READY = "WORKSPACE_READY"

    CONTEXT_BUILDING = "CONTEXT_BUILDING"
    CONTEXT_READY = "CONTEXT_READY"

    GENERATING = "GENERATING"
    GENERATED = "GENERATED"

    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"

    REVIEWING = "REVIEWING"
    REVIEWED = "REVIEWED"

    RISK_ASSESSING = "RISK_ASSESSING"
    RISK_ASSESSED = "RISK_ASSESSED"

    REPAIRING = "REPAIRING"

    AUTO_FINISHED = "AUTO_FINISHED"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"
    DENIED = "DENIED"

    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


@dataclass(frozen=True)
class Transition:
    source: RunState
    target: RunState
    retryable: bool = False


TRANSITIONS: FrozenSet[Transition] = frozenset(
    {
        Transition(
            RunState.CREATED,
            RunState.PRECHECKED,
        ),
        Transition(
            RunState.PRECHECKED,
            RunState.WORKSPACE_READY,
        ),
        Transition(
            RunState.WORKSPACE_READY,
            RunState.CONTEXT_BUILDING,
        ),
        Transition(
            RunState.CONTEXT_BUILDING,
            RunState.CONTEXT_READY,
        ),
        Transition(
            RunState.CONTEXT_READY,
            RunState.GENERATING,
        ),
        Transition(
            RunState.GENERATING,
            RunState.GENERATED,
        ),
        Transition(
            RunState.GENERATED,
            RunState.VERIFYING,
        ),
        Transition(
            RunState.VERIFYING,
            RunState.VERIFIED,
        ),
        Transition(
            RunState.VERIFYING,
            RunState.REPAIRING,
            retryable=True,
        ),
        Transition(
            RunState.REPAIRING,
            RunState.VERIFYING,
            retryable=True,
        ),
        Transition(
            RunState.VERIFIED,
            RunState.REVIEWING,
        ),
        Transition(
            RunState.REVIEWING,
            RunState.REVIEWED,
        ),
        Transition(
            RunState.REVIEWED,
            RunState.REPAIRING,
            retryable=True,
        ),
        Transition(
            RunState.REVIEWED,
            RunState.RISK_ASSESSING,
        ),
        Transition(
            RunState.RISK_ASSESSING,
            RunState.RISK_ASSESSED,
        ),
        Transition(
            RunState.RISK_ASSESSED,
            RunState.AUTO_FINISHED,
        ),
        Transition(
            RunState.RISK_ASSESSED,
            RunState.HUMAN_REQUIRED,
        ),
        Transition(
            RunState.RISK_ASSESSED,
            RunState.DENIED,
        ),
    }
)


TERMINAL_STATES = frozenset(
    {
        RunState.AUTO_FINISHED,
        RunState.HUMAN_REQUIRED,
        RunState.DENIED,
        RunState.FAILED_TERMINAL,
        RunState.CANCELLED,
    }
)


def can_transition(
    source: RunState,
    target: RunState,
) -> bool:
    return any(
        transition.source == source
        and transition.target == target
        for transition in TRANSITIONS
    )
