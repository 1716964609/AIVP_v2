import json
import tempfile
import unittest

from pathlib import Path

from aivp.telemetry.pricing import (
    PricingCatalog,
)


class PricingCatalogTests(unittest.TestCase):
    def _catalog(
        self,
        *,
        semantics: str,
    ) -> PricingCatalog:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pricing.json"

            path.write_text(
                json.dumps(
                    {
                        "version": "test-v1",
                        "models": {
                            "openai": {
                                "test-model": {
                                    "input_token_accounting": semantics,
                                    "input_per_million_usd": 2.0,
                                    "cached_input_per_million_usd": 0.5,
                                    "output_per_million_usd": 8.0,
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            return PricingCatalog.load(path)

    def test_loads_version(self):
        catalog = self._catalog(
            semantics=(
                "total_includes_cached"
            )
        )

        self.assertEqual(
            catalog.version,
            "test-v1",
        )

    def test_total_input_includes_cached(self):
        catalog = self._catalog(
            semantics=(
                "total_includes_cached"
            )
        )

        cost = catalog.estimate_cost_usd(
            provider="openai",
            model="test-model",
            input_tokens=1000,
            cached_tokens=400,
            output_tokens=200,
        )

        self.assertAlmostEqual(
            cost,
            0.003,
        )

    def test_uncached_input_excludes_cached(self):
        catalog = self._catalog(
            semantics=(
                "uncached_excludes_cached"
            )
        )

        cost = catalog.estimate_cost_usd(
            provider="openai",
            model="test-model",
            input_tokens=600,
            cached_tokens=400,
            output_tokens=200,
        )

        self.assertAlmostEqual(
            cost,
            0.003,
        )

    def test_unknown_model_returns_none(self):
        catalog = self._catalog(
            semantics=(
                "total_includes_cached"
            )
        )

        cost = catalog.estimate_cost_usd(
            provider="openai",
            model="unknown",
            input_tokens=1000,
            cached_tokens=400,
            output_tokens=200,
        )

        self.assertIsNone(cost)

    def test_missing_usage_returns_none(self):
        catalog = self._catalog(
            semantics=(
                "total_includes_cached"
            )
        )

        cost = catalog.estimate_cost_usd(
            provider="openai",
            model="test-model",
            input_tokens=None,
            cached_tokens=400,
            output_tokens=200,
        )

        self.assertIsNone(cost)

    def test_invalid_cached_subset_returns_none(self):
        catalog = self._catalog(
            semantics=(
                "total_includes_cached"
            )
        )

        cost = catalog.estimate_cost_usd(
            provider="openai",
            model="test-model",
            input_tokens=100,
            cached_tokens=200,
            output_tokens=10,
        )

        self.assertIsNone(cost)


if __name__ == "__main__":
    unittest.main()
