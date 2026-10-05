from __future__ import annotations

import json
import re
import subprocess

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Optional

from aivp.containment.docker_sandbox import (
    AIVP_DOCKER_OWNER_LABEL,
    AIVP_DOCKER_OWNER_VALUE,
    AIVP_DOCKER_RESOURCE_LABEL,
    AIVP_DOCKER_RESOURCE_VALUE,
)
from aivp.errors import AIVPError


@dataclass(frozen=True)
class DockerContainer:
    container_id: str
    created_at: datetime
    running: bool
    labels: Mapping[str, str]


@dataclass(frozen=True)
class DockerCleanupResult:
    container_id: str
    removed: bool
    dry_run: bool
    age_seconds: float
    reason: str


def _run_docker(
    *args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            *args,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _require_success(
    cp: subprocess.CompletedProcess[str],
    *,
    operation: str,
) -> str:
    if cp.returncode != 0:
        raise AIVPError(
            f"Docker {operation} failed:\n"
            f"{cp.stderr}"
        )

    return cp.stdout


def _parse_timestamp(
    value: str,
) -> datetime:
    text = value.strip()

    if not text:
        raise AIVPError(
            "Docker container Created timestamp "
            "is missing"
        )

    text = re.sub(
        r"(\.\d{6})\d+(?=Z$)",
        r"\1",
        text,
    )

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(
            text
        )
    except ValueError as exc:
        raise AIVPError(
            "Docker container Created timestamp "
            f"is invalid: {value}"
        ) from exc

    if parsed.tzinfo is None:
        raise AIVPError(
            "Docker container Created timestamp "
            "must include timezone information"
        )

    return parsed.astimezone(
        timezone.utc
    )


def _owned_labels(
    labels: Mapping[str, str],
) -> bool:
    return (
        labels.get(
            AIVP_DOCKER_OWNER_LABEL
        )
        == AIVP_DOCKER_OWNER_VALUE
        and labels.get(
            AIVP_DOCKER_RESOURCE_LABEL
        )
        == AIVP_DOCKER_RESOURCE_VALUE
    )


def list_owned_containers() -> list[DockerContainer]:
    ps = _run_docker(
        "ps",
        "-a",
        "--filter",
        (
            "label="
            f"{AIVP_DOCKER_OWNER_LABEL}="
            f"{AIVP_DOCKER_OWNER_VALUE}"
        ),
        "--format",
        "{{.ID}}",
    )

    stdout = _require_success(
        ps,
        operation="container listing",
    )

    container_ids = [
        line.strip()
        for line in stdout.splitlines()
        if line.strip()
    ]

    if not container_ids:
        return []

    inspect = _run_docker(
        "inspect",
        *container_ids,
    )

    raw = _require_success(
        inspect,
        operation="container inspection",
    )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AIVPError(
            "Docker inspect returned invalid JSON"
        ) from exc

    if not isinstance(payload, list):
        raise AIVPError(
            "Docker inspect result must be a list"
        )

    containers: list[DockerContainer] = []

    for item in payload:
        if not isinstance(item, dict):
            raise AIVPError(
                "Docker inspect item must be an object"
            )

        container_id = item.get("Id")
        created = item.get("Created")
        config = item.get("Config")
        state = item.get("State")

        if (
            not isinstance(container_id, str)
            or not container_id.strip()
        ):
            raise AIVPError(
                "Docker inspect item is missing Id"
            )

        if not isinstance(created, str):
            raise AIVPError(
                "Docker inspect item is missing Created"
            )

        if not isinstance(config, dict):
            raise AIVPError(
                "Docker inspect item is missing Config"
            )

        if not isinstance(state, dict):
            raise AIVPError(
                "Docker inspect item is missing State"
            )

        raw_labels = config.get(
            "Labels"
        ) or {}

        if not isinstance(
            raw_labels,
            dict,
        ):
            raise AIVPError(
                "Docker container Labels "
                "must be an object"
            )

        labels = {
            str(key): str(value)
            for key, value
            in raw_labels.items()
        }

        if not _owned_labels(labels):
            continue

        running = state.get(
            "Running"
        )

        if not isinstance(
            running,
            bool,
        ):
            raise AIVPError(
                "Docker container State.Running "
                "must be boolean"
            )

        containers.append(
            DockerContainer(
                container_id=(
                    container_id
                ),
                created_at=(
                    _parse_timestamp(
                        created
                    )
                ),
                running=running,
                labels=labels,
            )
        )

    return containers


def cleanup_stale_containers(
    *,
    older_than_seconds: float,
    dry_run: bool = True,
    now: Optional[datetime] = None,
) -> list[DockerCleanupResult]:
    if older_than_seconds < 0:
        raise ValueError(
            "older_than_seconds must not be negative"
        )

    current = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )

    if current.tzinfo is None:
        raise ValueError(
            "now must be timezone-aware"
        )

    current = current.astimezone(
        timezone.utc
    )

    results: list[
        DockerCleanupResult
    ] = []

    for container in list_owned_containers():
        age = (
            current
            - container.created_at
        ).total_seconds()

        if age < 0:
            results.append(
                DockerCleanupResult(
                    container_id=(
                        container.container_id
                    ),
                    removed=False,
                    dry_run=dry_run,
                    age_seconds=age,
                    reason=(
                        "container creation time is "
                        "in the future; preserve"
                    ),
                )
            )
            continue

        if age < older_than_seconds:
            results.append(
                DockerCleanupResult(
                    container_id=(
                        container.container_id
                    ),
                    removed=False,
                    dry_run=dry_run,
                    age_seconds=age,
                    reason=(
                        "AIVP container is still "
                        "within retention"
                    ),
                )
            )
            continue

        if dry_run:
            results.append(
                DockerCleanupResult(
                    container_id=(
                        container.container_id
                    ),
                    removed=False,
                    dry_run=True,
                    age_seconds=age,
                    reason=(
                        "stale AIVP container would "
                        "be removed"
                    ),
                )
            )
            continue

        rm = _run_docker(
            "rm",
            "-f",
            container.container_id,
        )

        _require_success(
            rm,
            operation=(
                "stale container removal"
            ),
        )

        results.append(
            DockerCleanupResult(
                container_id=(
                    container.container_id
                ),
                removed=True,
                dry_run=False,
                age_seconds=age,
                reason=(
                    "stale AIVP container removed"
                ),
            )
        )

    return results
