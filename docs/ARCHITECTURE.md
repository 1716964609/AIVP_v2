# AIVP v2 — As-Built Architecture

## この文書の位置づけ

この文書は、AIVP v2の**理想設計図**ではなく、現在のSource Codeから確認できる**As-Built Architecture**を説明します。

Source of Truthの優先順位は次の通りです。

```text
Git Source / Frozen Tag
        ↓
Raw Test / Evaluation Evidence
        ↓
PROJECT_STATE / CAPABILITY_LEDGER
        ↓
Architecture / README / Technical Report
```

したがって、この文書と実装が矛盾した場合は、Git SourceとFrozen Evidenceを優先します。

AIVP v2の位置づけは、

**production-minded local-first coding-agent harness prototype**

です。

Production-grade Multi-user Service、Complete Zero-trust Platform、Distributed Worker Platformであるとは主張しません。

---

## 1. Architecture Summary

AIVP v2は、Coding Modelそのものではなく、その外側にある**Harness Panel**を中心に構成されています。

Harness Panelが所有する責務は大きく次の通りです。

- Run lifecycle
- Durable state
- Context construction
- Cache
- Repository containment
- Model invocation
- Deterministic verification
- Capability policy
- Risk routing
- Human escalation
- Artifact / telemetry recording
- Evaluation
- Garbage collection

論理的な全体像は次のように整理できます。

```text
                         User / CLI
                             |
             +---------------+---------------+
             |                               |
             v                               v
        Normal Run                     Maintenance GC
             |                               |
             v                               v
       Application Layer                GC Command
             |
             v
       Harness Panel
             |
   +---------+----------+-----------+-------------+
   |                    |                         |
   v                    v                         v
Durable State      Context / Cache          Containment
   |                    |                         |
   |                    v                         |
   |               Model Adapters                 |
   |                    |                         |
   |                    v                         |
   |            Deterministic Verify <------------+
   |                    |
   |                    v
   |              Policy / Risk
   |                    |
   |                    v
   |          AUTO_FINISHED /
   |          HUMAN_REQUIRED
   |                    |
   +--------------------+
             |
             v
     Artifacts / Telemetry


Evaluation Harness
      |
      +----> Fixed Cases
      +----> Harness Run
      +----> Grading
      +----> Benchmark / Regrade
```

この図は**Logical Architecture**です。

PythonのすべてのFunction Callを一対一で表すLiteral Call Graphではありません。

---

## 2. Public Entry Points

Public CLIは、

```text
aivp run
aivp eval
aivp gc
aivp resume
```

の4系統です。

Entry pointは、

```text
src/aivp/cli.py
```

です。

Package metadata上では、

```text
aivp = "aivp.cli:main"
```

として公開されています。

CLIから主要Application Boundaryへ処理を渡します。

As-Built Source上ではCLIが少なくとも次の領域を参照しています。

```text
aivp.application
aivp.eval.suite
aivp.maintenance.gc_command
aivp.structured
```

Normal Harness Execution、Evaluation、Maintenance GCを同じ巨大なOrchestratorへ押し込めず、入口を分離しています。

---

## 3. Application Layer

Primary application boundary:

```text
src/aivp/application.py
```

主要な役割は、CLIと内部Harness Executionの間に立ち、

- new run
- resume
- repository/worktree preparation
- state store
- runtime construction
- Harness Panel invocation

などをつなぐことです。

Sourceには、

```text
run_new(...)
```

が存在します。

Application Layerは、CLI Argument ParsingそのものとHarness Panel内部のCoding Workflowを分離するBoundaryとして扱います。

---

## 4. Harness Panel

中心となるOrchestration実装は、

```text
src/aivp/panel/orchestrator.py
```

です。

主要Entry:

```text
run_panel(...)
```

Harness Panelは、単にModelを順番に呼ぶだけではありません。

Run中に必要となる、

- artifact registration
- context preparation
- checkpoint-aware resume
- generation
- deterministic verification
- review
- risk evaluation
- routing
- terminal decision
- metrics
- human review artifact
- status artifact

などを統合します。

関連Module:

```text
src/aivp/panel/config.py
src/aivp/panel/task.py
src/aivp/panel/prompts.py
src/aivp/panel/budget_routing.py
src/aivp/panel/reporting.py
```

### Design Principle

```text
Model = reasoning / generation component

Harness Panel = execution control owner
```

という責務分離を採用しています。

Model自身に、

- durable state
- permission decision
- filesystem ownership
- cleanup decision
- terminal outcome

を全面的に委譲しません。

---

