import subprocess
import tempfile
import unittest
from pathlib import Path

from aivp.legacy.orchestrator_v1 import (
    run_verification as legacy_run_verification,
    verification_summary as legacy_verification_summary,
)

from aivp.verification.deterministic import (
    run_verification,
    verification_summary,
)


class FakeRuntime:
    def __init__(self, run_dir: Path, returncodes):
        self.run_dir = run_dir
        self.returncodes = iter(returncodes)

    def command(
        self,
        argv,
        *,
        cwd,
        timeout_seconds,
        log_stem,
        stdin_text=None,
        actor=None,
        check=False,
    ):
        rc = next(self.returncodes)

        return subprocess.CompletedProcess(
            argv,
            rc,
            stdout=f"stdout-{rc}",
            stderr=f"stderr-{rc}",
        )


class VerificationCompatibilityTests(unittest.TestCase):
    def run_pair(self, config, returncodes):
        with tempfile.TemporaryDirectory() as legacy_dir, \
             tempfile.TemporaryDirectory() as new_dir:

            repo = Path(legacy_dir)

            legacy_runtime = FakeRuntime(
                Path(legacy_dir),
                list(returncodes),
            )

            new_runtime = FakeRuntime(
                Path(new_dir),
                list(returncodes),
            )

            legacy = legacy_run_verification(
                legacy_runtime,
                repo,
                config,
                "round-0",
            )

            new = run_verification(
                new_runtime,
                repo,
                config,
                "round-0",
            )

            return legacy, new

    def test_no_verification_commands(self):
        legacy, new = self.run_pair({}, [])
        self.assertEqual(new, legacy)

    def test_all_required_pass(self):
        config = {
            "verification": [
                {
                    "name": "tests",
                    "argv": ["python3", "-m", "unittest"],
                    "required": True,
                    "timeout_seconds": 120,
                }
            ]
        }

        legacy, new = self.run_pair(config, [0])
        self.assertEqual(new, legacy)

    def test_required_failure_matches_legacy(self):
        config = {
            "verification": [
                {
                    "name": "tests",
                    "argv": ["test-command"],
                    "required": True,
                },
                {
                    "name": "optional",
                    "argv": ["optional-command"],
                    "required": False,
                },
            ]
        }

        legacy, new = self.run_pair(
            config,
            [1, 0],
        )

        self.assertEqual(new, legacy)
        self.assertFalse(new["passed"])

    def test_optional_failure_does_not_fail_overall(self):
        config = {
            "verification": [
                {
                    "name": "optional",
                    "argv": ["optional-command"],
                    "required": False,
                }
            ]
        }

        legacy, new = self.run_pair(config, [1])

        self.assertEqual(new, legacy)
        self.assertTrue(new["passed"])

    def test_summary_matches_legacy(self):
        payload = {
            "passed": False,
            "results": [
                {
                    "name": "tests",
                    "passed": False,
                    "stdout_tail": "out",
                    "stderr_tail": "err",
                }
            ],
        }

        self.assertEqual(
            verification_summary(payload),
            legacy_verification_summary(payload),
        )


if __name__ == "__main__":
    unittest.main()
