from __future__ import annotations

import shutil

from dataclasses import dataclass
from pathlib import Path

from aivp.errors import StateIntegrityError
from aivp.maintenance.artifact_retention import (
    ArtifactRetentionDecision,
)
from aivp.maintenance.gc import (
    Classification,
    PlannedAction,
)
from aivp.maintenance.worktree_gc import (
    remove_owned_worktree,
)
from aivp.state.sqlite import SQLiteStateStore


RETENTION_INTENT_EVENT = (
    "retention.purge.intent"
)

RETENTION_COMPLETED_EVENT = (
    "retention.purge.completed"
)


@dataclass(frozen=True)
class ArtifactRetentionExecutionResult:
    run_id: str
    dry_run: bool
    removed_worktree: bool
    removed_run_dir: bool
    already_completed: bool
    reason: str


def _resolve_non_symlink_directory(
    directory: Path,
    *,
    label: str,
    must_exist: bool,
) -> Path:
    expanded = directory.expanduser()

    if expanded.exists():
        if expanded.is_symlink():
            raise StateIntegrityError(
                f"{label} must not be a symlink"
            )

        if not expanded.is_dir():
            raise StateIntegrityError(
                f"{label} must be a directory"
            )

    elif must_exist:
        raise StateIntegrityError(
            f"{label} does not exist"
        )

    return expanded.resolve()


def _validate_retention_paths(
    *,
    run_id: str,
    reports_root: Path,
    run_dir: Path,
    worktree_path: Path,
) -> tuple[Path, Path, Path]:
    resolved_root = (
        _resolve_non_symlink_directory(
            reports_root,
            label="reports_root",
            must_exist=True,
        )
    )

    if run_dir.exists() and run_dir.is_symlink():
        raise StateIntegrityError(
            "run_dir must not be a symlink"
        )

    resolved_run = run_dir.expanduser().resolve()

    if resolved_run.parent != resolved_root:
        raise StateIntegrityError(
            "run_dir must be a direct child "
            "of reports_root"
        )

    if resolved_run.name != run_id:
        raise StateIntegrityError(
            "run_dir name must equal run_id"
        )

    if (
        worktree_path.exists()
        and worktree_path.is_symlink()
    ):
        raise StateIntegrityError(
            "worktree_path must not be a symlink"
        )

    resolved_worktree = (
        worktree_path.expanduser().resolve()
    )

    expected_worktree = (
        resolved_run / "worktree"
    )

    if resolved_worktree != expected_worktree:
        raise StateIntegrityError(
            "worktree_path must equal "
            "run_dir/worktree"
        )

    return (
        resolved_root,
        resolved_run,
        resolved_worktree,
    )


def execute_artifact_retention(
    *,
    decision: ArtifactRetentionDecision,
    reports_root: Path,
    run_dir: Path,
    canonical_repo: Path,
    worktree_path: Path,
    store: SQLiteStateStore,
    dry_run: bool = True,
) -> ArtifactRetentionExecutionResult:
    run_id = decision.run_id

    if (
        decision.action
        != PlannedAction.GC_CANDIDATE
    ):
        return ArtifactRetentionExecutionResult(
            run_id=run_id,
            dry_run=dry_run,
            removed_worktree=False,
            removed_run_dir=False,
            already_completed=False,
            reason=(
                "retention planner did not "
                "authorize garbage collection"
            ),
        )

    if (
        decision.classification
        != Classification.EXPIRED
    ):
        raise StateIntegrityError(
            "GC candidate must be classified "
            "as EXPIRED"
        )

    (
        _,
        resolved_run,
        resolved_worktree,
    ) = _validate_retention_paths(
        run_id=run_id,
        reports_root=reports_root,
        run_dir=run_dir,
        worktree_path=worktree_path,
    )

    resolved_canonical = (
        _resolve_non_symlink_directory(
            canonical_repo,
            label="canonical_repo",
            must_exist=True,
        )
    )

    if store.event_exists(
        run_id=run_id,
        event_type=RETENTION_COMPLETED_EVENT,
    ):
        return ArtifactRetentionExecutionResult(
            run_id=run_id,
            dry_run=dry_run,
            removed_worktree=False,
            removed_run_dir=False,
            already_completed=True,
            reason=(
                "retention purge already completed"
            ),
        )

    if dry_run:
        if resolved_worktree.exists():
            remove_owned_worktree(
                canonical_repo=resolved_canonical,
                worktree_path=resolved_worktree,
                dry_run=True,
                allow_dirty=False,
            )

        return ArtifactRetentionExecutionResult(
            run_id=run_id,
            dry_run=True,
            removed_worktree=False,
            removed_run_dir=False,
            already_completed=False,
            reason=(
                "expired run would be purged"
            ),
        )

    if not store.event_exists(
        run_id=run_id,
        event_type=RETENTION_INTENT_EVENT,
    ):
        store.record_event(
            run_id=run_id,
            event_type=RETENTION_INTENT_EVENT,
            payload={
                "classification": (
                    decision.classification.value
                ),
                "action": decision.action.value,
                "age_seconds": (
                    decision.age_seconds
                ),
                "run_dir": str(resolved_run),
                "worktree_path": str(
                    resolved_worktree
                ),
            },
        )

    removed_worktree = False

    if resolved_worktree.exists():
        cleanup = remove_owned_worktree(
            canonical_repo=resolved_canonical,
            worktree_path=resolved_worktree,
            dry_run=False,
            allow_dirty=False,
        )

        removed_worktree = cleanup.removed

        if resolved_worktree.exists():
            raise StateIntegrityError(
                "worktree cleanup did not remove "
                "the expected worktree"
            )

    removed_run_dir = False

    if resolved_run.exists():
        if resolved_run.is_symlink():
            raise StateIntegrityError(
                "run_dir became a symlink"
            )

        shutil.rmtree(
            resolved_run
        )

        removed_run_dir = True

    store.record_event(
        run_id=run_id,
        event_type=RETENTION_COMPLETED_EVENT,
        payload={
            "classification": (
                decision.classification.value
            ),
            "action": decision.action.value,
            "run_dir_removed": (
                not resolved_run.exists()
            ),
            "worktree_removed": (
                not resolved_worktree.exists()
            ),
        },
    )

    return ArtifactRetentionExecutionResult(
        run_id=run_id,
        dry_run=False,
        removed_worktree=removed_worktree,
        removed_run_dir=removed_run_dir,
        already_completed=False,
        reason=(
            "expired run filesystem payload "
            "purged; durable history retained"
        ),
    )
