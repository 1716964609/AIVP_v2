import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aivp.execution.runtime as new_runtime
import aivp.legacy.orchestrator_v1 as legacy


class RuntimeCompatibilityTests(unittest.TestCase):
    def make_pair(
        self,
        legacy_dir: Path,
        new_dir: Path,
        *,
        dry_run=False,
        codex_max_calls=4,
        claude_max_calls=3,
        whole_run_timeout_seconds=900,
    ):
        legacy_budgets = legacy.Budgets(
            max_fix_iterations=2,
            codex_max_calls=codex_max_calls,
            claude_max_calls=claude_max_calls,
            codex_timeout_seconds=300,
            claude_timeout_seconds=300,
            whole_run_timeout_seconds=whole_run_timeout_seconds,
        )

        new_budgets = new_runtime.Budgets(
            max_fix_iterations=2,
            codex_max_calls=codex_max_calls,
            claude_max_calls=claude_max_calls,
            codex_timeout_seconds=300,
            claude_timeout_seconds=300,
            whole_run_timeout_seconds=whole_run_timeout_seconds,
        )

        return (
            legacy.Runtime(
                legacy_dir,
                legacy_budgets,
                dry_run=dry_run,
            ),
            new_runtime.Runtime(
                new_dir,
                new_budgets,
                dry_run=dry_run,
            ),
        )

    def test_default_budgets_match(self):
        self.assertEqual(
            legacy.Budgets().__dict__,
            new_runtime.Budgets().__dict__,
        )

    def test_initial_counters_match(self):
        self.assertEqual(
            legacy.Counters().__dict__,
            new_runtime.Counters().__dict__,
        )

    def test_budget_consumption_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            old, new = self.make_pair(
                root / "old",
                root / "new",
            )

            old.consume("codex")
            old.consume("claude")

            new.consume("codex")
            new.consume("claude")

            self.assertEqual(
                old.counters.__dict__,
                new.counters.__dict__,
            )

    def test_codex_budget_exception_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            old, new = self.make_pair(
                root / "old",
                root / "new",
                codex_max_calls=1,
            )

            old.consume("codex")
            new.consume("codex")

            with self.assertRaises(
                legacy.BudgetExceeded
            ) as old_ctx:
                old.consume("codex")

            with self.assertRaises(
                new_runtime.BudgetExceeded
            ) as new_ctx:
                new.consume("codex")

            self.assertEqual(
                str(old_ctx.exception),
                str(new_ctx.exception),
            )

    def test_unknown_actor_exception_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            old, new = self.make_pair(
                root / "old",
                root / "new",
            )

            with self.assertRaises(
                legacy.AIVPError
            ) as old_ctx:
                old.consume("other")

            with self.assertRaises(
                new_runtime.AIVPError
            ) as new_ctx:
                new.consume("other")

            self.assertEqual(
                str(old_ctx.exception),
                str(new_ctx.exception),
            )

    def test_dry_run_artifact_and_events_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            old_dir = root / "old"
            new_dir = root / "new"
            repo = root / "repo"

            old_dir.mkdir()
            new_dir.mkdir()
            repo.mkdir()

            old, new = self.make_pair(
                old_dir,
                new_dir,
                dry_run=True,
            )

            timestamp = (
                "2026-09-30T00:00:00+09:00"
            )

            with patch.object(
                legacy,
                "now_iso",
                return_value=timestamp,
            ), patch.object(
                new_runtime,
                "now_iso",
                return_value=timestamp,
            ):
                old_cp = old.command(
                    ["echo", "hello world"],
                    cwd=repo,
                    timeout_seconds=10,
                    log_stem="example",
                    actor="codex",
                    check=True,
                )

                new_cp = new.command(
                    ["echo", "hello world"],
                    cwd=repo,
                    timeout_seconds=10,
                    log_stem="example",
                    actor="codex",
                    check=True,
                )

            self.assertEqual(
                old_cp.returncode,
                new_cp.returncode,
            )

            self.assertEqual(
                old_cp.stdout,
                new_cp.stdout,
            )

            self.assertEqual(
                old.counters.__dict__,
                new.counters.__dict__,
            )

            self.assertEqual(
                [
                    event["kind"]
                    for event in old.events
                ],
                [
                    event["kind"]
                    for event in new.events
                ],
            )

            self.assertEqual(
                old.events[0]["actor"],
                new.events[0]["actor"],
            )

            self.assertNotIn(
                "command",
                new.events[0],
            )
            self.assertNotIn(
                "cwd",
                new.events[0],
            )

            self.assertEqual(
                new.events[0]["tool"],
                "codex",
            )
            self.assertEqual(
                new.events[0]["timeout_seconds"],
                10,
            )

            self.assertEqual(
                (
                    old_dir
                    / "example.dry-run.txt"
                ).read_bytes(),
                (
                    new_dir
                    / "example.dry-run.txt"
                ).read_bytes(),
            )

            persisted_old = json.loads(
                (
                    old_dir
                    / "events.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            persisted_new = json.loads(
                (
                    new_dir
                    / "events.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                persisted_old,
                old.events,
            )
            self.assertEqual(
                persisted_new,
                new.events,
            )


if __name__ == "__main__":
    unittest.main()
