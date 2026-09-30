#!/usr/bin/env python3
"""
AIVP-MVP Orchestrator v1.0

Deterministic local controller for:
  - Codex CLI: Generator / Fixer + final independent risk judge
  - Claude Code: Independent Reviewer + risk assessment
  - Local deterministic gates: test / lint / typecheck / security commands
  - Rule-based risk checks
  - Human escalation packet generation

Design constraints:
  * No third AI agent.
  * Python owns workflow, budgets, stop conditions, logs, and escalation.
  * Generator != Verifier.
  * No auto-merge and no auto-deploy.
  * Clean Git working tree required before a real run.
  * Maximum fix loops, CLI calls, and total runtime are hard budgets.

The script uses the Python standard library only for runtime.
JSON config/task files are supported natively. YAML is supported only if PyYAML
is installed.

Current CLI shapes assumed:
  Codex:
    codex exec --model <model> --sandbox workspace-write --cd <repo>
      --ephemeral --config 'approval_policy="never"' <prompt>

  Claude Code:
    claude -p <prompt> --output-format json --max-turns <n> --model <model>

Both command templates are configurable in config.json so CLI changes do not
require rewriting the orchestrator.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


VERSION = "1.0.0"
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


# ---------------------------------------------------------------------------
# Basic utilities
# ---------------------------------------------------------------------------

class AIVPError(RuntimeError):
    pass


class BudgetExceeded(AIVPError):
    pass


class CommandFailed(AIVPError):
    def __init__(self, message: str, returncode: int = 1):
        super().__init__(message)
        self.returncode = returncode


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def run_id() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def load_structured(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise AIVPError(f"File not found: {path}")
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix == ".json":
        data = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise AIVPError(
                f"{path.name} is YAML but PyYAML is not installed. "
                "Use JSON or install PyYAML."
            ) from exc
        data = yaml.safe_load(text)
    else:
        # JSON first; YAML if available.
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:
                import yaml  # type: ignore
            except ImportError as exc:
                raise AIVPError(
                    f"Cannot parse {path}. Use .json, or install PyYAML for YAML."
                ) from exc
            data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise AIVPError(f"Top-level object must be a mapping: {path}")
    return data


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dump_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def which(name: str) -> Optional[str]:
    return shutil.which(name)


def quote_cmd(argv: Sequence[str]) -> str:
    return " ".join(shlex.quote(str(x)) for x in argv)


def normalize_risk(value: Any) -> str:
    v = str(value or "").strip().lower()
    if v not in RISK_ORDER:
        return "medium"
    return v


def extract_json_object(text: str) -> Dict[str, Any]:
    """Parse plain JSON, fenced JSON, or the first JSON object in text."""
    text = text.strip()
    if not text:
        raise AIVPError("Empty JSON response")

    # Direct parse.
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Strip markdown fence.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    if fenced:
        obj = json.loads(fenced.group(1))
        if isinstance(obj, dict):
            return obj

    # First balanced-ish JSON object: try all opening braces from left to right.
    starts = [m.start() for m in re.finditer(r"\{", text)]
    decoder = json.JSONDecoder()
    for start in starts:
        try:
            obj, _ = decoder.raw_decode(text[start:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    raise AIVPError("Could not parse JSON object from model output")


# ---------------------------------------------------------------------------
# Budgets / process execution
# ---------------------------------------------------------------------------

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


class Runtime:
    def __init__(self, run_dir: Path, budgets: Budgets, dry_run: bool = False):
        self.run_dir = run_dir
        self.budgets = budgets
        self.counters = Counters()
        self.started = time.monotonic()
        self.dry_run = dry_run
        self.events: List[Dict[str, Any]] = []

    def remaining_seconds(self) -> float:
        used = time.monotonic() - self.started
        return max(0.0, self.budgets.whole_run_timeout_seconds - used)

    def assert_time_budget(self) -> None:
        if self.remaining_seconds() <= 0:
            raise BudgetExceeded("Whole-run time budget exceeded")

    def consume(self, actor: str) -> None:
        self.assert_time_budget()
        if actor == "codex":
            if self.counters.codex_calls >= self.budgets.codex_max_calls:
                raise BudgetExceeded("Codex call budget exceeded")
            self.counters.codex_calls += 1
        elif actor == "claude":
            if self.counters.claude_calls >= self.budgets.claude_max_calls:
                raise BudgetExceeded("Claude call budget exceeded")
            self.counters.claude_calls += 1
        else:
            raise AIVPError(f"Unknown budget actor: {actor}")

    def log_event(self, kind: str, **fields: Any) -> None:
        event = {"ts": now_iso(), "kind": kind, **fields}
        self.events.append(event)
        dump_json(self.run_dir / "events.json", self.events)

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

        timeout = min(timeout_seconds, max(1, int(self.remaining_seconds())))
        argv = [str(x) for x in argv]
        self.log_event("command_start", actor=actor, command=quote_cmd(argv), cwd=str(cwd))

        if self.dry_run:
            dump_text(
                self.run_dir / f"{log_stem}.dry-run.txt",
                f"$ {quote_cmd(argv)}\nCWD={cwd}\nTIMEOUT={timeout}s\n",
            )
            return subprocess.CompletedProcess(argv, 0, stdout="[DRY RUN]\n", stderr="")

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
            elapsed = time.monotonic() - started
            dump_text(self.run_dir / f"{log_stem}.stdout.txt", exc.stdout or "")
            dump_text(self.run_dir / f"{log_stem}.stderr.txt", exc.stderr or "")
            self.log_event("command_timeout", command=quote_cmd(argv), elapsed_seconds=elapsed)
            raise BudgetExceeded(f"Command timed out after {timeout}s: {argv[0]}") from exc

        elapsed = time.monotonic() - started
        dump_text(self.run_dir / f"{log_stem}.stdout.txt", cp.stdout)
        dump_text(self.run_dir / f"{log_stem}.stderr.txt", cp.stderr)
        self.log_event(
            "command_end",
            actor=actor,
            command=quote_cmd(argv),
            returncode=cp.returncode,
            elapsed_seconds=round(elapsed, 3),
        )
        if check and cp.returncode != 0:
            raise CommandFailed(f"Command failed ({cp.returncode}): {quote_cmd(argv)}", cp.returncode)
        return cp


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and cp.returncode != 0:
        raise AIVPError(f"git {' '.join(args)} failed:\n{cp.stderr}")
    return cp


def assert_git_repo(repo: Path) -> None:
    cp = git(repo, "rev-parse", "--is-inside-work-tree", check=False)
    if cp.returncode != 0 or cp.stdout.strip() != "true":
        raise AIVPError(f"Not a Git repository: {repo}")


def assert_clean_repo(repo: Path) -> None:
    status = git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout
    if status.strip():
        raise AIVPError(
            "Target repository must be clean before a real run.\n"
            "Commit/stash/remove current changes first.\n\n"
            + status
        )


def changed_paths(repo: Path) -> List[str]:
    paths = set()
    for args in [
        ("diff", "--name-only"),
        ("diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ]:
        out = git(repo, *args).stdout
        for line in out.splitlines():
            line = line.strip()
            if line:
                paths.add(line)
    return sorted(paths)


def capture_diff(repo: Path, max_untracked_bytes: int = 200_000) -> str:
    parts = []
    diff = git(repo, "diff", "--no-ext-diff", "--binary").stdout
    if diff:
        parts.append(diff)

    cached = git(repo, "diff", "--cached", "--no-ext-diff", "--binary").stdout
    if cached:
        parts.append("\n# STAGED DIFF\n" + cached)

    untracked = git(repo, "ls-files", "--others", "--exclude-standard").stdout.splitlines()
    for rel in untracked:
        p = repo / rel
        if not p.is_file():
            continue
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        if len(raw) > max_untracked_bytes or b"\x00" in raw:
            parts.append(f"\n# UNTRACKED FILE (binary/large): {rel}\n")
            continue
        text = raw.decode("utf-8", errors="replace")
        parts.append(
            f"\n# UNTRACKED FILE: {rel}\n"
            f"--- /dev/null\n+++ b/{rel}\n"
            + "\n".join("+" + line for line in text.splitlines())
            + "\n"
        )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Locking
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def repo_lock(repo: Path):
    key = hashlib.sha256(str(repo.resolve()).encode()).hexdigest()[:16]
    lock_path = Path(tempfile.gettempdir()) / f"aivp-{key}.lock"
    fd = None
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"pid={os.getpid()}\nrepo={repo}\n".encode())
        os.close(fd)
        fd = None
    except FileExistsError as exc:
        raise AIVPError(
            f"Another AIVP run appears active for this repository: {lock_path}\n"
            "If no process is active, remove the stale lock manually."
        ) from exc
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        with contextlib.suppress(FileNotFoundError):
            lock_path.unlink()


# ---------------------------------------------------------------------------
# Config / task model
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    "codex": {
        "binary": "codex",
        "model": "",
        "reasoning_effort": "low",
        "generator_extra_args": [
            "exec",
            "--sandbox", "workspace-write",
            "--ephemeral",
            "--config", "approval_policy=\"never\""
        ],
        "risk_extra_args": [
            "exec",
            "--sandbox", "read-only",
            "--ephemeral",
            "--config", "approval_policy=\"never\""
        ]
    },
    "claude": {
        "binary": "claude",
        "model": "sonnet",
        "max_turns": 2,
        "extra_args": ["-p", "--output-format", "json"]
    },
    "budgets": {
        "max_fix_iterations": 2,
        "codex_max_calls": 4,
        "claude_max_calls": 3,
        "codex_timeout_seconds": 300,
        "claude_timeout_seconds": 300,
        "whole_run_timeout_seconds": 900
    },
    "verification": [
        {
            "name": "tests",
            "argv": ["python", "-m", "pytest", "-q"],
            "timeout_seconds": 180,
            "required": True
        }
    ],
    "risk_policy": {
        "high_risk_paths": [
            "auth/**",
            "security/**",
            "db/migrations/**",
            "infra/iam/**",
            ".github/workflows/**"
        ],
        "high_risk_patterns": [
            "DROP TABLE",
            "DELETE FROM",
            "AdministratorAccess",
            "iam:PassRole"
        ]
    },
    "diff_context": {
        "max_chars": 120000
    }
}

DEFAULT_TASK: Dict[str, Any] = {
    "task": "Implement input validation for GET /users/:id.",
    "acceptance": [
        "Invalid UUID returns HTTP 400.",
        "Valid UUID keeps existing behavior.",
        "Add or update automated tests."
    ],
    "constraints": [
        "Do not change the database schema.",
        "Do not add new dependencies.",
        "Do not commit or push."
    ]
}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = json.loads(json.dumps(base))
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def budgets_from(config: Dict[str, Any]) -> Budgets:
    b = config.get("budgets", {})
    return Budgets(
        max_fix_iterations=int(b.get("max_fix_iterations", 2)),
        codex_max_calls=int(b.get("codex_max_calls", 4)),
        claude_max_calls=int(b.get("claude_max_calls", 3)),
        codex_timeout_seconds=int(b.get("codex_timeout_seconds", 300)),
        claude_timeout_seconds=int(b.get("claude_timeout_seconds", 300)),
        whole_run_timeout_seconds=int(b.get("whole_run_timeout_seconds", 900)),
    )


def render_task(task: Dict[str, Any]) -> str:
    acceptance = "\n".join(f"- {x}" for x in task.get("acceptance", []))
    constraints = "\n".join(f"- {x}" for x in task.get("constraints", []))
    return (
        f"TASK\n{task.get('task','')}\n\n"
        f"ACCEPTANCE CRITERIA\n{acceptance or '- None specified'}\n\n"
        f"CONSTRAINTS\n{constraints or '- None specified'}\n"
    )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def run_verification(
    runtime: Runtime,
    repo: Path,
    config: Dict[str, Any],
    phase: str,
) -> Dict[str, Any]:
    results = []
    all_required_pass = True
    commands = config.get("verification", [])
    if not commands:
        return {"passed": True, "results": [], "note": "No verification commands configured"}

    for i, spec in enumerate(commands):
        name = str(spec.get("name", f"gate-{i+1}"))
        argv = spec.get("argv")
        if not isinstance(argv, list) or not argv:
            raise AIVPError(f"verification[{i}].argv must be a non-empty array")
        required = bool(spec.get("required", True))
        timeout = int(spec.get("timeout_seconds", 180))
        cp = runtime.command(
            argv,
            cwd=repo,
            timeout_seconds=timeout,
            log_stem=f"{phase}.verify.{i+1}.{name}",
            check=False,
        )
        passed = cp.returncode == 0
        if required and not passed:
            all_required_pass = False
        results.append(
            {
                "name": name,
                "argv": argv,
                "required": required,
                "returncode": cp.returncode,
                "passed": passed,
                "stdout_tail": cp.stdout[-4000:],
                "stderr_tail": cp.stderr[-4000:],
            }
        )
    payload = {"passed": all_required_pass, "results": results}
    dump_json(runtime.run_dir / f"{phase}.verification.json", payload)
    return payload


def verification_summary(verification: Dict[str, Any]) -> str:
    lines = []
    for r in verification.get("results", []):
        state = "PASS" if r.get("passed") else "FAIL"
        lines.append(
            f"[{state}] {r.get('name')}\n"
            f"stdout:\n{r.get('stdout_tail','')}\n"
            f"stderr:\n{r.get('stderr_tail','')}"
        )
    return "\n\n".join(lines) or "No deterministic gates configured."


# ---------------------------------------------------------------------------
# Codex calls
# ---------------------------------------------------------------------------

def codex_base_argv(config: Dict[str, Any], *, risk: bool, repo: Path) -> List[str]:
    c = config["codex"]
    argv = [str(c.get("binary", "codex"))]
    extra_key = "risk_extra_args" if risk else "generator_extra_args"
    argv.extend(str(x) for x in c.get(extra_key, ["exec"]))
    model = str(c.get("model", "")).strip()
    if model:
        argv.extend(["--model", model])
    reasoning = str(c.get("reasoning_effort", "")).strip()
    if reasoning:
        argv.extend(["--config", f'model_reasoning_effort="{reasoning}"'])
    argv.extend(["--cd", str(repo.resolve())])
    return argv


def call_codex_edit(
    runtime: Runtime,
    repo: Path,
    config: Dict[str, Any],
    prompt: str,
    log_stem: str,
) -> None:
    argv = codex_base_argv(config, risk=False, repo=repo)
    output_file = runtime.run_dir / f"{log_stem}.last-message.txt"
    argv.extend(["-o", str(output_file), prompt])
    runtime.command(
        argv,
        cwd=repo,
        timeout_seconds=runtime.budgets.codex_timeout_seconds,
        log_stem=log_stem,
        actor="codex",
        check=True,
    )


def codex_risk_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["risk", "confidence", "reasons"],
        "properties": {
            "risk": {"type": "string", "enum": ["low", "medium", "high"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reasons": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 10
            }
        }
    }


def call_codex_risk(
    runtime: Runtime,
    repo: Path,
    config: Dict[str, Any],
    task_text: str,
    diff_text: str,
) -> Dict[str, Any]:
    schema_path = runtime.run_dir / "risk.schema.json"
    dump_json(schema_path, codex_risk_schema())
    output_file = runtime.run_dir / "codex-risk.raw.json"
    prompt = f"""You are the independent final risk judge.

