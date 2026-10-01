from __future__ import annotations

import dataclasses
import os

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Any

from aivp.artifacts.io import (
    dump_json,
    dump_text,
)
from aivp.errors import (
    InjectedCrash,
    StateIntegrityError,
)
from aivp.execution.runtime import (
    Counters,
    Runtime,
    now_iso,
)
from aivp.models.base import ModelResult
from aivp.repository.git import (
    capture_diff,
    git,
)
from aivp.state.base import DurableStateStore
from aivp.state.checkpoint import (
    CHECKPOINT_SCHEMA_VERSION,
)
from aivp.state.hashing import (
    sha256_file,
    sha256_json,
    sha256_text,
)


def _hard_crash_if_requested(
    state: str,
) -> None:
    enabled = os.environ.get(
        "AIVP_ENABLE_FAULT_INJECTION"
    )

    requested = os.environ.get(
        "AIVP_HARD_CRASH_AFTER_STATE"
    )

    if (
        enabled == "1"
        and requested == state
    ):
        # Intentional abrupt process death:
        # no exception unwinding,
        # no finally,
        # no context-manager cleanup.
        os._exit(97)


@dataclass
class DurableExecution:
    store: DurableStateStore
    run_id: str
    attempt: int = 1
    resume_checkpoint: Optional[
        Mapping[str, Any]
    ] = None
    canonical_repo_path: Optional[
        Path
    ] = None
    fault_after_state: Optional[str] = None

    @property
    def is_resume(self) -> bool:
        return (
            self.resume_checkpoint
            is not None
        )


