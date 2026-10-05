# ADR-009 — MCP is an Optional Adapter Surface, not a Harness Dependency

## Status

Accepted scope boundary.

## Context

AIVP v2のHarness Responsibilityは、

- durable state
- context
- policy
- verification
- routing
- telemetry
- evaluation

である。

特定Tool ProtocolをHarness Coreへ必須Dependencyとして組み込むと、Control ModelとTransport / Tool Integrationが結合する。

## Decision

MCPを将来Supportする場合も、Harnessの必須Core Dependencyにはしない。

MCPはTool / Provider Adapter Surfaceの一つとして扱う。

Current v2 As-Built RepositoryにはMCP Gatewayを実装しない。

## Consequences

利点:

- Harness Control ModelをProtocol-independentに保つ
- MCPなしでもLocal Harnessが成立する
- Future IntegrationをAdapterとして追加可能

制約:

- v2はFull MCP Gatewayを提供しない

## Evidence

Current As-Built ArchitectureがModel / Policy / Tool ControlをProtocol-specific MCP Dependencyなしで成立させていること。

## Revisit Trigger

MCP IntegrationがConcrete Requirementになった時。ただしCore Dependency化には別ADRを要求する。
