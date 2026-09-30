import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aivp.legacy.orchestrator_v1 as legacy


class RuntimeCharacterizationTests(unittest.TestCase):
    def make_runtime(
        self,
        run_dir: Path,
        *,
        dry_run: bool = False,
        codex_max_calls: int = 4,
        claude_max_calls: int = 3,
        whole_run_timeout_seconds: int = 900,
    ):
        budgets = legacy.Budgets(
            max_fix_iterations=2,
            codex_max_calls=codex_max_calls,
            claude_max_calls=claude_max_calls,
            codex_timeout_seconds=300,
            claude_timeout_seconds=300,
            whole_run_timeout_seconds=whole_run_timeout_seconds,
        )

        return legacy.Runtime(
            run_dir,
            budgets,
            dry_run=dry_run,
        )

    def test_consume_tracks_actor_budgets(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self.make_runtime(Path(tmp))

            runtime.consume("codex")
            runtime.consume("claude")

            self.assertEqual(
                runtime.counters.codex_calls,
                1,
            )

            self.assertEqual(
                runtime.counters.claude_calls,
                1,
            )

    def test_codex_budget_exceeded(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self.make_runtime(
                Path(tmp),
                codex_max_calls=1,
            )

            runtime.consume("codex")

            with self.assertRaisesRegex(
                legacy.BudgetExceeded,
                "Codex call budget exceeded",
            ):
                runtime.consume("codex")

            self.assertEqual(
                runtime.counters.codex_calls,
                1,
            )

    def test_unknown_actor_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self.make_runtime(Path(tmp))

            with self.assertRaisesRegex(
                legacy.AIVPError,
                "Unknown budget actor: other",
            ):
                runtime.consume("other")

    def test_whole_run_budget_precedes_actor_consumption(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self.make_runtime(
                Path(tmp),
                whole_run_timeout_seconds=0,
            )

            with self.assertRaisesRegex(
                legacy.BudgetExceeded,
                "Whole-run time budget exceeded",
            ):
                runtime.consume("codex")

            self.assertEqual(
                runtime.counters.codex_calls,
                0,
            )

    def test_dry_run_command_writes_artifact_and_start_event_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()

            runtime = self.make_runtime(
                root / "run",
                dry_run=True,
            )

            runtime.run_dir.mkdir()

            with patch.object(
                legacy,
                "now_iso",
                return_value="2026-09-30T00:00:00+09:00",
            ):
                cp = runtime.command(
                    ["echo", "hello world"],
                    cwd=repo,
                    timeout_seconds=10,
                    log_stem="example",
                    actor="codex",
                    check=True,
                )

            self.assertEqual(cp.returncode, 0)
            self.assertEqual(cp.stdout, "[DRY RUN]\n")
            self.assertEqual(
                runtime.counters.codex_calls,
                1,
            )

            artifact = (
                runtime.run_dir
                / "example.dry-run.txt"
            )

            self.assertTrue(artifact.exists())

            text = artifact.read_text(
                encoding="utf-8"
            )

            self.assertIn(
                "$ echo 'hello world'",
                text,
            )

            self.assertIn(
                f"CWD={repo}",
                text,
            )

            self.assertEqual(
                [event["kind"] for event in runtime.events],
                ["command_start"],
            )

            persisted = json.loads(
                (
                    runtime.run_dir
                    / "events.json"
                ).read_text(encoding="utf-8")
            )

            self.assertEqual(
                persisted,
                runtime.events,
            )

    def test_successful_command_writes_logs_and_end_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()

            runtime = self.make_runtime(
                root / "run"
            )

            runtime.run_dir.mkdir()

            cp = runtime.command(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; "
                        "print('stdout-value'); "
                        "print('stderr-value', "
                        "file=sys.stderr)"
                    ),
                ],
                cwd=repo,
                timeout_seconds=10,
                log_stem="real",
                check=True,
            )

            self.assertEqual(
                cp.returncode,
                0,
            )

            self.assertIn(
                "stdout-value",
                (
                    runtime.run_dir
                    / "real.stdout.txt"
                ).read_text(encoding="utf-8"),
            )

            self.assertIn(
                "stderr-value",
                (
                    runtime.run_dir
                    / "real.stderr.txt"
                ).read_text(encoding="utf-8"),
            )

            self.assertEqual(
                [event["kind"] for event in runtime.events],
                [
                    "command_start",
                    "command_end",
                ],
            )

    def test_checked_failure_preserves_returncode_and_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()

            runtime = self.make_runtime(
                root / "run"
            )

            runtime.run_dir.mkdir()

            with self.assertRaises(
                legacy.CommandFailed,
            ) as ctx:
                runtime.command(
                    [
                        sys.executable,
                        "-c",
                        (
                            "import sys; "
                            "print('failed', "
                            "file=sys.stderr); "
                            "sys.exit(7)"
                        ),
                    ],
                    cwd=repo,
                    timeout_seconds=10,
                    log_stem="failure",
                    check=True,
                )

            self.assertEqual(
                ctx.exception.returncode,
                7,
            )

            self.assertTrue(
                (
                    runtime.run_dir
                    / "failure.stderr.txt"
                ).exists()
            )

            self.assertEqual(
                runtime.events[-1]["kind"],
                "command_end",
            )

            self.assertEqual(
                runtime.events[-1]["returncode"],
                7,
            )


if __name__ == "__main__":
    unittest.main()
