import tempfile
import unittest
from pathlib import Path

from aivp.artifacts.io import (
    dump_json,
    dump_text,
)
from aivp.errors import (
    AIVPError,
    BudgetExceeded,
    CommandFailed,
)

from aivp.legacy.orchestrator_v1 import (
    dump_json as legacy_dump_json,
    dump_text as legacy_dump_text,
)


class CorePrimitiveCompatibilityTests(
    unittest.TestCase
):
    def test_error_hierarchy(self):
        self.assertTrue(
            issubclass(
                BudgetExceeded,
                AIVPError,
            )
        )

        self.assertTrue(
            issubclass(
                CommandFailed,
                AIVPError,
            )
        )

    def test_command_failed_returncode(self):
        exc = CommandFailed(
            "failed",
            7,
        )

        self.assertEqual(
            str(exc),
            "failed",
        )

        self.assertEqual(
            exc.returncode,
            7,
        )

    def test_dump_json_matches_legacy(self):
        value = {
            "hello": "世界",
            "nested": {
                "value": 1,
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            legacy_path = (
                root / "legacy" / "value.json"
            )

            new_path = (
                root / "new" / "value.json"
            )

            legacy_dump_json(
                legacy_path,
                value,
            )

            dump_json(
                new_path,
                value,
            )

            self.assertEqual(
                new_path.read_bytes(),
                legacy_path.read_bytes(),
            )

    def test_dump_text_matches_legacy(self):
        value = "hello\n世界\n"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            legacy_path = (
                root / "legacy" / "value.txt"
            )

            new_path = (
                root / "new" / "value.txt"
            )

            legacy_dump_text(
                legacy_path,
                value,
            )

            dump_text(
                new_path,
                value,
            )

            self.assertEqual(
                new_path.read_bytes(),
                legacy_path.read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
