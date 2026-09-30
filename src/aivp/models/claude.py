from typing import Any, Dict, List


def claude_argv(config: Dict[str, Any]) -> List[str]:
    c = config["claude"]

    argv = [str(c.get("binary", "claude"))]

    argv.extend(
        str(x)
        for x in c.get(
            "extra_args",
            ["-p", "--output-format", "json"],
        )
    )

    argv.extend([
        "--max-turns",
        str(int(c.get("max_turns", 2))),
    ])

    model = str(c.get("model", "")).strip()

    if model:
        argv.extend(["--model", model])

    return argv


def normalize_findings(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []

    out = []

    for item in value:
        if not isinstance(item, dict):
            continue

        sev = str(
            item.get("severity", "minor")
        ).lower()

        if sev not in {
            "critical",
            "major",
            "minor",
            "suggestion",
        }:
            sev = "minor"

        out.append(
            {
                "severity": sev,
                "category": str(
                    item.get("category", "other")
                ),
                "file": str(item.get("file", "")),
                "line": item.get("line"),
                "reason": str(item.get("reason", "")),
                "suggested_direction": str(
                    item.get(
                        "suggested_direction",
                        "",
                    )
                ),
            }
        )

    return out


def blocking_findings(
    review: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return [
        finding
        for finding in review.get("findings", [])
        if finding.get("severity")
        in {"critical", "major"}
    ]
