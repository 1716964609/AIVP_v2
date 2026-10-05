from __future__ import annotations

import json
import tempfile
import unittest

from pathlib import Path

from aivp.errors import (
    StateIntegrityError,
)
from aivp.state.sqlite import (
    SQLiteStateStore,
)

from aivp.application import (
    _execute,
    _finalize_durable_run,
)


class TerminalRunLifecycleTests(
    unittest.TestCase
):
    def make_running_run(
        self,
        store: SQLiteStateStore,
        run_id: str = "run-1",
    ) -> None:
        store.save(
            run_id,
            {
                "state": "VERIFIED",
                "status": "RUNNING",
            },
        )

    def test_finalize_run_marks_terminal(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"

            with SQLiteStateStore(db) as store:
                self.make_running_run(
                    store
                )

                store.finalize_run(
                    run_id="run-1",
                    status="AUTO_FINISHED",
                )

                row = store.connection.execute(
                    """
                    SELECT
                        status,
                        current_state,
                        finished_at
                    FROM runs
                    WHERE run_id = ?
                    """,
                    ("run-1",),
                ).fetchone()

                self.assertEqual(
                    row["status"],
                    "AUTO_FINISHED",
                )

                self.assertEqual(
                    row["current_state"],
                    "AUTO_FINISHED",
                )

                self.assertIsNotNone(
                    row["finished_at"]
                )

                store.finalize_run(
                    run_id="run-1",
                    status="AUTO_FINISHED",
                )

    def test_finalize_rejects_non_terminal(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"

            with SQLiteStateStore(db) as store:
                self.make_running_run(
                    store
                )

                with self.assertRaises(
                    StateIntegrityError
                ):
                    store.finalize_run(
                        run_id="run-1",
                        status="RUNNING",
                    )

    def test_terminal_run_is_not_resumable(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"

            with SQLiteStateStore(db) as store:
                self.make_running_run(
                    store
                )

                store.finalize_run(
                    run_id="run-1",
                    status="HUMAN_REQUIRED",
                )

                with self.assertRaises(
                    StateIntegrityError
                ):
                    store.load_resume_checkpoint(
                        "run-1"
                    )

    def test_status_artifact_finalizes_store(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "state.db"
            run_dir = root / "run"
            run_dir.mkdir()

            (
                run_dir / "status.json"
            ).write_text(
                json.dumps(
                    {
                        "status":
                        "AUTO_FINISHED"
                    }
                ),
                encoding="utf-8",
            )

            with SQLiteStateStore(db) as store:
                self.make_running_run(
                    store
                )

                _finalize_durable_run(
                    store=store,
                    run_id="run-1",
                    run_dir=run_dir,
                )

                row = store.connection.execute(
                    """
                    SELECT
                        status,
                        finished_at
                    FROM runs
                    WHERE run_id = ?
                    """,
                    ("run-1",),
                ).fetchone()

                self.assertEqual(
                    row["status"],
                    "AUTO_FINISHED",
                )

                self.assertIsNotNone(
                    row["finished_at"]
                )

    def test_execute_wires_terminal_finalizer(
        self,
    ):
        import inspect

        source = inspect.getsource(
            _execute
        )

        self.assertIn(
            "_finalize_durable_run",
            source,
        )

        self.assertIn(
            "durable is not None",
            source,
        )


if __name__ == "__main__":
    unittest.main()
