from __future__ import annotations

import datetime as dt
import json
from typing import Any, Dict

from aivp.artifacts.io import dump_json
from aivp.models.base import ModelRequest, ModelResult
from aivp.models.codex import codex_base_argv


def _now_iso() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .astimezone()
        .isoformat(timespec="seconds")
    )


def _decode_codex_jsonl(
    raw: str,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}

    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except (
            json.JSONDecodeError,
            TypeError,
        ):
            continue

        if not isinstance(event, dict):
            continue

        if (
            event.get("type")
            == "thread.started"
        ):
            thread_id = event.get(
                "thread_id"
            )

            if isinstance(thread_id, str):
                metadata[
                    "thread_id"
                ] = thread_id

        if (
            event.get("type")
            == "turn.completed"
        ):
            usage = event.get(
                "usage"
            )

            if isinstance(usage, dict):
                metadata["usage"] = usage

    return metadata


class CodexAdapter:
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

        is_risk = (
            request.role == "risk"
            or request.output_schema is not None
        )

        argv = codex_base_argv(
            self.config,
            risk=is_risk,
            repo=request.repo,
        )

        argv.append("--json")

        artifacts = []

        if request.output_schema is not None:
            if request.role == "risk":
                schema_path = (
                    self.runtime.run_dir
                    / "risk.schema.json"
                )
            else:
                schema_path = (
                    self.runtime.run_dir
                    / f"{request.log_stem}.schema.json"
                )

            dump_json(
                schema_path,
                request.output_schema,
            )

            artifacts.append(schema_path)

            argv.extend(
                [
                    "--output-schema",
                    str(schema_path),
                ]
            )

        if request.output_schema is not None:
            output_file = (
                self.runtime.run_dir
                / f"{request.log_stem}.raw.json"
            )
        else:
            output_file = (
                self.runtime.run_dir
                / f"{request.log_stem}.last-message.txt"
            )

        argv.extend(
            [
                "-o",
                str(output_file),
                request.prompt,
            ]
        )

        cp = self.runtime.command(
            argv,
            cwd=request.repo,
            timeout_seconds=request.timeout_seconds,
            log_stem=request.log_stem,
            actor="codex",
            check=True,
        )

        if output_file.exists():
            last_message = output_file.read_text(
                encoding="utf-8"
            )
            artifacts.append(output_file)
        else:
            last_message = cp.stdout

        model = str(
            self.config
            .get("codex", {})
            .get("model", "")
        ).strip() or "unknown"

        metadata = _decode_codex_jsonl(
            cp.stdout
        )

        metadata["role"] = request.role

        usage = metadata.get(
            "usage"
        )

        if not isinstance(usage, dict):
            usage = {}

        input_tokens = usage.get(
            "input_tokens"
        )

        cached_tokens = usage.get(
            "cached_input_tokens"
        )

        output_tokens = usage.get(
            "output_tokens"
        )

        return ModelResult(
            provider="openai",
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
            artifact_paths=tuple(artifacts),
            last_message=last_message,
            raw_metadata=metadata,
        )
