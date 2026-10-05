# ADR-002 — SQLite for Durable State

## Status

Accepted.

## Context

AIVP v2にはProcess Crash後も、

```text
what completed?
what can resume?
what evidence belongs to this run?
```

を回答できるDurable Stateが必要だった。

Local-first / Single-user Boundaryでは、External Database Serviceを導入すると運用面の複雑性が先に増える。

## Decision

Durable Run MetadataにはSQLiteを使用する。

主要Boundary:

```text
SQLiteStateStore
DurableExecution
Checkpoint
ResumePlan
ArtifactRecord
```

Process MemoryをRecovery Source of Truthにしない。

## Consequences

得られるもの:

- local durable transactions
- explicit checkpoint
- crash recovery
- auditable state
- no external DB dependency

得られないもの:

- distributed consensus
- multi-node write coordination
- HA database service

## Evidence

- `src/aivp/state/sqlite.py`
- `src/aivp/state/durable.py`
- `src/aivp/state/resume.py`
- process-resume / state-integrity tests
- `docs/EVALS.md`

## Revisit Trigger

複数Worker / 複数Hostから同一State Storeを共有するRequirementが成立した時。
