import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aivp.eval.benchmark import (
    EvalBenchmarkError,
    generate_benchmark,
)


class EvalBenchmarkTests(
    unittest.TestCase
):
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

    def _fixture(
        self,
        root: Path,
    ) -> Path:
        evaluation = (
            root / "evaluation"
        )

        self._write_json(
            evaluation
            / "evaluation-manifest.json",
            {
                "evaluation_id": (
                    "eval-1"
                ),
                "case_id": "case-1",
                "status": "COMPLETED",
            },
        )

        outcomes = (
            "PASS",
            "FAIL",
            "ERROR",
        )

        statuses = (
            "AUTO_FINISHED",
            "HUMAN_REQUIRED",
            "DENIED",
        )

        risks = (
            "low",
            "medium",
            "high",
        )

        elapsed = (
            10.0,
            20.0,
            40.0,
        )

        for index in range(1, 4):
            trial_id = (
                f"trial-{index:03d}"
            )

            run_relative = (
                "runs/"
                f"eval-1-{trial_id}"
            )

            self._write_json(
                evaluation
                / "trials"
                / f"{trial_id}.json",
                {
                    "execution_status": (
                        "COMPLETED"
                    ),
                    "run_dir": (
                        run_relative
                    ),
                },
            )

            self._write_json(
                evaluation
                / run_relative
                / "metrics.json",
                {
                    "status": (
                        statuses[
                            index - 1
                        ]
                    ),
                    "elapsed_seconds": (
                        elapsed[
                            index - 1
                        ]
                    ),
                    "codex_calls": index,
                    "claude_calls": 1,
                    "fix_iterations": (
                        index - 1
                    ),
                    "final_risk": (
                        risks[
                            index - 1
                        ]
                    ),
                },
            )

            self._write_json(
                evaluation
                / "regrades"
                / "regrade-001"
                / f"{trial_id}.json",
                {
                    "trial_id": (
                        trial_id
                    ),
                    "source_trial_manifest": (
                        "trials/"
                        f"{trial_id}.json"
                    ),
                    "overall_outcome": (
                        outcomes[
                            index - 1
                        ]
                    ),
                    "grader_results": [
                        {
                            "grader": (
                                "expected-decision"
                            ),
                            "outcome": (
                                outcomes[
                                    index - 1
                                ]
                            ),
                        }
                    ],
                },
            )

        self._write_json(
            evaluation
            / "regrades"
            / "regrade-001"
            / "manifest.json",
            {
                "status": "COMPLETED",
                "trial_outputs": [
                    "trial-001.json",
                    "trial-002.json",
                    "trial-003.json",
                ],
            },
        )

        # Trial 1: complete economics.
        self._write_json(
            evaluation
            / "runs"
            / "eval-1-trial-001"
            / "run-summary.json",
            {
                "model_calls": {
                    "count": 2,
                },
                "tokens": {
                    "input_tokens": 1000,
                    "cached_tokens": 400,
                    "output_tokens": 200,
                    "input_known_calls": 2,
                    "cached_known_calls": 2,
                    "output_known_calls": 2,
                },
                "cost": {
                    "total_usd": 0.01,
                    "known_calls": 2,
                    "total_calls": 2,
                },
            },
        )

        # Trial 2: partial economics.
        self._write_json(
            evaluation
            / "runs"
            / "eval-1-trial-002"
            / "run-summary.json",
            {
                "model_calls": {
                    "count": 2,
                },
                "tokens": {
                    "input_tokens": 500,
                    "cached_tokens": 100,
                    "output_tokens": 50,
                    "input_known_calls": 2,
                    "cached_known_calls": 1,
                    "output_known_calls": 2,
                },
                "cost": {
                    "total_usd": 0.005,
                    "known_calls": 1,
                    "total_calls": 2,
                },
            },
        )

        # Trial 3 intentionally has no
        # run-summary.json.

        return evaluation

    def test_aggregates_quality_and_distributions(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            evaluation = (
                self._fixture(
                    Path(td)
                )
            )

            result = (
                generate_benchmark(
                    evaluation_root=(
                        evaluation
                    ),
                    regrade_id=(
                        "regrade-001"
                    ),
                    benchmark_id=(
                        "benchmark-001"
                    ),
                )
            )

            report = json.loads(
                (
                    result.benchmark_root
                    / "benchmark.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                report["quality"][
                    "counts"
                ],
                {
                    "PASS": 1,
                    "FAIL": 1,
                    "ERROR": 1,
                },
            )

            self.assertAlmostEqual(
                report["quality"][
                    "pass_rate"
                ],
                1 / 3,
            )

            elapsed = (
                report[
                    "performance"
                ][
                    "elapsed_seconds"
                ]
            )

            self.assertEqual(
                elapsed["values"],
                [
                    10.0,
                    20.0,
                    40.0,
                ],
            )

            self.assertEqual(
                elapsed["min"],
                10.0,
            )

            self.assertEqual(
                elapsed["max"],
                40.0,
            )

            self.assertEqual(
                elapsed["p50"],
                20.0,
            )

            self.assertAlmostEqual(
                elapsed["p95"],
                38.0,
            )

    def test_categorical_distributions_are_preserved(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            evaluation = (
                self._fixture(
                    Path(td)
                )
            )

            result = (
                generate_benchmark(
                    evaluation_root=(
                        evaluation
                    ),
                    regrade_id=(
                        "regrade-001"
                    ),
                    benchmark_id=(
                        "benchmark-001"
                    ),
                )
            )

            report = json.loads(
                (
                    result.benchmark_root
                    / "benchmark.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                report[
                    "categorical"
                ][
                    "terminal_status"
                ][
                    "counts"
                ],
                {
                    "AUTO_FINISHED": 1,
                    "DENIED": 1,
                    "HUMAN_REQUIRED": 1,
                },
            )

            self.assertEqual(
                report[
                    "categorical"
                ][
                    "final_risk"
                ][
                    "counts"
                ],
                {
                    "high": 1,
                    "low": 1,
                    "medium": 1,
                },
            )

    def test_partial_economics_are_not_reported_as_complete_totals(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            evaluation = (
                self._fixture(
                    Path(td)
                )
            )

            result = (
                generate_benchmark(
                    evaluation_root=(
                        evaluation
                    ),
                    regrade_id=(
                        "regrade-001"
                    ),
                    benchmark_id=(
                        "benchmark-001"
                    ),
                )
            )

            report = json.loads(
                (
                    result.benchmark_root
                    / "benchmark.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            economics = (
                report["economics"]
            )

            self.assertEqual(
                economics[
                    "run_summary_coverage"
                ],
                {
                    "available": 2,
                    "missing": 1,
                    "partial": 1,
                },
            )

            # Input/output are complete in
            # trials 1 and 2.
            self.assertEqual(
                economics[
                    "input_tokens"
                ][
                    "values"
                ],
                [
                    1000.0,
                    500.0,
                ],
            )

            # Cached tokens are incomplete
            # for trial 2.
            self.assertEqual(
                economics[
                    "cached_tokens"
                ][
                    "values"
                ],
                [
                    400.0,
                ],
            )

            # Partial trial-2 cost must not
            # become a total-cost sample.
            self.assertEqual(
                economics[
                    "cost_usd"
                ][
                    "values"
                ],
                [
                    0.01,
                ],
            )

            self.assertEqual(
                economics[
                    "cost_usd"
                ][
                    "missing_count"
                ],
                2,
            )

    def test_missing_run_summary_is_a_limitation_not_zero(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            evaluation = (
                self._fixture(
                    Path(td)
                )
            )

            result = (
                generate_benchmark(
                    evaluation_root=(
                        evaluation
                    ),
                    regrade_id=(
                        "regrade-001"
                    ),
                    benchmark_id=(
                        "benchmark-001"
                    ),
                )
            )

            report = json.loads(
                (
                    result.benchmark_root
                    / "benchmark.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertTrue(
                any(
                    "trial-003"
                    in limitation
                    and "economics unavailable"
                    in limitation
                    for limitation
                    in report[
                        "limitations"
                    ]
                )
            )

            self.assertNotIn(
                0.0,
                report[
                    "economics"
                ][
                    "cost_usd"
                ][
                    "values"
                ],
            )

    def test_existing_benchmark_id_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            evaluation = (
                self._fixture(
                    Path(td)
                )
            )

            generate_benchmark(
                evaluation_root=(
                    evaluation
                ),
                regrade_id=(
                    "regrade-001"
                ),
                benchmark_id=(
                    "benchmark-001"
                ),
            )

            with self.assertRaises(
                EvalBenchmarkError
            ):
                generate_benchmark(
                    evaluation_root=(
                        evaluation
                    ),
                    regrade_id=(
                        "regrade-001"
                    ),
                    benchmark_id=(
                        "benchmark-001"
                    ),
                )

    def test_incomplete_regrade_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            evaluation = (
                self._fixture(
                    Path(td)
                )
            )

            manifest_path = (
                evaluation
                / "regrades"
                / "regrade-001"
                / "manifest.json"
            )

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            manifest[
                "status"
            ] = "FAILED"

            self._write_json(
                manifest_path,
                manifest,
            )

            with self.assertRaises(
                EvalBenchmarkError
            ):
                generate_benchmark(
                    evaluation_root=(
                        evaluation
                    ),
                    regrade_id=(
                        "regrade-001"
                    ),
                    benchmark_id=(
                        "benchmark-001"
                    ),
                )

    def test_regrade_id_path_traversal_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            evaluation = (
                self._fixture(
                    Path(td)
                )
            )

            with self.assertRaises(
                EvalBenchmarkError
            ):
                generate_benchmark(
                    evaluation_root=(
                        evaluation
                    ),
                    regrade_id=(
                        "../regrades/"
                        "regrade-001"
                    ),
                    benchmark_id=(
                        "benchmark-001"
                    ),
                )

    def test_cost_total_calls_must_match_model_call_count(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            evaluation = (
                self._fixture(
                    Path(td)
                )
            )

            summary_path = (
                evaluation
                / "runs"
                / "eval-1-trial-002"
                / "run-summary.json"
            )

            summary = json.loads(
                summary_path.read_text(
                    encoding="utf-8"
                )
            )

            # Deliberately inconsistent:
            # two model calls exist, but the
            # cost block claims only one.
            summary["cost"] = {
                "total_usd": 0.005,
                "known_calls": 1,
                "total_calls": 1,
            }

            self._write_json(
                summary_path,
                summary,
            )

            result = (
                generate_benchmark(
                    evaluation_root=(
                        evaluation
                    ),
                    regrade_id=(
                        "regrade-001"
                    ),
                    benchmark_id=(
                        "benchmark-001"
                    ),
                )
            )

            report = json.loads(
                (
                    result.benchmark_root
                    / "benchmark.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                report[
                    "economics"
                ][
                    "cost_usd"
                ][
                    "values"
                ],
                [
                    0.01,
                ],
            )

            self.assertEqual(
                report[
                    "economics"
                ][
                    "cost_usd"
                ][
                    "missing_count"
                ],
                2,
            )

    def test_benchmarking_does_not_modify_source_evidence(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            evaluation = (
                self._fixture(
                    Path(td)
                )
            )

            source_paths = sorted(
                path
                for path
                in evaluation.rglob("*")
                if path.is_file()
            )

            before = {
                path.relative_to(
                    evaluation
                ).as_posix(): (
                    path.read_bytes()
                )
                for path in source_paths
            }

            generate_benchmark(
                evaluation_root=(
                    evaluation
                ),
                regrade_id=(
                    "regrade-001"
                ),
                benchmark_id=(
                    "benchmark-001"
                ),
            )

            after = {
                path.relative_to(
                    evaluation
                ).as_posix(): (
                    path.read_bytes()
                )
                for path in source_paths
            }

            self.assertEqual(
                before,
                after,
            )

    def test_benchmarking_does_not_execute_harness_or_commands(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            evaluation = (
                self._fixture(
                    Path(td)
                )
            )

            with patch(
                "aivp.application.run_new",
                side_effect=AssertionError(
                    "Harness must not execute"
                ),
            ), patch(
                "subprocess.run",
                side_effect=AssertionError(
                    "External commands must "
                    "not execute"
                ),
            ):
                result = (
                    generate_benchmark(
                        evaluation_root=(
                            evaluation
                        ),
                        regrade_id=(
                            "regrade-001"
                        ),
                        benchmark_id=(
                            "benchmark-001"
                        ),
                    )
                )

            self.assertEqual(
                result.trial_count,
                3,
            )

            self.assertEqual(
                result.overall_outcome,
                "ERROR",
            )


if __name__ == "__main__":
    unittest.main()
