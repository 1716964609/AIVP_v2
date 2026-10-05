# AIVP v2

**AIVP v2 は、AIが生成するソフトウェア変更を「耐障害性のある実行」「限定されたblast radius」「計測」「評価」の中に閉じ込める、ローカルファーストのCoding-Agent Harnessです。**

位置づけは、**本番運用を意識した（production-minded）プロトタイプ**です。

本番稼働中のmulti-user coding platformそのものではありません。

AIVPではCoding Modelそのものを開発システム全体とは考えません。

Modelの外側に **Harness Panel** を置き、Model自身に任せるべきではない制御をHarness側で所有します。

- durable execution
- context selection
- cache
- permission / policy
- deterministic verification
- risk-aware routing
- observability
- evaluation
- bounded garbage collection

## なぜ作ったのか

コード生成そのものは、これからさらに安く・速くなっていきます。

その一方で、実際のSoftware Engineeringでは次の問題が残ります。

- このrunはいま何の状態なのか。
- Processが落ちた後、完了済み作業を無駄に繰り返さずresumeできるか。
- ModelにRepositoryの何を見せるべきか。
- Modelに何を変更・実行させてよいか。
- どの変更ならdeterministic gateだけで十分なのか。
- どの変更なら独立Reviewerが必要なのか。
- いつHumanへEscalationすべきか。
- OptimizationによってQualityを壊していないか。
- Model call、token、retry、latencyはどの程度発生したか。
- Interrupted runが残したresourceを、何を根拠に削除してよいのか。

AIVP v2は、これらをCoding Agentの周辺にある「Harnessの問題」として扱います。

## Mental Model

```text
Task / Acceptance Criteria / Constraints
                  |
                  v
       +-----------------------+
       |      Harness Panel    |
       |-----------------------|
       | Durable Execution     |
       | Context / Cache       |
       | Policy / Routing      |
       | Worktree / Sandbox    |
       | Telemetry / Economics |
       | Evaluation / GC       |
       +-----------+-----------+
                   |
                   v
        Generate -> Verify
              -> Review
              -> Risk
              -> Decision
                   |
          +--------+--------+
          |                 |
          v                 v
   AUTO_FINISHED      HUMAN_REQUIRED
```

Modelは変更案を生成します。

**その変更案をどの境界の中で実行し、どう検証し、どこまで自動化してよいかはHarnessが決めます。**

## 何がEvidenceとして確認されているか

AIVP v2は、v1 baselineを凍結したうえで、Milestone単位で実装・検証してきました。

### M7 — Fixed Evaluation

凍結したM7 Formal Evaluationでは、次の結果を記録しています。

| Metric | M7 |
|---|---:|
| Fixed cases passed | 15 / 15 |
| Trials / regrades | 27 |
| Codex calls | 47 |
| Claude calls | 31 |
| Total model calls | 78 |
| Fix iterations | 7 |
| AUTO_FINISHED | 14 |
| HUMAN_REQUIRED | 13 |
| Observed suite wall time | 1122.694 s |

Evidence:

- [`docs/evidence/m7-eval.md`](docs/evidence/m7-eval.md)
- [`docs/evidence/m7-eval-summary.json`](docs/evidence/m7-eval-summary.json)

これは**固定された15-case evaluation suiteに対する結果**です。

任意のReal-world coding task全体に対するAccuracyを意味するものではありません。

### M8 — Risk-aware Routing / Economics

M8では、同じFrozen Evaluation Suiteの結果を維持しながら、不要なReviewer Callを削減しました。

| Metric | M7 | M8 | Observed change |
|---|---:|---:|---:|
| Fixed cases passed | 15 / 15 | 15 / 15 | preserved |
| Codex calls | 47 | 47 | 0 |
| Claude calls | 31 | 25 | -6 (-19.35%) |
| Total model calls | 78 | 72 | -6 (-7.69%) |
| Fix iterations | 7 | 7 | 0 |
| AUTO_FINISHED | 14 | 14 | preserved |
| HUMAN_REQUIRED | 13 | 13 | preserved |
| Suite wall time | 1122.694 s | 1036.739 s | -7.66% observed |

6件のdeterministic no-op exitと、6回減少したClaude review callが対応しています。

Wall-clockについては、

**1122.694秒 → 1036.739秒**

という観測値を報告しています。

ただし、この差分全体をRisk Routingによる純粋な因果効果とは主張しません。

また、Live Provider CostのCoverageが不完全であるため、

**USD Cost per Accepted Changeは算出済みの事実として報告しません。**

Evidence:

- [`docs/evidence/m8-routing-economics.md`](docs/evidence/m8-routing-economics.md)
- [`docs/evidence/m8-routing-economics-summary.json`](docs/evidence/m8-routing-economics-summary.json)

