from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Ownership(str, Enum):
    AIVP = "aivp"
    FOREIGN = "foreign"
    UNKNOWN = "unknown"


class Classification(str, Enum):
    PROTECTED = "protected"
    RESUMABLE = "resumable"
    TERMINAL_RETAINED = "terminal-retained"
    EXPIRED = "expired"
    ORPHANED = "orphaned"
    FOREIGN = "foreign"
    UNKNOWN = "unknown"


class PlannedAction(str, Enum):
    PRESERVE = "preserve"
    GC_CANDIDATE = "gc-candidate"


@dataclass(frozen=True)
class ResourceFacts:
    resource_id: str
    ownership: Ownership
    protected: bool = False
    resumable: bool = False
    terminal: bool = False
    orphaned: bool = False
    age_seconds: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.resource_id.strip():
            raise ValueError(
                "resource_id must not be empty"
            )

        if (
            self.age_seconds is not None
            and self.age_seconds < 0
        ):
            raise ValueError(
                "age_seconds must not be negative"
            )

        if self.orphaned and self.resumable:
            raise ValueError(
                "a resource cannot be both "
                "orphaned and resumable"
            )


@dataclass(frozen=True)
class GCDecision:
    resource_id: str
    classification: Classification
    action: PlannedAction
    reason: str


def classify_resource(
    facts: ResourceFacts,
    *,
    older_than_seconds: float,
) -> GCDecision:
    if older_than_seconds < 0:
        raise ValueError(
            "older_than_seconds must not be negative"
        )

    if facts.ownership is Ownership.FOREIGN:
        return GCDecision(
            resource_id=facts.resource_id,
            classification=Classification.FOREIGN,
            action=PlannedAction.PRESERVE,
            reason="resource is not owned by AIVP",
        )

    if facts.ownership is Ownership.UNKNOWN:
        return GCDecision(
            resource_id=facts.resource_id,
            classification=Classification.UNKNOWN,
            action=PlannedAction.PRESERVE,
            reason="resource ownership is unknown",
        )

    if facts.protected:
        return GCDecision(
            resource_id=facts.resource_id,
            classification=Classification.PROTECTED,
            action=PlannedAction.PRESERVE,
            reason="resource is explicitly protected",
        )

    if facts.resumable:
        return GCDecision(
            resource_id=facts.resource_id,
            classification=Classification.RESUMABLE,
            action=PlannedAction.PRESERVE,
            reason="resource is required for resume",
        )

    age = facts.age_seconds

    if facts.orphaned:
        old_enough = (
            age is not None
            and age >= older_than_seconds
        )

        return GCDecision(
            resource_id=facts.resource_id,
            classification=Classification.ORPHANED,
            action=(
                PlannedAction.GC_CANDIDATE
                if old_enough
                else PlannedAction.PRESERVE
            ),
            reason=(
                "AIVP-owned orphan is older than "
                "the retention cutoff"
                if old_enough
                else
                "AIVP-owned orphan has not "
                "reached the retention cutoff"
            ),
        )

    if facts.terminal:
        expired = (
            age is not None
            and age >= older_than_seconds
        )

        if expired:
            return GCDecision(
                resource_id=facts.resource_id,
                classification=Classification.EXPIRED,
                action=PlannedAction.GC_CANDIDATE,
                reason=(
                    "terminal AIVP resource is older "
                    "than the retention cutoff"
                ),
            )

        return GCDecision(
            resource_id=facts.resource_id,
            classification=(
                Classification.TERMINAL_RETAINED
            ),
            action=PlannedAction.PRESERVE,
            reason=(
                "terminal AIVP resource is still "
                "within retention"
            ),
        )

    return GCDecision(
        resource_id=facts.resource_id,
        classification=Classification.UNKNOWN,
        action=PlannedAction.PRESERVE,
        reason=(
            "AIVP ownership is known but lifecycle "
            "state is insufficient for deletion"
        ),
    )
