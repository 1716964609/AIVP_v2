from __future__ import annotations

import copy
import datetime as dt
import re
import uuid

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

from aivp.application import run_new
from aivp.artifacts.io import dump_json
from aivp.containment.worktree import (
    resolve_revision,
)
from aivp.errors import AIVPError
from aivp.eval.case import EvalCase


EVAL_RUNNER_VERSION = "1.0.0"

_EVALUATION_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)


class EvalRunnerError(AIVPError):
    """Invalid or unsafe evaluation execution."""


@dataclass(frozen=True)
class TrialExecution:
    trial_id: str
    trial_index: int
    run_id: str
    run_dir: Path
    manifest_path: Path


@dataclass(frozen=True)
class EvalExecution:
    evaluation_id: str
    evaluation_root: Path
    resolved_base_sha: str
    trials: Tuple[TrialExecution, ...]


def _now_iso() -> str:
    return dt.datetime.now(
        dt.timezone.utc
    ).isoformat()


def new_evaluation_id() -> str:
    stamp = dt.datetime.now(
        dt.timezone.utc
    ).strftime("%Y%m%d-%H%M%S")

    suffix = uuid.uuid4().hex[:8]

    return f"eval-{stamp}-{suffix}"


def _jsonable(
    value: Any,
) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _jsonable(item)
            for item in value
        ]

    if isinstance(value, Path):
        return str(value)

    return value


def _validate_evaluation_id(
    evaluation_id: str,
) -> str:
    evaluation_id = evaluation_id.strip()

    if not _EVALUATION_ID_RE.fullmatch(
        evaluation_id
    ):
        raise EvalRunnerError(
            "evaluation_id must match "
            "[a-z0-9][a-z0-9._-]*"
        )

    return evaluation_id


def _write_evaluation_manifest(
    path: Path,
    *,
    evaluation_id: str,
    case: EvalCase,
    resolved_base_sha: str,
    state_db: Path,
    status: str,
    completed_trials: int,
    created_at: str,
    finished_at: Optional[str] = None,
    failed_trial_id: Optional[str] = None,
) -> None:
    dump_json(
        path,
        {
            "version": EVAL_RUNNER_VERSION,
            "evaluation_id": evaluation_id,
            "case_id": case.case_id,
            "declared_revision": (
                case.repository.revision
            ),
            "resolved_base_sha": (
                resolved_base_sha
            ),
            "planned_trials": (
                case.trials.count
            ),
            "completed_trials": (
                completed_trials
            ),
            "status": status,
            "created_at": created_at,
            "finished_at": finished_at,
            "failed_trial_id": (
                failed_trial_id
            ),
            "state_db_path": str(
                state_db
            ),
        },
    )


def _write_case_snapshots(
    *,
    evaluation_root: Path,
    case: EvalCase,
    resolved_base_sha: str,
    task: Mapping[str, Any],
    config: Mapping[str, Any],
) -> None:
    dump_json(
        evaluation_root
        / "case-snapshot.json",
        {
            "schema_version": (
                case.schema_version
            ),
            "id": case.case_id,
            "description": (
                case.description
            ),
            "source_path": str(
                case.source_path
            ),
            "repository": {
                "path": str(
                    case.repository.path
                ),
                "declared_revision": (
                    case.repository.revision
                ),
                "resolved_base_sha": (
                    resolved_base_sha
                ),
            },
            "inputs": {
                "task_source": str(
                    case.inputs.task_path
                ),
                "config_source": str(
                    case.inputs.config_path
                ),
                "task_snapshot": (
                    "task-snapshot.json"
                ),
                "config_snapshot": (
                    "config-snapshot.json"
                ),
            },
            "expected": _jsonable(
                case.expected
            ),
            "graders": list(
                case.graders
            ),
            "trials": {
                "count": (
                    case.trials.count
                )
            },
        },
    )

    dump_json(
        evaluation_root
        / "task-snapshot.json",
        _jsonable(task),
    )

    dump_json(
        evaluation_root
        / "config-snapshot.json",
        _jsonable(config),
    )


def _write_trial_manifest(
    path: Path,
    *,
    evaluation_id: str,
    case: EvalCase,
    trial_id: str,
    trial_index: int,
    run_id: str,
    resolved_base_sha: str,
    status: str,
    started_at: str,
    finished_at: Optional[str],
    run_dir_relative: str,
    error_type: Optional[str] = None,
) -> None:
    dump_json(
        path,
        {
            "version": EVAL_RUNNER_VERSION,
            "evaluation_id": (
                evaluation_id
            ),
            "case_id": case.case_id,
            "trial_id": trial_id,
            "trial_index": trial_index,
            "run_id": run_id,
            "declared_revision": (
                case.repository.revision
            ),
            "resolved_base_sha": (
                resolved_base_sha
            ),
            "execution_status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "run_dir": run_dir_relative,
            "error_type": error_type,
        },
    )


