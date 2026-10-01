import subprocess
import tempfile
import unittest

from pathlib import Path

from aivp.containment.docker_sandbox import (
    DockerSandbox,
    DockerSandboxPolicy,
)
from aivp.execution.runtime import (
    Budgets,
    Runtime,
)
from aivp.verification.deterministic import (
    DeterministicVerifier,
)


IMAGE = "postgres:17-alpine"


class DockerVerificationIntegrationTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls):
        daemon = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if daemon.returncode != 0:
            raise unittest.SkipTest(
                "Docker daemon is unavailable"
            )

        image = subprocess.run(
            [
                "docker",
                "image",
                "inspect",
                IMAGE,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if image.returncode != 0:
            raise unittest.SkipTest(
                f"Required local image missing: {IMAGE}"
            )

    def test_verification_runs_inside_sandbox(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            workspace = root / "workspace"
            run_dir = root / "run"

            workspace.mkdir()
            run_dir.mkdir()

            runtime = Runtime(
                run_dir,
                Budgets(),
            )

            sandbox = DockerSandbox(
                DockerSandboxPolicy(
                    image=IMAGE,
                )
            )

            verifier = DeterministicVerifier(
                runtime,
                sandbox=sandbox,
            )

            config = {
                "verification": [
                    {
                        "name": "sandbox-proof",
                        "argv": [
                            "sh",
                            "-lc",
                            (
                                "printf 'verified\\n' "
                                "> verification-proof.txt"
                            ),
                        ],
                        "required": True,
                        "timeout_seconds": 10,
                    }
                ]
            }

            result = verifier.verify(
                repo=workspace,
                config=config,
                phase="round-0",
            )

            self.assertTrue(
                result["passed"]
            )

            self.assertEqual(
                result["results"][0][
                    "returncode"
                ],
                0,
            )

            self.assertEqual(
                result["results"][0][
                    "argv"
                ],
                config["verification"][0][
                    "argv"
                ],
            )

            self.assertEqual(
                (
                    workspace
                    / "verification-proof.txt"
                ).read_text(
                    encoding="utf-8"
                ),
                "verified\n",
            )

            events = (
                run_dir / "events.json"
            ).read_text(
                encoding="utf-8"
            )

            self.assertIn(
                "docker run",
                events,
            )


if __name__ == "__main__":
    unittest.main()
