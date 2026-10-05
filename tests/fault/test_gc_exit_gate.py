from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest

from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from aivp.cli import main
from aivp.maintenance.artifact_retention_executor import (
    RETENTION_COMPLETED_EVENT,
)
from aivp.maintenance.gc_command import (
    run_gc,
)
from aivp.state.sqlite import (
    SQLiteStateStore,
)


NOW = datetime(
    2026,
    10,
    5,
    5,
    0,
    0,
    tzinfo=timezone.utc,
)

OLD_FINISHED_AT = (
    "2000-01-01T00:00:00+00:00"
)


def run_git(
    repo: Path,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            *args,
        ],
        check=True,
        text=True,
        capture_output=True,
    )


def make_repo(
    root: Path,
) -> Path:
    repo = root / "canonical-repo"

    repo.mkdir()

    run_git(
        repo,
        "init",
        "-q",
    )

    run_git(
        repo,
        "config",
        "user.name",
        "AIVP M9 Test",
    )

    run_git(
        repo,
        "config",
        "user.email",
        "aivp-m9@example.invalid",
    )

    (
        repo / "README.md"
    ).write_text(
        "fixture\n",
        encoding="utf-8",
    )

    run_git(
        repo,
        "add",
        "README.md",
    )

    run_git(
        repo,
        "commit",
        "-q",
        "-m",
        "fixture",
    )

    return repo


def repo_head(
    repo: Path,
) -> str:
    return run_git(
        repo,
        "rev-parse",
        "HEAD",
    ).stdout.strip()


def make_worktree(
    *,
    repo: Path,
    run_dir: Path,
) -> Path:
    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    worktree = (
        run_dir / "worktree"
    )

    run_git(
        repo,
        "worktree",
        "add",
        "--detach",
        str(worktree),
        "HEAD",
    )

    return worktree


