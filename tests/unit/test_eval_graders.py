import json
import tempfile
import unittest

from pathlib import Path

from aivp.eval.graders import (
    EvalGraderError,
    grade_expected_decision,
    grade_trial_from_artifacts,
    grade_verification,
)


class EvalGraderTests(unittest.TestCase):
    def _write_json(
        self,
        path: Path,
        data,
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                data,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

    def test_expected_decision_passes(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            self._write_json(
                run_dir / "status.json",
                {
                    "status": (
                        "AUTO_FINISHED"
                    )
                },
            )

            result = (
                grade_expected_decision(
                    run_dir=run_dir,
                    expected={
                        "terminal_status": (
                            "AUTO_FINISHED"
                        )
                    },
                )
            )

            self.assertTrue(
                result.passed
            )
            self.assertEqual(
                result.outcome,
                "PASS",
            )

    def test_expected_decision_mismatch_is_fail(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            self._write_json(
                run_dir / "status.json",
                {
                    "status": (
                        "HUMAN_REQUIRED"
                    )
                },
            )

            result = (
                grade_expected_decision(
                    run_dir=run_dir,
                    expected={
                        "terminal_status": (
                            "AUTO_FINISHED"
                        )
                    },
                )
            )

            self.assertFalse(
                result.passed
            )
            self.assertEqual(
                result.outcome,
                "FAIL",
            )
            self.assertEqual(
                result.observed,
                "HUMAN_REQUIRED",
            )

    def test_missing_status_is_error_not_fail(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            result = (
                grade_expected_decision(
                    run_dir=Path(td),
                    expected={
                        "terminal_status": (
                            "AUTO_FINISHED"
                        )
                    },
                )
            )

            self.assertFalse(
                result.passed
            )
            self.assertEqual(
                result.outcome,
                "ERROR",
            )

    def test_verification_uses_latest_round(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            self._write_json(
                run_dir
                / "round-0.verification.json",
                {
                    "passed": False
                },
            )

            self._write_json(
                run_dir
                / "round-1.verification.json",
                {
                    "passed": True
                },
            )

            result = grade_verification(
                run_dir=run_dir,
                expected={
                    "verification": {
                        "passed": True
                    }
                },
            )

            self.assertTrue(
                result.passed
            )
            self.assertEqual(
                result.outcome,
                "PASS",
            )
            self.assertEqual(
                result.evidence,
                (
                    "round-1.verification.json",
                ),
            )

    def test_missing_verification_is_error(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            result = grade_verification(
                run_dir=Path(td),
                expected={
                    "verification": {
                        "passed": True
                    }
                },
            )

            self.assertEqual(
                result.outcome,
                "ERROR",
            )
            self.assertFalse(
                result.passed
            )

    def test_grades_trial_only_from_saved_artifacts(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            evaluation_root = (
                root / "evaluation"
            )

            run_dir = (
                evaluation_root
                / "runs"
                / "eval-test-trial-001"
            )

            self._write_json(
                evaluation_root
                / "case-snapshot.json",
                {
                    "expected": {
                        "terminal_status": (
                            "AUTO_FINISHED"
                        ),
                        "verification": {
                            "passed": True
                        },
                    },
                    "graders": [
                        "expected-decision",
                        "verification",
                    ],
                },
            )

            self._write_json(
                evaluation_root
                / "trials"
                / "trial-001.json",
                {
                    "run_dir": (
                        "runs/"
                        "eval-test-trial-001"
                    )
                },
            )

            self._write_json(
                run_dir / "status.json",
                {
                    "status": (
                        "AUTO_FINISHED"
                    )
                },
            )

            self._write_json(
                run_dir
                / "round-0.verification.json",
                {
                    "passed": True
                },
            )

            results = (
                grade_trial_from_artifacts(
                    evaluation_root=(
                        evaluation_root
                    ),
                    trial_id="trial-001",
                )
            )

            self.assertEqual(
                len(results),
                2,
            )

            self.assertEqual(
                [
                    result.outcome
                    for result in results
                ],
                [
                    "PASS",
                    "PASS",
                ],
            )

            self.assertEqual(
                results[0].evidence,
                (
                    "runs/"
                    "eval-test-trial-001/"
                    "status.json",
                ),
            )

    def test_run_dir_path_escape_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            evaluation_root = (
                root / "evaluation"
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

            self._write_json(
                evaluation_root
                / "trials"
                / "trial-001.json",
                {
                    "run_dir": "../../escape"
                },
            )

            with self.assertRaises(
                EvalGraderError
            ):
                grade_trial_from_artifacts(
                    evaluation_root=(
                        evaluation_root
                    ),
                    trial_id="trial-001",
                )


if __name__ == "__main__":
    unittest.main()
