from __future__ import annotations

import datetime as dt
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from aivp.errors import AIVPError


BENCHMARK_SCHEMA_VERSION = 1
BENCHMARK_VERSION = "1.0.0"

_BENCHMARK_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
)

_REGRADE_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
)


class EvalBenchmarkError(AIVPError):
    pass


@dataclass(frozen=True)
class BenchmarkExecution:
    benchmark_id: str
    benchmark_root: Path
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


def _new_benchmark_id() -> str:
    stamp = (
        dt.datetime.now(
            dt.timezone.utc
        )
        .strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
    )

    return f"benchmark-{stamp}"


def _validate_benchmark_id(
    benchmark_id: str,
) -> str:
    if not isinstance(
        benchmark_id,
        str,
    ):
        raise EvalBenchmarkError(
            "benchmark_id must be a string"
        )

    normalized = benchmark_id.strip()

    if not _BENCHMARK_ID_RE.fullmatch(
        normalized
    ):
        raise EvalBenchmarkError(
            "Invalid benchmark_id"
        )

    return normalized


def _load_json_mapping(
    path: Path,
    *,
    required: bool = True,
) -> Optional[Mapping[str, Any]]:
    if not path.is_file():
        if required:
            raise EvalBenchmarkError(
                "Required benchmark source "
                f"is missing: {path}"
            )

        return None

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
        raise EvalBenchmarkError(
            "Cannot load benchmark source: "
            f"{path}"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise EvalBenchmarkError(
            "Benchmark source must contain "
            f"a JSON object: {path}"
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


def _safe_relative(
    *,
    root: Path,
    relative: str,
    label: str,
) -> Path:
    if not isinstance(
        relative,
        str,
    ):
        raise EvalBenchmarkError(
            f"{label} must be a string"
        )

    relative_path = Path(relative)

    if relative_path.is_absolute():
        raise EvalBenchmarkError(
            f"{label} must be relative"
        )

    resolved = (
        root / relative_path
    ).resolve()

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise EvalBenchmarkError(
            f"{label} escapes evaluation root"
        ) from exc

    return resolved


def _number(
    value: Any,
) -> Optional[float]:
    if isinstance(
        value,
        bool,
    ):
        return None

    if not isinstance(
        value,
        (int, float),
    ):
        return None

    numeric = float(value)

    if not math.isfinite(numeric):
        return None

    if numeric < 0:
        return None

    return numeric


def _integer(
    value: Any,
) -> Optional[int]:
    if isinstance(
        value,
        bool,
    ):
        return None

    if not isinstance(
        value,
        int,
    ):
        return None

    if value < 0:
        return None

    return value


def _percentile(
    values: Sequence[float],
    q: float,
) -> float:
    if not values:
        raise EvalBenchmarkError(
            "Cannot calculate percentile "
            "of empty values"
        )

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (
        (len(ordered) - 1)
        * q
    )

    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    fraction = position - lower

    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * fraction
    )


def _clean_number(
    value: float,
) -> float:
    return round(
        value,
        9,
    )


def _distribution(
    values: Sequence[float],
    *,
    missing_count: int,
) -> Mapping[str, Any]:
    clean_values = [
        _clean_number(value)
        for value in values
    ]

    if not clean_values:
        return {
            "available_count": 0,
            "missing_count": (
                missing_count
            ),
            "values": [],
            "min": None,
            "max": None,
            "mean": None,
            "p50": None,
            "p95": None,
        }

    return {
        "available_count": len(
            clean_values
        ),
        "missing_count": (
            missing_count
        ),
        "values": clean_values,
        "min": _clean_number(
            min(clean_values)
        ),
        "max": _clean_number(
            max(clean_values)
        ),
        "mean": _clean_number(
            sum(clean_values)
            / len(clean_values)
        ),
        "p50": _clean_number(
            _percentile(
                clean_values,
                0.50,
            )
        ),
        "p95": _clean_number(
            _percentile(
                clean_values,
                0.95,
            )
        ),
    }


def _categorical(
    values: Sequence[str],
    *,
    missing_count: int,
) -> Mapping[str, Any]:
    counts = Counter(values)

    return {
        "available_count": len(values),
        "missing_count": (
            missing_count
        ),
        "counts": {
            key: counts[key]
            for key in sorted(counts)
        },
    }


def _overall_outcome(
    counts: Mapping[str, int],
) -> str:
    if counts.get("ERROR", 0):
        return "ERROR"

    if counts.get("FAIL", 0):
        return "FAIL"

    return "PASS"


def generate_benchmark(
    *,
    evaluation_root: Path,
    regrade_id: str,
    benchmark_id: Optional[str] = None,
) -> BenchmarkExecution:
    evaluation_root = (
        evaluation_root
        .expanduser()
        .resolve()
    )

    if not evaluation_root.is_dir():
        raise EvalBenchmarkError(
            "Evaluation root does not exist"
        )

    evaluation_manifest = (
        _load_json_mapping(
            evaluation_root
            / "evaluation-manifest.json"
        )
    )

    if not isinstance(
        regrade_id,
        str,
    ):
        raise EvalBenchmarkError(
            "regrade_id must be a string"
        )

    regrade_id = regrade_id.strip()

    if not _REGRADE_ID_RE.fullmatch(
        regrade_id
    ):
        raise EvalBenchmarkError(
            "Invalid regrade_id"
        )

    regrade_root = _safe_relative(
        root=evaluation_root,
        relative=(
            f"regrades/{regrade_id}"
        ),
        label="regrade root",
    )

    regrade_manifest = (
        _load_json_mapping(
            regrade_root
            / "manifest.json"
        )
    )

    if (
        regrade_manifest.get("status")
        != "COMPLETED"
    ):
        raise EvalBenchmarkError(
            "Benchmark requires a "
            "COMPLETED regrade"
        )

    outputs = regrade_manifest.get(
        "trial_outputs"
    )

    if (
        not isinstance(outputs, list)
        or not outputs
        or not all(
            isinstance(item, str)
            and item
            for item in outputs
        )
    ):
        raise EvalBenchmarkError(
            "Regrade manifest has no valid "
            "trial_outputs"
        )

    if benchmark_id is None:
        benchmark_id = (
            _new_benchmark_id()
        )

    benchmark_id = (
        _validate_benchmark_id(
            benchmark_id
        )
    )

    benchmark_root = (
        evaluation_root
        / "benchmarks"
        / benchmark_id
    )

    if benchmark_root.exists():
        raise EvalBenchmarkError(
            "Benchmark output already exists: "
            f"{benchmark_id}"
        )

    benchmark_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    quality_counts = {
        "PASS": 0,
        "FAIL": 0,
        "ERROR": 0,
    }

    grader_counts = defaultdict(
        lambda: {
            "PASS": 0,
            "FAIL": 0,
            "ERROR": 0,
        }
    )

    terminal_statuses = []
    final_risks = []

    terminal_status_missing = 0
    final_risk_missing = 0

    numeric_values = {
        "elapsed_seconds": [],
        "codex_calls": [],
        "claude_calls": [],
        "fix_iterations": [],
    }

    numeric_missing = {
        key: 0
        for key in numeric_values
    }

    economics_values = {
        "input_tokens": [],
        "cached_tokens": [],
        "output_tokens": [],
        "cost_usd": [],
    }

    economics_missing = {
        key: 0
        for key in economics_values
    }

    run_summary_available = 0
    run_summary_missing = 0
    run_summary_partial = 0

    limitations = []
    trial_rows = []

    for output_name in outputs:
        regrade_output_path = (
            regrade_root
            / output_name
        ).resolve()

        try:
            regrade_output_path.relative_to(
                regrade_root
            )
        except ValueError as exc:
            raise EvalBenchmarkError(
                "Regrade trial output "
                "escapes regrade root"
            ) from exc

        regrade_output = (
            _load_json_mapping(
                regrade_output_path
            )
        )

        trial_id = (
            regrade_output.get(
                "trial_id"
            )
        )

        if not isinstance(
            trial_id,
            str,
        ):
            raise EvalBenchmarkError(
                "Regrade trial output "
                "has no trial_id"
            )

        outcome = (
            regrade_output.get(
                "overall_outcome"
            )
        )

        if outcome not in quality_counts:
            raise EvalBenchmarkError(
                "Invalid trial benchmark "
                f"outcome: {outcome}"
            )

        quality_counts[outcome] += 1

        grader_results = (
            regrade_output.get(
                "grader_results"
            )
        )

        if not isinstance(
            grader_results,
            list,
        ):
            raise EvalBenchmarkError(
                "grader_results must be "
                "a list"
            )

        for grader_result in (
            grader_results
        ):
            if not isinstance(
                grader_result,
                dict,
            ):
                raise EvalBenchmarkError(
                    "Malformed grader result"
                )

            grader = (
                grader_result.get(
                    "grader"
                )
            )

            grader_outcome = (
                grader_result.get(
                    "outcome"
                )
            )

            if (
                not isinstance(
                    grader,
                    str,
                )
                or grader_outcome
                not in quality_counts
            ):
                raise EvalBenchmarkError(
                    "Malformed grader result"
                )

            grader_counts[
                grader
            ][grader_outcome] += 1

        source_manifest_relative = (
            regrade_output.get(
                "source_trial_manifest"
            )
        )

        trial_manifest_path = (
            _safe_relative(
                root=evaluation_root,
                relative=(
                    source_manifest_relative
                ),
                label=(
                    "source trial manifest"
                ),
            )
        )

        trial_manifest = (
            _load_json_mapping(
                trial_manifest_path
            )
        )

        run_relative = (
            trial_manifest.get(
                "run_dir"
            )
        )

        run_dir = _safe_relative(
            root=evaluation_root,
            relative=run_relative,
            label="trial run_dir",
        )

        metrics = _load_json_mapping(
            run_dir / "metrics.json",
            required=False,
        )

        if metrics is None:
            limitations.append(
                f"{trial_id}: "
                "metrics.json missing"
            )

            terminal_status_missing += 1
            final_risk_missing += 1

            for key in numeric_missing:
                numeric_missing[key] += 1

        else:
            status = metrics.get(
                "status"
            )

            if isinstance(
                status,
                str,
            ) and status:
                terminal_statuses.append(
                    status
                )
            else:
                terminal_status_missing += 1

            risk = metrics.get(
                "final_risk"
            )

            if isinstance(
                risk,
                str,
            ) and risk:
                final_risks.append(
                    risk
                )
            else:
                final_risk_missing += 1

            elapsed = _number(
                metrics.get(
                    "elapsed_seconds"
                )
            )

            if elapsed is None:
                numeric_missing[
                    "elapsed_seconds"
                ] += 1
            else:
                numeric_values[
                    "elapsed_seconds"
                ].append(elapsed)

            for key in (
                "codex_calls",
                "claude_calls",
                "fix_iterations",
            ):
                value = _integer(
                    metrics.get(key)
                )

                if value is None:
                    numeric_missing[
                        key
                    ] += 1
                else:
                    numeric_values[
                        key
                    ].append(
                        float(value)
                    )

        summary = _load_json_mapping(
            run_dir
            / "run-summary.json",
            required=False,
        )

        economics_complete = False

        if summary is None:
            run_summary_missing += 1

            limitations.append(
                f"{trial_id}: "
                "run-summary.json missing; "
                "economics unavailable"
            )

            for key in economics_missing:
                economics_missing[key] += 1

        else:
            run_summary_available += 1

            model_calls = (
                summary.get(
                    "model_calls"
                )
            )
            tokens = summary.get(
                "tokens"
            )
            cost = summary.get(
                "cost"
            )

            total_calls = None

            if isinstance(
                model_calls,
                dict,
            ):
                total_calls = _integer(
                    model_calls.get(
                        "count"
                    )
                )

            complete_fields = 0

            token_specs = (
                (
                    "input_tokens",
                    "input_known_calls",
                ),
                (
                    "cached_tokens",
                    "cached_known_calls",
                ),
                (
                    "output_tokens",
                    "output_known_calls",
                ),
            )

            for (
                value_key,
                known_key,
            ) in token_specs:
                value = None
                known = None

                if isinstance(
                    tokens,
                    dict,
                ):
                    value = _integer(
                        tokens.get(
                            value_key
                        )
                    )
                    known = _integer(
                        tokens.get(
                            known_key
                        )
                    )

                if (
                    total_calls is not None
                    and known is not None
                    and known == total_calls
                    and value is not None
                ):
                    economics_values[
                        value_key
                    ].append(
                        float(value)
                    )
                    complete_fields += 1
                else:
                    economics_missing[
                        value_key
                    ] += 1

            cost_value = None
            cost_known = None
            cost_total = None

            if isinstance(
                cost,
                dict,
            ):
                cost_value = _number(
                    cost.get(
                        "total_usd"
                    )
                )
                cost_known = _integer(
                    cost.get(
                        "known_calls"
                    )
                )
                cost_total = _integer(
                    cost.get(
                        "total_calls"
                    )
                )

            if (
                total_calls is not None
                and cost_total is not None
                and cost_known is not None
                and cost_total == total_calls
                and cost_known == total_calls
                and cost_value is not None
            ):
                economics_values[
                    "cost_usd"
                ].append(
                    cost_value
                )
                complete_fields += 1
            else:
                economics_missing[
                    "cost_usd"
                ] += 1

            economics_complete = (
                complete_fields == 4
            )

            if not economics_complete:
                run_summary_partial += 1

                limitations.append(
                    f"{trial_id}: "
                    "run-summary economics "
                    "are partially known"
                )

        trial_rows.append(
            {
                "trial_id": trial_id,
                "outcome": outcome,
                "run_dir": run_relative,
                "metrics_available": (
                    metrics is not None
                ),
                "run_summary_available": (
                    summary is not None
                ),
                "economics_complete": (
                    economics_complete
                ),
            }
        )

    trial_count = len(outputs)

    pass_count = quality_counts[
        "PASS"
    ]

    report = {
        "schema_version": (
            BENCHMARK_SCHEMA_VERSION
        ),
        "benchmark_version": (
            BENCHMARK_VERSION
        ),
        "benchmark_id": benchmark_id,
        "generated_at": _now_iso(),
        "source": {
            "evaluation_id": (
                evaluation_manifest.get(
                    "evaluation_id"
                )
            ),
            "case_id": (
                evaluation_manifest.get(
                    "case_id"
                )
            ),
            "regrade_id": regrade_id,
            "regrade_manifest": (
                f"regrades/{regrade_id}/"
                "manifest.json"
            ),
        },
        "quality": {
            "trial_count": trial_count,
            "counts": quality_counts,
            "pass_rate": (
                round(
                    pass_count
                    / trial_count,
                    9,
                )
                if trial_count
                else None
            ),
            "pass_rate_denominator": (
                "all_trials"
            ),
            "by_grader": {
                grader: (
                    grader_counts[
                        grader
                    ]
                )
                for grader in sorted(
                    grader_counts
                )
            },
        },
        "categorical": {
            "terminal_status": (
                _categorical(
                    terminal_statuses,
                    missing_count=(
                        terminal_status_missing
                    ),
                )
            ),
            "final_risk": (
                _categorical(
                    final_risks,
                    missing_count=(
                        final_risk_missing
                    ),
                )
            ),
        },
        "performance": {
            key: _distribution(
                numeric_values[key],
                missing_count=(
                    numeric_missing[key]
                ),
            )
            for key in numeric_values
        },
        "economics": {
            "run_summary_coverage": {
                "available": (
                    run_summary_available
                ),
                "missing": (
                    run_summary_missing
                ),
                "partial": (
                    run_summary_partial
                ),
            },
            **{
                key: _distribution(
                    economics_values[key],
                    missing_count=(
                        economics_missing[key]
                    ),
                )
                for key in economics_values
            },
        },
        "trials": trial_rows,
        "limitations": limitations,
    }

    overall = _overall_outcome(
        quality_counts
    )

    report["overall_outcome"] = (
        overall
    )

    _write_json(
        benchmark_root
        / "benchmark.json",
        report,
    )

    return BenchmarkExecution(
        benchmark_id=benchmark_id,
        benchmark_root=(
            benchmark_root
        ),
        trial_count=trial_count,
        overall_outcome=overall,
    )
