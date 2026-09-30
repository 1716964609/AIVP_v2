from __future__ import annotations

import json
import sqlite3
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


SCHEMA_VERSION = 1


MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS runs(
    run_id TEXT PRIMARY KEY,
    task_id TEXT,
    repo_path TEXT,
    base_sha TEXT,
    status TEXT,
    current_state TEXT,
    policy_version TEXT,
    harness_version TEXT,
    pricing_version TEXT,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS steps(
    step_id TEXT PRIMARY KEY,
    run_id TEXT,
    step_type TEXT,
    attempt INTEGER,
    status TEXT,
    input_hash TEXT,
    output_hash TEXT,
    started_at TEXT,
    finished_at TEXT,
    error_class TEXT,
    retryable INTEGER
);

CREATE TABLE IF NOT EXISTS events(
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    step_id TEXT,
    ts TEXT,
    event_type TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS artifacts(
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT,
    type TEXT,
    path TEXT,
    sha256 TEXT,
    size_bytes INTEGER,
    sensitive INTEGER,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS model_calls(
    call_id TEXT PRIMARY KEY,
    run_id TEXT,
    step_id TEXT,
    provider TEXT,
    model TEXT,
    input_tokens INTEGER,
    cached_tokens INTEGER,
    output_tokens INTEGER,
    latency_ms INTEGER,
    cost_usd REAL,
    status TEXT
);

CREATE TABLE IF NOT EXISTS checkpoints(
    checkpoint_id TEXT PRIMARY KEY,
    run_id TEXT,
    state TEXT,
    payload_json TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS risk_assessments(
    assessment_id TEXT PRIMARY KEY,
    run_id TEXT,
    correctness TEXT,
    security TEXT,
    business_impact TEXT,
    blast_radius TEXT,
    reversibility TEXT,
    confidence REAL,
    result_json TEXT
);

CREATE TABLE IF NOT EXISTS approvals(
    approval_id TEXT PRIMARY KEY,
    run_id TEXT,
    capability TEXT,
    decision TEXT,
    actor TEXT,
    reason TEXT,
    created_at TEXT
);
"""


def _now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).astimezone().isoformat(
        timespec="seconds"
    )


class SQLiteStateStore:
    def __init__(
        self,
        path: Path,
    ):
        self.path = path
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.connection = sqlite3.connect(
            str(path)
        )

        self.connection.row_factory = (
            sqlite3.Row
        )

        self.connection.execute(
            "PRAGMA journal_mode=WAL"
        )

        self._migrate()

    def _migrate(self) -> None:
        version = self.connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

        if version > SCHEMA_VERSION:
            raise RuntimeError(
                "Database schema version "
                f"{version} is newer than "
                f"supported version "
                f"{SCHEMA_VERSION}"
            )

        if version < 1:
            self.connection.executescript(
                MIGRATION_1
            )

            self.connection.execute(
                "PRAGMA user_version = 1"
            )

            self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(
        self,
    ) -> "SQLiteStateStore":
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        self.close()

    def save(
        self,
        run_id: str,
        state: Dict[str, Any],
    ) -> None:
        now = _now_iso()

        current_state = str(
            state.get(
                "state",
                "UNKNOWN",
            )
        )

        self.connection.execute(
            """
            INSERT INTO runs(
                run_id,
                status,
                current_state,
                started_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                status = excluded.status,
                current_state = excluded.current_state
            """,
            (
                run_id,
                state.get(
                    "status"
                ),
                current_state,
                now,
            ),
        )

        checkpoint_id = str(
            uuid.uuid4()
        )

        self.connection.execute(
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
                checkpoint_id,
                run_id,
                current_state,
                json.dumps(
                    state,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                now,
            ),
        )

        self.connection.commit()

    def load(
        self,
        run_id: str,
    ) -> Optional[Dict[str, Any]]:
        row = self.connection.execute(
            """
            SELECT payload_json
            FROM checkpoints
            WHERE run_id = ?
            ORDER BY rowid DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()

        if row is None:
            return None

        return json.loads(
            row["payload_json"]
        )

    def schema_version(self) -> int:
        return self.connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

    def journal_mode(self) -> str:
        return str(
            self.connection.execute(
                "PRAGMA journal_mode"
            ).fetchone()[0]
        ).lower()
