# AIVP v2 — Benchmark Report

## 1. この文書の目的

この文書は、AIVP v2で実際に保存されたBenchmark / Evaluation Evidenceを、第三者が比較しやすい形へ整理したものである。

新しいLive Benchmarkは実行していない。

M10では既存のFrozen Evidenceを再利用し、

```text
Measurement
    ↓
Scope
    ↓
Observed Result
    ↓
Caveat
    ↓
Public Claim
```

を分離する。

このReportは、

- M5 Context Compiler
- M6 Cache
- M7 Fixed Evaluation
- M8 Risk Routing / Economics

を主な対象とする。

M9はHardening / Fault Evidenceであり、Performance Benchmarkとは分離して扱う。

---

## 2. Benchmark Policy

AIVP v2では、Benchmark Resultを次のRuleで扱う。

### Rule 1 — Before / Afterを固定する

比較対象となるCode、Corpus、Task、Configが変わった場合は、単純なBefore / Afterとして扱わない。

### Rule 2 — Quality Gateを先に置く

Efficiency Improvementは、

```text
Quality preserved
```

を確認した上で評価する。

### Rule 3 — Missing Dataを0にしない

```text
UNAVAILABLE
```

は、

```text
0
```

ではない。

### Rule 4 — Controlled Measurementを一般化しない

Local Controlled BenchmarkをProduction Workload全体へ一般化しない。

### Rule 5 — Observed Wall TimeとCausal Effectを分離する

Elapsed Timeが短くなっても、その差分全体を単一Optimizationの因果効果とは扱わない。

---

## 3. Summary

| Area | Before | After | Observed Result | Claim Boundary |
|---|---:|---:|---:|---|
| M5 provider input tokens | 413,779 | 110,790 | -73.22% | Controlled context experiment |
| M6 local context cache median | 133.203 ms | 8.242 ms | 16.162x / -93.813% | Local context-preparation benchmark |
| M6 provider prompt cache | — | 11,008 / 22,052 cached tokens | 49.918% cached | Controlled second provider call |
| M7 fixed-suite quality | — | 15 / 15 PASS | PASS | Frozen 15-case suite |
| M7 total model calls | — | 78 | baseline | Frozen formal run |
| M8 fixed-suite quality | 15 / 15 | 15 / 15 | preserved | Same frozen suite |
| M8 Claude calls | 31 | 25 | -19.35% | Frozen M7 → M8 comparison |
| M8 total model calls | 78 | 72 | -7.69% | Frozen M7 → M8 comparison |
| M8 observed wall time | 1122.694 s | 1036.739 s | -7.66% | Observational, not pure causal estimate |
| USD Cost per Accepted Change | unavailable | unavailable | unavailable | Missing provider billing evidence |

---

## 4. M5 — Context Compiler

### 4.1 Question

M5で検証したQuestionは、

**Repository Contextをより選択的に構成し、Modelへ送るProvider Inputを減らせるか**

である。

Context Compilerは、

- repository map
- relevant-file selector
- test association
- one-hop import neighbors
- context budget

を利用する。

---

## 5. M5 — Initial BenchmarkをReject

M5では、最初に高いCompression Ratioを持つResultを得た。

しかし、そのResultはExit Evidenceとして採用されなかった。

理由は、

```text
high compression
    !=
high retrieval quality
```

だからである。

Primary TargetやRelevant Testを十分に選択できるようRetrievalを修正した後、Controlled Experimentをやり直した。

このRejected Resultを最終Benchmarkから削除して「最初から成功した」ことにはしていない。

---

## 6. M5 — Provider Input Result

Controlled Experiment:

```text
Before
413,779 provider input tokens

After
110,790 provider input tokens
```

Observed reduction:

```text
73.22%
```

Quality GateはControlled Case内でpreserveされた。

### Interpretation

Claimできること:

> Tested Context Compiler configurationでは、Controlled CaseのQuality Gateを維持しながらProvider Inputを73.22%削減した。

