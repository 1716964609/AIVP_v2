import tempfile
import unittest
from pathlib import Path

from aivp.legacy.orchestrator_v1 import (
    blocking_findings as legacy_blocking_findings,
    claude_argv as legacy_claude_argv,
    codex_base_argv as legacy_codex_base_argv,
    codex_risk_schema as legacy_codex_risk_schema,
    normalize_findings as legacy_normalize_findings,
)

from aivp.models.claude import (
    blocking_findings,
    claude_argv,
    normalize_findings,
)

from aivp.models.codex import (
    codex_base_argv,
    codex_risk_schema,
)


class ModelHelperCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "codex": {
                "binary": "codex",
                "model": "",
                "reasoning_effort": "low",
                "generator_extra_args": [
                    "exec",
                    "--sandbox",
                    "workspace-write",
                ],
                "risk_extra_args": [
                    "exec",
                    "--sandbox",
                    "read-only",
                ],
            },
            "claude": {
                "binary": "claude",
                "model": "sonnet",
                "max_turns": 2,
                "extra_args": [
                    "-p",
                    "--output-format",
                    "json",
                ],
            },
        }

    def test_codex_generator_argv_matches_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            self.assertEqual(
                codex_base_argv(
                    self.config,
                    risk=False,
                    repo=repo,
                ),
                legacy_codex_base_argv(
                    self.config,
                    risk=False,
                    repo=repo,
                ),
            )

    def test_codex_risk_argv_matches_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            self.assertEqual(
                codex_base_argv(
                    self.config,
                    risk=True,
                    repo=repo,
                ),
                legacy_codex_base_argv(
                    self.config,
                    risk=True,
                    repo=repo,
                ),
            )

    def test_codex_risk_schema_matches_legacy(self):
        self.assertEqual(
            codex_risk_schema(),
            legacy_codex_risk_schema(),
        )

    def test_claude_argv_matches_legacy(self):
        self.assertEqual(
            claude_argv(self.config),
            legacy_claude_argv(self.config),
        )

    def test_findings_normalization_matches_legacy(self):
        value = [
            {
                "severity": "CRITICAL",
                "category": "security",
                "file": "auth/access.py",
                "line": 10,
                "reason": "unsafe",
                "suggested_direction": "fix",
            },
            {
                "severity": "nonsense",
                "reason": "fallback",
            },
            "not-a-dict",
        ]

        self.assertEqual(
            normalize_findings(value),
            legacy_normalize_findings(value),
        )

    def test_blocking_findings_matches_legacy(self):
        review = {
            "findings": [
                {"severity": "critical"},
                {"severity": "major"},
                {"severity": "minor"},
                {"severity": "suggestion"},
            ]
        }

        self.assertEqual(
            blocking_findings(review),
            legacy_blocking_findings(review),
        )


if __name__ == "__main__":
    unittest.main()
