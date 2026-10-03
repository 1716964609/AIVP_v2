# M7 — Eval Harness Evidence

Status: COMPLETE / STRONGLY PROVEN

## Exit Gate

The M7 Master Plan requires:

1. approximately 15 fixed cases executable through one command;
2. results recomputable from preserved raw artifacts.

Both conditions are satisfied.

## Frozen Identity

Implementation baseline:

`891655b84060186f6019bd43a2273d204574dc13`

Frozen corpus commit:

`54500b1`

Formal clean run:

`m7-final-clean-20261004-072204`

All 27 trial manifests resolved to the exact implementation baseline above.

Baseline mismatches:

`0 / 27`

## Formal Fixed-Suite Result

Command shape:

`aivp eval run evals/suites/m7-fixed.json ... --yes`

Result:

- suite outcome: PASS
- fixed cases: 15
- cases PASS: 15
- cases FAIL: 0
- cases ERROR: 0
- trial manifests: 27
- regrade-001 results: 27
- benchmark reports: 15
- Codex usage-limit failures in the successful formal run: 0

The suite includes capability, business logic, specification conflict,
repair, authorization risk, policy/containment, durability, stale cache,
malformed model output, and budget exhaustion behavior.

## Re-Grading From Preserved Artifacts

A second independent offline re-grade was created as `regrade-002`.

Result:

- trials compared: 27
- semantic matches with regrade-001: 27
- mismatches: 0
- regrade-002 PASS: 27

No Harness execution, Codex call, Claude call, or external command was needed
to regenerate the grading result.

Source evidence immutability check:

- source evidence files before: 7,255
- source evidence files after: 7,255
- changed: 0
- missing: 0
- added: 0

Therefore M7 grading is reproducible from preserved evidence without mutating
that evidence.

## Three-Trial Behavioral Cases

| Case | Trials | Pass rate | Codex mean | Claude mean | Fix mean | Elapsed p50 s | Elapsed p95 s | Input p50 | Cached p50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| business-invariant-failure | 3 | 100% | 1.0 | 1.0 | 0.0 | 11.905 | 12.2182 | 102.0 | 10178.0 |
| dependency-addition | 3 | 100% | 2.0 | 1.0 | 0.0 | 58.184 | 62.8658 | 117968.0 | 125282.0 |
| high-auth-change | 3 | 100% | 2.0 | 2.0 | 1.0 | 118.671 | 130.8462 | 253178.0 | 256821.0 |
| low-username-normalization | 3 | 100% | 2.0 | 1.0 | 0.0 | 56.123 | 58.3082 | 124669.0 | 91312.0 |
| medium-pricing-rule | 3 | 100% | 2.0 | 1.0 | 0.0 | 68.448 | 70.9509 | 145395.0 | 157942.0 |
| specification-conflict | 3 | 100% | 2.0 | 2.0 | 1.0 | 69.291 | 72.441 | 119240.0 | 158587.0 |

Full per-case distributions are preserved in:

`docs/evidence/m7-eval-summary.json`

and in the generated benchmark reports under the formal run directory.

## Economics Interpretation

M7 records model calls, latency, input tokens, cached tokens, and output
tokens when available.

One nominal USD-cost sample exists:

- case: `budget-exhaustion`
- value: `$0.00`
- source: scripted budget-exhaustion behavior

This is not live-provider billing evidence.

Therefore:

- live-provider USD cost samples: 0
- suite-level Cost per Accepted Change in USD: unavailable
- missing USD cost is not converted to zero
- missing USD cost is not estimated

The measured model-call, token, cache, and latency distributions are retained
as the Before baseline for M8 Risk-based Routing / Economics.

## Discovery Evidence

M7 did more than validate a finished implementation. Shakedown exposed real
Harness and fixture defects before corpus freeze.

Observed discoveries included:

- Python bytecode-cache nondeterminism in controlled repair verification;
- malformed model output escaping normal terminalization;
- insufficient live Claude review turn budget;
- durable verification artifact identity collision when one execution
  attempt contained multiple verification rounds;
- HIGH authorization-case reviewer expectation needing calibration before
  freeze;
- external Codex usage-limit exhaustion during the first formal run.

Corrections were constrained to M7-safe execution, fixture, grading, and
failure-normalization behavior.

M8 risk routing, reviewer routing, model/call routing, and early exit were not
implemented during M7.

## Negative Runs Preserved

The first formal run:

`m7-final-20261004-062003`

completed the suite infrastructure but encountered external Codex usage-limit
exhaustion, producing 11 PASS / 4 ERROR at case level.

This was classified as provider availability evidence rather than a functional
quality regression.

A later clean run was manually interrupted during Claude review after three
completed trials:

`m7-final-clean-20261004-070037`

It is preserved as interruption evidence and is not used as the final
benchmark.

Neither negative run was rewritten or deleted to make the final result look
cleaner.

## Final Regression

At M7 close:

- 323 unit tests PASS
- 11 integration tests PASS
- `git diff --check` PASS

The unit suite also exercises the CLI fail-closed requirement for real eval
execution without `--yes`.

## Limitations

- Six major behavioral cases use three trials; most deterministic/fault cases
  use one.
- Provider/model behavior remains nondeterministic.
- Subscription/provider quota remains an external dependency.
- USD cost coverage is unavailable and is not inferred.
- M7 measures and grades current behavior; optimization belongs to M8.

## Exit Status

PROVEN AT M7 BOUNDARY.

M8 may now optimize model/reviewer routing and early exit against this frozen
quality and economics baseline.
