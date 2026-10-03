from __future__ import annotations

import datetime as dt
import json
import re
import uuid

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

from aivp.errors import AIVPError
from aivp.eval.benchmark import (
    generate_benchmark,
)
from aivp.eval.case import (
    EvalCase,
    load_eval_case,
)
from aivp.eval.regrade import (
    regrade_evaluation,
)
from aivp.eval.runner import (
    run_eval_case,
)
from aivp.structured import load_structured


EVAL_SUITE_SCHEMA_VERSION = 1
EVAL_SUITE_RUNNER_VERSION = "1.0.0"

_SUITE_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)

_SUITE_RUN_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)


class EvalSuiteError(AIVPError):
    pass


@dataclass(frozen=True)
class EvalSuite:
    schema_version: int
    suite_id: str
    description: str
    cases: Tuple[EvalCase, ...]
    source_path: Path


@dataclass(frozen=True)
class SuiteExecution:
    suite_run_id: str
    suite_root: Path
    case_count: int
    overall_outcome: str


def _now_iso() -> str:
    return (
        dt.datetime.now(
            dt.timezone.utc
        )
        .isoformat()
        .replace("+00:00", "Z")
    )


def new_suite_run_id() -> str:
    stamp = (
        dt.datetime.now(
            dt.timezone.utc
        )
        .strftime(
            "%Y%m%d-%H%M%S"
        )
    )

    suffix = uuid.uuid4().hex[:8]

    return (
        f"suite-{stamp}-{suffix}"
    )


