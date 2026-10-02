from __future__ import annotations

import datetime as dt
import contextlib
import time
import uuid


from pathlib import Path
from typing import Any, Dict, Optional

from aivp.artifacts.io import (
    dump_json,
    dump_text,
)
from aivp.artifacts.registry import ArtifactRegistry
from aivp.errors import (
    AIVPError,
    BudgetExceeded,
    CommandFailed,
    HumanApprovalRequired,
    PolicyDenied,
    StateIntegrityError,
)
from aivp.execution.runtime import Runtime
from aivp.models.base import (
    ModelAdapter,
    ModelRequest,
    ModelResult,
)
from aivp.models.claude import (
    blocking_findings,
    normalize_findings,
)
from aivp.models.claude_adapter import ClaudeAdapter
from aivp.models.codex import codex_risk_schema
from aivp.models.codex_adapter import CodexAdapter
from aivp.models.parsing import extract_json_object
from aivp.panel.config import budgets_from
from aivp.panel.prompts import (
    fix_prompt,
    generate_prompt,
    review_prompt,
    risk_prompt,
)
from aivp.panel.reporting import (
    human_packet,
    write_metrics,
    write_run_summary,
)
from aivp.panel.task import render_task
from aivp.policy.capability import (
    Capability,
    CapabilityRequest,
    StaticCapabilityPolicy,
    v2_default_policy,
)
from aivp.repository.diff import truncate_diff
from aivp.repository.git import (
    assert_clean_repo,
    assert_git_repo,
    capture_diff,
    changed_paths,
    repo_lock,
)
from aivp.risk.aggregate import normalize_risk
from aivp.risk.base import RiskEngine
from aivp.risk.engine import LegacyCompatibleRiskEngine
from aivp.state.durable import (
    DurableExecution,
    begin_generation,
    complete_generation,
    complete_terminal_outcome,
    complete_verification,
)
from aivp.state.resume import (
    build_resume_plan,
    validate_resume_inputs,
    validate_resume_repository,
)
from aivp.verification.base import Verifier
from aivp.verification.deterministic import (
    DeterministicVerifier,
)
from aivp.verification.diff_guard import (
    evaluate_diff_guard,
)


COMPAT_VERSION = "1.0.0"


def _run_id() -> str:
    return dt.datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )


def _write_json(
    artifacts: ArtifactRegistry,
    name: str,
    path: Path,
    data: Any,
) -> None:
    dump_json(path, data)
    artifacts.register(
        name,
        path,
    )


def _write_text(
    artifacts: ArtifactRegistry,
    name: str,
    path: Path,
    text: str,
) -> None:
    dump_text(path, text)
    artifacts.register(
        name,
        path,
    )


def _write_terminal_run_summary(
    *,
    runtime: Runtime,
    artifacts: ArtifactRegistry,
    durable: Optional[DurableExecution],
    status: str,
) -> Dict[str, Any]:
    if durable is not None:
        model_calls = (
            durable.store
            .model_calls_for_run(
                durable.run_id
            )
        )

        run_id = durable.run_id

        pricing_version = (
            durable.pricing_catalog.version
            if durable.pricing_catalog
            is not None
            else None
        )

    else:
        model_calls = []
        run_id = runtime.run_dir.name
        pricing_version = None

    summary = write_run_summary(
        runtime=runtime,
        status=status,
        run_id=run_id,
        model_calls=model_calls,
        pricing_version=pricing_version,
    )

    artifacts.register(
        "run-summary",
        runtime.run_dir
        / "run-summary.json",
    )

    return summary


