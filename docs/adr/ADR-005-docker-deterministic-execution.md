# ADR-005 — Docker for Deterministic Verification First

## Status

Accepted.

## Context

Generated ChangeをHost上でそのままVerificationすると、Network、Environment、FilesystemなどのBlast Radiusが広がる。

ただし、AIVP v2はRemote Sandbox Platformそのものを構築するProjectではない。

## Decision

最初にContainerizeするBoundaryはModel Reasoningではなく、Deterministic Verificationとする。

Docker SandboxではEvidence上、

- network isolation
- non-root execution
- read-only root filesystem
- host environment isolation
- canonical repository hiding

を検証する。

## Consequences

利点:

- deterministic commandのblast radiusを制限
- local reproductionが容易
- Security Testを機械化できる

非主張:

- Complete zero-trust isolation
- full model CLI containment
- multi-tenant sandbox

## Evidence

- `src/aivp/containment/docker_sandbox.py`
- `docs/SECURITY.md`
- Docker sandbox integration tests
- `forbidden-secret-access`
- `forbidden-network-action`

## Revisit Trigger

Model Execution Plane自体のHost IsolationがRequirementになった時。
