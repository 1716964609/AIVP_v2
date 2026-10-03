# M7 — Eval Harness

Status: ACTIVE / IMPLEMENTATION NOT STARTED

## Purpose

M7 creates the measuring instrument used to evaluate AIVP Harness behavior.

It does not optimize routing yet.

M8 uses evidence produced by M7 to change routing and economics.

## Normative Requirements

The Master Implementation Plan requires:

- case schema
- trial runner
- deterministic graders
- expected decision grader
- benchmark report generator

Exit Gate:

- approximately 15 fixed cases execute through one command
- results can be recomputed from raw artifacts

## Starting Repository State

M7 branch:

`m7-eval`

Base:

`47b7908`
`m6-cache-complete`

At M7 start there was no existing:

- `src/aivp/eval/`
- `evals/`
- eval-specific test suite

Therefore M7 begins cleanly from the M6 completion snapshot.

## Minimum Eval Suite

The normative seed suite is approximately:

1. LOW username normalization
2. MEDIUM pricing rule
3. specification conflict
4. controlled fault repair
5. HIGH auth change
6. forbidden secret access
7. large diff
8. dependency addition
9. reviewer timeout
10. process kill / resume
11. stale context / cache
12. forbidden network / tool action
13. tests pass but business invariant fails
14. malformed model output
15. budget exhaustion

These are fixed evaluation cases, not ordinary unit tests.

## Existing Capabilities M7 May Reuse

M0-M6 already provide reusable mechanisms including:

- preserved v1 baseline behavior
- deterministic verification
- risk aggregation
- durable state and resume
- worktree isolation
- Docker containment
- policy gates
- telemetry
- model-call accounting
- context compilation
- cache behavior
- raw run artifacts

M7 should orchestrate and grade these capabilities rather than reimplement them.

## Implementation Order

### M7-1 — Case Schema

Status: COMPLETE

Implementation evidence:

- `src/aivp/eval/case.py`
- `tests/unit/test_eval_case.py`
- existing AIVP task/config contracts are reused rather than duplicated
- case contract is frozen, including nested expected values
- relative task/config/repository references resolve from the case definition
- grader identifiers and trial count are validated
- 7 focused Eval Case unit tests pass
- 255 total unit regression tests pass
- `git diff --check` passes

Define the immutable contract for one evaluation case.

The schema should wrap or reference existing AIVP task/config contracts rather
than introducing a duplicate task model.

Required concern areas include:

- identity
- repository baseline
- task/config input
- expected outcome / decision
- applicable graders
- trial configuration

Exact field names must follow existing repository contracts.

### M7-2 — Trial Runner

Status: COMPLETE

Implementation evidence:

- `bc9e3cf` adds explicit repository baseline support
- `src/aivp/eval/runner.py`
- `tests/unit/test_explicit_baseline.py`
- `tests/unit/test_eval_runner.py`
- declared repository revision is resolved to one exact commit SHA per evaluation
- every trial executes against the same resolved baseline
- canonical repository HEAD remains unchanged
- task/config/case expectations are snapshotted for later re-grading
- evaluation and per-trial manifests preserve execution identity and status
- Harness execution failures are recorded before being re-raised
- unexpected run-directory contract violations fail closed and are recorded
- 264 total unit regression tests pass
- `git diff --check` passes

Execute one case for one or more trials.

Responsibilities:

- establish reproducible baseline
- invoke the existing Harness
- preserve raw run artifacts
- record trial identity
- avoid mixing execution and grading concerns

### M7-3 — Graders

Status: COMPLETE

Implementation evidence:

- `b7a6dc9` adds expected-decision and verification graders
- `b91079b` adds risk-artifact and diff graders
- `76a07c2` adds policy and artifact-integrity grading
- `c8f2b20` adds reviewer and human-calibration graders
- graders consume preserved run artifacts rather than rerunning Harness execution
- expected-decision grading distinguishes expected terminal outcomes
- verification grading evaluates the latest numeric verification round
- diff grading supports exact/required/forbidden paths and size limits
- policy grading distinguishes policy denial/human gates from other terminal outcomes
- artifact-integrity grading validates evaluation-local SHA-256 and size snapshots
- reviewer grading reuses existing AIVP blocking-finding semantics
- human calibration compares frozen human labels against saved reviewer decisions
- grade outcomes distinguish `PASS`, `FAIL`, and `ERROR`
- 293 total unit regression tests pass
- `git diff --check` passes

Deterministic grading is used where deterministic evidence exists.
Saved LLM-review artifacts are graded without making new model calls.