def elapsed_from_checkpoint(
    checkpoint: Mapping[str, Any],
) -> float:
    if "elapsed_seconds" not in checkpoint:
        raise StateIntegrityError(
            "Resume checkpoint is missing "
            "elapsed_seconds"
        )

    try:
        elapsed = float(
            checkpoint["elapsed_seconds"]
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise StateIntegrityError(
            "Resume checkpoint contains "
            "invalid elapsed_seconds"
        ) from exc

    if elapsed < 0:
        raise StateIntegrityError(
            "Resume checkpoint contains "
            "negative elapsed_seconds"
        )

    return elapsed


def counters_from_checkpoint(
    checkpoint: Mapping[str, Any],
) -> Counters:
    raw = checkpoint.get(
        "counters",
        {},
    )

    return Counters(
        codex_calls=int(
            raw.get(
                "codex_calls",
                0,
            )
        ),
        claude_calls=int(
            raw.get(
                "claude_calls",
                0,
            )
        ),
        fix_iterations=int(
            raw.get(
                "fix_iterations",
                0,
            )
        ),
    )


def begin_generation(
    *,
    durable: DurableExecution,
    repo: Path,
) -> str:
    base_sha = git(
        repo,
        "rev-parse",
        "HEAD",
    ).stdout.strip()

    durable.store.begin_run(
        run_id=durable.run_id,
        repo_path=repo.resolve(),
        base_sha=base_sha,
        current_state="GENERATING",
    )

    return base_sha


def complete_generation(
    *,
    durable: DurableExecution,
    runtime: Runtime,
    repo: Path,
    prompt: str,
    task: Mapping[str, Any],
    config: Mapping[str, Any],
    model_result: ModelResult,
    base_sha: str,
) -> None:
    diff_text = capture_diff(
        repo
    )

    diff_path = (
        runtime.run_dir
        / "generated.diff.txt"
    )

    dump_text(
        diff_path,
        diff_text,
    )

    artifact_id = (
        f"{durable.run_id}:"
        f"generated-diff:"
        f"{durable.attempt}"
    )

    artifact_sha = sha256_file(
        diff_path
    )

    diff_hash = sha256_text(
        diff_text
    )

    checkpoint = {
        "checkpoint_schema_version": (
            CHECKPOINT_SCHEMA_VERSION
        ),
        "state": "GENERATED",
        "attempt": durable.attempt,
        "repo_path": str(
            repo.resolve()
        ),
        **(
            {
                "canonical_repo_path": str(
                    durable.canonical_repo_path
                    .expanduser()
                    .resolve()
                )
            }
            if durable.canonical_repo_path
            is not None
            else {}
        ),
        "run_dir": str(
            runtime.run_dir.resolve()
        ),
        "base_sha": base_sha,
        "current_diff_hash": diff_hash,
        "task_hash": sha256_json(
            dict(task)
        ),
        "config_hash": sha256_json(
            dict(config)
        ),
        "artifact_ids": [
            artifact_id
        ],
        "counters": dataclasses.asdict(
            runtime.counters
        ),
        "elapsed_seconds": (
            runtime.elapsed_seconds()
        ),
        "model": {
            "provider": (
                model_result.provider
            ),
            "model": (
                model_result.model
            ),
            "raw_exit_status": (
                model_result.raw_exit_status
            ),
        },
    }

    durable.store.complete_step(
        step_id=(
            f"{durable.run_id}:generate:1"
        ),
        run_id=durable.run_id,
        step_type="generate",
        attempt=durable.attempt,
        input_hash=sha256_text(
            prompt
        ),
        output_hash=diff_hash,
        started_at=(
            model_result.started_at
        ),
        finished_at=(
            model_result.finished_at
        ),
        retryable=False,
        checkpoint_state="GENERATED",
        checkpoint_payload=checkpoint,
        artifacts=[
            {
                "artifact_id": artifact_id,
                "artifact_type": (
                    "generated-diff"
                ),
                "path": diff_path,
                "sha256": artifact_sha,
                "size_bytes": (
                    diff_path.stat().st_size
                ),
            }
        ],
    )

    _hard_crash_if_requested(
        "GENERATED"
    )

    if (
        durable.fault_after_state
        == "GENERATED"
    ):
        raise InjectedCrash(
            "Injected crash after "
            "GENERATED checkpoint"
        )



def complete_verification(
    *,
    durable: DurableExecution,
    runtime: Runtime,
    repo: Path,
    task: Mapping[str, Any],
    config: Mapping[str, Any],
    verification: Mapping[str, Any],
) -> None:
    verification_path = (
        runtime.run_dir
        / (
            "durable-verification-"
            f"{durable.attempt}.json"
        )
    )

    dump_json(
        verification_path,
        dict(verification),
    )

    artifact_id = (
        f"{durable.run_id}:"
        f"verification:"
        f"{durable.attempt}"
    )

    artifact_sha = sha256_file(
        verification_path
    )

    diff_text = capture_diff(
        repo
    )

    diff_hash = sha256_text(
        diff_text
    )

    base_sha = git(
        repo,
        "rev-parse",
        "HEAD",
    ).stdout.strip()

    verification_hash = (
        sha256_json(
            dict(verification)
        )
    )

    timestamp = now_iso()

    checkpoint = {
        "checkpoint_schema_version": (
            CHECKPOINT_SCHEMA_VERSION
        ),
        "state": "VERIFIED",
        "attempt": durable.attempt,
        "repo_path": str(
            repo.resolve()
        ),
        **(
            {
                "canonical_repo_path": str(
                    durable.canonical_repo_path
                    .expanduser()
                    .resolve()
                )
            }
            if durable.canonical_repo_path
            is not None
            else {}
        ),
        "run_dir": str(
            runtime.run_dir.resolve()
        ),
        "base_sha": base_sha,
        "current_diff_hash": diff_hash,
        "task_hash": sha256_json(
            dict(task)
        ),
        "config_hash": sha256_json(
            dict(config)
        ),
        "verification_artifact_id": (
            artifact_id
        ),
        "verification_hash": (
            verification_hash
        ),
        "verification": dict(
            verification
        ),
        "counters": dataclasses.asdict(
            runtime.counters
        ),
        "elapsed_seconds": (
            runtime.elapsed_seconds()
        ),
    }

    durable.store.complete_step(
        step_id=(
            f"{durable.run_id}:"
            f"verify:"
            f"{durable.attempt}"
        ),
        run_id=durable.run_id,
        step_type="verify",
        attempt=durable.attempt,
        input_hash=diff_hash,
        output_hash=verification_hash,
        started_at=timestamp,
        finished_at=timestamp,
        retryable=False,
        checkpoint_state="VERIFIED",
        checkpoint_payload=checkpoint,
        artifacts=[
            {
                "artifact_id": artifact_id,
                "artifact_type": (
                    "deterministic-verification"
                ),
                "path": verification_path,
                "sha256": artifact_sha,
                "size_bytes": (
                    verification_path
                    .stat()
                    .st_size
                ),
            }
        ],
    )

    _hard_crash_if_requested(
        "VERIFIED"
    )

    if (
        durable.fault_after_state
        == "VERIFIED"
    ):
        raise InjectedCrash(
            "Injected crash after "
            "VERIFIED checkpoint"
        )


def complete_terminal_outcome(
    *,
    durable: DurableExecution,
    runtime: Runtime,
    repo: Path,
    task: Mapping[str, Any],
    config: Mapping[str, Any],
    state: str,
    reason: str,
) -> None:
    if state not in {
        "HUMAN_REQUIRED",
        "DENIED",
    }:
        raise StateIntegrityError(
            "Unsupported terminal outcome: "
            f"{state}"
        )

    timestamp = now_iso()

    diff_text = capture_diff(repo)
    diff_hash = sha256_text(diff_text)

    base_sha = git(
        repo,
        "rev-parse",
        "HEAD",
    ).stdout.strip()

    checkpoint = {
        "checkpoint_schema_version": (
            CHECKPOINT_SCHEMA_VERSION
        ),
        "state": state,
        "status": state,
        "reason": reason,
        "attempt": durable.attempt,
        "repo_path": str(
            repo.resolve()
        ),
        **(
            {
                "canonical_repo_path": str(
                    durable.canonical_repo_path
                    .expanduser()
                    .resolve()
                )
            }
            if durable.canonical_repo_path
            is not None
            else {}
        ),
        "run_dir": str(
            runtime.run_dir.resolve()
        ),
        "base_sha": base_sha,
        "current_diff_hash": diff_hash,
        "task_hash": sha256_json(
            dict(task)
        ),
        "config_hash": sha256_json(
            dict(config)
        ),
        "counters": dataclasses.asdict(
            runtime.counters
        ),
        "elapsed_seconds": (
            runtime.elapsed_seconds()
        ),
    }

    durable.store.complete_step(
        step_id=(
            f"{durable.run_id}:"
            f"policy-terminal:"
            f"{durable.attempt}"
        ),
        run_id=durable.run_id,
        step_type="policy-terminal",
        attempt=durable.attempt,
        input_hash=sha256_text(reason),
        output_hash=sha256_json(
            {
                "state": state,
                "reason": reason,
            }
        ),
        started_at=timestamp,
        finished_at=timestamp,
        retryable=False,
        checkpoint_state=state,
        checkpoint_payload=checkpoint,
        run_status=state,
        run_finished_at=timestamp,
    )
