import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.errors import StateIntegrityError
from aivp.state.hashing import sha256_file
from aivp.state.resume import (
    build_resume_plan,
    validate_resume_inputs,
    validate_resume_repository,
)
from aivp.repository.git import (
    capture_diff,
)
from aivp.state.hashing import (
    sha256_json,
    sha256_text,
)


class ResumePlanTests(unittest.TestCase):
    def test_generated_resumes_at_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "generated.diff"
            artifact.write_text(
                "diff-content",
                encoding="utf-8",
            )

            plan = build_resume_plan(
                run_id="run-1",
                checkpoint={
                    "state": "GENERATED",
                    "attempt": 1,
                },
                artifact_records=[
                    {
                        "path": str(artifact),
                        "sha256": sha256_file(
                            artifact
                        ),
                        "size_bytes": (
                            artifact.stat().st_size
                        ),
                    }
                ],
            )

            self.assertEqual(
                plan.current_state,
                "GENERATED",
            )
            self.assertEqual(
                plan.next_state,
                "VERIFYING",
            )
            self.assertEqual(
                plan.resume_attempt,
                2,
            )

    def test_verified_resumes_at_review(self):
        plan = build_resume_plan(
            run_id="run-1",
            checkpoint={
                "state": "VERIFIED",
                "attempt": 3,
            },
            artifact_records=[],
        )

        self.assertEqual(
            plan.next_state,
            "REVIEWING",
        )
        self.assertEqual(
            plan.resume_attempt,
            4,
        )

    def test_corrupt_artifact_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "generated.diff"
            artifact.write_text(
                "original",
                encoding="utf-8",
            )

            expected_hash = sha256_file(
                artifact
            )
            expected_size = (
                artifact.stat().st_size
            )

            artifact.write_text(
                "corrupted",
                encoding="utf-8",
            )

            with self.assertRaises(
                StateIntegrityError
            ):
                build_resume_plan(
                    run_id="run-1",
                    checkpoint={
                        "state": "GENERATED",
                        "attempt": 1,
                    },
                    artifact_records=[
                        {
                            "path": str(
                                artifact
                            ),
                            "sha256": expected_hash,
                            "size_bytes": (
                                expected_size
                            ),
                        }
                    ],
                )

    def test_unknown_state_fails_closed(self):
        with self.assertRaises(
            StateIntegrityError
        ):
            build_resume_plan(
                run_id="run-1",
                checkpoint={
                    "state": "SOMETHING_WEIRD",
                },
                artifact_records=[],
            )


    def test_repository_integrity_matches_checkpoint(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
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

            target = repo / "file.txt"
            target.write_text(
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

            base_sha = subprocess.run(
                [
                    "git",
                    "rev-parse",
                    "HEAD",
                ],
                cwd=repo,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()

            target.write_text(
                "generated\n",
                encoding="utf-8",
            )

            checkpoint = {
                "repo_path": str(
                    repo.resolve()
                ),
                "base_sha": base_sha,
                "current_diff_hash": (
                    sha256_text(
                        capture_diff(repo)
                    )
                ),
            }

            validate_resume_repository(
                repo=repo,
                checkpoint=checkpoint,
            )

    def test_repository_diff_tamper_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
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

            target = repo / "file.txt"

            target.write_text(
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

            base_sha = subprocess.run(
                [
                    "git",
                    "rev-parse",
                    "HEAD",
                ],
                cwd=repo,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()

            target.write_text(
                "generated\n",
                encoding="utf-8",
            )

            checkpoint = {
                "repo_path": str(
                    repo.resolve()
                ),
                "base_sha": base_sha,
                "current_diff_hash": (
                    sha256_text(
                        capture_diff(repo)
                    )
                ),
            }

            target.write_text(
                "tampered\n",
                encoding="utf-8",
            )

            with self.assertRaises(
                StateIntegrityError
            ):
                validate_resume_repository(
                    repo=repo,
                    checkpoint=checkpoint,
                )


    def test_task_identity_tamper_fails_closed(
        self,
    ):
        original_task = {
            "task": "original"
        }

        config = {
            "mode": "test"
        }

        checkpoint = {
            "task_hash": (
                sha256_json(
                    original_task
                )
            ),
            "config_hash": (
                sha256_json(
                    config
                )
            ),
        }

        with self.assertRaises(
            StateIntegrityError
        ):
            validate_resume_inputs(
                task={
                    "task": "tampered"
                },
                config=config,
                checkpoint=checkpoint,
            )

    def test_config_identity_tamper_fails_closed(
        self,
    ):
        task = {
            "task": "original"
        }

        original_config = {
            "mode": "original"
        }

        checkpoint = {
            "task_hash": (
                sha256_json(
                    task
                )
            ),
            "config_hash": (
                sha256_json(
                    original_config
                )
            ),
        }

        with self.assertRaises(
            StateIntegrityError
        ):
            validate_resume_inputs(
                task=task,
                config={
                    "mode": "tampered"
                },
                checkpoint=checkpoint,
            )


if __name__ == "__main__":
    unittest.main()