### M9 — Hardening / Garbage Collection

M9 completion boundaryでは次を確認しています。

- 415 unit tests PASS
- 8 / 8 M9 GC exit-gate fault tests PASS
- GCはdefaultでdry-run
- destructive GCには明示的な `--yes` が必要
- dirty worktreeをforce removeしない
- resumable runを保持する
- protected formal evidenceを保持する
- ownershipを証明できないresourceは保持する
- tested boundary内でcleanupはidempotent

Evidence:

- [`docs/evidence/M9_GC_EXIT_GATE.md`](docs/evidence/M9_GC_EXIT_GATE.md)

## Core Capabilities

### Durable Execution

AIVPはrun stateをSQLiteへ保存し、checkpointをdurableに記録します。

目的は、Process Failureが発生したときに、

```text
state
  = runが現在どこにいるか

checkpoint
  = どこまでのprogressがdurableに保存されたか

resume
  = そのprogressからどう再開するか
```

を分離することです。

Interrupted runを、単純に最初からやり直すことを前提にしていません。

### Context Compiler / Cache

HarnessはRepository全体を毎回Modelへ渡すことを前提にせず、Taskに必要なContextを選択します。

また、

- filesystem CAS
- SQLite cache metadata
- explicit invalidation
- fail-closed integrity checks

を使い、Context Preparationの不要な再実行を減らします。

Evidence:

- [`docs/evidence/m5-context-compiler.md`](docs/evidence/m5-context-compiler.md)
- [`docs/evidence/m6-cache.md`](docs/evidence/m6-cache.md)
- [`docs/evidence/m6-cache-latency.json`](docs/evidence/m6-cache-latency.json)
- [`docs/evidence/m6-provider-cache.json`](docs/evidence/m6-provider-cache.json)

Provider Prompt Cacheについては、Controlled Testで実際のcached tokenを観測しています。

ただし、それを任意のProvider RunにおけるGuaranteed Cache Hit Rateとは扱いません。

### Risk-aware Routing

AIVPの目的はAgent数を最大化することではありません。

**高価なReasoningを、Decisionを変える可能性がある場所へ集中させること**です。

Deterministicに判断可能なケースではModel Reviewerを呼ばず、

Risk、Uncertainty、Policy上必要なケースでは独立ReviewやHuman Escalationを残します。

### Bounded Blast Radius

AIVPではPer-run Git WorktreeとDocker Verification Sandboxを利用して、Local Executionのblast radiusを制限します。

ModelへのPromptそのものをSecurity Boundaryとは考えません。

ただし、これはLocal-first Containment Mechanismです。

Complete Zero-trust Enterprise IsolationやProduction Multi-tenancyを証明するものではありません。

### Observability / Economics

Harness側で次のEvidenceを管理します。

- model call
- latency
- token telemetry
- verification
- retry
- terminal decision
- evaluation result
- provider dataが存在する範囲でのusage evidence

Providerから取得できなかったDataは、推測値で埋めません。

**Missing DataはMissing Dataのまま扱います。**

### Evaluation as an External Control Loop

Evaluation Harnessは通常のCoding-Agent Loopの外側にあります。

Fixed CaseとExpected Outcomeを用いて、

- context selection
- routing
- policy
- orchestration
- repair logic

などの変更が、過去に証明したBehaviorを壊していないかを確認します。

## Installation

Python 3.11以上を前提とします。

```bash
python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e .

aivp --version
aivp --help
```

Unit TestはPython標準ライブラリの`unittest`で実行できます。

```bash
python -m unittest discover -s tests/unit -p 'test_*.py'
```

このTest Suiteの実行に`pytest`は必要ありません。

Package metadataとCLI entry pointは、

[`pyproject.toml`](pyproject.toml)

で定義しています。

現在のpackage versionはdevelopment boundaryとして、

```text
2.0.0.dev0
```

です。

## One-command Deterministic Demo

Live Codex / Claude Providerを呼ばず、AIVPのControl Loopを一度通すDeterministic Demoを用意しています。

```bash
make doctor
make demo
```

`make demo`は既存のscripted Codex / scripted Claude fixtureを利用し、

```text
Generate
  ↓
Controlled Verification Failure
  ↓
Bounded Repair
  ↓
Re-verification
  ↓
Terminal Decision
```

を実行します。

Demo用Runtime Artifactは`.aivp/`配下へ保存され、Git管理対象には入りません。

追加の公開用Command:

```bash
make test
make benchmark
```

`make benchmark`はFrozen Benchmark Evidenceを検証するだけで、Live Benchmarkを再実行しません。

Full M7 Evaluationも、

```bash
make eval
```

で起動できますが、これは一部CaseでLive Codex / Claude Providerを使用する可能性があり、Provider Quotaを消費します。

