# M9 Hardening / Garbage Collection — Exit-Gate Evidence

## Scope

This evidence closes the M9 host-garbage safety proof for the local
production-minded AIVP v2 prototype.

No live model calls were used.

The destructive scenarios were executed only against temporary Git
repositories, temporary worktrees, temporary report directories, and
temporary SQLite databases.

Docker and cache orchestration were isolated from the host in the M9-7
fault suite; their destructive semantics remain covered by their
dedicated M9 unit regressions.

## Proven behaviors

The M9-7 fault suite demonstrates that:

- default `aivp gc` behavior is dry-run and does not remove an eligible
  expired run;
- an expired AIVP-owned terminal run can be removed when destructive GC
  is explicitly enabled;
- a resumable interrupted run is preserved;
- explicitly protected formal evidence is preserved;
- a dirty orphan worktree is preserved rather than force-removed;
- a resource whose ownership cannot be proven is preserved;
- repeating destructive GC after a completed purge is idempotent and
  does not create a duplicate completion event.

## Safety boundary

Destructive GC remains opt-in through `--yes`.

`--yes` does not translate into dirty-worktree force deletion.
Worktree cleanup continues to use `allow_dirty=False`.

Unknown ownership fails closed to preservation.

SQLite historical provenance is retained when filesystem payloads are
purged.

## Verification

Observed at M9-7 preparation:

- M9-7 fault / exit-gate suite: 8 tests PASS
- M9 GC CLI regression: 9 tests PASS
- Worktree GC regression: 8 tests PASS
- Docker GC regression: 7 tests PASS
- Cache GC regression: 8 tests PASS
- Artifact retention planner regression: 10 tests PASS
- Artifact retention executor regression: 8 tests PASS
- Full unit regression: 415 tests PASS

## Exit-gate conclusion

Within the tested local-first boundary, interrupted/resumable,
protected, dirty, and ownership-unknown resources are preserved while
expired AIVP-owned garbage is eligible for bounded cleanup.

Repeated cleanup is idempotent.

This satisfies the M9 implementation intent without claiming a
production-grade background maintenance service.
