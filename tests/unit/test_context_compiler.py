import json
import tempfile
import unittest

from pathlib import Path

from aivp.context.base import (
    ContextBudget,
    ContextRequest,
)
from aivp.context.compiler import (
    compile_context,
)


class ContextCompilerTests(
    unittest.TestCase
):
    def _make_repo(
        self,
        root: Path,
    ) -> Path:
        repo = root / "repo"

        (
            repo
            / "src"
        ).mkdir(
            parents=True
        )

        (
            repo
            / "tests"
        ).mkdir()

        (
            repo
            / "src"
            / "authentication.py"
        ).write_text(
            (
                "from .config "
                "import TIMEOUT\n\n"
                "def authenticate():\n"
                "    return TIMEOUT\n"
            ),
            encoding="utf-8",
        )

        (
            repo
            / "src"
            / "config.py"
        ).write_text(
            "TIMEOUT = 30\n",
            encoding="utf-8",
        )

        (
            repo
            / "tests"
            / "test_authentication.py"
        ).write_text(
            (
                "def test_authentication():\n"
                "    pass\n"
            ),
            encoding="utf-8",
        )

        (
            repo
            / "unrelated.py"
        ).write_text(
            "PRICE = 100\n",
            encoding="utf-8",
        )

        return repo

    def _request(
        self,
        repo: Path,
        *,
        max_files: int = 10,
    ) -> ContextRequest:
        return ContextRequest(
            repo=repo,
            task_text=(
                "Fix authentication "
                "timeout handling"
            ),
            budget=ContextBudget(
                max_files=max_files,
                max_chars=100_000,
            ),
        )

    def test_compiler_builds_context_artifact(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo = self._make_repo(
                root
            )

            result = compile_context(
                self._request(
                    repo
                )
            )

            artifact = (
                result.artifact
            )

            paths = [
                entry.path
                for entry
                in artifact.entries
            ]

            self.assertIn(
                (
                    "src/"
                    "authentication.py"
                ),
                paths,
            )

            self.assertNotIn(
                "unrelated.py",
                paths,
            )

            self.assertIn(
                (
                    "===== CONTEXT FILE: "
                    "src/authentication.py "
                    "====="
                ),
                artifact
                .rendered_context,
            )

    def test_manifest_explains_selection(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo = self._make_repo(
                root
            )

            result = compile_context(
                self._request(
                    repo
                )
            )

            manifest = json.loads(
                result.manifest_json
            )

            self.assertEqual(
                manifest[
                    "compiler_version"
                ],
                "1.0.0",
            )

            selected = {
                item["path"]: item
                for item
                in manifest["selected"]
            }

            source = selected[
                "src/authentication.py"
            ]

            self.assertTrue(
                source["reasons"]
            )

            self.assertEqual(
                source[
                    "content_hash"
                ],
                next(
                    entry.content_hash
                    for entry
                    in result
                    .artifact
                    .entries
                    if entry.path
                    == (
                        "src/"
                        "authentication.py"
                    )
                ),
            )

    def test_same_input_produces_same_manifest_hash(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo = self._make_repo(
                root
            )

            request = self._request(
                repo
            )

            first = compile_context(
                request
            )

            second = compile_context(
                request
            )

            self.assertEqual(
                first.artifact
                .manifest_hash,
                second.artifact
                .manifest_hash,
            )

            self.assertEqual(
                first.manifest_json,
                second.manifest_json,
            )

    def test_content_change_changes_manifest_hash(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo = self._make_repo(
                root
            )

            request = self._request(
                repo
            )

            first = compile_context(
                request
            )

            (
                repo
                / "src"
                / "authentication.py"
            ).write_text(
                (
                    "from .config "
                    "import TIMEOUT\n\n"
                    "def authenticate():\n"
                    "    return TIMEOUT + 1\n"
                ),
                encoding="utf-8",
            )

            second = compile_context(
                request
            )

            self.assertNotEqual(
                first.artifact
                .manifest_hash,
                second.artifact
                .manifest_hash,
            )

    def test_manifest_records_budget_rejections(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            repo = self._make_repo(
                root
            )

            result = compile_context(
                self._request(
                    repo,
                    max_files=1,
                )
            )

            manifest = json.loads(
                result.manifest_json
            )

            self.assertEqual(
                len(
                    manifest[
                        "selected"
                    ]
                ),
                1,
            )

            self.assertTrue(
                manifest[
                    "rejected_paths"
                ]
            )

            self.assertEqual(
                manifest[
                    "manifest_hash"
                ],
                result.artifact
                .manifest_hash,
            )


if __name__ == "__main__":
    unittest.main()
