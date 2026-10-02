from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from aivp.errors import AIVPError
from aivp.structured import load_structured


@dataclass(frozen=True)
class PricingCatalog:
    version: str
    models: Dict[str, Any]

    @classmethod
    def load(
        cls,
        path: Path,
    ) -> "PricingCatalog":
        raw = load_structured(path)

        version = raw.get("version")
        models = raw.get("models")

        if (
            not isinstance(version, str)
            or not version.strip()
        ):
            raise AIVPError(
                "Pricing catalog requires "
                "a non-empty version"
            )

        if not isinstance(models, dict):
            raise AIVPError(
                "Pricing catalog requires "
                "a models mapping"
            )

        return cls(
            version=version.strip(),
            models=dict(models),
        )

    def estimate_cost_usd(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: Optional[int],
        cached_tokens: Optional[int],
        output_tokens: Optional[int],
    ) -> Optional[float]:
        if (
            input_tokens is None
            or cached_tokens is None
            or output_tokens is None
        ):
            return None

        if (
            input_tokens < 0
            or cached_tokens < 0
            or output_tokens < 0
        ):
            return None

        provider_table = self.models.get(
            provider
        )

        if not isinstance(
            provider_table,
            dict,
        ):
            return None

        raw = provider_table.get(model)

        if not isinstance(raw, dict):
            return None

        semantics = raw.get(
            "input_token_accounting"
        )

        try:
            input_rate = float(
                raw[
                    "input_per_million_usd"
                ]
            )

            cached_rate = float(
                raw[
                    "cached_input_per_million_usd"
                ]
            )

            output_rate = float(
                raw[
                    "output_per_million_usd"
                ]
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            return None

        if (
            input_rate < 0
            or cached_rate < 0
            or output_rate < 0
        ):
            return None

        if semantics == "total_includes_cached":
            if cached_tokens > input_tokens:
                return None

            uncached_input = (
                input_tokens
                - cached_tokens
            )

        elif semantics == "uncached_excludes_cached":
            uncached_input = input_tokens

        else:
            return None

        return (
            uncached_input
            * input_rate
            + cached_tokens
            * cached_rate
            + output_tokens
            * output_rate
        ) / 1_000_000
