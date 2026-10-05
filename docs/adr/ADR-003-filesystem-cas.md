# ADR-003 — Filesystem CAS + SQLite Metadata

## Status

Accepted.

## Context

Context Compilerで生成するRepository MapやContext Selection Artifactには、同一Contentを再利用するCacheが必要だった。

Local-first BoundaryでRedis等のRemote Cacheを導入する必要はない。

## Decision

Cacheは、

```text
Filesystem Content-addressed Storage
        +
SQLite Metadata Index
```

で構成する。

Content IdentityをHashで固定し、Metadata / ReferenceはSQLiteで管理する。

## Consequences

利点:

- deterministic identity
- local inspection
- simple invalidation model
- binary / text artifactを同じCAS原則で扱える

制約:

- distributed shared cacheではない
- network cache coherenceを提供しない

## Evidence

- `src/aivp/cache/cas.py`
- `src/aivp/cache/index.py`
- `docs/evidence/m6-cache.md`
- `docs/BENCHMARK.md`

## Revisit Trigger

Remote Worker間でCache共有による明確なEconomic Benefitが測定された時。
