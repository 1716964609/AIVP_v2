import json
import re

from typing import Any, Dict

from aivp.errors import AIVPError


def extract_json_object(
    text: str,
) -> Dict[str, Any]:
    """Parse plain JSON, fenced JSON, or the first JSON object in text."""
    text = text.strip()

    if not text:
        raise AIVPError(
            "Empty JSON response"
        )

    try:
        obj = json.loads(text)

        if isinstance(obj, dict):
            return obj

    except json.JSONDecodeError:
        pass

    fenced = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        re.S | re.I,
    )

    if fenced:
        obj = json.loads(
            fenced.group(1)
        )

        if isinstance(obj, dict):
            return obj

    starts = [
        match.start()
        for match in re.finditer(
            r"\{",
            text,
        )
    ]

    decoder = json.JSONDecoder()

    for start in starts:
        try:
            obj, _ = decoder.raw_decode(
                text[start:]
            )

            if isinstance(obj, dict):
                return obj

        except json.JSONDecodeError:
            continue

    raise AIVPError(
        "Could not parse JSON object from model output"
    )
