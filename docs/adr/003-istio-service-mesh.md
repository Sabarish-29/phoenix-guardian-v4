# ADR-003: Istio Service Mesh Adoption

## Status
Accepted

## Date
Day 102 (Phase 3)

## Context

Phoenix Guardian consists of 8 microservices communicating in a complex pattern. We need:
1. Mutual TLS between all services
2. Traffic management and canary deployments
3. Observability (distributed tracing, metrics)
4. Rate limiting and circuit breaking
5. Service-to-service authorization

Implementing these cross-cutting concerns in application code would require significant effort and introduce inconsistency.

## Decision

We will adopt Istio as our service mesh to handle cross-cutting infrastructure concerns uniformly across all services.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Istio Control Plane                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                 │
│  │   Istiod   │  │   Pilot    │  │   Citadel  │                 │
│  │  (config)  │  │  (routing) │  │   (certs)  │                 │
│  └────────────┘  └────────────┘  └────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                          Data Plane                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────────┐        ┌───────────────────┐             │
│  │    API Gateway    │        │  Auth Service     │             │
│  │  ┌─────────────┐  │        │  ┌─────────────┐  │             │
│  │  │    Envoy    │  │◄──────►│  │    Envoy    │  │             │
│  │  │   (sidecar) │  │  mTLS  │  │   (sidecar) │  │             │
│  │  └─────────────┘  │        │  └─────────────┘  │             │
│  └───────────────────┘        └───────────────────┘             │
│           │                            │                         │
│           ▼                            ▼                         │
│  ┌───────────────────┐        ┌───────────────────┐             │
│  │  Encounter Svc    │        │  Threat Detection │             │
│  │  ┌─────────────┐  │        │  ┌─────────────┐  │             │
│  │  │    Envoy    │  │◄──────►│  │    Envoy    │  │             │
│  │  │   (sidecar) │  │  mTLS  │  │   (sidecar) │  │             │
│  │  └─────────────┘  │        │  └─────────────┘  │             │
│  └───────────────────┘        └───────────────────┘             │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Configurations

```yaml
# PeerAuthentication - require mTLS
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: phoenix-guardian
spec:
  mtls:
    mode: STRICT

---
# DestinationRule - circuit breaker
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: encounter-service
spec:
  host: encounter-service
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        h2UpgradePolicy: UPGRADE
        http1MaxPendingRequests: 100
        http2MaxRequests: 1000
    outlierDetection:
      consecutiveErrors: 5
      interval: 30s
      baseEjectionTime: 30s
      maxEjectionPercent: 50

---
# VirtualService - canary routing
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: api-gateway
spec:
  hosts:
    - api-gateway
  http:
    - route:
        - destination:
            host: api-gateway
            subset: stable
          weight: 90
        - destination:
            host: api-gateway
            subset: canary
          weight: 10
```

## Consequences

### Positive

1. **Automatic mTLS** - All service communication encrypted without code changes
2. **Observability** - Distributed tracing, metrics, and access logs
3. **Traffic management** - Canary deployments, A/B testing, fault injection
4. **Resilience** - Circuit breaking, retries, timeouts at infrastructure level
5. **Security policies** - Fine-grained authorization rules
6. **Consistent implementation** - Same patterns across all services

### Negative

1. **Complexity** - Additional infrastructure to manage
2. **Resource overhead** - Sidecar proxies consume CPU/memory
3. **Latency** - Sidecar adds ~1-2ms per hop
4. **Learning curve** - Team needs Istio expertise
5. **Debugging complexity** - More layers to troubleshoot

### Risks

1. **Sidecar injection failures** - Mitigated by admission controller monitoring
2. **Control plane outage** - Mitigated by high-availability Istiod deployment
3. **Version compatibility** - Mitigated by careful upgrade planning

## Alternatives Considered

### Linkerd

**Pros:**
- Simpler than Istio
- Lower resource overhead
- Faster startup

**Cons:**
- Fewer features
- Smaller ecosystem
- Less enterprise adoption

**Rejected because:** Istio's feature set better matches our requirements for traffic management and security policies.

### Consul Connect

**Pros:**
- Good service discovery
- Multi-datacenter support
- HashiCorp integration (pairs with Vault)

**Cons:**
- Less mature than Istio
- Smaller Kubernetes footprint
- Different architecture

**Rejected because:** Istio is the de facto standard for Kubernetes service mesh.

### App-Level Implementation

**Pros:**
- Full control
- No infrastructure dependency
- Simpler architecture

**Cons:**
- Significant development effort
- Inconsistent implementation
- Maintenance burden

**Rejected because:** Would require implementing mTLS, tracing, and circuit breaking in every service.

### No Service Mesh

**Pros:**
- Simplest architecture
- No overhead
- No learning curve

**Cons:**
- No mTLS between services
- Manual observability setup
- No traffic management

**Rejected because:** Security requirements mandate encrypted service-to-service communication.

## Validation

1. **mTLS verification** - Confirmed encryption on all internal traffic
2. **Performance testing** - Latency overhead within acceptable bounds
3. **Chaos testing** - Circuit breaking and failover validated
4. **Security audit** - Authorization policies reviewed

## References

- Istio Documentation: https://istio.io/latest/docs/
- Istio Best Practices: https://istio.io/latest/docs/ops/best-practices/
- Phase 3 Service Mesh Architecture Document
