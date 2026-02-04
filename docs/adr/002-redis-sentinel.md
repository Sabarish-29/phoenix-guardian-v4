# ADR-002: Redis Sentinel for High Availability

## Status
Accepted

## Date
Day 98 (Phase 3)

## Context

Phoenix Guardian requires a high-availability caching layer for:
1. Session management and JWT token caching
2. Rate limiting across API pods
3. WebSocket connection coordination
4. Real-time dashboard data caching
5. Temporary transcription state

The caching layer must:
- Survive single node failures without data loss
- Provide sub-millisecond read latency
- Support pub/sub for real-time features
- Scale to 100,000+ operations/second
- Meet 99.9% availability SLA

## Decision

We will deploy Redis with Sentinel for high availability, using a 3-node primary + 2 replica configuration with 3 Sentinel instances for failover coordination.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Redis Sentinel Cluster                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │  Sentinel 1 │    │  Sentinel 2 │    │  Sentinel 3 │          │
│  │   (quorum)  │    │   (quorum)  │    │   (quorum)  │          │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘          │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                  │
│                            │                                     │
│  ┌─────────────────────────┼─────────────────────────┐          │
│  │                         ▼                         │          │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐│          │
│  │  │   Primary   │◄─│  Replica 1  │  │  Replica 2  ││          │
│  │  │   (write)   │  │   (read)    │  │   (read)    ││          │
│  │  └─────────────┘  └─────────────┘  └─────────────┘│          │
│  │         │                                         │          │
│  │         └────────────────────────────────────────►│          │
│  │                    Replication                    │          │
│  └───────────────────────────────────────────────────┘          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration

```yaml
# Redis primary configuration
redis:
  maxmemory: 8gb
  maxmemory-policy: volatile-lru
  appendonly: yes
  appendfsync: everysec
  repl-diskless-sync: yes
  tcp-keepalive: 300
  timeout: 0

# Sentinel configuration
sentinel:
  quorum: 2
  down-after-milliseconds: 5000
  failover-timeout: 30000
  parallel-syncs: 1
```

### Client Configuration

```python
from redis.sentinel import Sentinel

sentinel = Sentinel(
    [
        ('sentinel-1.redis.svc', 26379),
        ('sentinel-2.redis.svc', 26379),
        ('sentinel-3.redis.svc', 26379),
    ],
    socket_timeout=0.5,
    sentinel_kwargs={'password': SENTINEL_PASSWORD}
)

# Get primary for writes
primary = sentinel.master_for('phoenix-guardian', password=REDIS_PASSWORD)

# Get replica for reads
replica = sentinel.slave_for('phoenix-guardian', password=REDIS_PASSWORD)
```

## Consequences

### Positive

1. **Automatic failover** - <10 second failover on primary failure
2. **Read scaling** - Replicas handle read-heavy dashboard workloads
3. **Data persistence** - AOF ensures minimal data loss on failure
4. **Pub/Sub support** - Native support for real-time features
5. **Proven technology** - Battle-tested at scale

### Negative

1. **Failover disruption** - Brief write unavailability during failover
2. **Sentinel coordination** - Additional complexity vs standalone Redis
3. **Split-brain risk** - Network partitions can cause issues
4. **Client complexity** - Sentinel-aware clients required
5. **Memory cost** - Replication multiplies memory usage

### Risks

1. **Failover during peak load** - Mitigated by gradual connection drain
2. **Split-brain scenario** - Mitigated by minimum quorum of 2
3. **Memory pressure** - Mitigated by eviction policies and monitoring

## Alternatives Considered

### Redis Cluster

**Pros:**
- Horizontal scaling
- Data sharding
- Higher throughput

**Cons:**
- More complex client handling
- Multi-key operations limited
- Higher operational complexity

**Rejected because:** Our data size (<50GB) doesn't require sharding, and multi-key operations are needed for rate limiting.

### Managed Redis (ElastiCache/MemoryStore)

**Pros:**
- Managed service
- Automatic patching
- Built-in monitoring

**Cons:**
- Vendor lock-in
- Less configuration control
- Higher cost at scale

**Rejected because:** Need fine-grained control for HIPAA compliance and multi-cloud strategy.

### Memcached

**Pros:**
- Simple architecture
- Multi-threaded
- Lower memory overhead

**Cons:**
- No persistence
- No pub/sub
- No replication

**Rejected because:** Requires persistence for sessions and pub/sub for real-time.

### Dragonfly

**Pros:**
- Redis-compatible
- Better performance
- Lower memory usage

**Cons:**
- Less mature
- Smaller community
- Production readiness uncertain

**Rejected because:** Risk tolerance for healthcare platform requires proven technology.

## Validation

1. **Chaos testing** - Failover tested under load
2. **Performance testing** - 100K ops/sec validated
3. **Latency testing** - Sub-millisecond reads confirmed
4. **Data persistence testing** - Recovery after restarts validated

## References

- Redis Sentinel Documentation: https://redis.io/docs/management/sentinel/
- Redis High Availability: https://redis.io/docs/management/replication/
- HIPAA Data Caching Guidelines
