import tempfile
import unittest

from pathlib import Path

from aivp.models.base import (
    ModelRequest,
    ModelResult,
)
from aivp.panel.orchestrator import (
    _invoke_model_call,
)
from aivp.state.durable import (
    DurableExecution,
)
from aivp.state.sqlite import (
    SQLiteStateStore,
)
from aivp.telemetry.pricing import (
    PricingCatalog,
)


class FakeAdapter:
    def __init__(
        self,
        *,
        native_cost=None,
    ):
        self.native_cost = native_cost

    def invoke(
        self,
        request: ModelRequest,
    ) -> ModelResult:
        return ModelResult(
            provider="openai",
            model="test-model",
            started_at="2026-10-02T00:00:00+00:00",
            finished_at="2026-10-02T00:00:01+00:00",
            raw_exit_status=0,
            input_tokens=1000,
            cached_tokens=400,
            output_tokens=200,
            cost_estimate_usd=(
                self.native_cost
            ),
            last_message="ok",
        )


def catalog() -> PricingCatalog:
    return PricingCatalog(
        version="test-v1",
        models={
            "openai": {
                "test-model": {
                    "input_token_accounting":
                        "total_includes_cached",
                    "input_per_million_usd": 2.0,
                    "cached_input_per_million_usd": 0.5,
                    "output_per_million_usd": 8.0,
                }
            }
        },
    )


class PricingLedgerWiringTests(
    unittest.TestCase
):
    def _run(
        self,
        *,
        native_cost=None,
    ):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)

        root = Path(tmp.name)
        repo = root / "repo"
        repo.mkdir()

        store = SQLiteStateStore(
            root / "state.db"
        )
        self.addCleanup(store.close)

        pricing = catalog()

        store.begin_run(
            run_id="run-1",
            repo_path=repo,
            base_sha="base",
            current_state="GENERATING",
            pricing_version=pricing.version,
        )

        durable = DurableExecution(
            store=store,
            run_id="run-1",
            pricing_catalog=pricing,
        )

        _invoke_model_call(
            adapter=FakeAdapter(
                native_cost=native_cost
            ),
            request=ModelRequest(
                role="generator",
                prompt="work",
                repo=repo,
                timeout_seconds=10,
                log_stem="generate",
            ),
            durable=durable,
            step_id="generate",
        )

        return store

    def test_fallback_cost_is_recorded(self):
        store = self._run()

        rows = store.model_calls_for_run(
            "run-1"
        )

        self.assertEqual(len(rows), 1)

        self.assertAlmostEqual(
            rows[0]["cost_usd"],
            0.003,
        )

        run = store.connection.execute(
            """
            SELECT pricing_version
            FROM runs
            WHERE run_id = ?
            """,
            ("run-1",),
        ).fetchone()

        self.assertEqual(
            run["pricing_version"],
            "test-v1",
        )

    def test_native_cost_wins(self):
        store = self._run(
            native_cost=0.123456,
        )

        rows = store.model_calls_for_run(
            "run-1"
        )

        self.assertAlmostEqual(
            rows[0]["cost_usd"],
            0.123456,
        )


if __name__ == "__main__":
    unittest.main()
