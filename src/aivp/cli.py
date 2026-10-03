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
from aivp.eval.suite import (
    load_eval_suite,
    run_eval_suite,
)
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

    eval_parser = (
        subparsers.add_parser(
            "eval",
            help=(
                "run evaluation suites"
            ),
        )
    )

    eval_subparsers = (
        eval_parser.add_subparsers(
            dest="eval_command",
            required=True,
        )
    )

    eval_run_parser = (
        eval_subparsers.add_parser(
            "run",
            help=(
                "run a fixed eval suite"
            ),
        )
    )

    eval_run_parser.add_argument(
        "suite",
        type=Path,
    )

    eval_run_parser.add_argument(
        "--reports",
        type=Path,
        default=Path(
            "./reports/eval"
        ),
    )

    eval_run_parser.add_argument(
        "--state-db",
        type=Path,
        default=Path(
            "./.aivp/state.db"
        ),
    )

    eval_run_parser.add_argument(
        "--suite-run-id",
        default=None,
    )

    eval_run_parser.add_argument(
        "--yes",
        action="store_true",
        help=(
            "required for real eval runs"
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

        if args.command == "eval":
            if (
                args.eval_command
                == "run"
            ):
                if not args.yes:
                    print(
                        "ERROR: refusing real "
                        "eval run without --yes",
                        file=sys.stderr,
                    )
                    return 2

                suite = (
                    load_eval_suite(
                        args.suite
                        .expanduser()
                        .resolve()
                    )
                )

                result = run_eval_suite(
                    suite,
                    reports_root=(
                        args.reports
                    ),
                    state_db=(
                        args.state_db
                    ),
                    suite_run_id=(
                        args.suite_run_id
                    ),
                )

                print(
                    "SUITE_RUN_ID="
                    f"{result.suite_run_id}"
                )

                print(
                    "SUITE_DIR="
                    f"{result.suite_root}"
                )

                print(
                    "SUITE_OUTCOME="
                    f"{result.overall_outcome}"
                )

                return (
                    0
                    if (
                        result
                        .overall_outcome
                        == "PASS"
                    )
                    else 1
                )

            parser.error(
                "unknown eval command"
            )

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
