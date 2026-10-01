import subprocess
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from aivp.containment.docker_sandbox import (
    DockerSandbox,
    DockerSandboxPolicy,
)
from aivp.errors import AIVPError


class DockerSandboxTests(
    unittest.TestCase
):
    def sandbox(self) -> DockerSandbox:
        return DockerSandbox(
            DockerSandboxPolicy(
                image="aivp-test:local",
            )
        )

    def test_build_argv_contains_containment_flags(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            argv = self.sandbox().build_argv(
                workspace=workspace,
                command=[
                    "python",
                    "-m",
                    "unittest",
                ],
            )

            self.assertIn(
                "--network",
                argv,
            )

            self.assertEqual(
                argv[
                    argv.index("--network")
                    + 1
                ],
                "none",
            )

            self.assertIn(
                "ALL",
                argv,
            )

            self.assertIn(
                "no-new-privileges:true",
                argv,
            )

            self.assertIn(
                "--read-only",
                argv,
            )

            self.assertIn(
                "--pids-limit",
                argv,
            )

            self.assertIn(
                "--memory",
                argv,
            )

            self.assertIn(
                "--cpus",
                argv,
            )

            self.assertIn(
                "--user",
                argv,
            )

            self.assertIn(
                "HOME=/tmp",
                argv,
            )

    def test_only_execution_workspace_is_mounted(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()

            argv = self.sandbox().build_argv(
                workspace=workspace,
                command=["true"],
            )

            mounts = [
                argv[index + 1]
                for index, value in enumerate(argv)
                if value == "--mount"
            ]

            self.assertEqual(
                mounts,
                [
                    (
                        "type=bind,"
                        f"src={workspace},"
                        "dst=/workspace"
                    )
                ],
            )

    def test_run_invokes_docker_without_shell(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="ok\n",
                stderr="",
            )

            with patch(
                "aivp.containment.docker_sandbox."
                "subprocess.run",
                return_value=completed,
            ) as run:
                result = self.sandbox().run(
                    workspace=workspace,
                    command=[
                        "python",
                        "-V",
                    ],
                    timeout_seconds=30,
                )

            self.assertEqual(
                result.returncode,
                0,
            )

            kwargs = run.call_args.kwargs

            self.assertNotIn(
                "shell",
                kwargs,
            )

            self.assertEqual(
                kwargs["timeout"],
                30,
            )

    def test_missing_workspace_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            missing = (
                Path(tmp)
                / "missing"
            )

            with self.assertRaises(
                AIVPError
            ):
                self.sandbox().build_argv(
                    workspace=missing,
                    command=["true"],
                )


if __name__ == "__main__":
    unittest.main()
