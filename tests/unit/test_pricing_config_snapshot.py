import json
import tempfile
import unittest

from pathlib import Path

from aivp.application import (
    _pricing_catalog_from_config,
)
from aivp.telemetry.pricing import (
    PricingCatalog,
)


class PricingConfigSnapshotTests(
    unittest.TestCase
):
    def test_relative_pricing_file_is_snapshotted(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            run_dir = root / "run"

            repo.mkdir()
            run_dir.mkdir()

            config_dir = repo / "config"
            config_dir.mkdir()

            source = (
                config_dir
                / "model-pricing.json"
            )

            source.write_text(
                json.dumps(
                    {
                        "version": "pricing-v1",
                        "models": {
                            "openai": {
                                "test-model": {
                                    "input_token_accounting":
                                        "total_includes_cached",
                                    "input_per_million_usd":
                                        2.0,
                                    "cached_input_per_million_usd":
                                        0.5,
                                    "output_per_million_usd":
                                        8.0,
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            snapshot = (
                run_dir
                / "pricing-catalog.json"
            )

            catalog = (
                _pricing_catalog_from_config(
                    config={
                        "pricing": {
                            "file": (
                                "config/"
                                "model-pricing.json"
                            )
                        }
                    },
                    repo=repo,
                    snapshot_path=snapshot,
                )
            )

            self.assertIsNotNone(catalog)
            self.assertEqual(
                catalog.version,
                "pricing-v1",
            )
            self.assertTrue(
                snapshot.exists()
            )

            source.write_text(
                json.dumps(
                    {
                        "version": "pricing-v2",
                        "models": {},
                    }
                ),
                encoding="utf-8",
            )

            restored = PricingCatalog.load(
                snapshot
            )

            self.assertEqual(
                restored.version,
                "pricing-v1",
            )

            self.assertIn(
                "test-model",
                restored.models["openai"],
            )

    def test_missing_pricing_config_is_disabled(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            run_dir = root / "run"

            repo.mkdir()
            run_dir.mkdir()

            snapshot = (
                run_dir
                / "pricing-catalog.json"
            )

            catalog = (
                _pricing_catalog_from_config(
                    config={},
                    repo=repo,
                    snapshot_path=snapshot,
                )
            )

            self.assertIsNone(catalog)
            self.assertFalse(
                snapshot.exists()
            )


if __name__ == "__main__":
    unittest.main()
