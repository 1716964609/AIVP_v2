from __future__ import annotations

import datetime as dt
import json
import math
import platform
import statistics
import sys
import tempfile
import time

from pathlib import Path

from aivp.context import (
    ContextBudget,
    ContextRequest,
)
from aivp.panel.orchestrator import (
    _compile_context_with_cache,
)
from aivp.repository.git import git


ITERATIONS = 30
SOURCE_FILES = 400
TEST_FILES = 100


def _round(value: float) -> float:
    return round(value, 3)


def _p95(values):
    ordered = sorted(values)
    index = max(
        0,
        math.ceil(
            len(ordered) * 0.95
        )
        - 1,
    )
    return ordered[index]


def _write_fixture_repo(
    repo: Path,
) -> None:
    src = repo / "src"
    tests = repo / "tests"

    src.mkdir(
        parents=True
    )
    tests.mkdir(
        parents=True
    )

    for index in range(
        SOURCE_FILES
    ):
        symbol = (
            "calculate_total"
            if index
            == SOURCE_FILES - 1
            else f"helper_{index:03d}"
        )

        body = "\n".join(
            [
                f"VALUE_{n} = {n}"
                for n in range(30)
            ]
        )

        (
            src
            / f"service_{index:03d}.py"
        ).write_text(
            (
                f"{body}\n\n"
                f"def {symbol}(value):\n"
                "    total = value\n"
                "    for offset in range(20):\n"
                "        total += offset\n"
                "    return total\n"
            ),
            encoding="utf-8",
        )

    for index in range(
        TEST_FILES
    ):
        (
            tests
            / f"test_service_{index:03d}.py"
        ).write_text(
            (
                "import unittest\n\n"
                f"class Service{index:03d}Tests("
                "unittest.TestCase):\n"
                "    def test_value(self):\n"
                "        self.assertTrue(True)\n"
            ),
            encoding="utf-8",
        )

    (
        repo / "README.md"
    ).write_text(
        "Synthetic M6 cache benchmark repository.\n",
        encoding="utf-8",
    )

    git(
        repo,
        "init",
    )

    git(
        repo,
        "config",
        "user.email",
        "benchmark@example.com",
    )

    git(
        repo,
        "config",
        "user.name",
        "AIVP Benchmark",
    )

    git(
        repo,
        "add",
        ".",
    )

    git(
        repo,
        "commit",
        "-m",
        "benchmark fixture",
    )


def _measure_pair(
    *,
    request: ContextRequest,
    cache_root: Path,
):
    started = time.perf_counter()

    (
        miss_compilation,
        miss_context,
        miss_repo_map,
    ) = _compile_context_with_cache(
        request,
        cache_root=cache_root,
    )

    miss_ms = (
        time.perf_counter()
        - started
    ) * 1000

    if miss_context is None:
        raise RuntimeError(
            "Expected context cache result"
        )

    if miss_context.cache_hit:
        raise RuntimeError(
            "First compilation must miss "
            "context cache"
        )

    if (
        miss_repo_map is None
        or miss_repo_map.cache_hit
    ):
        raise RuntimeError(
            "First compilation must miss "
            "repo-map cache"
        )

    started = time.perf_counter()

    (
        hit_compilation,
        hit_context,
        hit_repo_map,
    ) = _compile_context_with_cache(
        request,
        cache_root=cache_root,
    )

    hit_ms = (
        time.perf_counter()
        - started
    ) * 1000

    if (
        hit_context is None
        or not hit_context.cache_hit
    ):
        raise RuntimeError(
            "Second compilation must hit "
            "context cache"
        )

    if hit_repo_map is not None:
        raise RuntimeError(
            "Context cache hit must skip "
            "repo-map cache"
        )

    if (
        hit_compilation
        != miss_compilation
    ):
        raise RuntimeError(
            "Cache hit changed compilation"
        )

    return miss_ms, hit_ms


def main() -> int:
    output = Path(
        "docs/evidence/"
        "m6-cache-latency.json"
    )

    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        repo = root / "repo"
        repo.mkdir()

        _write_fixture_repo(
            repo
        )

        request = ContextRequest(
            repo=repo,
            task_text=(
                "Change calculate_total in "
                "src/service_399.py while "
                "preserving existing behavior"
            ),
            budget=ContextBudget(
                max_files=20,
                max_chars=120_000,
            ),
        )

        _measure_pair(
            request=request,
            cache_root=(
                root / "warmup-cache"
            ),
        )

        misses = []
        hits = []

        for index in range(
            ITERATIONS
        ):
            miss_ms, hit_ms = (
                _measure_pair(
                    request=request,
                    cache_root=(
                        root
                        / "trials"
                        / f"{index:03d}"
                    ),
                )
            )

            misses.append(
                miss_ms
            )
            hits.append(
                hit_ms
            )

        miss_median = (
            statistics.median(
                misses
            )
        )

        hit_median = (
            statistics.median(
                hits
            )
        )

        speedup = (
            miss_median
            / hit_median
        )

        reduction = (
            (
                miss_median
                - hit_median
            )
            / miss_median
            * 100
        )

        repo_sha = git(
            repo,
            "rev-parse",
            "HEAD",
        ).stdout.strip()

        payload = {
            "version": "1.0.0",
            "benchmark": (
                "m6-context-cache-latency"
            ),
            "generated_at": (
                dt.datetime.now(
                    dt.timezone.utc
                )
                .isoformat()
            ),
            "environment": {
                "python": (
                    sys.version.split()[0]
                ),
                "platform": (
                    platform.platform()
                ),
            },
            "fixture": {
                "repo_sha": repo_sha,
                "source_files": (
                    SOURCE_FILES
                ),
                "test_files": TEST_FILES,
                "iterations": ITERATIONS,
                "max_files": 20,
                "max_chars": 120_000,
            },
            "miss_ms": {
                "median": _round(
                    miss_median
                ),
                "mean": _round(
                    statistics.mean(
                        misses
                    )
                ),
                "p95": _round(
                    _p95(
                        misses
                    )
                ),
            },
            "hit_ms": {
                "median": _round(
                    hit_median
                ),
                "mean": _round(
                    statistics.mean(
                        hits
                    )
                ),
                "p95": _round(
                    _p95(
                        hits
                    )
                ),
            },
            "median_speedup_x": (
                _round(
                    speedup
                )
            ),
            "median_latency_reduction_percent": (
                _round(
                    reduction
                )
            ),
            "semantics": {
                "miss": (
                    "context cache miss + "
                    "repo-map cache miss + "
                    "context compilation"
                ),
                "hit": (
                    "context selection cache "
                    "hit; compiler and repo-map "
                    "cache skipped"
                ),
                "model_calls": 0,
                "provider_cost_measured": False,
            },
            "samples_ms": {
                "miss": [
                    _round(value)
                    for value in misses
                ],
                "hit": [
                    _round(value)
                    for value in hits
                ],
            },
        }

        output.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        print(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
