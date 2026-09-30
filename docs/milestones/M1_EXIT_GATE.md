# M1 — Harness Panel Refactor — Exit Evidence

Date: 2026-10-01

## Milestone

M1 — Harness Core Refactor

Project terminology used during implementation:
Harness Panel

## Build completed

- package split
- ModelAdapter contract
- CodexAdapter
- ClaudeAdapter
- Verifier interface
- DeterministicVerifier
- StateStore interface
- RiskEngine interface
- legacy-compatible RiskEngine implementation
- ArtifactRegistry
- Runtime extraction
- repository boundary
- reporting boundary
- Harness Panel orchestration loop

## Regression Gate

Unit / compatibility suite:

- 59 tests
- 59 passed
- production components contain no `aivp.legacy` imports

## LOW Decision Parity

Frozen target base:

`81d6f523933b0d651acd779f7864c3e737a207cb`

Current-runtime compatibility overlay:

`claude.max_turns = 3`

The frozen configuration file itself was not modified.

### v1

- status: AUTO_FINISHED
- reason: null
- final risk: low
- Codex calls: 2
- Claude calls: 1
- fix iterations: 0
- changed paths:
  - tests/test_username.py
  - username.py

### v2 Harness Panel

- status: AUTO_FINISHED
- reason: null
- final risk: low
- Codex calls: 2
- Claude calls: 1
- fix iterations: 0
- changed paths:
  - tests/test_username.py
  - username.py

Result:

`LOW DECISION PARITY = PASS`

## MEDIUM Decision Parity

Frozen target base:

`0e2ae21d9096a6cb6b9f9bb35442b725dc663d95`

Current-runtime compatibility overlay:

`claude.max_turns = 3`

The frozen configuration file itself was not modified.

### v1

- status: AUTO_FINISHED
- reason: null
- final risk: low
- Codex calls: 2
- Claude calls: 1
- fix iterations: 0
- changed paths:
  - pricing.py
  - tests/test_pricing.py

### v2 Harness Panel

- status: AUTO_FINISHED
- reason: null
- final risk: low
- Codex calls: 2
- Claude calls: 1
- fix iterations: 0
- changed paths:
  - pricing.py
  - tests/test_pricing.py

Result:

`MEDIUM DECISION PARITY = PASS`

## Provider Drift Observation

The frozen v1 configuration specifies:

`claude.max_turns = 2`

With the current Claude Code / Sonnet runtime, both the frozen v1
implementation and the refactored v2 Harness Panel reached the same
review-stage failure:

`error_max_turns`

A direct review replay showed that `max_turns = 3` is sufficient for the
current runtime.

Therefore the current-runtime parity tests applied the same temporary
`max_turns = 3` compatibility overlay to both v1 and v2.

This overlay was not written back to the frozen benchmark configuration.

## Exit Gate

- LOW case same final decision: PASS
- MEDIUM case same final decision: PASS
- Regression-free refactor: PASS

# M1 EXIT GATE: PASS
