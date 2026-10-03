import json
import tempfile
import unittest

from types import SimpleNamespace
from unittest.mock import patch

from pathlib import Path

from aivp.cli import build_parser, main
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

    def test_eval_run_command_parses(
        self,
    ):
        parser = build_parser()

        args = parser.parse_args(
            [
                "eval",
                "run",
                "suite.json",
                "--yes",
                "--suite-run-id",
                "suite-test",
            ]
        )

        self.assertEqual(
            args.command,
            "eval",
        )

        self.assertEqual(
            args.eval_command,
            "run",
        )

        self.assertEqual(
            args.suite,
            Path("suite.json"),
        )

        self.assertEqual(
            args.suite_run_id,
            "suite-test",
        )

        self.assertTrue(
            args.yes
        )

    def test_eval_run_requires_yes(
        self,
    ):
        result = main(
            [
                "eval",
                "run",
                "suite.json",
            ]
        )

        self.assertEqual(
            result,
            2,
        )

    def test_eval_run_returns_suite_outcome(
        self,
    ):
        fake_suite = object()

        fake_result = (
            SimpleNamespace(
                suite_run_id=(
                    "suite-test"
                ),
                suite_root=Path(
                    "/tmp/suite-test"
                ),
                overall_outcome=(
                    "PASS"
                ),
            )
        )

        with patch(
            "aivp.cli.load_eval_suite",
            return_value=fake_suite,
        ), patch(
            "aivp.cli.run_eval_suite",
            return_value=fake_result,
        ) as run_suite:
            result = main(
                [
                    "eval",
                    "run",
                    "suite.json",
                    "--yes",
                    "--suite-run-id",
                    "suite-test",
                ]
            )

        self.assertEqual(
            result,
            0,
        )

        self.assertEqual(
            run_suite.call_count,
            1,
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
