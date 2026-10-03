from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from aivp.errors import AIVPError
from aivp.eval.graders import (
    GradeResult,
    grade_result_to_dict,
    grade_trial_from_artifacts,
)


REGRADE_SCHEMA_VERSION = 1
REGRADER_VERSION = "1.0.0"

_REGRADING_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
)

_TRIAL_RE = re.compile(
    r"^trial-(\d+)\.json$"
)


class EvalRegradeError(AIVPError):
    pass


@dataclass(frozen=True)
class RegradeExecution:
    regrade_id: str
    regrade_root: Path
    trial_count: int
    overall_outcome: str


def _now_iso() -> str:
    return (
        dt.datetime.now(
            dt.timezone.utc
        )
        .isoformat()
        .replace("+00:00", "Z")
    )


def _load_json_mapping(
    path: Path,
) -> Mapping[str, Any]:
    if not path.is_file():
        raise EvalRegradeError(
            f"Required regrade source is missing: "
            f"{path.name}"
        )

    try:
        value = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise EvalRegradeError(
            f"Cannot load regrade source: "
            f"{path.name}"
        ) from exc

    if not isinstance(value, dict):
        raise EvalRegradeError(
            f"Regrade source must contain "
            f"a JSON object: {path.name}"
        )

    return value


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


def _new_regrade_id() -> str:
    stamp = (
        dt.datetime.now(
            dt.timezone.utc
        )
        .strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
    )

    return f"regrade-{stamp}"


def _validate_regrade_id(
    regrade_id: str,
) -> str:
    if not isinstance(
        regrade_id,
        str,
    ):
        raise EvalRegradeError(
            "regrade_id must be a string"
        )

    normalized = regrade_id.strip()

    if not _REGRADING_ID_RE.fullmatch(
        normalized
    ):
        raise EvalRegradeError(
            "Invalid regrade_id"
        )

    return normalized


def _trial_manifest_paths(
    evaluation_root: Path,
) -> Sequence[Path]:
    trials_root = (
        evaluation_root / "trials"
    )

    if not trials_root.is_dir():
        raise EvalRegradeError(
            "Evaluation has no trials directory"
        )

    candidates = []

    for path in trials_root.glob(
        "trial-*.json"
    ):
        match = _TRIAL_RE.fullmatch(
            path.name
        )

        if match is None:
            raise EvalRegradeError(
                "Malformed trial manifest name: "
                f"{path.name}"
            )

        candidates.append(
            (
                int(match.group(1)),
                path,
            )
        )

    if not candidates:
        raise EvalRegradeError(
            "Evaluation contains no "
            "trial manifests"
        )

    candidates.sort(
        key=lambda item: item[0]
    )

    return tuple(
        path
        for _, path in candidates
    )


def _overall_grade_outcome(
    results: Sequence[GradeResult],
) -> str:
    outcomes = {
        result.outcome
        for result in results
    }

    if "ERROR" in outcomes:
        return "ERROR"

    if "FAIL" in outcomes:
        return "FAIL"

    return "PASS"


def _aggregate_outcome(
    outcomes: Sequence[str],
) -> str:
    if "ERROR" in outcomes:
        return "ERROR"

    if "FAIL" in outcomes:
        return "FAIL"

    return "PASS"


