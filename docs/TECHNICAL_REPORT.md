# AIVP v2 — Technical Report

## 1. このReportの目的

AIVP v2は、Coding Modelそのものを作るProjectではない。

目的は、

**AIがSoftware Changeを生成する時代に、Modelの外側にどのようなHarnessが必要になるか**

を、実装・Fault Test・Evaluation・Measurementを通じて検証することである。

AIVP v2の位置づけは、

**production-minded local-first coding-agent harness prototype**

である。

Production-grade Multi-user Platformそのものではない。

このReportでは、成功したFeatureだけではなく、

- 当初の仮説
- 実装上のDeviation
- RejectしたOptimization
- Negative Evidence
- Missing Data
- Known Limitation

も含めて記録する。

---

## 2. 問題設定

Code Generationの能力が上がるほど、System全体の価値はModel単体だけでは決まらなくなる。

実際のEngineering Systemでは、少なくとも次のControl Problemが残る。

```text
What should the model see?
What is the model allowed to do?
What has already completed?
Can execution resume after a crash?
What can be verified deterministically?
When is another model call worth paying for?
When must a human decide?
What evidence proves the system improved?
What resources can safely be deleted?
```

AIVP v2ではこれらを、

**Harness Problem**

として扱った。

---

## 3. 中心となる設計思想

AIVP v2のArchitectureは、次の原則へ収束した。

### Harness owns control

ModelはReasoningとGenerationを担当する。

Harnessは、

- state
- permission
- verification
- routing
- artifacts
- telemetry
- cleanup

を所有する。

### Deterministic before probabilistic

機械的に判定可能な処理に、不要なModel Callを使わない。

### Durable before clever

Agentの賢さを増やす前に、

- durable state
- checkpoint
- resume
- artifacts

を成立させる。

### Evidence before claim

```text
Implemented
    !=
Proven
    !=
Safe to claim publicly
```

として扱う。

### Preserve under ambiguity

Ownership、Integrity、Lifecycleが曖昧な場合は、

```text
delete / automate
```

ではなく、

```text
preserve / HUMAN_REQUIRED
```

側へ倒す。

---

## 4. Development Strategy

AIVP v2は、巨大なArchitectureを一度に完成させる方式ではなく、Milestone単位で構築した。

```text
M0  Baseline Freeze
 |
 v
M1  Harness Panel Refactor
 |
 v
M2  Durable Execution
 |
 v
M3  Containment
 |
 v
M4  Telemetry / Cost Ledger
 |
 v
M5  Context Compiler
 |
 v
M6  Cache
 |
 v
M7  Eval Harness
 |
 v
M8  Risk Routing / Economics
 |
 v
M9  Hardening / Garbage Collection
 |
 v
M10 Evidence / Publication
```

各Milestoneは、

```text
Plan
  ↓
Implementation
  ↓
Test / Measurement
  ↓
Deviation / Correction
  ↓
Exit Gate
  ↓
Frozen Tag
```

という形で進めた。

---

## 5. M0 — Baselineを先に凍結する

v2を始める前に、v1 baselineをGit上でFreezeした。

Frozen boundary:

```text
m0-baseline-frozen
```

目的は、後からv2が改善したように見せるために過去のBaselineを書き換えないことである。

Baselineを固定したことで、

```text
Before
vs
After
```

の比較対象を保つことができた。

---

## 6. M1 — OrchestratorからHarness Panelへ

v1はHistorical Compatibility Anchorとして保持し、

```text
src/aivp/legacy/orchestrator_v1.py
```

へ分離した。

v2では、

```text
application
panel
models
repository
risk
verification
artifacts
```

などのBoundaryを抽出した。

この段階で重要だったのは、Featureを増やすことより、

**Control Loopを分解し、責務をModelからHarnessへ移すこと**

だった。

M1 completion:

```text
m1-harness-panel-refactor
```

---

## 7. M2 — Durable Execution

次の問題はProcess Failureだった。

単純なAgent Loopでは、

