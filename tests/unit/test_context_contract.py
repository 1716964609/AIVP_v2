import tempfile
import unittest

from dataclasses import FrozenInstanceError
from pathlib import Path

from aivp.context.base import (
    ContextArtifact,
    ContextBudget,
    ContextEntry,
    ContextRequest,
)


class ContextContractTests(unittest.TestCase):
    def test_context_request_has_explicit_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            budget = ContextBudget(
                max_files=12,
                max_chars=120_000,
            )

            request = ContextRequest(
                repo=repo,
                task_text="Fix authentication timeout",
                budget=budget,
            )

            self.assertEqual(
                request.repo,
                repo,
            )

            self.assertEqual(
                request.task_text,
                "Fix authentication timeout",
            )

            self.assertEqual(
                request.budget.max_files,
                12,
            )

            self.assertEqual(
                request.budget.max_chars,
                120_000,
            )

    def test_context_entry_preserves_multiple_reasons(self):
        entry = ContextEntry(
            path="src/auth/service.py",
            reasons=(
                "task_keyword_match",
                "direct_import",
            ),
            content="def authenticate():\n    pass\n",
            size_chars=29,
            content_hash="abc123",
        )

        self.assertEqual(
            entry.path,
            "src/auth/service.py",
        )

        self.assertEqual(
            entry.reasons,
            (
                "task_keyword_match",
                "direct_import",
            ),
        )

    def test_context_artifact_is_immutable(self):
        entry = ContextEntry(
            path="src/auth/service.py",
            reasons=("task_keyword_match",),
            content="content",
            size_chars=7,
            content_hash="abc123",
        )

        artifact = ContextArtifact(
            entries=(entry,),
            rendered_context="content",
            total_chars=7,
            manifest_hash="manifest123",
            compiler_version="1.0.0",
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            artifact.total_chars = 8


if __name__ == "__main__":
    unittest.main()
