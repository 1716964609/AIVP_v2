from __future__ import annotations

import datetime as dt
import json
from typing import Any, Dict, Tuple

from aivp.models.base import ModelRequest, ModelResult
from aivp.models.claude import claude_argv


def _now_iso() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .astimezone()
        .isoformat(timespec="seconds")
    )


def _decode_claude_output(
    raw: str,
) -> Tuple[str, Dict[str, Any], Any]:
    try:
        outer = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw, {}, None

    if not isinstance(outer, dict):
        return raw, {}, None

    inner = outer.get("result")

    if (
        outer.get("type") == "result"
        and isinstance(inner, str)
    ):
        meta = {
            "duration_ms": outer.get(
                "duration_ms"
            ),
            "duration_api_ms": outer.get(
                "duration_api_ms"
            ),
            "num_turns": outer.get(
                "num_turns"
            ),
            "total_cost_usd": outer.get(
                "total_cost_usd"
            ),
            "session_id": outer.get(
                "session_id"
            ),
        }

        cost = outer.get(
            "total_cost_usd"
        )

        if not isinstance(
            cost,
            (int, float),
        ):
            cost = None

        return inner, meta, cost

    return raw, {}, None


class ClaudeAdapter:
    def __init__(
        self,
        runtime: Any,
        config: Dict[str, Any],
    ):
        self.runtime = runtime
        self.config = config

    def invoke(
        self,
        request: ModelRequest,
    ) -> ModelResult:
        started_at = _now_iso()

        argv = claude_argv(
            self.config
        )

        argv.append(
            request.prompt
        )

        cp = self.runtime.command(
            argv,
            cwd=request.repo,
            timeout_seconds=request.timeout_seconds,
            log_stem=request.log_stem,
            actor="claude",
            check=True,
        )

        (
            last_message,
            metadata,
            cost,
        ) = _decode_claude_output(
            cp.stdout
        )

        model = str(
            self.config
            .get("claude", {})
            .get("model", "")
        ).strip() or "unknown"

        artifact_paths = tuple(
            path
            for path in (
                self.runtime.run_dir
                / f"{request.log_stem}.stdout.txt",
                self.runtime.run_dir
                / f"{request.log_stem}.stderr.txt",
            )
            if path.exists()
        )

        return ModelResult(
            provider="anthropic",
            model=model,
            started_at=started_at,
            finished_at=_now_iso(),
            raw_exit_status=cp.returncode,
            cost_estimate_usd=cost,
            artifact_paths=artifact_paths,
            last_message=last_message,
            raw_metadata=metadata,
        )
