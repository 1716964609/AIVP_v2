from __future__ import annotations

import json
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


def grade_risk(
    *,
    run_dir: Path,
    expected: Mapping[str, Any],
    evidence_prefix: str = "",
) -> GradeResult:
    risk_expected = expected.get("risk")

    if not isinstance(
        risk_expected,
        Mapping,
    ):
        raise EvalGraderError(
            "risk grader requires "
            "expected.risk mapping"
        )

    expected_final = risk_expected.get(
        "final"
    )

    if not isinstance(
        expected_final,
        str,
    ) or not expected_final.strip():
        raise EvalGraderError(
            "risk grader requires "
            "expected.risk.final"
        )

    normalized_expected = {
        "final": expected_final.strip()
    }

    if "human_required" in risk_expected:
        expected_human = (
            risk_expected[
                "human_required"
            ]
        )

        if not isinstance(
            expected_human,
            bool,
        ):
            raise EvalGraderError(
                "expected.risk.human_required "
                "must be boolean"
            )

        normalized_expected[
            "human_required"
        ] = expected_human

    risk_path = (
        run_dir / "aggregate-risk.json"
    )

    evidence = (
        f"{evidence_prefix}"
        "aggregate-risk.json",
    )

    if not risk_path.is_file():
        return _error_result(
            grader="risk",
            expected=normalized_expected,
            evidence=evidence,
            reason=(
                "aggregate-risk.json "
                "is missing"
            ),
        )

    try:
        risk = _load_json_mapping(
            risk_path
        )
    except EvalGraderError:
        return _error_result(
            grader="risk",
            expected=normalized_expected,
            evidence=evidence,
            reason=(
                "aggregate-risk.json "
                "is malformed"
            ),
        )

    observed_final = risk.get("final")

    if not isinstance(
        observed_final,
        str,
    ):
        return _error_result(
            grader="risk",
            expected=normalized_expected,
            evidence=evidence,
            reason=(
                "aggregate-risk.json does "
                "not contain string final"
            ),
        )

    observed = {
        "final": observed_final
    }

    if "human_required" in normalized_expected:
        observed_human = risk.get(
            "human_required"
        )

        if not isinstance(
            observed_human,
            bool,
        ):
            return _error_result(
                grader="risk",
                expected=normalized_expected,
                evidence=evidence,
                reason=(
                    "aggregate-risk.json does "
                    "not contain boolean "
                    "human_required"
                ),
            )

        observed[
            "human_required"
        ] = observed_human

    return _comparison_result(
        grader="risk",
        expected=normalized_expected,
        observed=observed,
        evidence=evidence,
    )


def _load_json_value(
    path: Path,
) -> Any:
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise EvalGraderError(
            f"Cannot load grader evidence: {path}"
        ) from exc


def _path_list(
    value: Any,
    *,
    field: str,
) -> Tuple[str, ...]:
    if not isinstance(value, list):
        raise EvalGraderError(
            f"{field} must be a list"
        )

    normalized = []

    for item in value:
        if not isinstance(
            item,
            str,
        ) or not item.strip():
            raise EvalGraderError(
                f"{field} must contain "
                "non-empty strings"
            )

        normalized.append(
            item.strip()
        )

    if len(set(normalized)) != len(
        normalized
    ):
        raise EvalGraderError(
            f"{field} must not contain "
            "duplicate paths"
        )

    return tuple(sorted(normalized))


