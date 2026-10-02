from typing import Any, Dict, Optional
from pathlib import Path

from aivp.containment.docker_sandbox import (
    DockerSandbox,
    DockerSandboxPolicy,
)
from aivp.errors import AIVPError

from aivp.execution.runtime import Budgets


def budgets_from(
    config: Dict[str, Any],
) -> Budgets:
    budgets = config.get(
        "budgets",
        {},
    )

    return Budgets(
        max_fix_iterations=int(
            budgets.get(
                "max_fix_iterations",
                2,
            )
        ),
        codex_max_calls=int(
            budgets.get(
                "codex_max_calls",
                4,
            )
        ),
        claude_max_calls=int(
            budgets.get(
                "claude_max_calls",
                3,
            )
        ),
        codex_timeout_seconds=int(
            budgets.get(
                "codex_timeout_seconds",
                300,
            )
        ),
        claude_timeout_seconds=int(
            budgets.get(
                "claude_timeout_seconds",
                300,
            )
        ),
        whole_run_timeout_seconds=int(
            budgets.get(
                "whole_run_timeout_seconds",
                900,
            )
        ),
    )


def verification_sandbox_from(
    config: Dict[str, Any],
) -> Optional[DockerSandbox]:
    raw = config.get(
        "verification_sandbox"
    )

    if raw is None:
        return None

    if not isinstance(raw, dict):
        raise AIVPError(
            "verification_sandbox must "
            "be an object"
        )

    enabled = raw.get(
        "enabled",
        False,
    )

    if not isinstance(enabled, bool):
        raise AIVPError(
            "verification_sandbox.enabled "
            "must be boolean"
        )

    if not enabled:
        return None

    image = raw.get("image")

    if (
        not isinstance(image, str)
        or not image.strip()
    ):
        raise AIVPError(
            "Enabled verification sandbox "
            "requires image"
        )

    try:
        cpus = float(
            raw.get("cpus", 1.0)
        )

        pids_limit = int(
            raw.get("pids_limit", 128)
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise AIVPError(
            "Invalid verification sandbox "
            "resource limits"
        ) from exc

    memory = raw.get(
        "memory",
        "512m",
    )

    user = raw.get(
        "user",
        "65532:65532",
    )

    tmpfs_size = raw.get(
        "tmpfs_size",
        "64m",
    )

    for name, value in (
        ("memory", memory),
        ("user", user),
        ("tmpfs_size", tmpfs_size),
    ):
        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise AIVPError(
                "verification_sandbox."
                f"{name} must be a "
                "non-empty string"
            )

    return DockerSandbox(
        DockerSandboxPolicy(
            image=image,
            cpus=cpus,
            memory=memory,
            pids_limit=pids_limit,
            user=user,
            tmpfs_size=tmpfs_size,
        )
    )


def tracing_from(
    config: Dict[str, Any],
    run_dir: Path,
):
    from aivp.telemetry.tracing import (
        TracingSession,
    )

    raw = config.get(
        "telemetry",
        {},
    )

    if raw is None:
        raw = {}

    if not isinstance(raw, dict):
        raise AIVPError(
            "telemetry must be an object"
        )

    enabled = raw.get(
        "otel",
        False,
    )

    if not isinstance(enabled, bool):
        raise AIVPError(
            "telemetry.otel must be boolean"
        )

    return TracingSession(
        enabled=enabled,
        output_path=(
            run_dir
            / "otel-spans.jsonl"
        ),
    )


def context_budget_from(
    config: Dict[str, Any],
):
    from aivp.context.base import (
        ContextBudget,
    )

    raw = config.get("context")

    if raw is None:
        return None

    if not isinstance(raw, dict):
        raise AIVPError(
            "context must be an object"
        )

    enabled = raw.get(
        "enabled",
        True,
    )

    if not isinstance(enabled, bool):
        raise AIVPError(
            "context.enabled must be boolean"
        )

    if not enabled:
        return None

    try:
        max_files = int(
            raw.get(
                "max_files",
                20,
            )
        )

        max_chars = int(
            raw.get(
                "max_chars",
                120_000,
            )
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise AIVPError(
            "Invalid context budget"
        ) from exc

    if max_files <= 0:
        raise AIVPError(
            "context.max_files must "
            "be greater than zero"
        )

    if max_chars <= 0:
        raise AIVPError(
            "context.max_chars must "
            "be greater than zero"
        )

    return ContextBudget(
        max_files=max_files,
        max_chars=max_chars,
    )