```text
Generate
Verify
Review
```

の途中でProcessが落ちた場合、

```text
何が完了したか
何をやり直すべきか
```

をProcess Memoryだけでは説明できない。

M2では、

- explicit state machine
- SQLite durable state
- checkpoint
- artifact integrity
- resume planning
- task/config identity binding
- hard process crash recovery

を追加した。

主要Capability:

```text
SQLiteStateStore
DurableExecution
ResumePlan
```

設計の中心は、

```text
Process != Source of Truth
Durable State = Source of Recovery
```

である。

Completion:

```text
m2-durable-execution
```

---

## 8. M3 — Containment

Durableに動くだけでは十分ではない。

AgentがCanonical RepositoryやHost Environmentへ与えるblast radiusを制限する必要がある。

M3では、

- per-run Git worktree
- canonical / execution repository separation
- Docker verification sandbox
- default-deny capability policy
- deterministic diff guard

を導入した。

Conceptually:

```text
Canonical Repo
     |
     v
Per-run Worktree
     |
     v
Generated Change
     |
     v
Diff Guard
     |
     v
Docker Verification
```

Docker Sandboxには、

- network isolation
- non-root execution
- read-only root filesystem
- host environment isolation
- canonical repository hiding

に関するTest Evidenceがある。

ただしこれは、

**Complete Zero-trust Multi-tenant Isolation**

を意味しない。

Completion:

```text
m3-containment-complete
```

---

## 9. M4 — Telemetry / Cost Ledger

Optimizationを議論するには、まずMeasurementが必要になる。

M4では、

- durable model-call ledger
- provider token normalization
- pricing catalog
- OpenTelemetry substrate
- model-call tracing
- command tracing
- run tracing
- run summary
- privacy-safe telemetry

を追加した。

ここで採用した重要ルールは、

```text
Missing != Zero
Unknown != Free
```

である。

Provider側から取得できないBilling Dataを、

```text
0 USD
```

として扱わない。

これは後のM7/M8でも維持した。

Completion:

```text
m4-telemetry-cost-ledger-complete
```

---

## 10. M5 — Context Compiler

Large Repository全体を毎回Modelへ渡す方法は、Token、Noise、Latencyの観点から効率が悪い。

M5では、

- deterministic repository map
- relevant-file selector
- test association
- one-hop import neighbors
- context budget
- auditable manifest/hash

を持つContext Compilerを構築した。

### 最初のBenchmarkはRejectした

M5で最初に得られた高いCompression Ratioは、そのまま採用されなかった。

理由は、

**Compressionが高いこと自体はQuality Evidenceではない**

からである。

Retrieval Precisionを見直し、Primary TargetやRelevant Testが正しく含まれる形へ修正した。

最終Controlled Experimentでは、

```text
Provider input tokens
413,779
    ↓
110,790
```

となり、

```text
73.22% reduction
```

を観測した。

Quality Gateはpreserveされた。

一方で、Compiled Runは比較対象より約3.35秒遅かったため、

**M5ではLatency ImprovementをClaimしなかった。**

これがAIVP v2のEvidence Philosophyを強く形作った。

---

## 11. M6 — Cache

M5でContext Generationを構築すると、次にRepeated Computationが見えるようになった。

M6では、

- deterministic cache identity
- filesystem CAS
- SQLite cache metadata
- repository map cache
- context selection cache
- provider-cache-friendly prompt layout
- fail-closed stale-cache handling

を追加した。

### Harness-owned Cache Latency

Controlled Measurementでは、

```text
median miss: 133.203 ms
median hit:    8.242 ms
```

を観測した。

これは、

```text
16.162x
```

のmedian speedup、

```text
93.813%
```

のmedian context-preparation latency reductionに相当する。

これはLocal Controlled Benchmarkの結果であり、Production Workload全体のLatency Claimではない。

### Provider Prompt Cache

Controlled Provider Testでは、2回目のCallについて、

```text
input tokens: 22,052
cached tokens: 11,008
cached share: 49.918%
```

