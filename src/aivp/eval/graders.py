from __future__ import annotations

import re

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

from aivp.errors import AIVPError
from aivp.structured import load_structured


GRADE_RESULT_VERSION = "1.0.0"

_VERIFICATION_RE = re.compile(
    r"^round-(\d+)\.verification\.json$"
)


class EvalGraderError(AIVPError):
    """Invalid evaluation grading request."""


@dataclass(frozen=True)
class GradeResult:
    grader: str
    outcome: str
    passed: bool
    expected: Any
    observed: Any
    evidence: Tuple[str, ...]
    reason: Optional[str] = None


def _error_result(
    *,
    grader: str,
    expected: Any,
    evidence: Tuple[str, ...],
    reason: str,
) -> GradeResult:
    return GradeResult(
        grader=grader,
        outcome="ERROR",
        passed=False,
        expected=expected,
        observed=None,
        evidence=evidence,
        reason=reason,
    )


def _comparison_result(
    *,
    grader: str,
    expected: Any,
    observed: Any,
    evidence: Tuple[str, ...],
) -> GradeResult:
    passed = expected == observed

    return GradeResult(
        grader=grader,
        outcome=(
            "PASS"
            if passed
            else "FAIL"
        ),
        passed=passed,
        expected=expected,
        observed=observed,
        evidence=evidence,
        reason=None,
    )


def _load_json_mapping(
    path: Path,
) -> Mapping[str, Any]:
    try:
        data = load_structured(path)
    except Exception as exc:
        raise EvalGraderError(
            f"Cannot load grader evidence: {path}"
        ) from exc

    return data


def grade_expected_decision(
    *,
    run_dir: Path,
    expected: Mapping[str, Any],
    evidence_prefix: str = "",
) -> GradeResult:
    expected_status = expected.get(
        "terminal_status"
    )

    if not isinstance(
        expected_status,
        str,
    ) or not expected_status.strip():
        raise EvalGraderError(
            "expected-decision grader requires "
            "expected.terminal_status"
        )

    expected_status = (
        expected_status.strip()
    )

    status_path = (
        run_dir / "status.json"
    )

    evidence = (
        f"{evidence_prefix}status.json",
    )

    if not status_path.is_file():
        return _error_result(
            grader="expected-decision",
            expected=expected_status,
            evidence=evidence,
            reason="status.json is missing",
        )

    try:
        status = _load_json_mapping(
            status_path
        )
    except EvalGraderError:
        return _error_result(
            grader="expected-decision",
            expected=expected_status,
            evidence=evidence,
            reason="status.json is malformed",
        )

    observed = status.get("status")

    if not isinstance(observed, str):
        return _error_result(
            grader="expected-decision",
            expected=expected_status,
            evidence=evidence,
            reason=(
                "status.json does not contain "
                "a string status"
            ),
        )

    return _comparison_result(
        grader="expected-decision",
        expected=expected_status,
        observed=observed,
        evidence=evidence,
    )


def _latest_verification(
    run_dir: Path,
) -> Optional[Path]:
    candidates = []

    for path in run_dir.glob(
        "round-*.verification.json"
    ):
        match = _VERIFICATION_RE.fullmatch(
            path.name
        )

        if match is None:
            continue

        candidates.append(
            (
                int(match.group(1)),
                path,
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0]
    )

    return candidates[-1][1]


