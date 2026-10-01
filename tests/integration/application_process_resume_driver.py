from __future__ import annotations

import sys

from pathlib import Path

import aivp.application as application

from aivp.artifacts.registry import (
    ArtifactRegistry,
)
from aivp.panel.orchestrator import (
    execute_panel,
)
from aivp.risk.engine import (
    LegacyCompatibleRiskEngine,
)

from process_resume_driver import (
    FakeModel,
    FakeVerifier,
    config,
    task,
)


RUN_ID = "application-process-resume-test"


def fake_execute(
    *,
    runtime,
    repo,
    canonical_repo,
    task,
    config,
    durable,
):
    return execute_panel(
        runtime=runtime,
        repo=repo,
        canonical_repo=canonical_repo,
        task=task,
        config=config,
        generator=FakeModel(
            runtime,
            "codex",
        ),
        reviewer=FakeModel(
            runtime,
            "claude",
        ),
        risk_judge=FakeModel(
            runtime,
            "codex",
        ),
        verifier=FakeVerifier(),
        risk_engine=(
            LegacyCompatibleRiskEngine()
        ),
        artifacts=ArtifactRegistry(),
        durable=durable,
    )


def main() -> int:
    mode = sys.argv[1]

    root = Path(
        sys.argv[2]
    ).resolve()

    repo = root / "repo"
    reports_root = root / "reports"
    state_db = root / "state.db"

    application._execute = fake_execute

    if mode == "start":
        application.run_new(
            repo=repo,
            task=task(),
            config=config(),
            reports_root=reports_root,
            state_db=state_db,
            run_id=RUN_ID,
        )

        return 0

    if mode == "resume":
        application.resume_run(
            run_id=RUN_ID,
            state_db=state_db,
        )

        return 0

    raise RuntimeError(
        f"unknown mode: {mode}"
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
