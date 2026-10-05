# ADR-001 — Local-first / Single-user v2

## Status

Accepted.

## Context

AIVP v2の目的は、Distributed Agent Platformを先に構築することではなく、Coding-Agent HarnessのControl Boundaryを検証可能な形で成立させることだった。

必要だったのは、

- durable execution
- containment
- context control
- routing
- evaluation
- telemetry
- bounded maintenance

であり、最初からRemote Worker、Multi-user、Multi-tenant Control Planeを導入する必要はなかった。

## Decision

AIVP v2はLocal-first / Single-user Architectureとする。

State、Cache、Artifact、Evaluation EvidenceはLocal Repository / Local Filesystem / SQLiteを中心に構成する。

## Consequences

利点:

- Failureを再現しやすい
- State / Artifactを直接監査できる
- Infrastructure ComplexityをHarness Logicから分離できる
- Small SurfaceでEvaluation可能

非目標:

- Multi-user authentication
- Multi-tenant isolation
- remote worker fleet
- HA control plane

## Evidence

- `docs/ARCHITECTURE.md`
- `docs/TECHNICAL_REPORT.md`
- `docs/SECURITY.md`
- `docs/evidence/M10_PUBLICATION_HYGIENE.md`

## Revisit Trigger

Local single-user boundaryが実際のScaling Bottleneckになった時。
