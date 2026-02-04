# Phoenix Guardian On-Call Runbook

**Version:** 3.0  
**Last Updated:** Week 35-36 (Phase 3 Close)  
**Classification:** Internal - Operations Team Only

---

## Table of Contents

1. [On-Call Overview](#1-on-call-overview)
2. [Incident Response](#2-incident-response)
3. [Alert Playbooks](#3-alert-playbooks)
4. [Service-Specific Runbooks](#4-service-specific-runbooks)
5. [Database Operations](#5-database-operations)
6. [Security Incidents](#6-security-incidents)
7. [Performance Issues](#7-performance-issues)
8. [Disaster Recovery](#8-disaster-recovery)
9. [Escalation Procedures](#9-escalation-procedures)
10. [Post-Incident](#10-post-incident)

---

## 1. On-Call Overview

### 1.1 On-Call Rotation

```yaml
Primary On-Call:
  Schedule: Weekly rotation (Monday 9AM - Monday 9AM UTC)
  Response SLA: 
    - P1 (Critical): 5 minutes
    - P2 (High): 15 minutes
    - P3 (Medium): 1 hour
    - P4 (Low): 4 hours

Secondary On-Call:
  Purpose: Backup for primary, escalation point
  Response SLA: 15 minutes after escalation

Management On-Call:
  Purpose: Customer communication, major incident coordination
  Response SLA: 30 minutes for P1/P2
```

### 1.2 Tools Access Required

```yaml
Required Access:
  - PagerDuty: Acknowledge and resolve incidents
  - Grafana: View dashboards and metrics
  - Prometheus: Query metrics
  - AWS Console: Infrastructure access
  - kubectl: Kubernetes cluster access
  - Vault: Secret management
  - GitHub: Access to runbooks and code
  - Slack: #phoenix-incidents channel
  - Zoom: Incident bridge

Access Verification:
  Run: ./scripts/verify-oncall-access.sh
```

### 1.3 Quick Reference Card

```
┌────────────────────────────────────────────────────────────┐
│              PHOENIX GUARDIAN QUICK REFERENCE              │
├────────────────────────────────────────────────────────────┤
│ Dashboards                                                 │
│   Main:    https://grafana.phoenix-guardian.internal       │
│   Threats: https://grafana.phoenix-guardian.internal/d/thr │
│   API:     https://grafana.phoenix-guardian.internal/d/api │
├────────────────────────────────────────────────────────────┤
│ Clusters                                                   │
│   Prod:    kubectl config use-context phoenix-prod         │
│   DR:      kubectl config use-context phoenix-dr           │
│   Staging: kubectl config use-context phoenix-staging      │
├────────────────────────────────────────────────────────────┤
│ Key Commands                                               │
│   Pod status:  kubectl get pods -A | grep phoenix          │
│   Logs:        kubectl logs -f deploy/<svc> -n phoenix-api │
│   Restart:     kubectl rollout restart deploy/<svc> -n ns  │
│   Scale:       kubectl scale deploy/<svc> --replicas=N     │
├────────────────────────────────────────────────────────────┤
│ Emergency Contacts                                         │
│   Security:    +1-555-SEC-TEAM (24/7)                      │
│   Database:    +1-555-DBA-TEAM (24/7)                      │
│   Management:  @phoenix-leadership (Slack)                 │
└────────────────────────────────────────────────────────────┘
```

---

## 2. Incident Response

### 2.1 Incident Severity Levels

| Level | Name | Description | Response Time | Examples |
|-------|------|-------------|---------------|----------|
| P1 | Critical | Complete service outage, data breach, critical security | 5 min | All API down, PHI exposure |
| P2 | High | Major feature unavailable, significant degradation | 15 min | Transcription down, 50%+ errors |
| P3 | Medium | Minor feature issue, performance degradation | 1 hour | Single hospital affected, slow queries |
| P4 | Low | Minor issue, no user impact | 4 hours | Non-critical alert, cosmetic bug |

### 2.2 Incident Response Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    INCIDENT RESPONSE FLOW                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. ALERT RECEIVED                                              │
│     │                                                           │
│     ▼                                                           │
│  2. ACKNOWLEDGE (within response SLA)                           │
│     │                                                           │
│     ├─→ Join #phoenix-incidents Slack                           │
│     │                                                           │
│     ▼                                                           │
│  3. ASSESS SEVERITY                                             │
│     │                                                           │
│     ├─→ P1/P2: Start incident bridge, notify management        │
│     │                                                           │
│     ▼                                                           │
│  4. INVESTIGATE (use runbook for alert type)                    │
│     │                                                           │
│     ├─→ Check dashboards                                        │
│     ├─→ Check logs                                              │
│     ├─→ Check recent changes                                    │
│     │                                                           │
│     ▼                                                           │
│  5. MITIGATE (restore service first)                            │
│     │                                                           │
│     ├─→ Rollback if needed                                      │
│     ├─→ Scale resources                                         │
│     ├─→ Failover if needed                                      │
│     │                                                           │
│     ▼                                                           │
│  6. RESOLVE (confirm service restored)                          │
│     │                                                           │
│     ├─→ Verify metrics normal                                   │
│     ├─→ Resolve PagerDuty incident                              │
│     │                                                           │
│     ▼                                                           │
│  7. POST-INCIDENT (within 24-48 hours)                          │
│     │                                                           │
│     └─→ Write incident report                                   │
│     └─→ Schedule post-mortem (P1/P2)                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Starting an Incident Bridge

For P1/P2 incidents:

```bash
# 1. Create incident channel
/slack create-channel phoenix-inc-$(date +%Y%m%d-%H%M)

# 2. Start Zoom bridge
# Use dedicated incident bridge: https://zoom.us/j/phoenix-incident

# 3. Post incident template
/slack post-template incident-start

# 4. Notify stakeholders
@phoenix-oncall @phoenix-leadership
INCIDENT: [P1/P2] Brief description
Bridge: https://zoom.us/j/phoenix-incident
Channel: #phoenix-inc-YYYYMMDD-HHMM
```

---

## 3. Alert Playbooks

### 3.1 High Error Rate (HighErrorRate)

**Trigger:** API error rate > 1% for 5 minutes

**Investigation Steps:**

```bash
# 1. Check which endpoints are failing
kubectl exec -n phoenix-api deploy/api-gateway -- \
  curl -s localhost:9090/metrics | grep 'http_requests_total{status="5'

# 2. Check recent deployments
kubectl rollout history deploy/api-gateway -n phoenix-api

# 3. Check pod health
kubectl get pods -n phoenix-api -o wide
kubectl describe pods -l app=api-gateway -n phoenix-api

# 4. Check application logs
kubectl logs -l app=api-gateway -n phoenix-api --tail=100 | grep -i error

# 5. Check database connectivity
kubectl exec -n phoenix-api deploy/api-gateway -- \
  python -c "from app.db import engine; engine.execute('SELECT 1')"

# 6. Check external dependencies
kubectl exec -n phoenix-api deploy/api-gateway -- \
  curl -s -o /dev/null -w "%{http_code}" https://whisper-api.openai.com/health
```

**Mitigation:**

```bash
# Option 1: Rollback recent deployment
kubectl rollout undo deploy/api-gateway -n phoenix-api

# Option 2: Restart pods
kubectl rollout restart deploy/api-gateway -n phoenix-api

# Option 3: Scale up replicas
kubectl scale deploy/api-gateway --replicas=6 -n phoenix-api

# Option 4: Enable circuit breaker
kubectl set env deploy/api-gateway CIRCUIT_BREAKER_ENABLED=true -n phoenix-api
```

### 3.2 Threat Detection High (ThreatDetectionHigh)

**Trigger:** Critical threat rate > 0.1/s for 1 minute

**Investigation Steps:**

```bash
# 1. Check threat dashboard
open https://grafana.phoenix-guardian.internal/d/threats

# 2. Get recent threats
kubectl exec -n phoenix-api deploy/api-gateway -- \
  curl -s localhost:8080/api/v1/threats/recent?limit=20 | jq .

# 3. Check threat detector logs
kubectl logs -l app=threat-detector -n phoenix-security --tail=200

# 4. Check if single source
kubectl exec -n phoenix-data redis-sentinel-0 -- \
  redis-cli -a $REDIS_PASSWORD HGETALL threat:sources:$(date +%Y%m%d)

# 5. Check for known attack patterns
kubectl exec -n phoenix-security deploy/threat-detector -- \
  python -c "from app.patterns import get_active_attacks; print(get_active_attacks())"
```

**Immediate Actions:**

```bash
# 1. If confirmed attack, enable enhanced protection
kubectl set env deploy/api-gateway ENHANCED_THREAT_MODE=true -n phoenix-api

# 2. Block suspicious IPs (if identified)
kubectl exec -n phoenix-security deploy/honeypot-controller -- \
  /app/scripts/block_ip.sh <IP_ADDRESS>

# 3. Notify security team
/pagerduty page phoenix-security "Critical threat activity detected"

# 4. Enable additional logging
kubectl set env deploy/threat-detector LOG_LEVEL=debug -n phoenix-security
```

**DO NOT:**
- Disable threat detection
- Ignore if it auto-resolves (still investigate)
- Share threat details externally without security approval

### 3.3 Transcription Latency High (TranscriptionLatencyHigh)

**Trigger:** P95 transcription latency > 30 seconds for 5 minutes

**Investigation Steps:**

```bash
# 1. Check transcription queue depth
kubectl exec -n phoenix-ai deploy/transcription-service -- \
  curl -s localhost:9090/metrics | grep transcription_queue

# 2. Check GPU utilization
kubectl exec -n phoenix-ai deploy/transcription-service -- nvidia-smi

# 3. Check if model loaded correctly
kubectl logs -l app=transcription-service -n phoenix-ai | grep -i "model\|loaded"

# 4. Check audio processing times
kubectl exec -n phoenix-ai deploy/transcription-service -- \
  curl -s localhost:9090/metrics | grep audio_processing_seconds

# 5. Check for memory issues
kubectl top pods -n phoenix-ai
```

**Mitigation:**

```bash
# Option 1: Scale up GPU pods
kubectl scale deploy/transcription-service --replicas=8 -n phoenix-ai

# Option 2: Use smaller model temporarily
kubectl set env deploy/transcription-service WHISPER_MODEL=medium -n phoenix-ai

# Option 3: Restart pods (clears any stuck jobs)
kubectl rollout restart deploy/transcription-service -n phoenix-ai

# Option 4: Enable queue throttling
kubectl set env deploy/transcription-service QUEUE_THROTTLE_ENABLED=true -n phoenix-ai
```

### 3.4 Database Connection Pool Exhausted

**Trigger:** Connection usage > 90% for 5 minutes

**Investigation Steps:**

```bash
# 1. Check current connections
kubectl exec -n phoenix-data phoenix-db-1 -- \
  psql -U postgres -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# 2. Check for long-running queries
kubectl exec -n phoenix-data phoenix-db-1 -- \
  psql -U postgres -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query 
  FROM pg_stat_activity WHERE state = 'active' ORDER BY duration DESC LIMIT 10;"

# 3. Check for blocked queries
kubectl exec -n phoenix-data phoenix-db-1 -- \
  psql -U postgres -c "SELECT * FROM pg_blocking_pids(pg_backend_pid());"

# 4. Check which services are using connections
kubectl exec -n phoenix-data phoenix-db-1 -- \
  psql -U postgres -c "SELECT application_name, count(*) 
  FROM pg_stat_activity GROUP BY application_name ORDER BY count DESC;"
```

**Mitigation:**

```bash
# Option 1: Terminate idle connections
kubectl exec -n phoenix-data phoenix-db-1 -- \
  psql -U postgres -c "SELECT pg_terminate_backend(pid) 
  FROM pg_stat_activity WHERE state = 'idle' AND query_start < now() - interval '10 minutes';"

# Option 2: Kill long-running queries
kubectl exec -n phoenix-data phoenix-db-1 -- \
  psql -U postgres -c "SELECT pg_terminate_backend(pid) 
  FROM pg_stat_activity WHERE duration > interval '5 minutes';"

# Option 3: Increase max connections (temporary)
kubectl exec -n phoenix-data phoenix-db-1 -- \
  psql -U postgres -c "ALTER SYSTEM SET max_connections = 600;"

# Option 4: Restart application pods (resets connection pools)
kubectl rollout restart deploy/api-gateway -n phoenix-api
```

### 3.5 Pod CrashLoopBackOff

**Trigger:** Pod restart count > 3 in 10 minutes

**Investigation Steps:**

```bash
# 1. Get pod status
kubectl get pods -n <namespace> | grep <pod-name>

# 2. Check pod events
kubectl describe pod <pod-name> -n <namespace>

# 3. Check previous container logs
kubectl logs <pod-name> -n <namespace> --previous

# 4. Check resource constraints
kubectl top pod <pod-name> -n <namespace>

# 5. Check liveness probe
kubectl get pod <pod-name> -n <namespace> -o yaml | grep -A5 livenessProbe
```

**Common Causes & Fixes:**

```bash
# Cause: OOMKilled
# Fix: Increase memory limits
kubectl patch deploy <deployment> -n <namespace> \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"<container>","resources":{"limits":{"memory":"4Gi"}}}]}}}}'

# Cause: Missing secret/configmap
# Fix: Verify secrets exist
kubectl get secret <secret-name> -n <namespace>
kubectl create secret generic <secret-name> --from-literal=key=value -n <namespace>

# Cause: Liveness probe failing
# Fix: Increase probe timeout
kubectl patch deploy <deployment> -n <namespace> \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"<container>","livenessProbe":{"initialDelaySeconds":60}}]}}}}'

# Cause: Database connection failure
# Fix: Verify database is accessible
kubectl run db-test --image=postgres:15 --rm -it --restart=Never -- \
  psql -h phoenix-db-rw -U app -d phoenix -c "SELECT 1"
```

---

## 4. Service-Specific Runbooks

### 4.1 API Gateway

**Health Check:**
```bash
# Check health endpoints
curl https://api.phoenix-guardian.health/health/live
curl https://api.phoenix-guardian.health/health/ready

# Check metrics
kubectl port-forward -n phoenix-api deploy/api-gateway 9090:9090
curl localhost:9090/metrics | grep http_requests
```

**Common Issues:**

| Issue | Symptom | Resolution |
|-------|---------|------------|
| High latency | P95 > 500ms | Scale replicas, check downstream services |
| Auth failures | 401/403 spikes | Check Vault connection, verify JWT keys |
| Rate limiting | 429 responses | Check rate limit config, identify abusive clients |
| Timeout errors | 504 responses | Check database, check transcription service |

**Restart Procedure:**
```bash
# Graceful restart (rolling)
kubectl rollout restart deploy/api-gateway -n phoenix-api

# Force restart all pods
kubectl delete pods -l app=api-gateway -n phoenix-api
```

### 4.2 Transcription Service

**Health Check:**
```bash
# Check GPU availability
kubectl exec -n phoenix-ai deploy/transcription-service -- nvidia-smi

# Check model loaded
kubectl logs -l app=transcription-service -n phoenix-ai | grep "Model loaded"

# Check queue depth
kubectl exec -n phoenix-ai deploy/transcription-service -- \
  curl -s localhost:9090/metrics | grep transcription_queue_depth
```

**GPU Troubleshooting:**
```bash
# If GPU not detected
kubectl describe pod -l app=transcription-service -n phoenix-ai | grep -A5 nvidia

# Check NVIDIA device plugin
kubectl get pods -n kube-system | grep nvidia

# Restart NVIDIA device plugin
kubectl rollout restart daemonset nvidia-device-plugin-daemonset -n kube-system
```

### 4.3 Threat Detector

**Health Check:**
```bash
# Check detector status
kubectl exec -n phoenix-security deploy/threat-detector -- \
  curl -s localhost:8080/health

# Check detection stats
kubectl exec -n phoenix-security deploy/threat-detector -- \
  curl -s localhost:9090/metrics | grep threat_
```

**False Positive Handling:**
```bash
# 1. Review the threat
kubectl exec -n phoenix-security deploy/threat-detector -- \
  /app/scripts/review_threat.py --threat-id <THREAT_ID>

# 2. Mark as false positive (requires security approval)
kubectl exec -n phoenix-security deploy/threat-detector -- \
  /app/scripts/mark_false_positive.py --threat-id <THREAT_ID> --reason "description"

# 3. Update detection rules if pattern is wrong
# Requires PR to threat-patterns repository
```

### 4.4 Federated Learning Service

**Health Check:**
```bash
# Check aggregation status
kubectl exec -n phoenix-fed deploy/federation-aggregator -- \
  curl -s localhost:8080/api/v1/federation/status

# Check privacy engine
kubectl exec -n phoenix-fed deploy/privacy-engine -- \
  curl -s localhost:8080/health
```

**Aggregation Issues:**
```bash
# If aggregation stuck
kubectl logs -l app=federation-aggregator -n phoenix-fed | grep -i error

# Check contributor count
kubectl exec -n phoenix-fed deploy/federation-aggregator -- \
  curl -s localhost:8080/api/v1/signatures/pending | jq '.count'

# Force aggregation cycle (if stuck)
kubectl exec -n phoenix-fed deploy/federation-aggregator -- \
  /app/scripts/force_aggregation.py
```

---

## 5. Database Operations

### 5.1 PostgreSQL Operations

**Check Cluster Status:**
```bash
kubectl cnpg status phoenix-db -n phoenix-data
```

**Failover to Replica:**
```bash
# Automatic failover (let operator handle)
# Just wait for operator to promote replica

# Manual failover (emergency only)
kubectl cnpg promote phoenix-db-2 -n phoenix-data
```

**Backup Operations:**
```bash
# Trigger manual backup
kubectl cnpg backup phoenix-db -n phoenix-data

# Check backup status
kubectl get backup -n phoenix-data

# Restore from backup (creates new cluster)
kubectl cnpg restore phoenix-db-restored \
  --backup phoenix-db-backup-20231101 \
  -n phoenix-data
```

**Query Performance:**
```bash
# Find slow queries
kubectl exec -n phoenix-data phoenix-db-1 -- \
  psql -U postgres -c "
  SELECT pid, now() - query_start AS duration, query
  FROM pg_stat_activity
  WHERE state = 'active' AND query_start < now() - interval '5 seconds'
  ORDER BY duration DESC LIMIT 10;"

# Kill a specific query
kubectl exec -n phoenix-data phoenix-db-1 -- \
  psql -U postgres -c "SELECT pg_terminate_backend(<PID>);"
```

### 5.2 Redis Operations

**Check Sentinel Status:**
```bash
kubectl exec -n phoenix-data redis-sentinel-0 -- \
  redis-cli -p 26379 sentinel master mymaster
```

**Force Failover:**
```bash
kubectl exec -n phoenix-data redis-sentinel-0 -- \
  redis-cli -p 26379 sentinel failover mymaster
```

**Clear Cache (Emergency):**
```bash
# Clear specific key pattern
kubectl exec -n phoenix-data redis-master-0 -- \
  redis-cli -a $REDIS_PASSWORD KEYS "cache:*" | xargs redis-cli DEL

# Clear all (DANGER - use only if necessary)
kubectl exec -n phoenix-data redis-master-0 -- \
  redis-cli -a $REDIS_PASSWORD FLUSHALL
```

---

## 6. Security Incidents

### 6.1 Security Incident Response

**Severity Levels:**

| Level | Description | Response |
|-------|-------------|----------|
| SEV1 | Confirmed data breach | Immediate escalation, legal notification |
| SEV2 | Active attack in progress | Block attacker, preserve evidence |
| SEV3 | Suspicious activity detected | Investigate, increase monitoring |
| SEV4 | Policy violation | Log, review, address in normal cycle |

### 6.2 Confirmed Attack Response

```bash
# 1. Preserve evidence (FIRST - before any changes)
kubectl logs -l app=api-gateway -n phoenix-api > /evidence/api-logs-$(date +%s).log
kubectl logs -l app=threat-detector -n phoenix-security > /evidence/threat-logs-$(date +%s).log

# 2. Block attacker IP (if identified)
kubectl exec -n phoenix-security deploy/waf-controller -- \
  /app/scripts/emergency_block.sh <IP_ADDRESS>

# 3. Enable enhanced logging
kubectl set env deploy/api-gateway SECURITY_LOG_LEVEL=trace -n phoenix-api

# 4. Notify security team
/pagerduty page phoenix-security "SECURITY INCIDENT: [description]"

# 5. Start incident bridge
# See Section 2.3
```

### 6.3 PHI Exposure Response

**CRITICAL: Follow exactly**

```bash
# 1. Immediately notify security lead
# Call +1-555-SEC-LEAD directly, do not wait for PagerDuty

# 2. Do NOT delete any logs or data

# 3. Document exactly what was exposed
# - What data types?
# - How many records?
# - What time range?
# - Who had access?

# 4. Disable affected accounts/APIs
kubectl set env deploy/api-gateway EMERGENCY_LOCKDOWN=true -n phoenix-api

# 5. Security team will handle:
# - Legal notification requirements (HIPAA: 60 days)
# - Patient notification if required
# - Forensic investigation
# - Regulatory reporting
```

### 6.4 Honeypot Alert Response

```bash
# Honeypot alerts indicate reconnaissance or attack

# 1. Get honeypot alert details
kubectl exec -n phoenix-security deploy/honeypot-controller -- \
  curl -s localhost:8080/api/v1/alerts/recent

# 2. Check source IP reputation
kubectl exec -n phoenix-security deploy/threat-detector -- \
  /app/scripts/check_ip_reputation.py <SOURCE_IP>

# 3. Review attacker actions
kubectl logs -l app=honeypot -n phoenix-security | grep <SOURCE_IP>

# 4. Block if malicious
kubectl exec -n phoenix-security deploy/waf-controller -- \
  /app/scripts/block_ip.sh <SOURCE_IP>

# 5. Add to threat intelligence
kubectl exec -n phoenix-security deploy/threat-detector -- \
  /app/scripts/add_ioc.py --type ip --value <SOURCE_IP>
```

---

## 7. Performance Issues

### 7.1 High CPU Usage

```bash
# 1. Identify high CPU pods
kubectl top pods -A | sort -k3 -rn | head -20

# 2. Get pod details
kubectl describe pod <pod-name> -n <namespace>

# 3. Profile application (if instrumented)
kubectl port-forward <pod-name> 8080:8080 -n <namespace>
curl localhost:8080/debug/pprof/profile?seconds=30 > cpu.prof

# 4. Mitigation options
# Scale horizontally
kubectl scale deploy/<deployment> --replicas=6 -n <namespace>

# Or restart to clear state
kubectl rollout restart deploy/<deployment> -n <namespace>
```

### 7.2 High Memory Usage

```bash
# 1. Check memory usage
kubectl top pods -A | sort -k4 -rn | head -20

# 2. Check for memory leaks
kubectl exec <pod-name> -n <namespace> -- \
  cat /sys/fs/cgroup/memory/memory.stat

# 3. Get heap dump (Java/Node)
kubectl exec <pod-name> -n <namespace> -- \
  jmap -dump:format=b,file=/tmp/heap.hprof <PID>

# 4. Mitigation
# Restart pod
kubectl delete pod <pod-name> -n <namespace>

# Or scale up and restart rolling
kubectl scale deploy/<deployment> --replicas=6 -n <namespace>
kubectl rollout restart deploy/<deployment> -n <namespace>
```

### 7.3 Network Latency

```bash
# 1. Check inter-pod latency
kubectl exec <pod-name> -n <namespace> -- \
  curl -w "@curl-format.txt" -s -o /dev/null http://<target-service>:8080/health

# 2. Check DNS resolution time
kubectl exec <pod-name> -n <namespace> -- \
  time nslookup <service-name>

# 3. Check Istio sidecar metrics
kubectl exec <pod-name> -c istio-proxy -n <namespace> -- \
  curl -s localhost:15020/stats/prometheus | grep request_duration

# 4. Check network policies
kubectl get networkpolicy -n <namespace>
```

---

## 8. Disaster Recovery

### 8.1 Full Region Failover

**Trigger:** Primary region (us-east-1) completely unavailable

```bash
#!/bin/bash
# dr-failover.sh

echo "=== INITIATING DR FAILOVER ==="
echo "Time: $(date)"
echo "Operator: $USER"

# 1. Verify DR health
echo "Checking DR region health..."
kubectl --context phoenix-dr get nodes
if [ $? -ne 0 ]; then
  echo "ERROR: Cannot reach DR cluster"
  exit 1
fi

# 2. Check database replication lag
echo "Checking database replication..."
REPLICATION_LAG=$(kubectl --context phoenix-dr exec -n phoenix-data phoenix-db-dr-1 -- \
  psql -U postgres -t -c "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))::integer;")
echo "Replication lag: ${REPLICATION_LAG}s"

if [ "$REPLICATION_LAG" -gt 300 ]; then
  echo "WARNING: High replication lag. Data loss possible."
  read -p "Continue? (yes/no): " confirm
  if [ "$confirm" != "yes" ]; then
    exit 1
  fi
fi

# 3. Promote DR database
echo "Promoting DR database..."
kubectl --context phoenix-dr exec -n phoenix-data phoenix-db-dr-1 -- \
  pg_ctl promote -D /var/lib/postgresql/data

# 4. Update DNS
echo "Updating DNS records..."
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890 \
  --change-batch file://dr-dns-failover.json

# 5. Scale DR workloads
echo "Scaling DR workloads..."
kubectl --context phoenix-dr scale deployment --all --replicas=3 -n phoenix-api
kubectl --context phoenix-dr scale deployment --all --replicas=3 -n phoenix-ai
kubectl --context phoenix-dr scale deployment --all --replicas=2 -n phoenix-security

# 6. Verify health
echo "Verifying health..."
sleep 30
for i in {1..10}; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://api.phoenix-guardian.health/health)
  echo "Health check $i: $HTTP_CODE"
  if [ "$HTTP_CODE" == "200" ]; then
    echo "=== FAILOVER COMPLETE ==="
    exit 0
  fi
  sleep 10
done

echo "WARNING: Health checks not passing. Manual intervention required."
```

### 8.2 Failback Procedure

After primary region is restored:

```bash
#!/bin/bash
# dr-failback.sh

echo "=== INITIATING FAILBACK TO PRIMARY ==="

# 1. Sync data from DR to primary
echo "Syncing database..."
kubectl --context phoenix-prod exec -n phoenix-data phoenix-db-1 -- \
  pg_basebackup -h phoenix-db-dr-1.us-west-2 -U replicator -D /var/lib/postgresql/data -Fp -Xs -P

# 2. Verify sync complete
echo "Verifying sync..."
# Wait for sync to complete

# 3. Update DNS back to primary
echo "Updating DNS..."
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890 \
  --change-batch file://primary-dns.json

# 4. Scale primary workloads
echo "Scaling primary workloads..."
kubectl --context phoenix-prod scale deployment --all --replicas=3 -n phoenix-api

# 5. Scale down DR
echo "Scaling down DR..."
kubectl --context phoenix-dr scale deployment --all --replicas=1 -n phoenix-api

echo "=== FAILBACK COMPLETE ==="
```

---

## 9. Escalation Procedures

### 9.1 Escalation Matrix

| Time Without Resolution | Action |
|------------------------|--------|
| 15 minutes (P1) | Page secondary on-call |
| 30 minutes (P1) | Page engineering manager |
| 1 hour (P1) | Page VP Engineering |
| 30 minutes (P2) | Page secondary on-call |
| 2 hours (P2) | Page engineering manager |

### 9.2 Escalation Commands

```bash
# Escalate to secondary on-call
/pagerduty escalate phoenix-secondary "Unable to resolve: [description]"

# Escalate to management
/pagerduty page phoenix-management "P1 Incident: [description]"

# Request additional help
/pagerduty page phoenix-experts "Need expertise on: [area]"
```

### 9.3 Customer Communication

For P1/P2 incidents affecting customers:

```markdown
## Status Page Update Template

**Title:** [Service] Degraded/Outage

**Status:** Investigating | Identified | Monitoring | Resolved

**Message:**
We are currently investigating [brief description of issue].

Our team is actively working to restore full functionality.
Affected services: [list services]

Updates will be provided every [15/30/60] minutes.

**Last Update:** [timestamp]
```

---

## 10. Post-Incident

### 10.1 Incident Report Template

```markdown
# Incident Report: INC-YYYYMMDD-XXX

## Summary
- **Date/Time:** YYYY-MM-DD HH:MM UTC
- **Duration:** X hours Y minutes
- **Severity:** P1/P2/P3/P4
- **Services Affected:** 
- **Customers Affected:**
- **On-Call Engineer:**

## Timeline
| Time (UTC) | Event |
|------------|-------|
| HH:MM | Alert triggered |
| HH:MM | Engineer acknowledged |
| HH:MM | Root cause identified |
| HH:MM | Mitigation applied |
| HH:MM | Service restored |
| HH:MM | Incident resolved |

## Root Cause
[Detailed explanation of what caused the incident]

## Impact
- **User Impact:** [Description of user experience]
- **Data Impact:** [Any data loss or corruption]
- **Revenue Impact:** [Estimated if applicable]

## Mitigation
[What was done to restore service]

## Resolution
[What was done to permanently fix the issue]

## Follow-Up Actions
| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| | | | |

## Lessons Learned
- What went well:
- What could be improved:
- What surprised us:
```

### 10.2 Post-Mortem Meeting

For P1/P2 incidents, schedule within 48 hours:

**Agenda:**
1. Timeline review (10 min)
2. Root cause discussion (15 min)
3. Impact assessment (10 min)
4. Prevention discussion (20 min)
5. Action items (10 min)

**Participants:**
- On-call engineer(s)
- Service owner
- Engineering manager
- Security representative (if security-related)

**Output:**
- Updated incident report
- Action items in tracking system
- Runbook updates if needed

---

## Quick Reference: Common Commands

```bash
# Get all Phoenix pods
kubectl get pods -A | grep phoenix

# Check recent deployments
kubectl rollout history deploy/<name> -n <namespace>

# Get pod logs
kubectl logs -f deploy/<name> -n <namespace>

# Restart deployment
kubectl rollout restart deploy/<name> -n <namespace>

# Scale deployment
kubectl scale deploy/<name> --replicas=N -n <namespace>

# Port forward for debugging
kubectl port-forward deploy/<name> 8080:8080 -n <namespace>

# Exec into pod
kubectl exec -it deploy/<name> -n <namespace> -- /bin/sh

# Check events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# Check resource usage
kubectl top pods -n <namespace>

# Database connection
kubectl exec -it phoenix-db-1 -n phoenix-data -- psql -U app -d phoenix

# Redis connection
kubectl exec -it redis-master-0 -n phoenix-data -- redis-cli -a $REDIS_PASSWORD
```

---

*Document maintained by Phoenix Guardian SRE Team*  
*Last review: Week 35-36*  
*Emergency contact: +1-555-PHOENIX*