を観測した。

ただし、

**49.918%が一般的なGuaranteed Cache Hit Rateであるとは主張しない。**

### Semantic CacheはDeferred

M6ではSemantic Cacheを実装対象から外した。

Reasoning ResultをSemantic SimilarityだけでReuseすると、

- Task Invariant
- Repository State
- Business Rule
- Security Context

の違いを誤って無視する可能性がある。

そのため、

```text
semantic_cache = deferred
```

とした。

Completion:

```text
m6-cache-complete
```

---

## 12. M7 — Eval Harness

M6までの時点では、

```text
Systemが変わった
```

ことは分かっても、

```text
Qualityをpreserveできたか
```

を継続的に評価する固定Control Loopが不足していた。

M7では、

- Eval Case Schema
- Trial Runner
- Deterministic Graders
- Regrading
- Benchmark Reporting
- Fixed Suite
- One-command Suite Execution

を追加した。

Frozen Suite:

```text
evals/suites/m7-fixed.json
```

### Formal Result

M7 Formal Evaluation:

```text
15 / 15 cases PASS
27 trials / regrades
47 Codex calls
31 Claude calls
78 total model calls
7 fix iterations
14 AUTO_FINISHED
13 HUMAN_REQUIRED
1122.694 seconds observed wall time
```

### Raw Evidenceから再Gradeできる

Preserved ArtifactからOffline Regradeを行い、

```text
27 / 27 match
```

を確認した。

これはEvaluation自体を再実行しなくても、

**保存済みEvidenceからResultを再計算できる**

ことを意味する。

### Negative Runを削除しなかった

M7では途中のNegative RunもPreserveした。

最終結果を綺麗に見せるために、

```text
failed / error run
```

をHistoryから消すことはしなかった。

### USD Cost

Live-provider USD Cost Coverageは不足していた。

したがって、

```text
Cost per Accepted Change (USD)
=
UNAVAILABLE
```

とした。

Missing Costを0へ変換しなかった。

Completion:

```text
m7-eval-harness-complete
```

---

## 13. M8 — Risk Routing / Economics

M7のFixed Suiteができたことで、初めてRouting OptimizationをQuality Regressionと分離して評価できるようになった。

目的は、

**同じQuality Outcomeを維持したまま、不要なModel Callを削減できるか**

だった。

### Rejected Optimization

M8初期には、

```text
LOW / LOW risk
    ↓
review skip
```

というBroad Hypothesisを検討した。

しかし既存のCaseの中に、

```text
HUMAN_REQUIRED
```

を維持すべきケースが存在し、このPolicyでは安全にAUTO_FINISHEDへ倒れる可能性があった。

そのため、

**Broad LOW/LOW Skip HypothesisはIntegration前にRejectした。**

このNegative Resultは削除せず、Design Evidenceとして残した。

### Narrower Routing

その後、Optimizationをより限定した。

- safe terminal routing
- unchanged worktree fingerprint
- no-op repair detection
- downstream call reservation
- deterministic repair budgeting

など、よりDeterministicな条件へ絞った。

### Formal Comparison

Frozen M7 / M8比較:

| Metric | M7 | M8 |
|---|---:|---:|
| Fixed cases PASS | 15 / 15 | 15 / 15 |
| Trials | 27 | 27 |
| Codex calls | 47 | 47 |
| Claude calls | 31 | 25 |
| Total calls | 78 | 72 |
| Fix iterations | 7 | 7 |
| AUTO_FINISHED | 14 | 14 |
| HUMAN_REQUIRED | 13 | 13 |
| Wall time | 1122.694 s | 1036.739 s |

Observed Change:

```text
Claude calls
31 -> 25
-19.35%

Total model calls
78 -> 72
-7.69%
```

6件のNo-op Review-repair Artifactと、6回減少したClaude Callが対応した。

### Latency Caveat

Wall Clockは、

```text
1122.694
    ↓
1036.739 seconds
```

