import json

from typing import Any, Dict, Optional

from aivp.models.claude import (
    blocking_findings,
)
from aivp.verification.deterministic import (
    verification_summary,
)


def generate_prompt(
    task_text: str,
) -> str:
    return f"""You are the Generator/Fixer in a controlled code-verification experiment.

Implement the task in the current Git repository.

Rules:
- Make the smallest coherent change satisfying the task.
- Add/update tests when required.
- Do not commit or push.
- Do not change unrelated files.
- Do not modify secrets or credentials.
- Do not install new dependencies unless the task explicitly permits it.
- Stop after implementing the change; the orchestrator runs verification separately.

{task_text}
"""


def fix_prompt(
    task_text: str,
    *,
    verification: Optional[
        Dict[str, Any]
    ] = None,
    review: Optional[
        Dict[str, Any]
    ] = None,
) -> str:
    parts = [
        (
            "You are the Generator/Fixer. "
            "Fix the current working tree; "
            "do not commit or push."
        ),
        (
            "Keep the change minimal and "
            "within the original constraints."
        ),
        task_text,
    ]

    if verification is not None:
        parts += [
            "DETERMINISTIC FAILURES",
            verification_summary(
                verification
            ),
        ]

    if review is not None:
        parts += [
            "INDEPENDENT REVIEW FINDINGS",
            json.dumps(
                blocking_findings(
                    review
                ),
                ensure_ascii=False,
                indent=2,
            ),
        ]

    parts.append(
        "Fix only the blocking issues, then stop. "
        "The orchestrator will re-run verification."
    )

    return "\n\n".join(parts)