def _validate_suite_id(
    value: str,
    *,
    field: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise EvalSuiteError(
            f"{field} must be a string"
        )

    normalized = value.strip()

    if not _SUITE_ID_RE.fullmatch(
        normalized
    ):
        raise EvalSuiteError(
            f"{field} must match "
            "[a-z0-9][a-z0-9._-]*"
        )

    return normalized


def _validate_suite_run_id(
    value: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise EvalSuiteError(
            "suite_run_id must be a string"
        )

    normalized = value.strip()

    if not _SUITE_RUN_ID_RE.fullmatch(
        normalized
    ):
        raise EvalSuiteError(
            "suite_run_id must match "
            "[a-z0-9][a-z0-9._-]*"
        )

    return normalized


def _write_json(
    path: Path,
    value: Mapping[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp = path.with_name(
        f".{path.name}.tmp"
    )

    temp.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    temp.replace(path)


def load_eval_suite(
    path: Path,
) -> EvalSuite:
    source_path = (
        path.expanduser().resolve()
    )

    raw = load_structured(
        source_path
    )

    schema_version = raw.get(
        "schema_version"
    )

    if (
        schema_version
        != EVAL_SUITE_SCHEMA_VERSION
    ):
        raise EvalSuiteError(
            "Unsupported eval suite "
            "schema_version: "
            f"{schema_version!r}; expected "
            f"{EVAL_SUITE_SCHEMA_VERSION}"
        )

    suite_id = _validate_suite_id(
        raw.get("id"),
        field="suite.id",
    )

    description = raw.get(
        "description",
        "",
    )

    if not isinstance(
        description,
        str,
    ):
        raise EvalSuiteError(
            "suite.description must be "
            "a string"
        )

    raw_cases = raw.get(
        "cases"
    )

    if (
        not isinstance(
            raw_cases,
            list,
        )
        or not raw_cases
    ):
        raise EvalSuiteError(
            "suite.cases must be a "
            "non-empty list"
        )

    case_paths = []

    for value in raw_cases:
        if (
            not isinstance(
                value,
                str,
            )
            or not value.strip()
        ):
            raise EvalSuiteError(
                "suite case references must "
                "be non-empty strings"
            )

        candidate = Path(
            value.strip()
        ).expanduser()

        if not candidate.is_absolute():
            candidate = (
                source_path.parent
                / candidate
            )

        case_paths.append(
            candidate.resolve()
        )

    if (
        len(set(case_paths))
        != len(case_paths)
    ):
        raise EvalSuiteError(
            "suite case references "
            "must be unique"
        )

    cases = tuple(
        load_eval_case(case_path)
        for case_path in case_paths
    )

    case_ids = [
        case.case_id
        for case in cases
    ]

    if (
        len(set(case_ids))
        != len(case_ids)
    ):
        raise EvalSuiteError(
            "suite case IDs must be unique"
        )

    return EvalSuite(
        schema_version=schema_version,
        suite_id=suite_id,
        description=(
            description.strip()
        ),
        cases=cases,
        source_path=source_path,
    )


def _overall_outcome(
    outcomes: Tuple[str, ...],
) -> str:
    if "ERROR" in outcomes:
        return "ERROR"

    if "FAIL" in outcomes:
        return "FAIL"

    return "PASS"


def run_eval_suite(
    suite: EvalSuite,
    *,
    reports_root: Path,
    state_db: Path,
    suite_run_id: Optional[str] = None,
) -> SuiteExecution:
    reports_root = (
        reports_root
        .expanduser()
        .resolve()
    )

    state_db = (
        state_db
        .expanduser()
        .resolve()
    )

    selected_run_id = (
        _validate_suite_run_id(
            suite_run_id
            or new_suite_run_id()
        )
    )

    suite_root = (
        reports_root
        / suite.suite_id
        / selected_run_id
    )

    if suite_root.exists():
        raise EvalSuiteError(
            "Suite output already exists: "
            f"{suite_root}"
        )

    suite_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    cases_root = (
        suite_root / "cases"
    )

    evaluations_root = (
        suite_root / "evaluations"
    )

    cases_root.mkdir()
    evaluations_root.mkdir()

    created_at = _now_iso()

    _write_json(
        suite_root
        / "suite-snapshot.json",
        {
            "schema_version": (
                suite.schema_version
            ),
            "id": suite.suite_id,
            "description": (
                suite.description
            ),
            "source_path": str(
                suite.source_path
            ),
            "cases": [
                {
                    "id": case.case_id,
                    "source_path": str(
                        case.source_path
                    ),
                    "trials": (
                        case.trials.count
                    ),
                }
                for case in suite.cases
            ],
        },
    )

    manifest_path = (
        suite_root
        / "suite-manifest.json"
    )

    _write_json(
        manifest_path,
        {
            "version": (
                EVAL_SUITE_RUNNER_VERSION
            ),
            "suite_run_id": (
                selected_run_id
            ),
            "suite_id": (
                suite.suite_id
            ),
            "status": "RUNNING",
            "created_at": created_at,
            "finished_at": None,
            "planned_cases": len(
                suite.cases
            ),
            "completed_cases": 0,
        },
    )

    case_records = []
    outcomes = []

    for index, case in enumerate(
        suite.cases,
        start=1,
    ):
        evaluation_id = (
            f"{selected_run_id}-"
            f"{index:03d}"
        )

        evaluation_root = (
            evaluations_root
            / case.case_id
            / evaluation_id
        )

        record = {
            "case_index": index,
            "case_id": case.case_id,
            "evaluation_id": (
                evaluation_id
            ),
            "evaluation_root": (
                evaluation_root
                .relative_to(
                    suite_root
                )
                .as_posix()
            ),
            "status": "RUNNING",
            "outcome": None,
            "regrade_id": None,
            "benchmark_id": None,
            "error_type": None,
        }

        try:
            run_eval_case(
                case,
                reports_root=(
                    evaluations_root
                ),
                state_db=state_db,
                evaluation_id=(
                    evaluation_id
                ),
            )

            regrade_id = (
                "regrade-001"
            )

            regrade_evaluation(
                evaluation_root=(
                    evaluation_root
                ),
                regrade_id=regrade_id,
            )

            benchmark_id = (
                "benchmark-001"
            )

            benchmark = (
                generate_benchmark(
                    evaluation_root=(
                        evaluation_root
                    ),
                    regrade_id=(
                        regrade_id
                    ),
                    benchmark_id=(
                        benchmark_id
                    ),
                )
            )

            outcome = (
                benchmark
                .overall_outcome
            )

            record.update(
                {
                    "status": (
                        "COMPLETED"
                    ),
                    "outcome": outcome,
                    "regrade_id": (
                        regrade_id
                    ),
                    "benchmark_id": (
                        benchmark_id
                    ),
                }
            )

        except Exception as exc:
            outcome = "ERROR"

            record.update(
                {
                    "status": "FAILED",
                    "outcome": "ERROR",
                    "error_type": (
                        type(exc).__name__
                    ),
                }
            )

        outcomes.append(
            outcome
        )

        case_records.append(
            dict(record)
        )

        _write_json(
            cases_root
            / (
                f"case-{index:03d}.json"
            ),
            record,
        )

    outcome_tuple = tuple(
        outcomes
    )

    overall = _overall_outcome(
        outcome_tuple
    )

    counts = Counter(
        outcome_tuple
    )

    summary = {
        "version": (
            EVAL_SUITE_RUNNER_VERSION
        ),
        "suite_id": suite.suite_id,
        "suite_run_id": (
            selected_run_id
        ),
        "case_count": len(
            suite.cases
        ),
        "overall_outcome": (
            overall
        ),
        "counts": {
            key: counts.get(
                key,
                0,
            )
            for key in (
                "PASS",
                "FAIL",
                "ERROR",
            )
        },
        "cases": case_records,
    }

    _write_json(
        suite_root
        / "suite-summary.json",
        summary,
    )

    _write_json(
        manifest_path,
        {
            "version": (
                EVAL_SUITE_RUNNER_VERSION
            ),
            "suite_run_id": (
                selected_run_id
            ),
            "suite_id": (
                suite.suite_id
            ),
            "status": "COMPLETED",
            "created_at": created_at,
            "finished_at": _now_iso(),
            "planned_cases": len(
                suite.cases
            ),
            "completed_cases": len(
                suite.cases
            ),
            "overall_outcome": (
                overall
            ),
            "summary": (
                "suite-summary.json"
            ),
        },
    )

    return SuiteExecution(
        suite_run_id=(
            selected_run_id
        ),
        suite_root=suite_root,
        case_count=len(
            suite.cases
        ),
        overall_outcome=overall,
    )
