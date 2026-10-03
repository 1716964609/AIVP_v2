# M6 Cache Exit Evidence

日付: 2026-10-03  
Branch: `m6-cache`

## 結果

M6 Cache Exit Gate: **PASS**

AIVP v2 に以下を実装・検証した。

- Repository-aware な階層型 Deterministic Cache
- Context Selection Cache
- Content-Addressed Artifact Cache
- Stable Prompt Prefix
- Fail-Closed な Stale Cache Handling
- Harness-owned Cache の Latency 計測
- Provider-side Prompt Cache の実測
- Provider Cache Read による Economics の計測

---

## 1. 実装した Cache Layer

### Layer A — Context Selection Cache

Context Selection Cache の Logical Identity は以下で構成する。

```text
repo_sha
+ task_fingerprint
+ compiler_version
+ context budget
```

Cache Storage は以下。

```text
Filesystem CAS
+
SQLite Metadata Index
```

`ContextCompilation` を Content-Addressed Storage に保存し、
Logical Cache Key と Object SHA-256 の Mapping を SQLite で管理する。

実装後の挙動:

```text
同一 Repo + 同一 Task
→ Context Selection Cache HIT
→ compile_context() SKIP
→ RepoMapCache も SKIP
```

```text
同一 Repo + 異なる Task
→ Context Selection Cache MISS
→ RepoMapCache HIT
→ Task-specific Context Selection のみ再計算
```

```text
新しい Repository Commit
→ Context Selection Cache MISS
→ RepoMapCache MISS
→ Context Pipeline を再計算
```

これにより、上位 Cache が MISS しても、
下位 Artifact Cache を再利用できる階層構造を成立させた。

---

## 2. Layer B — Stable Prompt Prefix

Prompt Layout を明示的に Versioning した。

```text
PROMPT_LAYOUT_VERSION = "1.0.0"
```

対象 Role:

```text
Generator
Fixer
Reviewer
Risk Judge
```

Prompt を以下の構造へ整理した。

```text
[ STABLE PREFIX ]

Role Definition
Rules
Security Constraints
Behavior Contract
Output Contract

-----------------------------

[ DYNAMIC SUFFIX ]

Task
Compiled Context
Verification Result
Review Findings
Diff
Runtime Information
```

Dynamic Data より前に Stable Prefix を配置することで、
Provider-side Prompt / KV Cache が利用しやすい Token Ordering を保証する。

AIVP は Provider 内部の KV Cache 自体を所有しない。

AIVP が所有するのは、

```text
Provider が Cache しやすい Prompt Layout
```

である。

Legacy Prompt Compatibility Test も PASS しており、
Prompt Refactor による既存 Semantics の Regression は確認されなかった。

---

## 3. Layer C — Deterministic Artifact Cache

Repository Map を Task-specific Context Selection と独立して Cache する。

構成:

```text
Repo SHA
   ↓
RepoMap Cache Key
   ↓
SQLite Index
   ↓
Filesystem CAS
```

同じ Repository Snapshot に対して Task が異なる場合でも、

```text
Repo Map
```

を再利用できる。

これにより、

```text
Task A
→ Context MISS
→ RepoMap HIT

Task B
→ Context MISS
→ RepoMap HIT
```

という部分再利用が可能になった。

---

## 4. Content-Addressed Storage

Cache Object は File Name ではなく Content Hash によって Addressing する。

```text
SHA-256(content)
→ object address
```

Storage Layout:

```text
cache/
└── sha256/
    └── <prefix>/
        └── <sha256>
```

特性:

```text
同一 Content
→ 同一 Object

異なる Content
→ 異なる Object
```

CAS により以下を保証する。

```text
Deduplication
Integrity
Deterministic Reuse
```

既存 Object を再利用する場合も Content Hash を再検証する。

---

## 5. Cache Invalidation

Cache Identity に以下を含める。

```text
repo SHA
task fingerprint
compiler version
context max_files
context max_chars
```

以下の変更で Cache MISS になることを Test した。

```text
Repository SHA change
Task change
Compiler version change
Context max_files change
Context max_chars change
```

Cache Hit Rate より、

```text
Invalidation Correctness
```

を優先する。

---

## 6. Dirty Working Tree Boundary

Shared Cross-run Cache の Key は Repository HEAD SHA を利用する。

しかし Dirty Working Tree では、

```text
HEAD SHA = same
Filesystem Content = different
```

が成立し得る。

そのため Dry Run では Shared Cache を使用しない。

```text
normal clean run
→ shared cache ENABLED

dry run
→ shared cache DISABLED
```

これにより、

```text
same HEAD
+ different uncommitted bytes
→ stale cache HIT
```

を防止する。

---

## 7. Cache Integrity

以下の Integrity Check を実装した。

```text
CAS content hash validation
Logical cache identity validation
Metadata validation
Payload validation
Context content hash validation
Manifest validation
Schema version validation
```

以下の異常状態は Fail Closed する。

```text
CAS corruption
stale metadata
stale payload
context content corruption
unsupported future schema
logical identity mismatch
```

---

## 8. SQLite Resource Lifecycle

