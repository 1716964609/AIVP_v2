import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aivp.eval.regrade import (
    EvalRegradeError,
    regrade_evaluation,
)


class EvalRegradeTests(unittest.TestCase):
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

    def _evaluation(
        self,
        root: Path,
        *,
        statuses=(
            "AUTO_FINISHED",
        ),
    ) -> Path:
        evaluation_root = (
            root / "evaluation"
        )

        self._write_json(
            evaluation_root
            / "evaluation-manifest.json",
            {
                "evaluation_id": "eval-1",
                "case_id": "case-1",
                "status": "COMPLETED",
            },
        )

        self._write_json(
            evaluation_root
            / "case-snapshot.json",
            {
                "expected": {
                    "terminal_status": (
                        "AUTO_FINISHED"
                    )
                },
                "graders": [
                    "expected-decision"
                ],
            },
        )

        for index, status in enumerate(
            statuses,
            start=1,
        ):
            trial_id = (
                f"trial-{index:03d}"
            )

            run_relative = (
                "runs/"
                f"eval-1-{trial_id}"
            )

            self._write_json(
                evaluation_root
                / "trials"
                / f"{trial_id}.json",
                {
                    "status": "COMPLETED",
                    "run_dir": run_relative,
                },
            )

            self._write_json(
                evaluation_root
                / run_relative
                / "status.json",
                {
                    "status": status,
                    "metrics": {},
                },
            )

        return evaluation_root

    def test_regrades_all_completed_trials_from_saved_artifacts(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            evaluation_root = (
                self._evaluation(
                    root,
                    statuses=(
                        "AUTO_FINISHED",
                        "AUTO_FINISHED",
                    ),
                )
            )

            result = regrade_evaluation(
                evaluation_root=(
                    evaluation_root
                ),
                regrade_id="regrade-001",
            )

            self.assertEqual(
                result.trial_count,
                2,
            )

            self.assertEqual(
                result.overall_outcome,
                "PASS",
            )

            manifest = json.loads(
                (
                    result.regrade_root
                    / "manifest.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                manifest["status"],
                "COMPLETED",
            )

            self.assertEqual(
                manifest["trial_counts"],
                {
                    "ERROR": 0,
                    "FAIL": 0,
                    "PASS": 2,
                },
            )

            self.assertEqual(
                manifest["grader_counts"],
                {
                    "ERROR": 0,
                    "FAIL": 0,
                    "PASS": 2,
                },
            )

            self.assertTrue(
                (
                    result.regrade_root
                    / "trial-001.json"
                ).is_file()
            )

            self.assertTrue(
                (
                    result.regrade_root
                    / "trial-002.json"
                ).is_file()
            )

    def test_regrade_recomputes_after_raw_artifact_change(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            evaluation_root = (
                self._evaluation(root)
            )

            first = regrade_evaluation(
                evaluation_root=(
                    evaluation_root
                ),
                regrade_id="regrade-001",
            )

            self.assertEqual(
                first.overall_outcome,
                "PASS",
            )

            status_path = (
                evaluation_root
                / "runs"
                / "eval-1-trial-001"
                / "status.json"
            )

            self._write_json(
                status_path,
                {
                    "status": (
                        "HUMAN_REQUIRED"
                    ),
                    "metrics": {},
                },
            )

            second = regrade_evaluation(
                evaluation_root=(
                    evaluation_root
                ),
                regrade_id="regrade-002",
            )

            self.assertEqual(
                second.overall_outcome,
                "FAIL",
            )

            first_trial = json.loads(
                (
                    first.regrade_root
                    / "trial-001.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            second_trial = json.loads(
                (
                    second.regrade_root
                    / "trial-001.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                first_trial[
                    "overall_outcome"
                ],
                "PASS",
            )

            self.assertEqual(
                second_trial[
                    "overall_outcome"
                ],
                "FAIL",
            )

    def test_noncompleted_trial_is_recorded_as_error(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            evaluation_root = (
                self._evaluation(root)
            )

            trial_path = (
                evaluation_root
                / "trials"
                / "trial-001.json"
            )

            trial = json.loads(
                trial_path.read_text(
                    encoding="utf-8"
                )
            )

            trial["status"] = "FAILED"

            self._write_json(
                trial_path,
                trial,
            )

            result = regrade_evaluation(
                evaluation_root=(
                    evaluation_root
                ),
                regrade_id="regrade-001",
            )

            self.assertEqual(
                result.overall_outcome,
                "ERROR",
            )

            output = json.loads(
                (
                    result.regrade_root
                    / "trial-001.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                output[
                    "source_trial_status"
                ],
                "FAILED",
            )

            self.assertEqual(
                output[
                    "overall_outcome"
                ],
                "ERROR",
            )

            self.assertEqual(
                output[
                    "grader_results"
                ],
                [],
            )

    def test_existing_regrade_id_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            evaluation_root = (
                self._evaluation(root)
            )

            regrade_evaluation(
                evaluation_root=(
                    evaluation_root
                ),
                regrade_id="regrade-001",
            )

            with self.assertRaises(
                EvalRegradeError
            ):
                regrade_evaluation(
                    evaluation_root=(
                        evaluation_root
                    ),
                    regrade_id=(
                        "regrade-001"
                    ),
                )

    def test_missing_trial_manifests_fail_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            evaluation_root = (
                root / "evaluation"
            )

            self._write_json(
                evaluation_root
                / "evaluation-manifest.json",
                {
                    "evaluation_id": (
                        "eval-1"
                    )
                },
            )

            (
                evaluation_root
                / "trials"
            ).mkdir(
                parents=True
            )

            with self.assertRaises(
                EvalRegradeError
            ):
                regrade_evaluation(
                    evaluation_root=(
                        evaluation_root
                    ),
                    regrade_id=(
                        "regrade-001"
                    ),
                )

    def test_regrading_does_not_modify_source_evidence(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            evaluation_root = (
                self._evaluation(root)
            )

            source_paths = [
                (
                    evaluation_root
                    / "evaluation-manifest.json"
                ),
                (
                    evaluation_root
                    / "case-snapshot.json"
                ),
                (
                    evaluation_root
                    / "trials"
                    / "trial-001.json"
                ),
                (
                    evaluation_root
                    / "runs"
                    / "eval-1-trial-001"
                    / "status.json"
                ),
            ]

            before = {
                path: path.read_bytes()
                for path in source_paths
            }

            regrade_evaluation(
                evaluation_root=(
                    evaluation_root
                ),
                regrade_id="regrade-001",
            )

            after = {
                path: path.read_bytes()
                for path in source_paths
            }

            self.assertEqual(
                before,
                after,
            )

    def test_regrading_does_not_execute_harness_or_commands(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            evaluation_root = (
                self._evaluation(root)
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
                    regrade_evaluation(
                        evaluation_root=(
                            evaluation_root
                        ),
                        regrade_id=(
                            "regrade-001"
                        ),
                    )
                )

            self.assertEqual(
                result.overall_outcome,
                "PASS",
            )


if __name__ == "__main__":
    unittest.main()
