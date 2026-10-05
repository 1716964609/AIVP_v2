from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from aivp.maintenance.gc import (
    Classification,
    PlannedAction,
)
from aivp.state.sqlite import (
    TERMINAL_RUN_STATUSES,
)


@dataclass(frozen=True)
class ArtifactRetentionFacts:
    run_id: str
    status: str
    current_state: str
    finished_at: Optional[datetime]
    has_resume_checkpoint: bool
    protected: bool = False

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError(
                "run_id must not be empty"
            )

        if not self.status.strip():
            raise ValueError(
                "status must not be empty"
            )

        if not self.current_state.strip():
            raise ValueError(
                "current_state must not be empty"
            )


@dataclass(frozen=True)
class ArtifactRetentionDecision:
    run_id: str
    classification: Classification
    action: PlannedAction
    age_seconds: Optional[float]
    reason: str


def is_protected_run(
    run_id: str,
    *,
    protected_run_prefixes: Iterable[str],
) -> bool:
    for raw_prefix in protected_run_prefixes:
        prefix = raw_prefix.strip()

        if not prefix:
            continue

        if (
            run_id == prefix
            or run_id.startswith(
                prefix + "-"
            )
        ):
            return True

    return False


def classify_artifact_retention(
    facts: ArtifactRetentionFacts,
    *,
    older_than_seconds: float,
    now: Optional[datetime] = None,
) -> ArtifactRetentionDecision:
    if older_than_seconds < 0:
        raise ValueError(
            "older_than_seconds must not be negative"
        )

    current = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    if current.tzinfo is None:
        raise ValueError(
            "now must be timezone-aware"
        )

    current = current.astimezone(
        timezone.utc
    )

    if facts.protected:
        return ArtifactRetentionDecision(
            run_id=facts.run_id,
            classification=(
                Classification.PROTECTED
            ),
            action=PlannedAction.PRESERVE,
            age_seconds=None,
            reason=(
                "run is explicitly protected evidence"
            ),
        )

    terminal = (
        facts.status
        in TERMINAL_RUN_STATUSES
    )

    if terminal:
        if (
            facts.current_state
            != facts.status
        ):
            return ArtifactRetentionDecision(
                run_id=facts.run_id,
                classification=(
                    Classification.UNKNOWN
                ),
                action=(
                    PlannedAction.PRESERVE
                ),
                age_seconds=None,
                reason=(
                    "terminal run status/state "
                    "are inconsistent"
                ),
            )

        if facts.finished_at is None:
            return ArtifactRetentionDecision(
                run_id=facts.run_id,
                classification=(
                    Classification.UNKNOWN
                ),
                action=(
                    PlannedAction.PRESERVE
                ),
                age_seconds=None,
                reason=(
                    "terminal run is missing "
                    "finished_at"
                ),
            )

        finished = facts.finished_at

        if finished.tzinfo is None:
            return ArtifactRetentionDecision(
                run_id=facts.run_id,
                classification=(
                    Classification.UNKNOWN
                ),
                action=(
                    PlannedAction.PRESERVE
                ),
                age_seconds=None,
                reason=(
                    "terminal finished_at is "
                    "timezone-naive"
                ),
            )

        age = (
            current
            - finished.astimezone(
                timezone.utc
            )
        ).total_seconds()

        if age < 0:
            return ArtifactRetentionDecision(
                run_id=facts.run_id,
                classification=(
                    Classification.UNKNOWN
                ),
                action=(
                    PlannedAction.PRESERVE
                ),
                age_seconds=age,
                reason=(
                    "terminal finished_at is "
                    "in the future"
                ),
            )

        if (
            facts.status
            == "HUMAN_REQUIRED"
        ):
            return ArtifactRetentionDecision(
                run_id=facts.run_id,
                classification=(
                    Classification.TERMINAL_RETAINED
                ),
                action=(
                    PlannedAction.PRESERVE
                ),
                age_seconds=age,
                reason=(
                    "human-review run is retained"
                ),
            )

        if age >= older_than_seconds:
            return ArtifactRetentionDecision(
                run_id=facts.run_id,
                classification=(
                    Classification.EXPIRED
                ),
                action=(
                    PlannedAction.GC_CANDIDATE
                ),
                age_seconds=age,
                reason=(
                    "terminal run exceeded "
                    "retention cutoff"
                ),
            )

        return ArtifactRetentionDecision(
            run_id=facts.run_id,
            classification=(
                Classification.TERMINAL_RETAINED
            ),
            action=PlannedAction.PRESERVE,
            age_seconds=age,
            reason=(
                "terminal run is still "
                "within retention"
            ),
        )

    if facts.finished_at is not None:
        return ArtifactRetentionDecision(
            run_id=facts.run_id,
            classification=(
                Classification.UNKNOWN
            ),
            action=PlannedAction.PRESERVE,
            age_seconds=None,
            reason=(
                "non-terminal run unexpectedly "
                "has finished_at"
            ),
        )

    if facts.has_resume_checkpoint:
        return ArtifactRetentionDecision(
            run_id=facts.run_id,
            classification=(
                Classification.RESUMABLE
            ),
            action=PlannedAction.PRESERVE,
            age_seconds=None,
            reason=(
                "non-terminal run has durable "
                "resume checkpoint"
            ),
        )

    return ArtifactRetentionDecision(
        run_id=facts.run_id,
        classification=(
            Classification.UNKNOWN
        ),
        action=PlannedAction.PRESERVE,
        age_seconds=None,
        reason=(
            "run is non-terminal but resumability "
            "cannot be proven"
        ),
    )
