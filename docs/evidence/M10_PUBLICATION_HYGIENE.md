# M10 — Publication Hygiene / Reproducibility Evidence

## Status

PASS

## Purpose

M10 Publication Exit Gateとして、公開対象Repositoryが第三者に渡せる状態かを確認した。

検証対象:

- tracked / local runtime separation
- ignore rules
- private absolute path
- common secret material
- frozen benchmark publication files
- clean clone identity
- clean clone runtime leakage
- source import / CLI parser
- Python compilation
- unit regression
- Markdown local links
- README reproduction command

Live Model CallおよびBenchmark Rerunは実行していない。

---

## Test Framework Correction

初回Auditでは`pytest`の存在を仮定したが、実RepositoryのUnit Testはstdlib `unittest`を使用していた。

Observed:

```text
pytest imports: none
unittest imports: present
```

したがって、Projectへ不要な`pytest` dependencyを追加せず、Audit側をAs-Built Repositoryへ合わせた。

Canonical unit command:

```bash
python -m unittest discover -s tests/unit -p 'test_*.py'
```

---

## Source Unit Regression

Source Repository上:

```text
Ran 415 tests
OK
```

Result:

```text
PASS
```

---

## Tracked / Local Runtime Separation

Tracked file inventoryに、次のruntime / local-only artifactは含まれていなかった。

```text
.aivp/
reports/
__pycache__/
*.pyc
.venv/
```

Local runtime filesについては`.gitignore`適用を確認した。

Examples:

```text
.aivp/state.db
.aivp/state.db-shm
.aivp/state.db-wal
evals/tools/__pycache__/*.pyc
reports/*
```

Result:

```text
PASS
```

---

## Private Absolute Path Scan

Tracked files全体を対象に、少なくとも次のprivate absolute path patternをscanした。

```text
/Users/<name>/
/home/<name>/
C:\Users\<name>\
file:///Users/<name>/
```

Result:

```text
PASS
```

No matching private absolute path was found.

---

## Secret Material Scan

Tracked files全体を対象に、少なくとも次のsecret-like materialをscanした。

```text
AWS access key
GitHub token
OpenAI-style secret
Anthropic-style secret
Slack token
private key material
```

Result:

```text
PASS
```

No matching tracked secret material was found.

このScanは一般的Patternに対するPublication Checkであり、あらゆるSecret形式を数学的に否定するものではない。

---

## Frozen Benchmark Publication Files

次のJSON EvidenceがTrackedかつValid JSONであることを確認した。

```text
docs/evidence/m6-cache-latency.json
docs/evidence/m6-provider-cache.json
docs/evidence/m7-eval-summary.json
docs/evidence/m8-routing-economics-summary.json
```

Result:

```text
PASS
```

---

## Clean Clone Identity

Local Repositoryから`--no-hardlinks`でtemporary clean cloneを作成した。

Audit時:

```text
source HEAD = 0fae220
clone HEAD  = 0fae220
```

Clone Working Tree:

```text
clean
```

Result:

```text
PASS
```

---

## Runtime Artifact Leakage

Fresh cloneに次が存在しないことを確認した。

```text
.aivp/
reports/
.venv/
*.pyc
state.db
state.db-wal
state.db-shm
```

Result:

```text
PASS
```

---

## Clean Clone Import / CLI

Clean clone上で`PYTHONPATH=src`を使用し、`aivp.cli`をimportした。

Public CLI Surface:

```text
run
eval
gc
resume
```

Result:

```text
PASS
```

---

## Clean Clone Compilation

Clean clone上で、

```bash
python -m compileall -q src/aivp
```

相当を実行した。

Result:

```text
PASS
```

---

## Clean Clone Unit Regression

Clean clone上で、

```bash
python -m unittest discover -s tests/unit -p 'test_*.py'
```

を実行した。

Observed:

```text
Ran 415 tests
OK
```

Result:

```text
PASS
```

---

## Markdown Local Links

Clean clone上で次のPublication DocumentのLocal Markdown Linkを検証した。

```text
README.md
docs/ARCHITECTURE.md
docs/TECHNICAL_REPORT.md
docs/BENCHMARK.md
docs/SECURITY.md
docs/EVALS.md
```

Result:

```text
PASS
```

---

## README Reproducibility Command

READMEに第三者がコピー可能なUnit Test Commandを明示した。

```bash
python -m unittest discover -s tests/unit -p 'test_*.py'
```

`pytest`はCurrent Unit SuiteのDependencyではない。

---

## Exit Interpretation

このEvidenceがSupportするClaim:

> AIVP v2のtracked publication surfaceは、private absolute-path / common secret-pattern scanを通過し、local runtime artifactを含まないclean clone上でimport、compile、415-unit-test regression、Publication Markdown link validationを再現できた。

このEvidenceがSupportしないClaim:

```text
all possible secrets are impossible
all operating systems are proven
all Python >=3.11 versions are proven
live provider evaluation is deterministic
production deployment is reproduced
complete supply-chain security is proven
```

---

## M10-7 Exit Status

```text
tracked/runtime separation: PASS
private absolute-path scan: PASS
common secret-pattern scan: PASS
benchmark publication JSON: PASS
clean clone identity: PASS
runtime leakage: PASS
CLI import: PASS
compileall: PASS
unit regression: 415 PASS
Markdown local links: PASS
README unit reproduction command: PASS
```

Overall:

```text
PASS
```