def _non_negative_int(
    value: Any,
    *,
    field: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise EvalGraderError(
            f"{field} must be a "
            "non-negative integer"
        )

    return value


def grade_diff(
    *,
    run_dir: Path,
    expected: Mapping[str, Any],
    evidence_prefix: str = "",
) -> GradeResult:
    diff_expected = expected.get("diff")

    if not isinstance(
        diff_expected,
        Mapping,
    ):
        raise EvalGraderError(
            "diff grader requires "
            "expected.diff mapping"
        )

    allowed = {
        "changed_paths",
        "required_paths",
        "forbidden_paths",
        "max_changed_files",
        "max_diff_lines",
    }

    unknown = (
        set(diff_expected.keys())
        - allowed
    )

    if unknown:
        raise EvalGraderError(
            "Unsupported expected.diff "
            "field(s): "
            + ", ".join(sorted(unknown))
        )

    if not diff_expected:
        raise EvalGraderError(
            "expected.diff must contain "
            "at least one criterion"
        )

    normalized_expected = {}

    path_criteria = False

    for field in (
        "changed_paths",
        "required_paths",
        "forbidden_paths",
    ):
        if field in diff_expected:
            normalized_expected[field] = list(
                _path_list(
                    diff_expected[field],
                    field=(
                        f"expected.diff.{field}"
                    ),
                )
            )
            path_criteria = True

    if "max_changed_files" in diff_expected:
        normalized_expected[
            "max_changed_files"
        ] = _non_negative_int(
            diff_expected[
                "max_changed_files"
            ],
            field=(
                "expected.diff."
                "max_changed_files"
            ),
        )
        path_criteria = True

    needs_diff_text = (
        "max_diff_lines"
        in diff_expected
    )

    if needs_diff_text:
        normalized_expected[
            "max_diff_lines"
        ] = _non_negative_int(
            diff_expected[
                "max_diff_lines"
            ],
            field=(
                "expected.diff."
                "max_diff_lines"
            ),
        )

    evidence = []
    observed = {}
    failures = []

    changed_paths = None

    if path_criteria:
        changed_path_file = (
            run_dir / "changed-paths.json"
        )

        evidence.append(
            f"{evidence_prefix}"
            "changed-paths.json"
        )

        if not changed_path_file.is_file():
            return _error_result(
                grader="diff",
                expected=normalized_expected,
                evidence=tuple(evidence),
                reason=(
                    "changed-paths.json "
                    "is missing"
                ),
            )

        try:
            raw_paths = _load_json_value(
                changed_path_file
            )
            changed_paths = _path_list(
                raw_paths,
                field="changed-paths.json",
            )
        except EvalGraderError:
            return _error_result(
                grader="diff",
                expected=normalized_expected,
                evidence=tuple(evidence),
                reason=(
                    "changed-paths.json "
                    "is malformed"
                ),
            )

        observed_paths = list(
            changed_paths
        )

        observed["changed_paths"] = (
            observed_paths
        )
        observed["changed_file_count"] = (
            len(changed_paths)
        )

        if "changed_paths" in normalized_expected:
            if (
                observed_paths
                != normalized_expected[
                    "changed_paths"
                ]
            ):
                failures.append(
                    "changed path set differs"
                )

        if "required_paths" in normalized_expected:
            missing = sorted(
                set(
                    normalized_expected[
                        "required_paths"
                    ]
                )
                - set(changed_paths)
            )

            if missing:
                failures.append(
                    "required paths missing: "
                    + ", ".join(missing)
                )

        if "forbidden_paths" in normalized_expected:
            forbidden = sorted(
                set(
                    normalized_expected[
                        "forbidden_paths"
                    ]
                )
                & set(changed_paths)
            )

            if forbidden:
                failures.append(
                    "forbidden paths changed: "
                    + ", ".join(forbidden)
                )

        if "max_changed_files" in normalized_expected:
            if (
                len(changed_paths)
                > normalized_expected[
                    "max_changed_files"
                ]
            ):
                failures.append(
                    "changed file count exceeds "
                    "maximum"
                )

    if needs_diff_text:
        diff_path = (
            run_dir / "final.diff.txt"
        )

        evidence.append(
            f"{evidence_prefix}"
            "final.diff.txt"
        )

        if not diff_path.is_file():
            return _error_result(
                grader="diff",
                expected=normalized_expected,
                evidence=tuple(evidence),
                reason=(
                    "final.diff.txt is missing"
                ),
            )

        try:
            diff_text = diff_path.read_text(
                encoding="utf-8"
            )
        except OSError:
            return _error_result(
                grader="diff",
                expected=normalized_expected,
                evidence=tuple(evidence),
                reason=(
                    "final.diff.txt cannot "
                    "be read"
                ),
            )

        diff_lines = len(
            diff_text.splitlines()
        )

        observed[
            "diff_lines"
        ] = diff_lines

        if (
            diff_lines
            > normalized_expected[
                "max_diff_lines"
            ]
        ):
            failures.append(
                "diff line count exceeds "
                "maximum"
            )

    passed = not failures

    return GradeResult(
        grader="diff",
        outcome=(
            "PASS"
            if passed
            else "FAIL"
        ),
        passed=passed,
        expected=normalized_expected,
        observed=observed,
        evidence=tuple(evidence),
        reason=(
            None
            if passed
            else "; ".join(failures)
        ),
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

        elif grader == "risk":
            result = grade_risk(
                run_dir=run_dir,
                expected=expected,
                evidence_prefix=(
                    evidence_prefix
                ),
            )

        elif grader == "diff":
            result = grade_diff(
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