def grade_verification(
    *,
    run_dir: Path,
    expected: Mapping[str, Any],
    evidence_prefix: str = "",
) -> GradeResult:
    verification_expected = (
        expected.get("verification")
    )

    if not isinstance(
        verification_expected,
        Mapping,
    ):
        raise EvalGraderError(
            "verification grader requires "
            "expected.verification mapping"
        )

    expected_passed = (
        verification_expected.get(
            "passed"
        )
    )

    if not isinstance(
        expected_passed,
        bool,
    ):
        raise EvalGraderError(
            "verification grader requires "
            "expected.verification.passed boolean"
        )

    verification_path = (
        _latest_verification(
            run_dir
        )
    )

    if verification_path is None:
        return _error_result(
            grader="verification",
            expected=expected_passed,
            evidence=(),
            reason=(
                "No round-N.verification.json "
                "artifact exists"
            ),
        )

    evidence = (
        f"{evidence_prefix}"
        f"{verification_path.name}",
    )

    try:
        verification = (
            _load_json_mapping(
                verification_path
            )
        )
    except EvalGraderError:
        return _error_result(
            grader="verification",
            expected=expected_passed,
            evidence=evidence,
            reason=(
                "Verification artifact "
                "is malformed"
            ),
        )

    observed = verification.get(
        "passed"
    )

    if not isinstance(observed, bool):
        return _error_result(
            grader="verification",
            expected=expected_passed,
            evidence=evidence,
            reason=(
                "Verification artifact does not "
                "contain boolean passed"
            ),
        )

    return _comparison_result(
        grader="verification",
        expected=expected_passed,
        observed=observed,
        evidence=evidence,
    )


def grade_result_to_dict(
    result: GradeResult,
) -> Mapping[str, Any]:
    return {
        "version": GRADE_RESULT_VERSION,
        "grader": result.grader,
        "outcome": result.outcome,
        "passed": result.passed,
        "expected": result.expected,
        "observed": result.observed,
        "evidence": list(
            result.evidence
        ),
        "reason": result.reason,
    }


def grade_trial_from_artifacts(
    *,
    evaluation_root: Path,
    trial_id: str,
) -> Tuple[GradeResult, ...]:
    evaluation_root = (
        evaluation_root
        .expanduser()
        .resolve()
    )

    case_path = (
        evaluation_root
        / "case-snapshot.json"
    )

    trial_path = (
        evaluation_root
        / "trials"
        / f"{trial_id}.json"
    )

    if not case_path.is_file():
        raise EvalGraderError(
            "case-snapshot.json is missing"
        )

    if not trial_path.is_file():
        raise EvalGraderError(
            f"Trial manifest is missing: {trial_id}"
        )

    case_snapshot = (
        _load_json_mapping(case_path)
    )

    trial_manifest = (
        _load_json_mapping(trial_path)
    )

    expected = case_snapshot.get(
        "expected",
        {},
    )

    if not isinstance(
        expected,
        Mapping,
    ):
        raise EvalGraderError(
            "case snapshot expected field "
            "must be a mapping"
        )

    graders = case_snapshot.get(
        "graders"
    )

    if not isinstance(graders, list):
        raise EvalGraderError(
            "case snapshot graders field "
            "must be a list"
        )

    run_dir_raw = trial_manifest.get(
        "run_dir"
    )

    if not isinstance(
        run_dir_raw,
        str,
    ) or not run_dir_raw:
        raise EvalGraderError(
            "Trial manifest run_dir is invalid"
        )

    run_dir = (
        evaluation_root
        / run_dir_raw
    ).resolve()

    try:
        run_dir.relative_to(
            evaluation_root
        )
    except ValueError as exc:
        raise EvalGraderError(
            "Trial run_dir escapes "
            "evaluation root"
        ) from exc

    evidence_prefix = (
        f"{run_dir_raw.rstrip('/')}/"
    )

    results = []

    for grader in graders:
        if grader == "expected-decision":
            result = (
                grade_expected_decision(
                    run_dir=run_dir,
                    expected=expected,
                    evidence_prefix=(
                        evidence_prefix
                    ),
                )
            )

        elif grader == "verification":
            result = grade_verification(
                run_dir=run_dir,
                expected=expected,
                evidence_prefix=(
                    evidence_prefix
                ),
            )

        else:
            raise EvalGraderError(
                "Unsupported grader: "
                f"{grader}"
            )

        results.append(result)

    return tuple(results)