def write_project_state(
    destination: Path,
    *,
    protected_run_id: str | None = None,
) -> None:
    payload: dict[str, object] = {}

    if protected_run_id is not None:
        payload["formal_evidence"] = {
            "formal_run": protected_run_id,
        }

    destination.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def record_run(
    *,
    state_db: Path,
    run_id: str,
    canonical_repo: Path,
    run_dir: Path,
    worktree: Path,
    current_state: str,
    terminal: bool,
) -> None:
    base_sha = repo_head(
        canonical_repo
    )

    checkpoint = {
        "checkpoint_schema_version": 1,
        "state": current_state,
        "attempt": 1,
        "repo_path": str(
            worktree.resolve()
        ),
        "canonical_repo_path": str(
            canonical_repo.resolve()
        ),
        "run_dir": str(
            run_dir.resolve()
        ),
        "base_sha": base_sha,
        "current_diff_hash": (
            "sha256:m9-exit-gate-fixture"
        ),
    }

    with SQLiteStateStore(
        state_db
    ) as store:
        store.begin_run(
            run_id=run_id,
            repo_path=worktree,
            base_sha=base_sha,
            current_state=current_state,
        )

        with store.connection:
            if terminal:
                store.connection.execute(
                    """
                    UPDATE runs
                    SET
                        status = ?,
                        current_state = ?,
                        finished_at = ?
                    WHERE run_id = ?
                    """,
                    (
                        current_state,
                        current_state,
                        OLD_FINISHED_AT,
                        run_id,
                    ),
                )

            store.connection.execute(
                """
                INSERT INTO checkpoints(
                    checkpoint_id,
                    run_id,
                    state,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    f"checkpoint-{run_id}",
                    run_id,
                    current_state,
                    json.dumps(
                        checkpoint,
                        sort_keys=True,
                    ),
                    NOW.isoformat(),
                ),
            )


def completed_event_exists(
    *,
    state_db: Path,
    run_id: str,
) -> bool:
    with SQLiteStateStore(
        state_db
    ) as store:
        return store.event_exists(
            run_id=run_id,
            event_type=(
                RETENTION_COMPLETED_EVENT
            ),
        )


class M9GCExitGateTests(
    unittest.TestCase
):
    def fixture_root(
        self,
    ):
        return tempfile.TemporaryDirectory()

    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_stale_containers",
        return_value=[],
    )
    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_cache",
        return_value=[],
    )
    def test_dry_run_preserves_expired_owned_run(
        self,
        _mock_cache,
        _mock_docker,
    ):
        with self.fixture_root() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()

            repo = make_repo(
                root
            )

            run_id = (
                "expired-dry-run"
            )

            run_dir = (
                reports / run_id
            )

            worktree = make_worktree(
                repo=repo,
                run_dir=run_dir,
            )

            state_db = (
                root / "state.db"
            )

            project_state = (
                root
                / "PROJECT_STATE.json"
            )

            write_project_state(
                project_state
            )

            record_run(
                state_db=state_db,
                run_id=run_id,
                canonical_repo=repo,
                run_dir=run_dir,
                worktree=worktree,
                current_state=(
                    "AUTO_FINISHED"
                ),
                terminal=True,
            )

            run_gc(
                older_than_seconds=1.0,
                reports_root=reports,
                state_db=state_db,
                project_state=(
                    project_state
                ),
                dry_run=True,
                now=NOW,
            )

            self.assertTrue(
                run_dir.exists()
            )

            self.assertTrue(
                worktree.exists()
            )

            self.assertFalse(
                completed_event_exists(
                    state_db=state_db,
                    run_id=run_id,
                )
            )

    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_stale_containers",
        return_value=[],
    )
    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_cache",
        return_value=[],
    )
    def test_apply_removes_only_expired_owned_run(
        self,
        _mock_cache,
        _mock_docker,
    ):
        with self.fixture_root() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()

            repo = make_repo(
                root
            )

            state_db = (
                root / "state.db"
            )

            project_state = (
                root
                / "PROJECT_STATE.json"
            )

            write_project_state(
                project_state
            )

            run_id = (
                "expired-apply"
            )

            run_dir = (
                reports / run_id
            )

            worktree = make_worktree(
                repo=repo,
                run_dir=run_dir,
            )

            record_run(
                state_db=state_db,
                run_id=run_id,
                canonical_repo=repo,
                run_dir=run_dir,
                worktree=worktree,
                current_state=(
                    "AUTO_FINISHED"
                ),
                terminal=True,
            )

            run_gc(
                older_than_seconds=1.0,
                reports_root=reports,
                state_db=state_db,
                project_state=(
                    project_state
                ),
                dry_run=False,
                now=NOW,
            )

            self.assertFalse(
                run_dir.exists()
            )

            self.assertTrue(
                completed_event_exists(
                    state_db=state_db,
                    run_id=run_id,
                )
            )

    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_stale_containers",
        return_value=[],
    )
    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_cache",
        return_value=[],
    )
    def test_resumable_interrupted_run_survives_apply(
        self,
        _mock_cache,
        _mock_docker,
    ):
        with self.fixture_root() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()

            repo = make_repo(
                root
            )

            run_id = (
                "interrupted-resumable"
            )

            run_dir = (
                reports / run_id
            )

            worktree = make_worktree(
                repo=repo,
                run_dir=run_dir,
            )

            state_db = (
                root / "state.db"
            )

            project_state = (
                root
                / "PROJECT_STATE.json"
            )

            write_project_state(
                project_state
            )

            record_run(
                state_db=state_db,
                run_id=run_id,
                canonical_repo=repo,
                run_dir=run_dir,
                worktree=worktree,
                current_state="GENERATED",
                terminal=False,
            )

            run_gc(
                older_than_seconds=1.0,
                reports_root=reports,
                state_db=state_db,
                project_state=(
                    project_state
                ),
                dry_run=False,
                now=NOW,
            )

            self.assertTrue(
                run_dir.exists()
            )

            self.assertTrue(
                worktree.exists()
            )

            self.assertFalse(
                completed_event_exists(
                    state_db=state_db,
                    run_id=run_id,
                )
            )

    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_stale_containers",
        return_value=[],
    )
    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_cache",
        return_value=[],
    )
    def test_formal_evidence_survives_apply(
        self,
        _mock_cache,
        _mock_docker,
    ):
        with self.fixture_root() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()

            repo = make_repo(
                root
            )

            run_id = (
                "formal-suite-protected"
            )

            run_dir = (
                reports / run_id
            )

            worktree = make_worktree(
                repo=repo,
                run_dir=run_dir,
            )

            state_db = (
                root / "state.db"
            )

            project_state = (
                root
                / "PROJECT_STATE.json"
            )

            write_project_state(
                project_state,
                protected_run_id=run_id,
            )

            record_run(
                state_db=state_db,
                run_id=run_id,
                canonical_repo=repo,
                run_dir=run_dir,
                worktree=worktree,
                current_state=(
                    "AUTO_FINISHED"
                ),
                terminal=True,
            )

            run_gc(
                older_than_seconds=1.0,
                reports_root=reports,
                state_db=state_db,
                project_state=(
                    project_state
                ),
                dry_run=False,
                now=NOW,
            )

            self.assertTrue(
                run_dir.exists()
            )

            self.assertTrue(
                worktree.exists()
            )

    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_stale_containers",
        return_value=[],
    )
    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_cache",
        return_value=[],
    )
    def test_dirty_orphan_worktree_survives_apply(
        self,
        _mock_cache,
        _mock_docker,
    ):
        with self.fixture_root() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()

            repo = make_repo(
                root
            )

            run_dir = (
                reports
                / "dirty-orphan"
            )

            worktree = make_worktree(
                repo=repo,
                run_dir=run_dir,
            )

            (
                worktree
                / "README.md"
            ).write_text(
                "dirty change\n",
                encoding="utf-8",
            )

            old_epoch = 1_000_000_000

            os.utime(
                run_dir,
                (
                    old_epoch,
                    old_epoch,
                ),
            )

            state_db = (
                root / "state.db"
            )

            with SQLiteStateStore(
                state_db
            ):
                pass

            project_state = (
                root
                / "PROJECT_STATE.json"
            )

            write_project_state(
                project_state
            )

            run_gc(
                older_than_seconds=1.0,
                reports_root=reports,
                state_db=state_db,
                project_state=(
                    project_state
                ),
                dry_run=False,
                now=NOW,
            )

            self.assertTrue(
                run_dir.exists()
            )

            self.assertTrue(
                worktree.exists()
            )

            status = run_git(
                worktree,
                "status",
                "--porcelain",
            ).stdout

            self.assertTrue(
                status.strip()
            )

    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_stale_containers",
        return_value=[],
    )
    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_cache",
        return_value=[],
    )
    def test_unknown_orphan_directory_survives_apply(
        self,
        _mock_cache,
        _mock_docker,
    ):
        with self.fixture_root() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()

            unknown_run = (
                reports
                / "unknown-orphan"
            )

            unknown_worktree = (
                unknown_run
                / "worktree"
            )

            unknown_worktree.mkdir(
                parents=True,
            )

            old_epoch = 1_000_000_000

            os.utime(
                unknown_run,
                (
                    old_epoch,
                    old_epoch,
                ),
            )

            state_db = (
                root / "state.db"
            )

            with SQLiteStateStore(
                state_db
            ):
                pass

            project_state = (
                root
                / "PROJECT_STATE.json"
            )

            write_project_state(
                project_state
            )

            run_gc(
                older_than_seconds=1.0,
                reports_root=reports,
                state_db=state_db,
                project_state=(
                    project_state
                ),
                dry_run=False,
                now=NOW,
            )

            self.assertTrue(
                unknown_run.exists()
            )

            self.assertTrue(
                unknown_worktree.exists()
            )

    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_stale_containers",
        return_value=[],
    )
    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_cache",
        return_value=[],
    )
    def test_second_apply_is_idempotent(
        self,
        _mock_cache,
        _mock_docker,
    ):
        with self.fixture_root() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()

            repo = make_repo(
                root
            )

            run_id = (
                "idempotent-expired"
            )

            run_dir = (
                reports / run_id
            )

            worktree = make_worktree(
                repo=repo,
                run_dir=run_dir,
            )

            state_db = (
                root / "state.db"
            )

            project_state = (
                root
                / "PROJECT_STATE.json"
            )

            write_project_state(
                project_state
            )

            record_run(
                state_db=state_db,
                run_id=run_id,
                canonical_repo=repo,
                run_dir=run_dir,
                worktree=worktree,
                current_state=(
                    "AUTO_FINISHED"
                ),
                terminal=True,
            )

            first = run_gc(
                older_than_seconds=1.0,
                reports_root=reports,
                state_db=state_db,
                project_state=(
                    project_state
                ),
                dry_run=False,
                now=NOW,
            )

            second = run_gc(
                older_than_seconds=1.0,
                reports_root=reports,
                state_db=state_db,
                project_state=(
                    project_state
                ),
                dry_run=False,
                now=NOW,
            )

            self.assertFalse(
                run_dir.exists()
            )

            self.assertTrue(
                completed_event_exists(
                    state_db=state_db,
                    run_id=run_id,
                )
            )

            with SQLiteStateStore(
                state_db
            ) as store:
                count = (
                    store.connection
                    .execute(
                        """
                        SELECT COUNT(*)
                        FROM events
                        WHERE run_id = ?
                          AND event_type = ?
                        """,
                        (
                            run_id,
                            RETENTION_COMPLETED_EVENT,
                        ),
                    )
                    .fetchone()[0]
                )

            self.assertEqual(
                count,
                1,
            )

            self.assertIsInstance(
                first,
                list,
            )

            self.assertIsInstance(
                second,
                list,
            )

    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_stale_containers",
        return_value=[],
    )
    @patch(
        "aivp.maintenance.gc_command."
        "cleanup_cache",
        return_value=[],
    )
    def test_cli_defaults_to_non_destructive_exit_gate(
        self,
        _mock_cache,
        _mock_docker,
    ):
        with self.fixture_root() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()

            repo = make_repo(
                root
            )

            run_id = (
                "cli-dry-run"
            )

            run_dir = (
                reports / run_id
            )

            worktree = make_worktree(
                repo=repo,
                run_dir=run_dir,
            )

            state_db = (
                root / "state.db"
            )

            project_state = (
                root
                / "PROJECT_STATE.json"
            )

            write_project_state(
                project_state
            )

            record_run(
                state_db=state_db,
                run_id=run_id,
                canonical_repo=repo,
                run_dir=run_dir,
                worktree=worktree,
                current_state=(
                    "AUTO_FINISHED"
                ),
                terminal=True,
            )

            output = io.StringIO()

            with redirect_stdout(
                output
            ):
                result = main(
                    [
                        "gc",
                        "--older-than",
                        "1s",
                        "--reports",
                        str(reports),
                        "--state-db",
                        str(state_db),
                        "--project-state",
                        str(project_state),
                    ]
                )

            self.assertEqual(
                result,
                0,
            )

            self.assertTrue(
                run_dir.exists()
            )

            self.assertIn(
                "GC_MODE=DRY_RUN",
                output.getvalue(),
            )


if __name__ == "__main__":
    unittest.main()
