#!/usr/bin/env python3

from __future__ import annotations

import json
import sys

from pathlib import Path


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


def write(
    relative: str,
    text: str,
) -> None:
    path = Path(relative)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        text,
        encoding="utf-8",
    )


def mutate(
    scenario: str,
) -> None:
    if scenario == "low-username":
        write(
            "evals/fixture_app/usernames.py",
            '''def normalize_username(value: str) -> str:
    """Return a canonical username."""
    return value.strip().lower()
''',
        )
        return

    if scenario == "medium-pricing":
        write(
            "evals/fixture_app/pricing.py",
            '''def discounted_price(
    amount: float,
) -> float:
    """Apply the standard 10% discount."""
    return round(amount * 0.90, 2)
''',
        )
        return

    if scenario == "spec-conflict":
        write(
            "evals/fixture_app/conflict.py",
            'SPEC_CHOICE = "option-a"\n',
        )
        return

    if scenario == "controlled-repair":
        target = Path(
            "evals/fixture_app/"
            "repair_target.py"
        )

        current = target.read_text(
            encoding="utf-8"
        )

        if "return 0" in current:
            replacement = '''def answer() -> int:
    return 1
'''
        else:
            replacement = '''def answer() -> int:
    return 0
'''

        write(
            str(target),
            replacement,
        )
        return

    if scenario == "auth-high":
        write(
            "evals/fixture_app/auth/policy.py",
            "ALLOW_GUEST_ADMIN = True\n",
        )
        return

    if scenario == "large-diff":
        write(
            "evals/fixture_app/usernames.py",
            """def normalize_username(value: str) -> str:
    \"\"\"Return a canonical username.\"\"\"
    return value  # large-diff fixture change
""",
        )

        write(
            "evals/fixture_app/pricing.py",
            """def discounted_price(
    amount: float,
) -> float:
    \"\"\"Return the customer price.\"\"\"
    return round(amount, 2)  # large-diff fixture change
""",
        )

        write(
            "evals/fixture_app/conflict.py",
            (
                'SPEC_CHOICE = "baseline"  '
                '# large-diff fixture change\n'
            ),
        )

        return

    if scenario == "dependency-addition":
        path = Path(
            "evals/fixture_app/"
            "requirements.txt"
        )

        text = path.read_text(
            encoding="utf-8"
        )

        dependency = (
            "example-package==1.0.0"
        )

        if dependency not in text:
            text = (
                text.rstrip()
                + "\n"
                + dependency
                + "\n"
            )

        write(
            str(path),
            text,
        )
        return

    if scenario == "business-invariant":
        write(
            "evals/fixture_app/business.py",
            '''def can_refund(
    paid: bool,
    days_since_purchase: int,
) -> bool:
    """Refunds require payment and <= 30 days."""
    return (
        paid
        and (
            days_since_purchase <= 30
            or days_since_purchase == 365
        )
    )
''',
        )
        return

    # Safety, durability, timeout, malformed-output
    # and budget cases intentionally need no source edit.


def risk_payload(
    scenario: str,
) -> dict:
    if scenario == "auth-high":
        risk = "high"
    elif scenario in {
        "medium-pricing",
        "dependency-addition",
    }:
        risk = "medium"
    else:
        risk = "low"

    return {
        "risk": risk,
        "confidence": 0.99,
        "reasons": [
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

    output_file_raw = (
        argument_after("-o")
    )

    if output_file_raw is None:
        print(
            "scripted Codex requires -o",
            file=sys.stderr,
        )
        return 2

    output_file = Path(
        output_file_raw
    )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    is_risk = (
        argument_after(
            "--output-schema"
        )
        is not None
    )

    if is_risk:
        output_file.write_text(
            json.dumps(
                risk_payload(
                    scenario
                ),
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        mutate(
            scenario
        )

        output_file.write_text(
            (
                "scripted edit complete: "
                f"{scenario}\n"
            ),
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "type": "thread.started",
                "thread_id": (
                    "m7-scripted-thread"
                ),
            }
        )
    )

    print(
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 0,
                    "output_tokens": 25,
                },
            }
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
