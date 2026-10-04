# M8 — Risk-based Routing / Economics

Status: ACTIVE / BASELINE INSPECTION

## 目的

M8では、M7で完成した固定Eval Harnessを品質基準として利用し、
現在のAIVP Harnessから不要なModel Callを削減する。

目標は単純なCall数削減ではない。

必要な品質・安全性を維持しながら、
不要なModel Call、Latency、Token、Costを削減し、
Routing判断をArtifactから説明可能にする。

## M7固定ベースライン

M7 completion evidence commit:

ec499e0a601023a5187d474e7b596662ff89abee

M7 completion tag:

m7-eval-harness-complete

M7 continuity commit:

038b18879c9052c188e8a4ebcd42eebea89b5d0f

Formal M7 run:

m7-final-clean-20261004-072204

品質基準:

- 15 / 15 fixed cases PASS
- 27 trials
- 27 / 27 offline re-grade reproduction
- baseline SHA mismatch: 0
- 323 unit tests PASS
- 11 integration tests PASS

機械可読ベースライン:

docs/evidence/m7-eval-summary.json

M7のEvidenceと期待値は歴史的証拠として固定する。

M8の結果を良く見せるためにM7期待値を書き換えてはならない。

## Master Plan上の実装対象

- deterministic risk floor
- review routing
- model / call budget routing
- early exit

## M8-0 — 現在のControl Flow調査

Status: ACTIVE

確認するもの:

- Generatorがどこで呼ばれるか
- Fixerがどこで呼ばれるか
- Claude Reviewerがどこで呼ばれるか
- Risk Judgeがどこで呼ばれるか
- 既存のdeterministic policy / risk情報
- terminal decisionが確定する位置
- model-call budgetの位置
- repair budgetの位置
- M7各CaseのBefore指標

この段階ではRouting動作を変更しない。

## M8-1 — Deterministic Risk Floor

Status: IMPLEMENTED / TESTED

LLM判断より前に確定できる安全境界をDeterministicに定義する。

候補:

- capability / policy class
- sensitive / forbidden path
- auth / security change
- dependency addition
- diff size / blast radius
- deterministic verification failure
- production / external mutation intent

Deterministicな安全境界をLLMが弱めてはならない。

## M8-2 — Review Routing

Status: IMPLEMENTED / TESTED

Independent Reviewerを、

「呼べるから毎回呼ぶ」

から、

「DecisionまたはSafetyに意味がある場合だけ呼ぶ」

へ変更する。

Reviewをskipした場合も、
なぜskipしたかをArtifactとして保存する。

## M8-3 — Model / Call Budget Routing

Status: IMPLEMENTED / TESTED

Generator / Fixer / Reviewer / Risk Judgeごとに
Call Budgetを明示的に管理する。

Terminal Outcomeが既に確定している場合、
不要な後続Model Callを行わない。

Budget exhaustionは引き続きfail-safeに扱う。

## M8-4 — Early Exit

Status: IMPLEMENTED / TESTED

Deterministic evidenceだけで安全なTerminal Pathが確定した場合、
後続処理を停止する。

候補:

- hard policy denial
- deterministic HUMAN_REQUIRED
- repair / call budget exhaustion
- unrecoverable deterministic verification failure

正確なRuleはM8-0で現在のControl Flowを確認してから決める。

### M8-4 As-Built Decision

M8-4では新しいEarly Exitアルゴリズムを追加しない。

M8-1〜M8-3および既存Capability Policyを棚卸しした結果、
計画時に想定していたTerminal Pathは既に以下の形で成立している。

- Capability PolicyのHUMAN_REQUIRED / DENIEDは例外処理から
  terminal outcomeへ直接遷移し、後続処理を行わない。
- deterministic verificationがfix budget内で回復しない場合は
  HUMAN_REQUIREDへescalateし、Review / Risk処理へ進まない。
- deterministic repair / review repairのAdmissionが拒否された場合は
  Fixerを呼ばずHUMAN_REQUIREDへescalateする。
