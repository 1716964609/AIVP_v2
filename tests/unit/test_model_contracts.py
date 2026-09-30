import unittest
from pathlib import Path

from aivp.models.base import (
    ModelRequest,
    ModelResult,
)


class ModelContractTests(unittest.TestCase):
    def test_request_preserves_role_and_execution_context(self):
        request = ModelRequest(
            role="generator",
            prompt="implement task",
            repo=Path("/tmp/repo"),
            timeout_seconds=300,
            log_stem="codex-generate",
        )

        self.assertEqual(
            request.role,
            "generator",
        )
        self.assertEqual(
            request.timeout_seconds,
            300,
        )

    def test_unknown_economics_are_not_zero(self):
        result = ModelResult(
            provider="openai",
            model="unknown",
            started_at="start",
            finished_at="end",
            raw_exit_status=0,
        )

        self.assertIsNone(
            result.input_tokens
        )
        self.assertIsNone(
            result.output_tokens
        )
        self.assertIsNone(
            result.cached_tokens
        )
        self.assertIsNone(
            result.cost_estimate_usd
        )


if __name__ == "__main__":
    unittest.main()