## 5. Durable Execution / State

State subsystem:

```text
src/aivp/state/
```

主要Module:

```text
base.py
checkpoint.py
durable.py
hashing.py
integrity.py
machine.py
records.py
resume.py
sqlite.py
```

主要Type:

```text
DurableExecution
SQLiteStateStore
RunState
Transition
ResumePlan
StepRecord
ArtifactRecord
```

Durable Executionでは、次を分離します。

```text
Current State
    |
    +---- Runが現在どこにいるか

Checkpoint
    |
    +---- 何がdurableに保存されたか

Resume Plan
    |
    +---- どこから安全に再開可能か

Artifact Record
    |
    +---- どのEvidenceがRunに属するか
```

### SQLite

Durable metadataはSQLite State Storeによって管理されます。

Local-first Prototypeとして、

- external database service
- distributed consensus
- remote state service

を前提にしません。

一方で、

- integrity validation
- explicit terminalization
- resume checkpoint
- state transition

をHarness側で所有します。

---

## 6. Runtime / Budgets

Execution runtime:

```text
src/aivp/execution/runtime.py
```

主要Type:

```text
Runtime
Budgets
Counters
```

Runtimeは、Harness Run中に必要なExecution ContextとBudget / Counter情報を保持します。

Budgetは単なるAccounting用途ではなく、

**「これ以上AI reasoningを継続してよいか」**

というRouting Decisionにも関係します。

Budget Routingには、

```text
src/aivp/panel/budget_routing.py
```

が存在します。

---

## 7. Repository Containment

Containment subsystem:

```text
src/aivp/containment/
```

### Git Worktree

```text
src/aivp/containment/worktree.py
```

主要Type:

```text
RunWorktree
```

主要Operation:

```text
create_run_worktree(...)
validate_run_worktree(...)
```

Per-run Git Worktreeによって、Modelが直接Canonical Repository上で作業することを避けます。

Validationでは、

- worktree path
- canonical repository ownership
- Git common directory
- base SHA

などを確認します。

Conceptually:

```text
Canonical Repository
        |
        +---- Base SHA
                 |
                 v
          Per-run Worktree
                 |
                 v
          Agent-generated Change
```

### Docker Sandbox

```text
src/aivp/containment/docker_sandbox.py
```

主要Type:

```text
DockerSandbox
DockerSandboxPolicy
```

Docker-based VerificationはLocal Executionのblast radiusを制限するための一層です。

これはComplete Zero-trust Isolationの証明ではありません。

---

## 8. Context Compiler

Context subsystem:

```text
src/aivp/context/
```

主要Module:

```text
association.py
base.py
budget.py
compiler.py
imports.py
repo_map.py
selector.py
```

主要Data Structure:

```text
ContextBudget
ContextRequest
ContextEntry
ContextArtifact
ContextCompilation
```

Context Compilerの目的は、

**Repository全体を毎回そのままModelへ渡すこと**

ではありません。

Taskに関連する情報を選択し、Context Budgetの中で構成します。

Logical flow:

```text
Repository
    |
    v
Repo Map
    |
    +---- Imports
    +---- Test Association
    +---- Selection Candidate
    |
    v
Context Budget
    |
    v
Context Artifact
    |
    v
Prompt
```

---

## 9. Cache Architecture

Cache subsystem:

```text
src/aivp/cache/
```

主要Module:

```text
base.py
cas.py
context_selection.py
index.py
repo_map.py
```

主要Type:

```text
ContentAddressedCache
SQLiteCacheIndex
ContextSelectionCache
RepoMapCache
ContextCacheIdentity
```

Architectureは、

```text
Filesystem CAS
      +
SQLite Metadata Index
```

を基本形とします。

Logical flow:

```text
Repository / Task Identity
          |
          v
    Cache Identity
          |
       +--+--+
       |     |
      HIT   MISS
       |     |
       |     v
       | Context Compile
       |     |
       |     v
       +--> CAS + Index
              |
              v
       Context Artifact
```

Cache Integrityが壊れている場合に、無条件でFallbackして問題を隠す設計ではありません。

M6ではFail-closed integrity behaviorをEvidenceとして残しています。

---

## 10. Model Adapter Boundary

Model subsystem:

```text
src/aivp/models/
```

主要Module:

```text
base.py
codex.py
codex_adapter.py
claude.py
claude_adapter.py
parsing.py
```

Common abstraction:

```text
ModelAdapter
ModelRequest
ModelResult
```

Concrete adapter:

```text
CodexAdapter
ClaudeAdapter
```