- review repair後のworktree fingerprintが不変の場合は
  再Verification / 再Reviewを行わずHUMAN_REQUIREDへescalateする。
- aggregate outcomeが既にHIGHへ固定される場合は
  redundantなCodex Risk Judgeを呼ばない。

Evidenceは新しい重複Artifactへ統合せず、
既存の構造化ArtifactをSource of Truthとして維持する。

- deterministic-repair-budget-*.json
- review-repair-budget-*.json
- no-op-review-repair-*.json
- risk-routing.json
- aggregate-risk.json
- status.json

`status.json`をterminal outcomeのSource of Truth、
各routing Artifactをdecision provenanceのSource of Truthとする。

M8-4で新たな`early-exit.json`を追加しない理由は、
同じdecisionを複数Artifactへ重複記録して
Source of Truthを曖昧にすることを避けるためである。

## M8-5 — 再Benchmark

Status: NOT STARTED

M7と同じ固定Eval SuiteをM8で再実行する。

最低比較項目:

- Eval pass rate
- final decision correctness
- total model calls
- Codex calls
- Claude calls
- repair iterations
- input tokens
- cached tokens
- output tokens
- p50 latency
- p95 latency
- HUMAN_REQUIRED behavior
- Cost per Accepted Change
- Cost coverage

Hard Gate:

15 / 15 fixed cases PASS

品質またはSafetyがRegressionした場合、
Call削減結果は成功として扱わない。

## 明示的な非対象

M8では以下を行わない。

- Reviewer Agent追加
- Redis
- PostgreSQL
- Temporal
- Kubernetes
- Semantic Cache
- Distributed Execution
- Production Deployment
- M9 Garbage Collection
- M10 Publication

## Closure Gate

### Technical

- [x] deterministic risk floor
- [x] review routing
- [x] model / call budget routing
- [x] early exit
- [x] routing evidence persistence
- [ ] M7 fixed suite 15 / 15 PASS
- [ ] full regression PASS

### Economics

- [ ] total model calls Before / After
- [ ] role別Model Call Before / After
- [ ] Token Before / After
- [ ] p50 / p95 latency Before / After
- [ ] Cost per Accepted Change比較
- [ ] unavailableなCostを0として扱わない

### Repository Memory

- [ ] docs/evidence/m8-routing-economics.md
- [ ] machine-readable M8 comparison evidence
- [ ] docs/milestones/M8.md
- [ ] docs/CAPABILITY_LEDGER.json
- [ ] docs/PROJECT_STATE.json
- [ ] execution planをcompletedへ移動

### Git Closure

- [ ] git diff --check PASS
- [ ] completion commit
- [ ] completion tag
- [ ] clean working tree


## M8-1 Discovery — Conservative LOW Skip Rejected

M7 formal evidence initially suggested a conservative optimization:

- deterministic rule risk = LOW
- Claude review risk = LOW
- no blocking findings
- high Claude risk confidence
- deterministic verification PASS

Under the frozen M7 formal run, Codex Risk had zero observed marginal
final-decision contribution across the 14 trials that reached aggregate risk,
and 10 / 14 trials matched the proposed conservative LOW skip conditions.

However, the existing safety regression contract contains an explicit case
where:

- deterministic rule = LOW
- Claude review = LOW
- Codex independent risk judge = HIGH

and the required terminal outcome is HUMAN_REQUIRED.

Therefore the proposed conservative LOW skip could convert a required
HUMAN_REQUIRED outcome into AUTO_FINISHED.

The hypothesis was rejected before orchestration integration.

M8 will preserve the independent Codex risk judge whenever its result can
still change the aggregate outcome.

The first accepted skip rule is limited to mathematically terminal HIGH cases:
if deterministic rule risk or Claude review risk is already HIGH, the existing
aggregate contract is forced to HIGH regardless of Codex output.

This negative result is preserved as M8 design evidence.
