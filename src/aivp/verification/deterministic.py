import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Sequence

from aivp.artifacts.io import dump_json
from aivp.containment.docker_sandbox import (
    DockerSandbox,
)
from aivp.errors import AIVPError
from aivp.policy.capability import (
    Capability,
    CapabilityRequest,
    StaticCapabilityPolicy,
    v2_default_policy,
)


class VerificationRuntime(Protocol):
    run_dir: Path

    def command(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        timeout_seconds: int,
        log_stem: str,
        stdin_text: Optional[str] = None,
        actor: Optional[str] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        ...



class _SandboxedVerificationRuntime:
    def __init__(
        self,
        runtime: VerificationRuntime,
        sandbox: DockerSandbox,
        workspace: Path,
    ):
        self.runtime = runtime
        self.sandbox = sandbox
        self.workspace = (
            workspace
            .expanduser()
            .resolve()
        )
        self.run_dir = runtime.run_dir

    def command(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        timeout_seconds: int,
        log_stem: str,
        stdin_text: Optional[str] = None,
        actor: Optional[str] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        requested_cwd = (
            cwd.expanduser().resolve()
        )

        if requested_cwd != self.workspace:
            raise AIVPError(
                "Sandbox verification cwd "
                "must equal execution workspace"
            )

        docker_argv = (
            self.sandbox.build_argv(
                workspace=self.workspace,
                command=argv,
            )
        )

        return self.runtime.command(
            docker_argv,
            cwd=self.workspace,
            timeout_seconds=timeout_seconds,
            log_stem=log_stem,
            stdin_text=stdin_text,
            actor=actor,
            check=check,
        )



def run_verification(
    runtime: VerificationRuntime,
    repo: Path,
    config: Dict[str, Any],
    phase: str,
    policy: Optional[
        StaticCapabilityPolicy
    ] = None,
) -> Dict[str, Any]:
    results = []
    all_required_pass = True
    commands = config.get("verification", [])

    if not commands:
        return {
            "passed": True,
            "results": [],
            "note": "No verification commands configured",
        }

    effective_policy = (
        policy or v2_default_policy()
    )

    for i, spec in enumerate(commands):
        name = str(spec.get("name", f"gate-{i+1}"))
        argv = spec.get("argv")

        if not isinstance(argv, list) or not argv:
            raise AIVPError(
                f"verification[{i}].argv must be a non-empty array"
            )

        required = bool(spec.get("required", True))
        timeout = int(spec.get("timeout_seconds", 180))

        effective_policy.authorize(
            CapabilityRequest(
                capability=(
                    Capability.C1_LOCAL_MUTATE
                ),
                actor="verifier",
                action="verification_exec",
                target=str(
                    repo.expanduser().resolve()
                ),
            )
        )

        cp = runtime.command(
            argv,
            cwd=repo,
            timeout_seconds=timeout,
            log_stem=f"{phase}.verify.{i+1}.{name}",
            check=False,
        )

        passed = cp.returncode == 0

        if required and not passed:
            all_required_pass = False

        results.append(
            {
                "name": name,
                "argv": argv,
                "required": required,
                "returncode": cp.returncode,
                "passed": passed,
                "stdout_tail": cp.stdout[-4000:],
                "stderr_tail": cp.stderr[-4000:],
            }
        )

    payload = {
        "passed": all_required_pass,
        "results": results,
    }

    dump_json(
        runtime.run_dir / f"{phase}.verification.json",
        payload,
    )

    return payload


def verification_summary(
    verification: Dict[str, Any],
) -> str:
    lines = []

    for result in verification.get("results", []):
        state = "PASS" if result.get("passed") else "FAIL"

        lines.append(
            f"[{state}] {result.get('name')}\n"
            f"stdout:\n{result.get('stdout_tail','')}\n"
            f"stderr:\n{result.get('stderr_tail','')}"
        )

    return (
        "\n\n".join(lines)
        or "No deterministic gates configured."
    )


class DeterministicVerifier:
    def __init__(
        self,
        runtime: VerificationRuntime,
        sandbox: Optional[
            DockerSandbox
        ] = None,
        policy: Optional[
            StaticCapabilityPolicy
        ] = None,
    ):
        self.runtime = runtime
        self.sandbox = sandbox
        self.policy = (
            policy or v2_default_policy()
        )

    def verify(
        self,
        *,
        repo: Path,
        config: Dict[str, Any],
        phase: str,
    ) -> Dict[str, Any]:
        runtime: VerificationRuntime = (
            self.runtime
        )

        if self.sandbox is not None:
            runtime = (
                _SandboxedVerificationRuntime(
                    self.runtime,
                    self.sandbox,
                    repo,
                )
            )

        return run_verification(
            runtime,
            repo,
            config,
            phase,
            policy=self.policy,
        )