def _invoke_model_call(
    *,
    adapter: ModelAdapter,
    request: ModelRequest,
    durable: Optional[DurableExecution],
    step_id: str,
    tracing=None,
) -> ModelResult:
    span_attributes = {
        "step.id": (
            f"{durable.run_id}:{step_id}"
            if durable is not None
            else step_id
        ),
        "role": request.role,
    }

    if durable is not None:
        span_attributes[
            "run.id"
        ] = durable.run_id

    span_context = (
        tracing.span(
            "model.call",
            attributes=span_attributes,
        )
        if tracing is not None
        else contextlib.nullcontext(None)
    )

    with span_context as span:
        started = time.monotonic()

        result = adapter.invoke(request)

        latency_ms = max(
            0,
            round(
                (
                    time.monotonic()
                    - started
                )
                * 1000
            ),
        )

        cost_usd = (
            result.cost_estimate_usd
        )

        if (
            cost_usd is None
            and durable is not None
            and durable.pricing_catalog
            is not None
        ):
            cost_usd = (
                durable.pricing_catalog
                .estimate_cost_usd(
                    provider=result.provider,
                    model=result.model,
                    input_tokens=(
                        result.input_tokens
                    ),
                    cached_tokens=(
                        result.cached_tokens
                    ),
                    output_tokens=(
                        result.output_tokens
                    ),
                )
            )

        call_status = (
            "SUCCEEDED"
            if result.raw_exit_status == 0
            else "FAILED"
        )

        if durable is not None:
            durable.store.record_model_call(
                call_id=str(uuid.uuid4()),
                run_id=durable.run_id,
                step_id=(
                    f"{durable.run_id}:"
                    f"{step_id}"
                ),
                provider=result.provider,
                model=result.model,
                input_tokens=(
                    result.input_tokens
                ),
                cached_tokens=(
                    result.cached_tokens
                ),
                output_tokens=(
                    result.output_tokens
                ),
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                status=call_status,
            )

        if span is not None:
            span.set_attribute(
                "provider",
                result.provider,
            )
            span.set_attribute(
                "model",
                result.model,
            )
            span.set_attribute(
                "status",
                call_status,
            )
            span.set_attribute(
                "latency_ms",
                latency_ms,
            )

            if (
                result.input_tokens
                is not None
            ):
                span.set_attribute(
                    "input_tokens",
                    result.input_tokens,
                )

            if (
                result.cached_tokens
                is not None
            ):
                span.set_attribute(
                    "cached_tokens",
                    result.cached_tokens,
                )

            if (
                result.output_tokens
                is not None
            ):
                span.set_attribute(
                    "output_tokens",
                    result.output_tokens,
                )

            if cost_usd is not None:
                span.set_attribute(
                    "cost_usd",
                    cost_usd,
                )

        if result.raw_exit_status != 0:
            raise CommandFailed(
                (
                    "Model call failed "
                    f"({result.raw_exit_status}): "
                    f"{result.provider}"
                ),
                result.raw_exit_status,
            )

        return result

def _invoke_edit(
    *,
    adapter: ModelAdapter,
    runtime: Runtime,
    repo: Path,
    prompt: str,
    log_stem: str,
    role: str,
    policy: StaticCapabilityPolicy,
    durable: Optional[DurableExecution] = None,
) -> ModelResult:
    policy.authorize(
        CapabilityRequest(
            capability=(
                Capability.C1_LOCAL_MUTATE
            ),
            actor="codex",
            action=role,
            target=str(repo),
        )
    )

    return _invoke_model_call(
        adapter=adapter,
        request=ModelRequest(
            role=role,
            prompt=prompt,
            repo=repo,
            timeout_seconds=(
                runtime.budgets
                .codex_timeout_seconds
            ),
            log_stem=log_stem,
        ),
        durable=durable,
        step_id=log_stem,
        tracing=runtime.tracing,
    )


def _invoke_review(
    *,
    adapter: ModelAdapter,
    runtime: Runtime,
    artifacts: ArtifactRegistry,
    repo: Path,
    task_text: str,
    diff_text: str,
    verification: Dict[str, Any],
    review_index: int,
    policy: StaticCapabilityPolicy,
    durable: Optional[DurableExecution] = None,
) -> Dict[str, Any]:
    policy.authorize(
        CapabilityRequest(
            capability=(
                Capability.C0_OBSERVE
            ),
            actor="claude",
            action="review",
            target=str(repo),
        )
    )

    prompt = review_prompt(
        task_text,
        diff_text,
        verification,
    )

    prompt_path = (
        runtime.run_dir
        / f"claude-review-{review_index}.prompt.txt"
    )

    _write_text(
        artifacts,
        f"claude-review-{review_index}-prompt",
        prompt_path,
        prompt,
    )

    result = _invoke_model_call(
        adapter=adapter,
        request=ModelRequest(
            role="reviewer",
            prompt=prompt,
            repo=repo,
            timeout_seconds=(
                runtime.budgets
                .claude_timeout_seconds
            ),
            log_stem=(
                f"claude-review-{review_index}"
            ),
        ),
        durable=durable,
        step_id=(
            f"claude-review-{review_index}"
        ),
        tracing=runtime.tracing,
    )

    if runtime.dry_run:
        return {
            "summary": "dry-run",
            "findings": [],
            "risk": "medium",
            "risk_confidence": 0.0,
            "risk_reasons": [
                "dry-run"
            ],
        }

    obj = extract_json_object(
        result.last_message or ""
    )

    obj["findings"] = normalize_findings(
        obj.get("findings")
    )

    obj["risk"] = normalize_risk(
        obj.get("risk")
    )

    obj["_claude_meta"] = dict(
        result.raw_metadata
    )

    path = (
        runtime.run_dir
        / f"claude-review-{review_index}.json"
    )

    _write_json(
        artifacts,
        f"claude-review-{review_index}",
        path,
        obj,
    )

    return obj


