import time

from typing import Any, Dict, Optional, Sequence

from aivp.artifacts.io import dump_json
from aivp.execution.runtime import (
    Runtime,
    now_iso,
)


LEGACY_METRIC_VERSION = "1.0.0"


def write_metrics(
    runtime: Runtime,
    status: str,
    extra: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:
    metrics = {
        "version": LEGACY_METRIC_VERSION,
        "status": status,
        "started_at": (
            runtime.events[0]["ts"]
            if runtime.events
            else None
        ),
        "finished_at": now_iso(),
        "elapsed_seconds": round(
            runtime.elapsed_seconds(),
            3,
        ),
        "codex_calls": (
            runtime.counters.codex_calls
        ),
        "claude_calls": (
            runtime.counters.claude_calls
        ),
        "fix_iterations": (
            runtime.counters.fix_iterations
        ),
    }

    if extra:
        metrics.update(extra)

    dump_json(
        runtime.run_dir
        / "metrics.json",
        metrics,
    )

    return metrics


def human_packet(
    *,
    task: Dict[str, Any],
    verification: Optional[
        Dict[str, Any]
    ],
    claude_review: Optional[
        Dict[str, Any]
    ],
    rule_risk: Optional[
        Dict[str, Any]
    ],
    codex_risk: Optional[
        Dict[str, Any]
    ],
    aggregate: Optional[
        Dict[str, Any]
    ],
    paths: Sequence[str],
    reason: str,
    metrics: Dict[str, Any],
) -> str:
    findings = (
        claude_review or {}
    ).get(
        "findings",
        [],
    )

    blocking = [
        finding
        for finding in findings
        if finding.get(
            "severity"
        ) in {
            "critical",
            "major",
        }
    ]

    verification_result = (
        verification or {}
    )

    lines = [
        "# Human Review Required",
        "",
        f"**Escalation reason:** {reason}",
        "",
        "## Task",
        "",
        str(
            task.get(
                "task",
                "",
            )
        ),
        "",
        "## Deterministic verification",
        "",
        (
            "Overall: "
            + (
                "PASS"
                if verification_result.get(
                    "passed"
                )
                else "FAIL / UNKNOWN"
            )
        ),
    ]

    for result in (
        verification_result.get(
            "results",
            [],
        )
    ):
        lines.append(
            "- "
            + (
                "PASS"
                if result.get("passed")
                else "FAIL"
            )
            + " — "
            + str(
                result.get("name")
            )
        )

    lines += [
        "",
        "## Blocking AI findings",
        "",
    ]

    if blocking:
        for finding in blocking:
            lines.append(
                "- **"
                + str(
                    finding.get(
                        "severity",
                        "",
                    )
                ).upper()
                + "** "
                + str(
                    finding.get(
                        "file",
                        "",
                    )
                )
                + (
                    ":"
                    + str(
                        finding.get("line")
                    )
                    if finding.get("line")
                    else ""
                )
                + " — "
                + str(
                    finding.get(
                        "reason",
                        "",
                    )
                )
            )

    else:
        lines.append(
            "- None"
        )

    lines += [
        "",
        "## Risk",
        "",
        (
            "- Rule engine: "
            + str(
                (
                    rule_risk or {}
                ).get(
                    "risk",
                    "unknown",
                )
            )
        ),
        (
            "- Codex: "
            + str(
                (
                    codex_risk or {}
                ).get(
                    "risk",
                    "unknown",
                )
            )
        ),
        (
            "- Claude: "
            + str(
                (
                    claude_review or {}
                ).get(
                    "risk",
                    "unknown",
                )
            )
        ),
        (
            "- Aggregate: "
            + str(
                (
                    aggregate or {}
                ).get(
                    "final",
                    "unknown",
                )
            )
        ),
        "",
        "## Files to inspect",
        "",
    ]

    lines += (
        [
            f"- {path}"
            for path in paths
        ]
        or [
            "- No changed paths detected"
        ]
    )

    lines += [
        "",
        "## Resource usage",
        "",
        (
            "- Codex calls: "
            f"{metrics.get('codex_calls')}"
        ),
        (
            "- Claude calls: "
            f"{metrics.get('claude_calls')}"
        ),
        (
            "- Fix iterations: "
            f"{metrics.get('fix_iterations')}"
        ),
        (
            "- Elapsed seconds: "
            f"{metrics.get('elapsed_seconds')}"
        ),
        "",
        "## Human decision",
        "",
        "- [ ] Accept change",
        "- [ ] Request another manual change",
        "- [ ] Reject / revert",
        "",
    ]

    return "\n".join(lines)


RUN_SUMMARY_VERSION = "1.0.0"


def write_run_summary(
    *,
    runtime: Runtime,
    status: str,
    run_id: str,
    model_calls: Sequence[
        Dict[str, Any]
    ],
    pricing_version: Optional[str] = None,
) -> Dict[str, Any]:
    calls = [
        dict(row)
        for row in model_calls
    ]

    provider_totals: Dict[
        str,
        Dict[str, Any],
    ] = {}

    steps = []

    total_latency_ms = 0
    total_input_tokens = 0
    total_cached_tokens = 0
    total_output_tokens = 0
    total_cost_usd = 0.0

    input_known_calls = 0
    cached_known_calls = 0
    output_known_calls = 0
    cost_known_calls = 0
    latency_known_calls = 0

    for row in calls:
        provider = str(
            row.get("provider")
            or "unknown"
        )

        bucket = provider_totals.setdefault(
            provider,
            {
                "calls": 0,
                "latency_ms": 0,
                "input_tokens": 0,
                "cached_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "cost_known_calls": 0,
            },
        )

        bucket["calls"] += 1

        latency = row.get(
            "latency_ms"
        )

        if isinstance(
            latency,
            (int, float),
        ):
            latency = int(latency)
            total_latency_ms += latency
            latency_known_calls += 1
            bucket["latency_ms"] += (
                latency
            )

        input_tokens = row.get(
            "input_tokens"
        )

        if isinstance(
            input_tokens,
            int,
        ):
            total_input_tokens += (
                input_tokens
            )
            input_known_calls += 1
            bucket["input_tokens"] += (
                input_tokens
            )

        cached_tokens = row.get(
            "cached_tokens"
        )

        if isinstance(
            cached_tokens,
            int,
        ):
            total_cached_tokens += (
                cached_tokens
            )
            cached_known_calls += 1
            bucket["cached_tokens"] += (
                cached_tokens
            )

        output_tokens = row.get(
            "output_tokens"
        )

        if isinstance(
            output_tokens,
            int,
        ):
            total_output_tokens += (
                output_tokens
            )
            output_known_calls += 1
            bucket["output_tokens"] += (
                output_tokens
            )

        cost = row.get(
            "cost_usd"
        )

        if isinstance(
            cost,
            (int, float),
        ):
            cost = float(cost)
            total_cost_usd += cost
            cost_known_calls += 1
            bucket["cost_usd"] += cost
            bucket[
                "cost_known_calls"
            ] += 1

        steps.append(
            {
                "step_id": row.get(
                    "step_id"
                ),
                "provider": row.get(
                    "provider"
                ),
                "model": row.get(
                    "model"
                ),
                "latency_ms": latency,
                "input_tokens": (
                    input_tokens
                    if isinstance(
                        input_tokens,
                        int,
                    )
                    else None
                ),
                "cached_tokens": (
                    cached_tokens
                    if isinstance(
                        cached_tokens,
                        int,
                    )
                    else None
                ),
                "output_tokens": (
                    output_tokens
                    if isinstance(
                        output_tokens,
                        int,
                    )
                    else None
                ),
                "cost_usd": (
                    cost
                    if isinstance(
                        cost,
                        float,
                    )
                    else None
                ),
                "status": row.get(
                    "status"
                ),
            }
        )

    for bucket in (
        provider_totals.values()
    ):
        bucket["cost_usd"] = round(
            bucket["cost_usd"],
            12,
        )

    command_count = 0
    command_elapsed = 0.0
    tool_totals: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for event in runtime.events:
        if event.get("kind") not in {
            "command_end",
            "command_timeout",
        }:
            continue

        command_count += 1

        tool = str(
            event.get("tool")
            or "command"
        )

        bucket = tool_totals.setdefault(
            tool,
            {
                "commands": 0,
                "elapsed_seconds": 0.0,
            },
        )

        bucket["commands"] += 1

        elapsed = event.get(
            "elapsed_seconds"
        )

        if isinstance(
            elapsed,
            (int, float),
        ):
            elapsed = float(elapsed)
            command_elapsed += elapsed
            bucket[
                "elapsed_seconds"
            ] += elapsed

    for bucket in tool_totals.values():
        bucket["elapsed_seconds"] = round(
            bucket["elapsed_seconds"],
            3,
        )

    summary = {
        "version": RUN_SUMMARY_VERSION,
        "run_id": run_id,
        "status": status,
        "generated_at": now_iso(),
        "pricing_version": (
            pricing_version
        ),
        "time": {
            "run_elapsed_seconds": round(
                runtime.elapsed_seconds(),
                3,
            ),
            "model_latency_ms": (
                total_latency_ms
            ),
            "model_latency_known_calls": (
                latency_known_calls
            ),
            "command_elapsed_seconds": round(
                command_elapsed,
                3,
            ),
            "command_count": command_count,
            "nested_durations_not_additive": (
                True
            ),
        },
        "tokens": {
            "input_tokens": (
                total_input_tokens
            ),
            "cached_tokens": (
                total_cached_tokens
            ),
            "output_tokens": (
                total_output_tokens
            ),
            "input_known_calls": (
                input_known_calls
            ),
            "cached_known_calls": (
                cached_known_calls
            ),
            "output_known_calls": (
                output_known_calls
            ),
        },
        "cost": {
            "total_usd": round(
                total_cost_usd,
                12,
            ),
            "known_calls": (
                cost_known_calls
            ),
            "total_calls": len(calls),
        },
        "model_calls": {
            "count": len(calls),
            "by_provider": (
                provider_totals
            ),
            "by_step": steps,
        },
        "commands": {
            "count": command_count,
            "by_tool": tool_totals,
        },
    }

    dump_json(
        runtime.run_dir
        / "run-summary.json",
        summary,
    )

    return summary