Architecture Decision Records:

- [`docs/adr/README.md`](docs/adr/README.md)

## CLI

現在のPublic CLI Surfaceは次の4系統です。

```text
aivp run
aivp eval
aivp gc
aivp resume
```

### Run

CLI Surface:

```bash
aivp run --help
```

基本形:

```bash
aivp run \
  --repo /path/to/target-repository \
  --task /path/to/task.json \
  --config /path/to/config.json \
  --dry-run
```

Real Runには明示的な `--yes` が必要です。

```bash
aivp run \
  --repo /path/to/target-repository \
  --task /path/to/task.json \
  --config /path/to/config.json \
  --yes
```

Repository内にはFixed Evaluation用のTask / Config exampleがあります。

例:

```text
evals/inputs/tasks/low-username-normalization.json
evals/inputs/configs/low-username-normalization.json
```

Provider ConfigurationやCredential Requirementsは、選択したRun ConfigurationとLocal CLI Environmentに依存します。

このPrototypeへProduction Credentialを渡すことは推奨しません。

### Resume

```bash
aivp resume RUN_ID \
  --state-db ./.aivp/state.db
```

Resumeでは、前Processの存在そのものではなくDurable Stateを基準に再開します。

### Evaluation

固定Evaluation Suiteは、

```text
evals/suites/m7-fixed.json
```

にあります。

Evaluation CLIの正確なOption Surfaceは実装中のCLI Helpを正本として確認できます。

```bash
aivp eval --help
aivp eval run --help
```

Live Providerを使うReal Evaluationは、

- model quota
- execution time
- external provider resource

を消費する可能性があります。

M10 Publicationでは、不要なLive Rerunを行わず、M7/M8でFreeze済みのEvidenceを優先します。

### Garbage Collection

GCはdefaultでdry-runです。

```bash
aivp gc \
  --older-than 7d
```

Destructive Cleanupには明示的なApprovalが必要です。

```bash
aivp gc \
  --older-than 7d \
  --yes
```

`--yes` を付けてもDirty WorktreeをForce Deleteする設定には変わりません。

Ownershipを証明できないResourceはPreserveします。

## Fixed Evaluation Corpus

Repositoryには15 CaseのFixed Evaluation Corpusがあります。

Location:

[`evals/cases`](evals/cases)

```text
01  low username normalization
02  medium pricing rule
03  specification conflict
04  controlled fault repair
05  high auth change
06  forbidden secret access
07  large diff
08  dependency addition
09  reviewer timeout
10  process-kill resume
11  stale context cache
12  forbidden network action
13  business invariant failure
14  malformed model output
15  budget exhaustion
```

Fixture Application、Task Input、Config Inputも、

[`evals`](evals)

配下に保持しています。

このSuiteには、単純なHappy Pathだけではなく、

- specification conflict
- forbidden secret access
- large diff
- reviewer timeout
- process-kill / resume
- stale cache
- forbidden network action
- malformed model output
- budget exhaustion

などのFailure / Safety Caseも含まれています。

## Milestone History

AIVP v2は、MilestoneごとにExit Gateを通しながら構築しました。

| Milestone | Focus | Frozen boundary |
|---|---|---|
| M0 | v1 baseline freeze | `m0-baseline-frozen` |
| M1 | Harness Panel refactor | `m1-harness-panel-refactor` |
| M2 | Durable execution | `m2-durable-execution` |
| M3 | Containment | `m3-containment-complete` |
| M4 | Telemetry / Cost Ledger | `m4-telemetry-cost-ledger-complete` |
| M5 | Context Compiler | `m5-context-compiler-complete` |
| M6 | Cache | `m6-cache-complete` |
| M7 | Eval Harness | `m7-eval-harness-complete` |
| M8 | Risk Routing / Economics | `m8-risk-routing-economics-complete` |
| M9 | Hardening / GC | `m9-hardening-gc-complete` |
| M10 | Evidence / Publication | in progress |

Milestone Record:

- [`docs/milestones`](docs/milestones)
- [`docs/exec-plans`](docs/exec-plans)

## Evidence Model

AIVPでは、

```text
Planned Design
      |
      v
Actual Implementation
      |
      v
Deviation
      |
      v
Measured / Tested Evidence
      |
      v
Public Claim
```

を分離します。

「設計書に書いてある」ことと、

「実装されている」ことと、

「Evidenceで証明されている」ことは同じではありません。

Publication Claimの正本は、

[`docs/evidence/M10_CLAIM_EVIDENCE_MATRIX.md`](docs/evidence/M10_CLAIM_EVIDENCE_MATRIX.md)

です。

Public Claimは原則として、

1. EvidenceへMappingできる
2. Caveat付きで表現する
3. Claimしない

のいずれかに分類します。

