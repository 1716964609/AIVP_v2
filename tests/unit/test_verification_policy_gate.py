import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.errors import PolicyDenied
from aivp.policy.capability import (
    Capability,
    Decision,
    StaticCapabilityPolicy,
)
from aivp.verification.deterministic import (
    DeterministicVerifier,
)


class RecordingRuntime:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.calls = []

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
        self.calls.append(
            tuple(argv)
        )

        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="ok\n",
            stderr="",
        )


class VerificationPolicyGateTests(
    unittest.TestCase
):
    def test_denial_blocks_command_execution(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()

            repo = root / "repo"
            repo.mkdir()

            runtime = RecordingRuntime(
                run_dir
            )

            policy = StaticCapabilityPolicy(
                {
                    Capability.C1_LOCAL_MUTATE:
                        Decision.DENY,
                }
            )

            verifier = DeterministicVerifier(
                runtime,
                policy=policy,
            )

            config = {
                "verification": [
                    {
                        "name": "tests",
                        "argv": [
                            "echo",
                            "must-not-run",
                        ],
                    }
                ]
            }

            with self.assertRaises(
                PolicyDenied
            ):
                verifier.verify(
                    repo=repo,
                    config=config,
                    phase="round-0",
                )

            self.assertEqual(
                runtime.calls,
                [],
            )

            self.assertFalse(
                (
                    run_dir
                    / "round-0.verification.json"
                ).exists()
            )

    def test_no_commands_remains_noop_when_denied(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()

            repo = root / "repo"
            repo.mkdir()

            runtime = RecordingRuntime(
                run_dir
            )

            policy = StaticCapabilityPolicy(
                {
                    Capability.C1_LOCAL_MUTATE:
                        Decision.DENY,
                }
            )

            verifier = DeterministicVerifier(
                runtime,
                policy=policy,
            )

            result = verifier.verify(
                repo=repo,
                config={},
                phase="round-0",
            )

            self.assertTrue(
                result["passed"]
            )

            self.assertEqual(
                runtime.calls,
                [],
            )


if __name__ == "__main__":
    unittest.main()
