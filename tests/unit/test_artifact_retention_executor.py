from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.errors import StateIntegrityError
from aivp.maintenance.artifact_retention import (
    ArtifactRetentionDecision,
)
from aivp.maintenance.artifact_retention_executor import (
    RETENTION_COMPLETED_EVENT,
    RETENTION_INTENT_EVENT,
    execute_artifact_retention,
)
from aivp.maintenance.gc import (
    Classification,
    PlannedAction,
)
from aivp.maintenance.worktree_gc import (
    remove_owned_worktree,
)
from aivp.state.sqlite import SQLiteStateStore


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
    name: str,
) -> Path:
    repo = root / name
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
        "AIVP Test",
    )

    run_git(
        repo,
        "config",
        "user.email",
        "aivp@example.invalid",
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


def make_worktree(
    canonical_repo: Path,
    worktree_path: Path,
) -> None:
    worktree_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_git(
        canonical_repo,
        "worktree",
        "add",
        "--detach",
        str(worktree_path),
        "HEAD",
    )


def expired_decision(
    run_id: str,
) -> ArtifactRetentionDecision:
    return ArtifactRetentionDecision(
        run_id=run_id,
        classification=(
            Classification.EXPIRED
        ),
        action=(
            PlannedAction.GC_CANDIDATE
        ),
        age_seconds=864000.0,
        reason="fixture expired run",
    )


def preserve_decision(
    run_id: str,
) -> ArtifactRetentionDecision:
    return ArtifactRetentionDecision(
        run_id=run_id,
        classification=(
            Classification.PROTECTED
        ),
        action=PlannedAction.PRESERVE,
        age_seconds=None,
        reason="fixture protected run",
    )


class ArtifactRetentionExecutorTests(
    unittest.TestCase
):
    def test_dry_run_preserves_filesystem_and_events(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(
                root,
                "repo",
            )
            reports = root / "reports"
            reports.mkdir()
            run_id = "run-old"
            run_dir = reports / run_id
            worktree = (
                run_dir / "worktree"
            )

            make_worktree(
                repo,
                worktree,
            )

            with SQLiteStateStore(
                root / "state.db"
            ) as store:
                result = (
                    execute_artifact_retention(
                        decision=expired_decision(
                            run_id
                        ),
                        reports_root=reports,
                        run_dir=run_dir,
                        canonical_repo=repo,
                        worktree_path=worktree,
                        store=store,
                        dry_run=True,
                    )
                )

                self.assertTrue(
                    result.dry_run
                )
                self.assertTrue(
                    run_dir.exists()
                )
                self.assertTrue(
                    worktree.exists()
                )
                self.assertFalse(
                    store.event_exists(
                        run_id=run_id,
                        event_type=(
                            RETENTION_INTENT_EVENT
                        ),
                    )
                )

    def test_real_execution_removes_owned_payload(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(
                root,
                "repo",
            )
            reports = root / "reports"
            reports.mkdir()
            run_id = "run-expired"
            run_dir = reports / run_id
            worktree = (
                run_dir / "worktree"
            )

            make_worktree(
                repo,
                worktree,
            )

            (
                run_dir / "status.json"
            ).write_text(
                "{}\n",
                encoding="utf-8",
            )

            with SQLiteStateStore(
                root / "state.db"
            ) as store:
                result = (
                    execute_artifact_retention(
                        decision=expired_decision(
                            run_id
                        ),
                        reports_root=reports,
                        run_dir=run_dir,
                        canonical_repo=repo,
                        worktree_path=worktree,
                        store=store,
                        dry_run=False,
                    )
                )

                self.assertTrue(
                    result.removed_worktree
                )
                self.assertTrue(
                    result.removed_run_dir
                )
                self.assertFalse(
                    run_dir.exists()
                )

                self.assertTrue(
                    store.event_exists(
                        run_id=run_id,
                        event_type=(
                            RETENTION_INTENT_EVENT
                        ),
                    )
                )

                self.assertTrue(
                    store.event_exists(
                        run_id=run_id,
                        event_type=(
                            RETENTION_COMPLETED_EVENT
                        ),
                    )
                )

    def test_artifact_rows_remain_as_history(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(
                root,
                "repo",
            )
            reports = root / "reports"
            reports.mkdir()
            run_id = "run-history"
            run_dir = reports / run_id
            worktree = (
                run_dir / "worktree"
            )

            make_worktree(
                repo,
                worktree,
            )

            artifact_file = (
                run_dir / "artifact.json"
            )

            artifact_file.write_text(
                "{}\n",
                encoding="utf-8",
            )

            with SQLiteStateStore(
                root / "state.db"
            ) as store:
                store.record_artifact(
                    artifact_id="artifact-1",
                    run_id=run_id,
                    artifact_type="fixture",
                    path=artifact_file,
                    sha256="0" * 64,
                    size_bytes=3,
                )

                execute_artifact_retention(
                    decision=expired_decision(
                        run_id
                    ),
                    reports_root=reports,
                    run_dir=run_dir,
                    canonical_repo=repo,
                    worktree_path=worktree,
                    store=store,
                    dry_run=False,
                )

                rows = store.artifacts_for_run(
                    run_id
                )

                self.assertEqual(
                    len(rows),
                    1,
                )

                self.assertFalse(
                    Path(rows[0]["path"]).exists()
                )

    def test_preserve_decision_never_mutates(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(
                root,
                "repo",
            )
            reports = root / "reports"
            reports.mkdir()
            run_id = "run-protected"
            run_dir = reports / run_id
            worktree = (
                run_dir / "worktree"
            )

            make_worktree(
                repo,
                worktree,
            )

            with SQLiteStateStore(
                root / "state.db"
            ) as store:
                result = (
                    execute_artifact_retention(
                        decision=preserve_decision(
                            run_id
                        ),
                        reports_root=reports,
                        run_dir=run_dir,
                        canonical_repo=repo,
                        worktree_path=worktree,
                        store=store,
                        dry_run=False,
                    )
                )

                self.assertFalse(
                    result.removed_run_dir
                )
                self.assertTrue(
                    run_dir.exists()
                )
                self.assertTrue(
                    worktree.exists()
                )

    def test_dirty_worktree_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(
                root,
                "repo",
            )
            reports = root / "reports"
            reports.mkdir()
            run_id = "run-dirty"
            run_dir = reports / run_id
            worktree = (
                run_dir / "worktree"
            )

            make_worktree(
                repo,
                worktree,
            )

            (
                worktree / "README.md"
            ).write_text(
                "dirty\n",
                encoding="utf-8",
            )

            with SQLiteStateStore(
                root / "state.db"
            ) as store:
                with self.assertRaises(
                    Exception
                ):
                    execute_artifact_retention(
                        decision=expired_decision(
                            run_id
                        ),
                        reports_root=reports,
                        run_dir=run_dir,
                        canonical_repo=repo,
                        worktree_path=worktree,
                        store=store,
                        dry_run=False,
                    )

                self.assertTrue(
                    run_dir.exists()
                )
                self.assertTrue(
                    worktree.exists()
                )

                self.assertTrue(
                    store.event_exists(
                        run_id=run_id,
                        event_type=(
                            RETENTION_INTENT_EVENT
                        ),
                    )
                )

                self.assertFalse(
                    store.event_exists(
                        run_id=run_id,
                        event_type=(
                            RETENTION_COMPLETED_EVENT
                        ),
                    )
                )

    def test_run_dir_must_be_direct_owned_child(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(
                root,
                "repo",
            )
            reports = root / "reports"
            reports.mkdir()
            outside = root / "outside"
            outside.mkdir()
            run_id = "run-outside"
            run_dir = (
                outside / run_id
            )
            worktree = (
                run_dir / "worktree"
            )

            with SQLiteStateStore(
                root / "state.db"
            ) as store:
                with self.assertRaises(
                    StateIntegrityError
                ):
                    execute_artifact_retention(
                        decision=expired_decision(
                            run_id
                        ),
                        reports_root=reports,
                        run_dir=run_dir,
                        canonical_repo=repo,
                        worktree_path=worktree,
                        store=store,
                        dry_run=False,
                    )

    def test_retry_after_filesystem_purge_completes_event(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(
                root,
                "repo",
            )
            reports = root / "reports"
            reports.mkdir()
            run_id = "run-retry"
            run_dir = reports / run_id
            worktree = (
                run_dir / "worktree"
            )

            run_dir.mkdir()

            with SQLiteStateStore(
                root / "state.db"
            ) as store:
                store.record_event(
                    run_id=run_id,
                    event_type=(
                        RETENTION_INTENT_EVENT
                    ),
                    payload={
                        "fixture": True,
                    },
                )

                shutil.rmtree(
                    run_dir
                )

                result = (
                    execute_artifact_retention(
                        decision=expired_decision(
                            run_id
                        ),
                        reports_root=reports,
                        run_dir=run_dir,
                        canonical_repo=repo,
                        worktree_path=worktree,
                        store=store,
                        dry_run=False,
                    )
                )

                self.assertFalse(
                    result.removed_run_dir
                )

                self.assertTrue(
                    store.event_exists(
                        run_id=run_id,
                        event_type=(
                            RETENTION_COMPLETED_EVENT
                        ),
                    )
                )

    def test_completed_purge_is_idempotent(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = make_repo(
                root,
                "repo",
            )
            reports = root / "reports"
            reports.mkdir()
            run_id = "run-idempotent"
            run_dir = reports / run_id
            worktree = (
                run_dir / "worktree"
            )

            run_dir.mkdir()

            with SQLiteStateStore(
                root / "state.db"
            ) as store:
                first = (
                    execute_artifact_retention(
                        decision=expired_decision(
                            run_id
                        ),
                        reports_root=reports,
                        run_dir=run_dir,
                        canonical_repo=repo,
                        worktree_path=worktree,
                        store=store,
                        dry_run=False,
                    )
                )

                second = (
                    execute_artifact_retention(
                        decision=expired_decision(
                            run_id
                        ),
                        reports_root=reports,
                        run_dir=run_dir,
                        canonical_repo=repo,
                        worktree_path=worktree,
                        store=store,
                        dry_run=False,
                    )
                )

                self.assertFalse(
                    first.already_completed
                )
                self.assertTrue(
                    second.already_completed
                )

                count = store.connection.execute(
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
                ).fetchone()[0]

                self.assertEqual(
                    count,
                    1,
                )


if __name__ == "__main__":
    unittest.main()
