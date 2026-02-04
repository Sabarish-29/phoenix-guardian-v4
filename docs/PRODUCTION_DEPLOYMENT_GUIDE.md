# Phoenix Guardian Production Deployment Guide

**Version:** 3.0  
**Last Updated:** Week 35-36 (Phase 3 Close)  
**Classification:** Internal - Operations Team

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Prerequisites](#2-prerequisites)
3. [Architecture Overview](#3-architecture-overview)
4. [Infrastructure Setup](#4-infrastructure-setup)
5. [Database Deployment](#5-database-deployment)
6. [Application Deployment](#6-application-deployment)
7. [Security Configuration](#7-security-configuration)
8. [Monitoring Setup](#8-monitoring-setup)
9. [Disaster Recovery](#9-disaster-recovery)
10. [Verification Checklist](#10-verification-checklist)
11. [Troubleshooting](#11-troubleshooting)
12. [Appendix](#12-appendix)

---

## 1. Executive Summary

### 1.1 Purpose

This document provides comprehensive instructions for deploying Phoenix Guardian to production environments. It covers infrastructure provisioning, application deployment, security hardening, and operational verification.

### 1.2 Scope

- Multi-tenant SaaS deployment
- Single-hospital on-premises deployment
- Hybrid cloud deployment

### 1.3 Target Audience

- DevOps Engineers
- Site Reliability Engineers (SRE)
- Security Operations Teams
- IT Infrastructure Teams

### 1.4 Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 3.0 | Week 35-36 | Phoenix Team | Phase 3 completion, multi-language, federated learning |
| 2.5 | Week 30 | Phoenix Team | Mobile support, offline sync |
| 2.0 | Week 20 | Phoenix Team | Multi-tenant architecture |
| 1.0 | Week 10 | Phoenix Team | Initial production deployment |

---

## 2. Prerequisites

### 2.1 Required Access

```yaml
Cloud Provider Access:
  - AWS Account with OrganizationAdmin role
  - GCP Project with Owner role (for Whisper API)
  - Azure AD for healthcare SSO integration

Kubernetes Access:
  - kubectl configured with cluster-admin
  - Helm 3.10+ installed
  - ArgoCD admin access

Database Access:
  - PostgreSQL 15+ admin credentials
  - Redis 7+ admin credentials

Security Tools:
  - Vault admin access
  - PagerDuty admin access
  - SOC 2 compliance portal access
```

### 2.2 Software Requirements

```yaml
Local Development:
  - Docker Desktop 4.20+
  - kubectl 1.28+
  - Helm 3.10+
  - Terraform 1.5+
  - Python 3.11+
  - Node.js 18+

CI/CD Tools:
  - GitHub Actions / GitLab CI
  - ArgoCD 2.8+
  - Tekton Pipelines 0.50+
```

### 2.3 Hardware Requirements

#### Production Cluster (50 Hospitals)

```yaml
Kubernetes Nodes:
  Master Nodes: 3x c5.2xlarge (8 vCPU, 16GB RAM)
  Worker Nodes: 12x c5.4xlarge (16 vCPU, 32GB RAM)
  GPU Nodes: 4x g4dn.2xlarge (NVIDIA T4, 8 vCPU, 32GB RAM)
  
Storage:
  - 2TB SSD for databases (GP3 IOPS: 16,000)
  - 10TB HDD for audio archives
  - 500GB SSD for Redis

Network:
  - 10 Gbps inter-node bandwidth
  - Dedicated NAT Gateway
  - VPN Gateway for EHR connectivity
```

#### Scaling Guidelines

| Hospitals | Worker Nodes | GPU Nodes | Database Replicas |
|-----------|--------------|-----------|-------------------|
| 1-10 | 3 | 1 | 1 |
| 11-50 | 6 | 2 | 2 |
| 51-100 | 12 | 4 | 3 |
| 101-250 | 24 | 8 | 5 |
| 251-500 | 48 | 16 | 7 |

---

## 3. Architecture Overview

### 3.1 High-Level Architecture

```
                                   ┌─────────────────────────────────┐
                                   │         CDN (CloudFront)        │
                                   └─────────────┬───────────────────┘
                                                 │
                              ┌──────────────────┴──────────────────┐
                              │         AWS WAF + Shield            │
                              └──────────────────┬──────────────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    │                    ALB + NLB                            │
                    └────────────────────────────┼────────────────────────────┘
                                                 │
         ┌───────────────────────────────────────┼───────────────────────────────────────┐
         │                                       │                                       │
         │                              Kubernetes Cluster                               │
         │                                       │                                       │
         │   ┌─────────────────┐   ┌─────────────┴───────────────┐   ┌─────────────────┐ │
         │   │  Ingress NGINX  │   │      Service Mesh (Istio)   │   │   Cert Manager  │ │
         │   └────────┬────────┘   └─────────────────────────────┘   └─────────────────┘ │
         │            │                                                                  │
         │   ┌────────┴────────────────────────────────────────────────────────┐         │
         │   │                         Namespaces                              │         │
         │   │                                                                 │         │
         │   │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │         │
         │   │  │ phoenix-api     │  │ phoenix-ai      │  │ phoenix-data    │  │         │
         │   │  │ - API Gateway   │  │ - Transcription │  │ - PostgreSQL    │  │         │
         │   │  │ - Auth Service  │  │ - AI Engine     │  │ - Redis         │  │         │
         │   │  │ - Dashboard     │  │ - Threat Detect │  │ - Kafka         │  │         │
         │   │  └─────────────────┘  └─────────────────┘  └─────────────────┘  │         │
         │   │                                                                 │         │
         │   │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │         │
         │   │  │ phoenix-security│  │ phoenix-fed     │  │ phoenix-monitor │  │         │
         │   │  │ - Honeypots     │  │ - Fed Learning  │  │ - Prometheus    │  │         │
         │   │  │ - SIEM Agent    │  │ - Aggregation   │  │ - Grafana       │  │         │
         │   │  │ - Vault Agent   │  │ - Privacy       │  │ - Alertmanager  │  │         │
         │   │  └─────────────────┘  └─────────────────┘  └─────────────────┘  │         │
         │   └─────────────────────────────────────────────────────────────────┘         │
         │                                                                               │
         └───────────────────────────────────────────────────────────────────────────────┘
                                                 │
                    ┌────────────────────────────┴────────────────────────────┐
                    │                    External Services                    │
                    │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐ │
                    │  │ EHR     │  │ PagerDuty│  │ SIEM    │  │ Consortium  │ │
                    │  │ Systems │  │         │  │         │  │ (Federated) │ │
                    │  └─────────┘  └─────────┘  └─────────┘  └─────────────┘ │
                    └─────────────────────────────────────────────────────────┘
```

### 3.2 Namespace Architecture

```yaml
Namespaces:
  phoenix-api:
    - api-gateway (3 replicas)
    - auth-service (3 replicas)
    - dashboard-backend (3 replicas)
    - mobile-api (3 replicas)
    
  phoenix-ai:
    - transcription-service (5 replicas, GPU)
    - soap-generator (3 replicas, GPU)
    - threat-detector (3 replicas)
    - language-detector (2 replicas)
    
  phoenix-data:
    - postgresql-primary (1 pod)
    - postgresql-replica (2 pods)
    - redis-sentinel (3 pods)
    - kafka-broker (3 pods)
    
  phoenix-security:
    - honeypot-controller (2 replicas)
    - siem-agent (DaemonSet)
    - vault-agent (Sidecar)
    - threat-response (2 replicas)
    
  phoenix-fed:
    - federation-aggregator (2 replicas)
    - privacy-engine (2 replicas)
    - signature-generator (2 replicas)
    
  phoenix-monitor:
    - prometheus (2 replicas)
    - grafana (2 replicas)
    - alertmanager (3 replicas)
    - loki (3 replicas)
```

---

## 4. Infrastructure Setup

### 4.1 Terraform Infrastructure

#### Initialize Terraform

```bash
# Clone infrastructure repository
git clone https://github.com/phoenix-guardian/infrastructure.git
cd infrastructure/terraform/environments/production

# Initialize Terraform
terraform init \
  -backend-config="bucket=phoenix-terraform-state" \
  -backend-config="key=prod/terraform.tfstate" \
  -backend-config="region=us-east-1"
```

#### Main Infrastructure Variables

```hcl
# terraform.tfvars
environment = "production"
region      = "us-east-1"
dr_region   = "us-west-2"

# VPC Configuration
vpc_cidr = "10.0.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]

# EKS Configuration
eks_cluster_version = "1.28"
eks_node_groups = {
  general = {
    instance_types = ["c5.4xlarge"]
    desired_size   = 6
    min_size       = 3
    max_size       = 12
  }
  gpu = {
    instance_types = ["g4dn.2xlarge"]
    desired_size   = 2
    min_size       = 1
    max_size       = 8
    gpu_enabled    = true
  }
}

# Database Configuration
rds_instance_class     = "db.r6g.2xlarge"
rds_multi_az          = true
rds_read_replicas     = 2
elasticache_node_type = "cache.r6g.xlarge"
elasticache_num_nodes = 3

# Security
enable_waf           = true
enable_shield        = true
enable_guardduty     = true
enable_securityhub   = true

# Compliance
hipaa_compliance     = true
soc2_compliance      = true
```

#### Apply Infrastructure

```bash
# Plan changes
terraform plan -out=tfplan

# Apply (requires approval)
terraform apply tfplan

# Export outputs for later use
terraform output -json > infrastructure-outputs.json
```

### 4.2 Kubernetes Cluster Setup

#### Configure kubectl

```bash
# Update kubeconfig
aws eks update-kubeconfig \
  --region us-east-1 \
  --name phoenix-guardian-prod \
  --alias phoenix-prod

# Verify connection
kubectl cluster-info
kubectl get nodes
```

#### Install Core Components

```bash
# Install Ingress NGINX
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --values infrastructure/helm/ingress-nginx-values.yaml

# Install Cert Manager
helm repo add jetstack https://charts.jetstack.io
helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true \
  --values infrastructure/helm/cert-manager-values.yaml

# Install Istio Service Mesh
istioctl install --set profile=production -y
kubectl label namespace default istio-injection=enabled
```

### 4.3 Create Namespaces

```bash
# Create all namespaces
kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: phoenix-api
  labels:
    istio-injection: enabled
    environment: production
---
apiVersion: v1
kind: Namespace
metadata:
  name: phoenix-ai
  labels:
    istio-injection: enabled
    environment: production
---
apiVersion: v1
kind: Namespace
metadata:
  name: phoenix-data
  labels:
    environment: production
---
apiVersion: v1
kind: Namespace
metadata:
  name: phoenix-security
  labels:
    istio-injection: enabled
    environment: production
---
apiVersion: v1
kind: Namespace
metadata:
  name: phoenix-fed
  labels:
    istio-injection: enabled
    environment: production
---
apiVersion: v1
kind: Namespace
metadata:
  name: phoenix-monitor
  labels:
    environment: production
EOF
```

---

## 5. Database Deployment

### 5.1 PostgreSQL Setup

#### Deploy CloudNativePG Operator

```bash
# Install operator
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm upgrade --install cnpg cnpg/cloudnative-pg \
  --namespace cnpg-system \
  --create-namespace

# Wait for operator
kubectl wait --for=condition=available deployment/cnpg-controller-manager \
  -n cnpg-system --timeout=120s
```

#### Deploy PostgreSQL Cluster

```yaml
# postgresql-cluster.yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: phoenix-db
  namespace: phoenix-data
spec:
  instances: 3
  
  imageName: ghcr.io/cloudnative-pg/postgresql:15.4
  
  postgresql:
    parameters:
      max_connections: "500"
      shared_buffers: "4GB"
      effective_cache_size: "12GB"
      maintenance_work_mem: "512MB"
      checkpoint_completion_target: "0.9"
      wal_buffers: "64MB"
      default_statistics_target: "100"
      random_page_cost: "1.1"
      effective_io_concurrency: "200"
      work_mem: "16MB"
      min_wal_size: "2GB"
      max_wal_size: "8GB"
      max_worker_processes: "8"
      max_parallel_workers_per_gather: "4"
      max_parallel_workers: "8"
      max_parallel_maintenance_workers: "4"
      
      # Security
      ssl: "on"
      ssl_min_protocol_version: "TLSv1.3"
      
      # Auditing
      log_statement: "all"
      log_connections: "on"
      log_disconnections: "on"
      
  storage:
    storageClass: gp3-encrypted
    size: 500Gi
    
  walStorage:
    storageClass: gp3-encrypted
    size: 100Gi
    
  backup:
    barmanObjectStore:
      destinationPath: s3://phoenix-db-backup/prod
      s3Credentials:
        accessKeyId:
          name: aws-credentials
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: aws-credentials
          key: SECRET_ACCESS_KEY
      wal:
        compression: gzip
      data:
        compression: gzip
    retentionPolicy: "30d"
    
  monitoring:
    enablePodMonitor: true
    
  affinity:
    podAntiAffinityType: required
```

```bash
# Apply PostgreSQL cluster
kubectl apply -f postgresql-cluster.yaml

# Wait for cluster
kubectl wait --for=condition=Ready cluster/phoenix-db \
  -n phoenix-data --timeout=600s

# Get connection credentials
kubectl get secret phoenix-db-app -n phoenix-data \
  -o jsonpath='{.data.password}' | base64 -d
```

#### Initialize Database Schema

```bash
# Connect to primary
kubectl exec -it phoenix-db-1 -n phoenix-data -- psql -U app

# Run schema migration
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration
  namespace: phoenix-api
spec:
  template:
    spec:
      containers:
      - name: migrate
        image: ghcr.io/phoenix-guardian/api:latest
        command: ["python", "-m", "alembic", "upgrade", "head"]
        envFrom:
        - secretRef:
            name: database-credentials
      restartPolicy: Never
  backoffLimit: 3
EOF
```

### 5.2 Row-Level Security Setup

```sql
-- Enable RLS on all PHI tables
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE encounters ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE soap_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Create tenant isolation policy
CREATE POLICY tenant_isolation ON patients
  USING (tenant_id = current_setting('app.current_tenant')::uuid);

CREATE POLICY tenant_isolation ON encounters
  USING (tenant_id = current_setting('app.current_tenant')::uuid);

CREATE POLICY tenant_isolation ON transcriptions
  USING (tenant_id = current_setting('app.current_tenant')::uuid);

CREATE POLICY tenant_isolation ON soap_notes
  USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Audit log policy (security team can see all)
CREATE POLICY audit_tenant_isolation ON audit_logs
  USING (
    tenant_id = current_setting('app.current_tenant')::uuid
    OR current_setting('app.security_admin')::boolean = true
  );
```

### 5.3 Redis Sentinel Setup

```yaml
# redis-sentinel.yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: redis
  namespace: phoenix-data
spec:
  interval: 1h
  chart:
    spec:
      chart: redis
      version: "18.x"
      sourceRef:
        kind: HelmRepository
        name: bitnami
  values:
    architecture: replication
    
    auth:
      enabled: true
      sentinel: true
      existingSecret: redis-credentials
      existingSecretPasswordKey: password
      
    master:
      resources:
        requests:
          cpu: "2"
          memory: "4Gi"
        limits:
          cpu: "4"
          memory: "8Gi"
      persistence:
        enabled: true
        storageClass: gp3-encrypted
        size: 50Gi
        
    replica:
      replicaCount: 2
      resources:
        requests:
          cpu: "2"
          memory: "4Gi"
        limits:
          cpu: "4"
          memory: "8Gi"
          
    sentinel:
      enabled: true
      quorum: 2
      resources:
        requests:
          cpu: "100m"
          memory: "128Mi"
          
    metrics:
      enabled: true
      serviceMonitor:
        enabled: true
```

---

## 6. Application Deployment

### 6.1 ArgoCD Application Setup

```yaml
# argocd-application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: phoenix-guardian
  namespace: argocd
spec:
  project: production
  
  source:
    repoURL: https://github.com/phoenix-guardian/manifests
    targetRevision: v3.0.0
    path: overlays/production
    
  destination:
    server: https://kubernetes.default.svc
    namespace: phoenix-api
    
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
    - PrunePropagationPolicy=foreground
    - PruneLast=true
    
  ignoreDifferences:
  - group: "*"
    kind: Secret
    jsonPointers:
    - /data
```

### 6.2 Core Service Deployments

#### API Gateway

```yaml
# api-gateway-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: phoenix-api
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
        version: v3.0.0
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
    spec:
      serviceAccountName: api-gateway
      
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchLabels:
                app: api-gateway
            topologyKey: kubernetes.io/hostname
            
      containers:
      - name: api-gateway
        image: ghcr.io/phoenix-guardian/api-gateway:v3.0.0
        ports:
        - containerPort: 8080
          name: http
        - containerPort: 9090
          name: metrics
          
        env:
        - name: ENVIRONMENT
          value: production
        - name: LOG_LEVEL
          value: info
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: http://otel-collector:4317
          
        envFrom:
        - secretRef:
            name: api-gateway-secrets
        - configMapRef:
            name: api-gateway-config
            
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "2"
            memory: "2Gi"
            
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
          
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
          
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          readOnlyRootFilesystem: true
          allowPrivilegeEscalation: false
          capabilities:
            drop:
            - ALL
            
      - name: vault-agent
        image: hashicorp/vault:1.15
        args:
        - agent
        - -config=/vault/config/agent.hcl
        volumeMounts:
        - name: vault-config
          mountPath: /vault/config
        - name: secrets
          mountPath: /vault/secrets
          
      volumes:
      - name: vault-config
        configMap:
          name: vault-agent-config
      - name: secrets
        emptyDir:
          medium: Memory
```

#### Transcription Service (GPU)

```yaml
# transcription-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: transcription-service
  namespace: phoenix-ai
spec:
  replicas: 5
  selector:
    matchLabels:
      app: transcription-service
  template:
    metadata:
      labels:
        app: transcription-service
    spec:
      serviceAccountName: transcription-service
      
      nodeSelector:
        nvidia.com/gpu: "true"
        
      tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule
        
      containers:
      - name: transcription
        image: ghcr.io/phoenix-guardian/transcription:v3.0.0
        
        resources:
          requests:
            cpu: "4"
            memory: "16Gi"
            nvidia.com/gpu: "1"
          limits:
            cpu: "8"
            memory: "32Gi"
            nvidia.com/gpu: "1"
            
        env:
        - name: WHISPER_MODEL
          value: "large-v3"
        - name: SUPPORTED_LANGUAGES
          value: "en,es,zh,ar,hi,pt,fr"
        - name: MAX_CONCURRENT_TRANSCRIPTIONS
          value: "4"
        - name: CUDA_VISIBLE_DEVICES
          value: "0"
          
        volumeMounts:
        - name: model-cache
          mountPath: /models
        - name: audio-temp
          mountPath: /tmp/audio
          
      volumes:
      - name: model-cache
        persistentVolumeClaim:
          claimName: whisper-models
      - name: audio-temp
        emptyDir:
          medium: Memory
          sizeLimit: 2Gi
```

### 6.3 Horizontal Pod Autoscaler

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: phoenix-api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: 1000
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
      - type: Pods
        value: 4
        periodSeconds: 15
      selectPolicy: Max
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: transcription-hpa
  namespace: phoenix-ai
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: transcription-service
  minReplicas: 2
  maxReplicas: 16
  metrics:
  - type: Pods
    pods:
      metric:
        name: transcription_queue_depth
      target:
        type: AverageValue
        averageValue: 5
```

### 6.4 Pod Disruption Budget

```yaml
# pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway-pdb
  namespace: phoenix-api
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: api-gateway
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: transcription-pdb
  namespace: phoenix-ai
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: transcription-service
```

---

## 7. Security Configuration

### 7.1 Network Policies

```yaml
# network-policies.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-gateway-policy
  namespace: phoenix-api
spec:
  podSelector:
    matchLabels:
      app: api-gateway
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: phoenix-data
    ports:
    - protocol: TCP
      port: 5432
    - protocol: TCP
      port: 6379
  - to:
    - namespaceSelector:
        matchLabels:
          name: phoenix-ai
    ports:
    - protocol: TCP
      port: 8080
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: database-policy
  namespace: phoenix-data
spec:
  podSelector:
    matchLabels:
      app: postgresql
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          environment: production
    ports:
    - protocol: TCP
      port: 5432
```

### 7.2 Vault Integration

```yaml
# vault-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: vault-agent-config
  namespace: phoenix-api
data:
  agent.hcl: |
    vault {
      address = "https://vault.phoenix-guardian.internal:8200"
    }
    
    auto_auth {
      method "kubernetes" {
        mount_path = "auth/kubernetes"
        config = {
          role = "phoenix-api"
        }
      }
      
      sink "file" {
        config = {
          path = "/vault/secrets/.token"
        }
      }
    }
    
    template {
      destination = "/vault/secrets/database.env"
      contents = <<EOT
      {{ with secret "database/creds/phoenix-api" }}
      DATABASE_URL=postgresql://{{ .Data.username }}:{{ .Data.password }}@phoenix-db-rw:5432/phoenix
      {{ end }}
      EOT
    }
    
    template {
      destination = "/vault/secrets/jwt.key"
      contents = <<EOT
      {{ with secret "secret/data/phoenix/jwt" }}
      {{ .Data.data.private_key }}
      {{ end }}
      EOT
    }
```

### 7.3 TLS Configuration

```yaml
# tls-certificates.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: security@phoenix-guardian.health
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: phoenix-guardian-tls
  namespace: phoenix-api
spec:
  secretName: phoenix-guardian-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  commonName: api.phoenix-guardian.health
  dnsNames:
  - api.phoenix-guardian.health
  - dashboard.phoenix-guardian.health
  - "*.phoenix-guardian.health"
```

### 7.4 RBAC Configuration

```yaml
# rbac.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: api-gateway-role
  namespace: phoenix-api
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get"]
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: api-gateway-binding
  namespace: phoenix-api
subjects:
- kind: ServiceAccount
  name: api-gateway
  namespace: phoenix-api
roleRef:
  kind: Role
  name: api-gateway-role
  apiGroup: rbac.authorization.k8s.io
```

---

## 8. Monitoring Setup

### 8.1 Prometheus Stack

```yaml
# prometheus-stack.yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: prometheus-stack
  namespace: phoenix-monitor
spec:
  interval: 1h
  chart:
    spec:
      chart: kube-prometheus-stack
      version: "54.x"
      sourceRef:
        kind: HelmRepository
        name: prometheus-community
  values:
    prometheus:
      prometheusSpec:
        retention: 30d
        storageSpec:
          volumeClaimTemplate:
            spec:
              storageClassName: gp3-encrypted
              resources:
                requests:
                  storage: 200Gi
        additionalScrapeConfigs:
        - job_name: phoenix-services
          kubernetes_sd_configs:
          - role: pod
            namespaces:
              names:
              - phoenix-api
              - phoenix-ai
              - phoenix-security
              
    alertmanager:
      config:
        global:
          resolve_timeout: 5m
          pagerduty_url: https://events.pagerduty.com/v2/enqueue
        route:
          receiver: pagerduty-critical
          routes:
          - match:
              severity: critical
            receiver: pagerduty-critical
          - match:
              severity: warning
            receiver: pagerduty-warning
        receivers:
        - name: pagerduty-critical
          pagerduty_configs:
          - routing_key_file: /etc/alertmanager/secrets/pagerduty-routing-key
            severity: critical
        - name: pagerduty-warning
          pagerduty_configs:
          - routing_key_file: /etc/alertmanager/secrets/pagerduty-routing-key
            severity: warning
            
    grafana:
      adminPassword: ${GRAFANA_ADMIN_PASSWORD}
      persistence:
        enabled: true
        size: 10Gi
      dashboardProviders:
        dashboardproviders.yaml:
          apiVersion: 1
          providers:
          - name: phoenix-dashboards
            folder: Phoenix Guardian
            type: file
            options:
              path: /var/lib/grafana/dashboards/phoenix
```

### 8.2 Custom Alerts

```yaml
# phoenix-alerts.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: phoenix-alerts
  namespace: phoenix-monitor
spec:
  groups:
  - name: phoenix-critical
    rules:
    - alert: ThreatDetectionHigh
      expr: |
        sum(rate(phoenix_threats_detected_total{severity="critical"}[5m])) > 0.1
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: High rate of critical threats detected
        description: |
          Critical threat detection rate is {{ $value }}/s over the last 5 minutes.
          
    - alert: TranscriptionLatencyHigh
      expr: |
        histogram_quantile(0.95, 
          rate(phoenix_transcription_duration_seconds_bucket[5m])
        ) > 30
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: Transcription latency SLA breach
        description: P95 transcription latency is {{ $value }}s (SLA: 30s)
        
    - alert: EncounterFlowSlowdown
      expr: |
        histogram_quantile(0.95,
          rate(phoenix_encounter_duration_seconds_bucket[5m])
        ) > 120
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: Encounter flow exceeding 2 minute SLA
        description: P95 encounter completion time is {{ $value }}s
        
    - alert: DatabaseConnectionPoolExhausted
      expr: |
        pg_stat_activity_count / pg_settings_max_connections > 0.9
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: Database connection pool near exhaustion
        description: Connection usage at {{ $value | humanizePercentage }}
        
    - alert: HighErrorRate
      expr: |
        sum(rate(http_requests_total{status=~"5.."}[5m])) /
        sum(rate(http_requests_total[5m])) > 0.01
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: API error rate above 1%
        description: Current error rate is {{ $value | humanizePercentage }}
```

---

## 9. Disaster Recovery

### 9.1 Backup Configuration

```yaml
# backup-schedule.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: database-backup
  namespace: phoenix-data
spec:
  schedule: "0 */4 * * *"  # Every 4 hours
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: ghcr.io/phoenix-guardian/backup-tools:latest
            command:
            - /bin/sh
            - -c
            - |
              pg_dump -h phoenix-db-rw -U phoenix -d phoenix \
                | gzip \
                | aws s3 cp - s3://phoenix-backup-prod/db/$(date +%Y%m%d_%H%M%S).sql.gz
            envFrom:
            - secretRef:
                name: backup-credentials
          restartPolicy: OnFailure
```

### 9.2 DR Failover Procedure

```bash
#!/bin/bash
# dr-failover.sh - Disaster Recovery Failover Script

set -e

echo "=== Phoenix Guardian DR Failover ==="
echo "Starting failover to DR region: us-west-2"

# 1. Verify DR database is synced
echo "Step 1: Checking database replication lag..."
REPLICATION_LAG=$(psql -h phoenix-db-dr.us-west-2 -U postgres -t -c \
  "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))::integer;")

if [ "$REPLICATION_LAG" -gt 60 ]; then
  echo "ERROR: Replication lag is ${REPLICATION_LAG}s (max: 60s)"
  exit 1
fi
echo "Replication lag: ${REPLICATION_LAG}s - OK"

# 2. Promote DR database
echo "Step 2: Promoting DR database to primary..."
kubectl exec -n phoenix-data phoenix-db-dr-1 -- \
  pg_ctl promote -D /var/lib/postgresql/data

# 3. Update DNS
echo "Step 3: Updating DNS to DR region..."
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890 \
  --change-batch file://dr-dns-change.json

# 4. Scale DR workloads
echo "Step 4: Scaling DR workloads..."
kubectl config use-context phoenix-dr
kubectl scale deployment --all --replicas=3 -n phoenix-api
kubectl scale deployment --all --replicas=3 -n phoenix-ai

# 5. Verify health
echo "Step 5: Verifying DR health..."
for i in {1..30}; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://api.phoenix-guardian.health/health)
  if [ "$HTTP_CODE" == "200" ]; then
    echo "Health check passed!"
    break
  fi
  echo "Waiting for services... (attempt $i/30)"
  sleep 10
done

echo "=== Failover Complete ==="
echo "DR region is now serving production traffic"
```

---

## 10. Verification Checklist

### 10.1 Pre-Deployment Checklist

```markdown
## Pre-Deployment Verification

### Infrastructure
- [ ] Terraform plan shows no unexpected changes
- [ ] All nodes are Ready in kubectl get nodes
- [ ] Ingress controller is healthy
- [ ] Cert-manager certificates are valid
- [ ] Vault is unsealed and accessible

### Database
- [ ] PostgreSQL cluster has 3 healthy pods
- [ ] Replication is working (check pg_stat_replication)
- [ ] RLS policies are enabled on all PHI tables
- [ ] Backup job completed successfully in last 24h
- [ ] DR replica lag < 60 seconds

### Security
- [ ] Network policies applied to all namespaces
- [ ] No pods running as root
- [ ] All secrets are in Vault, not K8s secrets
- [ ] WAF rules are active
- [ ] GuardDuty has no critical findings

### Compliance
- [ ] SOC 2 evidence collector running
- [ ] Audit logging enabled
- [ ] Data retention policies configured
- [ ] Access reviews completed this quarter
```

### 10.2 Post-Deployment Verification

```bash
#!/bin/bash
# post-deployment-verification.sh

echo "=== Post-Deployment Verification ==="

# 1. Check all pods running
echo "1. Checking pod status..."
UNHEALTHY=$(kubectl get pods -A | grep -v "Running\|Completed" | grep "phoenix" | wc -l)
if [ "$UNHEALTHY" -gt 0 ]; then
  echo "WARNING: $UNHEALTHY unhealthy pods found"
  kubectl get pods -A | grep -v "Running\|Completed" | grep "phoenix"
fi

# 2. Check endpoints
echo "2. Checking API endpoints..."
ENDPOINTS=(
  "https://api.phoenix-guardian.health/health"
  "https://api.phoenix-guardian.health/api/v1/status"
  "https://dashboard.phoenix-guardian.health/health"
)
for endpoint in "${ENDPOINTS[@]}"; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$endpoint")
  echo "  $endpoint: $HTTP_CODE"
done

# 3. Check database connectivity
echo "3. Checking database connectivity..."
kubectl exec -n phoenix-api deploy/api-gateway -- \
  python -c "from app.db import get_db; print('DB OK')"

# 4. Check Redis connectivity
echo "4. Checking Redis connectivity..."
kubectl exec -n phoenix-api deploy/api-gateway -- \
  python -c "from app.cache import redis_client; redis_client.ping(); print('Redis OK')"

# 5. Check threat detection
echo "5. Checking threat detection service..."
curl -s https://api.phoenix-guardian.health/api/v1/threats/health | jq .

# 6. Run smoke tests
echo "6. Running smoke tests..."
kubectl run smoke-test \
  --image=ghcr.io/phoenix-guardian/test-runner:latest \
  --rm -it --restart=Never -- \
  pytest tests/smoke/ -v

echo "=== Verification Complete ==="
```

---

## 11. Troubleshooting

### 11.1 Common Issues

#### Pod CrashLoopBackOff

```bash
# Get pod logs
kubectl logs <pod-name> -n <namespace> --previous

# Check events
kubectl describe pod <pod-name> -n <namespace>

# Common causes:
# 1. Missing secrets/configmaps
# 2. Database connection failure
# 3. Insufficient resources
# 4. Liveness probe failure
```

#### Database Connection Issues

```bash
# Check PostgreSQL cluster status
kubectl cnpg status phoenix-db -n phoenix-data

# Check connection from app pod
kubectl exec -n phoenix-api deploy/api-gateway -- \
  pg_isready -h phoenix-db-rw -p 5432 -U app

# Check connection pool
kubectl exec -n phoenix-data phoenix-db-1 -- \
  psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
```

#### High Latency

```bash
# Check Istio sidecar metrics
kubectl exec -n phoenix-api deploy/api-gateway -c istio-proxy -- \
  curl -s localhost:15020/stats/prometheus | grep request_duration

# Check network policies
kubectl get networkpolicy -A -o yaml

# Profile application
kubectl port-forward -n phoenix-api deploy/api-gateway 8080:8080
curl http://localhost:8080/debug/pprof/profile?seconds=30 > cpu.prof
```

### 11.2 Emergency Procedures

#### Emergency Pod Kill

```bash
# If a pod is causing issues, force delete
kubectl delete pod <pod-name> -n <namespace> --grace-period=0 --force
```

#### Emergency Rollback

```bash
# Rollback to previous deployment
kubectl rollout undo deployment/<deployment-name> -n <namespace>

# Or rollback to specific revision
kubectl rollout undo deployment/<deployment-name> -n <namespace> --to-revision=<revision>

# Check rollout status
kubectl rollout status deployment/<deployment-name> -n <namespace>
```

#### Circuit Breaker Activation

```bash
# Enable maintenance mode
kubectl set env deployment/api-gateway MAINTENANCE_MODE=true -n phoenix-api

# Disable specific feature
kubectl set env deployment/api-gateway FEATURE_TRANSCRIPTION=false -n phoenix-api
```

---

## 12. Appendix

### 12.1 Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Deployment environment | `production` |
| `LOG_LEVEL` | Logging verbosity | `info` |
| `DATABASE_URL` | PostgreSQL connection string | - |
| `REDIS_URL` | Redis connection string | - |
| `VAULT_ADDR` | Vault server address | - |
| `WHISPER_MODEL` | Whisper model to use | `large-v3` |
| `JWT_SECRET_KEY` | JWT signing key | - |
| `PAGERDUTY_ROUTING_KEY` | PagerDuty integration key | - |

### 12.2 Port Reference

| Service | Port | Protocol |
|---------|------|----------|
| API Gateway | 8080 | HTTP |
| API Gateway Metrics | 9090 | HTTP |
| PostgreSQL | 5432 | TCP |
| Redis | 6379 | TCP |
| Redis Sentinel | 26379 | TCP |
| Kafka | 9092 | TCP |
| Prometheus | 9090 | HTTP |
| Grafana | 3000 | HTTP |

### 12.3 Contact Information

| Role | Name | Contact |
|------|------|---------|
| On-Call Engineer | PagerDuty | @phoenix-oncall |
| Database Admin | DBA Team | dba@phoenix-guardian.health |
| Security | Security Team | security@phoenix-guardian.health |
| Platform | SRE Team | sre@phoenix-guardian.health |

---

*Document maintained by Phoenix Guardian Platform Team*  
*Last review: Week 35-36*  
*Next scheduled review: Week 45 (Phase 4)*
