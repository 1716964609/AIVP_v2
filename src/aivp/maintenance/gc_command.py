from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote

from aivp.errors import (
    AIVPError,
    StateIntegrityError,
)
from aivp.maintenance.artifact_retention import (
    ArtifactRetentionFacts,
    classify_artifact_retention,
    is_protected_run,
)
from aivp.maintenance.artifact_retention_executor import (
    RETENTION_COMPLETED_EVENT,
    execute_artifact_retention,
)
from aivp.maintenance.cache_gc import (
    cleanup_cache,
)
from aivp.maintenance.docker_gc import (
    cleanup_stale_containers,
)
from aivp.maintenance.gc import (
    Classification,
    PlannedAction,
)
from aivp.maintenance.worktree_gc import (
    remove_owned_worktree,
    worktree_owned_by_repo,
)
from aivp.state.checkpoint import (
    validate_checkpoint_schema_version,
)
from aivp.state.sqlite import (
    SQLiteStateStore,
)


_DURATION_RE = re.compile(
    r"^(?P<value>[0-9]+(?:\.[0-9]+)?)"
    r"(?P<unit>[smhd])$"
)

_FORMAL_KEY_RE = re.compile(
    r"formal",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GCReportItem:
    kind: str
    resource: str
    classification: str
    action: str
    reason: str


@dataclass(frozen=True)
class _RunPlan:
    run_id: str
    decision: Any
    checkpoint: Optional[dict[str, Any]]
    purge_completed: bool


class _EventProbe:
    def __init__(
        self,
        *,
        completed: bool,
    ) -> None:
        self.completed = completed

    def event_exists(
        self,
        *,
        run_id: str,
        event_type: str,
    ) -> bool:
        del run_id

        return (
            self.completed
            and event_type
            == RETENTION_COMPLETED_EVENT
        )


def parse_duration_seconds(
    value: str,
) -> float:
    match = _DURATION_RE.fullmatch(
        value.strip()
    )

    if match is None:
        raise ValueError(
            "duration must use s/m/h/d suffix, "
            "for example 30m, 12h, or 7d"
        )

    amount = float(
        match.group("value")
    )

    if amount <= 0:
        raise ValueError(
            "duration must be greater than zero"
        )

    multipliers = {
        "s": 1.0,
        "m": 60.0,
        "h": 3600.0,
        "d": 86400.0,
    }

    return (
        amount
        * multipliers[
            match.group("unit")
        ]
    )


def format_gc_report_item(
    item: GCReportItem,
) -> str:
    def clean(
        value: str,
    ) -> str:
        return (
            value.replace(
                "\t",
                " ",
            )
            .replace(
                "\n",
                " ",
            )
        )

    return "\t".join(
        (
            clean(item.resource),
            clean(item.classification),
            clean(item.action),
            clean(item.reason),
        )
    )


def gc_report_has_errors(
    items: Iterable[GCReportItem],
) -> bool:
    return any(
        item.classification == "error"
        for item in items
    )


def _collect_strings(
    value: Any,
) -> list[str]:
    if isinstance(
        value,
        str,
    ):
        return [value]

    if isinstance(
        value,
        dict,
    ):
        result: list[str] = []

        for nested in value.values():
            result.extend(
                _collect_strings(
                    nested
                )
            )

        return result

    if isinstance(
        value,
        list,
    ):
        result = []

        for nested in value:
            result.extend(
                _collect_strings(
                    nested
                )
            )

        return result

    return []


def _protected_run_prefixes(
    project_state: Path,
) -> tuple[str, ...]:
    source = (
        project_state
        .expanduser()
    )

    if not source.is_file():
        raise StateIntegrityError(
            "PROJECT_STATE file is missing"
        )

    if source.is_symlink():
        raise StateIntegrityError(
            "PROJECT_STATE must not be a symlink"
        )

    payload = json.loads(
        source.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise StateIntegrityError(
            "PROJECT_STATE must be a JSON object"
        )

    protected: set[str] = set()

    def walk(
        value: Any,
    ) -> None:
        if isinstance(
            value,
            dict,
        ):
            for key, nested in value.items():
                if (
                    isinstance(
                        key,
                        str,
                    )
                    and _FORMAL_KEY_RE.search(
                        key
                    )
                ):
                    for candidate in _collect_strings(
                        nested
                    ):
                        candidate = candidate.strip()

                        if candidate:
                            protected.add(
                                candidate
                            )

                walk(
                    nested
                )

        elif isinstance(
            value,
            list,
        ):
            for nested in value:
                walk(
                    nested
                )

    walk(
        payload
    )

    return tuple(
        sorted(
            protected
        )
    )


def _readonly_connection(
    database: Path,
) -> sqlite3.Connection:
    resolved = (
        database
        .expanduser()
        .resolve()
    )

    uri = (
        "file:"
        + quote(
            str(resolved)
        )
        + "?mode=ro"
    )

    connection = sqlite3.connect(
        uri,
        uri=True,
    )

    connection.row_factory = (
        sqlite3.Row
    )

    return connection


def _parse_timestamp(
    value: Optional[str],
) -> Optional[datetime]:
    if value is None:
        return None

    try:
        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None


def _checkpoint_payload(
    connection: sqlite3.Connection,
    run_id: str,
) -> Optional[dict[str, Any]]:
    row = connection.execute(
        """
        SELECT payload_json
        FROM checkpoints
        WHERE run_id = ?
        ORDER BY created_at DESC,
                 checkpoint_id DESC
        LIMIT 1
        """,
        (run_id,),
    ).fetchone()

    if row is None:
        return None

    try:
        payload = json.loads(
            row["payload_json"]
        )
    except (
        TypeError,
        json.JSONDecodeError,
    ):
        return None

    if not isinstance(
        payload,
        dict,
    ):
        return None

    return payload


def _checkpoint_is_resume_evidence(
    payload: Optional[
        dict[str, Any]
    ],
    *,
    current_state: str,
) -> bool:
    if payload is None:
        return False

    try:
        validate_checkpoint_schema_version(
            payload
        )
    except StateIntegrityError:
        return False

    if payload.get(
        "state"
    ) != current_state:
        return False

    required = (
        "attempt",
        "repo_path",
        "run_dir",
        "base_sha",
        "current_diff_hash",
    )

    return all(
        key in payload
        for key in required
    )


def _load_run_plans(
    *,
    state_db: Path,
    protected_run_prefixes: tuple[
        str,
        ...
    ],
    older_than_seconds: float,
    now: datetime,
) -> tuple[
    list[_RunPlan],
    set[str],
]:
    database = (
        state_db
        .expanduser()
    )

    if not database.exists():
        return [], set()

    if database.is_symlink():
        raise StateIntegrityError(
            "state database must not be a symlink"
        )

    if not database.is_file():
        raise StateIntegrityError(
            "state database must be a file"
        )

    connection = _readonly_connection(
        database
    )

    try:
        rows = connection.execute(
            """
            SELECT
                run_id,
                status,
                current_state,
                finished_at
            FROM runs
            ORDER BY started_at, run_id
            """
        ).fetchall()

        plans: list[_RunPlan] = []
        known_run_ids: set[str] = set()

        for row in rows:
            run_id = str(
                row["run_id"]
            )

            known_run_ids.add(
                run_id
            )

            status = str(
                row["status"]
            )

            current_state = str(
                row["current_state"]
            )

            checkpoint = (
                _checkpoint_payload(
                    connection,
                    run_id,
                )
            )

            protected = is_protected_run(
                run_id,
                protected_run_prefixes=(
                    protected_run_prefixes
                ),
            )

            facts = ArtifactRetentionFacts(
                run_id=run_id,
                status=status,
                current_state=(
                    current_state
                ),
                finished_at=(
                    _parse_timestamp(
                        row["finished_at"]
                    )
                ),
                has_resume_checkpoint=(
                    _checkpoint_is_resume_evidence(
                        checkpoint,
                        current_state=(
                            current_state
                        ),
                    )
                ),
                protected=protected,
            )

            decision = (
                classify_artifact_retention(
                    facts,
                    older_than_seconds=(
                        older_than_seconds
                    ),
                    now=now,
                )
            )

            completed = (
                connection.execute(
                    """
                    SELECT 1
                    FROM events
                    WHERE run_id = ?
                      AND event_type = ?
                    LIMIT 1
                    """,
                    (
                        run_id,
                        RETENTION_COMPLETED_EVENT,
                    ),
                ).fetchone()
                is not None
            )

            plans.append(
                _RunPlan(
                    run_id=run_id,
                    decision=decision,
                    checkpoint=checkpoint,
                    purge_completed=completed,
                )
            )

        return (
            plans,
            known_run_ids,
        )

    finally:
        connection.close()


def _run_path_context(
    *,
    checkpoint: Optional[
        dict[str, Any]
    ],
    configured_reports_root: Path,
) -> Optional[
    tuple[
        Path,
        Path,
        Path,
        Path,
    ]
]:
    if checkpoint is None:
        return None

    raw_run_dir = checkpoint.get(
        "run_dir"
    )

    raw_repo_path = checkpoint.get(
        "repo_path"
    )

    raw_canonical = checkpoint.get(
        "canonical_repo_path"
    )

    if not all(
        isinstance(
            value,
            str,
        )
        and value.strip()
        for value in (
            raw_run_dir,
            raw_repo_path,
            raw_canonical,
        )
    ):
        return None

    configured_root = (
        configured_reports_root
        .expanduser()
        .resolve()
    )

    run_dir = Path(
        raw_run_dir
    ).expanduser()

    worktree = Path(
        raw_repo_path
    ).expanduser()

    canonical = Path(
        raw_canonical
    ).expanduser()

    if (
        run_dir.exists()
        and run_dir.is_symlink()
    ):
        return None

    resolved_run = (
        run_dir.resolve()
    )

    try:
        resolved_run.relative_to(
            configured_root
        )
    except ValueError:
        return None

    expected_worktree = (
        resolved_run / "worktree"
    )

    if (
        worktree.resolve()
        != expected_worktree
    ):
        return None

    return (
        resolved_run.parent,
        resolved_run,
        expected_worktree,
        canonical,
    )


def _artifact_retention_items(
    *,
    plans: list[_RunPlan],
    configured_reports_root: Path,
    state_db: Path,
    dry_run: bool,
) -> list[GCReportItem]:
    items: list[GCReportItem] = []

    executable: list[
        tuple[
            _RunPlan,
            tuple[
                Path,
                Path,
                Path,
                Path,
            ],
        ]
    ] = []

    for plan in plans:
        decision = plan.decision

        if (
            decision.action
            != PlannedAction.GC_CANDIDATE
        ):
            items.append(
                GCReportItem(
                    kind="artifact",
                    resource=(
                        f"run:{plan.run_id}"
                    ),
                    classification=(
                        decision.classification.value
                    ),
                    action=(
                        decision.action.value
                    ),
                    reason=decision.reason,
                )
            )

            continue

        context = _run_path_context(
            checkpoint=plan.checkpoint,
            configured_reports_root=(
                configured_reports_root
            ),
        )

        if context is None:
            items.append(
                GCReportItem(
                    kind="artifact",
                    resource=(
                        f"run:{plan.run_id}"
                    ),
                    classification=(
                        Classification.UNKNOWN.value
                    ),
                    action=(
                        PlannedAction.PRESERVE.value
                    ),
                    reason=(
                        "expired run lacks a safe "
                        "retention path context"
                    ),
                )
            )

            continue

        executable.append(
            (
                plan,
                context,
            )
        )

    if dry_run:
        for (
            plan,
            (
                execution_root,
                run_dir,
                worktree,
                canonical,
            ),
        ) in executable:
            try:
                result = (
                    execute_artifact_retention(
                        decision=plan.decision,
                        reports_root=(
                            execution_root
                        ),
                        run_dir=run_dir,
                        canonical_repo=canonical,
                        worktree_path=worktree,
                        store=_EventProbe(
                            completed=(
                                plan.purge_completed
                            )
                        ),
                        dry_run=True,
                    )
                )

                action = (
                    PlannedAction.PRESERVE.value
                    if result.already_completed
                    else
                    PlannedAction.GC_CANDIDATE.value
                )

                classification = (
                    Classification.TERMINAL_RETAINED.value
                    if result.already_completed
                    else
                    plan.decision.classification.value
                )

                items.append(
                    GCReportItem(
                        kind="artifact",
                        resource=(
                            f"run:{plan.run_id}"
                        ),
                        classification=(
                            classification
                        ),
                        action=action,
                        reason=result.reason,
                    )
                )

            except (
                AIVPError,
                StateIntegrityError,
                OSError,
                subprocess.SubprocessError,
            ) as exc:
                items.append(
                    GCReportItem(
                        kind="artifact",
                        resource=(
                            f"run:{plan.run_id}"
                        ),
                        classification=(
                            Classification.UNKNOWN.value
                        ),
                        action=(
                            PlannedAction.PRESERVE.value
                        ),
                        reason=(
                            "artifact purge blocked: "
                            f"{exc}"
                        ),
                    )
                )

        return items

    if not executable:
        return items

    with SQLiteStateStore(
        state_db
    ) as store:
        for (
            plan,
            (
                execution_root,
                run_dir,
                worktree,
                canonical,
            ),
        ) in executable:
            try:
                result = (
                    execute_artifact_retention(
                        decision=plan.decision,
                        reports_root=(
                            execution_root
                        ),
                        run_dir=run_dir,
                        canonical_repo=canonical,
                        worktree_path=worktree,
                        store=store,
                        dry_run=False,
                    )
                )

                items.append(
                    GCReportItem(
                        kind="artifact",
                        resource=(
                            f"run:{plan.run_id}"
                        ),
                        classification=(
                            plan.decision
                            .classification
                            .value
                        ),
                        action=(
                            "preserve"
                            if result.already_completed
                            else "removed"
                        ),
                        reason=result.reason,
                    )
                )

            except (
                AIVPError,
                StateIntegrityError,
                OSError,
                subprocess.SubprocessError,
            ) as exc:
                items.append(
                    GCReportItem(
                        kind="artifact",
                        resource=(
                            f"run:{plan.run_id}"
                        ),
                        classification=(
                            Classification.UNKNOWN.value
                        ),
                        action=(
                            PlannedAction.PRESERVE.value
                        ),
                        reason=(
                            "artifact purge blocked: "
                            f"{exc}"
                        ),
                    )
                )

    return items


def _infer_canonical_repo(
    worktree: Path,
) -> Optional[Path]:
    cp = subprocess.run(
        [
            "git",
            "-C",
            str(worktree),
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    if cp.returncode != 0:
        return None

    raw = cp.stdout.strip()

    if not raw:
        return None

    common_dir = Path(
        raw
    ).expanduser().resolve()

    if common_dir.name != ".git":
        return None

    canonical = (
        common_dir.parent
    )

    if not canonical.is_dir():
        return None

    return canonical


def _worktree_candidates(
    reports_root: Path,
) -> list[Path]:
    root = (
        reports_root
        .expanduser()
    )

    if not root.exists():
        return []

    if (
        root.is_symlink()
        or not root.is_dir()
    ):
        raise StateIntegrityError(
            "reports root must be "
            "a real directory"
        )

    found: list[Path] = []

    for (
        current_dir,
        directory_names,
        _,
    ) in os.walk(
        root,
        followlinks=False,
    ):
        current = Path(
            current_dir
        )

        if "worktree" in directory_names:
            candidate = (
                current / "worktree"
            )

            found.append(
                candidate
            )

            directory_names.remove(
                "worktree"
            )

    return sorted(
        found
    )


def _orphan_worktree_items(
    *,
    reports_root: Path,
    known_run_ids: set[str],
    protected_run_prefixes: tuple[
        str,
        ...
    ],
    older_than_seconds: float,
    dry_run: bool,
    now: datetime,
) -> list[GCReportItem]:
    items: list[GCReportItem] = []

    for worktree in _worktree_candidates(
        reports_root
    ):
        run_dir = worktree.parent
        run_id = run_dir.name

        if run_id in known_run_ids:
            continue

        if is_protected_run(
            run_id,
            protected_run_prefixes=(
                protected_run_prefixes
            ),
        ):
            items.append(
                GCReportItem(
                    kind="worktree",
                    resource=str(
                        worktree
                    ),
                    classification=(
                        Classification.PROTECTED.value
                    ),
                    action=(
                        PlannedAction.PRESERVE.value
                    ),
                    reason=(
                        "worktree belongs to "
                        "explicitly protected evidence"
                    ),
                )
            )

            continue

        try:
            mtime = datetime.fromtimestamp(
                run_dir.stat().st_mtime,
                tz=timezone.utc,
            )

            age = (
                now - mtime
            ).total_seconds()

        except OSError as exc:
            items.append(
                GCReportItem(
                    kind="worktree",
                    resource=str(
                        worktree
                    ),
                    classification=(
                        Classification.UNKNOWN.value
                    ),
                    action=(
                        PlannedAction.PRESERVE.value
                    ),
                    reason=(
                        "cannot inspect orphan age: "
                        f"{exc}"
                    ),
                )
            )

            continue

        if age < 0:
            items.append(
                GCReportItem(
                    kind="worktree",
                    resource=str(
                        worktree
                    ),
                    classification=(
                        Classification.UNKNOWN.value
                    ),
                    action=(
                        PlannedAction.PRESERVE.value
                    ),
                    reason=(
                        "worktree timestamp "
                        "is in the future"
                    ),
                )
            )

            continue

        if (
            age
            < older_than_seconds
        ):
            items.append(
                GCReportItem(
                    kind="worktree",
                    resource=str(
                        worktree
                    ),
                    classification=(
                        Classification.ORPHANED.value
                    ),
                    action=(
                        PlannedAction.PRESERVE.value
                    ),
                    reason=(
                        "orphan worktree is still "
                        "within retention"
                    ),
                )
            )

            continue

        canonical = (
            _infer_canonical_repo(
                worktree
            )
        )

        if canonical is None:
            items.append(
                GCReportItem(
                    kind="worktree",
                    resource=str(
                        worktree
                    ),
                    classification=(
                        Classification.UNKNOWN.value
                    ),
                    action=(
                        PlannedAction.PRESERVE.value
                    ),
                    reason=(
                        "cannot prove canonical "
                        "repository ownership"
                    ),
                )
            )

            continue

        try:
            owned = (
                worktree_owned_by_repo(
                    canonical_repo=(
                        canonical
                    ),
                    worktree_path=(
                        worktree
                    ),
                )
            )
        except (
            AIVPError,
            StateIntegrityError,
            OSError,
            subprocess.SubprocessError,
        ) as exc:
            items.append(
                GCReportItem(
                    kind="worktree",
                    resource=str(
                        worktree
                    ),
                    classification=(
                        Classification.UNKNOWN.value
                    ),
                    action=(
                        PlannedAction.PRESERVE.value
                    ),
                    reason=(
                        "ownership check failed: "
                        f"{exc}"
                    ),
                )
            )

            continue

        if not owned:
            items.append(
                GCReportItem(
                    kind="worktree",
                    resource=str(
                        worktree
                    ),
                    classification=(
                        Classification.UNKNOWN.value
                    ),
                    action=(
                        PlannedAction.PRESERVE.value
                    ),
                    reason=(
                        "worktree ownership "
                        "could not be proven"
                    ),
                )
            )

            continue

        try:
            result = remove_owned_worktree(
                canonical_repo=canonical,
                worktree_path=worktree,
                dry_run=dry_run,
                allow_dirty=False,
            )

            items.append(
                GCReportItem(
                    kind="worktree",
                    resource=str(
                        worktree
                    ),
                    classification=(
                        Classification.ORPHANED.value
                    ),
                    action=(
                        PlannedAction.GC_CANDIDATE.value
                        if dry_run
                        else (
                            "removed"
                            if result.removed
                            else
                            PlannedAction.PRESERVE.value
                        )
                    ),
                    reason=result.reason,
                )
            )

        except (
            AIVPError,
            StateIntegrityError,
            OSError,
            subprocess.SubprocessError,
        ) as exc:
            items.append(
                GCReportItem(
                    kind="worktree",
                    resource=str(
                        worktree
                    ),
                    classification=(
                        Classification.UNKNOWN.value
                    ),
                    action=(
                        PlannedAction.PRESERVE.value
                    ),
                    reason=(
                        "orphan cleanup blocked: "
                        f"{exc}"
                    ),
                )
            )

    return items


def _generic_cleanup_items(
    *,
    kind: str,
    results: Iterable[Any],
) -> list[GCReportItem]:
    items: list[GCReportItem] = []

    for result in results:
        reason = str(
            result.reason
        )

        candidate = (
            bool(
                getattr(
                    result,
                    "removed",
                    False,
                )
            )
            or "would be removed"
            in reason.lower()
        )

        removed = bool(
            getattr(
                result,
                "removed",
                False,
            )
        )

        if kind == "cache":
            resource = str(
                getattr(
                    result,
                    "resource",
                    "cache",
                )
            )
        else:
            resource = str(
                getattr(
                    result,
                    "container_id",
                    "container",
                )
            )

        items.append(
            GCReportItem(
                kind=kind,
                resource=resource,
                classification=(
                    Classification.EXPIRED.value
                    if candidate
                    else
                    Classification.TERMINAL_RETAINED.value
                ),
                action=(
                    "removed"
                    if removed
                    else (
                        PlannedAction.GC_CANDIDATE.value
                        if candidate
                        else
                        PlannedAction.PRESERVE.value
                    )
                ),
                reason=reason,
            )
        )

    return items


def run_gc(
    *,
    older_than_seconds: float,
    reports_root: Path,
    state_db: Path,
    project_state: Path,
    cache_root: Optional[
        Path
    ] = None,
    dry_run: bool = True,
    now: Optional[datetime] = None,
) -> list[GCReportItem]:
    if older_than_seconds <= 0:
        raise ValueError(
            "older_than_seconds must "
            "be greater than zero"
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

    protected = (
        _protected_run_prefixes(
            project_state
        )
    )

    plans, known_run_ids = (
        _load_run_plans(
            state_db=state_db,
            protected_run_prefixes=(
                protected
            ),
            older_than_seconds=(
                older_than_seconds
            ),
            now=current,
        )
    )

    items = (
        _artifact_retention_items(
            plans=plans,
            configured_reports_root=(
                reports_root
            ),
            state_db=state_db,
            dry_run=dry_run,
        )
    )

    items.extend(
        _orphan_worktree_items(
            reports_root=reports_root,
            known_run_ids=known_run_ids,
            protected_run_prefixes=(
                protected
            ),
            older_than_seconds=(
                older_than_seconds
            ),
            dry_run=dry_run,
            now=current,
        )
    )

    effective_cache_root = (
        cache_root
        if cache_root is not None
        else (
            state_db
            .expanduser()
            .parent
            / "cache"
        )
    )

    try:
        cache_results = cleanup_cache(
            cache_root=(
                effective_cache_root
            ),
            older_than_seconds=(
                older_than_seconds
            ),
            dry_run=dry_run,
            now=current,
        )

        items.extend(
            _generic_cleanup_items(
                kind="cache",
                results=cache_results,
            )
        )

    except Exception as exc:
        items.append(
            GCReportItem(
                kind="cache",
                resource=str(
                    effective_cache_root
                ),
                classification="error",
                action="preserve",
                reason=(
                    "cache GC failed: "
                    f"{exc}"
                ),
            )
        )

    try:
        docker_results = (
            cleanup_stale_containers(
                older_than_seconds=(
                    older_than_seconds
                ),
                dry_run=dry_run,
                now=current,
            )
        )

        items.extend(
            _generic_cleanup_items(
                kind="docker",
                results=docker_results,
            )
        )

    except Exception as exc:
        items.append(
            GCReportItem(
                kind="docker",
                resource="AIVP-owned containers",
                classification="error",
                action="preserve",
                reason=(
                    "Docker GC failed: "
                    f"{exc}"
                ),
            )
        )

    return items