で、

```text
-85.955 seconds
-7.66%
```

だった。

しかしこれはPaired Observed Runである。

**差分全体をRoutingの純粋な因果効果とは扱わない。**

### Economics Caveat

M8でもLive-provider USD Cost Coverageは不足していた。

したがって、

```text
Cost per Accepted Change (USD)
=
UNAVAILABLE
```

を維持した。

Completion:

```text
m8-risk-routing-economics-complete
```

---

## 14. M9 — Hardening / Garbage Collection

長時間動くHarnessは、自分自身がHost Garbageを増やしてはいけない。

M9では、

- ownership classification
- bounded worktree cleanup
- bounded Docker cleanup
- cache GC
- artifact retention planner
- artifact retention executor
- terminal lifecycle hardening
- dry-run-first GC CLI
- interruption exit-gate tests

を追加した。

### Central Principle

```text
Delete less,
identify ownership first.
```

Resource Classification:

```text
AIVP-owned
Foreign
Unknown
```

Unknown OwnershipはDeleteしない。

### Lifecycle Safety

Cleanup判断を単純なFile Ageだけへ委ねず、

- terminal status
- resumability
- protected evidence
- worktree ownership
- dirty state

を考慮する。

### Default Behavior

```text
aivp gc --older-than 7d
```

はDry-run。

Destructive Cleanupには、

```text
--yes
```

が必要。

しかし `--yes` は、

```text
dirty worktree force deletion
```

を意味しない。

### Exit Gate

M9 completion evidence:

```text
415 unit tests PASS
8 / 8 GC fault / exit-gate tests PASS
```

さらにComponent Regressionとして、

```text
GC CLI                9 PASS
Worktree GC           8 PASS
Docker GC             7 PASS
Cache GC              8 PASS
Artifact Planner     10 PASS
Artifact Executor     8 PASS
```

を確認した。

Completion:

```text
m9-hardening-gc-complete
```

---

## 15. M10 — Evidence / Publication

M10ではCore Featureを増やすのではなく、

**既存のImplementationとEvidenceを、第三者が監査できる形へ変換する**

ことを目的としている。

Publication Pipeline:

```text
Git Source
   ↓
Frozen Evidence
   ↓
Claim / Evidence Matrix
   ↓
README
   ↓
Architecture
   ↓
Technical Report
   ↓
Benchmark / Security / Evals
   ↓
Reproducibility / Hygiene
```

Canonical Claim Registry:

```text
docs/evidence/M10_CLAIM_EVIDENCE_MATRIX.md
```

Public Claimは、

```text
PUBLIC
PUBLIC WITH CAVEAT
DO NOT CLAIM
```

へ分類する。

EvidenceへMappingできないClaimは、

- Evidenceを追加する
- Caveat付きHypothesisへ下げる
- 削除する

のいずれかとする。

---

## 16. Planned → Actual → Deviation

AIVP v2で重要だったのは、Planをそのまま実行することではない。

### M5

Planned:

```text
Reduce context aggressively
```

Initial Actual:

High Compression Ratio。

Problem:

Relevant Contextの選択品質が十分ではなかった。

Deviation:

Initial BenchmarkをRejectし、Retrieval Precisionを改善した。

### M6

Planned:

Cache repeated work。

Actual:

Deterministic Cacheは有効だった。

Deviation:

Semantic CacheはSafety Boundaryが弱いためDeferred。

### M7

Planned:

Fixed Eval Harness。

Actual:

正式Suiteを構築し15/15 PASS。

Deviation:

Negative Runsを削除せず、Missing USD CostもMissingのまま記録した。

### M8

Planned:

Risk RoutingでModel Call削減。

Initial Actual:

Broad LOW/LOW Skipはunsafe。

Deviation:

HypothesisをRejectし、よりDeterministicで狭いRoutingへ変更した。

### M9

Planned:

Host garbage cleanup。

Actual:

Ownership、Lifecycle、Resume、Protectionを考慮したBounded GCへ拡張した。