Do NOT edit files. Assess the production/change risk of the proposed diff.
Return only the JSON object required by the output schema.

Risk definitions:
- low: local/reversible change with small blast radius
- medium: meaningful behavior change but bounded/reversible
- high: auth/security/permissions/data migration/destructive operation,
        large cross-service blast radius, irreversible change, or uncertainty
        that requires human judgment

{task_text}

DIFF
----
{diff_text}
"""
    argv = codex_base_argv(config, risk=True, repo=repo)
    argv.extend(["--output-schema", str(schema_path), "-o", str(output_file), prompt])
    cp = runtime.command(
        argv,
        cwd=repo,
        timeout_seconds=runtime.budgets.codex_timeout_seconds,
        log_stem="codex-risk",
        actor="codex",
        check=True,
    )
    if runtime.dry_run:
        return {"risk": "medium", "confidence": 0.0, "reasons": ["dry-run"]}
    raw = output_file.read_text(encoding="utf-8") if output_file.exists() else cp.stdout
    obj = extract_json_object(raw)
    obj["risk"] = normalize_risk(obj.get("risk"))
    dump_json(runtime.run_dir / "codex-risk.json", obj)
    return obj


# ---------------------------------------------------------------------------
# Claude review
# ---------------------------------------------------------------------------

def claude_argv(config: Dict[str, Any]) -> List[str]:
    c = config["claude"]
    argv = [str(c.get("binary", "claude"))]
    argv.extend(str(x) for x in c.get("extra_args", ["-p", "--output-format", "json"]))
    argv.extend(["--max-turns", str(int(c.get("max_turns", 2)))])
    model = str(c.get("model", "")).strip()
    if model:
        argv.extend(["--model", model])
    return argv


def normalize_findings(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity", "minor")).lower()
        if sev not in {"critical", "major", "minor", "suggestion"}:
            sev = "minor"
        out.append(
            {
                "severity": sev,
                "category": str(item.get("category", "other")),
                "file": str(item.get("file", "")),
                "line": item.get("line"),
                "reason": str(item.get("reason", "")),
                "suggested_direction": str(item.get("suggested_direction", "")),
            }
        )
    return out


def call_claude_review(
    runtime: Runtime,
    repo: Path,
    config: Dict[str, Any],
    task_text: str,
    diff_text: str,
    verification: Dict[str, Any],
    review_index: int,
) -> Dict[str, Any]:
    prompt = f"""You are an independent code reviewer. The generator is a different model.

