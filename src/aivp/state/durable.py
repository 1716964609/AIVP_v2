from __future__ import annotations

import dataclasses

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Any

from aivp.artifacts.io import dump_text
from aivp.errors import InjectedCrash
from aivp.execution.runtime import (
    Counters,
    Runtime,
)
from aivp.models.base import ModelResult
from aivp.repository.git import (
    capture_diff,
    git,
)
from aivp.state.base import DurableStateStore
from aivp.state.hashing import (
    sha256_file,
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
