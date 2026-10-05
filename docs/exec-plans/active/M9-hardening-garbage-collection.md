# M9 — Hardening / Garbage Collection

Status: IN PROGRESS
Base: b86a17cd5596141f52355bff6fd52d0c53cef9b0
M8 completion tag: m8-risk-routing-economics-complete
Branch: m9-hardening-gc

## Objective

Close the host-lifecycle gap without weakening durability, evidence retention,
or containment.

M9 must remove only AIVP-owned resources that are demonstrably safe to purge.

North-star exit condition:

> An interrupted run must not cause unbounded host garbage accumulation.

## Master Plan Scope

Required:
- orphan worktree cleanup
- stale container cleanup
- old cache GC
- artifact retention

Optional:
- repo quality scan

Decision:
- repo quality scan is deferred because it is optional and risks overlapping
  the v3 automatic codebase-quality backlog.

## As-Built Discovery

### Worktrees

Run worktrees are created under each run directory using detached Git worktrees.

There is no corresponding production cleanup lifecycle.

Resume explicitly validates and reuses the original worktree, therefore a
resumable run's worktree is not garbage.

### Docker

Deterministic sandbox execution already uses `docker run --rm`.

Normal container termination therefore cleans itself up.

M9 must not use host-wide `docker system prune` or delete unrelated containers.

Any additional cleanup must be limited to resources provably owned by AIVP.

### Cache

The cache index records `created_at` and supports individual entry deletion.

The CAS is shared by cache entries and currently has no garbage collector.

Deleting old index rows without sweeping only unreferenced CAS objects would
leak storage or risk deleting shared objects.

### Artifacts / Durable State

Durable state contains runs, checkpoints, and artifact records.

Resume requires both the run directory and, for isolated runs, the original
worktree.

Artifact retention must therefore distinguish resumable state from terminal
historical state and protected benchmark/evidence runs.

## Invariants

1. Never delete the canonical repository.
2. Never delete a worktree that belongs to a resumable run.
3. Never delete an artifact required by a resumable run.
4. Never delete a CAS object referenced by any surviving cache entry.
5. Never prune Docker resources not provably owned by AIVP.
6. Default GC mode is dry-run.
7. Destructive GC requires explicit `--yes`.
8. Re-running GC must be idempotent.
9. Missing resources are handled safely and do not corrupt durable state.
10. M7/M8 formal benchmark evidence is protected until explicitly released.

## Planned Implementation

### M9-1 — Ownership and GC Model

Introduce a small GC planning layer that classifies resources before deletion.

Classification:
- protected
- resumable
- terminal-retained
- expired
- orphaned
- foreign / unknown

Unknown ownership always means preserve.

### M9-2 — Worktree Cleanup

Add bounded worktree removal helpers.

Rules:
- canonical repository is never removable
- resumable worktrees are preserved
- expired terminal worktrees may be removed
- missing worktree registrations may be pruned
- cleanup is idempotent

### M9-3 — Docker Cleanup

Keep existing `--rm` behavior.

Add AIVP ownership metadata only if needed for deterministic stale-resource
identification.

GC must never use global Docker prune operations.

### M9-4 — Cache GC

Use cutoff-based cache-entry expiry.

After index expiry:
- compute all CAS digests referenced by surviving entries
- remove only unreferenced CAS objects
- reject symlinks / unexpected paths
- remain safe under repeated execution

### M9-5 — Artifact Retention

Define retention around durable run state.

Preserve:
- resumable runs
- current runs
- protected benchmark/evidence runs

Only terminal runs older than the configured cutoff may become purge
candidates.

Filesystem and durable metadata must not silently diverge.

### M9-6 — CLI

Add:

    aivp gc --older-than 7d

Default:
- plan/report only
- no deletion

Destructive execution:

    aivp gc --older-than 7d --yes

Output must explain:
- resource
- ownership
- age
- classification
- planned action
- reason

### M9-7 — Exit-Gate Tests

Required deterministic tests:
- interrupted/resumable worktree survives GC
- expired terminal worktree is removed
- foreign worktree is preserved
- unrelated Docker container is preserved
- surviving cache reference protects shared CAS object
- orphan CAS object is removed after cutoff
- protected evidence run survives retention
- repeated GC is idempotent
- dry-run performs no deletion

No live model calls are required for M9 proof.

## Explicit Non-Goals

- background maintenance agents
- automatic repository quality scoring
- global Docker pruning
- arbitrary host cleanup
- redesigning durable state
- PostgreSQL / Redis / Temporal
- cloud workers
- multi-user retention policy
- M10 publication work

## Evidence Required for Closure

- unit tests for classification and deletion boundaries
- deterministic interrupted-run cleanup test
- dry-run output
- destructive test in temporary repositories/directories only
- full unit and integration regression suite
- evidence document describing before/after host-resource behavior

## Exit Gate

M9 is complete only when an interrupted run can be followed by bounded,
explicit GC without:

- deleting resumable state
- deleting foreign host resources
- corrupting cache references
- damaging protected benchmark evidence

and repeated GC does not accumulate additional garbage.
