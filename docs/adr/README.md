# Architecture Decision Records (ADRs)

## Overview

This directory contains Architecture Decision Records (ADRs) for the Phoenix Guardian platform. ADRs document important architectural decisions, their context, and the rationale behind choosing specific solutions.

## ADR Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](001-rls-tenant-isolation.md) | PostgreSQL RLS for Tenant Isolation | Accepted | Day 95 |
| [ADR-002](002-redis-sentinel.md) | Redis Sentinel for High Availability | Accepted | Day 98 |
| [ADR-003](003-istio-service-mesh.md) | Istio Service Mesh Adoption | Accepted | Day 102 |
| [ADR-004](004-cloudnativepg-operator.md) | CloudNativePG for Database Operations | Accepted | Day 105 |
| [ADR-005](005-differential-privacy.md) | Differential Privacy Parameters | Accepted | Day 125 |
| [ADR-006](006-websocket-realtime.md) | WebSocket for Real-time Communication | Accepted | Day 135 |
| [ADR-007](007-argocd-gitops.md) | ArgoCD for GitOps Deployment | Accepted | Day 140 |
| [ADR-008](008-vault-secrets.md) | HashiCorp Vault for Secrets | Accepted | Day 145 |
| [ADR-009](009-prometheus-observability.md) | Prometheus Stack for Observability | Accepted | Day 150 |
| [ADR-010](010-locust-load-testing.md) | Locust for Load Testing | Accepted | Day 160 |
| [ADR-011](011-jwt-tenant-context.md) | JWT-based Tenant Context | Accepted | Day 96 |
| [ADR-012](012-chunked-upload.md) | Chunked Upload for Mobile Audio | Accepted | Day 118 |
| [ADR-013](013-attack-detection-pipeline.md) | Attack Detection Pipeline | Accepted | Day 108 |
| [ADR-014](014-federated-aggregation.md) | Federated Learning Aggregation | Accepted | Day 128 |
| [ADR-015](015-medical-nlp-models.md) | Medical NLP Model Selection | Accepted | Day 132 |
| [ADR-016](016-multi-language-architecture.md) | Multi-Language Architecture | Accepted | Day 155 |
| [ADR-017](017-soc2-evidence-automation.md) | SOC 2 Evidence Automation | Accepted | Day 148 |
| [ADR-018](018-kubernetes-hpa.md) | Kubernetes HPA Configuration | Accepted | Day 142 |
| [ADR-019](019-circuit-breaker-pattern.md) | Circuit Breaker for External Services | Accepted | Day 112 |
| [ADR-020](020-audit-log-retention.md) | Audit Log Retention Policy | Accepted | Day 152 |

## ADR Template

```markdown
# ADR-XXX: [Title]

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-XXX]

## Context
[What is the issue we're seeing that motivates this decision?]

## Decision
[What is the change we're proposing?]

## Consequences

### Positive
- [List positive outcomes]

### Negative
- [List negative outcomes]

### Risks
- [List potential risks]

## Alternatives Considered
[What other options were evaluated?]

## References
- [Links to related documents, issues, or PRs]
```

## ADR Categories

### Infrastructure
- ADR-002: Redis Sentinel
- ADR-003: Istio Service Mesh
- ADR-004: CloudNativePG
- ADR-007: ArgoCD GitOps
- ADR-008: Vault Secrets
- ADR-009: Prometheus Stack
- ADR-018: Kubernetes HPA

### Security
- ADR-001: RLS Tenant Isolation
- ADR-011: JWT Tenant Context
- ADR-013: Attack Detection
- ADR-017: SOC 2 Automation
- ADR-020: Audit Log Retention

### AI/ML
- ADR-005: Differential Privacy
- ADR-014: Federated Aggregation
- ADR-015: Medical NLP Models

### Application
- ADR-006: WebSocket Real-time
- ADR-012: Chunked Upload
- ADR-016: Multi-Language
- ADR-019: Circuit Breakers

### Testing
- ADR-010: Locust Load Testing
