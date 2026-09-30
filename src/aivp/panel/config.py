from typing import Any, Dict

from aivp.execution.runtime import Budgets


def budgets_from(
    config: Dict[str, Any],
) -> Budgets:
    budgets = config.get(
        "budgets",
        {},
    )

    return Budgets(
        max_fix_iterations=int(
            budgets.get(
                "max_fix_iterations",
                2,
            )
        ),
        codex_max_calls=int(
            budgets.get(
                "codex_max_calls",
                4,
            )
        ),
        claude_max_calls=int(
            budgets.get(
                "claude_max_calls",
                3,
            )
        ),
        codex_timeout_seconds=int(
            budgets.get(
                "codex_timeout_seconds",
                300,
            )
        ),
        claude_timeout_seconds=int(
            budgets.get(
                "claude_timeout_seconds",
                300,
            )
        ),
        whole_run_timeout_seconds=int(
            budgets.get(
                "whole_run_timeout_seconds",
                900,
            )
        ),
    )