def _invoke_risk(
    *,
    adapter: ModelAdapter,
    runtime: Runtime,
    artifacts: ArtifactRegistry,
    repo: Path,
    task_text: str,
    diff_text: str,
    policy: StaticCapabilityPolicy,
    durable: Optional[DurableExecution] = None,
) -> Dict[str, Any]:
    policy.authorize(
        CapabilityRequest(
            capability=(
                Capability.C0_OBSERVE
            ),
            actor="codex",
            action="risk",
            target=str(repo),
        )
    )

    result = _invoke_model_call(
        adapter=adapter,
        request=ModelRequest(
            role="risk",
            prompt=risk_prompt(
                task_text,
                diff_text,
            ),
            repo=repo,
            timeout_seconds=(
                runtime.budgets
                .codex_timeout_seconds
            ),
            log_stem="codex-risk",
            output_schema=(
                codex_risk_schema()
            ),
        ),
        durable=durable,
        step_id="codex-risk",
        tracing=runtime.tracing,
    )

    if runtime.dry_run:
        return {
            "risk": "medium",
            "confidence": 0.0,
            "reasons": [
                "dry-run"
            ],
        }

    obj = extract_json_object(
        result.last_message or ""
    )

    obj["risk"] = normalize_risk(
        obj.get("risk")
    )

    path = (
        runtime.run_dir
        / "codex-risk.json"
    )

    _write_json(
        artifacts,
        "codex-risk",
        path,
        obj,
    )

    return obj


