from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from aivp.errors import StateIntegrityError
from aivp.state.integrity import validate_artifact


@dataclass(frozen=True)
class ResumePlan:
    run_id: str
    current_state: str
    next_state: str
    resume_attempt: int


NEXT_STATE = {
    "GENERATED": "VERIFYING",
    "VERIFIED": "REVIEWING",
    "REVIEWED": "RISK_ASSESSING",
    "RISK_ASSESSED": "AUTO_FINISHED",
}


def build_resume_plan(
    *,
    run_id: str,
    checkpoint: Mapping[str, Any],
    artifact_records: list[Mapping[str, Any]],
) -> ResumePlan:
    state = str(
        checkpoint.get("state", "")
    )

    if state not in NEXT_STATE:
        raise StateIntegrityError(
            f"Checkpoint state is not resumable: {state}"
        )

    for artifact in artifact_records:
        validate_artifact(
            path=Path(
                artifact["path"]
            ),
            expected_sha256=str(
                artifact["sha256"]
            ),
            expected_size_bytes=int(
                artifact["size_bytes"]
            ),
        )

    attempt = int(
        checkpoint.get(
            "attempt",
            1,
        )
    )

    return ResumePlan(
        run_id=run_id,
        current_state=state,
        next_state=NEXT_STATE[state],
        resume_attempt=attempt + 1,
    )


def validate_resume_repository(
    *,
    repo: Path,
    checkpoint: Mapping[str, Any],
) -> None:
    from aivp.repository.git import (
        capture_diff,
        git,
    )
    from aivp.state.hashing import (
        sha256_text,
    )

    if not repo.exists():
        raise StateIntegrityError(
            f"Resume repository missing: {repo}"
        )

    required = (
        "repo_path",
        "base_sha",
        "current_diff_hash",
    )

    for key in required:
        if key not in checkpoint:
            raise StateIntegrityError(
                "Checkpoint missing required "
                f"field: {key}"
            )

    expected_repo = Path(
        str(checkpoint["repo_path"])
    ).resolve()

    if repo.resolve() != expected_repo:
        raise StateIntegrityError(
            "Resume repository path mismatch"
        )

    current_base = git(
        repo,
        "rev-parse",
        "HEAD",
    ).stdout.strip()

    if current_base != str(
        checkpoint["base_sha"]
    ):
        raise StateIntegrityError(
            "Resume base SHA mismatch"
        )

    current_diff_hash = sha256_text(
        capture_diff(repo)
    )

    if current_diff_hash != str(
        checkpoint["current_diff_hash"]
    ):
        raise StateIntegrityError(
            "Resume diff hash mismatch"
        )


def validate_resume_inputs(
    *,
    task: Mapping[str, Any],
    config: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
) -> None:
    from aivp.state.hashing import (
        sha256_json,
    )

    expected_task_hash = (
        checkpoint.get(
            "task_hash"
        )
    )

    expected_config_hash = (
        checkpoint.get(
            "config_hash"
        )
    )

    if not isinstance(
        expected_task_hash,
        str,
    ):
        raise StateIntegrityError(
            "Checkpoint task hash missing"
        )

    if not isinstance(
        expected_config_hash,
        str,
    ):
        raise StateIntegrityError(
            "Checkpoint config hash missing"
        )

    if (
        sha256_json(dict(task))
        != expected_task_hash
    ):
        raise StateIntegrityError(
            "Resume task identity mismatch"
        )

    if (
        sha256_json(dict(config))
        != expected_config_hash
    ):
        raise StateIntegrityError(
            "Resume config identity mismatch"
        )