Claimしないこと:

> 任意のRepository、任意のTaskで常に73.22%削減できる。

---

## 7. M5 — Latency ResultはOptimization Claimにしない

Context Reductionが成功しても、Latencyまで必ず改善するわけではなかった。

Controlled Compiled Runは比較対象より約3.35秒遅かった。

したがってM5では、

```text
Context Token Reduction
```

はClaimしたが、

```text
End-to-end Latency Improvement
```

はClaimしなかった。

この分離は重要である。

```text
fewer tokens
    !=
automatically faster end-to-end execution
```

---

## 8. M5 Evidence

Primary Evidence:

- [`evidence/m5-context-compiler.md`](evidence/m5-context-compiler.md)
- [`milestones/M5.md`](milestones/M5.md)

Capability Ledger:

- `m5_controlled_context_reduction`

---

## 9. M6 — Harness-owned Local Cache

### 9.1 Question

Context CompilerのRepeated WorkをHarness-owned Cacheで削減できるかを検証した。

Cache Architecture:

```text
Filesystem CAS
      +
SQLite Metadata Index
```

主要Cache:

- Repository Map Cache
- Context Selection Cache
- Content-addressed Artifact Cache

---

## 10. M6 — Local Cache Latency

Controlled Local Benchmark:

```text
Median MISS
133.203 ms

Median HIT
8.242 ms
```

Observed ratio:

```text
16.162x median speedup
```

Observed reduction:

```text
93.813%
```

対象は、

**Context PreparationのLocal Controlled Benchmark**

である。

### Public Claim Boundary

Claimできること:

> Tested Local Cache pathでは、median context-preparation latencyが133.203 msから8.242 msへ低下した。

Claimしないこと:

> AIVP全体のProduction End-to-end Latencyが93.813%改善する。

---

## 11. M6 — Provider Prompt Cache

AIVPはPrompt Layoutを、

```text
stable prefix
    ↓
dynamic content
```

の順序へ寄せた。

Controlled Provider Testの2回目では、

```text
Input tokens
22,052

Cached tokens
11,008
```

を観測した。

Cached share:

```text
49.918%
```

### Interpretation

これは、

**Provider Prompt Cacheが実際にHitしたEvidence**

である。

ただし、

```text
49.918%
```

を一般的・恒常的なCache Hit Rateとは扱わない。

Provider Behavior、Prompt Identity、Repository State、Taskなどに依存する。

---

## 12. M6 — Semantic CacheをBenchmarkしなかった理由

Semantic CacheはM6でDeferredされた。

理由は、

```text
similar prompt
```

だけを根拠に過去ResultをReuseすると、

- business invariant
- security context
- repository state
- task intent

の違いを誤って無視する可能性があるためである。

したがって、

**Benchmark値を増やすためだけにSemantic Cacheを追加しなかった。**

---

## 13. M6 Evidence

Primary Evidence:

- [`evidence/m6-cache.md`](evidence/m6-cache.md)
- [`evidence/m6-cache-latency.json`](evidence/m6-cache-latency.json)
- [`evidence/m6-provider-cache.json`](evidence/m6-provider-cache.json)
- [`milestones/M6.md`](milestones/M6.md)

Capability Ledger:

```text
m6_local_cache_latency_evidence
m6_provider_prompt_cache_hit
```

---

## 14. M7 — Fixed Evaluation Baseline

### 14.1 Why

M5 / M6までは、個別OptimizationのControlled Evidenceは存在した。

しかし、

```text
Harness全体を変更したとき、
既存Behaviorを壊していないか
```

を比較する固定Control Loopが不足していた。

M7では15-case Fixed SuiteをFreezeした。

Suite:

```text
evals/suites/m7-fixed.json
```

---

## 15. M7 — Frozen Identity

Formal Run:

```text
m7-final-clean-20261004-072204
```

Frozen implementation baseline:

```text
891655b84060186f6019bd43a2273d204574dc13
```

