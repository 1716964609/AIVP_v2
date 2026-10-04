# M8 — Risk-based Routing / Economics Evidence

Status: COMPLETE / STRONGLY PROVEN

## Purpose

M8 reduces unnecessary model calls while preserving the frozen M7
evaluation quality and safety boundary.

The optimization target is not raw call reduction at any cost. The target
is fewer unnecessary calls while preserving deterministic verification,
independent-risk semantics where they can still change the outcome,
bounded execution, explicit human escalation, and auditability.

## Comparison Boundary

Candidate implementation SHA:

`99995181a2c1b235e2ce1299ed49543bb3857e22`

Frozen suite:

`evals/suites/m7-fixed.json`

Before:

`m7-final-clean-20261004-072204`

After:

`m8-final-routing-20261004-120728`

Both runs use:

- 15 fixed cases
- 27 trials
- the same frozen M7 corpus and trial multiplicity

## Headline Result

| Metric | M7 Before | M8 After | Change |
| --- | ---: | ---: | ---: |
| Eval cases PASS | 15 / 15 | 15 / 15 | preserved |
| Codex calls | 47 | 47 | 0.00% |
| Claude calls | 31 | 25 | -19.35% |
| Total model calls | 78 | 72 | -7.69% |
| Fix iterations | 7 | 7 | unchanged |
| AUTO_FINISHED | 14 | 14 | unchanged |
| HUMAN_REQUIRED | 13 | 13 | unchanged |
| Suite wall-clock | 1122.694 s | 1036.739 s | -7.66% |

The M8 hard quality gate passed: all 15 fixed cases remained PASS.

## Review-Routing Result

The formal M8 run contains exactly:

- 6 `no-op-review-repair-*` artifacts
- 6 `review-repair-budget-*` artifacts
- 1 `deterministic-repair-budget-*` artifact
- 14 `risk-routing.json` artifacts
- 14 `aggregate-risk.json` artifacts

Claude calls decreased by exactly six, from 31 to 25.

Codex calls remained 47, fix iterations remained 7, and terminal outcome
counts remained unchanged.

The observed reduction is therefore consistent with the implemented M8-2
no-op repair early exit: after a Claude blocker triggers a repair attempt,
an unchanged worktree fingerprint terminates safely as HUMAN_REQUIRED
without an otherwise redundant second Claude review.

## Deterministic Risk Routing

M8-1 introduced a safe optimization boundary rather than a broad LOW-risk
shortcut.

An earlier LOW/LOW skip hypothesis was rejected because the existing
safety contract contains a case where deterministic risk is LOW and Claude
risk is LOW but the independent Codex risk judge is HIGH.

The accepted skip is restricted to mathematically terminal HIGH outcomes.

In this formal corpus, Codex calls remained 47 -> 47. Therefore M8-1
provided the safety-preserving routing mechanism but did not produce a
measured Codex-call reduction in this run.

## Call-Budget Routing

M8 reserves downstream calls required for safety before admitting
discretionary deterministic or review repair.

The runtime hard call cap remains authoritative.

The formal suite preserved expected terminal behavior while recording
repair-budget decision provenance.

## Early Exit

M8 does not add a duplicate generic `early-exit.json`.

Existing structured artifacts remain the source of truth:

- `deterministic-repair-budget-*.json`
- `review-repair-budget-*.json`
- `no-op-review-repair-*.json`
- `risk-routing.json`
- `aggregate-risk.json`
- `status.json`

`status.json` is the terminal-outcome source of truth. Routing artifacts
record decision provenance.

## Latency

Suite wall-clock:

- M7: 1122.694 seconds
- M8: 1036.739 seconds
- observed delta: -85.955 seconds / -7.66%

Per-trial benchmark elapsed-time distribution:

- M7 p50: 49.553 seconds
- M7 p95: 111.515 seconds
- M8 p50: 54.208 seconds
- M8 p95: 82.326 seconds

The suite wall-clock result is an observed paired-run result, not a general
causal latency claim. Provider/model execution is nondeterministic.

## Token Telemetry

Observed benchmark telemetry:

| Metric | M7 Before | M8 After |
| --- | ---: | ---: |
| Input tokens total | 2253529 | 2327369 |
| Cached tokens total | 2435735 | 2148680 |
| Output tokens total | 34262 | 27412 |

These values are preserved as measured telemetry. M8 does not promote a
causal token-saving claim from this single paired formal run.

## Economics

Live-provider USD cost coverage is unavailable.

Therefore:

`Cost per Accepted Change (USD) = UNAVAILABLE`

Missing provider billing evidence is not interpreted as zero.

M8 instead uses measured proxy economics where coverage is complete:

- model calls
- role-specific model calls
- suite wall-clock
- token telemetry
- repair iterations
- terminal outcomes

## Regression Evidence

The M8 candidate SHA was regression-tested before the formal benchmark:

- 349 unit tests PASS
- 11 integration tests PASS

No code changed between that regression boundary and the formal M8
benchmark candidate SHA.

## Measured Claim

On the frozen 15-case / 27-trial evaluation suite, M8 reduced total model
calls from 78 to 72 (-7.69%) while preserving 15 / 15 eval quality and the
same terminal-outcome distribution.

Claude review calls fell from 31 to 25 (-19.35%). Six preserved no-op
review-repair artifacts match the six-call reduction.

Suite wall-clock decreased from 1122.694 seconds to 1036.739 seconds
(-7.66%) in this paired formal run.

## Limitations

- Provider/model behavior remains nondeterministic.
- The formal comparison is one paired M7/M8 suite run.
- Live-provider USD billing evidence is unavailable.
- Dollar Cost per Accepted Change is therefore unavailable.
- The fixed suite exercises production-relevant Harness failure classes,
  not the full scale or domain complexity of a production monorepo.
- M8-1 produced no measured Codex-call reduction in this formal corpus.

## Exit Status

PROVEN AT M8 BOUNDARY.

Next milestone:

M9 — Hardening / Garbage Collection.
