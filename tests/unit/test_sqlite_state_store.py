import json
import sqlite3
import tempfile
import unittest

from pathlib import Path

from aivp.errors import StateIntegrityError
from aivp.state.sqlite import (
    SCHEMA_VERSION,
    SQLiteStateStore,
)


CORE_TABLES = {
    "runs",
    "steps",
    "events",
    "artifacts",
    "model_calls",
    "checkpoints",
    "risk_assessments",
    "approvals",
}


class SQLiteStateStoreTests(
    unittest.TestCase
):
    def test_creates_core_schema_and_wal(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = (
                Path(tmp)
                / "state.db"
            )

            with SQLiteStateStore(
                db_path
            ) as store:
                self.assertEqual(
                    store.schema_version(),
                    SCHEMA_VERSION,
                )

                self.assertEqual(
                    store.journal_mode(),
                    "wal",
                )

                rows = (
                    store.connection.execute(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'table'
                        """
                    ).fetchall()
                )

                names = {
                    row["name"]
                    for row in rows
                }

                self.assertTrue(
                    CORE_TABLES
                    <= names
                )

    def test_checkpoint_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = (
                Path(tmp)
                / "state.db"
            )

            state = {
                "state": "GENERATED",
                "status": "RUNNING",
                "step_id": "generate",
                "attempt": 1,
            }

            with SQLiteStateStore(
                db_path
            ) as store:
                store.save(
                    "run-1",
                    state,
                )

                self.assertEqual(
                    store.load(
                        "run-1"
                    ),
                    state,
                )

    def test_survives_process_like_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = (
                Path(tmp)
                / "state.db"
            )

            first = {
                "state": "GENERATED",
                "status": "RUNNING",
            }

            store = SQLiteStateStore(
                db_path
            )

            store.save(
                "run-1",
                first,
            )

            store.close()

            reopened = SQLiteStateStore(
                db_path
            )

            try:
                self.assertEqual(
                    reopened.load(
                        "run-1"
                    ),
                    first,
                )
            finally:
                reopened.close()

    def test_latest_checkpoint_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = (
                Path(tmp)
                / "state.db"
            )

            with SQLiteStateStore(
                db_path
            ) as store:
                store.save(
                    "run-1",
                    {
                        "state": "GENERATED",
                    },
                )

                store.save(
                    "run-1",
                    {
                        "state": "VERIFIED",
                    },
                )

                self.assertEqual(
                    store.load(
                        "run-1"
                    ),
                    {
                        "state": "VERIFIED",
                    },
                )

    def test_future_schema_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = (
                Path(tmp)
                / "state.db"
            )

            connection = sqlite3.connect(
                str(db_path)
            )

            connection.execute(
                "PRAGMA user_version = 999"
            )

            connection.commit()
            connection.close()

            with self.assertRaises(
                RuntimeError
            ):
                SQLiteStateStore(
                    db_path
                )


    def test_artifacts_can_be_loaded_by_run(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = (
                Path(tmp) / "state.db"
            )

            artifact_path = (
                Path(tmp) / "result.txt"
            )

            artifact_path.write_text(
                "result",
                encoding="utf-8",
            )

            with SQLiteStateStore(
                db_path
            ) as store:
                store.record_artifact(
                    artifact_id="artifact-1",
                    run_id="run-1",
                    artifact_type="model-result",
                    path=artifact_path,
                    sha256="abc",
                    size_bytes=6,
                )

                rows = (
                    store.artifacts_for_run(
                        "run-1"
                    )
                )

                self.assertEqual(
                    len(rows),
                    1,
                )

                self.assertEqual(
                    rows[0]["artifact_id"],
                    "artifact-1",
                )


    def test_malformed_checkpoint_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = (
                Path(tmp) / "state.db"
            )

            with SQLiteStateStore(
                db_path
            ) as store:
                store.begin_run(
                    run_id="run-broken",
                    repo_path=Path(tmp),
                    base_sha="base",
                    current_state="GENERATED",
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
                        "broken",
                        "run-broken",
                        "GENERATED",
                        "{not-json",
                        "now",
                    ),
                )

                store.connection.commit()

                with self.assertRaises(
                    StateIntegrityError
                ):
                    (
                        store
                        .load_resume_checkpoint(
                            "run-broken"
                        )
                    )

    def test_checkpoint_state_tamper_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = (
                Path(tmp) / "state.db"
            )

            with SQLiteStateStore(
                db_path
            ) as store:
                store.begin_run(
                    run_id="run-tampered",
                    repo_path=Path(tmp),
                    base_sha="base",
                    current_state="GENERATED",
                )

                payload = {
                    "state": "VERIFIED",
                    "attempt": 1,
                    "repo_path": str(
                        Path(tmp)
                    ),
                    "run_dir": str(
                        Path(tmp)
                    ),
                    "base_sha": "base",
                    "current_diff_hash": (
                        "diff"
                    ),
                    "counters": {},
                }

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
                        "tampered",
                        "run-tampered",
                        "GENERATED",
                        json.dumps(payload),
                        "now",
                    ),
                )

                store.connection.commit()

                with self.assertRaises(
                    StateIntegrityError
                ):
                    (
                        store
                        .load_resume_checkpoint(
                            "run-tampered"
                        )
                    )


    def test_model_call_ledger_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.db"

            with SQLiteStateStore(db_path) as store:
                store.begin_run(
                    run_id="run-model",
                    repo_path=Path(tmp),
                    base_sha="base",
                    current_state="GENERATING",
                )

                store.record_model_call(
                    call_id="call-1",
                    run_id="run-model",
                    step_id="generate-1",
                    provider="openai",
                    model="test-model",
                    input_tokens=100,
                    cached_tokens=25,
                    output_tokens=40,
                    latency_ms=1234,
                    cost_usd=0.0123,
                    status="SUCCEEDED",
                )

                rows = store.model_calls_for_run(
                    "run-model"
                )

                self.assertEqual(len(rows), 1)

                row = rows[0]

                self.assertEqual(
                    row["call_id"],
                    "call-1",
                )
                self.assertEqual(
                    row["provider"],
                    "openai",
                )
                self.assertEqual(
                    row["model"],
                    "test-model",
                )
                self.assertEqual(
                    row["input_tokens"],
                    100,
                )
                self.assertEqual(
                    row["cached_tokens"],
                    25,
                )
                self.assertEqual(
                    row["output_tokens"],
                    40,
                )
                self.assertEqual(
                    row["latency_ms"],
                    1234,
                )
                self.assertAlmostEqual(
                    row["cost_usd"],
                    0.0123,
                )
                self.assertEqual(
                    row["status"],
                    "SUCCEEDED",
                )


if __name__ == "__main__":
    unittest.main()
