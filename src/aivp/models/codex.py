from pathlib import Path
from typing import Any, Dict, List


def codex_base_argv(
    config: Dict[str, Any],
    *,
    risk: bool,
    repo: Path,
) -> List[str]:
    c = config["codex"]

    argv = [str(c.get("binary", "codex"))]

    extra_key = (
        "risk_extra_args"
        if risk
        else "generator_extra_args"
    )

    argv.extend(
        str(x)
        for x in c.get(extra_key, ["exec"])
    )

    model = str(c.get("model", "")).strip()

    if model:
        argv.extend(["--model", model])

    reasoning = str(
        c.get("reasoning_effort", "")
    ).strip()

    if reasoning:
        argv.extend(
            [
                "--config",
                f'model_reasoning_effort="{reasoning}"',
            ]
        )

    argv.extend(["--cd", str(repo.resolve())])

    return argv


def codex_risk_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "risk",
            "confidence",
            "reasons",
        ],
        "properties": {
            "risk": {
                "type": "string",
                "enum": [
                    "low",
                    "medium",
                    "high",
                ],
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },
            "reasons": {
                "type": "array",
                "items": {
                    "type": "string",
                },
                "maxItems": 10,
            },
        },
    }
