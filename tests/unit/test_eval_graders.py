import json
import tempfile
import unittest

from pathlib import Path

from aivp.eval.graders import (
    EvalGraderError,
    grade_artifact_integrity,
    grade_diff,
    grade_expected_decision,
    grade_policy,
    grade_risk,
    grade_trial_from_artifacts,
    grade_verification,
)
from aivp.state.hashing import sha256_file


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

    def test_risk_passes_against_saved_aggregate(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            self._write_json(
                run_dir / "aggregate-risk.json",
                {
                    "final": "low",
                    "human_required": False,
                },
            )

            result = grade_risk(
                run_dir=run_dir,
                expected={
                    "risk": {
                        "final": "low",
                        "human_required": False,
                    }
                },
            )

            self.assertEqual(
                result.outcome,
                "PASS",
            )
            self.assertTrue(
                result.passed
            )

    def test_risk_mismatch_is_fail(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            self._write_json(
                run_dir / "aggregate-risk.json",
                {
                    "final": "high",
                    "human_required": True,
                },
            )

            result = grade_risk(
                run_dir=run_dir,
                expected={
                    "risk": {
                        "final": "low"
                    }
                },
            )

            self.assertEqual(
                result.outcome,
                "FAIL",
            )
            self.assertFalse(
                result.passed
            )

    def test_missing_risk_is_error(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            result = grade_risk(
                run_dir=Path(td),
                expected={
                    "risk": {
                        "final": "low"
                    }
                },
            )

            self.assertEqual(
                result.outcome,
                "ERROR",
            )

    def test_diff_constraints_pass(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            self._write_json(
                run_dir / "changed-paths.json",
                [
                    "tests/test_username.py",
                    "username.py",
                ],
            )

            (
                run_dir / "final.diff.txt"
            ).write_text(
                "line1\nline2\nline3\n",
                encoding="utf-8",
            )

            result = grade_diff(
                run_dir=run_dir,
                expected={
                    "diff": {
                        "required_paths": [
                            "username.py"
                        ],
                        "forbidden_paths": [
                            ".env"
                        ],
                        "max_changed_files": 2,
                        "max_diff_lines": 10,
                    }
                },
            )

            self.assertEqual(
                result.outcome,
                "PASS",
            )
            self.assertEqual(
                result.observed[
                    "changed_file_count"
                ],
                2,
            )
            self.assertEqual(
                result.observed[
                    "diff_lines"
                ],
                3,
            )

    def test_diff_constraint_violation_is_fail(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            self._write_json(
                run_dir / "changed-paths.json",
                [
                    ".env",
                    "username.py",
                ],
            )

            (
                run_dir / "final.diff.txt"
            ).write_text(
                "1\n2\n3\n4\n",
                encoding="utf-8",
            )

            result = grade_diff(
                run_dir=run_dir,
                expected={
                    "diff": {
                        "required_paths": [
                            "tests/test_username.py"
                        ],
                        "forbidden_paths": [
                            ".env"
                        ],
                        "max_changed_files": 1,
                        "max_diff_lines": 2,
                    }
                },
            )

            self.assertEqual(
                result.outcome,
                "FAIL",
            )
            self.assertFalse(
                result.passed
            )
            self.assertIn(
                "required paths missing",
                result.reason,
            )
            self.assertIn(
                "forbidden paths changed",
                result.reason,
            )

    def test_missing_changed_paths_is_error(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            result = grade_diff(
                run_dir=Path(td),
                expected={
                    "diff": {
                        "max_changed_files": 2
                    }
                },
            )

            self.assertEqual(
                result.outcome,
                "ERROR",
            )

    def test_exact_changed_path_set_is_order_independent(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            self._write_json(
                run_dir / "changed-paths.json",
                [
                    "b.py",
                    "a.py",
                ],
            )

            result = grade_diff(
                run_dir=run_dir,
                expected={
                    "diff": {
                        "changed_paths": [
                            "a.py",
                            "b.py",
                        ]
                    }
                },
            )

            self.assertEqual(
                result.outcome,
                "PASS",
            )

    def test_risk_and_diff_dispatch_from_saved_artifacts(
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
                        "risk": {
                            "final": "low"
                        },
                        "diff": {
                            "max_changed_files": 1
                        },
                    },
                    "graders": [
                        "risk",
                        "diff",
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
                run_dir / "aggregate-risk.json",
                {
                    "final": "low",
                    "human_required": False,
                },
            )

            self._write_json(
                run_dir / "changed-paths.json",
                [
                    "username.py"
                ],
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
                [
                    result.grader
                    for result in results
                ],
                [
                    "risk",
                    "diff",
                ],
            )

            self.assertTrue(
                all(
                    result.passed
                    for result in results
                )
            )

    def test_policy_denial_is_distinguished_from_other_terminal_status(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            self._write_json(
                run_dir / "status.json",
                {
                    "status": "DENIED",
                    "metrics": {
                        "policy_denied": True
                    },
                },
            )

            result = grade_policy(
                run_dir=run_dir,
                expected={
                    "policy": {
                        "outcome": "DENIED"
                    }
                },
            )

            self.assertEqual(
                result.outcome,
                "PASS",
            )

    def test_policy_human_required_is_distinguished(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            self._write_json(
                run_dir / "status.json",
                {
                    "status": (
                        "HUMAN_REQUIRED"
                    ),
                    "metrics": {
                        "policy_human_required": (
                            True
                        )
                    },
                },
            )

            result = grade_policy(
                run_dir=run_dir,
                expected={
                    "policy": {
                        "outcome": (
                            "HUMAN_REQUIRED"
                        )
                    }
                },
            )

            self.assertEqual(
                result.outcome,
                "PASS",
            )

    def test_non_policy_human_required_does_not_match_policy_gate(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            self._write_json(
                run_dir / "status.json",
                {
                    "status": (
                        "HUMAN_REQUIRED"
                    ),
                    "metrics": {
                        "budget_exceeded": True
                    },
                },
            )

            result = grade_policy(
                run_dir=run_dir,
                expected={
                    "policy": {
                        "outcome": (
                            "HUMAN_REQUIRED"
                        )
                    }
                },
            )

            self.assertEqual(
                result.outcome,
                "FAIL",
            )
            self.assertEqual(
                result.observed,
                "NONE",
            )

    def test_policy_internal_inconsistency_is_error(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)

            self._write_json(
                run_dir / "status.json",
                {
                    "status": (
                        "AUTO_FINISHED"
                    ),
                    "metrics": {
                        "policy_denied": True
                    },
                },
            )

            result = grade_policy(
                run_dir=run_dir,
                expected={
                    "policy": {
                        "outcome": "DENIED"
                    }
                },
            )

            self.assertEqual(
                result.outcome,
                "ERROR",
            )

    def test_artifact_integrity_passes_against_snapshot(
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
                / "run-1"
            )

            run_dir.mkdir(
                parents=True
            )

            artifact = (
                run_dir / "status.json"
            )

            artifact.write_text(
                '{"status":"AUTO_FINISHED"}\n',
                encoding="utf-8",
            )

            manifest_path = (
                evaluation_root
                / "integrity"
                / "trial-001.json"
            )

            self._write_json(
                manifest_path,
                {
                    "artifacts": [
                        {
                            "path": (
                                "status.json"
                            ),
                            "sha256": (
                                sha256_file(
                                    artifact
                                )
                            ),
                            "size_bytes": (
                                artifact.stat()
                                .st_size
                            ),
                        }
                    ]
                },
            )

            result = (
                grade_artifact_integrity(
                    evaluation_root=(
                        evaluation_root
                    ),
                    run_dir=run_dir,
                    trial_manifest={
                        "integrity_manifest": (
                            "integrity/"
                            "trial-001.json"
                        )
                    },
                )
            )

            self.assertEqual(
                result.outcome,
                "PASS",
            )
            self.assertEqual(
                result.observed[
                    "checked_artifacts"
                ],
                1,
            )

    def test_artifact_integrity_detects_tampering(
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
                / "run-1"
            )

            run_dir.mkdir(
                parents=True
            )

            artifact = (
                run_dir / "status.json"
            )

            artifact.write_text(
                "original\n",
                encoding="utf-8",
            )

            expected_sha = sha256_file(
                artifact
            )
            expected_size = (
                artifact.stat().st_size
            )

            self._write_json(
                evaluation_root
                / "integrity"
                / "trial-001.json",
                {
                    "artifacts": [
                        {
                            "path": (
                                "status.json"
                            ),
                            "sha256": (
                                expected_sha
                            ),
                            "size_bytes": (
                                expected_size
                            ),
                        }
                    ]
                },
            )

            artifact.write_text(
                "tampered\n",
                encoding="utf-8",
            )

            result = (
                grade_artifact_integrity(
                    evaluation_root=(
                        evaluation_root
                    ),
                    run_dir=run_dir,
                    trial_manifest={
                        "integrity_manifest": (
                            "integrity/"
                            "trial-001.json"
                        )
                    },
                )
            )

            self.assertEqual(
                result.outcome,
                "FAIL",
            )
            self.assertFalse(
                result.passed
            )

    def test_policy_and_integrity_dispatch_from_saved_artifacts(
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

            run_dir.mkdir(
                parents=True
            )

            status_path = (
                run_dir / "status.json"
            )

            self._write_json(
                status_path,
                {
                    "status": (
                        "HUMAN_REQUIRED"
                    ),
                    "metrics": {
                        "policy_human_required": (
                            True
                        )
                    },
                },
            )

            self._write_json(
                evaluation_root
                / "case-snapshot.json",
                {
                    "expected": {
                        "policy": {
                            "outcome": (
                                "HUMAN_REQUIRED"
                            )
                        }
                    },
                    "graders": [
                        "policy",
                        "artifact-integrity",
                    ],
                },
            )

            self._write_json(
                evaluation_root
                / "integrity"
                / "trial-001.json",
                {
                    "artifacts": [
                        {
                            "path": (
                                "status.json"
                            ),
                            "sha256": (
                                sha256_file(
                                    status_path
                                )
                            ),
                            "size_bytes": (
                                status_path
                                .stat()
                                .st_size
                            ),
                        }
                    ]
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
                    ),
                    "integrity_manifest": (
                        "integrity/"
                        "trial-001.json"
                    ),
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
                [
                    result.grader
                    for result in results
                ],
                [
                    "policy",
                    "artifact-integrity",
                ],
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
