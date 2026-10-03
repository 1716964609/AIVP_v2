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
    tracing_from,
    verification_sandbox_from,
)
from aivp.panel.orchestrator import (
    execute_panel,
)
from aivp.policy.capability import (
    v2_default_policy,
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
from aivp.artifacts.io import dump_json
from aivp.telemetry.pricing import (
    PricingCatalog,
)
from aivp.verification.deterministic import (
    DeterministicVerifier,
)


def _pricing_catalog_from_config(
    *,
    config: Dict[str, Any],
    repo: Path,
    snapshot_path: Path,
) -> Optional[PricingCatalog]:
    raw = config.get("pricing")

    if raw is None:
        return None

    if not isinstance(raw, dict):
        raise AIVPError(
            "pricing must be an object"
        )

    raw_file = raw.get("file")

    if raw_file is None:
        return None

    if (
        not isinstance(raw_file, str)
        or not raw_file.strip()
    ):
        raise AIVPError(
            "pricing.file must be "
            "a non-empty string"
        )

    pricing_path = Path(
        raw_file
    ).expanduser()

    if not pricing_path.is_absolute():
        pricing_path = (
            repo / pricing_path
        )

    pricing_path = pricing_path.resolve()

    catalog = PricingCatalog.load(
        pricing_path
    )

    dump_json(
        snapshot_path,
        catalog.as_dict(),
    )

    return catalog


def _cache_root_from_state_db(
    state_db: Path,
) -> Path:
    state_db = (
        state_db
        .expanduser()
        .resolve()
    )

    return (
        state_db.parent
        / "cache"
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
    cache_root: Optional[
        Path
    ] = None,
) -> Path:
    run_id = (
        durable.run_id
        if durable is not None
        else runtime.run_dir.name
    )

    with runtime.tracing.span(
        "run",
        attributes={
            "run.id": run_id,
            "dry_run": runtime.dry_run,
        },
    ) as run_span:
        policy = v2_default_policy()

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
            policy=policy,
        )

        risk_engine = (
            LegacyCompatibleRiskEngine()
        )

        result = execute_panel(
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
            cache_root=cache_root,
            policy=policy,
        )

        if run_span is not None:
            for event in reversed(
                runtime.events
            ):
                if (
                    event.get("kind")
                    == "run_end"
                ):
                    status = event.get(
                        "status"
                    )

                    if isinstance(
                        status,
                        str,
                    ):
                        run_span.set_attribute(
                            "status",
                            status,
                        )

                    break

        return result

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

    state_db = (
        state_db
        .expanduser()
        .resolve()
    )

    cache_root = (
        None
        if dry_run
        else _cache_root_from_state_db(
            state_db
        )
    )

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
        tracing=tracing_from(
            config,
            run_dir,
        ),
    )

    if dry_run:
        return _execute(
            runtime=runtime,
            repo=repo,
            canonical_repo=repo,
            task=task,
            config=config,
            durable=None,
            cache_root=cache_root,
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
        pricing_catalog = (
            _pricing_catalog_from_config(
                config=config,
                repo=repo,
                snapshot_path=(
                    run_dir
                    / "pricing-catalog.json"
                ),
            )
        )

        durable = DurableExecution(
            store=store,
            run_id=selected_run_id,
            canonical_repo_path=(
                worktree.canonical_repo
            ),
            pricing_catalog=(
                pricing_catalog
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
            cache_root=cache_root,
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
            tracing=tracing_from(
                config,
                run_dir,
            ),
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

        pricing_snapshot = (
            run_dir
            / "pricing-catalog.json"
        )

        pricing_catalog = (
            PricingCatalog.load(
                pricing_snapshot
            )
            if pricing_snapshot.exists()
            else None
        )

        durable = DurableExecution(
            store=store,
            run_id=run_id,
            canonical_repo_path=(
                canonical_repo
            ),
            pricing_catalog=(
                pricing_catalog
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
