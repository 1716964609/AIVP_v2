# ADR-008 — Evaluation Precedes Routing Optimization

## Status

Accepted.

## Context

Reviewer CallやModel Callを減らすOptimizationは、Quality Regressionを同時に測れなければ安全に評価できない。

Call Countだけ減少しても、Expected HUMAN_REQUIREDをAUTO_FINISHEDへ誤変換する可能性がある。

## Decision

Risk / Model Routing Optimizationより先にFixed Evaluation HarnessをFreezeする。

Development Order:

```text
M7 Fixed Evaluation
        ↓
M8 Routing Optimization
```

Quality Gateを先に固定し、その後にEconomicsを改善する。

## Consequences

M8ではBroad LOW/LOW Review SkipをRejectできた。

その後、

```text
15 / 15 PASS preserved
Claude calls 31 -> 25
Total model calls 78 -> 72
```

を同時に示せた。

## Evidence

- `docs/EVALS.md`
- `docs/evidence/m7-eval.md`
- `docs/evidence/m8-routing-economics.md`
- `docs/BENCHMARK.md`

## Revisit Trigger

なし。Routing Strategyが変わっても「Eval before optimization」は維持する。
