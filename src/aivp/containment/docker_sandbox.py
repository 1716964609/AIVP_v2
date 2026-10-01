from __future__ import annotations

import subprocess

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from aivp.errors import AIVPError


@dataclass(frozen=True)
class DockerSandboxPolicy:
    image: str
    cpus: float = 1.0
    memory: str = "512m"
    pids_limit: int = 128
    user: str = "65532:65532"
    tmpfs_size: str = "64m"

    def __post_init__(self) -> None:
        if not self.image.strip():
            raise AIVPError(
                "Sandbox image must not be empty"
            )

        if self.cpus <= 0:
            raise AIVPError(
                "Sandbox CPU limit must be positive"
            )

        if self.pids_limit <= 0:
            raise AIVPError(
                "Sandbox PID limit must be positive"
            )


class DockerSandbox:
    def __init__(
        self,
        policy: DockerSandboxPolicy,
    ):
        self.policy = policy

    def build_argv(
        self,
        *,
        workspace: Path,
        command: Sequence[str],
    ) -> list[str]:
        workspace = (
            workspace
            .expanduser()
            .resolve()
        )

        if not workspace.is_dir():
            raise AIVPError(
                "Sandbox workspace must be "
                f"an existing directory: {workspace}"
            )

        if not command:
            raise AIVPError(
                "Sandbox command must not be empty"
            )

        mount = (
            "type=bind,"
            f"src={workspace},"
            "dst=/workspace"
        )

        tmpfs = (
            "/tmp:"
            "rw,nosuid,nodev,noexec,"
            f"size={self.policy.tmpfs_size}"
        )

        return [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--read-only",
            "--tmpfs",
            tmpfs,
            "--pids-limit",
            str(self.policy.pids_limit),
            "--memory",
            self.policy.memory,
            "--cpus",
            str(self.policy.cpus),
            "--user",
            self.policy.user,
            "--mount",
            mount,
            "--workdir",
            "/workspace",
            "--env",
            "HOME=/tmp",
            self.policy.image,
            *[
                str(value)
                for value in command
            ],
        ]

    def run(
        self,
        *,
        workspace: Path,
        command: Sequence[str],
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        if timeout_seconds <= 0:
            raise AIVPError(
                "Sandbox timeout must be positive"
            )

        argv = self.build_argv(
            workspace=workspace,
            command=command,
        )

        return subprocess.run(
            argv,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