`SQLiteCacheIndex.__init__()` 中に Migration / Schema Validation が失敗した場合でも、
開いた SQLite Connection を必ず Close する。

修正後:

```text
sqlite3.connect()
    ↓
try
    ↓
migration / validation
    ↓
failure
    ↓
connection.close()
    ↓
re-raise
```

Resource Leak Test では、
Constructor Failure 後の Connection に対する SQL 実行が
`sqlite3.ProgrammingError` になることを確認した。

これにより Constructor Failure Path の Resource Ownership も閉じた。

---

## 9. Deliberate Stale-Cache Test

M6 Exit Gate として意図的に Stale Cache を生成した。

Test Flow:

```text
1. 正常な Context Cache を生成

2. SQLite Metadata 内の
   Logical Identity を意図的に破壊

3. 同一 Request で
   _compile_context_with_cache() を再実行

4. StateIntegrityError

5. compile_context() fallback なし

6. RepoMapCache fallback なし
```

Observed Result:

```text
stale Context Cache
→ StateIntegrityError
→ compiler fallback なし
→ Repo-map fallback なし
```

つまり AIVP は Logical Cache Corruption を、

```text
無視して再計算する
```

のではなく、

```text
Fail Closed
```

する。

M6 deliberate stale-cache Exit Gate:

```text
PASS
```

---

## 10. Harness-owned Cache Latency

Evidence Artifact:

```text
docs/evidence/m6-cache-latency.json
```

Benchmark Fixture:

```text
Source Files : 400
Test Files   : 100
Total Files  : 500

Iterations   : 30 paired trials
max_files    : 20
max_chars    : 120000
Model Calls  : 0
```

MISS の意味:

```text
Context Cache MISS
+
RepoMap Cache MISS
+
Repo Map Build
+
Relevant File Selection
+
Test Association
+
Import Analysis
+
Budget Enforcement
+
Context Rendering
+
CAS / SQLite Store
```

HIT の意味:

```text
Context Selection Cache HIT
+
CAS Read
+
Deserialize

compile_context() SKIP
RepoMapCache SKIP
```

Measured Result:

| Metric | MISS | HIT |
|---|---:|---:|
| Median | 133.203 ms | 8.242 ms |
| Mean | 134.038 ms | 8.468 ms |
| p95 | 138.605 ms | 9.040 ms |

Median Speedup:

```text
16.162x
```

Median Latency Reduction:

```text
93.813%
```

したがって、この Synthetic 500-file Fixture における
Context Preparation Latency は、

```text
133.203 ms
↓
8.242 ms
```

となった。

ただし、この結果は

```text
Context Preparation Step
```

に限定される。

以下を意味しない。

```text
AIVP End-to-End Runtime が
93.813% 短縮した
```

---

## 11. Provider-side Prompt Cache

Evidence Artifact:

```text
docs/evidence/m6-provider-cache.json
```

Controlled Experiment:

```text
Provider       : OpenAI
Model          : gpt-5.6-luna
Calls          : 2

Stable Prefix  : Same
Dynamic Suffix : Different

Stable Prefix Characters:
30301
```

Prompt Content 自体は Evidence JSON に保存していない。

保存したもの:

```text
Stable Prefix SHA-256
Stable Prefix Character Count
Token Usage
Latency
Model
Provider
```

---

## 12. Provider Prompt Cache Result

### Call 1

```text
Input Tokens   : 22,742
Cached Tokens  : 0
Cached Ratio   : 0.000%
Output Tokens  : 19
Elapsed        : 6509.108 ms
```

### Call 2

```text
Input Tokens   : 22,052
Cached Tokens  : 11,008
Cached Ratio   : 49.918%
Output Tokens  : 19
Elapsed        : 5345.618 ms
```

Call 2 において、

```text
cached_tokens = 11,008
```

が Provider から直接 Report された。

したがって、

```text
Provider-side Prompt Cache HIT
```

を実測で確認した。

Exit Evidence:

```text
Provider Cache Hit = TRUE
```

---

## 13. Provider Latency Interpretation

Observed Elapsed:

```text
Call 1
6509.108 ms

Call 2
5345.618 ms
```

差:

```text
約 17.9% 短縮
```

ただし Call 数は 2 であり、
Dynamic Suffix も異なる。

そのため、

```text
Latency 改善は Prompt Cache が原因である
```

とは断定しない。

M6 で直接主張するのは、

```text
cached_tokens > 0
```

によって Provider-side Prefix Reuse が確認されたことまでとする。

---

## 14. Provider Cache Read Economics

今回の算定で使用した
2026-10-03 時点の OpenAI API Pricing Snapshot:

```text
Model:
gpt-5.6-luna

Uncached Input:
$0.20 / 1M tokens

Cached Input:
$0.02 / 1M tokens

Output:
$1.20 / 1M tokens
```

Call 2:

```text
Total Input Tokens:
22,052

Cached Tokens:
11,008

Uncached Tokens:
11,044
```

### All-Uncached Counterfactual

全 Input が Uncached だった場合:

```text
22,052
× $0.20
÷ 1,000,000

= $0.00441040
```