Deviation:

単純なAge-based Cleanupではなく、Fail-closed Retention Modelを採用した。

---

## 17. Negative Evidenceを残す理由

AIVP v2では、

```text
Failed Experiment
Rejected Hypothesis
Unavailable Data
```

をProject Historyから消さない。

理由は、Engineering DecisionのQualityは、

```text
最終結果
```

だけでなく、

```text
どの仮説を
何のEvidenceで
なぜ捨てたか
```

にも現れるからである。

Representative Negative Evidence:

```text
M5:
initial context benchmark rejected

M6:
semantic cache deferred

M7:
negative evaluation runs preserved

M7/M8:
USD cost unavailable

M8:
broad LOW/LOW skip rejected

M9:
unknown ownership preserved rather than deleted
```

---

## 18. QualityとEfficiencyを分離する

Optimizationでは、

```text
Fast
Cheap
Few Calls
```

だけを成功条件にしない。

M8のHard Gateは、

```text
15 / 15 fixed cases PASS
```

を維持することだった。

その上で、

```text
78 -> 72 model calls
```

を評価した。

つまり、

```text
Quality Gate
    ↓
Efficiency Optimization
```

の順番である。

これは、

```text
Efficiency improvement
```

を理由にQuality Regressionを正当化しないためである。

---

## 19. Missing Data Policy

AIVP v2で繰り返し採用したRule:

```text
Unknown != Zero
Unavailable != Free
Missing != Estimated Fact
```

例:

```text
Live provider USD billing
```

が欠落している場合、

```text
Cost = 0
```

とも、

```text
Estimated Cost = X
```

とも扱わない。

Public Claimでは、

```text
UNAVAILABLE
```

として保持する。

---

## 20. Human RequiredはFailureではない

AIVP v2では、

```text
AUTO_FINISHED
```

だけを成功とは定義していない。

Risk、Policy、Ambiguity、Budgetなどによって、

```text
HUMAN_REQUIRED
```

へEscalateすること自体がCorrect BehaviorとなるCaseがある。

M7/M8 Formal Suiteでは、

```text
AUTO_FINISHED   14
HUMAN_REQUIRED  13
```

というTrial-level Terminal Distributionが維持された。

Automation Rate最大化より、

**Wrong Automationを防ぐこと**

を優先している。

---

## 21. Local-firstというBoundary

AIVP v2はLocal-first Prototypeである。

そのため、現在証明している範囲は、

- local Git repository
- local SQLite
- local filesystem CAS
- local Docker
- CLI provider adapter
- local evaluation corpus

を中心とする。

現在証明していないもの:

```text
Distributed Worker Cluster
Multi-user Authentication
Enterprise RBAC
Multi-tenant Isolation
Remote Control Plane
24/7 HA State Store
Production SLO / On-call Operation
Automatic Production Deployment
```

---

## 22. Production-minded Prototypeという表現

AIVP v2を、

```text
production-grade system
```

とは呼ばない。

一方で、

```text
toy script
```

とも異なる。

Productionを意識したCharacteristicとして、

- explicit state machine
- durable resume
- fail-closed integrity
- blast-radius containment
- default-deny policy
- deterministic verification
- telemetry
- frozen evaluation
- negative evidence
- bounded GC

を実装・検証している。

したがって外部表現として、

**production-minded coding-agent harness prototype**

を採用する。

---

## 23. Evidence Summary

### M5

```text
Provider input
413,779 -> 110,790
73.22% reduction
```

Controlled Quality preserved。

Latency improvementはClaimしない。

### M6

```text
Cache miss median 133.203 ms
Cache hit median    8.242 ms

16.162x median speedup
93.813% median context-preparation reduction
```

Provider controlled observation:

```text
22,052 input tokens
11,008 cached tokens
49.918% cached
```

### M7

```text
15 / 15 cases PASS
27 trials
78 model calls
47 Codex
31 Claude
14 AUTO_FINISHED
13 HUMAN_REQUIRED
```

