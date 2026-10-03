import json
import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aivp.eval.suite import (
    EvalSuiteError,
    load_eval_suite,
    run_eval_suite,
)


class EvalSuiteTests(unittest.TestCase):
    def _write_json(
        self,
        path: Path,
        value,
    ):
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                value,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _case(
        self,
        root: Path,
        *,
        filename: str,
        case_id: str,
    ) -> Path:
        case_path = (
            root / "cases" / filename
        )

        task_path = (
            root
            / "inputs"
            / f"{case_id}-task.json"
        )

        config_path = (
            root
            / "inputs"
            / f"{case_id}-config.json"
        )

        self._write_json(
            task_path,
            {
                "task": "test task",
                "acceptance": [],
                "constraints": [],
            },
        )

        self._write_json(
            config_path,
            {},
        )

        self._write_json(
            case_path,
            {
                "schema_version": 1,
                "id": case_id,
                "description": (
                    f"Case {case_id}"
                ),
                "repository": {
                    "path": "..",
                    "revision": "HEAD",
                },
                "inputs": {
                    "task": (
                        "../inputs/"
                        f"{case_id}-task.json"
                    ),
                    "config": (
                        "../inputs/"
                        f"{case_id}-config.json"
                    ),
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
                    "count": 1,
                },
            },
        )

        return case_path

    def _suite(
        self,
        root: Path,
        *,
        duplicate_ids: bool = False,
    ) -> Path:
        first = self._case(
            root,
            filename="case-01.json",
            case_id="case-01",
        )

        second = self._case(
            root,
            filename="case-02.json",
            case_id=(
                "case-01"
                if duplicate_ids
                else "case-02"
            ),
        )

        suite_path = (
            root
            / "suites"
            / "suite.json"
        )

        self._write_json(
            suite_path,
            {
                "schema_version": 1,
                "id": "m7-test",
                "description": (
                    "M7 test suite"
                ),
                "cases": [
                    str(
                        Path("..")
                        / "cases"
                        / first.name
                    ),
                    str(
                        Path("..")
                        / "cases"
                        / second.name
                    ),
                ],
            },
        )

        return suite_path

    def test_loads_suite_and_resolves_cases(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            suite = load_eval_suite(
                self._suite(root)
            )

            self.assertEqual(
                suite.suite_id,
                "m7-test",
            )

            self.assertEqual(
                [
                    case.case_id
                    for case
                    in suite.cases
                ],
                [
                    "case-01",
                    "case-02",
                ],
            )

    def test_duplicate_case_ids_fail_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            with self.assertRaises(
                EvalSuiteError
            ):
                load_eval_suite(
                    self._suite(
                        root,
                        duplicate_ids=True,
                    )
                )

    def test_empty_suite_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            path = (
                root / "suite.json"
            )

            self._write_json(
                path,
                {
                    "schema_version": 1,
                    "id": "empty",
                    "cases": [],
                },
            )

            with self.assertRaises(
                EvalSuiteError
            ):
                load_eval_suite(path)

    def test_runs_case_pipeline_and_writes_summary(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            suite = load_eval_suite(
                self._suite(root)
            )

            benchmark_results = [
                SimpleNamespace(
                    overall_outcome=(
                        "PASS"
                    )
                ),
                SimpleNamespace(
                    overall_outcome=(
                        "FAIL"
                    )
                ),
            ]

            with patch(
                "aivp.eval.suite."
                "run_eval_case"
            ) as run_case, patch(
                "aivp.eval.suite."
                "regrade_evaluation"
            ) as regrade, patch(
                "aivp.eval.suite."
                "generate_benchmark",
                side_effect=(
                    benchmark_results
                ),
            ) as benchmark:
                result = run_eval_suite(
                    suite,
                    reports_root=(
                        root / "reports"
                    ),
                    state_db=(
                        root / "state.db"
                    ),
                    suite_run_id=(
                        "suite-test"
                    ),
                )

            self.assertEqual(
                run_case.call_count,
                2,
            )

            self.assertEqual(
                regrade.call_count,
                2,
            )

            self.assertEqual(
                benchmark.call_count,
                2,
            )

            self.assertEqual(
                result.overall_outcome,
                "FAIL",
            )

            summary = json.loads(
                (
                    result.suite_root
                    / "suite-summary.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                summary["counts"],
                {
                    "PASS": 1,
                    "FAIL": 1,
                    "ERROR": 0,
                },
            )

    def test_case_failure_does_not_hide_later_cases(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            suite = load_eval_suite(
                self._suite(root)
            )

            with patch(
                "aivp.eval.suite."
                "run_eval_case",
                side_effect=[
                    RuntimeError(
                        "synthetic"
                    ),
                    None,
                ],
            ) as run_case, patch(
                "aivp.eval.suite."
                "regrade_evaluation"
            ) as regrade, patch(
                "aivp.eval.suite."
                "generate_benchmark",
                return_value=(
                    SimpleNamespace(
                        overall_outcome=(
                            "PASS"
                        )
                    )
                ),
            ):
                result = run_eval_suite(
                    suite,
                    reports_root=(
                        root / "reports"
                    ),
                    state_db=(
                        root / "state.db"
                    ),
                    suite_run_id=(
                        "suite-test"
                    ),
                )

            self.assertEqual(
                run_case.call_count,
                2,
            )

            self.assertEqual(
                regrade.call_count,
                1,
            )

            self.assertEqual(
                result.overall_outcome,
                "ERROR",
            )

            first = json.loads(
                (
                    result.suite_root
                    / "cases"
                    / "case-001.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            second = json.loads(
                (
                    result.suite_root
                    / "cases"
                    / "case-002.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                first["status"],
                "FAILED",
            )

            self.assertEqual(
                first["error_type"],
                "RuntimeError",
            )

            self.assertEqual(
                second["status"],
                "COMPLETED",
            )

    def test_existing_suite_output_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            suite = load_eval_suite(
                self._suite(root)
            )

            existing = (
                root
                / "reports"
                / suite.suite_id
                / "suite-test"
            )

            existing.mkdir(
                parents=True
            )

            with self.assertRaises(
                EvalSuiteError
            ):
                run_eval_suite(
                    suite,
                    reports_root=(
                        root / "reports"
                    ),
                    state_db=(
                        root / "state.db"
                    ),
                    suite_run_id=(
                        "suite-test"
                    ),
                )


if __name__ == "__main__":
    unittest.main()
