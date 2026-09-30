import dataclasses
import datetime as dt
import json
import os
import shlex
import subprocess
import time

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from aivp.artifacts.io import dump_json, dump_text
from aivp.errors import (
    AIVPError,
    BudgetExceeded,
    CommandFailed,
)


@dataclasses.dataclass
class Budgets:
    max_fix_iterations: int = 2
    codex_max_calls: int = 4
    claude_max_calls: int = 3
    codex_timeout_seconds: int = 300
    claude_timeout_seconds: int = 300
    whole_run_timeout_seconds: int = 900


@dataclasses.dataclass
class Counters:
    codex_calls: int = 0
    claude_calls: int = 0
    fix_iterations: int = 0


def now_iso() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .astimezone()
        .isoformat(timespec="seconds")
    )


def quote_cmd(argv: Sequence[str]) -> str:
    return " ".join(
        shlex.quote(str(x))
        for x in argv
    )


class Runtime:
    def __init__(
        self,
        run_dir: Path,
        budgets: Budgets,
        dry_run: bool = False,
        resume: bool = False,
        counters: Optional[Counters] = None,
    ):
        self.run_dir = run_dir
        self.budgets = budgets
        self.counters = counters or Counters()
        self.started = time.monotonic()
        self.dry_run = dry_run
        self.events: List[Dict[str, Any]] = []

        if resume:
            events_path = (
                self.run_dir / "events.json"
            )

            if events_path.exists():
                try:
                    loaded = json.loads(
                        events_path.read_text(
                            encoding="utf-8"
                        )
                    )
                except (
                    OSError,
                    json.JSONDecodeError,
                ) as exc:
                    raise AIVPError(
                        "Cannot restore runtime events"
                    ) from exc

                if not isinstance(
                    loaded,
                    list,
                ):
                    raise AIVPError(
                        "Runtime events artifact "
                        "must contain a JSON list"
                    )

                self.events = loaded

    def remaining_seconds(self) -> float:
        used = time.monotonic() - self.started

        return max(
            0.0,
            self.budgets.whole_run_timeout_seconds - used,
        )

    def assert_time_budget(self) -> None:
        if self.remaining_seconds() <= 0:
            raise BudgetExceeded(
                "Whole-run time budget exceeded"
            )

    def consume(self, actor: str) -> None:
        self.assert_time_budget()

        if actor == "codex":
            if (
                self.counters.codex_calls
                >= self.budgets.codex_max_calls
            ):
                raise BudgetExceeded(
                    "Codex call budget exceeded"
                )

            self.counters.codex_calls += 1

        elif actor == "claude":
            if (
                self.counters.claude_calls
                >= self.budgets.claude_max_calls
            ):
                raise BudgetExceeded(
                    "Claude call budget exceeded"
                )

            self.counters.claude_calls += 1

        else:
            raise AIVPError(
                f"Unknown budget actor: {actor}"
            )

    def log_event(
        self,
        kind: str,
        **fields: Any,
    ) -> None:
        event = {
            "ts": now_iso(),
            "kind": kind,
            **fields,
        }

        self.events.append(event)

        dump_json(
            self.run_dir / "events.json",
            self.events,
        )

    def command(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        timeout_seconds: int,
        log_stem: str,
        stdin_text: Optional[str] = None,
        actor: Optional[str] = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        self.assert_time_budget()

        if actor:
            self.consume(actor)

        timeout = min(
            timeout_seconds,
            max(
                1,
                int(self.remaining_seconds()),
            ),
        )

        argv = [str(x) for x in argv]

        self.log_event(
            "command_start",
            actor=actor,
            command=quote_cmd(argv),
            cwd=str(cwd),
        )

        if self.dry_run:
            dump_text(
                self.run_dir
                / f"{log_stem}.dry-run.txt",
                (
                    f"$ {quote_cmd(argv)}\n"
                    f"CWD={cwd}\n"
                    f"TIMEOUT={timeout}s\n"
                ),
            )

            return subprocess.CompletedProcess(
                argv,
                0,
                stdout="[DRY RUN]\n",
                stderr="",
            )

        started = time.monotonic()

        try:
            cp = subprocess.run(
                argv,
                cwd=str(cwd),
                input=stdin_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                env=os.environ.copy(),
            )

        except subprocess.TimeoutExpired as exc:
            elapsed = (
                time.monotonic()
                - started
            )

            dump_text(
                self.run_dir
                / f"{log_stem}.stdout.txt",
                exc.stdout or "",
            )

            dump_text(
                self.run_dir
                / f"{log_stem}.stderr.txt",
                exc.stderr or "",
            )

            self.log_event(
                "command_timeout",
                command=quote_cmd(argv),
                elapsed_seconds=elapsed,
            )

            raise BudgetExceeded(
                "Command timed out after "
                f"{timeout}s: {argv[0]}"
            ) from exc

        elapsed = (
            time.monotonic()
            - started
        )

        dump_text(
            self.run_dir
            / f"{log_stem}.stdout.txt",
            cp.stdout,
        )

        dump_text(
            self.run_dir
            / f"{log_stem}.stderr.txt",
            cp.stderr,
        )

        self.log_event(
            "command_end",
            actor=actor,
            command=quote_cmd(argv),
            returncode=cp.returncode,
            elapsed_seconds=round(
                elapsed,
                3,
            ),
        )

        if check and cp.returncode != 0:
            raise CommandFailed(
                (
                    f"Command failed "
                    f"({cp.returncode}): "
                    f"{quote_cmd(argv)}"
                ),
                cp.returncode,
            )

        return cp
