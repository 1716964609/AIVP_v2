from __future__ import annotations

import datetime as dt
import uuid

from pathlib import Path
from typing import Any, Dict, Optional

from aivp.artifacts.registry import (
    ArtifactRegistry,
)
from aivp.containment.worktree import (
    create_run_worktree,
    validate_run_worktree,
)
from aivp.errors import AIVPError
from aivp.execution.runtime import Runtime
from aivp.models.claude_adapter import (
    ClaudeAdapter,
)
from aivp.models.codex_adapter import (
    CodexAdapter,
)
from aivp.panel.config import (
    budgets_from,
    verification_sandbox_from,
)
from aivp.panel.orchestrator import (
    execute_panel,
)
from aivp.risk.engine import (
    LegacyCompatibleRiskEngine,
)
from aivp.state.durable import (
    DurableExecution,
    counters_from_checkpoint,
    elapsed_from_checkpoint,
)
from aivp.state.sqlite import (
    SQLiteStateStore,
)
from aivp.structured import load_structured
from aivp.verification.deterministic import (
    DeterministicVerifier,
)


def new_run_id() -> str:
    timestamp = (
        dt.datetime.now()
        .strftime("%Y%m%d-%H%M%S")
    )

    suffix = uuid.uuid4().hex[:8]

    return (
        f"run-{timestamp}-{suffix}"
    )


def _execute(
    *,
    runtime: Runtime,
    repo: Path,
    canonical_repo: Path,
    task: Dict[str, Any],
    config: Dict[str, Any],
    durable: Optional[
        DurableExecution
    ],
) -> Path:
    generator = CodexAdapter(
        runtime,
        config,
    )

    reviewer = ClaudeAdapter(
        runtime,
        config,
    )

    risk_judge = CodexAdapter(
        runtime,
        config,
    )

    verifier = DeterministicVerifier(
        runtime,
        sandbox=(
            verification_sandbox_from(
                config
            )
        ),
    )

    risk_engine = (
        LegacyCompatibleRiskEngine()
    )

    return execute_panel(
        runtime=runtime,
        repo=repo,
        canonical_repo=canonical_repo,
        task=task,
        config=config,
        generator=generator,
        reviewer=reviewer,
        risk_judge=risk_judge,
        verifier=verifier,
        risk_engine=risk_engine,
        artifacts=ArtifactRegistry(),
        durable=durable,
    )


def run_new(
    *,
    repo: Path,
    task: Dict[str, Any],
    config: Dict[str, Any],
    reports_root: Path,
    state_db: Path,
    run_id: Optional[str] = None,
    dry_run: bool = False,
) -> Path:
    repo = repo.expanduser().resolve()

    if not repo.exists():
        raise AIVPError(
            f"Repository not found: {repo}"
        )

    selected_run_id = (
        run_id or new_run_id()
    )

    reports_root = (
        reports_root
        .expanduser()
        .resolve()
    )

    reports_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_dir = (
        reports_root
        / selected_run_id
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    runtime = Runtime(
        run_dir,
        budgets_from(config),
        dry_run=dry_run,
    )

    if dry_run:
        return _execute(
            runtime=runtime,
            repo=repo,
            canonical_repo=repo,
            task=task,
            config=config,
            durable=None,
        )

    worktree = create_run_worktree(
        canonical_repo=repo,
        worktree_path=(
            run_dir / "worktree"
        ),
    )

    state_db = (
        state_db
        .expanduser()
        .resolve()
    )

    with SQLiteStateStore(
        state_db
    ) as store:
        durable = DurableExecution(
            store=store,
            run_id=selected_run_id,
            canonical_repo_path=(
                worktree.canonical_repo
            ),
        )

        return _execute(
            runtime=runtime,
            repo=worktree.path,
            canonical_repo=(
                worktree.canonical_repo
            ),
            task=task,
            config=config,
            durable=durable,
        )


def resume_run(
    *,
    run_id: str,
    state_db: Path,
) -> Path:
    state_db = (
        state_db
        .expanduser()
        .resolve()
    )

    if not state_db.exists():
        raise AIVPError(
            "State database not found: "
            f"{state_db}"
        )

    with SQLiteStateStore(
        state_db
    ) as store:
        checkpoint = (
            store.load_resume_checkpoint(
                run_id
            )
        )

        if checkpoint is None:
            raise AIVPError(
                f"Run not found: {run_id}"
            )

        repo = Path(
            str(
                checkpoint["repo_path"]
            )
        ).expanduser().resolve()

        canonical_repo = Path(
            str(
                checkpoint.get(
                    "canonical_repo_path",
                    checkpoint["repo_path"],
                )
            )
        ).expanduser().resolve()

        if canonical_repo != repo:
            validate_run_worktree(
                canonical_repo=canonical_repo,
                worktree_path=repo,
                base_sha=str(
                    checkpoint["base_sha"]
                ),
            )

        run_dir = Path(
            str(
                checkpoint["run_dir"]
            )
        ).expanduser().resolve()

        if not run_dir.exists():
            raise AIVPError(
                "Run directory not found: "
                f"{run_dir}"
            )

        task = load_structured(
            run_dir / "task.json"
        )

        config = load_structured(
            run_dir
            / "effective-config.json"
        )

        runtime = Runtime(
            run_dir,
            budgets_from(config),
            resume=True,
            counters=(
                counters_from_checkpoint(
                    checkpoint
                )
            ),
            elapsed_before_resume=(
                elapsed_from_checkpoint(
                    checkpoint
                )
            ),
        )

        durable = DurableExecution(
            store=store,
            run_id=run_id,
            canonical_repo_path=(
                canonical_repo
            ),
            attempt=(
                int(
                    checkpoint["attempt"]
                )
                + 1
            ),
            resume_checkpoint=checkpoint,
        )

        return _execute(
            runtime=runtime,
            repo=repo,
            canonical_repo=canonical_repo,
            task=task,
            config=config,
            durable=durable,
        )