Harness PanelはProvider-specific behaviorを直接全体へ拡散させず、Adapter Boundaryを持ちます。

概念的には、

```text
Harness Panel
      |
      v
ModelAdapter
   /      \
  v        v
Codex    Claude
```

です。

Provider ResponseはParsing Boundaryを経由し、Harness側のStructured Decisionへ変換されます。

---

## 11. Deterministic Verification

Verification subsystem:

```text
src/aivp/verification/
```

主要Module:

```text
base.py
deterministic.py
diff_guard.py
```

主要Type:

```text
Verifier
DeterministicVerifier
VerificationRuntime
```

基本原則は、

**Model Reviewより前に、機械的に判定できることを機械的に判定する**

ことです。

例:

```text
Generated Change
      |
      v
Diff Guard
      |
      v
Deterministic Verification
      |
   +--+--+
   |     |
 PASS   FAIL
   |     |
   |     +---- Repair / Human / Terminal Policy
   |
   v
Risk / Review Routing
```

Deterministic VerificationはDocker Sandboxと組み合わせて利用可能です。

---

## 12. Capability Policy

Policy subsystem:

```text
src/aivp/policy/
```

主要Module:

```text
capability.py
```

主要Type:

```text
Capability
Decision
CapabilityRequest
StaticCapabilityPolicy
```

Policy Layerの目的は、

**Modelが「やりたい」と出力したことと、Harnessが「許可する」ことを分離する**

ことです。

Conceptually:

```text
Requested Capability
        |
        v
Capability Policy
     /      \
 ALLOW      DENY
              |
              v
        PolicyDenied
```

Prompt InstructionだけをSecurity Controlとして扱いません。

---

## 13. Risk Engine / Routing

Risk subsystem:

```text
src/aivp/risk/
```

主要Module:

```text
aggregate.py
base.py
engine.py
routing.py
rules.py
```

主要Type:

```text
RiskEngine
LegacyCompatibleRiskEngine
RiskRoutingDecision
```

Risk-aware Routingでは、すべてのChangeに同じReview Costを払うのではなく、

```text
Change
  |
  v
Deterministic Evidence
  |
  v
Risk Evaluation
  |
  +------ Low / deterministic-safe
  |             |
  |             v
  |        expensive reviewを省略可能
  |
  +------ Review required
  |             |
  |             v
  |        independent model review
  |
  +------ Human required
                |
                v
          HUMAN_REQUIRED
```

というDecision Boundaryを持ちます。

M8では、このRouting OptimizationについてFrozen Evaluation Evidenceを残しています。

---

## 14. Artifact Registry / Reporting

Artifact subsystem:

```text
src/aivp/artifacts/
```

主要Module:

```text
io.py
registry.py
```

主要Type:

```text
ArtifactRegistry
```

Run中に生成されたEvidenceはRun Directoryへ記録されます。

確認されている代表Artifactには、

```text
effective-config.json
task.json
task.txt
context.txt
metrics.json
status.json
human-review.md
```

などがあります。

Artifactは単なるLogではなく、

**Runを後から説明・検証するためのEvidence Surface**

として扱います。

---

## 15. Telemetry

Telemetry subsystem:

```text
src/aivp/telemetry/
```

主要Module:

```text
pricing.py
tracing.py
```

主要Type:

```text
PricingCatalog
TracingSession
JsonlSpanExporter
```

Harnessが観測可能な範囲で、

- latency
- model call
- token usage
- step execution
- provider usage evidence

などを記録します。

重要なルールは、

```text
Unknown != Zero
Missing != Estimated Fact
```

です。

Provider Cost Coverageがない場合、推測したUSD値をMeasured Factとして扱いません。

---

## 16. Evaluation Harness

Evaluation subsystem:

```text
src/aivp/eval/
```

主要Module:

```text
case.py
runner.py
suite.py
graders.py
regrade.py
benchmark.py
```

主要Type / Entry:

```text
EvalCase
EvalExecution
EvalSuite
SuiteExecution
GradeResult
RegradeExecution
BenchmarkExecution

run_eval_case(...)
run_eval_suite(...)
```

Evaluationは通常Runの内部だけではなく、**Harnessそのものを外側から評価するControl Loop**です。

```text
Fixed Eval Case
      |
      v
Harness Run
      |
      v
Artifacts / Outcome
      |
      v
Grader
      |
   +--+--+
   |     |
 PASS   FAIL / Regrade
   |
   v
Benchmark Evidence
```

RepositoryにはFrozen 15-case Suiteがあります。

