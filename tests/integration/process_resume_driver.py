from __future__ import annotations

import json
import sys

from pathlib import Path

from aivp.artifacts.registry import (
    ArtifactRegistry,
)
from aivp.execution.runtime import (
    Budgets,
    Runtime,
    now_iso,
)
from aivp.models.base import (
    ModelAdapter,
    ModelRequest,
    ModelResult,
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
from aivp.verification.base import Verifier


class FakeModel(ModelAdapter):
    def __init__(
        self,
        runtime: Runtime,
        role: str,
    ):
        self.runtime = runtime
        self.role = role

    def invoke(
        self,
        request: ModelRequest,
    ) -> ModelResult:
        if request.role in {
            "generator",
            "verification-fixer",
            "review-fixer",
        }:
            self.runtime.consume("codex")

            generated = (
                request.repo
                / "generated.txt"
            )

            if not generated.exists():
                generated.write_text(
                    "generated\n",
                    encoding="utf-8",
                )

            message = "generated"

        elif request.role == "reviewer":
            self.runtime.consume("claude")
            message = json.dumps(
                {
                    "summary": "ok",
                    "findings": [],
                    "risk": "low",
                    "risk_confidence": 1.0,
                    "risk_reasons": ["test"],
                }
            )

        elif request.role == "risk":
            self.runtime.consume("codex")
            message = json.dumps(
                {
                    "risk": "low",
                    "confidence": 1.0,
                    "reasons": ["test"],
                }
            )

        else:
            raise RuntimeError(
                f"unexpected role: "
                f"{request.role}"
            )

        timestamp = now_iso()

        return ModelResult(
            provider="fake",
            model=f"fake-{self.role}",
            started_at=timestamp,
            finished_at=timestamp,
            last_message=message,
            raw_metadata={},
            raw_exit_status=0,
        )


class FakeVerifier(Verifier):
    def verify(
        self,
        *,
        repo: Path,
        config,
        phase: str,
    ):
        return {
            "passed": True,
            "phase": phase,
            "commands": [],
        }


def config():
    return {
        "budgets": {
            "max_fix_iterations": 2,
            "codex_max_calls": 4,
            "claude_max_calls": 3,
            "codex_timeout_seconds": 300,
            "claude_timeout_seconds": 300,
            "whole_run_timeout_seconds": 900,
        }
    }


def task():
    return {
        "title": "process durability test",
        "description": "generate a test file",
    }


def main() -> int:
    mode = sys.argv[1]

    root = Path(
        sys.argv[2]
    ).resolve()

    repo = root / "repo"
    run_dir = root / "run"
    db_path = root / "state.db"

    run_id = "process-resume-test"

    store = SQLiteStateStore(
        db_path
    )

    try:
        if mode == "start":
            runtime = Runtime(
                run_dir,
                Budgets(),
            )

            durable = DurableExecution(
                store=store,
                run_id=run_id,
            )

        elif mode == "resume":
            checkpoint = (
                store
                .load_resume_checkpoint(
                    run_id
                )
            )

            if checkpoint is None:
                raise RuntimeError(
                    "checkpoint missing"
                )

            runtime = Runtime(
                run_dir,
                Budgets(),
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
                attempt=(
                    int(
                        checkpoint[
                            "attempt"
                        ]
                    )
                    + 1
                ),
                resume_checkpoint=checkpoint,
            )

        else:
            raise RuntimeError(
                f"unknown mode: {mode}"
            )

        execute_panel(
            runtime=runtime,
            repo=repo,
            task=task(),
            config=config(),
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

        return 0

    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
