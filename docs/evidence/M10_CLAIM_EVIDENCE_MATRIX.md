# M10 Claim → Evidence Matrix

This document is the canonical publication claim registry for AIVP v2.

Public documentation should derive claims from this matrix rather than
independently reconstructing them.

Legend:

- **PUBLIC** — evidence supports the claim directly.
- **PUBLIC WITH CAVEAT** — claim is supportable only with the stated
  limitation.
- **DO NOT CLAIM** — current evidence is insufficient.

| Claim | Status | Evidence | Publication wording / caveat |
|---|---|---|---|
| AIVP v1 baseline was frozen before v2 implementation | PUBLIC | `m0-baseline-frozen`, `docs/milestones/M0.md` | v1 baseline preceded v2 implementation and was retained for comparison. |
| AIVP v2 implements durable SQLite-backed execution and checkpoint/resume mechanisms | PUBLIC | `docs/milestones/M2.md`, capability ledger, durable-state tests | Describe the implemented mechanism and fault-tested behavior, not 24/7 HA durability. |
| Per-run Git worktrees and Docker-based deterministic verification bound local execution blast radius | PUBLIC WITH CAVEAT | `docs/milestones/M3.md`, worktree / Docker containment tests | Local-first containment mechanism; not complete zero-trust or multi-tenant isolation. |
| Run-level telemetry and model-call accounting are implemented | PUBLIC WITH CAVEAT | `docs/milestones/M4.md`, capability ledger | Token/latency/call telemetry exists where provider data is available; do not invent unavailable USD cost. |
| Deterministic context selection reduces supplied context while preserving tested behavior | PUBLIC | `docs/evidence/m5-context-compiler.md`, `docs/milestones/M5.md` | Scope claim to the tested context-compiler cases. |
| Harness-owned local cache reduces repeated context-preparation latency | PUBLIC | `docs/evidence/m6-cache.md`, `docs/evidence/m6-cache-latency.json` | Controlled local benchmark evidence; do not generalize to production workload latency. |
| Provider prompt layout produced a measurable cached-token hit in the controlled test | PUBLIC WITH CAVEAT | `docs/evidence/m6-provider-cache.json` | Controlled provider observation, not a guaranteed cache-hit rate. |
| The frozen M7 fixed evaluation suite passed 15/15 cases | PUBLIC | `docs/evidence/m7-eval.md`, `docs/evidence/m7-eval-summary.json`, `docs/milestones/M7.md` | Fixed-suite evidence, not arbitrary-task accuracy. |
| M7 formal evaluation used 27 trials/regrades and ended with 14 AUTO_FINISHED / 13 HUMAN_REQUIRED outcomes | PUBLIC | `docs/evidence/m7-eval.md`, `docs/evidence/m7-eval-summary.json` | Reproduce exact terminology from frozen evidence. |
| M7 used 47 Codex + 31 Claude = 78 model calls | PUBLIC | `docs/evidence/m7-eval-summary.json` | Frozen formal-run measurement. |
| M8 preserved 15/15 fixed-suite quality while reducing Claude calls 31 → 25 | PUBLIC | `docs/evidence/m8-routing-economics.md`, `docs/evidence/m8-routing-economics-summary.json` | Same frozen suite; Claude calls -19.35%. |
| M8 reduced total model calls 78 → 72 while Codex calls remained 47 | PUBLIC | `docs/evidence/m8-routing-economics.md`, `docs/evidence/m8-routing-economics-summary.json` | Total model calls -7.69%; Codex 47 → 47. |
| Six no-op exits coincide with six fewer Claude review calls | PUBLIC WITH CAVEAT | `docs/evidence/m8-routing-economics.md` | Strong mechanism evidence, but wording should remain observational rather than universal causal law. |
| M7 → M8 observed suite wall time changed 1122.694 s → 1036.739 s | PUBLIC WITH CAVEAT | M7/M8 frozen evidence | May report the observed -7.66% difference; do not attribute the full difference causally to routing. |
| M9 bounded GC preserves dirty, resumable, protected, and ownership-unknown resources | PUBLIC | `docs/evidence/M9_GC_EXIT_GATE.md`, `fff46f5` | Proven inside the tested local-first boundary. |
| M9 default GC is dry-run and destructive cleanup requires `--yes` | PUBLIC | `docs/evidence/M9_GC_EXIT_GATE.md`, M9 CLI tests | `--yes` does not enable dirty-worktree force deletion. |
| M9 cleanup is idempotent in the tested scenarios | PUBLIC | `docs/evidence/M9_GC_EXIT_GATE.md` | Scope to tested bounded cleanup behavior. |
| M9 closed with 415 unit tests PASS and 8/8 GC exit-gate fault tests PASS | PUBLIC | `docs/evidence/M9_GC_EXIT_GATE.md`, `m9-hardening-gc-complete` | Frozen M9 completion evidence. |
| AIVP v2 is a production-minded coding-agent harness prototype | PUBLIC | Technical design, milestone evidence M0-M9 | Preferred external positioning. |
| AIVP v2 is a production-grade multi-user service | DO NOT CLAIM | No supporting evidence | Explicitly out of scope. |
| AIVP v2 provides complete zero-trust enterprise isolation | DO NOT CLAIM | No supporting evidence | Current containment is local-first and bounded. |
| AIVP v2 demonstrates mature SRE on-call / SLO operations | DO NOT CLAIM | No supporting evidence | Not part of prototype scope. |
| AIVP v2 proves large-scale multi-tenant cost optimization | DO NOT CLAIM | No supporting evidence | Local prototype economics only. |
| M8 reduced USD Cost per Accepted Change by a known percentage | DO NOT CLAIM | Provider-cost coverage incomplete | USD Cost per Accepted Change remains unavailable. |
| AIVP v2 fixed-suite quality equals general real-world coding accuracy | DO NOT CLAIM | No supporting evidence | Fixed evaluation must not be generalized beyond its corpus. |

## Publication Rule

If a future README, report, diagram caption, article, presentation, or
interview claim cannot be mapped back to one of the supported entries
above, it must either:

1. add new evidence,
2. be downgraded to an explicit hypothesis / limitation, or
3. be removed.