### M8

```text
15 / 15 cases PASS preserved

Claude
31 -> 25
-19.35%

Total model calls
78 -> 72
-7.69%
```

Observed wall time:

```text
1122.694 -> 1036.739 seconds
```

Causal Claimはしない。

### M9

```text
415 unit tests PASS
8 / 8 GC exit-gate fault tests PASS
```

---

## 24. Major Lessons

### 1. ModelよりHarnessが重要になる領域がある

Code Generationが強くなるほど、

```text
state
context
policy
verification
evaluation
economics
```

の価値が上がる。

### 2. Agentを増やせばよいわけではない

M8ではReviewer Callを増やすのではなく、

**必要ないCallを安全に削る**

ことで改善した。

### 3. EvalなしではOptimizationできない

M7 Fixed Suiteが存在したからこそ、

M8で、

```text
calls reduced
quality preserved
```

を同時に語れた。

### 4. Negative ResultはAssetになる

Rejected Hypothesisが残っていることで、

なぜ現在のDesignがConservativeなのか説明できる。

### 5. CleanupもArchitectureである

Long-running Automationでは、

```text
create resource
```

だけでなく、

```text
who owns it?
when can it be deleted?
what must survive?
```

までSystem Designに含まれる。

### 6. Claim ManagementもEngineeringである

M10では、

```text
READMEを書く
```

だけでなく、

```text
何を言ってよいか
何を言ってはいけないか
```

をEvidence Matrixとして管理した。

---

## 25. Known Limitations

Current Limitations:

- Local-first prototype
- Fixed Evaluation Corpusは15 cases
- General real-world coding accuracyを証明しない
- Live Provider USD Cost Coverageは不完全
- Wall-clock差分の純粋因果効果は証明していない
- Docker containmentはcomplete zero-trustではない
- Multi-user / Multi-tenant architectureは未実装
- Semantic CacheはDeferred
- Production deployment automationはScope外
- Production SLO / on-call evidenceは存在しない

---

## 26. Related Evidence

Project overview:

- [`../README.md`](../README.md)

As-Built Architecture:

- [`ARCHITECTURE.md`](ARCHITECTURE.md)

Claim Registry:

- [`evidence/M10_CLAIM_EVIDENCE_MATRIX.md`](evidence/M10_CLAIM_EVIDENCE_MATRIX.md)

Context Compiler:

- [`evidence/m5-context-compiler.md`](evidence/m5-context-compiler.md)

Cache:

- [`evidence/m6-cache.md`](evidence/m6-cache.md)

Evaluation:

- [`evidence/m7-eval.md`](evidence/m7-eval.md)

Routing / Economics:

- [`evidence/m8-routing-economics.md`](evidence/m8-routing-economics.md)

Hardening / GC:

- [`evidence/M9_GC_EXIT_GATE.md`](evidence/M9_GC_EXIT_GATE.md)

Project State:

- [`PROJECT_STATE.json`](PROJECT_STATE.json)

Capability Ledger:

- [`CAPABILITY_LEDGER.json`](CAPABILITY_LEDGER.json)

---

## 27. Conclusion

AIVP v2の中心的な成果は、

**AIがCodeを書けることを示したことではない。**

より重要なのは、

```text
AIが変更を提案する
        ↓
Harnessが状態を持つ
        ↓
Contextを制御する
        ↓
Permissionを制御する
        ↓
Deterministicに検証する
        ↓
Riskに応じてReasoning Costを配分する
        ↓
HumanへEscalateできる
        ↓
Evidenceとして保存する
        ↓
System自身が残したResourceまで安全に片付ける
```

というControl Systemを実装し、

その一部をFixed Evaluation、Fault Injection、Benchmarkによって検証したことである。

AIVP v2は完成したProduction Platformではない。

しかし、

**Coding Agentを単体Modelではなく、State・Policy・Evidence・Economicsを持つEngineering Systemとして扱う**

ための、実装済み・検証済みのPrototypeである。