```text
evals/suites/m7-fixed.json
```

このEvaluationは、

- happy path
- specification conflict
- forbidden capability
- process crash / resume
- malformed model output
- budget exhaustion

などを含みます。

---

## 17. Maintenance / Garbage Collection

Maintenance subsystem:

```text
src/aivp/maintenance/
```

主要Module:

```text
gc.py
gc_command.py
worktree_gc.py
docker_gc.py
cache_gc.py
artifact_retention.py
artifact_retention_executor.py
```

主要Type / Entry:

```text
Ownership
Classification
PlannedAction
ResourceFacts
GCDecision

ArtifactRetentionFacts
ArtifactRetentionDecision
ArtifactRetentionExecutionResult

WorktreeCleanupResult
DockerCleanupResult
CacheGCResult

run_gc(...)
```

M9の中心原則は、

**Delete less, identify ownership first.**

です。

Logical flow:

```text
Resource
   |
   v
Ownership Classification
   |
   +---- FOREIGN ------> PRESERVE
   |
   +---- UNKNOWN ------> PRESERVE
   |
   +---- AIVP
           |
           v
     Lifecycle / Age
           |
       +---+---+
       |       |
   Protected  Expired
       |       |
       v       v
   PRESERVE   GC Candidate
                 |
                 v
        dry-run by default
                 |
          explicit --yes
                 |
                 v
         bounded deletion
```

Destructive Executionでも、Dirty Worktreeを自動的にforce-deleteする設計ではありません。

---

## 18. Normal Run — Logical Data Flow

Normal RunのArchitectureを、Literal Call GraphではなくLogical Flowとしてまとめると次のようになります。

```text
CLI
 |
 v
Application
 |
 +---- Load Task / Config
 |
 +---- Open State Store
 |
 +---- Create / Validate Per-run Worktree
 |
 +---- Build Runtime
 |
 v
Harness Panel
 |
 +---- Durable State / Resume Checkpoint
 |
 +---- Context Compiler / Cache
 |
 +---- Model Generation
 |
 +---- Repository Diff
 |
 +---- Deterministic Verification
 |
 +---- Capability Policy
 |
 +---- Risk / Review Routing
 |
 +---- Repair Budget
 |
 +---- Terminal Decision
 |
 +---- Artifact / Metrics / Status
 |
 v
AUTO_FINISHED
or
HUMAN_REQUIRED
```

各Stage間ではDurable StateとArtifact Evidenceを残すことを重視しています。

---

## 19. Resume Architecture

Resumeは単純にProcessを再起動することとは異なります。

```text
Previous Process Dies
        |
        v
SQLite Durable State
        +
Checkpoint
        +
Run Artifact
        |
        v
Integrity Validation
        |
        v
Resume Plan
        |
        v
Existing Worktree / Run Directory
        |
        v
Continue from Durable Boundary
```

Process Memoryではなく、

**Durable Evidenceを再開判断の根拠にする**

ことが設計上の重要点です。

---

## 20. Failure Bias

AIVP v2では、曖昧な状態でAggressive Automationへ進むより、

```text
ambiguity
   |
   v
preserve
or
HUMAN_REQUIRED
```

へ倒す設計を複数箇所で採用しています。

例:

- unknown ownership → preserve
- dirty worktree → preserve
- state integrity problem → fail closed
- unsupported capability → deny / escalate
- uncertain terminal condition → human review

これはAvailability最大化よりも、

**irreversible mistakeを避ける**

方向へBiasを置く選択です。

---

## 21. Legacy Boundary

Repositoryには、

```text
src/aivp/legacy/orchestrator_v1.py
```

が残っています。

これはv1由来のHistorical / Compatibility Boundaryであり、v2のArchitecture説明ではPrimary Harness Panelとして扱いません。

v2の中心は、

```text
src/aivp/panel/
src/aivp/application.py
src/aivp/state/
```

を中心とする構造です。

---

## 22. Architecture → Evidence Mapping

Architecture ComponentとEvidenceの関係は次のように整理できます。

| Architecture Area | Representative Evidence |
|---|---|
| Durable State / Resume | state / resume unit tests, process-resume integration test |
| Worktree Containment | worktree / fingerprint / application-worktree tests |
| Docker Sandbox | Docker sandbox / verification integration tests |
| Context Compiler | `docs/evidence/m5-context-compiler.md` |
| Cache | `docs/evidence/m6-cache.md` |
| Provider Prompt Cache | `docs/evidence/m6-provider-cache.json` |
| Evaluation Harness | `docs/evidence/m7-eval.md` |
| Risk Routing | `docs/evidence/m8-routing-economics.md` |
| Bounded GC | `docs/evidence/M9_GC_EXIT_GATE.md` |

