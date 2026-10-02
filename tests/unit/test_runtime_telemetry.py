import sys
import tempfile
import unittest

from pathlib import Path

from aivp.execution.runtime import Budgets, Runtime


class RuntimeTelemetryTests(unittest.TestCase):
    def test_command_events_do_not_capture_sensitive_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo = root / "SENSITIVE_CWD_TOKEN"
            repo.mkdir()

            run_dir = root / "run"
            run_dir.mkdir()

            runtime = Runtime(
                run_dir,
                Budgets(),
            )

            runtime.command(
                [
                    sys.executable,
                    "-c",
                    "print('SENSITIVE_SCRIPT_TOKEN')",
                    "SENSITIVE_ARG_TOKEN",
                ],
                cwd=repo,
                timeout_seconds=10,
                log_stem="telemetry-safe-command",
                stdin_text="SENSITIVE_STDIN_TOKEN",
                actor="codex",
                check=True,
            )

            telemetry = (
                run_dir / "events.json"
            ).read_text(encoding="utf-8")

            self.assertNotIn(
                "SENSITIVE_SCRIPT_TOKEN",
                telemetry,
            )
            self.assertNotIn(
                "SENSITIVE_ARG_TOKEN",
                telemetry,
            )
            self.assertNotIn(
                "SENSITIVE_STDIN_TOKEN",
                telemetry,
            )
            self.assertNotIn(
                "SENSITIVE_CWD_TOKEN",
                telemetry,
            )

            start_event = runtime.events[0]
            end_event = runtime.events[1]

            self.assertEqual(
                start_event["kind"],
                "command_start",
            )
            self.assertEqual(
                start_event["actor"],
                "codex",
            )
            self.assertEqual(
                start_event["tool"],
                "codex",
            )
            self.assertEqual(
                start_event["timeout_seconds"],
                10,
            )

            self.assertNotIn(
                "command",
                start_event,
            )
            self.assertNotIn(
                "cwd",
                start_event,
            )

            self.assertEqual(
                end_event["kind"],
                "command_end",
            )
            self.assertEqual(
                end_event["actor"],
                "codex",
            )
            self.assertEqual(
                end_event["tool"],
                "codex",
            )
            self.assertEqual(
                end_event["returncode"],
                0,
            )
            self.assertIn(
                "elapsed_seconds",
                end_event,
            )

            self.assertNotIn(
                "command",
                end_event,
            )


if __name__ == "__main__":
    unittest.main()