### M7-4 — Re-Grading

Status: COMPLETE

Implementation evidence:

- `3b56f7e` adds raw-artifact re-grading
- `src/aivp/eval/regrade.py`
- `tests/unit/test_eval_regrade.py`
- completed trials are re-graded exclusively from preserved evaluation artifacts
- re-grading does not invoke Harness execution, models, or external commands
- re-grading does not modify source evaluation evidence
- each re-grade writes a separate versioned output directory
- prior re-grade results are preserved rather than overwritten
- incomplete source trials are represented as re-grade `ERROR`
- evaluation outcome remains distinct from re-grade execution status
- 52 Eval Harness unit tests pass
- 300 total unit regression tests pass
- `git diff --check` passes

A completed trial is gradeable again from its raw artifacts without
rerunning the model or Harness execution.

This hard M7 property is now implemented.

### M7-5 — Benchmark Reporting

Status: COMPLETE

Implementation evidence:

- `2431062` adds benchmark reporting
- `src/aivp/eval/benchmark.py`
- `tests/unit/test_eval_benchmark.py`
- benchmark quality outcomes remain separate from performance measurements
- numerical measurements retain raw values, min, max, mean, p50, and p95
- categorical terminal-status and final-risk distributions are preserved
- missing `run-summary.json` is reported as unavailable rather than zero
- partially known token/cost measurements are excluded from complete-value samples
- cost coverage must agree with the recorded model-call count
- benchmark generation does not invoke Harness execution, models, or external commands
- benchmark generation does not modify source evaluation evidence
- source re-grade identifiers and output identities fail closed on invalid paths
- 62 Eval Harness unit tests pass
- 310 total unit regression tests pass
- `git diff --check` passes

For nondeterministic model behavior, repeated trials retain distributions and
ranges rather than mean-only summaries.

### M7-6 — Single-Command Suite

Status: NEXT

Expose the fixed suite through one CLI entry point.

Target conceptual interface:

`aivp eval run <suite>`

Exact CLI shape may adapt to the current CLI architecture.

## Explicit Non-Goals During M7

Do not implement M8 features yet:

- risk-based reviewer routing
- model routing optimization
- early exit optimization
- call-budget routing optimization

Do not introduce unrelated infrastructure such as:

- Redis
- PostgreSQL
- Temporal
- Kubernetes
- vector database
- semantic cache

## Evidence Required Before Closing M7

The closing evidence must demonstrate:

1. the fixed suite is discoverable and machine-readable;
2. approximately 15 cases execute via a single command;
3. raw artifacts are persisted;
4. graders produce structured results;
5. the same raw artifacts can be re-graded without model execution;
6. regression tests remain green;
7. M7 completion commit/tag and evidence are recorded.

## Current Next Step

Inspect the existing task, application, Harness Panel, structured-loader, and
run-artifact contracts.

Then implement:

`src/aivp/eval/case.py`

and its unit tests first.

Do not design the Trial Runner before the Case Schema contract is stable.

## Milestone Closure Gate

M7 is not COMPLETE merely because the implementation works.

The milestone closes only when both the technical Exit Gate and project
continuity requirements are satisfied.

### Technical

- [ ] Functional M7 Exit Gate is satisfied.
- [ ] Approximately 15 fixed cases execute through one command.
- [ ] Required success and failure cases are exercised.
- [ ] Raw trial artifacts are preserved.
- [ ] Deterministic graders produce structured results.
- [ ] Expected-decision grading works.
- [ ] Completed trials can be re-graded from raw artifacts without model execution.
- [ ] Full unit/integration regression passes.

### Evidence

- [ ] M7 evidence is written under `docs/evidence/`.
- [ ] Claims can be recomputed from raw artifacts.
- [ ] Trial counts and nondeterministic ranges/distributions are recorded where applicable.
- [ ] Negative results and known limitations are preserved.
- [ ] No favorable metric is promoted without corresponding quality evidence.

### Repository Memory

- [ ] `docs/milestones/M7.md` is finalized.
- [ ] `docs/CAPABILITY_LEDGER.json` is updated.
- [ ] `docs/PROJECT_STATE.json` records M7 completion and the next milestone.
- [ ] Important design deviations and decisions are recorded.
- [ ] This active execution plan is closed or moved to `docs/exec-plans/completed/`.

### Git Closure

- [ ] `git diff --check` passes.
- [ ] Completion commit is created.
- [ ] Completion tag is created.
- [ ] Working tree is clean.

Only after all applicable items above are satisfied may M7 be recorded as
COMPLETE.
