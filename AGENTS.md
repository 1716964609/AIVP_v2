# AIVP v2 — Agent Operating Guide

This repository is designed to remain recoverable across AI sessions,
conversation compaction, model changes, and human handoffs.

Do not rely on conversation memory as the source of truth.

## 1. Source-of-Truth Model

Different sources answer different questions.

### Normative / Planned Truth
`AIVP_v2_Master_Implementation_Plan.pdf`

Answers:
- What should AIVP v2 achieve?
- What is the intended milestone order?
- What are the Exit Gates?
- What is explicitly out of scope?

The Master Plan is NOT a literal historical record of implementation.

### As-Built Truth
Git repository, source code, commit history, branches, and tags.

Answers:
- What was actually implemented?
- In what order?
- What does the current system actually contain?

### Proven Truth
Tests, reports, raw benchmark artifacts, SQLite state, logs, and
`docs/evidence/`.

Answers:
- What has actually been demonstrated?
- Which Exit Gates have evidence?
- Which performance or safety claims are measured?

### Historical / Decision Provenance
`docs/milestones/`, `docs/decisions/`, and archived historical material.

Answers:
- Why was a design chosen?
- What failed or changed?
- Where did implementation diverge from the plan?

Never rewrite historical reality merely to make it match the Master Plan.

## 2. Mandatory Context Bootstrap

At the beginning of a new AI session, read in this order:

1. `AGENTS.md`
2. `docs/PROJECT_STATE.json`
3. the active plan referenced by `PROJECT_STATE.json`
4. `git status --short --branch`
5. `git log -10 --oneline --decorate`

Only then read older milestone documents when the current task requires them.

Do NOT load all historical documents by default.

## 3. Current Project Direction

AIVP v2 is a local-first, single-user coding-agent Harness Panel.

The core v1 control loop remains conceptually:

Generate
-> Deterministic Verification
-> Independent Review
-> Risk Evaluation
-> Decision
-> AUTO_FINISHED or HUMAN_REQUIRED

The v2 Harness adds durability, containment, observability/economics,
context control/cache, evaluation, and later risk-based routing.

## 4. Non-Negotiable Engineering Invariants

Preserve these unless an explicit, evidence-backed design decision changes them:

- Generator != Verifier.
- Deterministic checks precede LLM judgment when possible.
- HUMAN_REQUIRED is a valid design outcome, not necessarily a failure.
- Execution is bounded by explicit budgets and policies.
- Production capability is denied by default.
- AIVP v2 does not auto-deploy or auto-merge.
- State and Cache are different concepts.
- Integrity failures fail closed.
- Unknown economics are unknown, not zero.
- Telemetry must not expose sensitive content by default.
- Context selection starts deterministic-first rather than RAG-first.
- Cache identity is exact before semantic reuse is considered.
- Claims require evidence; favorable numbers alone are not sufficient.

## 5. Milestone Discipline

The Master Plan defines the normative milestone sequence.

However:

- actual implementation order is recorded by Git;
- historical deviations must remain visible;
- capability completion may cross milestone boundaries;
- `code exists` does not imply `Exit Gate proven`.

Do not mark a milestone complete until its Exit Gate has evidence.

## 6. Current Milestone

Read:

`docs/PROJECT_STATE.json`

and then:

`docs/exec-plans/active/M7-eval.md`

M7 must be completed before implementing M8 risk-based routing/economics.

## 7. Evidence Discipline

When evaluating an implementation claim, prefer evidence in this order:

1. current source and Git history
2. automated tests
3. raw reports / SQLite / benchmark artifacts
4. milestone / ADR documentation
5. historical conversation archive

Conversation recollection must never override contradictory repository evidence.

## 8. Historical Retrieval

Use `docs/milestones/M0.md` through later milestone files only when needed.

Use archived conversation material only for forensic reconstruction or
decision provenance.

Archive material is NOT implementation SoT.

## 9. Before Modifying the System

Check:

- current branch and HEAD
- active milestone
- active Exit Gate
- relevant tests
- applicable milestone/ADR history
- whether the requested feature belongs to a later milestone

If stuck, solve the current Failure Class instead of adding unrelated features.