You cannot approve based on style alone. Review the change against:
1. task and acceptance criteria
2. correctness and edge cases
3. regressions / missing tests
4. security and data safety
5. architecture / coupling / operational concerns

Return ONLY one JSON object, no Markdown:
{{
  "summary": "short summary",
  "findings": [
    {{
      "severity": "critical|major|minor|suggestion",
      "category": "correctness|security|tests|architecture|operations|other",
      "file": "path",
      "line": 123,
      "reason": "why this is a problem",
      "suggested_direction": "how to address it without writing the patch"
    }}
  ],
  "risk": "low|medium|high",
  "risk_confidence": 0.0,
  "risk_reasons": ["..."]
}}

Risk definitions:
- low: local/reversible small blast radius
- medium: meaningful behavior change but bounded/reversible
- high: auth/security/permissions/data migration/destructive operation,
        large cross-service blast radius, irreversible change, or uncertainty
        requiring human judgment

{task_text}

DETERMINISTIC VERIFICATION
--------------------------
{verification_summary(verification)}

DIFF
----
{diff_text}
"""
    dump_text(runtime.run_dir / f"claude-review-{review_index}.prompt.txt", prompt)
    argv = claude_argv(config)
    # Prompt is passed as the final argument. Reviewer does not need edit tools
    # because the diff and gate output are already in context.
    argv.append(prompt)
    cp = runtime.command(
        argv,
        cwd=repo,
        timeout_seconds=runtime.budgets.claude_timeout_seconds,
        log_stem=f"claude-review-{review_index}",
        actor="claude",
        check=True,
    )
    if runtime.dry_run:
        return {
            "summary": "dry-run",
            "findings": [],
            "risk": "medium",
            "risk_confidence": 0.0,
            "risk_reasons": ["dry-run"],
        }

    outer = extract_json_object(cp.stdout)
    # Claude --output-format json returns a wrapper with the response in "result".
    inner_text = outer.get("result") if outer.get("type") == "result" else None
    if isinstance(inner_text, str):
        obj = extract_json_object(inner_text)
        meta = {
            "duration_ms": outer.get("duration_ms"),
            "duration_api_ms": outer.get("duration_api_ms"),
            "num_turns": outer.get("num_turns"),
            "total_cost_usd": outer.get("total_cost_usd"),
            "session_id": outer.get("session_id"),
        }
    else:
        obj = outer
        meta = {}

    obj["findings"] = normalize_findings(obj.get("findings"))
    obj["risk"] = normalize_risk(obj.get("risk"))
    obj["_claude_meta"] = meta
    dump_json(runtime.run_dir / f"claude-review-{review_index}.json", obj)
    return obj


def blocking_findings(review: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        f for f in review.get("findings", [])
        if f.get("severity") in {"critical", "major"}
    ]


# ---------------------------------------------------------------------------
# Risk policy
# ---------------------------------------------------------------------------

def rule_based_risk(
    config: Dict[str, Any],
    paths: Sequence[str],
    diff_text: str,
) -> Dict[str, Any]:
    policy = config.get("risk_policy", {})
    high_paths = policy.get("high_risk_paths", [])
    high_patterns = policy.get("high_risk_patterns", [])
    reasons = []

    for path in paths:
        for pattern in high_paths:
            if fnmatch.fnmatch(path, pattern):
                reasons.append(f"path matches high-risk rule: {path} ~ {pattern}")

    for pattern in high_patterns:
        if str(pattern).lower() in diff_text.lower():
            reasons.append(f"diff contains high-risk pattern: {pattern}")

    return {
        "risk": "high" if reasons else "low",
        "reasons": reasons or ["no deterministic high-risk rule matched"],
    }


def aggregate_risk(
    rule: Dict[str, Any],
    codex: Dict[str, Any],
    claude: Dict[str, Any],
) -> Dict[str, Any]:
    risks = {
        "rule": normalize_risk(rule.get("risk")),
        "codex": normalize_risk(codex.get("risk")),
        "claude": normalize_risk(claude.get("risk")),
    }
    values = [RISK_ORDER[x] for x in risks.values()]
    disagreement = max(values) - min(values) >= 2
    any_high = any(x == "high" for x in risks.values())
    final = "high" if any_high or disagreement else ("medium" if "medium" in risks.values() else "low")
    return {
        "final": final,
        "sources": risks,
        "large_disagreement": disagreement,
        "human_required": final == "high",
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def write_metrics(runtime: Runtime, status: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metrics = {
        "version": VERSION,
        "status": status,
        "started_at": runtime.events[0]["ts"] if runtime.events else None,
        "finished_at": now_iso(),
        "elapsed_seconds": round(time.monotonic() - runtime.started, 3),
        "codex_calls": runtime.counters.codex_calls,
        "claude_calls": runtime.counters.claude_calls,
        "fix_iterations": runtime.counters.fix_iterations,
    }
    if extra:
        metrics.update(extra)
    dump_json(runtime.run_dir / "metrics.json", metrics)
    return metrics


def human_packet(
    *,
    task: Dict[str, Any],
    verification: Optional[Dict[str, Any]],
    claude_review: Optional[Dict[str, Any]],
    rule_risk: Optional[Dict[str, Any]],
    codex_risk: Optional[Dict[str, Any]],
    aggregate: Optional[Dict[str, Any]],
    paths: Sequence[str],
    reason: str,
    metrics: Dict[str, Any],
) -> str:
    findings = (claude_review or {}).get("findings", [])
    blocking = [f for f in findings if f.get("severity") in {"critical", "major"}]
    vr = verification or {}
    lines = [
        "# Human Review Required",
        "",
        f"**Escalation reason:** {reason}",
        "",
        "## Task",
        "",
        str(task.get("task", "")),
        "",
        "## Deterministic verification",
        "",
        f"Overall: {'PASS' if vr.get('passed') else 'FAIL / UNKNOWN'}",
    ]
    for r in vr.get("results", []):
        lines.append(f"- {'PASS' if r.get('passed') else 'FAIL'} — {r.get('name')}")
    lines += ["", "## Blocking AI findings", ""]
    if blocking:
        for f in blocking:
            lines.append(
                f"- **{f.get('severity','').upper()}** {f.get('file','')}"
                f"{':' + str(f.get('line')) if f.get('line') else ''} — {f.get('reason','')}"
            )
    else:
        lines.append("- None")
    lines += [
        "",
        "## Risk",
        "",
        f"- Rule engine: {(rule_risk or {}).get('risk','unknown')}",
        f"- Codex: {(codex_risk or {}).get('risk','unknown')}",
        f"- Claude: {(claude_review or {}).get('risk','unknown')}",
        f"- Aggregate: {(aggregate or {}).get('final','unknown')}",
        "",
        "## Files to inspect",
        "",
    ]
    lines += [f"- {p}" for p in paths] or ["- No changed paths detected"]
    lines += [
        "",
        "## Resource usage",
        "",
        f"- Codex calls: {metrics.get('codex_calls')}",
        f"- Claude calls: {metrics.get('claude_calls')}",
        f"- Fix iterations: {metrics.get('fix_iterations')}",
        f"- Elapsed seconds: {metrics.get('elapsed_seconds')}",
        "",
        "## Human decision",
        "",
        "- [ ] Accept change",
        "- [ ] Request another manual change",
        "- [ ] Reject / revert",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def truncate_diff(config: Dict[str, Any], diff_text: str) -> str:
    max_chars = int(config.get("diff_context", {}).get("max_chars", 120000))
    if len(diff_text) <= max_chars:
        return diff_text
    # Preserve both head and tail so file headers and final hunks survive.
    half = max_chars // 2
    return (
        diff_text[:half]
        + f"\n\n... [AIVP TRUNCATED {len(diff_text)-max_chars} CHARS] ...\n\n"
        + diff_text[-half:]
    )


def generate_prompt(task_text: str) -> str:
    return f"""You are the Generator/Fixer in a controlled code-verification experiment.

