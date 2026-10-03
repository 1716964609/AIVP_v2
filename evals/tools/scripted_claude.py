#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import time


def argument_after(
    name: str,
) -> str | None:
    args = sys.argv[1:]

    try:
        index = args.index(name)
    except ValueError:
        return None

    if index + 1 >= len(args):
        return None

    return args[index + 1]


def review_for(
    scenario: str,
) -> dict:
    findings = []
    risk = "low"

    if scenario == "medium-pricing":
        risk = "medium"

    elif scenario == "auth-high":
        risk = "high"

    elif scenario == "spec-conflict":
        risk = "medium"

        findings = [
            {
                "severity": "major",
                "category": (
                    "specification"
                ),
                "file": (
                    "evals/fixture_app/"
                    "conflict.py"
                ),
                "line": 1,
                "reason": (
                    "Acceptance criteria "
                    "conflict; a human must "
                    "choose the source of truth."
                ),
                "suggested_direction": (
                    "Resolve the conflicting "
                    "requirements explicitly."
                ),
            }
        ]

    elif scenario == "business-invariant":
        risk = "medium"

        findings = [
            {
                "severity": "major",
                "category": (
                    "business-logic"
                ),
                "file": (
                    "evals/fixture_app/"
                    "business.py"
                ),
                "line": 8,
                "reason": (
                    "The implementation permits "
                    "a 365-day refund even though "
                    "the business invariant is "
                    "30 days."
                ),
                "suggested_direction": (
                    "Preserve the documented "
                    "30-day invariant."
                ),
            }
        ]

    return {
        "summary": (
            "deterministic M7 review"
        ),
        "findings": findings,
        "risk": risk,
        "risk_confidence": 0.99,
        "risk_reasons": [
            (
                "deterministic M7 "
                f"fixture: {scenario}"
            )
        ],
    }


def main() -> int:
    scenario = (
        argument_after("--scenario")
        or "default"
    )

    if scenario == "reviewer-timeout":
        # Config for this case uses a 1s
        # Claude timeout.
        time.sleep(5)

    if scenario == "malformed-output":
        # Deliberately exit successfully while
        # returning content that cannot be parsed
        # as the expected reviewer JSON object.
        print("this is deliberately malformed")
        return 0

    review = review_for(
        scenario
    )

    outer = {
        "type": "result",
        "result": json.dumps(
            review,
            ensure_ascii=False,
        ),
        "duration_ms": 1,
        "duration_api_ms": 1,
        "num_turns": 1,
        "total_cost_usd": 0.0,
        "session_id": (
            "m7-scripted-session"
        ),
        "usage": {
            "input_tokens": 100,
            "cache_read_input_tokens": 0,
            "output_tokens": 25,
        },
        "modelUsage": {},
    }

    print(
        json.dumps(
            outer,
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
