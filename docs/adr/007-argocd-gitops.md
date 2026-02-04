# ADR-007: ArgoCD for GitOps Deployment

## Status
Accepted

## Date
Day 140 (Phase 3)

## Context

Phoenix Guardian needs a robust deployment strategy that:
1. Enables continuous deployment with audit trail
2. Supports canary and blue-green deployments
3. Provides rollback capabilities
4. Maintains declarative configuration
5. Works with our multi-environment setup (dev, staging, prod)

## Decision

We will use ArgoCD as our GitOps continuous deployment tool.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Git Repository                            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  manifests/                                                 │ │
│  │  ├── base/                                                  │ │
│  │  │   ├── api-gateway/                                      │ │
│  │  │   ├── encounter-service/                                │ │
│  │  │   └── threat-detection/                                 │ │
│  │  └── overlays/                                             │ │
│  │      ├── development/                                      │ │
│  │      ├── staging/                                          │ │
│  │      └── production/                                       │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │ Watches
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                         ArgoCD                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    ArgoCD Server                           │ │
│  │  - Application Controller                                  │ │
│  │  - Repo Server                                             │ │
│  │  - API Server                                              │ │
│  │  - Redis (caching)                                         │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │ Syncs
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Kubernetes Clusters                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Development │  │   Staging   │  │  Production │              │
│  │   Cluster   │  │   Cluster   │  │   Cluster   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

### Application Configuration

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: phoenix-guardian-prod
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: phoenix-guardian
  
  source:
    repoURL: https://github.com/org/phoenix-guardian-manifests
    targetRevision: main
    path: manifests/overlays/production
    
  destination:
    server: https://prod-cluster.example.com
    namespace: phoenix-guardian
    
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
        
  # Health checks
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas  # Ignore HPA-managed replicas
```

### AppProject Configuration

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: phoenix-guardian
  namespace: argocd
spec:
  description: Phoenix Guardian Platform
  
  sourceRepos:
    - https://github.com/org/phoenix-guardian-manifests
    - https://charts.bitnami.com/bitnami
    
  destinations:
    - namespace: phoenix-guardian
      server: https://prod-cluster.example.com
    - namespace: phoenix-guardian
      server: https://staging-cluster.example.com
      
  clusterResourceWhitelist:
    - group: ''
      kind: Namespace
    - group: networking.k8s.io
      kind: NetworkPolicy
      
  namespaceResourceBlacklist:
    - group: ''
      kind: ResourceQuota
    - group: ''
      kind: LimitRange
      
  roles:
    - name: developer
      policies:
        - p, proj:phoenix-guardian:developer, applications, get, phoenix-guardian/*, allow
        - p, proj:phoenix-guardian:developer, applications, sync, phoenix-guardian/*-dev, allow
      groups:
        - phoenix-dev-team
        
    - name: deployer
      policies:
        - p, proj:phoenix-guardian:deployer, applications, *, phoenix-guardian/*, allow
      groups:
        - phoenix-sre-team
```

### Rollout Strategy

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: api-gateway
spec:
  replicas: 5
  strategy:
    canary:
      canaryService: api-gateway-canary
      stableService: api-gateway-stable
      trafficRouting:
        istio:
          virtualService:
            name: api-gateway-vsvc
            routes:
              - primary
      steps:
        - setWeight: 5
        - pause: { duration: 2m }
        - setWeight: 20
        - pause: { duration: 5m }
        - setWeight: 50
        - pause: { duration: 5m }
        - setWeight: 80
        - pause: { duration: 2m }
      analysis:
        templates:
          - templateName: success-rate
        startingStep: 2
        args:
          - name: service-name
            value: api-gateway
```

## Consequences

### Positive

1. **GitOps workflow** - Git is the single source of truth
2. **Audit trail** - All deployments tracked in git history
3. **Easy rollback** - Revert to any previous commit
4. **Declarative** - Desired state clearly defined
5. **Self-healing** - Automatic drift detection and correction
6. **Multi-cluster** - Single pane of glass for all environments
7. **UI/CLI** - Good developer experience

### Negative

1. **Learning curve** - Team needs ArgoCD expertise
2. **Git complexity** - Manifest repo management overhead
3. **Sync delays** - Not instant like kubectl apply
4. **Resource overhead** - ArgoCD components consume cluster resources
5. **Webhook dependency** - Relies on git webhooks for fast sync

### Risks

1. **ArgoCD outage** - Mitigated by HA deployment
2. **Manifest repo corruption** - Mitigated by branch protection
3. **Sync storms** - Mitigated by sync waves and resource limits

## Alternatives Considered

### Flux CD

**Pros:**
- CNCF project
- GitOps Toolkit
- Lighter weight

**Cons:**
- Less mature UI
- Smaller ecosystem
- Fewer integrations

**Rejected because:** ArgoCD has better UI, more features, and larger community.

### Jenkins X

**Pros:**
- Full CI/CD platform
- Preview environments
- Good Java ecosystem

**Cons:**
- Heavyweight
- Complex setup
- Less Kubernetes-native

**Rejected because:** We already have CI (GitHub Actions), need only CD.

### Spinnaker

**Pros:**
- Netflix-proven
- Multi-cloud
- Advanced deployment strategies

**Cons:**
- Very complex
- High resource requirements
- Steep learning curve

**Rejected because:** Overkill for our scale; ArgoCD is simpler.

### Helm + kubectl

**Pros:**
- Simple
- No additional tools
- Direct control

**Cons:**
- No GitOps
- No drift detection
- Manual process

**Rejected because:** Need automated, auditable deployments.

## Validation

1. **Deployment testing** - Automated sync verified
2. **Rollback testing** - Git revert triggers rollback
3. **Drift detection** - Manual changes detected and corrected
4. **Multi-env testing** - Dev → Staging → Prod promotion works

## References

- ArgoCD Documentation: https://argo-cd.readthedocs.io/
- GitOps Principles: https://opengitops.dev/
- ArgoCD Best Practices: https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/