## AIVP v2が主張しないこと

AIVP v2は、次を証明したとは主張しません。

- Production-grade Multi-user Coding Platformであること
- Distributed Worker Platformであること
- 24/7 Production SRE Operationを実証したこと
- Complete Zero-trust Enterprise Isolationを実現したこと
- Large-scale Multi-tenant Cost Optimizationを証明したこと
- Automatic Production Deployment Systemであること
- 15-case Fixed Suiteが任意のReal-world Coding Accuracyを代表すること
- M8でUSD Cost per Accepted Changeが既知の割合だけ改善したこと

このProjectの目的は、

**Production Harnessに必要となるControl Mechanismを、実装し、Fault-testし、Measureし、比較可能にすること**

です。

## Repository Map

```text
src/aivp/                  Harness implementation
evals/                     Fixed evaluation corpus / fixtures
tests/unit/                Unit regression
tests/integration/         Integration tests
tests/fault/               Fault / exit-gate tests
docs/evidence/             Frozen evidence
docs/milestones/           Milestone record
docs/exec-plans/           Execution plan / historical decision
scripts/                   Controlled benchmark / bootstrap utilities
.aivp/                     Local runtime state / cache
reports/                   Local run / evaluation artifacts
```

`.aivp/` や `reports/` がLocal Filesystemに存在することと、Public RepositoryへPublicationされることは同じではありません。

M10では別途、

- tracked file
- ignored file
- local-only artifact
- secret
- private absolute path

を監査します。

## Documentation

M10ではさらに次のPublication Surfaceを追加します。

```text
docs/ARCHITECTURE.md
docs/TECHNICAL_REPORT.md
docs/BENCHMARK.md
docs/SECURITY.md
docs/EVALS.md
```

これらが完成するまでは、

- Git source
- frozen milestone tag
- raw evidence
- PROJECT_STATE
- CAPABILITY_LEDGER
- milestone record

をDetailed Source of Truthとして扱います。

## Project Status

**AIVP v2 — M0 through M10 complete.**

AIVP v2 は、Probabilistic Coding Agent を Software Engineering の既存原則の中で制御するための、Local-first / Single-user の **production-minded Harness prototype** です。

M0からM10までの実装、Fixed Evaluation、Benchmark、Security Boundary、Reproducibility、Evidence Publicationは完了しています。

正式なM10 frozen baseline:

`m10-evidence-publication-complete`

`main`には上記milestone tag以降のdocumentation-only refinementが存在する場合があります。M10の技術的Evidence Boundaryはこのtagに固定されています。

### Published Work

- **GitHub — Source / Architecture / Evidence:** https://github.com/1716964609/AIVP_v2
- **Note — Why / Insight:** https://note.com/sunlightjetrans/n/n158b0ae48aa7
- **Qiita — How / Implementation:** https://qiita.com/1716964609/items/8b73f7f36c33819eddc1
- **Medium — Engineering Thesis:** https://medium.com/@hxlj9909/engineering-around-probabilistic-workers-f8b31aa6d56f

### Key Evidence

| Evidence | Observed result |
| --- | ---: |
| Fixed evaluation | **15 / 15 PASS** |
| Total model calls | **78 → 72 (-7.69%)** |
| Claude calls | **31 → 25 (-19.35%)** |
| Controlled provider input | **413,779 → 110,790 (-73.22%)** |
| Local context-cache median | **133.203 ms → 8.242 ms (16.162x)** |
| Regression suite | **415 tests PASS** |

Risk Routing comparisonではFixed Evaluationの15/15を維持しました。

Wall-time差分は観測値として報告しており、その全量をRouting単独の因果効果とは主張しません。

`USD Cost per Accepted Change = UNAVAILABLE`

Provider Billing Evidenceが十分ではなかったため、USD値を推定で補完していません。

### Evidence Documents

- [Architecture](docs/ARCHITECTURE.md)
- [Technical Report](docs/TECHNICAL_REPORT.md)
- [Benchmark Report](docs/BENCHMARK.md)
- [Security](docs/SECURITY.md)
- [Evaluation](docs/EVALS.md)
- [Architecture Decisions](docs/adr/README.md)
- [M10 Claim / Evidence Matrix](docs/evidence/M10_CLAIM_EVIDENCE_MATRIX.md)
- [M10 Publication Hygiene](docs/evidence/M10_PUBLICATION_HYGIENE.md)
- [M10 Internal Exit Gate](docs/evidence/M10_EXIT_GATE.md)
- [M10 Final Closure](docs/evidence/M10_FINAL_CLOSURE.md)

### Explicit Non-Claims

AIVP v2 does **not** claim:

- production-ready multi-tenant operation
- completed zero-trust security
- general performance across arbitrary repositories or workloads
- proven USD provider-cost reduction
