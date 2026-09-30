import json
import tempfile
import unittest

from pathlib import Path

from aivp.cli import build_parser
from aivp.structured import (
    load_structured,
)


class CLITests(unittest.TestCase):
    def test_run_command_parses(self):
        parser = build_parser()

        args = parser.parse_args(
            [
                "run",
                "--repo",
                "/tmp/repo",
                "--task",
                "task.json",
                "--config",
                "config.json",
                "--yes",
            ]
        )

        self.assertEqual(
            args.command,
            "run",
        )

        self.assertTrue(
            args.yes
        )

    def test_resume_command_parses(self):
        parser = build_parser()

        args = parser.parse_args(
            [
                "resume",
                "run-123",
            ]
        )

        self.assertEqual(
            args.command,
            "resume",
        )

        self.assertEqual(
            args.run_id,
            "run-123",
        )

    def test_load_structured_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = (
                Path(tmp)
                / "input.json"
            )

            path.write_text(
                json.dumps(
                    {
                        "hello": "world"
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_structured(
                path
            )

            self.assertEqual(
                loaded,
                {
                    "hello": "world"
                },
            )


if __name__ == "__main__":
    unittest.main()
