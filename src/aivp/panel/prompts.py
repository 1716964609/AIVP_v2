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


def review_prompt(
    task_text: str,
    diff_text: str,
    verification: Dict[str, Any],
) -> str:
    return f"""You are an independent code reviewer. The generator is a different model.

You cannot approve based on style alone. Review the change against:
1. task and acceptance criteria
2. correctness and edge cases
3. regressions / missing tests
4. security and data safety
5. architecture / coupling / operational concerns

Return ONLY one JSON object, no Markdown:
{{
  "summary": "short summary",
  "findings": [
    {{
      "severity": "critical|major|minor|suggestion",
      "category": "correctness|security|tests|architecture|operations|other",
      "file": "path",
      "line": 123,
      "reason": "why this is a problem",
      "suggested_direction": "how to address it without writing the patch"
    }}
  ],
  "risk": "low|medium|high",
  "risk_confidence": 0.0,
  "risk_reasons": ["..."]
}}

Risk definitions:
- low: local/reversible small blast radius
- medium: meaningful behavior change but bounded/reversible
- high: auth/security/permissions/data migration/destructive operation,
        large cross-service blast radius, irreversible change, or uncertainty
        requiring human judgment

{task_text}

DETERMINISTIC VERIFICATION
--------------------------
{verification_summary(verification)}

DIFF
----
{diff_text}
"""


def risk_prompt(
    task_text: str,
    diff_text: str,
) -> str:
    return f"""You are the independent final risk judge.

Do NOT edit files. Assess the production/change risk of the proposed diff.
Return only the JSON object required by the output schema.

Risk definitions:
- low: local/reversible change with small blast radius
- medium: meaningful behavior change but bounded/reversible
- high: auth/security/permissions/data migration/destructive operation,
        large cross-service blast radius, irreversible change, or uncertainty
        that requires human judgment

{task_text}

DIFF
----
{diff_text}
"""