### Observed Cache-read Accounting

```text
Uncached:

11,044
× $0.20
÷ 1,000,000

= $0.00220880
```

```text
Cached:

11,008
× $0.02
÷ 1,000,000

= $0.00022016
```

合計:

```text
$0.00220880
+
$0.00022016

= $0.00242896
```

Observable Cache-read Saving:

```text
$0.00441040
-
$0.00242896

= $0.00198144
```

Reduction:

```text
44.927%
```

したがって Call 2 の Input Token Economics について、

```text
All-Uncached Counterfactual
$0.00441040

↓

Observed Cache-read Accounting
$0.00242896
```

となった。

---

## 15. Cost Limitation

この値は、

```text
Provider の総請求額
```

ではない。

GPT-5.6 系の Prompt Cache では Cache Write が
Read と別料金になる場合がある。

しかし現在の AIVP Codex Adapter は、

```text
input_tokens
cached_input_tokens
output_tokens
```

を取得する一方で、

```text
cache_write_tokens
```

を `ModelResult` に保存していない。

そのため M6 で主張する Cost Effect は、

```text
Provider が Report した
Cache Read 部分に帰属可能な Cost Difference
```

に限定する。

また、

```text
OpenAI API-equivalent Pricing
```

と、

```text
ChatGPT / Codex Subscription の
実際の請求額
```

を同一視しない。

今回、

```text
actual_subscription_charge_measured = false
```

である。

---

## 16. M5 / M6 Optimization Boundary

AIVP の Optimization は以下の3層に分離された。

```text
M5 Context Compiler
→ LESS INPUT
```

意味:

```text
Model に渡す Context 自体を減らす
```

---

```text
M6 Harness Cache
→ LESS RECOMPUTATION
```

意味:

```text
以前計算済みの Deterministic Artifact を再利用し、
CPU / Filesystem / Context Preparation を減らす
```

---

```text
M6 Stable Prompt Prefix
→ CHEAPER REPROCESSING
```

意味:

```text
Provider-side Prompt Cache が HIT した場合、
Stable Prefix の Provider 内部再処理を削減する
```

これらは同一の Optimization ではない。

---

## 17. Semantic Cache

Semantic Cache は M6 では実装しない。

理由:

```text
自然言語的に意味が似ている
```

だけで過去 Result を再利用すると、

```text
Repository State
Policy
Toolset
Security Rule
Task Detail
```

の差分を誤って無視する可能性があるため。

M6 では、

```text
Exact Identity
+
Content Addressing
+
Repo Awareness
+
Deterministic Invalidation
```

を優先した。

Semantic Cache は v2 Stretch Scope とする。

---

## 18. Final Regression

M6 全実装および Provider Cache Evidence 取得後に
Full Regression を実行した。

Unit Tests:

```text
248 tests
PASS
```

Integration Tests:

```text
11 tests
PASS
```

対象には以下を含む。

```text
Cache
Context Compiler
Prompt Contract
Legacy Compatibility
Durable State
Checkpoint / Resume
Process Crash Resume
Worktree Isolation
Docker Sandbox
Capability Policy
Diff Guard
Model Adapter
Model Call Ledger
Pricing
Tracing
Telemetry
Risk
Verification
Artifact Integrity
```

`git diff --check`:

```text
PASS
```

---

## 19. M6 Exit Gate

| Requirement | Result |
|---|---|
| Context Selection Cache | PASS |
| Content-addressed Artifact Cache | PASS |
| Repo Map Cache | PASS |
| Provider-cache-friendly Prompt Layout | PASS |
| Stable Prefix Contract | PASS |
| Invalidation Rules | PASS |
| CAS Integrity | PASS |
| Logical Cache Integrity | PASS |
| Dirty Working Tree Safety | PASS |
| SQLite Resource Lifecycle | PASS |
| Deliberate Stale-cache Test | PASS |
| Context Cache HIT / MISS Latency Measurement | PASS |
| Provider Prompt Cache HIT Evidence | PASS |
| Provider Cache Read Economics | PASS |
| Full Unit Regression | PASS |
| Full Integration Regression | PASS |

---

## 20. Conclusion

M6 により AIVP v2 は、

```text
以前計算したものを
安全に再利用できる Harness
```

になった。

最終構造:

```text
Task
  ↓
Context Cache
  │
  ├── HIT
  │     ↓
  │  ContextCompilation
  │
  └── MISS
        ↓
     RepoMap Cache
        │
        ├── HIT
        │
        └── MISS
              ↓
          Repo Scan
              ↓
        Context Compiler
              ↓
          CAS + SQLite
```

Model Boundary:

```text
Stable Prompt Prefix
        +
Dynamic Task / Context / Diff
        ↓
Provider
        ↓
Prompt Cache HIT可能
```

M6 の Optimization Boundary:

```text
M5
LESS INPUT

M6 Local Cache
LESS RECOMPUTATION

M6 Provider Prefix
CHEAPER REPROCESSING
```

Stale Cache は Fail Closed し、
Cache Hit Rate より Consistency を優先する。

M6 Cache:

```text
COMPLETE
```
