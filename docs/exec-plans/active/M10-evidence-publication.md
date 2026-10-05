# M10 — Evidence / Publication

Status: IN PROGRESS

Base tag: `m9-hardening-gc-complete`

Branch: `m10-evidence-publication`

## Objective

M10 converts the completed AIVP v2 implementation and its accumulated
evidence into a public, reproducible, auditable project package.

M10 is primarily a publication and evidence-reconciliation milestone,
not a new feature milestone.

The core question is no longer:

> What else can AIVP implement?

It is:

> Can a third party understand what AIVP does, reproduce the supported
> behavior, trace public claims back to evidence, and distinguish proven
> capabilities from limitations?

## Starting Inventory

At the frozen M9 boundary:

Existing evidence includes:

- M5 context-compiler evidence;
- M6 cache and provider-cache evidence;
- M7 fixed-evaluation evidence;
- M8 routing/economics evidence;
- M9 garbage-collection exit-gate evidence;
- milestone records M0 through M8;
- PROJECT_STATE and CAPABILITY_LEDGER;
- frozen completion tags through M9.

Major publication surfaces still need to be created:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/TECHNICAL_REPORT.md`
- `docs/BENCHMARK.md`
- `docs/SECURITY.md`
- `docs/EVALS.md`

The repository also contains local report trees and historical run
artifacts. Their presence in the local filesystem does not by itself
mean they are suitable for publication. M10 must separately determine
what is tracked, what is ignored, and what must remain local-only.

## Source-of-Truth Model

M10 uses the following evidence hierarchy.

1. Git source and immutable milestone tags for as-built behavior.
2. Raw evaluation / benchmark / fault evidence for measured claims.
3. `docs/PROJECT_STATE.json` for reconciled project state.
4. `docs/CAPABILITY_LEDGER.json` for capability status.
5. Milestone and execution-plan documents for historical reasoning.
6. Public documentation as a derived presentation layer.

Public documentation must not become an independent source of truth.

## Honesty Rules

Every quantitative or capability claim must map to concrete evidence.

AIVP v2 may be described as a production-minded coding-agent harness
prototype.

AIVP v2 must not be described as a production-grade multi-user service.

M10 must not silently convert:

- unavailable cost evidence into estimated USD savings;
- observed latency differences into unsupported causal claims;
- local fault tests into claims of 24/7 production reliability;
- sandbox mechanisms into claims of complete zero-trust isolation;
- fixed evaluation success into claims about arbitrary real-world tasks.

Missing data remains missing data.

Negative results and limitations remain visible.

## Planned → Actual → Deviation

### Planned

The Master Plan expects M10 to deliver publication-quality repository
documentation, architecture, benchmark evidence, security/evaluation
documentation, public articles, and clean-clone reproducibility.

### Actual at M10 Start

The implementation and substantial evidence already exist through M9,
but the primary publication surfaces have not yet been created.

### Deviation

M10 therefore begins with evidence freeze and claim reconciliation
before prose drafting.

This prevents README, architecture, benchmark, report, and interview
materials from drifting into separate narratives.

## Work Breakdown

### M10-1 — Evidence Freeze / Claim-Evidence Matrix

Build:

- canonical claim/evidence matrix;
- public / caveated / prohibited claim classification;
- publication execution plan;
- frozen M9 boundary reference.

Exit gate:

- every major public claim category has an evidence source or is
  explicitly marked unsupported;
- quantitative claims use frozen values;
- unsupported claims are explicitly excluded.

### M10-2 — Public README

Build:

- project purpose;
- mental model;
- feature summary;
- architecture overview;
- quick start;
- safety model;
- evaluation / benchmark summary;
- limitations;
- document navigation.

Exit gate:

- a first-time reader can understand the project from README alone;
- every numeric claim links to a deeper evidence document;
- README makes the production-minded prototype boundary explicit.

### M10-3 — Architecture Documentation

Build:

- `docs/ARCHITECTURE.md`;
- current as-built Harness Panel architecture;
- state / context / policy / sandbox / telemetry / evaluation / GC
  boundaries;
- key data and control flows;
- durability and containment boundaries.

Exit gate:

- architecture reflects current source rather than an old design-only
  diagram;
- planned-but-unimplemented components are not presented as as-built.

### M10-4 — Technical Report

Build:

- problem statement;
- design principles;
- milestone evolution;
- major decisions;
- failed/rejected hypotheses;
- Planned → Actual → Deviation;
- trade-offs;
- production gaps;
- lessons learned.

Exit gate:

- report explains both why and how;
- important deviations and negative evidence are preserved;
- no Business-grade experience claim is implied by prototype work.

### M10-5 — Benchmark Report

Build:

- `docs/BENCHMARK.md`;
- frozen baseline methodology;
- M7 formal evaluation;
- M7 → M8 routing comparison;
- M6 cache measurements where relevant;
- missing-cost semantics;
- raw-evidence references.

Exit gate:

- reported values can be traced to frozen evidence;
- quality and economics are separated;
- unavailable USD cost is not invented;
- observed wall-clock differences are not overstated causally.

### M10-6 — SECURITY / EVALS

Build:

- `docs/SECURITY.md`;
- `docs/EVALS.md`;
- threat model;
- capability boundaries;
- worktree / Docker isolation model;
- forbidden production capability;
- evaluation corpus and grading methodology;
- fault-injection coverage;
- known limitations.

Exit gate:

- third parties can understand what was tested and what was not;
- security claims stay inside the proven blast-radius boundary.

### M10-7 — Reproducibility / Public Hygiene

Build / verify:

- tracked-vs-local artifact classification;
- clean-clone setup;
- offline/unit verification path;
- one-command demonstration where supported;
- secret scan;
- private absolute-path scan;
- public artifact review;
- ignored local reports / caches / state review.

Exit gate:

- clean clone can follow documented verification steps;
- no private secret or personal absolute path is published;
- publication package does not depend on accidental local state.

### M10-8 — Publication Package

Build:

- final repository navigation;
- Note article: Why / Insight;
- Qiita article: How / Implementation;
- concise interview / portfolio summary;
- final cross-document claim consistency pass.

Exit gate:

- GitHub, articles, reports, and interview narrative use the same
  evidence;
- no publication surface contradicts the Claim-Evidence Matrix.

## Frozen Quantitative Evidence

M7 formal evaluation:

- 15 / 15 fixed cases PASS;
- 27 trials / regrades;
- 47 Codex calls;
- 31 Claude calls;
- 78 total model calls;
- 7 fix iterations;
- 14 AUTO_FINISHED;
- 13 HUMAN_REQUIRED;
- observed wall time 1122.694 seconds.

M8 routing evaluation:

- same 15 / 15 fixed cases PASS;
- same 27 trials / regrades;
- 47 Codex calls;
- 25 Claude calls;
- 72 total model calls;
- 7 fix iterations;
- same 14 AUTO_FINISHED / 13 HUMAN_REQUIRED terminal distribution;
- Claude calls reduced by 6, or 19.35 percent;
- total model calls reduced by 6, or 7.69 percent;
- observed wall time 1036.739 seconds.

The six no-op exits coincide with the six fewer Claude calls.

The wall-time difference is observational evidence and is not treated
as a clean causal estimate.

USD Cost per Accepted Change remains unavailable because the relevant
live-provider coverage is incomplete.

M9 hardening:

- 415 unit tests PASS;
- 8 / 8 M9 fault / exit-gate tests PASS;
- default GC mode is dry-run;
- destructive GC requires explicit `--yes`;
- dirty, resumable, protected, and ownership-unknown resources are
  preserved;
- bounded cleanup is idempotent in the tested local-first boundary.

## Scope Control

M10 does not add new agents, distributed workers, Kubernetes, a SaaS
control plane, authentication/RBAC, cloud runners, automatic merge or
deployment, or unrelated product features.

A code change is allowed only when required to remove a reproducibility
or publication blocker.

Live-model benchmark reruns are not part of M10 by default.

Existing frozen evidence should be reused unless a publication blocker
makes a new measurement necessary.

## M10 Exit Gate

M10 is complete when:

- public README exists;
- as-built architecture documentation exists;
- technical report exists;
- benchmark report exists;
- SECURITY and EVALS documentation exist;
- major public claims map to evidence;
- unsupported claims are explicitly excluded;
- clean-clone verification succeeds;
- secret / private-path publication scan is clean;
- public artifacts are reproducible from documented steps;
- publication narrative is consistent across repository and articles.

At that point AIVP v2.0 can be frozen as a completed
production-minded harness prototype.