Frozen corpus commit:

```text
54500b1
```

Completion:

```text
m7-eval-harness-complete
```

この固定Identityにより、M8のBeforeとしてM7を利用できた。

---

## 16. M7 — Quality Result

Formal Fixed-suite Result:

```text
15 cases
15 PASS
0 FAIL
0 ERROR
```

Trials / Regrades:

```text
27
```

Offline Regrade:

```text
27 matches
0 mismatches
```

Unit / Integration at completion:

```text
323 unit tests PASS
11 integration tests PASS
```

このResultは、

**Frozen 15-case Suiteに対するQuality Evidence**

である。

任意のReal-world Coding Task全体のAccuracyを意味しない。

---

## 17. M7 — Routing / Economics Baseline

M7 Formal Run:

```text
Codex calls
47

Claude calls
31

Total model calls
78

Fix iterations
7

AUTO_FINISHED
14

HUMAN_REQUIRED
13

Observed suite wall time
1122.694 seconds
```

この値をM8 Before BaselineとしてFreezeした。

---

## 18. M7 — HUMAN_REQUIREDの解釈

`HUMAN_REQUIRED` はFailureではない。

Policy、Risk、Budget、Ambiguityによって、

```text
Human judgment is required
```

と判断すること自体がCorrect OutcomeとなるCaseがある。

したがって、

```text
AUTO_FINISHEDを増やす
```

ことだけをOptimization Objectiveにはしない。

M7 Baseline:

```text
AUTO_FINISHED  14
HUMAN_REQUIRED 13
```

---

## 19. M7 — USD Cost

Live-provider USD Cost Coverageは不足していた。

そのため、

```text
Cost per Accepted Change (USD)
=
UNAVAILABLE
```

と記録した。

次の変換は行わない。

```text
missing
    ↓
0 USD
```

または、

```text
missing
    ↓
model-generated estimate
```

---

## 20. M7 Evidence

Primary Evidence:

- [`evidence/m7-eval.md`](evidence/m7-eval.md)
- [`evidence/m7-eval-summary.json`](evidence/m7-eval-summary.json)
- [`milestones/M7.md`](milestones/M7.md)
- [`exec-plans/completed/M7-eval.md`](exec-plans/completed/M7-eval.md)

---

## 21. M8 — Risk Routing / Economics

### 21.1 Question

M8では、

**M7 Frozen Quality Outcomeを維持したまま、不要なReasoning Costを削減できるか**

を検証した。

重要なのは順序である。

```text
Quality Gate
    ↓
Routing Optimization
```

であり、

```text
Fewer Calls
    ↓
Quality is probably okay
```

ではない。

---

## 22. M8 — Rejected Broad LOW/LOW Optimization

初期Hypothesis:

```text
LOW / LOW risk
     ↓
skip review
```

このPolicyは採用されなかった。

既存Corpusには、

```text
HUMAN_REQUIRED
```

を維持すべきCaseが存在したためである。

Broad Skipを適用すると、Correct Human EscalationをAUTO_FINISHEDへ変える可能性があった。

したがって、

**Integration前にRejectした。**

その後は、

- deterministic safe terminal routing
- unchanged worktree fingerprint
- no-op repair detection
- call-budget reservation

など、より狭く説明可能なOptimizationへ移行した。

---

## 23. M8 — Quality Comparison

| Metric | M7 | M8 |
|---|---:|---:|
| Fixed cases | 15 | 15 |
| PASS | 15 | 15 |
| FAIL | 0 | 0 |
| ERROR | 0 | 0 |
| Trials | 27 | 27 |
| Fix iterations | 7 | 7 |
| AUTO_FINISHED | 14 | 14 |
| HUMAN_REQUIRED | 13 | 13 |

Hard Quality Gate:

```text
15 / 15 PASS
```

をpreserveした。

---

## 24. M8 — Model Call Comparison

