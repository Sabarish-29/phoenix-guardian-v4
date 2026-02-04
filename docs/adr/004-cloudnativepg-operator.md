# ADR-004: CloudNativePG for Database Operations

## Status
Accepted

## Date
Day 105 (Phase 3)

## Context

Phoenix Guardian requires PostgreSQL for:
1. Multi-tenant data storage with RLS
2. HIPAA-compliant data handling
3. High availability (99.9%+ uptime)
4. Automated backups and point-in-time recovery
5. Seamless failover without application changes

Traditional PostgreSQL deployments require significant operational expertise for HA configuration, backup management, and failover orchestration.

## Decision

We will use CloudNativePG, a Kubernetes operator for PostgreSQL, to manage our database clusters with declarative configuration.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   CloudNativePG Operator                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐                                              │
│  │  CNPG Manager  │ ──► Monitors/Reconciles Clusters            │
│  └────────────────┘                                              │
└─────────────────────────────────────────────────────────────────┘
            │
            │ Manages
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PostgreSQL Cluster                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │    Primary      │  │   Replica 1     │  │   Replica 2     │  │
│  │   (pod/pvc)     │  │   (pod/pvc)     │  │   (pod/pvc)     │  │
│  │                 │  │                 │  │                 │  │
│  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────┐  │  │
│  │  │PostgreSQL │  │  │  │PostgreSQL │  │  │  │PostgreSQL │  │  │
│  │  │  Primary  │──┼──┼─►│  Replica  │  │  │  │  Replica  │  │  │
│  │  └───────────┘  │  │  └───────────┘  │  │  └───────────┘  │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                                │                                  │
│                   Streaming Replication                          │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    S3 Backup Storage                         │ │
│  │     WAL Archives │ Base Backups │ PITR Checkpoints          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Cluster Configuration

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: phoenix-guardian-db
  namespace: phoenix-guardian
spec:
  instances: 3
  
  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "2GB"
      effective_cache_size: "6GB"
      work_mem: "64MB"
      maintenance_work_mem: "512MB"
      wal_buffers: "64MB"
      checkpoint_completion_target: "0.9"
      wal_level: "replica"
      max_wal_senders: "10"
      random_page_cost: "1.1"
      effective_io_concurrency: "200"
      log_min_duration_statement: "1000"
  
  storage:
    size: 100Gi
    storageClass: gp3-encrypted
  
  backup:
    barmanObjectStore:
      destinationPath: s3://phoenix-guardian-backups/db
      s3Credentials:
        accessKeyId:
          name: aws-creds
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: aws-creds
          key: SECRET_ACCESS_KEY
      wal:
        compression: gzip
        maxParallel: 4
      data:
        compression: gzip
    retentionPolicy: "30d"
  
  monitoring:
    enablePodMonitor: true
  
  resources:
    requests:
      memory: "4Gi"
      cpu: "2"
    limits:
      memory: "8Gi"
      cpu: "4"
  
  affinity:
    enablePodAntiAffinity: true
    topologyKey: kubernetes.io/hostname
```

### Scheduled Backup Configuration

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: ScheduledBackup
metadata:
  name: daily-backup
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  backupOwnerReference: self
  cluster:
    name: phoenix-guardian-db
  immediate: false
  suspend: false
```

## Consequences

### Positive

1. **Declarative management** - Infrastructure as code for databases
2. **Automated failover** - <30 second failover with zero configuration
3. **Continuous WAL archiving** - Point-in-time recovery to any second
4. **Native Kubernetes** - Works with kubectl, Prometheus, GitOps
5. **High availability** - Synchronous replication across AZs
6. **Self-healing** - Automatic pod restart and replica rebuild
7. **TLS everywhere** - Encrypted connections by default

### Negative

1. **Operator dependency** - Tied to CNPG project health
2. **Kubernetes requirement** - Cannot run outside Kubernetes
3. **Learning curve** - Different from traditional PostgreSQL management
4. **Version lag** - New PostgreSQL versions take time to support
5. **PVC limitations** - Bound to PVC lifecycle and limitations

### Risks

1. **Operator bugs** - Mitigated by staging environment testing
2. **PVC corruption** - Mitigated by S3 backups and regular testing
3. **Failover storms** - Mitigated by careful probe configuration

## Alternatives Considered

### Managed PostgreSQL (RDS/Cloud SQL)

**Pros:**
- Fully managed
- Automatic patching
- Multi-AZ by default

**Cons:**
- Vendor lock-in
- Less configuration control
- Higher cost at scale
- Network latency to cloud service

**Rejected because:** Need for multi-cloud flexibility and fine-grained control for HIPAA compliance.

### Patroni + PostgreSQL

**Pros:**
- Battle-tested
- Flexible configuration
- Active community

**Cons:**
- More complex setup
- Requires etcd/Consul/ZooKeeper
- Manual manifest management

**Rejected because:** CloudNativePG provides similar capabilities with simpler Kubernetes-native management.

### CrunchyData PGO

**Pros:**
- Feature-rich
- Enterprise support available
- Good tooling

**Cons:**
- More complex than CNPG
- Larger resource footprint
- Commercial licensing

**Rejected because:** CloudNativePG meets our requirements with simpler architecture and CNCF backing.

### Zalando Postgres Operator

**Pros:**
- Production proven at Zalando
- Good documentation
- Active development

**Cons:**
- Zalando-specific patterns
- Less active than CNPG
- Complex configuration

**Rejected because:** CloudNativePG has better momentum and CNCF support.

## Validation

1. **Failover testing** - Primary failure recovers in <30 seconds
2. **Backup restoration** - PITR to any point in last 30 days
3. **Performance testing** - Query latency meets SLAs
4. **Chaos testing** - Pod deletion, network partition scenarios

## References

- CloudNativePG Documentation: https://cloudnative-pg.io/documentation/
- PostgreSQL High Availability: https://www.postgresql.org/docs/current/high-availability.html
- CNPG GitHub: https://github.com/cloudnative-pg/cloudnative-pg