def execute_panel(
    *,
    runtime: Runtime,
    repo: Path,
    task: Dict[str, Any],
    config: Dict[str, Any],
    generator: ModelAdapter,
    reviewer: ModelAdapter,
    risk_judge: ModelAdapter,
    verifier: Verifier,
    risk_engine: RiskEngine,
    artifacts: ArtifactRegistry,
    canonical_repo: Optional[Path] = None,
    durable: Optional[
        DurableExecution
    ] = None,
    policy: Optional[
        StaticCapabilityPolicy
    ] = None,
) -> Path:
    run_dir = runtime.run_dir

    if policy is None:
        policy = v2_default_policy()

    execution_repo = (
        repo.expanduser().resolve()
    )

    canonical_repo = (
        canonical_repo
        .expanduser()
        .resolve()
        if canonical_repo is not None
        else execution_repo
    )

    repo = execution_repo

    is_resume = (
        durable is not None
        and durable.is_resume
    )

    runtime.log_event(
        (
            "run_resume"
            if is_resume
            else "run_start"
        ),
        version=COMPAT_VERSION,
        isolated_worktree=(repo != canonical_repo),
        dry_run=runtime.dry_run,
    )

    _write_json(
        artifacts,
        "effective-config",
        run_dir / "effective-config.json",
        config,
    )

    _write_json(
        artifacts,
        "task-json",
        run_dir / "task.json",
        task,
    )

    task_text = render_task(
        task
    )

    _write_text(
        artifacts,
        "task-text",
        run_dir / "task.txt",
        task_text,
    )

    verification: Optional[
        Dict[str, Any]
    ] = None

    review: Optional[
        Dict[str, Any]
    ] = None

    rule_risk: Optional[
        Dict[str, Any]
    ] = None

    codex_risk: Optional[
        Dict[str, Any]
    ] = None

    aggregate: Optional[
        Dict[str, Any]
    ] = None

    escalation_reason: Optional[
        str
    ] = None

    with repo_lock(canonical_repo):
        assert_git_repo(
            canonical_repo
        )

        if repo != canonical_repo:
            assert_git_repo(repo)

        resume_plan = None

        if not runtime.dry_run:
            if is_resume:
                assert durable is not None
                assert (
                    durable.resume_checkpoint
                    is not None
                )

                validate_resume_repository(
                    repo=repo,
                    checkpoint=(
                        durable.resume_checkpoint
                    ),
                )

                validate_resume_inputs(
                    task=task,
                    config=config,
                    checkpoint=(
                        durable.resume_checkpoint
                    ),
                )

                resume_plan = build_resume_plan(
                    run_id=durable.run_id,
                    checkpoint=(
                        durable.resume_checkpoint
                    ),
                    artifact_records=list(
                        durable.store
                        .artifacts_for_run(
                            durable.run_id
                        )
                    ),
                )
            else:
                assert_clean_repo(
                    canonical_repo
                )

        try:
            if resume_plan is None:
                initial_prompt = (
                    generate_prompt(
                        task_text
                    )
                )

                _write_text(
                    artifacts,
                    "generate-prompt",
                    run_dir
                    / "generate.prompt.txt",
                    initial_prompt,
                )

                base_sha = None

                if durable is not None:
                    base_sha = (
                        begin_generation(
                            durable=durable,
                            repo=repo,
                        )
                    )

                generation_result = (
                    _invoke_edit(
                        adapter=generator,
                        runtime=runtime,
                        repo=repo,
                        prompt=initial_prompt,
                        log_stem=(
                            "codex-generate"
                        ),
                        role="generator",
                        policy=policy,
                        durable=durable,
                    )
                )

                if durable is not None:
                    assert base_sha is not None

                    complete_generation(
                        durable=durable,
                        runtime=runtime,
                        repo=repo,
                        prompt=initial_prompt,
                        task=task,
                        config=config,
                        model_result=(
                            generation_result
                        ),
                        base_sha=base_sha,
                    )

            else:
                if (
                    resume_plan.next_state
                    not in {
                        "VERIFYING",
                        "REVIEWING",
                    }
                ):
                    raise AIVPError(
                        "Unsupported durable "
                        "resume state"
                    )

            skip_verification_once = False

            if (
                resume_plan is not None
                and resume_plan.next_state
                == "REVIEWING"
            ):
                assert durable is not None
                assert (
                    durable.resume_checkpoint
                    is not None
                )

                restored = (
                    durable.resume_checkpoint
                    .get("verification")
                )

                if (
                    not isinstance(
                        restored,
                        dict,
                    )
                    or not restored.get(
                        "passed"
                    )
                ):
                    raise StateIntegrityError(
                        "VERIFIED checkpoint "
                        "does not contain a "
                        "valid successful "
                        "verification result"
                    )

                verification = dict(
                    restored
                )

                skip_verification_once = True

            review_index = 0

            while True:
                phase = (
                    "round-"
                    f"{runtime.counters.fix_iterations}"
                )

                if skip_verification_once:
                    skip_verification_once = False
                else:
                    diff_guard = (
                        evaluate_diff_guard(
                            repo,
                            config,
                        )
                    )

                    _write_json(
                        artifacts,
                        f"{phase}-diff-guard",
                        run_dir
                        / f"{phase}.diff-guard.json",
                        diff_guard,
                    )

                    if not diff_guard["passed"]:
                        verification = {
                            "passed": False,
                            "results": [
                                {
                                    "name": (
                                        "diff-guard"
                                    ),
                                    "argv": [],
                                    "required": True,
                                    "returncode": 1,
                                    "passed": False,
                                    "stdout_tail": "",
                                    "stderr_tail": (
                                        "\n".join(
                                            diff_guard[
                                                "violations"
                                            ]
                                        )
                                    ),
                                }
                            ],
                            "diff_guard": (
                                diff_guard
                            ),
                        }

                    else:
                        verification = (
                            verifier.verify(
                                repo=repo,
                                config=config,
                                phase=phase,
                            )
                        )

                        if (
                            verification["passed"]
                            and durable is not None
                        ):
                            complete_verification(
                                durable=durable,
                                runtime=runtime,
                                repo=repo,
                                task=task,
                                config=config,
                                verification=(
                                    verification
                                ),
                            )

                if not verification[
                    "passed"
                ]:
                    if (
                        runtime.counters
                        .fix_iterations
                        >= runtime.budgets
                        .max_fix_iterations
                    ):
                        diff_guard_result = (
                            verification.get(
                                "diff_guard"
                            )
                        )

                        if diff_guard_result:
                            violations = (
                                diff_guard_result.get(
                                    "violations",
                                    [],
                                )
                            )

                            escalation_reason = (
                                "diff guard blocked "
                                "change"
                            )

                            if violations:
                                escalation_reason += (
                                    ": "
                                    + "; ".join(
                                        str(value)
                                        for value
                                        in violations
                                    )
                                )

                        else:
                            escalation_reason = (
                                "deterministic gates "
                                "did not pass within "
                                "fix budget"
                            )

                        break

                    runtime.counters.fix_iterations += 1

                    prompt = fix_prompt(
                        task_text,
                        verification=verification,
                    )

                    stem = (
                        "codex-fix-"
                        f"{runtime.counters.fix_iterations}"
                    )

                    _write_text(
                        artifacts,
                        f"{stem}-prompt",
                        run_dir
                        / f"{stem}.prompt.txt",
                        prompt,
                    )

                    _invoke_edit(
                        adapter=generator,
                        runtime=runtime,
                        repo=repo,
                        prompt=prompt,
                        log_stem=stem,
                        role="fixer",
                        policy=policy,
                        durable=durable,
                    )

                    continue

                diff_text = truncate_diff(
                    config,
                    capture_diff(repo),
                )

                _write_text(
                    artifacts,
                    f"{phase}-diff",
                    run_dir
                    / f"{phase}.diff.txt",
                    diff_text,
                )

                review = _invoke_review(
                    adapter=reviewer,
                    runtime=runtime,
                    artifacts=artifacts,
                    repo=repo,
                    task_text=task_text,
                    diff_text=diff_text,
                    verification=verification,
                    review_index=review_index,
                    policy=policy,
                    durable=durable,
                )

                review_index += 1

                blockers = blocking_findings(
                    review
                )

                if not blockers:
                    break

                if (
                    runtime.counters
                    .fix_iterations
                    >= runtime.budgets
                    .max_fix_iterations
                ):
                    escalation_reason = (
                        "critical/major review "
                        "findings remained after "
                        "fix budget"
                    )
                    break

                runtime.counters.fix_iterations += 1

                prompt = fix_prompt(
                    task_text,
                    review=review,
                )

                stem = (
                    "codex-fix-"
                    f"{runtime.counters.fix_iterations}"
                )

                _write_text(
                    artifacts,
                    f"{stem}-prompt",
                    run_dir
                    / f"{stem}.prompt.txt",
                    prompt,
                )

                _invoke_edit(
                    adapter=generator,
                    runtime=runtime,
                    repo=repo,
                    prompt=prompt,
                    log_stem=stem,
                    role="fixer",
                    policy=policy,
                    durable=durable,
                )

            if escalation_reason is None:
                final_diff = truncate_diff(
                    config,
                    capture_diff(repo),
                )

                paths = changed_paths(
                    repo
                )

                _write_text(
                    artifacts,
                    "final-diff",
                    run_dir
                    / "final.diff.txt",
                    final_diff,
                )

                _write_json(
                    artifacts,
                    "changed-paths",
                    run_dir
                    / "changed-paths.json",
                    paths,
                )

                if review is None:
                    raise AIVPError(
                        "Internal error: "
                        "final Claude review missing"
                    )

                codex_risk = _invoke_risk(
                    adapter=risk_judge,
                    runtime=runtime,
                    artifacts=artifacts,
                    repo=repo,
                    task_text=task_text,
                    diff_text=final_diff,
                    policy=policy,
                    durable=durable,
                )

                assessed = (
                    risk_engine.assess(
                        config=config,
                        paths=paths,
                        diff_text=final_diff,
                        codex_risk=codex_risk,
                        claude_review=review,
                    )
                )

                rule_risk = assessed[
                    "rule"
                ]

                aggregate = assessed[
                    "aggregate"
                ]

                _write_json(
                    artifacts,
                    "rule-risk",
                    run_dir
                    / "rule-risk.json",
                    rule_risk,
                )

                _write_json(
                    artifacts,
                    "aggregate-risk",
                    run_dir
                    / "aggregate-risk.json",
                    aggregate,
                )

                if aggregate[
                    "human_required"
                ]:
                    escalation_reason = (
                        "high risk or large "
                        "model/policy disagreement"
                    )

            status = (
                "HUMAN_REQUIRED"
                if escalation_reason
                else "AUTO_FINISHED"
            )

            metrics = write_metrics(
                runtime,
                status,
                {
                    "changed_paths": (
                        changed_paths(repo)
                        if not runtime.dry_run
                        else []
                    ),
                    "final_risk": (
                        aggregate["final"]
                        if aggregate
                        else "unknown"
                    ),
                },
            )

            artifacts.register(
                "metrics",
                run_dir / "metrics.json",
            )

            if escalation_reason:
                packet = human_packet(
                    task=task,
                    verification=verification,
                    claude_review=review,
                    rule_risk=rule_risk,
                    codex_risk=codex_risk,
                    aggregate=aggregate,
                    paths=(
                        changed_paths(repo)
                        if not runtime.dry_run
                        else []
                    ),
                    reason=escalation_reason,
                    metrics=metrics,
                )

                _write_text(
                    artifacts,
                    "human-review",
                    run_dir
                    / "human-review.md",
                    packet,
                )

            status_payload = {
                "status": status,
                "reason": escalation_reason,
                "metrics": metrics,
            }

            _write_json(
                artifacts,
                "status",
                run_dir / "status.json",
                status_payload,
            )

            runtime.log_event(
                "run_end",
                status=status,
            )

            _write_terminal_run_summary(
                runtime=runtime,
                artifacts=artifacts,
                durable=durable,
                status=status,
            )

            return run_dir

        except HumanApprovalRequired as exc:
            escalation_reason = str(exc)

            if durable is not None:
                complete_terminal_outcome(
                    durable=durable,
                    runtime=runtime,
                    repo=repo,
                    task=task,
                    config=config,
                    state="HUMAN_REQUIRED",
                    reason=escalation_reason,
                )

            metrics = write_metrics(
                runtime,
                "HUMAN_REQUIRED",
                {
                    "policy_human_required": True
                },
            )

            artifacts.register(
                "metrics",
                run_dir / "metrics.json",
            )

            packet = human_packet(
                task=task,
                verification=verification,
                claude_review=review,
                rule_risk=rule_risk,
                codex_risk=codex_risk,
                aggregate=aggregate,
                paths=(
                    changed_paths(repo)
                    if not runtime.dry_run
                    else []
                ),
                reason=escalation_reason,
                metrics=metrics,
            )

            _write_text(
                artifacts,
                "human-review",
                run_dir / "human-review.md",
                packet,
            )

            _write_json(
                artifacts,
                "status",
                run_dir / "status.json",
                {
                    "status": "HUMAN_REQUIRED",
                    "reason": escalation_reason,
                    "metrics": metrics,
                },
            )

            runtime.log_event(
                "run_end",
                status="HUMAN_REQUIRED",
            )

            _write_terminal_run_summary(
                runtime=runtime,
                artifacts=artifacts,
                durable=durable,
                status="HUMAN_REQUIRED",
            )

            return run_dir

        except PolicyDenied as exc:
            escalation_reason = str(exc)

            if durable is not None:
                complete_terminal_outcome(
                    durable=durable,
                    runtime=runtime,
                    repo=repo,
                    task=task,
                    config=config,
                    state="DENIED",
                    reason=escalation_reason,
                )

            metrics = write_metrics(
                runtime,
                "DENIED",
                {
                    "policy_denied": True
                },
            )

            artifacts.register(
                "metrics",
                run_dir / "metrics.json",
            )

            _write_json(
                artifacts,
                "status",
                run_dir / "status.json",
                {
                    "status": "DENIED",
                    "reason": escalation_reason,
                    "metrics": metrics,
                },
            )

            runtime.log_event(
                "run_end",
                status="DENIED",
            )

            _write_terminal_run_summary(
                runtime=runtime,
                artifacts=artifacts,
                durable=durable,
                status="DENIED",
            )

            return run_dir

        except CommandFailed as exc:
            escalation_reason = str(
                exc
            )

            if durable is not None:
                complete_terminal_outcome(
                    durable=durable,
                    runtime=runtime,
                    repo=repo,
                    task=task,
                    config=config,
                    state="HUMAN_REQUIRED",
                    reason=escalation_reason,
                )

            metrics = write_metrics(
                runtime,
                "HUMAN_REQUIRED",
                {
                    "model_call_failed": True,
                    "model_returncode": (
                        exc.returncode
                    ),
                },
            )

            artifacts.register(
                "metrics",
                run_dir / "metrics.json",
            )

            packet = human_packet(
                task=task,
                verification=verification,
                claude_review=review,
                rule_risk=rule_risk,
                codex_risk=codex_risk,
                aggregate=aggregate,
                paths=(
                    changed_paths(repo)
                    if not runtime.dry_run
                    else []
                ),
                reason=escalation_reason,
                metrics=metrics,
            )

            _write_text(
                artifacts,
                "human-review",
                run_dir / "human-review.md",
                packet,
            )

            _write_json(
                artifacts,
                "status",
                run_dir / "status.json",
                {
                    "status": "HUMAN_REQUIRED",
                    "reason": escalation_reason,
                    "metrics": metrics,
                },
            )

            runtime.log_event(
                "run_end",
                status="HUMAN_REQUIRED",
            )

            _write_terminal_run_summary(
                runtime=runtime,
                artifacts=artifacts,
                durable=durable,
                status="HUMAN_REQUIRED",
            )

            return run_dir

        except BudgetExceeded as exc:
            escalation_reason = str(
                exc
            )

            metrics = write_metrics(
                runtime,
                "HUMAN_REQUIRED",
                {
                    "budget_exceeded": True
                },
            )

            artifacts.register(
                "metrics",
                run_dir / "metrics.json",
            )

            packet = human_packet(
                task=task,
                verification=verification,
                claude_review=review,
                rule_risk=rule_risk,
                codex_risk=codex_risk,
                aggregate=aggregate,
                paths=(
                    changed_paths(repo)
                    if not runtime.dry_run
                    else []
                ),
                reason=escalation_reason,
                metrics=metrics,
            )

            _write_text(
                artifacts,
                "human-review",
                run_dir / "human-review.md",
                packet,
            )

            _write_json(
                artifacts,
                "status",
                run_dir / "status.json",
                {
                    "status": "HUMAN_REQUIRED",
                    "reason": escalation_reason,
                    "metrics": metrics,
                },
            )

            runtime.log_event(
                "run_end",
                status="HUMAN_REQUIRED",
            )

            _write_terminal_run_summary(
                runtime=runtime,
                artifacts=artifacts,
                durable=durable,
                status="HUMAN_REQUIRED",
            )

            return run_dir


def run_panel(
    *,
    repo: Path,
    task: Dict[str, Any],
    config: Dict[str, Any],
    reports_root: Path,
    dry_run: bool = False,
) -> Path:
    run_dir = (
        reports_root
        / f"run-{_run_id()}"
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    runtime = Runtime(
        run_dir,
        budgets_from(config),
        dry_run=dry_run,
    )

    policy = v2_default_policy()

    generator = CodexAdapter(
        runtime,
        config,
    )

    reviewer = ClaudeAdapter(
        runtime,
        config,
    )

    risk_judge = CodexAdapter(
        runtime,
        config,
    )

    verifier = DeterministicVerifier(
        runtime,
        policy=policy,
    )

    risk_engine = (
        LegacyCompatibleRiskEngine()
    )

    artifacts = ArtifactRegistry()

    return execute_panel(
        runtime=runtime,
        repo=repo,
        task=task,
        config=config,
        generator=generator,
        reviewer=reviewer,
        risk_judge=risk_judge,
        verifier=verifier,
        risk_engine=risk_engine,
        artifacts=artifacts,
        policy=policy,
    )