Implement the task in the current Git repository.

Rules:
- Make the smallest coherent change satisfying the task.
- Add/update tests when required.
- Do not commit or push.
- Do not change unrelated files.
- Do not modify secrets or credentials.
- Do not install new dependencies unless the task explicitly permits it.
- Stop after implementing the change; the orchestrator runs verification separately.

{task_text}
"""


def fix_prompt(
    task_text: str,
    *,
    verification: Optional[Dict[str, Any]] = None,
    review: Optional[Dict[str, Any]] = None,
) -> str:
    parts = [
        "You are the Generator/Fixer. Fix the current working tree; do not commit or push.",
        "Keep the change minimal and within the original constraints.",
        task_text,
    ]
    if verification is not None:
        parts += ["DETERMINISTIC FAILURES", verification_summary(verification)]
    if review is not None:
        parts += [
            "INDEPENDENT REVIEW FINDINGS",
            json.dumps(blocking_findings(review), ensure_ascii=False, indent=2),
        ]
    parts.append("Fix only the blocking issues, then stop. The orchestrator will re-run verification.")
    return "\n\n".join(parts)


def run_pipeline(
    *,
    repo: Path,
    task: Dict[str, Any],
    config: Dict[str, Any],
    reports_root: Path,
    dry_run: bool,
) -> Path:
    rid = run_id()
    run_dir = reports_root / f"run-{rid}"
    run_dir.mkdir(parents=True, exist_ok=False)
    runtime = Runtime(run_dir, budgets_from(config), dry_run=dry_run)
    runtime.log_event("run_start", version=VERSION, repo=str(repo), dry_run=dry_run)
    dump_json(run_dir / "effective-config.json", config)
    dump_json(run_dir / "task.json", task)

    task_text = render_task(task)
    dump_text(run_dir / "task.txt", task_text)

    verification: Optional[Dict[str, Any]] = None
    review: Optional[Dict[str, Any]] = None
    rule_risk: Optional[Dict[str, Any]] = None
    codex_risk: Optional[Dict[str, Any]] = None
    aggregate: Optional[Dict[str, Any]] = None
    escalation_reason: Optional[str] = None

    with repo_lock(repo):
        assert_git_repo(repo)
        if not dry_run:
            assert_clean_repo(repo)

        try:
            # 1. Generate
            dump_text(run_dir / "generate.prompt.txt", generate_prompt(task_text))
            call_codex_edit(
                runtime, repo, config, generate_prompt(task_text), "codex-generate"
            )

            # 2. Verify / review / fix loop
            review_index = 0
            while True:
                phase = f"round-{runtime.counters.fix_iterations}"
                verification = run_verification(runtime, repo, config, phase)

                if not verification["passed"]:
                    if runtime.counters.fix_iterations >= runtime.budgets.max_fix_iterations:
                        escalation_reason = "deterministic gates did not pass within fix budget"
                        break
                    runtime.counters.fix_iterations += 1
                    prompt = fix_prompt(task_text, verification=verification)
                    dump_text(
                        run_dir / f"codex-fix-{runtime.counters.fix_iterations}.prompt.txt",
                        prompt,
                    )
                    call_codex_edit(
                        runtime,
                        repo,
                        config,
                        prompt,
                        f"codex-fix-{runtime.counters.fix_iterations}",
                    )
                    continue

                # Deterministic gates passed: independent semantic review.
                diff_text = truncate_diff(config, capture_diff(repo))
                dump_text(run_dir / f"round-{runtime.counters.fix_iterations}.diff.txt", diff_text)

                review = call_claude_review(
                    runtime,
                    repo,
                    config,
                    task_text,
                    diff_text,
                    verification,
                    review_index,
                )
                review_index += 1
                blockers = blocking_findings(review)

                if not blockers:
                    break

                if runtime.counters.fix_iterations >= runtime.budgets.max_fix_iterations:
                    escalation_reason = "critical/major review findings remained after fix budget"
                    break

                runtime.counters.fix_iterations += 1
                prompt = fix_prompt(task_text, review=review)
                dump_text(
                    run_dir / f"codex-fix-{runtime.counters.fix_iterations}.prompt.txt",
                    prompt,
                )
                call_codex_edit(
                    runtime,
                    repo,
                    config,
                    prompt,
                    f"codex-fix-{runtime.counters.fix_iterations}",
                )

            # If we could not converge, skip extra AI risk calls and escalate.
            if escalation_reason is None:
                final_diff = truncate_diff(config, capture_diff(repo))
                paths = changed_paths(repo)
                dump_text(run_dir / "final.diff.txt", final_diff)
                dump_json(run_dir / "changed-paths.json", paths)

                rule_risk = rule_based_risk(config, paths, final_diff)
                dump_json(run_dir / "rule-risk.json", rule_risk)

                # Claude risk is intentionally bundled into the final review to
                # preserve the max-3 Claude-call budget.
                if review is None:
                    raise AIVPError("Internal error: final Claude review missing")

                codex_risk = call_codex_risk(
                    runtime, repo, config, task_text, final_diff
                )
                aggregate = aggregate_risk(rule_risk, codex_risk, review)
                dump_json(run_dir / "aggregate-risk.json", aggregate)

                if aggregate["human_required"]:
                    escalation_reason = "high risk or large model/policy disagreement"

            status = "HUMAN_REQUIRED" if escalation_reason else "AUTO_FINISHED"
            metrics = write_metrics(
                runtime,
                status,
                {
                    "changed_paths": changed_paths(repo) if not dry_run else [],
                    "final_risk": aggregate["final"] if aggregate else "unknown",
                },
            )

            if escalation_reason:
                packet = human_packet(
                    task=task,
                    verification=verification,
                    claude_review=review,
                    rule_risk=rule_risk,
                    codex_risk=codex_risk,
                    aggregate=aggregate,
                    paths=changed_paths(repo) if not dry_run else [],
                    reason=escalation_reason,
                    metrics=metrics,
                )
                dump_text(run_dir / "human-review.md", packet)

            dump_json(
                run_dir / "status.json",
                {
                    "status": status,
                    "reason": escalation_reason,
                    "metrics": metrics,
                },
            )
            runtime.log_event("run_end", status=status, reason=escalation_reason)
            return run_dir

        except BudgetExceeded as exc:
            escalation_reason = str(exc)
            metrics = write_metrics(runtime, "HUMAN_REQUIRED", {"budget_exceeded": True})
            packet = human_packet(
                task=task,
                verification=verification,
                claude_review=review,
                rule_risk=rule_risk,
                codex_risk=codex_risk,
                aggregate=aggregate,
                paths=changed_paths(repo) if not dry_run else [],
                reason=escalation_reason,
                metrics=metrics,
            )
            dump_text(run_dir / "human-review.md", packet)
            dump_json(
                run_dir / "status.json",
                {"status": "HUMAN_REQUIRED", "reason": escalation_reason, "metrics": metrics},
            )
            runtime.log_event("run_end", status="HUMAN_REQUIRED", reason=escalation_reason)
            return run_dir


# ---------------------------------------------------------------------------
# CLI / doctor / init
# ---------------------------------------------------------------------------

def write_init_files(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    cfg = dest / "aivp-config.json"
    task = dest / "task.example.json"
    if cfg.exists() or task.exists():
        raise AIVPError(
            f"Refusing to overwrite existing init files in {dest}. "
            "Move/delete them first."
        )
    dump_json(cfg, DEFAULT_CONFIG)
    dump_json(task, DEFAULT_TASK)
    print(f"Wrote: {cfg}")
    print(f"Wrote: {task}")


def doctor(config: Dict[str, Any]) -> int:
    rows = []
    for label, binary in [
        ("git", "git"),
        ("codex", str(config["codex"].get("binary", "codex"))),
        ("claude", str(config["claude"].get("binary", "claude"))),
    ]:
        path = which(binary)
        rows.append((label, binary, path or "NOT FOUND"))

    print(f"AIVP-MVP Orchestrator v{VERSION}")
    print("Doctor:")
    for label, binary, result in rows:
        print(f"  {label:8} {binary:18} -> {result}")

    missing = [label for label, _, result in rows if result == "NOT FOUND"]
    if missing:
        print("\nMissing:", ", ".join(missing))
        print("Dry-run still works; real runs require all three.")
        return 1
    print("\nCore executables found.")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="AIVP-MVP deterministic Codex + Claude verification orchestrator"
    )
    p.add_argument("--version", action="version", version=VERSION)
    p.add_argument("--init", metavar="DIR", help="write example config/task files and exit")
    p.add_argument("--doctor", action="store_true", help="check CLI availability and exit")
    p.add_argument("--repo", type=Path, help="target Git repository")
    p.add_argument("--task", type=Path, help="task JSON/YAML")
    p.add_argument("--config", type=Path, help="config JSON/YAML")
    p.add_argument(
        "--reports",
        type=Path,
        default=Path("./reports"),
        help="reports directory (preferably outside target repo)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="exercise orchestration without invoking external commands",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="required for a real run; confirms manual start",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if args.init:
        write_init_files(Path(args.init).expanduser().resolve())
        return 0

    config = DEFAULT_CONFIG
    if args.config:
        config = deep_merge(DEFAULT_CONFIG, load_structured(args.config.expanduser().resolve()))

    if args.doctor:
        return doctor(config)

    if not args.repo or not args.task:
        print("ERROR: --repo and --task are required for a run.", file=sys.stderr)
        print("Try: --init ./aivp-config  OR  --doctor", file=sys.stderr)
        return 2

    repo = args.repo.expanduser().resolve()
    task_path = args.task.expanduser().resolve()
    reports = args.reports.expanduser().resolve()

    if not repo.exists() or not repo.is_dir():
        print(f"ERROR: repository not found: {repo}", file=sys.stderr)
        return 2

    task = load_structured(task_path)

    if not args.dry_run and not args.yes:
        print(
            "Refusing real run without --yes.\n"
            "This is the manual-start safety gate. Inspect config/task first.",
            file=sys.stderr,
        )
        return 2

    if not args.dry_run:
        missing = [
            b for b in [
                "git",
                str(config["codex"].get("binary", "codex")),
                str(config["claude"].get("binary", "claude")),
            ]
            if which(b) is None
        ]
        if missing:
            print(f"ERROR: required executable(s) not found: {', '.join(missing)}", file=sys.stderr)
            return 2

    try:
        run_dir = run_pipeline(
            repo=repo,
            task=task,
            config=config,
            reports_root=reports,
            dry_run=args.dry_run,
        )
    except (AIVPError, json.JSONDecodeError) as exc:
        print(f"AIVP ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130

    status_path = run_dir / "status.json"
    status = load_structured(status_path) if status_path.exists() else {}
    print(f"\nRun directory: {run_dir}")
    print(f"Status: {status.get('status', 'UNKNOWN')}")
    if status.get("reason"):
        print(f"Reason: {status['reason']}")
    if (run_dir / "human-review.md").exists():
        print(f"Human review packet: {run_dir / 'human-review.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
