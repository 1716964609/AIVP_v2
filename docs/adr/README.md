# AIVP v2 — Architecture Decision Records

このDirectoryは、AIVP v2で既に実装・検証された主要なArchitecture Decisionを記録する。

ADRはFuture ArchitectureのWish Listではない。

```text
Observed Problem
    ↓
Decision
    ↓
Implemented Boundary
    ↓
Evidence / Consequence
```

をRepository上へ固定する。

| ADR | Decision | Status |
|---|---|---|
| [ADR-001](ADR-001-local-first-single-user.md) | Local-first / Single-user v2 | Accepted |
| [ADR-002](ADR-002-sqlite-state-store.md) | SQLite for durable state | Accepted |
| [ADR-003](ADR-003-filesystem-cas.md) | Filesystem CAS + SQLite metadata | Accepted |
| [ADR-004](ADR-004-git-worktree-isolation.md) | Git worktree as repository isolation boundary | Accepted |
| [ADR-005](ADR-005-docker-deterministic-execution.md) | Docker for deterministic verification first | Accepted |
| [ADR-006](ADR-006-production-default-deny.md) | Production capability is blocked by default | Accepted |
| [ADR-007](ADR-007-semantic-cache-deferred.md) | Semantic cache is deferred | Accepted |
| [ADR-008](ADR-008-eval-before-routing.md) | Evaluation precedes routing optimization | Accepted |
| [ADR-009](ADR-009-mcp-adapter-boundary.md) | MCP is optional adapter surface, not Harness dependency | Accepted scope boundary |
| [ADR-010](ADR-010-cost-per-accepted-change.md) | Cost per Accepted Change is the economic North Star | Accepted with measurement caveat |

Current As-Built documentation:

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`../TECHNICAL_REPORT.md`](../TECHNICAL_REPORT.md)
- [`../BENCHMARK.md`](../BENCHMARK.md)
- [`../SECURITY.md`](../SECURITY.md)
- [`../EVALS.md`](../EVALS.md)
