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
            time.monotonic()
            - runtime.started,
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
