import json
import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.errors import (
    StateIntegrityError,
)
from aivp.execution.runtime import (
    Budgets,
    Runtime,
)
from aivp.models.base import (
    ModelResult,
)
from aivp.state.durable import (
    DurableExecution,
    complete_generation,
)
from aivp.state.resume import (
    build_resume_plan,
)
from aivp.state.sqlite import (
    SQLiteStateStore,
)


class ContextDurableArtifactTests(
    unittest.TestCase
):
    def _repo(
        self,
        root: Path,
    ) -> tuple[Path, str]:
        repo = root / "repo"
        repo.mkdir()

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

        (
            repo / "service.py"
        ).write_text(
            "value = 1\n",
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

        base_sha = subprocess.run(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        return repo, base_sha

    def test_context_artifacts_are_durable_and_validated(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo, base_sha = self._repo(
                root
            )

            run_dir = root / "run"
            run_dir.mkdir()

            context_path = (
                run_dir / "context.txt"
            )

            context_path.write_text(
                "selected context\n",
                encoding="utf-8",
            )

            manifest_path = (
                run_dir
                / "context-manifest.json"
            )

            manifest_path.write_text(
                json.dumps(
                    {
                        "manifest_hash": (
                            "semantic-hash"
                        )
                    }
                ),
                encoding="utf-8",
            )

            runtime = Runtime(
                run_dir,
                Budgets(),
            )

            state_db = (
                root / "state.db"
            )

            with SQLiteStateStore(
                state_db
            ) as store:
                store.begin_run(
                    run_id="run-context",
                    repo_path=repo,
                    base_sha=base_sha,
                    current_state=(
                        "WORKSPACE_READY"
                    ),
                )

                durable = DurableExecution(
                    store=store,
                    run_id="run-context",
                )

                complete_generation(
                    durable=durable,
                    runtime=runtime,
                    repo=repo,
                    prompt="prompt",
                    task={
                        "task": "test"
                    },
                    config={
                        "context": {
                            "max_files": 5,
                            "max_chars": 1000,
                        }
                    },
                    model_result=ModelResult(
                        provider="test",
                        model="test",
                        started_at=(
                            "2026-10-03T00:00:00+09:00"
                        ),
                        finished_at=(
                            "2026-10-03T00:00:01+09:00"
                        ),
                        raw_exit_status=0,
                        last_message="done",
                    ),
                    base_sha=base_sha,
                    context_path=context_path,
                    context_manifest_path=(
                        manifest_path
                    ),
                    context_manifest_hash=(
                        "semantic-hash"
                    ),
                )

                records = [
                    dict(row)
                    for row
                    in store.artifacts_for_run(
                        "run-context"
                    )
                ]

                by_type = {
                    record["type"]: record
                    for record in records
                }

                self.assertEqual(
                    set(by_type),
                    {
                        "generated-diff",
                        "context",
                        "context-manifest",
                    },
                )

                checkpoint = (
                    store.load_resume_checkpoint(
                        "run-context"
                    )
                )

                self.assertIsNotNone(
                    checkpoint
                )

                self.assertEqual(
                    checkpoint[
                        "context_manifest_hash"
                    ],
                    "semantic-hash",
                )

                self.assertEqual(
                    len(
                        checkpoint[
                            "context_artifact_ids"
                        ]
                    ),
                    2,
                )

                plan = build_resume_plan(
                    run_id="run-context",
                    checkpoint=checkpoint,
                    artifact_records=records,
                )

                self.assertEqual(
                    plan.next_state,
                    "VERIFYING",
                )

                context_path.write_text(
                    "tampered context\n",
                    encoding="utf-8",
                )

                with self.assertRaises(
                    StateIntegrityError
                ):
                    build_resume_plan(
                        run_id="run-context",
                        checkpoint=checkpoint,
                        artifact_records=records,
                    )


if __name__ == "__main__":
    unittest.main()
