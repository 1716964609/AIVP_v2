import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from pathlib import Path


class ProcessResumeTests(
    unittest.TestCase
):
    def test_hard_crash_after_generation_resumes_without_regeneration(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo = root / "repo"
            repo.mkdir()

            subprocess.run(
                ["git", "init"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            subprocess.run(
                [
                    "git",
                    "config",
                    "user.email",
                    "test@example.com",
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
                repo / "README.md"
            ).write_text(
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
                    "-m",
                    "base",
                ],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            run_dir = root / "run"
            run_dir.mkdir()

            env = os.environ.copy()

            src = (
                Path(__file__)
                .resolve()
                .parents[2]
                / "src"
            )

            env["PYTHONPATH"] = str(src)

            env[
                "AIVP_ENABLE_FAULT_INJECTION"
            ] = "1"

            env[
                "AIVP_HARD_CRASH_AFTER_STATE"
            ] = "GENERATED"

            first = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__)
                        .with_name(
                            "process_resume_driver.py"
                        )
                    ),
                    "start",
                    str(root),
                ],
                env=env,
            )

            self.assertEqual(
                first.returncode,
                97,
            )

            self.assertTrue(
                (
                    repo
                    / "generated.txt"
                ).exists()
            )

            events_before = json.loads(
                (
                    run_dir
                    / "events.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            command_starts_before = [
                event
                for event in events_before
                if event.get("kind")
                == "command_start"
            ]

            resume_env = (
                os.environ.copy()
            )

            resume_env[
                "PYTHONPATH"
            ] = str(src)

            second = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__)
                        .with_name(
                            "process_resume_driver.py"
                        )
                    ),
                    "resume",
                    str(root),
                ],
                env=resume_env,
            )

            self.assertEqual(
                second.returncode,
                0,
            )

            status = json.loads(
                (
                    run_dir
                    / "status.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                status["status"],
                "AUTO_FINISHED",
            )

            # Process #1 consumed one Codex call
            # for Generate. Resume must NOT generate
            # again; only the final Risk call adds
            # the second Codex call.
            self.assertEqual(
                status["metrics"][
                    "codex_calls"
                ],
                2,
            )

            self.assertEqual(
                status["metrics"][
                    "claude_calls"
                ],
                1,
            )

            events_after = json.loads(
                (
                    run_dir
                    / "events.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertGreater(
                len(events_after),
                len(events_before),
            )

            self.assertEqual(
                sum(
                    1
                    for event
                    in events_after
                    if (
                        event.get("kind")
                        == "run_start"
                    )
                ),
                1,
            )

            self.assertEqual(
                sum(
                    1
                    for event
                    in events_after
                    if (
                        event.get("kind")
                        == "run_resume"
                    )
                ),
                1,
            )

    def test_hard_crash_after_verification_resumes_at_review(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo = root / "repo"
            repo.mkdir()

            subprocess.run(
                ["git", "init"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            subprocess.run(
                [
                    "git",
                    "config",
                    "user.email",
                    "test@example.com",
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
                repo / "README.md"
            ).write_text(
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
                    "-m",
                    "base",
                ],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            run_dir = root / "run"
            run_dir.mkdir()

            src = (
                Path(__file__)
                .resolve()
                .parents[2]
                / "src"
            )

            driver = (
                Path(__file__)
                .with_name(
                    "process_resume_driver.py"
                )
            )

            env = os.environ.copy()
            env["PYTHONPATH"] = str(src)
            env[
                "AIVP_ENABLE_FAULT_INJECTION"
            ] = "1"
            env[
                "AIVP_HARD_CRASH_AFTER_STATE"
            ] = "VERIFIED"

            first = subprocess.run(
                [
                    sys.executable,
                    str(driver),
                    "start",
                    str(root),
                ],
                env=env,
            )

            self.assertEqual(
                first.returncode,
                97,
            )

            db_path = root / "state.db"

            with sqlite3.connect(
                db_path
            ) as connection:
                verification_artifacts = (
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM artifacts
                        WHERE run_id = ?
                          AND type = ?
                        """,
                        (
                            "process-resume-test",
                            (
                                "deterministic-"
                                "verification"
                            ),
                        ),
                    ).fetchone()[0]
                )

                verify_steps = (
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM steps
                        WHERE run_id = ?
                          AND step_type = ?
                          AND status = ?
                        """,
                        (
                            "process-resume-test",
                            "verify",
                            "SUCCEEDED",
                        ),
                    ).fetchone()[0]
                )

            # VERIFIED checkpoint must already
            # contain exactly one successful
            # verification result.
            self.assertEqual(
                verification_artifacts,
                1,
            )

            self.assertEqual(
                verify_steps,
                1,
            )

            resume_env = os.environ.copy()
            resume_env["PYTHONPATH"] = str(src)

            second = subprocess.run(
                [
                    sys.executable,
                    str(driver),
                    "resume",
                    str(root),
                ],
                env=resume_env,
            )

            self.assertEqual(
                second.returncode,
                0,
            )

            status = json.loads(
                (
                    run_dir
                    / "status.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                status["status"],
                "AUTO_FINISHED",
            )

            # Generate happened once before
            # the crash. Risk is the only
            # additional Codex call.
            self.assertEqual(
                status["metrics"][
                    "codex_calls"
                ],
                2,
            )

            # Review happens once after resume.
            self.assertEqual(
                status["metrics"][
                    "claude_calls"
                ],
                1,
            )

            with sqlite3.connect(
                db_path
            ) as connection:
                verification_artifacts_after = (
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM artifacts
                        WHERE run_id = ?
                          AND type = ?
                        """,
                        (
                            "process-resume-test",
                            (
                                "deterministic-"
                                "verification"
                            ),
                        ),
                    ).fetchone()[0]
                )

                verify_steps_after = (
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM steps
                        WHERE run_id = ?
                          AND step_type = ?
                          AND status = ?
                        """,
                        (
                            "process-resume-test",
                            "verify",
                            "SUCCEEDED",
                        ),
                    ).fetchone()[0]
                )

                generated_artifacts_after = (
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM artifacts
                        WHERE run_id = ?
                          AND type = ?
                        """,
                        (
                            "process-resume-test",
                            "generated-diff",
                        ),
                    ).fetchone()[0]
                )

            # Resume from VERIFIED must not
            # execute Verify or Generate again.
            self.assertEqual(
                verification_artifacts_after,
                1,
            )

            self.assertEqual(
                verify_steps_after,
                1,
            )

            self.assertEqual(
                generated_artifacts_after,
                1,
            )



    def test_application_worktree_survives_hard_crash_and_resumes(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

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
                    "test@example.com",
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
                repo / "README.md"
            ).write_text(
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

            src = (
                Path(__file__)
                .resolve()
                .parents[2]
                / "src"
            )

            driver = (
                Path(__file__)
                .with_name(
                    "application_process_resume_driver.py"
                )
            )

            run_id = (
                "application-process-resume-test"
            )

            run_dir = (
                root
                / "reports"
                / run_id
            )

            worktree = (
                run_dir
                / "worktree"
            )

            env = os.environ.copy()
            env["PYTHONPATH"] = str(src)

            env[
                "AIVP_ENABLE_FAULT_INJECTION"
            ] = "1"

            env[
                "AIVP_HARD_CRASH_AFTER_STATE"
            ] = "GENERATED"

            first = subprocess.run(
                [
                    sys.executable,
                    str(driver),
                    "start",
                    str(root),
                ],
                env=env,
            )

            self.assertEqual(
                first.returncode,
                97,
            )

            self.assertTrue(
                worktree.exists()
            )

            self.assertTrue(
                (
                    worktree
                    / "generated.txt"
                ).exists()
            )

            self.assertFalse(
                (
                    repo
                    / "generated.txt"
                ).exists()
            )

            canonical_status = subprocess.run(
                [
                    "git",
                    "status",
                    "--short",
                ],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout

            self.assertEqual(
                canonical_status,
                "",
            )

            db_path = root / "state.db"

            with sqlite3.connect(
                db_path
            ) as connection:
                row = connection.execute(
                    """
                    SELECT payload_json
                    FROM checkpoints
                    WHERE run_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (run_id,),
                ).fetchone()

            self.assertIsNotNone(
                row
            )

            checkpoint = json.loads(
                row[0]
            )

            self.assertEqual(
                checkpoint["repo_path"],
                str(
                    worktree.resolve()
                ),
            )

            self.assertEqual(
                checkpoint[
                    "canonical_repo_path"
                ],
                str(
                    repo.resolve()
                ),
            )

            resume_env = os.environ.copy()
            resume_env[
                "PYTHONPATH"
            ] = str(src)

            second = subprocess.run(
                [
                    sys.executable,
                    str(driver),
                    "resume",
                    str(root),
                ],
                env=resume_env,
            )

            self.assertEqual(
                second.returncode,
                0,
            )

            status = json.loads(
                (
                    run_dir
                    / "status.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                status["status"],
                "AUTO_FINISHED",
            )

            self.assertTrue(
                (
                    worktree
                    / "generated.txt"
                ).exists()
            )

            self.assertFalse(
                (
                    repo
                    / "generated.txt"
                ).exists()
            )

            canonical_status = subprocess.run(
                [
                    "git",
                    "status",
                    "--short",
                ],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout

            self.assertEqual(
                canonical_status,
                "",
            )

if __name__ == "__main__":
    unittest.main()