Architecture Document単体をProofとは扱いません。

ProofはSource、Test、Frozen Evidenceへ遡ります。

---

## 23. Architecture上の意図的な非目標

現在のAIVP v2は、次をAs-Built Capabilityとして持つとは主張しません。

```text
Distributed Worker Cluster
Multi-user Authentication
Enterprise RBAC
Remote SaaS Control Plane
Kubernetes Runtime
Automatic Production Deployment
Production Secret Management Platform
Multi-tenant Isolation
24/7 HA State Store
Production SLO / On-call System
```

これらはArchitecture Diagramへ「将来あり得るもの」として薄く描くこともしません。

**実装されていないものをAs-Built Diagramへ混ぜない**

ためです。

---

## 24. Package Map

```text
src/aivp/
├── application.py
├── cli.py
│
├── panel/
│   ├── orchestrator.py
│   ├── config.py
│   ├── task.py
│   ├── prompts.py
│   ├── reporting.py
│   └── budget_routing.py
│
├── state/
│   ├── durable.py
│   ├── sqlite.py
│   ├── checkpoint.py
│   ├── resume.py
│   ├── integrity.py
│   ├── machine.py
│   ├── records.py
│   └── hashing.py
│
├── context/
│   ├── compiler.py
│   ├── selector.py
│   ├── repo_map.py
│   ├── imports.py
│   ├── association.py
│   ├── budget.py
│   └── base.py
│
├── cache/
│   ├── cas.py
│   ├── index.py
│   ├── context_selection.py
│   ├── repo_map.py
│   └── base.py
│
├── containment/
│   ├── worktree.py
│   └── docker_sandbox.py
│
├── models/
│   ├── base.py
│   ├── codex_adapter.py
│   ├── claude_adapter.py
│   └── parsing.py
│
├── verification/
│   ├── deterministic.py
│   ├── diff_guard.py
│   └── base.py
│
├── policy/
│   └── capability.py
│
├── risk/
│   ├── engine.py
│   ├── routing.py
│   ├── rules.py
│   ├── aggregate.py
│   └── base.py
│
├── artifacts/
│   ├── registry.py
│   └── io.py
│
├── telemetry/
│   ├── tracing.py
│   └── pricing.py
│
├── eval/
│   ├── case.py
│   ├── runner.py
│   ├── suite.py
│   ├── graders.py
│   ├── regrade.py
│   └── benchmark.py
│
├── maintenance/
│   ├── gc.py
│   ├── gc_command.py
│   ├── worktree_gc.py
│   ├── docker_gc.py
│   ├── cache_gc.py
│   ├── artifact_retention.py
│   └── artifact_retention_executor.py
│
└── legacy/
    └── orchestrator_v1.py
```

---

## 25. Architectural Principles

現在のAs-Built Architectureから読み取れる主要原則は次の通りです。

### 1. Harness owns control

ModelではなくHarnessが、

- permission
- state
- verification
- routing
- evidence
- cleanup

を所有します。

### 2. Deterministic before probabilistic

機械的に判定できることに、不要なModel Callを使いません。

### 3. Durable before clever

高度なAgent Behaviorより先に、

- state
- checkpoint
- resume
- artifact

を成立させます。

### 4. Evidence before claim

実装したことと、証明したことと、公開してよいClaimを分離します。

### 5. Preserve under ambiguity

Ownership、Integrity、Lifecycleが不明確な場合はAggressive Operationを避けます。

### 6. Cost is part of architecture

Model Call数やReview Routingは単なるBilling問題ではなく、System Architecture上のResource Allocation問題として扱います。

---

## 26. Related Documents

Public overview:

- [`../README.md`](../README.md)

Canonical publication claims:

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

Project state:

- [`PROJECT_STATE.json`](PROJECT_STATE.json)

Capability ledger:

- [`CAPABILITY_LEDGER.json`](CAPABILITY_LEDGER.json)

---

## 27. Current Boundary

このArchitectureは、

```text
m9-hardening-gc-complete
        +
M10 publication work
```

を基準としたAIVP v2 As-Built Architectureです。

M10ではこの後、

```text
TECHNICAL_REPORT
BENCHMARK
SECURITY
EVALS
REPRODUCIBILITY
PUBLICATION HYGIENE
```

を追加します。

Architectureそのものを新しいSource of Truthにはしません。

**Code changes first. Architecture documentation follows the code.**
