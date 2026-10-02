import tempfile
import unittest

from pathlib import Path

from aivp.context.association import (
    TestAssociation,
)
from aivp.context.base import (
    ContextBudget,
)
from aivp.context.budget import (
    enforce_context_budget,
)
from aivp.context.imports import (
    ImportNeighbor,
)
from aivp.context.selector import (
    SelectionCandidate,
)


class ContextBudgetTests(
    unittest.TestCase
):
    def test_budget_prioritizes_lexical_seed(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo
                / "service.py"
            ).write_text(
                "service",
                encoding="utf-8",
            )

            (
                repo
                / "test_service.py"
            ).write_text(
                "test",
                encoding="utf-8",
            )

            (
                repo
                / "config.py"
            ).write_text(
                "config",
                encoding="utf-8",
            )

            result = enforce_context_budget(
                repo=repo,
                selected=(
                    SelectionCandidate(
                        path="service.py",
                        score=10,
                        reasons=(
                            "path_token:service",
                        ),
                    ),
                ),
                associations=(
                    TestAssociation(
                        source_path=(
                            "service.py"
                        ),
                        test_path=(
                            "test_service.py"
                        ),
                        reason="stem_match",
                    ),
                ),
                imports=(
                    ImportNeighbor(
                        source_path=(
                            "service.py"
                        ),
                        neighbor_path=(
                            "config.py"
                        ),
                        reason=(
                            "direct_import"
                        ),
                    ),
                ),
                budget=ContextBudget(
                    max_files=1,
                    max_chars=1000,
                ),
            )

            self.assertEqual(
                [
                    entry.path
                    for entry in result.entries
                ],
                [
                    "service.py",
                ],
            )

    def test_budget_enforces_max_files(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            for name in (
                "a.py",
                "b.py",
                "c.py",
            ):
                (
                    repo / name
                ).write_text(
                    name,
                    encoding="utf-8",
                )

            result = enforce_context_budget(
                repo=repo,
                selected=(
                    SelectionCandidate(
                        path="a.py",
                        score=3,
                        reasons=("seed",),
                    ),
                    SelectionCandidate(
                        path="b.py",
                        score=2,
                        reasons=("seed",),
                    ),
                    SelectionCandidate(
                        path="c.py",
                        score=1,
                        reasons=("seed",),
                    ),
                ),
                budget=ContextBudget(
                    max_files=2,
                    max_chars=1000,
                ),
            )

            self.assertEqual(
                len(result.entries),
                2,
            )

            self.assertEqual(
                result.rejected_paths,
                ("c.py",),
            )

    def test_budget_enforces_max_chars(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo / "large.py"
            ).write_text(
                "x" * 20,
                encoding="utf-8",
            )

            (
                repo / "small.py"
            ).write_text(
                "y" * 5,
                encoding="utf-8",
            )

            result = enforce_context_budget(
                repo=repo,
                selected=(
                    SelectionCandidate(
                        path="large.py",
                        score=10,
                        reasons=("seed",),
                    ),
                    SelectionCandidate(
                        path="small.py",
                        score=5,
                        reasons=("seed",),
                    ),
                ),
                budget=ContextBudget(
                    max_files=10,
                    max_chars=10,
                ),
            )

            self.assertEqual(
                [
                    entry.path
                    for entry in result.entries
                ],
                [
                    "small.py",
                ],
            )

            self.assertEqual(
                result.total_chars,
                5,
            )

            self.assertIn(
                "large.py",
                result.rejected_paths,
            )

    def test_duplicate_paths_merge_reasons(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo / "shared.py"
            ).write_text(
                "shared",
                encoding="utf-8",
            )

            result = enforce_context_budget(
                repo=repo,
                selected=(
                    SelectionCandidate(
                        path="shared.py",
                        score=5,
                        reasons=(
                            "content_token:shared",
                        ),
                    ),
                ),
                imports=(
                    ImportNeighbor(
                        source_path="other.py",
                        neighbor_path="shared.py",
                        reason="direct_import",
                    ),
                ),
                budget=ContextBudget(
                    max_files=10,
                    max_chars=1000,
                ),
            )

            self.assertEqual(
                len(result.entries),
                1,
            )

            reasons = (
                result.entries[0]
                .reasons
            )

            self.assertIn(
                "content_token:shared",
                reasons,
            )

            self.assertIn(
                "import_neighbor:other.py",
                reasons,
            )

    def test_budget_result_is_deterministic(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo / "b.py"
            ).write_text(
                "b",
                encoding="utf-8",
            )

            (
                repo / "a.py"
            ).write_text(
                "a",
                encoding="utf-8",
            )

            selected = (
                SelectionCandidate(
                    path="b.py",
                    score=1,
                    reasons=("seed",),
                ),
                SelectionCandidate(
                    path="a.py",
                    score=1,
                    reasons=("seed",),
                ),
            )

            budget = ContextBudget(
                max_files=10,
                max_chars=1000,
            )

            first = enforce_context_budget(
                repo=repo,
                selected=selected,
                budget=budget,
            )

            second = enforce_context_budget(
                repo=repo,
                selected=selected,
                budget=budget,
            )

            self.assertEqual(
                first,
                second,
            )

            self.assertEqual(
                [
                    entry.path
                    for entry in first.entries
                ],
                [
                    "a.py",
                    "b.py",
                ],
            )


if __name__ == "__main__":
    unittest.main()
