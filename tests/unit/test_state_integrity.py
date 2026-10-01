import tempfile
import unittest

from datetime import datetime, timezone
from pathlib import Path

from aivp.errors import StateIntegrityError
from aivp.execution.runtime import (
    Budgets,
    Runtime,
)
from aivp.state.durable import (
    DurableExecution,
    complete_terminal_outcome,
)
from aivp.state.hashing import (
    sha256_file,
    sha256_json,
)
from aivp.state.integrity import (
    validate_artifact,
)
from aivp.state.sqlite import (
    SQLiteStateStore,
)


class StateIntegrityTests(
    unittest.TestCase
):
    def test_json_hash_is_deterministic(self):
        left = {
            "b": 2,
            "a": 1,
        }

        right = {
            "a": 1,
            "b": 2,
        }

        self.assertEqual(
            sha256_json(left),
            sha256_json(right),
        )

    def test_artifact_validation_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = (
                Path(tmp)
                / "artifact.txt"
            )

            path.write_text(
                "hello",
                encoding="utf-8",
            )

            validate_artifact(
                path=path,
                expected_sha256=sha256_file(
                    path
                ),
                expected_size_bytes=(
                    path.stat().st_size
                ),
            )

    def test_corrupted_artifact_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = (
                Path(tmp)
                / "artifact.txt"
            )

            path.write_text(
                "original",
                encoding="utf-8",
            )

            expected_hash = sha256_file(
                path
            )

            expected_size = (
                path.stat().st_size
            )

            path.write_text(
                "corrupt!",
                encoding="utf-8",
            )

            with self.assertRaises(
                StateIntegrityError
            ):
                validate_artifact(
                    path=path,
                    expected_sha256=expected_hash,
                    expected_size_bytes=expected_size,
                )

    def test_completed_step_and_checkpoint_are_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = (
                Path(tmp)
                / "state.db"
            )

            now = datetime.now(
                timezone.utc
            ).isoformat()

            with SQLiteStateStore(
                db_path
            ) as store:
                store.save(
                    "run-1",
                    {
                        "state": "GENERATING",
                        "status": "RUNNING",
                    },
                )

                store.complete_step(
                    step_id="run-1:generate:1",
                    run_id="run-1",
                    step_type="generate",
                    attempt=1,
                    input_hash="input-hash",
                    output_hash="output-hash",
                    started_at=now,
                    finished_at=now,
                    retryable=False,
                    checkpoint_state="GENERATED",
                    checkpoint_payload={
                        "state": "GENERATED",
                        "step_id": "run-1:generate:1",
                        "attempt": 1,
                        "output_hash": "output-hash",
                    },
                )

                step = store.load_step(
                    "run-1:generate:1"
                )

                self.assertIsNotNone(
                    step
                )

                self.assertEqual(
                    step["status"],
                    "SUCCEEDED",
                )

                checkpoint = store.load(
                    "run-1"
                )

                self.assertEqual(
                    checkpoint["state"],
                    "GENERATED",
                )

                self.assertEqual(
                    checkpoint["step_id"],
                    "run-1:generate:1",
                )

    def test_step_artifact_and_checkpoint_roll_back_together(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            db_path = root / "state.db"
            artifact_path = (
                root / "artifact.txt"
            )

            artifact_path.write_text(
                "durable artifact",
                encoding="utf-8",
            )

            now = datetime.now(
                timezone.utc
            ).isoformat()

            with SQLiteStateStore(
                db_path
            ) as store:
                # Deliberately do NOT create run-404.
                # UPDATE runs must fail the integrity
                # invariant and roll the whole DB
                # transaction back.
                with self.assertRaises(
                    StateIntegrityError
                ):
                    store.complete_step(
                        step_id=(
                            "run-404:"
                            "generate:1"
                        ),
                        run_id="run-404",
                        step_type="generate",
                        attempt=1,
                        input_hash="input",
                        output_hash="output",
                        started_at=now,
                        finished_at=now,
                        retryable=False,
                        checkpoint_state=(
                            "GENERATED"
                        ),
                        checkpoint_payload={
                            "state": (
                                "GENERATED"
                            ),
                            "attempt": 1,
                        },
                        artifacts=[
                            {
                                "artifact_id": (
                                    "artifact-404"
                                ),
                                "artifact_type": (
                                    "generated-diff"
                                ),
                                "path": (
                                    artifact_path
                                ),
                                "sha256": (
                                    sha256_file(
                                        artifact_path
                                    )
                                ),
                                "size_bytes": (
                                    artifact_path
                                    .stat()
                                    .st_size
                                ),
                            }
                        ],
                    )

                self.assertIsNone(
                    store.load_step(
                        "run-404:generate:1"
                    )
                )

                self.assertIsNone(
                    store.load_artifact(
                        "artifact-404"
                    )
                )

                checkpoint_count = (
                    store.connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM checkpoints
                        WHERE run_id = ?
                        """,
                        ("run-404",),
                    ).fetchone()[0]
                )

                self.assertEqual(
                    checkpoint_count,
                    0,
                )



    def test_terminal_outcome_is_persisted_atomically(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "state.db"

            repo = root / "repo"
            repo.mkdir()

            import subprocess

            subprocess.run(
                ["git", "init", "-q"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "config",
                    "user.email",
                    "aivp@example.invalid",
                ],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "config",
                    "user.name",
                    "AIVP Test",
                ],
                cwd=repo,
                check=True,
            )

            (repo / "base.txt").write_text(
                "base\n",
                encoding="utf-8",
            )

            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-q",
                    "-m",
                    "base",
                ],
                cwd=repo,
                check=True,
            )

            run_dir = root / "run"
            run_dir.mkdir()

            runtime = Runtime(
                run_dir,
                Budgets(),
            )

            with SQLiteStateStore(
                db_path
            ) as store:
                store.begin_run(
                    run_id="run-policy",
                    repo_path=repo,
                    base_sha="base",
                    current_state="GENERATING",
                )

                durable = DurableExecution(
                    store=store,
                    run_id="run-policy",
                )

                complete_terminal_outcome(
                    durable=durable,
                    runtime=runtime,
                    repo=repo,
                    task={"task": "example"},
                    config={"policy": "test"},
                    state="DENIED",
                    reason="policy denied",
                )

                run = store.connection.execute(
                    """
                    SELECT *
                    FROM runs
                    WHERE run_id = ?
                    """,
                    ("run-policy",),
                ).fetchone()

                self.assertEqual(
                    run["current_state"],
                    "DENIED",
                )
                self.assertEqual(
                    run["status"],
                    "DENIED",
                )
                self.assertIsNotNone(
                    run["finished_at"]
                )

                checkpoint = store.load(
                    "run-policy"
                )

                self.assertEqual(
                    checkpoint["state"],
                    "DENIED",
                )
                self.assertEqual(
                    checkpoint["reason"],
                    "policy denied",
                )

                step = store.load_step(
                    "run-policy:"
                    "policy-terminal:1"
                )

                self.assertEqual(
                    step["status"],
                    "SUCCEEDED",
                )


if __name__ == "__main__":
    unittest.main()
