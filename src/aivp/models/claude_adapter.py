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

    if outer.get("type") == "result":
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
            "usage": outer.get(
                "usage"
            ),
            "model_usage": outer.get(
                "modelUsage"
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

        return (
            inner
            if isinstance(inner, str)
            else raw
        ), meta, cost

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
            check=False,
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

        usage = metadata.get(
            "usage"
        )

        if not isinstance(usage, dict):
            usage = {}

        input_tokens = usage.get(
            "input_tokens"
        )

        cached_tokens = usage.get(
            "cache_read_input_tokens"
        )

        output_tokens = usage.get(
            "output_tokens"
        )

        return ModelResult(
            provider="anthropic",
            model=model,
            started_at=started_at,
            finished_at=_now_iso(),
            raw_exit_status=cp.returncode,
            input_tokens=(
                input_tokens
                if isinstance(input_tokens, int)
                else None
            ),
            output_tokens=(
                output_tokens
                if isinstance(output_tokens, int)
                else None
            ),
            cached_tokens=(
                cached_tokens
                if isinstance(cached_tokens, int)
                else None
            ),
            cost_estimate_usd=cost,
            artifact_paths=artifact_paths,
            last_message=last_message,
            raw_metadata=metadata,
        )
