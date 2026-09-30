from __future__ import annotations

import argparse
import sys

from pathlib import Path
from typing import Optional, Sequence

from aivp.application import (
    new_run_id,
    resume_run,
    run_new,
)
from aivp.errors import AIVPError
from aivp.structured import load_structured


VERSION = "2.0.0-dev"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aivp",
        description=(
            "AIVP v2 Coding-Agent "
            "Harness Panel"
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=VERSION,
    )

    subparsers = (
        parser.add_subparsers(
            dest="command",
            required=True,
        )
    )

    run_parser = (
        subparsers.add_parser(
            "run",
            help="start a new Harness run",
        )
    )

    run_parser.add_argument(
        "--repo",
        type=Path,
        required=True,
    )

    run_parser.add_argument(
        "--task",
        type=Path,
        required=True,
    )

    run_parser.add_argument(
        "--config",
        type=Path,
        required=True,
    )

    run_parser.add_argument(
        "--reports",
        type=Path,
        default=Path("./reports"),
    )

    run_parser.add_argument(
        "--state-db",
        type=Path,
        default=Path(
            "./.aivp/state.db"
        ),
    )

    run_parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    run_parser.add_argument(
        "--yes",
        action="store_true",
        help=(
            "required for a real run"
        ),
    )

    resume_parser = (
        subparsers.add_parser(
            "resume",
            help=(
                "resume a durable Harness run"
            ),
        )
    )

    resume_parser.add_argument(
        "run_id",
    )

    resume_parser.add_argument(
        "--state-db",
        type=Path,
        default=Path(
            "./.aivp/state.db"
        ),
    )

    return parser


def main(
    argv: Optional[
        Sequence[str]
    ] = None,
) -> int:
    parser = build_parser()

    args = parser.parse_args(
        argv
    )

    try:
        if args.command == "run":
            if (
                not args.dry_run
                and not args.yes
            ):
                print(
                    "ERROR: refusing real "
                    "run without --yes",
                    file=sys.stderr,
                )
                return 2

            task = load_structured(
                args.task
                .expanduser()
                .resolve()
            )

            config = load_structured(
                args.config
                .expanduser()
                .resolve()
            )

            run_id = new_run_id()

            print(
                f"RUN_ID={run_id}"
            )

            run_dir = run_new(
                repo=args.repo,
                task=task,
                config=config,
                reports_root=(
                    args.reports
                ),
                state_db=(
                    args.state_db
                ),
                run_id=run_id,
                dry_run=args.dry_run,
            )

            print(
                f"RUN_DIR={run_dir}"
            )

            return 0

        if args.command == "resume":
            print(
                "RESUMING="
                f"{args.run_id}"
            )

            run_dir = resume_run(
                run_id=args.run_id,
                state_db=(
                    args.state_db
                ),
            )

            print(
                f"RUN_DIR={run_dir}"
            )

            return 0

        parser.error(
            "unknown command"
        )

    except AIVPError as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1

    return 0
