import tempfile
import unittest

from pathlib import Path

from aivp.errors import StateIntegrityError
from aivp.state.hashing import sha256_file
from aivp.state.resume import build_resume_plan


class ResumePlanTests(unittest.TestCase):
    def test_generated_resumes_at_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "generated.diff"
            artifact.write_text(
                "diff-content",
                encoding="utf-8",
            )

            plan = build_resume_plan(
                run_id="run-1",
                checkpoint={
                    "state": "GENERATED",
                    "attempt": 1,
                },
                artifact_records=[
                    {
                        "path": str(artifact),
                        "sha256": sha256_file(
                            artifact
                        ),
                        "size_bytes": (
                            artifact.stat().st_size
                        ),
                    }
                ],
            )

            self.assertEqual(
                plan.current_state,
                "GENERATED",
            )
            self.assertEqual(
                plan.next_state,
                "VERIFYING",
            )
            self.assertEqual(
                plan.resume_attempt,
                2,
            )

    def test_verified_resumes_at_review(self):
        plan = build_resume_plan(
            run_id="run-1",
            checkpoint={
                "state": "VERIFIED",
                "attempt": 3,
            },
            artifact_records=[],
        )

        self.assertEqual(
            plan.next_state,
            "REVIEWING",
        )
        self.assertEqual(
            plan.resume_attempt,
            4,
        )

    def test_corrupt_artifact_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "generated.diff"
            artifact.write_text(
                "original",
                encoding="utf-8",
            )

            expected_hash = sha256_file(
                artifact
            )
            expected_size = (
                artifact.stat().st_size
            )

            artifact.write_text(
                "corrupted",
                encoding="utf-8",
            )

            with self.assertRaises(
                StateIntegrityError
            ):
                build_resume_plan(
                    run_id="run-1",
                    checkpoint={
                        "state": "GENERATED",
                        "attempt": 1,
                    },
                    artifact_records=[
                        {
                            "path": str(
                                artifact
                            ),
                            "sha256": expected_hash,
                            "size_bytes": (
                                expected_size
                            ),
                        }
                    ],
                )

    def test_unknown_state_fails_closed(self):
        with self.assertRaises(
            StateIntegrityError
        ):
            build_resume_plan(
                run_id="run-1",
                checkpoint={
                    "state": "SOMETHING_WEIRD",
                },
                artifact_records=[],
            )


if __name__ == "__main__":
    unittest.main()
