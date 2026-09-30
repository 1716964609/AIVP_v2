from __future__ import annotations

import dataclasses

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Any

from aivp.artifacts.io import (
    dump_json,
    dump_text,
)
from aivp.errors import InjectedCrash
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
from aivp.state.hashing import (
    sha256_file,
    sha256_json,
    sha256_text,
)


@dataclass
class DurableExecution:
    store: DurableStateStore
    run_id: str
    attempt: int = 1
    resume_checkpoint: Optional[
        Mapping[str, Any]
    ] = None
    fault_after_state: Optional[str] = None

    @property
    def is_resume(self) -> bool:
        return (
            self.resume_checkpoint
            is not None
        )


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

    durable.store.record_artifact(
        artifact_id=artifact_id,
        run_id=durable.run_id,
        artifact_type="generated-diff",
        path=diff_path,
        sha256=artifact_sha,
        size_bytes=(
            diff_path.stat().st_size
        ),
    )

    diff_hash = sha256_text(
        diff_text
    )

    checkpoint = {
        "state": "GENERATED",
        "attempt": durable.attempt,
        "repo_path": str(
            repo.resolve()
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

    durable.store.record_artifact(
        artifact_id=artifact_id,
        run_id=durable.run_id,
        artifact_type=(
            "deterministic-verification"
        ),
        path=verification_path,
        sha256=artifact_sha,
        size_bytes=(
            verification_path.stat().st_size
        ),
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
        "state": "VERIFIED",
        "attempt": durable.attempt,
        "repo_path": str(
            repo.resolve()
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
    )

    if (
        durable.fault_after_state
        == "VERIFIED"
    ):
        raise InjectedCrash(
            "Injected crash after "
            "VERIFIED checkpoint"
        )
