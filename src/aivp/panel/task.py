from typing import Any, Dict


def render_task(
    task: Dict[str, Any],
) -> str:
    acceptance = "\n".join(
        f"- {x}"
        for x in task.get(
            "acceptance",
            [],
        )
    )

    constraints = "\n".join(
        f"- {x}"
        for x in task.get(
            "constraints",
            [],
        )
    )

    return (
        f"TASK\n"
        f"{task.get('task','')}\n\n"
        f"ACCEPTANCE CRITERIA\n"
        f"{acceptance or '- None specified'}\n\n"
        f"CONSTRAINTS\n"
        f"{constraints or '- None specified'}\n"
    )
