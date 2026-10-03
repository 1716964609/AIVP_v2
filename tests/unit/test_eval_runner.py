import json
import subprocess
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from aivp.errors import AIVPError
from aivp.eval.case import load_eval_case
from aivp.eval.runner import (
    EvalRunnerError,
    run_eval_case,
)


class EvalRunnerTests(unittest.TestCase):
    def _git(
        self,
        repo: Path,
        *args: str,
    ) -> str:
        cp = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                *args,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        return cp.stdout.strip()

    def _write_json(
        self,
        path: Path,
        data,
    ) -> None:
        path.write_text(
            json.dumps(
                data,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

    def _fixture(
        self,
        root: Path,
        *,
        trials: int = 3,
    ):
        repo = root / "repo"

        subprocess.run(
            [
                "git",
                "init",
                "-q",
                str(repo),
            ],
            check=True,
        )

        self._git(
            repo,
            "config",
            "user.name",
            "AIVP Test",
        )
        self._git(
            repo,
            "config",
            "user.email",
            "aivp@example.invalid",
        )

        target = repo / "value.txt"

        target.write_text(
            "one\n",
            encoding="utf-8",
        )
        self._git(repo, "add", "value.txt")
        self._git(
            repo,
            "commit",
            "-q",
            "-m",
            "first",
        )

        first = self._git(
            repo,
            "rev-parse",
            "HEAD",
        )

        target.write_text(
            "two\n",
            encoding="utf-8",
        )
        self._git(repo, "add", "value.txt")
        self._git(
            repo,
            "commit",
            "-q",
            "-m",
            "second",
        )

        second = self._git(
            repo,
            "rev-parse",
            "HEAD",
        )

        task_path = root / "task.json"
        config_path = root / "config.json"

        self._write_json(
            task_path,
            {
                "task": "Change value.",
                "acceptance": [
                    "Value changes."
                ],
                "constraints": [
                    "Do not commit."
                ],
            },
        )

        self._write_json(
            config_path,
            {
                "budgets": {
                    "max_fix_iterations": 1
                }
            },
        )

        case_path = root / "case.json"

        self._write_json(
            case_path,
            {
                "schema_version": 1,
                "id": "runner-case",
                "description": (
                    "Trial runner fixture."
                ),
                "repository": {
                    "path": "./repo",
                    "revision": first,
                },
                "inputs": {
                    "task": "./task.json",
                    "config": "./config.json",
                },
                "expected": {
                    "terminal_status": (
                        "AUTO_FINISHED"
                    )
                },
                "graders": [
                    "expected-decision"
                ],
                "trials": {
                    "count": trials
                },
            },
        )

        return (
            load_eval_case(case_path),
            repo,
            first,
            second,
        )

    def test_runs_all_trials_from_same_resolved_baseline(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            (
                case,
                repo,
                first,
                second,
            ) = self._fixture(root)

            reports = root / "eval-reports"
            state_db = root / "state.db"

            calls = []

            def fake_run_new(**kwargs):
                calls.append(kwargs)

                run_dir = (
                    kwargs["reports_root"]
                    / kwargs["run_id"]
                )

                run_dir.mkdir(
                    parents=True
                )

                self._write_json(
                    run_dir / "status.json",
                    {
                        "status": (
                            "AUTO_FINISHED"
                        )
                    },
                )

                return run_dir

            with patch(
                "aivp.eval.runner.run_new",
                side_effect=fake_run_new,
            ):
                result = run_eval_case(
                    case,
                    reports_root=reports,
                    state_db=state_db,
                    evaluation_id="eval-test",
                )

            self.assertEqual(
                len(calls),
                3,
            )

            self.assertEqual(
                len(result.trials),
                3,
            )

            self.assertEqual(
                result.resolved_base_sha,
                first,
            )

            self.assertEqual(
                [
                    call["base_revision"]
                    for call in calls
                ],
                [
                    first,
                    first,
                    first,
                ],
            )

            self.assertEqual(
                [
                    call["run_id"]
                    for call in calls
                ],
                [
                    "eval-test-trial-001",
                    "eval-test-trial-002",
                    "eval-test-trial-003",
                ],
            )

            self.assertEqual(
                self._git(
                    repo,
                    "rev-parse",
                    "HEAD",
                ),
                second,
            )

    def test_writes_regrading_ready_snapshots_and_manifests(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            case, _, first, _ = (
                self._fixture(
                    root,
                    trials=1,
                )
            )

            reports = root / "eval-reports"

            def fake_run_new(**kwargs):
                run_dir = (
                    kwargs["reports_root"]
                    / kwargs["run_id"]
                )

                run_dir.mkdir(
                    parents=True
                )

                return run_dir

            with patch(
                "aivp.eval.runner.run_new",
                side_effect=fake_run_new,
            ):
                result = run_eval_case(
                    case,
                    reports_root=reports,
                    state_db=(
                        root / "state.db"
                    ),
                    evaluation_id="eval-test",
                )

            eval_root = (
                result.evaluation_root
            )

            for name in (
                "evaluation-manifest.json",
                "case-snapshot.json",
                "task-snapshot.json",
                "config-snapshot.json",
                "trials/trial-001.json",
            ):
                self.assertTrue(
                    (eval_root / name).is_file(),
                    name,
                )

            case_snapshot = json.loads(
                (
                    eval_root
                    / "case-snapshot.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                case_snapshot[
                    "repository"
                ][
                    "resolved_base_sha"
                ],
                first,
            )

            self.assertEqual(
                case_snapshot[
                    "expected"
                ][
                    "terminal_status"
                ],
                "AUTO_FINISHED",
            )

            self.assertEqual(
                case_snapshot["graders"],
                [
                    "expected-decision"
                ],
            )

            trial = json.loads(
                (
                    eval_root
                    / "trials"
                    / "trial-001.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                trial["execution_status"],
                "COMPLETED",
            )
            self.assertEqual(
                trial["run_dir"],
                (
                    "runs/"
                    "eval-test-trial-001"
                ),
            )

            manifest = json.loads(
                (
                    eval_root
                    / "evaluation-manifest.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                manifest["status"],
                "COMPLETED",
            )
            self.assertEqual(
                manifest[
                    "completed_trials"
                ],
                1,
            )

    def test_execution_failure_is_recorded_and_reraised(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            case, _, _, _ = (
                self._fixture(
                    root,
                    trials=2,
                )
            )

            reports = root / "eval-reports"

            with patch(
                "aivp.eval.runner.run_new",
                side_effect=AIVPError(
                    "synthetic failure"
                ),
            ):
                with self.assertRaises(
                    AIVPError
                ):
                    run_eval_case(
                        case,
                        reports_root=reports,
                        state_db=(
                            root / "state.db"
                        ),
                        evaluation_id=(
                            "eval-failure"
                        ),
                    )

            eval_root = (
                reports.resolve()
                / "runner-case"
                / "eval-failure"
            )

            trial = json.loads(
                (
                    eval_root
                    / "trials"
                    / "trial-001.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                trial["execution_status"],
                "FAILED",
            )
            self.assertEqual(
                trial["error_type"],
                "AIVPError",
            )

            manifest = json.loads(
                (
                    eval_root
                    / "evaluation-manifest.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                manifest["status"],
                "FAILED",
            )
            self.assertEqual(
                manifest[
                    "completed_trials"
                ],
                0,
            )
            self.assertEqual(
                manifest[
                    "failed_trial_id"
                ],
                "trial-001",
            )

    def test_unexpected_run_directory_is_recorded_as_failure(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            case, _, _, _ = (
                self._fixture(
                    root,
                    trials=1,
                )
            )

            reports = root / "eval-reports"

            wrong_dir = root / "wrong-run-dir"
            wrong_dir.mkdir()

            with patch(
                "aivp.eval.runner.run_new",
                return_value=wrong_dir,
            ):
                with self.assertRaises(
                    EvalRunnerError
                ):
                    run_eval_case(
                        case,
                        reports_root=reports,
                        state_db=(
                            root / "state.db"
                        ),
                        evaluation_id=(
                            "eval-wrong-dir"
                        ),
                    )

            eval_root = (
                reports.resolve()
                / "runner-case"
                / "eval-wrong-dir"
            )

            trial = json.loads(
                (
                    eval_root
                    / "trials"
                    / "trial-001.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                trial["execution_status"],
                "FAILED",
            )
            self.assertEqual(
                trial["error_type"],
                "EvalRunnerError",
            )

            manifest = json.loads(
                (
                    eval_root
                    / "evaluation-manifest.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                manifest["status"],
                "FAILED",
            )
            self.assertEqual(
                manifest["failed_trial_id"],
                "trial-001",
            )

    def test_existing_evaluation_root_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            case, _, _, _ = (
                self._fixture(
                    root,
                    trials=1,
                )
            )

            reports = root / "eval-reports"

            existing = (
                reports
                / "runner-case"
                / "eval-existing"
            )

            existing.mkdir(
                parents=True
            )

            with self.assertRaises(
                EvalRunnerError
            ):
                run_eval_case(
                    case,
                    reports_root=reports,
                    state_db=(
                        root / "state.db"
                    ),
                    evaluation_id=(
                        "eval-existing"
                    ),
                )


if __name__ == "__main__":
    unittest.main()