| Metric | M7 | M8 | Delta |
|---|---:|---:|---:|
| Codex calls | 47 | 47 | 0 |
| Claude calls | 31 | 25 | -6 |
| Total model calls | 78 | 72 | -6 |

Claude call change:

```text
31
 ↓
25

-6
-19.35%
```

Total model call change:

```text
78
 ↓
72

-6
-7.69%
```

Codex Calls:

```text
47
 ↓
47

0
```

---

## 25. M8 — Regression Boundary

M8 completion時の通常RegressionもPASSしている。

```text
349 unit tests PASS
11 integration tests PASS
git diff --check PASS
```

これはRouting Optimizationを導入した状態で、Fixed Evaluationだけではなく既存Regression Suiteも通過していたことを示す。

ただし、Unit / Integration Test CountそのものをPerformance Metricとして扱うものではない。

## 26. M8 — Mechanism Evidence

M8では6件のNo-op Review-repair Artifactが観測された。

同じFormal ComparisonでClaude Callも6回減少した。

```text
No-op review-repair artifacts
6

Claude call reduction
6
```

この一致は、実装されたNo-op Routing MechanismとObserved Call Reductionが整合しているEvidenceである。

ただし、これをあらゆるWorkloadに対するUniversal Cost Reduction Lawとして扱わない。

---

## 27. M8 — Observed Wall Clock

Observed M7:

```text
1122.694 seconds
```

Observed M8:

```text
1036.739 seconds
```

Difference:

```text
-85.955 seconds
-7.66%
```

これはPaired Formal Runsで観測された値である。

### Caveat

この差分全体を、

```text
Risk Routingによる純粋な因果効果
```

とは主張しない。

External Provider LatencyやExecution Varianceを完全には分離していないためである。

したがってPublic Wordingは、

> M8 formal runではM7 formal runより7.66%短いsuite wall timeを観測した。

までとする。

---

## 28. M8 — USD Economics

Live-provider USD Cost CoverageはM8でも不足していた。

したがって、

```text
Live provider USD cost
=
UNAVAILABLE

Cost per Accepted Change USD
=
UNAVAILABLE
```

である。

M8で証明したEconomicsは、

**Model Call Resource Consumptionの削減**

であり、

**Dollar Cost Reduction Percentage**

ではない。

---

## 29. M8 Evidence

Primary Evidence:

- [`evidence/m8-routing-economics.md`](evidence/m8-routing-economics.md)
- [`evidence/m8-routing-economics-summary.json`](evidence/m8-routing-economics-summary.json)
- [`milestones/M8.md`](milestones/M8.md)
- [`exec-plans/completed/M8-routing-economics.md`](exec-plans/completed/M8-routing-economics.md)

---

## 30. M7 → M8 Headline Comparison

| Metric | M7 | M8 | Interpretation |
|---|---:|---:|---|
| Fixed-suite PASS | 15 / 15 | 15 / 15 | Quality gate preserved |
| Trials | 27 | 27 | Same suite boundary |
| Codex calls | 47 | 47 | unchanged |
| Claude calls | 31 | 25 | -19.35% |
| Total model calls | 78 | 72 | -7.69% |
| Fix iterations | 7 | 7 | unchanged |
| AUTO_FINISHED | 14 | 14 | unchanged |
| HUMAN_REQUIRED | 13 | 13 | unchanged |
| Wall time | 1122.694 s | 1036.739 s | -7.66% observed |
| USD Cost / Accepted Change | unavailable | unavailable | no dollar claim |

最も重要な結果は、

```text
Quality Outcome preserved
        +
Reviewer Calls reduced
```

である。

---

## 31. M9はPerformance Benchmarkではない

M9の主要Evidenceは、

```text
415 unit tests PASS
8 / 8 fault / exit-gate tests PASS
```

である。

これは、

- cleanup safety
- resumable preservation
- ownership handling
- idempotency
- dry-run-first behavior

を検証するHardening Evidenceである。

