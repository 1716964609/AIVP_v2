from __future__ import annotations

import json

from pathlib import Path
from typing import Any, Dict

from aivp.errors import AIVPError


def load_structured(
    path: Path,
) -> Dict[str, Any]:
    if not path.exists():
        raise AIVPError(
            f"Structured file not found: {path}"
        )

    text = path.read_text(
        encoding="utf-8"
    )

    suffix = path.suffix.lower()

    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIVPError(
                f"Invalid JSON: {path}"
            ) from exc

    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise AIVPError(
                "YAML input requires PyYAML"
            ) from exc

        try:
            data = yaml.safe_load(text)
        except Exception as exc:
            raise AIVPError(
                f"Invalid YAML: {path}"
            ) from exc

    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:
                import yaml  # type: ignore
            except ImportError as exc:
                raise AIVPError(
                    "Unknown structured file "
                    "format and PyYAML is not "
                    "installed"
                ) from exc

            try:
                data = yaml.safe_load(text)
            except Exception as exc:
                raise AIVPError(
                    "Cannot parse structured "
                    f"file: {path}"
                ) from exc

    if not isinstance(data, dict):
        raise AIVPError(
            "Structured input must contain "
            f"an object/mapping: {path}"
        )

    return dict(data)
