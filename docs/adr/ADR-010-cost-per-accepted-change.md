# ADR-010 — Cost per Accepted Change as Economic North Star

## Status

Accepted with measurement caveat.

## Context

Model Callを減らすだけではEngineering Valueを測れない。

安いがWrongなChangeは価値がない。

そのためEconomic Metricは、

```text
Cost
    /
Accepted Change
```

としてQuality Outcomeと結び付ける必要がある。

## Decision

Cost per Accepted ChangeをAIVPのEconomic North Starとする。

ただし、Missing Provider Billing Evidenceを推定値や0へ変換しない。

## Current Measurement Boundary

M7 / M8では、

```text
Live Provider USD Cost = UNAVAILABLE
USD Cost per Accepted Change = UNAVAILABLE
```

である。

一方でResource Consumptionとして、

```text
Claude calls 31 -> 25
Total model calls 78 -> 72
15 / 15 PASS preserved
```

は測定済みである。

## Consequences

利点:

- QualityとCostを同じDecision Frameworkへ置ける
- Missing Economicsを誤魔化さない
- Provider Billingが取得できれば将来同じMetricへ接続できる

制約:

- 現在Dollar Cost Reduction PercentageはClaimしない

## Evidence

- `docs/BENCHMARK.md`
- `docs/evidence/m8-routing-economics.md`
- `docs/evidence/M10_CLAIM_EVIDENCE_MATRIX.md`

## Revisit Trigger

Provider Billing Evidenceが十分に取得できた時。