def run_eval_case(
    case: EvalCase,
    *,
    reports_root: Path,
    state_db: Path,
    evaluation_id: Optional[str] = None,
) -> EvalExecution:
    selected_evaluation_id = (
        _validate_evaluation_id(
            evaluation_id
            or new_evaluation_id()
        )
    )

    reports_root = (
        reports_root
        .expanduser()
        .resolve()
    )

    state_db = (
        state_db
        .expanduser()
        .resolve()
    )

    # Resolve exactly once so every trial
    # executes against the same immutable commit.
    resolved_base_sha = resolve_revision(
        case.repository.path,
        case.repository.revision,
    )

    # Freeze execution inputs once for the
    # entire evaluation.
    task_snapshot = case.load_task()
    config_snapshot = case.load_config()

    evaluation_root = (
        reports_root
        / case.case_id
        / selected_evaluation_id
    )

    if evaluation_root.exists():
        raise EvalRunnerError(
            "Evaluation path already exists: "
            f"{evaluation_root}"
        )

    evaluation_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    runs_root = (
        evaluation_root / "runs"
    )

    trials_root = (
        evaluation_root / "trials"
    )

    runs_root.mkdir()
    trials_root.mkdir()

    _write_case_snapshots(
        evaluation_root=evaluation_root,
        case=case,
        resolved_base_sha=(
            resolved_base_sha
        ),
        task=task_snapshot,
        config=config_snapshot,
    )

    created_at = _now_iso()

    evaluation_manifest_path = (
        evaluation_root
        / "evaluation-manifest.json"
    )

    _write_evaluation_manifest(
        evaluation_manifest_path,
        evaluation_id=(
            selected_evaluation_id
        ),
        case=case,
        resolved_base_sha=(
            resolved_base_sha
        ),
        state_db=state_db,
        status="RUNNING",
        completed_trials=0,
        created_at=created_at,
    )

    completed = []

    for index in range(
        1,
        case.trials.count + 1,
    ):
        trial_id = (
            f"trial-{index:03d}"
        )

        run_id = (
            f"{selected_evaluation_id}-"
            f"{trial_id}"
        )

        run_dir_relative = (
            f"runs/{run_id}"
        )

        expected_run_dir = (
            runs_root / run_id
        )

        trial_manifest_path = (
            trials_root
            / f"{trial_id}.json"
        )

        started_at = _now_iso()

        _write_trial_manifest(
            trial_manifest_path,
            evaluation_id=(
                selected_evaluation_id
            ),
            case=case,
            trial_id=trial_id,
            trial_index=index,
            run_id=run_id,
            resolved_base_sha=(
                resolved_base_sha
            ),
            status="RUNNING",
            started_at=started_at,
            finished_at=None,
            run_dir_relative=(
                run_dir_relative
            ),
        )

        try:
            run_dir = run_new(
                repo=case.repository.path,
                task=copy.deepcopy(
                    task_snapshot
                ),
                config=copy.deepcopy(
                    config_snapshot
                ),
                reports_root=runs_root,
                state_db=state_db,
                run_id=run_id,
                dry_run=False,
                base_revision=(
                    resolved_base_sha
                ),
            )

            if (
                run_dir.expanduser().resolve()
                != expected_run_dir.resolve()
            ):
                raise EvalRunnerError(
                    "Harness returned unexpected "
                    f"run directory: {run_dir}"
                )

        except Exception as exc:
            finished_at = _now_iso()

            _write_trial_manifest(
                trial_manifest_path,
                evaluation_id=(
                    selected_evaluation_id
                ),
                case=case,
                trial_id=trial_id,
                trial_index=index,
                run_id=run_id,
                resolved_base_sha=(
                    resolved_base_sha
                ),
                status="FAILED",
                started_at=started_at,
                finished_at=finished_at,
                run_dir_relative=(
                    run_dir_relative
                ),
                error_type=(
                    type(exc).__name__
                ),
            )

            _write_evaluation_manifest(
                evaluation_manifest_path,
                evaluation_id=(
                    selected_evaluation_id
                ),
                case=case,
                resolved_base_sha=(
                    resolved_base_sha
                ),
                state_db=state_db,
                status="FAILED",
                completed_trials=len(
                    completed
                ),
                created_at=created_at,
                finished_at=finished_at,
                failed_trial_id=trial_id,
            )

            raise

        finished_at = _now_iso()

        _write_trial_manifest(
            trial_manifest_path,
            evaluation_id=(
                selected_evaluation_id
            ),
            case=case,
            trial_id=trial_id,
            trial_index=index,
            run_id=run_id,
            resolved_base_sha=(
                resolved_base_sha
            ),
            status="COMPLETED",
            started_at=started_at,
            finished_at=finished_at,
            run_dir_relative=(
                run_dir_relative
            ),
        )

        completed.append(
            TrialExecution(
                trial_id=trial_id,
                trial_index=index,
                run_id=run_id,
                run_dir=(
                    expected_run_dir.resolve()
                ),
                manifest_path=(
                    trial_manifest_path.resolve()
                ),
            )
        )

        _write_evaluation_manifest(
            evaluation_manifest_path,
            evaluation_id=(
                selected_evaluation_id
            ),
            case=case,
            resolved_base_sha=(
                resolved_base_sha
            ),
            state_db=state_db,
            status="RUNNING",
            completed_trials=len(
                completed
            ),
            created_at=created_at,
        )

    finished_at = _now_iso()

    _write_evaluation_manifest(
        evaluation_manifest_path,
        evaluation_id=(
            selected_evaluation_id
        ),
        case=case,
        resolved_base_sha=(
            resolved_base_sha
        ),
        state_db=state_db,
        status="COMPLETED",
        completed_trials=len(
            completed
        ),
        created_at=created_at,
        finished_at=finished_at,
    )

    return EvalExecution(
        evaluation_id=(
            selected_evaluation_id
        ),
        evaluation_root=(
            evaluation_root.resolve()
        ),
        resolved_base_sha=(
            resolved_base_sha
        ),
        trials=tuple(completed),
    )
