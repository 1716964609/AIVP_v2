# ADR-006 — Production Capability is Default Deny

## Status

Accepted.

## Context

ModelがActionを提案できることと、HarnessがそのActionを許可してよいことは別問題である。

特にProduction / Sensitive OperationをPrompt Instructionだけで制御するのはSecurity Boundaryとして弱い。

## Decision

Capability PermissionはHarness Policyが所有する。

Production / Sensitive Capabilityはv2でAutonomous Allowにしない。

Unsupported / Sensitive Actionは、

```text
DENY
or
HUMAN_REQUIRED
```

側へ倒す。

## Consequences

利点:

- Model IntentとPermissionを分離
- Production Blast Radiusを縮小
- Human Judgmentを明示的なTerminal Outcomeとして扱える

制約:

- v2はProduction Automation Platformではない
- Production Credential Lifecycleを提供しない

## Evidence

- `src/aivp/policy/capability.py`
- `docs/SECURITY.md`
- capability policy tests
- `high-auth-change` fixed eval case

## Revisit Trigger

Production Capabilityを許可するための独立Approval / Credential Boundaryが設計・評価された時。