M9の目的はPerformance Improvementではないため、このBenchmark ReportではPerformance Speedupとして扱わない。

Evidence:

- [`evidence/M9_GC_EXIT_GATE.md`](evidence/M9_GC_EXIT_GATE.md)

---

## 32. Cross-Milestone Interpretation

AIVP v2のOptimization Storyは、

```text
M5
Reduce unnecessary context
        ↓
M6
Reduce repeated context computation
        ↓
M7
Freeze quality evaluation
        ↓
M8
Reduce unnecessary reviewer reasoning
```

と整理できる。

対象にしているResourceが異なる。

```text
M5 = provider input
M6 = context preparation / prompt caching
M7 = quality measurement baseline
M8 = model-call routing
```

したがって、異なるMetricを一つのPercentageへ合成しない。

---

## 33. Benchmark Resultを合算しない理由

例えば、

```text
M5 -73.22%
M6 -93.813%
M8 -7.69%
```

を足して、

```text
AIVP is X% more efficient
```

とは言えない。

それぞれ分母が異なるためである。

- Provider input tokens
- Context-preparation latency
- Model-call count

は別Metricである。

Benchmark Reportでは、これらを独立して保持する。

---

## 34. Reproducibility Boundary

M10ではFrozen Evidenceを優先する。

理由は、Live Provider Benchmarkを無意味に再実行すると、

- provider model revision
- service latency
- quota
- external state
- billing environment

が変化し、Historical Comparison Boundaryを壊す可能性があるためである。

M7 / M8 Formal Resultは、当時のFrozen IdentityとRaw Artifactを基準に読む。

---

## 35. Public Claims

Evidenceから直接SupportできるClaim:

```text
M5:
Controlled context experimentで
provider input 413,779 -> 110,790
(-73.22%)

M6:
Controlled local cache benchmarkで
median 133.203 ms -> 8.242 ms
(16.162x / -93.813%)

M6:
Controlled provider observationで
11,008 / 22,052 input tokens cached
(49.918%)

M7:
Frozen suite 15 / 15 PASS

M8:
15 / 15 PASS preserved
Claude calls 31 -> 25
Total model calls 78 -> 72

M9:
415 unit tests PASS
8 / 8 GC exit-gate fault tests PASS
```

---

## 36. Claims We Do Not Make

このReportから次を導かない。

```text
AIVP is 73.22% faster overall
AIVP is 93.813% cheaper overall
Provider cache always hits 49.918%
M8 reduced dollar cost by 7.69%
M8 routing caused all of the 7.66% wall-time reduction
15 test cases equal general coding accuracy
Local cache benchmark equals production workload performance
```

---

## 37. Source of Truth

Publication claims:

- [`evidence/M10_CLAIM_EVIDENCE_MATRIX.md`](evidence/M10_CLAIM_EVIDENCE_MATRIX.md)

Technical interpretation:

- [`TECHNICAL_REPORT.md`](TECHNICAL_REPORT.md)

As-Built Architecture:

- [`ARCHITECTURE.md`](ARCHITECTURE.md)

Public overview:

- [`../README.md`](../README.md)

Project state:

- [`PROJECT_STATE.json`](PROJECT_STATE.json)

Capability ledger:

- [`CAPABILITY_LEDGER.json`](CAPABILITY_LEDGER.json)

---

## 38. Conclusion

AIVP v2のBenchmarkから読み取れるのは、

**単一の「速くなった」というStoryではない。**

より正確には、

```text
M5:
Modelへ送るContext量を減らした

M6:
同じContext Preparationの再計算を減らした

M7:
Qualityを固定して測れるようにした

M8:
不要なReviewer Reasoningを減らした
```

という異なるOptimization Layerがある。

そして、それぞれについて、

```text
What was measured?
What was preserved?
What remains unknown?
```

を分離してEvidenceを残した。

AIVP v2のBenchmark Philosophyは、

**数字を大きく見せることではなく、数字が何を意味し、何を意味しないかまで固定すること**

である。