def regrade_evaluation(
    *,
    evaluation_root: Path,
    regrade_id: Optional[str] = None,
) -> RegradeExecution:
    evaluation_root = (
        evaluation_root
        .expanduser()
        .resolve()
    )

    if not evaluation_root.is_dir():
        raise EvalRegradeError(
            "Evaluation root does not exist"
        )

    evaluation_manifest = (
        _load_json_mapping(
            evaluation_root
            / "evaluation-manifest.json"
        )
    )

    trial_paths = (
        _trial_manifest_paths(
            evaluation_root
        )
    )

    if regrade_id is None:
        regrade_id = _new_regrade_id()

    regrade_id = _validate_regrade_id(
        regrade_id
    )

    regrades_root = (
        evaluation_root / "regrades"
    )

    regrade_root = (
        regrades_root / regrade_id
    )

    if regrade_root.exists():
        raise EvalRegradeError(
            "Regrade output already exists: "
            f"{regrade_id}"
        )

    regrade_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    started_at = _now_iso()

    initial_manifest = {
        "schema_version": (
            REGRADE_SCHEMA_VERSION
        ),
        "regrader_version": (
            REGRADER_VERSION
        ),
        "regrade_id": regrade_id,
        "status": "RUNNING",
        "started_at": started_at,
        "finished_at": None,
        "source_evaluation": {
            key: evaluation_manifest[key]
            for key in (
                "evaluation_id",
                "case_id",
                "status",
            )
            if key in evaluation_manifest
        },
        "trial_count": len(
            trial_paths
        ),
    }

    _write_json(
        regrade_root / "manifest.json",
        initial_manifest,
    )

    trial_outcomes = []
    grader_counts = {
        "PASS": 0,
        "FAIL": 0,
        "ERROR": 0,
    }

    try:
        for trial_path in trial_paths:
            trial_id = trial_path.stem

            trial_manifest = (
                _load_json_mapping(
                    trial_path
                )
            )

            source_status = (
                trial_manifest.get(
                    "execution_status"
                )
            )

            if source_status != "COMPLETED":
                trial_payload = {
                    "schema_version": (
                        REGRADE_SCHEMA_VERSION
                    ),
                    "regrader_version": (
                        REGRADER_VERSION
                    ),
                    "trial_id": trial_id,
                    "source_trial_manifest": (
                        f"trials/"
                        f"{trial_path.name}"
                    ),
                    "source_trial_status": (
                        source_status
                    ),
                    "overall_outcome": (
                        "ERROR"
                    ),
                    "passed": False,
                    "grader_results": [],
                    "reason": (
                        "Source trial did not "
                        "complete execution"
                    ),
                }

                trial_outcomes.append(
                    "ERROR"
                )

                _write_json(
                    regrade_root
                    / f"{trial_id}.json",
                    trial_payload,
                )

                continue

            results = (
                grade_trial_from_artifacts(
                    evaluation_root=(
                        evaluation_root
                    ),
                    trial_id=trial_id,
                )
            )

            if not results:
                raise EvalRegradeError(
                    "Completed trial produced "
                    "no grade results"
                )

            overall = (
                _overall_grade_outcome(
                    results
                )
            )

            for result in results:
                if (
                    result.outcome
                    not in grader_counts
                ):
                    raise EvalRegradeError(
                        "Unknown grade outcome: "
                        f"{result.outcome}"
                    )

                grader_counts[
                    result.outcome
                ] += 1

            trial_outcomes.append(
                overall
            )

            trial_payload = {
                "schema_version": (
                    REGRADE_SCHEMA_VERSION
                ),
                "regrader_version": (
                    REGRADER_VERSION
                ),
                "trial_id": trial_id,
                "source_trial_manifest": (
                    f"trials/"
                    f"{trial_path.name}"
                ),
                "source_trial_status": (
                    source_status
                ),
                "overall_outcome": (
                    overall
                ),
                "passed": (
                    overall == "PASS"
                ),
                "grader_results": [
                    dict(
                        grade_result_to_dict(
                            result
                        )
                    )
                    for result in results
                ],
                "reason": None,
            }

            _write_json(
                regrade_root
                / f"{trial_id}.json",
                trial_payload,
            )

    except Exception as exc:
        failed_manifest = dict(
            initial_manifest
        )

        failed_manifest.update(
            {
                "status": "FAILED",
                "finished_at": _now_iso(),
                "error_type": (
                    type(exc).__name__
                ),
            }
        )

        _write_json(
            regrade_root
            / "manifest.json",
            failed_manifest,
        )

        raise

    overall_outcome = (
        _aggregate_outcome(
            trial_outcomes
        )
    )

    trial_counts = {
        outcome: trial_outcomes.count(
            outcome
        )
        for outcome in (
            "PASS",
            "FAIL",
            "ERROR",
        )
    }

    final_manifest = dict(
        initial_manifest
    )

    final_manifest.update(
        {
            "status": "COMPLETED",
            "finished_at": _now_iso(),
            "overall_outcome": (
                overall_outcome
            ),
            "trial_counts": (
                trial_counts
            ),
            "grader_counts": (
                grader_counts
            ),
            "trial_outputs": [
                f"{path.stem}.json"
                for path in trial_paths
            ],
        }
    )

    _write_json(
        regrade_root / "manifest.json",
        final_manifest,
    )

    return RegradeExecution(
        regrade_id=regrade_id,
        regrade_root=regrade_root,
        trial_count=len(
            trial_paths
        ),
        overall_outcome=(
            overall_outcome
        ),
    )
