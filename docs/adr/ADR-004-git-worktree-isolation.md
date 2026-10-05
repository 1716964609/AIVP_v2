# ADR-004 — Git Worktree as Repository Isolation Boundary

## Status

Accepted.

## Context

Coding AgentがCanonical Repository上で直接Changeを生成すると、Failure時のBlast RadiusとRecovery Boundaryが曖昧になる。

一方、Repository全体を独自Copy Protocolで複製するとGit Identity / Base Revision Trackingが複雑になる。

## Decision

RunごとにDetached Git Worktreeを作成し、Agent ChangeはそのWorktree内で生成する。

Validationでは少なくとも、

- canonical repositoryとの分離
- Git common directory
- expected base SHA

を確認する。

## Consequences

利点:

- canonical repositoryからChangeを分離
- Base SHAを明示できる
- Git-native diff / cleanupが可能

制約:

- WorktreeはOS-level Security Sandboxではない
- Host Filesystem全体のIsolationを意味しない

## Evidence

- `src/aivp/containment/worktree.py`
- `docs/ARCHITECTURE.md`
- `docs/SECURITY.md`
- worktree containment tests

## Revisit Trigger

Git以外のSource Backendを正式Supportする時。
