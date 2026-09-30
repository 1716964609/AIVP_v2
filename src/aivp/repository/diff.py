from typing import Any, Dict


def truncate_diff(
    config: Dict[str, Any],
    diff_text: str,
) -> str:
    max_chars = int(
        config.get(
            "diff_context",
            {},
        ).get(
            "max_chars",
            120000,
        )
    )

    if len(diff_text) <= max_chars:
        return diff_text

    half = max_chars // 2

    return (
        diff_text[:half]
        + (
            "\n\n... [AIVP TRUNCATED "
            f"{len(diff_text)-max_chars} CHARS] "
            "...\n\n"
        )
        + diff_text[-half:]
    )
