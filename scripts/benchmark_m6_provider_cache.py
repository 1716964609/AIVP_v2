from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time

from pathlib import Path

from aivp.models.base import (
    ModelRequest,
)
from aivp.models.codex_adapter import (
    CodexAdapter,
)
from aivp.panel.prompts import (
    RISK_STABLE_PREFIX,
)


MODEL = os.environ.get(
    "AIVP_M6_PROVIDER_MODEL",
    "gpt-5.6-luna",
)


class BenchmarkRuntime:
    def __init__(
        self,
        run_dir: Path,
    ):
        self.run_dir = run_dir
        self.run_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def command(
        self,
        argv,
        *,
        cwd: Path,
        timeout_seconds: int,
        log_stem: str,
        actor=None,
        check=False,
        stdin_text=None,
    ):
        cp = subprocess.run(
            [str(value) for value in argv],
            cwd=str(cwd),
            input=stdin_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            env=os.environ.copy(),
        )

        (
            self.run_dir
            / f"{log_stem}.stdout.txt"
        ).write_text(
            cp.stdout,
            encoding="utf-8",
        )

        (
            self.run_dir
            / f"{log_stem}.stderr.txt"
        ).write_text(
            cp.stderr,
            encoding="utf-8",
        )

        return cp


def make_repo(
    repo: Path,
) -> None:
    repo.mkdir()

    (
        repo / "README.md"
    ).write_text(
        (
            "# AIVP M6 Provider Cache Benchmark\n\n"
            "Read-only synthetic repository.\n"
        ),
        encoding="utf-8",
    )

    subprocess.run(
        ["git", "init", "-q"],
        cwd=str(repo),
        check=True,
    )

    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "benchmark@example.com",
        ],
        cwd=str(repo),
        check=True,
    )

    subprocess.run(
        [
            "git",
            "config",
            "user.name",
            "AIVP Benchmark",
        ],
        cwd=str(repo),
        check=True,
    )

    subprocess.run(
        ["git", "add", "."],
        cwd=str(repo),
        check=True,
    )

    subprocess.run(
        [
            "git",
            "commit",
            "-q",
            "-m",
            "benchmark fixture",
        ],
        cwd=str(repo),
        check=True,
    )


def stable_prefix() -> str:
    policy_lines = []

    for index in range(160):
        policy_lines.append(
            (
                f"REFERENCE POLICY {index:03d}: "
                "Preserve exact instruction ordering, "
                "perform no repository mutation, "
                "do not create network side effects, "
                "and return only the requested "
                "structured benchmark result."
            )
        )

    return (
        RISK_STABLE_PREFIX
        + "AIVP M6 PROVIDER CACHE "
        "REFERENCE POLICY\n\n"
        + "\n".join(policy_lines)
        + "\n\n"
    )


def main() -> int:
    output = Path(
        "docs/evidence/"
        "m6-provider-cache.json"
    )

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "ok",
            "label",
        ],
        "properties": {
            "ok": {
                "type": "boolean",
            },
            "label": {
                "type": "string",
            },
        },
    }

    prefix = stable_prefix()

    prefix_hash = hashlib.sha256(
        prefix.encode("utf-8")
    ).hexdigest()

    config = {
        "codex": {
            "binary": "codex",
            "model": MODEL,
            "reasoning_effort": "none",
            "risk_extra_args": [
                "exec",
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--config",
                'approval_policy="never"',
            ],
        }
    }

    results = []

    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)

        repo = root / "repo"
        make_repo(repo)

        runtime = BenchmarkRuntime(
            root / "run"
        )

        adapter = CodexAdapter(
            runtime,
            config,
        )

        for index, label in enumerate(
            ("A", "B"),
            start=1,
        ):
            suffix = (
                "DYNAMIC BENCHMARK SUFFIX\n"
                f"label={label}\n"
                "Do not inspect or modify repository "
                "files. Return ok=true and the exact "
                "label through the required schema."
            )

            prompt = (
                prefix
                + suffix
            )

            request = ModelRequest(
                role="risk",
                prompt=prompt,
                repo=repo,
                timeout_seconds=180,
                log_stem=(
                    f"provider-cache-{index}"
                ),
                output_schema=schema,
            )

            started = time.perf_counter()

            result = adapter.invoke(
                request
            )

            elapsed_ms = (
                time.perf_counter()
                - started
            ) * 1000

            if (
                result.raw_exit_status
                != 0
            ):
                stderr_path = (
                    runtime.run_dir
                    / (
                        f"provider-cache-"
                        f"{index}.stderr.txt"
                    )
                )

                stderr = (
                    stderr_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                    if stderr_path.exists()
                    else ""
                )

                raise RuntimeError(
                    "Provider call failed: "
                    f"{stderr[-4000:]}"
                )

            input_tokens = (
                result.input_tokens
            )

            cached_tokens = (
                result.cached_tokens
            )

            cached_ratio = None

            if (
                isinstance(
                    input_tokens,
                    int,
                )
                and input_tokens > 0
                and isinstance(
                    cached_tokens,
                    int,
                )
            ):
                cached_ratio = round(
                    (
                        cached_tokens
                        / input_tokens
                        * 100
                    ),
                    3,
                )

            results.append(
                {
                    "call": index,
                    "label": label,
                    "provider": (
                        result.provider
                    ),
                    "model": (
                        result.model
                    ),
                    "elapsed_ms": round(
                        elapsed_ms,
                        3,
                    ),
                    "input_tokens": (
                        result.input_tokens
                    ),
                    "cached_tokens": (
                        result.cached_tokens
                    ),
                    "cached_ratio_percent": (
                        cached_ratio
                    ),
                    "output_tokens": (
                        result.output_tokens
                    ),
                    "cost_estimate_usd": (
                        result
                        .cost_estimate_usd
                    ),
                    "raw_exit_status": (
                        result
                        .raw_exit_status
                    ),
                }
            )

            time.sleep(1)

    payload = {
        "version": "1.0.0",
        "benchmark": (
            "m6-provider-prompt-cache"
        ),
        "model_requested": MODEL,
        "calls": len(results),
        "stable_prefix": {
            "sha256": prefix_hash,
            "chars": len(prefix),
            "content_persisted": False,
        },
        "dynamic_suffix_changed": True,
        "results": results,
        "interpretation": {
            "provider_cache_hit_evidence": (
                (
                    results[1]
                    .get("cached_tokens")
                    or 0
                )
                > 0
            ),
            "actual_subscription_charge_measured": (
                False
            ),
            "pricing_note": (
                "Dollar cost is not computed "
                "here. Use the versioned AIVP "
                "pricing catalog or a separately "
                "documented public API pricing "
                "snapshot."
            ),
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
