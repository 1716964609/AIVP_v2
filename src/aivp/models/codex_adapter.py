from __future__ import annotations

import datetime as dt
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

        return ModelResult(
            provider="openai",
            model=model,
            started_at=started_at,
            finished_at=_now_iso(),
            raw_exit_status=cp.returncode,
            artifact_paths=tuple(artifacts),
            last_message=last_message,
            raw_metadata={
                "role": request.role,
            },
        )
