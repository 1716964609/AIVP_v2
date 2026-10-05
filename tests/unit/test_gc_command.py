from __future__ import annotations

import io
import json
import tempfile
import unittest

from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from aivp.cli import (
    build_parser,
    main,
)
from aivp.maintenance.gc_command import (
    GCReportItem,
    _protected_run_prefixes,
    gc_report_has_errors,
    parse_duration_seconds,
    run_gc,
)


class GCCommandTests(
    unittest.TestCase
):
    def test_parse_duration_days(
        self,
    ):
        self.assertEqual(
            parse_duration_seconds(
                "7d"
            ),
            604800.0,
        )

    def test_parse_duration_rejects_invalid_value(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            parse_duration_seconds(
                "seven-days"
            )

    def test_project_state_extracts_formal_runs(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            source = (
                Path(tmp)
                / "PROJECT_STATE.json"
            )

            source.write_text(
                json.dumps(
                    {
                        "m7": {
                            "formal_run": (
                                "m7-final-clean-"
                                "20261004-072204"
                            )
                        },
                        "m8": {
                            "before_formal_run": (
                                "m7-final-clean-"
                                "20261004-072204"
                            ),
                            "after_formal_run": (
                                "m8-final-routing-"
                                "20261004-120728"
                            ),
                        },
                    }
                ),
                encoding="utf-8",
            )

            protected = (
                _protected_run_prefixes(
                    source
                )
            )

            self.assertIn(
                (
                    "m7-final-clean-"
                    "20261004-072204"
                ),
                protected,
            )

            self.assertIn(
                (
                    "m8-final-routing-"
                    "20261004-120728"
                ),
                protected,
            )

    def test_parser_gc_defaults_to_dry_run(
        self,
    ):
        parser = build_parser()

        args = parser.parse_args(
            [
                "gc",
                "--older-than",
                "7d",
            ]
        )

        self.assertEqual(
            args.command,
            "gc",
        )

        self.assertEqual(
            args.older_than,
            604800.0,
        )

        self.assertFalse(
            args.yes
        )

    @patch(
        "aivp.maintenance."
        "gc_command.cleanup_stale_containers"
    )
    @patch(
        "aivp.maintenance."
        "gc_command.cleanup_cache"
    )
    def test_run_gc_dry_run_routes_to_all_subsystems(
        self,
        mock_cache,
        mock_docker,
    ):
        mock_cache.return_value = []
        mock_docker.return_value = []

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            reports = root / "reports"
            reports.mkdir()

            project_state = (
                root
                / "PROJECT_STATE.json"
            )

            project_state.write_text(
                "{}\n",
                encoding="utf-8",
            )

            state_db = (
                root / "state.db"
            )

            items = run_gc(
                older_than_seconds=(
                    604800.0
                ),
                reports_root=reports,
                state_db=state_db,
                project_state=(
                    project_state
                ),
                dry_run=True,
            )

            self.assertEqual(
                items,
                [],
            )

            self.assertTrue(
                mock_cache.call_args
                .kwargs["dry_run"]
            )

            self.assertTrue(
                mock_docker.call_args
                .kwargs["dry_run"]
            )

    @patch(
        "aivp.cli.run_gc"
    )
    def test_cli_gc_without_yes_is_dry_run(
        self,
        mock_run_gc,
    ):
        mock_run_gc.return_value = [
            GCReportItem(
                kind="cache",
                resource="fixture",
                classification="expired",
                action="gc-candidate",
                reason="fixture",
            )
        ]

        output = io.StringIO()

        with redirect_stdout(
            output
        ):
            result = main(
                [
                    "gc",
                    "--older-than",
                    "7d",
                ]
            )

        self.assertEqual(
            result,
            0,
        )

        self.assertTrue(
            mock_run_gc.call_args
            .kwargs["dry_run"]
        )

        self.assertIn(
            "GC_MODE=DRY_RUN",
            output.getvalue(),
        )

    @patch(
        "aivp.cli.run_gc"
    )
    def test_cli_gc_yes_enables_apply(
        self,
        mock_run_gc,
    ):
        mock_run_gc.return_value = []

        output = io.StringIO()

        with redirect_stdout(
            output
        ):
            result = main(
                [
                    "gc",
                    "--older-than",
                    "7d",
                    "--yes",
                ]
            )

        self.assertEqual(
            result,
            0,
        )

        self.assertFalse(
            mock_run_gc.call_args
            .kwargs["dry_run"]
        )

        self.assertIn(
            "GC_MODE=APPLY",
            output.getvalue(),
        )

    def test_error_report_causes_nonzero_status(
        self,
    ):
        items = [
            GCReportItem(
                kind="docker",
                resource="fixture",
                classification="error",
                action="preserve",
                reason="fixture failure",
            )
        ]

        self.assertTrue(
            gc_report_has_errors(
                items
            )
        )

    def test_orphan_cleanup_never_enables_dirty_force(
        self,
    ):
        import inspect

        from aivp.maintenance import (
            gc_command,
        )

        source = inspect.getsource(
            gc_command
        )

        self.assertIn(
            "allow_dirty=False",
            source,
        )

        self.assertNotIn(
            "allow_dirty=True",
            source,
        )


if __name__ == "__main__":
    unittest.main()
