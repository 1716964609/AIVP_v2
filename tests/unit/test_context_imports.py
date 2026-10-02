import tempfile
import unittest

from pathlib import Path

from aivp.context.imports import (
    find_import_neighbors,
)
from aivp.context.repo_map import (
    build_repo_map,
)
from aivp.context.selector import (
    SelectionCandidate,
)


class ContextImportNeighborTests(
    unittest.TestCase
):
    def test_python_absolute_import_resolves_repo_file(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo
                / "src"
                / "app"
            ).mkdir(
                parents=True
            )

            (
                repo
                / "src"
                / "app"
                / "service.py"
            ).write_text(
                (
                    "from app.auth "
                    "import authenticate\n"
                ),
                encoding="utf-8",
            )

            (
                repo
                / "src"
                / "app"
                / "auth.py"
            ).write_text(
                (
                    "def authenticate(): "
                    "pass\n"
                ),
                encoding="utf-8",
            )

            repo_map = build_repo_map(
                repo
            )

            neighbors = (
                find_import_neighbors(
                    repo=repo,
                    repo_map=repo_map,
                    selected=(
                        SelectionCandidate(
                            path=(
                                "src/app/"
                                "service.py"
                            ),
                            score=1,
                            reasons=(
                                "seed",
                            ),
                        ),
                    ),
                )
            )

            self.assertEqual(
                len(neighbors),
                1,
            )

            self.assertEqual(
                neighbors[0].neighbor_path,
                "src/app/auth.py",
            )

            self.assertEqual(
                neighbors[0].reason,
                "direct_import",
            )

    def test_python_relative_import_resolves_neighbor(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo
                / "pkg"
            ).mkdir()

            (
                repo
                / "pkg"
                / "service.py"
            ).write_text(
                "from .auth import login\n",
                encoding="utf-8",
            )

            (
                repo
                / "pkg"
                / "auth.py"
            ).write_text(
                "def login(): pass\n",
                encoding="utf-8",
            )

            neighbors = (
                find_import_neighbors(
                    repo=repo,
                    repo_map=build_repo_map(
                        repo
                    ),
                    selected=(
                        SelectionCandidate(
                            path=(
                                "pkg/service.py"
                            ),
                            score=1,
                            reasons=(
                                "seed",
                            ),
                        ),
                    ),
                )
            )

            self.assertEqual(
                [
                    item.neighbor_path
                    for item in neighbors
                ],
                [
                    "pkg/auth.py",
                ],
            )

    def test_typescript_relative_import_resolves_neighbor(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo
                / "src"
            ).mkdir()

            (
                repo
                / "src"
                / "service.ts"
            ).write_text(
                (
                    "import { timeout } "
                    "from './config';\n"
                ),
                encoding="utf-8",
            )

            (
                repo
                / "src"
                / "config.ts"
            ).write_text(
                (
                    "export const "
                    "timeout = 30;\n"
                ),
                encoding="utf-8",
            )

            neighbors = (
                find_import_neighbors(
                    repo=repo,
                    repo_map=build_repo_map(
                        repo
                    ),
                    selected=(
                        SelectionCandidate(
                            path=(
                                "src/service.ts"
                            ),
                            score=1,
                            reasons=(
                                "seed",
                            ),
                        ),
                    ),
                )
            )

            self.assertEqual(
                [
                    item.neighbor_path
                    for item in neighbors
                ],
                [
                    "src/config.ts",
                ],
            )

    def test_external_import_is_ignored(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo
                / "service.py"
            ).write_text(
                (
                    "import json\n"
                    "import requests\n"
                ),
                encoding="utf-8",
            )

            neighbors = (
                find_import_neighbors(
                    repo=repo,
                    repo_map=build_repo_map(
                        repo
                    ),
                    selected=(
                        SelectionCandidate(
                            path="service.py",
                            score=1,
                            reasons=(
                                "seed",
                            ),
                        ),
                    ),
                )
            )

            self.assertEqual(
                neighbors,
                (),
            )

    def test_import_expansion_is_one_hop_only(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo
                / "a.py"
            ).write_text(
                "import b\n",
                encoding="utf-8",
            )

            (
                repo
                / "b.py"
            ).write_text(
                "import c\n",
                encoding="utf-8",
            )

            (
                repo
                / "c.py"
            ).write_text(
                "value = 1\n",
                encoding="utf-8",
            )

            neighbors = (
                find_import_neighbors(
                    repo=repo,
                    repo_map=build_repo_map(
                        repo
                    ),
                    selected=(
                        SelectionCandidate(
                            path="a.py",
                            score=1,
                            reasons=(
                                "seed",
                            ),
                        ),
                    ),
                )
            )

            self.assertEqual(
                [
                    item.neighbor_path
                    for item in neighbors
                ],
                [
                    "b.py",
                ],
            )

    def test_import_neighbors_are_deterministic(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            (
                repo
                / "service.py"
            ).write_text(
                (
                    "import zebra\n"
                    "import alpha\n"
                ),
                encoding="utf-8",
            )

            (
                repo
                / "zebra.py"
            ).write_text(
                "value = 1\n",
                encoding="utf-8",
            )

            (
                repo
                / "alpha.py"
            ).write_text(
                "value = 1\n",
                encoding="utf-8",
            )

            repo_map = build_repo_map(
                repo
            )

            selected = (
                SelectionCandidate(
                    path="service.py",
                    score=1,
                    reasons=("seed",),
                ),
            )

            first = find_import_neighbors(
                repo=repo,
                repo_map=repo_map,
                selected=selected,
            )

            second = find_import_neighbors(
                repo=repo,
                repo_map=repo_map,
                selected=selected,
            )

            self.assertEqual(
                first,
                second,
            )

            self.assertEqual(
                [
                    item.neighbor_path
                    for item in first
                ],
                [
                    "alpha.py",
                    "zebra.py",
                ],
            )


if __name__ == "__main__":
    unittest.main()
