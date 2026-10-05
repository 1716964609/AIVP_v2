# ADR-007 — Semantic Cache is Deferred

## Status

Accepted.

## Context

Semantic Similarityだけで過去のReasoning ResultをReuseすると、

- repository state
- business invariant
- security context
- task intent

の差を誤って無視する可能性がある。

Cache Hit率を増やすこと自体はSafety Evidenceではない。

## Decision

AIVP v2ではSemantic Cacheを実装しない。

v2で採用するCacheは、Deterministic IdentityとExplicit Invalidationを持つものに限定する。

## Consequences

失うもの:

- semantic reuseによる追加Cost Reduction機会

得るもの:

- Cache Correctness Boundaryが説明可能
- Stale / invalid contextをFail Closedできる
- EvidenceとIdentityを結び付けやすい

## Evidence

- `docs/evidence/m6-cache.md`
- `docs/BENCHMARK.md`
- `stale-context-cache` fixed eval case
- capability ledger: `semantic_cache = deferred`

## Revisit Trigger

Semantic Cache Keyに必要なInvariantを明示し、False Reuseを測るEval Corpusを構築できた時。
