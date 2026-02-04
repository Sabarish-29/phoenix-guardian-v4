# Phoenix Guardian - Operational Runbook

**Version**: 1.0.0  
**Date**: February 1, 2026  
**Classification**: Internal - SOC Staff Only  
**Document ID**: PG-RUNBOOK-2026-001

---

## Table of Contents

1. [Overview](#1-overview)
2. [Daily Operations](#2-daily-operations)
3. [Incident Response](#3-incident-response)
4. [Maintenance Procedures](#4-maintenance-procedures)
5. [Emergency Procedures](#5-emergency-procedures)
6. [Escalation Matrix](#6-escalation-matrix)
7. [Reference Information](#7-reference-information)

---

## 1. Overview

### 1.1 Purpose

This runbook provides step-by-step operational procedures for the Security Operations Center (SOC) staff managing Phoenix Guardian. It covers daily operations, incident response, maintenance, and emergency procedures.

### 1.2 Scope

- Production environment only
- All SOC staff (Tier 1, Tier 2, Tier 3)
- 24/7 operations coverage

### 1.3 System Overview

| Component | Hostname | IP Address | Purpose |
|-----------|----------|------------|---------|
| Application Server | phoenix-app-01 | 10.0.1.100 | Main application |
| Database Server | phoenix-db-01 | 10.0.2.10 | PostgreSQL database |
| Cache Server | phoenix-cache-01 | 10.0.2.11 | Redis cache |
| Load Balancer | phoenix-lb-01 | 10.0.1.50 | Traffic distribution |

### 1.4 Contact Information

| Role | Contact | Phone | Availability |
|------|---------|-------|--------------|
| SOC Lead | soc-lead@hospital.org | x5001 | 24/7 |
| Security Manager | security-manager@hospital.org | x5002 | Business hours |
| CISO | ciso@hospital.org | x5003 | Escalation only |
| On-Call DBA | dba-oncall@hospital.org | x5010 | 24/7 |
| Vendor Support | support@phoenix-guardian.com | 1-800-XXX-XXXX | 24/7 |

---

## 2. Daily Operations

### 2.1 Daily Health Check (Start of Shift)

**Frequency**: Every shift change  
**Estimated Time**: 15 minutes  
**Performed By**: SOC Tier 1

#### Procedure

1. **Check Service Status**

   ```bash
   # SSH to application server
   ssh soc@phoenix-app-01
   
   # Check Phoenix Guardian service
   sudo systemctl status phoenix-guardian
   
   # Expected output:
   # ● phoenix-guardian.service - Phoenix Guardian AI Security System
   #    Loaded: loaded (/etc/systemd/system/phoenix-guardian.service; enabled)
   #    Active: active (running) since ...
   ```

2. **Verify Application Health**

   ```bash
   # Health check endpoint
   curl -s https://phoenix-guardian.hospital.internal/health | jq
   
   # Expected output:
   # {
   #   "status": "healthy",
   #   "version": "1.0.0",
   #   "database": "connected",
   #   "cache": "connected",
   #   "ml_models": "loaded",
   #   "timestamp": "2026-02-01T08:00:00Z"
   # }
   ```

3. **Check Database Connectivity**

   ```bash
   # PostgreSQL connection test
   psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian -c "SELECT 1;"
   
   # Check connection count
   psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian -c \
       "SELECT count(*) FROM pg_stat_activity WHERE datname = 'phoenix_guardian';"
   ```

4. **Check Redis Cache**

   ```bash
   # Redis health check
   redis-cli -h phoenix-cache-01 -a $REDIS_PASSWORD ping
   
   # Check memory usage
   redis-cli -h phoenix-cache-01 -a $REDIS_PASSWORD INFO memory | grep used_memory_human
   ```

5. **Review Dashboard Metrics**

   - Open Grafana: https://grafana.hospital.internal/d/phoenix-guardian
   - Verify all panels show green status
   - Check for any alerts in the last 24 hours

6. **Review Overnight Alerts**

   ```bash
   # Check recent alerts
   grep -i "alert\|error\|critical" /var/log/phoenix-guardian/error.log | tail -50
   ```

7. **Document Health Check**

   Log results in the SOC ticketing system with:
   - Date/Time
   - Operator name
   - All services: PASS/FAIL
   - Any anomalies noted

### 2.2 Log Monitoring

**Frequency**: Continuous / Hourly spot checks  
**Performed By**: SOC Tier 1

#### Key Log Files

| Log File | Location | What to Look For |
|----------|----------|------------------|
| Application | /var/log/phoenix-guardian/error.log | Errors, exceptions |
| Access | /var/log/phoenix-guardian/access.log | Unusual patterns |
| Audit | Database: audit_logs table | All actions |
| nginx | /var/log/nginx/phoenix-guardian-*.log | 4xx/5xx errors |

#### Log Search Commands

```bash
# Search for errors in last hour
grep -E "ERROR|CRITICAL" /var/log/phoenix-guardian/error.log | \
    awk -v d="$(date -d '1 hour ago' '+%Y-%m-%d %H')" '$0 ~ d'

# Search for attack detections
grep "attack_detected" /var/log/phoenix-guardian/access.log | tail -20

# Search for honeytoken triggers
grep "honeytoken_triggered" /var/log/phoenix-guardian/access.log | tail -20

# Count requests by status code
awk '{print $9}' /var/log/nginx/phoenix-guardian-access.log | \
    sort | uniq -c | sort -rn
```

### 2.3 Performance Monitoring

**Frequency**: Every 4 hours  
**Performed By**: SOC Tier 1

#### Metrics to Check

| Metric | Normal Range | Warning | Critical |
|--------|--------------|---------|----------|
| p95 Latency | < 2s | 2-3s | > 3s |
| Error Rate | < 0.1% | 0.1-1% | > 1% |
| CPU Usage | < 60% | 60-80% | > 80% |
| Memory Usage | < 70% | 70-85% | > 85% |
| DB Connections | < 100 | 100-150 | > 150 |

#### Quick Performance Check

```bash
# System resources
htop

# Database performance
psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian << EOF
SELECT 
    count(*) as active_connections,
    max(now() - xact_start) as longest_transaction
FROM pg_stat_activity 
WHERE datname = 'phoenix_guardian' AND state = 'active';
EOF

# ML cache hit rate
redis-cli -h phoenix-cache-01 -a $REDIS_PASSWORD INFO stats | grep keyspace
```

### 2.4 Daily Report Generation

**Frequency**: End of day (17:00)  
**Performed By**: SOC Tier 1

```bash
# Generate daily security report
cd /opt/phoenix-guardian
source venv/bin/activate
python -m phoenix_guardian.reports.daily_summary \
    --date $(date +%Y-%m-%d) \
    --output /var/reports/daily-$(date +%Y%m%d).pdf

# Email report to stakeholders
mail -s "Phoenix Guardian Daily Report - $(date +%Y-%m-%d)" \
    security-reports@hospital.org < /var/reports/daily-$(date +%Y%m%d).txt
```

---

## 3. Incident Response

### 3.1 Incident Classification

| Severity | Definition | Response Time | Examples |
|----------|------------|---------------|----------|
| **Critical** | Active breach, data exfiltration | Immediate | Honeytoken triggered, mass data access |
| **High** | Attack attempt detected | 15 minutes | Prompt injection, jailbreak attempt |
| **Medium** | Suspicious activity | 1 hour | Unusual access patterns |
| **Low** | Anomaly detected | 4 hours | Minor policy violations |

### 3.2 Honeytoken Trigger Response (CRITICAL)

**This is the most important procedure - a honeytoken trigger indicates potential data breach.**

#### Initial Response (First 5 Minutes)

1. **Acknowledge Alert**

   ```bash
   # Alert will appear in:
   # - Slack: #security-alerts
   # - Email: soc@hospital.org
   # - Prometheus: phoenix_honeytoken_triggers_total
   ```

2. **Gather Initial Information**

   ```bash
   # Get honeytoken access details
   psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian << EOF
   SELECT 
       hal.id,
       hal.honeytoken_id,
       hal.accessed_at,
       hal.accessor_ip,
       hal.accessor_user_agent,
       hal.access_context,
       h.mrn as honeytoken_mrn,
       h.patient_name as honeytoken_name
   FROM honeytoken_access_logs hal
   JOIN honeytokens h ON hal.honeytoken_id = h.id
   WHERE hal.accessed_at > NOW() - INTERVAL '1 hour'
   ORDER BY hal.accessed_at DESC;
   EOF
   ```

3. **Identify Source**

   ```bash
   # GeoIP lookup on accessor IP
   curl -s "https://api.ipgeolocation.io/ipgeo?apiKey=$GEOIP_KEY&ip=<ACCESSOR_IP>"
   
   # Check if IP is internal or external
   # Internal ranges: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
   ```

4. **Create Incident Ticket**

   - Ticket ID: INC-YYYYMMDD-XXXX
   - Severity: CRITICAL
   - Title: "Honeytoken Access Detected - Possible Data Breach"
   - Assign to: SOC Tier 2 + Security Manager

#### Investigation Phase (5-30 Minutes)

1. **Collect Evidence Package**

   ```bash
   # Generate evidence package
   cd /opt/phoenix-guardian
   source venv/bin/activate
   python -m phoenix_guardian.evidence.generate_package \
       --incident-id INC-YYYYMMDD-XXXX \
       --honeytoken-access-id <ACCESS_LOG_ID> \
       --output /secure/evidence/INC-YYYYMMDD-XXXX/
   
   # Evidence package includes:
   # - Honeytoken access logs
   # - Session data
   # - User context
   # - Network logs
   # - Timeline of events
   # - Digital signatures (for court admissibility)
   ```

2. **Identify Affected Systems**

   ```bash
   # Find all queries from same session
   psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian << EOF
   SELECT *
   FROM audit_logs
   WHERE session_id = '<SESSION_ID>'
   ORDER BY timestamp;
   EOF
   ```

3. **Check for Data Exfiltration**

   ```bash
   # Volume of data accessed
   psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian << EOF
   SELECT 
       COUNT(*) as query_count,
       SUM(result_count) as total_records_accessed
   FROM audit_logs
   WHERE session_id = '<SESSION_ID>'
     AND timestamp > NOW() - INTERVAL '24 hours';
   EOF
   ```

#### Containment Phase (30-60 Minutes)

1. **Block Attacker Access**

   ```bash
   # Add IP to firewall blocklist
   sudo iptables -A INPUT -s <ATTACKER_IP> -j DROP
   
   # Or use fail2ban
   sudo fail2ban-client set phoenix-guardian banip <ATTACKER_IP>
   ```

2. **Revoke Compromised Sessions**

   ```bash
   # Revoke all sessions from suspicious IP
   psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian << EOF
   UPDATE sessions 
   SET is_valid = false, 
       revoked_at = NOW(),
       revocation_reason = 'Security incident - honeytoken access'
   WHERE source_ip = '<ATTACKER_IP>';
   EOF
   
   # Clear from Redis
   redis-cli -h phoenix-cache-01 -a $REDIS_PASSWORD KEYS "session:*" | \
       xargs -I {} redis-cli -h phoenix-cache-01 -a $REDIS_PASSWORD DEL {}
   ```

3. **Notify Stakeholders**

   - Security Manager (immediate)
   - CISO (within 1 hour)
   - Legal Department (if confirmed breach)
   - Privacy Officer (if PHI involved)
   - CEO (if regulatory notification required)

#### Post-Incident (Within 24 Hours)

1. **Complete Investigation Report**

   ```markdown
   # Incident Report: INC-YYYYMMDD-XXXX
   
   ## Summary
   - Detection Time: YYYY-MM-DD HH:MM:SS
   - Containment Time: YYYY-MM-DD HH:MM:SS
   - Resolution Time: YYYY-MM-DD HH:MM:SS
   
   ## Timeline
   - [Time]: Event description
   
   ## Root Cause
   [Description]
   
   ## Impact Assessment
   - Records accessed: N
   - PHI exposed: Yes/No
   - Regulatory notification required: Yes/No
   
   ## Remediation Actions
   1. [Action taken]
   
   ## Lessons Learned
   [Description]
   ```

2. **Evidence Preservation**

   ```bash
   # Secure evidence package
   chmod 400 /secure/evidence/INC-YYYYMMDD-XXXX/*
   
   # Create cryptographic hash
   sha256sum /secure/evidence/INC-YYYYMMDD-XXXX/* > \
       /secure/evidence/INC-YYYYMMDD-XXXX/checksums.sha256
   
   # Archive to long-term storage
   tar -czf /archive/incidents/INC-YYYYMMDD-XXXX.tar.gz \
       /secure/evidence/INC-YYYYMMDD-XXXX/
   ```

3. **Regulatory Notifications (if required)**

   - HIPAA Breach Notification: Within 60 days
   - State notification laws: Varies by state
   - HHS OCR notification: If >500 individuals affected

### 3.3 Attack Detection Response (HIGH)

**For prompt injection, jailbreak, and other attack attempts that did NOT trigger honeytokens.**

#### Procedure

1. **Acknowledge Alert**

   ```bash
   # Get attack details
   psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian << EOF
   SELECT *
   FROM attack_detections
   WHERE detected_at > NOW() - INTERVAL '1 hour'
   ORDER BY confidence_score DESC;
   EOF
   ```

2. **Assess Threat Level**

   - Confidence score > 0.95: Confirmed attack
   - Confidence score 0.8-0.95: Likely attack
   - Confidence score < 0.8: Possible false positive

3. **Review Attack Pattern**

   ```bash
   # View attack payload
   psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian << EOF
   SELECT 
       attack_type,
       payload,
       source_ip,
       session_id,
       detected_at,
       response_action
   FROM attack_detections
   WHERE id = '<DETECTION_ID>';
   EOF
   ```

4. **Document and Monitor**

   - If blocked successfully: Log and monitor for repeat attempts
   - If attack succeeded: Escalate to honeytoken response procedure

### 3.4 System Outage Response

#### Application Not Responding

1. **Quick Diagnosis**

   ```bash
   # Check service status
   sudo systemctl status phoenix-guardian
   
   # Check recent logs
   sudo journalctl -u phoenix-guardian -n 100 --no-pager
   
   # Check system resources
   free -m
   df -h
   ```

2. **Restart Service**

   ```bash
   # Graceful restart
   sudo systemctl restart phoenix-guardian
   
   # Wait 30 seconds and verify
   sleep 30
   curl -s https://phoenix-guardian.hospital.internal/health
   ```

3. **If Restart Fails**

   ```bash
   # Check for port conflicts
   sudo netstat -tlnp | grep 8000
   
   # Check for zombie processes
   ps aux | grep phoenix | grep -v grep
   
   # Force kill if necessary
   sudo pkill -9 -f gunicorn
   
   # Start fresh
   sudo systemctl start phoenix-guardian
   ```

#### Database Connection Issues

1. **Test Connectivity**

   ```bash
   # Network connectivity
   nc -zv phoenix-db-01 5432
   
   # PostgreSQL connectivity
   psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian -c "SELECT 1;"
   ```

2. **Check Database Server**

   ```bash
   # SSH to database server
   ssh soc@phoenix-db-01
   
   # Check PostgreSQL status
   sudo systemctl status postgresql
   
   # Check pg_hba.conf if connection refused
   sudo cat /etc/postgresql/16/main/pg_hba.conf
   ```

3. **Clear Connection Pool**

   ```bash
   # Restart application to reset connections
   sudo systemctl restart phoenix-guardian
   ```

---

## 4. Maintenance Procedures

### 4.1 Monthly Key Rotation

**Frequency**: First Monday of each month  
**Maintenance Window**: 02:00 - 04:00  
**Performed By**: Security Engineer + DBA

#### Pre-Maintenance Checklist

- [ ] Change ticket approved
- [ ] Stakeholders notified
- [ ] Backup completed and verified
- [ ] Rollback plan documented
- [ ] On-call team aware

#### Procedure

1. **Generate New Keys in HSM**

   ```bash
   # Generate new master key
   /opt/safenet/lunaclient/bin/cmu generateKey \
       -keyType=AES \
       -keySize=256 \
       -label="phoenix-master-key-$(date +%Y%m)" \
       -slot=0
   
   # Verify key created
   /opt/safenet/lunaclient/bin/cmu list -slot=0
   ```

2. **Update Application Configuration**

   ```bash
   # Update .env file
   sudo nano /opt/phoenix-guardian/.env
   # Change HSM_MASTER_KEY_LABEL to new key label
   
   # Restart application
   sudo systemctl restart phoenix-guardian
   ```

3. **Re-encrypt Sensitive Data**

   ```bash
   # Run re-encryption job
   cd /opt/phoenix-guardian
   source venv/bin/activate
   python -m phoenix_guardian.security.reencrypt_data \
       --old-key-label="phoenix-master-key-$(date -d 'last month' +%Y%m)" \
       --new-key-label="phoenix-master-key-$(date +%Y%m)"
   ```

4. **Verify and Document**

   ```bash
   # Test encryption/decryption
   curl -s https://phoenix-guardian.hospital.internal/api/v1/test/encryption
   
   # Document in change management
   # - Old key label
   # - New key label
   # - Date/time of rotation
   # - Operator name
   ```

### 4.2 Certificate Renewal

**Frequency**: 30 days before expiry  
**Performed By**: Security Engineer

1. **Check Certificate Expiry**

   ```bash
   openssl x509 -in /etc/ssl/certs/phoenix-guardian.crt -noout -enddate
   ```

2. **Generate New CSR**

   ```bash
   openssl req -new -key /etc/ssl/private/phoenix-guardian.key \
       -out /tmp/phoenix-guardian.csr \
       -subj "/C=US/ST=State/L=City/O=Hospital/CN=phoenix-guardian.hospital.internal"
   ```

3. **Submit to CA and Install**

   ```bash
   # After receiving new certificate
   sudo cp new-certificate.crt /etc/ssl/certs/phoenix-guardian.crt
   sudo nginx -t
   sudo systemctl reload nginx
   ```

### 4.3 Database Maintenance

**Frequency**: Weekly (Sunday 03:00)  
**Performed By**: DBA (automated)

```bash
# VACUUM and ANALYZE
psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian << EOF
VACUUM ANALYZE patients;
VACUUM ANALYZE honeytokens;
VACUUM ANALYZE audit_logs;
VACUUM ANALYZE attack_detections;
REINDEX DATABASE phoenix_guardian;
EOF

# Check table bloat
psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian << EOF
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(tablename::regclass)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename::regclass) DESC;
EOF
```

### 4.4 Software Updates

**Frequency**: Monthly (second Tuesday)  
**Performed By**: Security Engineer

1. **Review Available Updates**

   ```bash
   cd /opt/phoenix-guardian
   git fetch origin
   git log HEAD..origin/main --oneline
   
   # Check for security advisories
   pip list --outdated
   ```

2. **Apply Updates in Staging First**

   ```bash
   # On staging server
   git pull origin main
   pip install -r requirements.txt --upgrade
   python -m pytest tests/ -v
   ```

3. **Production Deployment**

   ```bash
   # Create backup
   pg_dump -h phoenix-db-01 -U phoenix_user -Fc phoenix_guardian > \
       /backup/pre-update-$(date +%Y%m%d).dump
   
   # Apply update
   cd /opt/phoenix-guardian
   git pull origin main
   source venv/bin/activate
   pip install -r requirements.txt --upgrade
   
   # Run migrations if needed
   python -m phoenix_guardian.db.migrations
   
   # Restart with zero downtime
   sudo systemctl reload phoenix-guardian
   ```

### 4.5 Audit Log Archival

**Frequency**: Quarterly  
**Retention**: 7 years (HIPAA requirement)

```bash
# Archive old audit logs
psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian << EOF
-- Create archive table for quarter
CREATE TABLE audit_logs_archive_$(date +%Y)_Q$(($(date +%m)/4+1)) AS
SELECT * FROM audit_logs
WHERE timestamp < NOW() - INTERVAL '90 days';

-- Verify archive
SELECT COUNT(*) FROM audit_logs_archive_$(date +%Y)_Q$(($(date +%m)/4+1));

-- Delete archived records from main table
DELETE FROM audit_logs
WHERE timestamp < NOW() - INTERVAL '90 days';

-- VACUUM to reclaim space
VACUUM FULL audit_logs;
EOF

# Export to long-term storage
pg_dump -h phoenix-db-01 -U phoenix_user -Fc \
    -t audit_logs_archive_$(date +%Y)_Q$(($(date +%m)/4+1)) \
    phoenix_guardian > /archive/audit_logs_$(date +%Y)_Q$(($(date +%m)/4+1)).dump

# Upload to secure off-site storage
aws s3 cp /archive/audit_logs_$(date +%Y)_Q$(($(date +%m)/4+1)).dump \
    s3://hospital-archive/phoenix-guardian/audit-logs/ \
    --sse aws:kms --sse-kms-key-id $KMS_KEY_ID
```

---

## 5. Emergency Procedures

### 5.1 Complete System Failure

**Definition**: Phoenix Guardian completely unavailable

#### Immediate Actions (First 5 Minutes)

1. **Activate Incident Response**

   - Declare incident: "Phoenix Guardian Complete Outage"
   - Notify: SOC Lead, Security Manager, On-Call DBA

2. **Assess Impact**

   - Is EHR still functioning? (Should be - PG is monitoring only)
   - Are alerts still being generated?
   - Is data still being protected by other controls?

3. **Attempt Recovery**

   ```bash
   # Check all components
   sudo systemctl status phoenix-guardian
   sudo systemctl status postgresql
   sudo systemctl status redis
   sudo systemctl status nginx
   
   # Restart in order
   sudo systemctl restart redis
   sudo systemctl restart postgresql
   sleep 10
   sudo systemctl restart phoenix-guardian
   sudo systemctl restart nginx
   ```

#### If Recovery Fails (Escalation)

1. **Failover to DR Site** (if available)

   ```bash
   # Update DNS to point to DR site
   # This is typically done through DNS management console
   
   # Verify DR site is operational
   curl -s https://phoenix-guardian-dr.hospital.internal/health
   ```

2. **Manual Monitoring Mode**

   - Enable enhanced logging on EHR system
   - Increase SIEM alert sensitivity
   - Assign dedicated analyst to monitor EHR access

### 5.2 Data Breach Confirmed

**Definition**: Confirmed unauthorized access to PHI

#### Immediate Actions

1. **Contain the Breach**

   ```bash
   # Block attacker IP at firewall
   sudo iptables -A INPUT -s <ATTACKER_IP> -j DROP
   
   # Disable compromised user accounts
   psql -h phoenix-db-01 -U phoenix_user -d phoenix_guardian << EOF
   UPDATE users SET is_active = false, disabled_reason = 'Security incident'
   WHERE id IN (SELECT DISTINCT user_id FROM audit_logs WHERE session_id = '<COMPROMISED_SESSION>');
   EOF
   ```

2. **Preserve Evidence**

   ```bash
   # Do NOT restart services - preserve memory state
   # Create memory dump if needed
   sudo gcore $(pgrep -f gunicorn | head -1)
   
   # Copy all logs
   cp -r /var/log/phoenix-guardian /secure/evidence/$(date +%Y%m%d)/
   ```

3. **Notify Leadership**

   - CISO: Immediate
   - Legal: Within 1 hour
   - Privacy Officer: Within 1 hour
   - CEO: Within 2 hours

4. **Engage Forensics Team**

   - Internal security team
   - External forensics firm (if required)
   - Law enforcement (if criminal activity suspected)

#### HIPAA Breach Notification Requirements

| Requirement | Deadline |
|-------------|----------|
| Internal notification | Within 24 hours |
| Individual notification | Within 60 days |
| HHS notification (< 500 individuals) | Annual |
| HHS notification (≥ 500 individuals) | Within 60 days |
| Media notification (≥ 500 in one state) | Within 60 days |

### 5.3 Ransomware Attack

**Definition**: Encryption of systems by malicious actors

#### Immediate Actions (CRITICAL - DO NOT PAY RANSOM)

1. **Isolate Affected Systems**

   ```bash
   # Disconnect from network
   sudo ip link set eth0 down
   
   # Or at switch level - contact Network Operations
   ```

2. **Do NOT Restart Systems**

   - Preserve forensic evidence
   - Encryption keys may be in memory

3. **Activate DR Site**

   - Restore from clean backup
   - Verify backup integrity before restoration

4. **Contact Authorities**

   - FBI Cyber Division: ic3.gov
   - HHS: OCR breach reporting
   - Cyber insurance provider

### 5.4 Rollback Procedure

**For failed deployments or corrupt updates**

```bash
# Stop service
sudo systemctl stop phoenix-guardian

# Rollback code
cd /opt/phoenix-guardian
git checkout HEAD~1  # Or specific commit

# Restore database (if schema changed)
pg_restore -h phoenix-db-01 -U phoenix_user -d phoenix_guardian \
    -c /backup/pre-update-$(date +%Y%m%d).dump

# Restart service
sudo systemctl start phoenix-guardian

# Verify
curl -s https://phoenix-guardian.hospital.internal/health
```

---

## 6. Escalation Matrix

### 6.1 Escalation Tiers

| Tier | Role | Handles | Escalation Time |
|------|------|---------|-----------------|
| Tier 1 | SOC Analyst | Initial triage, known issues | 15 minutes |
| Tier 2 | Senior Analyst | Complex issues, investigations | 1 hour |
| Tier 3 | Security Engineer | System issues, advanced threats | 2 hours |
| Management | Security Manager/CISO | Critical incidents, breaches | Immediate |

### 6.2 Escalation Paths

```
┌─────────────────────────────────────────────────────────────┐
│                    ESCALATION FLOWCHART                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Alert Received                                              │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────┐                                            │
│  │  Tier 1     │ ◄─── Initial triage (15 min)               │
│  │  SOC Analyst│                                            │
│  └──────┬──────┘                                            │
│         │                                                    │
│         │ Not resolved / Complex                            │
│         ▼                                                    │
│  ┌─────────────┐                                            │
│  │  Tier 2     │ ◄─── Investigation (1 hour)                │
│  │  Sr. Analyst│                                            │
│  └──────┬──────┘                                            │
│         │                                                    │
│         │ System issue / Advanced threat                    │
│         ▼                                                    │
│  ┌─────────────┐                                            │
│  │  Tier 3     │ ◄─── Engineering (2 hours)                 │
│  │  Sec. Eng.  │                                            │
│  └──────┬──────┘                                            │
│         │                                                    │
│         │ Critical / Breach confirmed                       │
│         ▼                                                    │
│  ┌─────────────┐                                            │
│  │  Management │ ◄─── Executive response                    │
│  │  CISO/Legal │                                            │
│  └─────────────┘                                            │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 After-Hours Contacts

| Priority | Contact Method | Response Time |
|----------|----------------|---------------|
| Critical | PagerDuty | 5 minutes |
| High | Phone + SMS | 15 minutes |
| Medium | Email | Next business day |
| Low | Ticket | 48 hours |

---

## 7. Reference Information

### 7.1 Quick Commands Reference

#### Service Management

```bash
# Start/Stop/Restart
sudo systemctl start phoenix-guardian
sudo systemctl stop phoenix-guardian
sudo systemctl restart phoenix-guardian
sudo systemctl reload phoenix-guardian  # Zero-downtime

# Status
sudo systemctl status phoenix-guardian
sudo journalctl -u phoenix-guardian -f  # Live logs
```

#### Log Analysis

```bash
# Recent errors
tail -100 /var/log/phoenix-guardian/error.log | grep ERROR

# Attack detections
grep "attack_detected" /var/log/phoenix-guardian/access.log | tail -20

# Slow queries
grep "slow_query" /var/log/phoenix-guardian/performance.log

# Access by IP
grep "10.0.1." /var/log/phoenix-guardian/access.log | wc -l
```

#### Database Queries

```bash
# Active connections
psql -c "SELECT count(*) FROM pg_stat_activity;"

# Slow queries
psql -c "SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# Table sizes
psql -c "SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename::regclass)) FROM pg_tables WHERE schemaname='public';"
```

### 7.2 Important File Locations

| File/Directory | Purpose |
|----------------|---------|
| /opt/phoenix-guardian | Application code |
| /opt/phoenix-guardian/.env | Configuration |
| /var/log/phoenix-guardian/ | Application logs |
| /var/lib/phoenix-guardian/ | Data files, ML models |
| /etc/nginx/sites-available/phoenix-guardian | nginx config |
| /etc/systemd/system/phoenix-guardian.service | systemd unit |
| /secure/evidence/ | Incident evidence |
| /backup/ | Backup files |

### 7.3 Useful Links

| Resource | URL |
|----------|-----|
| Grafana Dashboard | https://grafana.hospital.internal/d/phoenix-guardian |
| Prometheus | https://prometheus.hospital.internal |
| SIEM Console | https://siem.hospital.internal |
| Ticketing System | https://tickets.hospital.internal |
| Documentation | https://docs.hospital.internal/phoenix-guardian |

### 7.4 Glossary

| Term | Definition |
|------|------------|
| Honeytoken | Synthetic patient record used to detect data theft |
| Beacon | Tracking mechanism embedded in honeytokens |
| SentinelQ | ML-based attack detection agent |
| PQC | Post-Quantum Cryptography |
| PHI | Protected Health Information |
| HIPAA | Health Insurance Portability and Accountability Act |

---

## Document Control

| Property | Value |
|----------|-------|
| Document Owner | Security Operations Center |
| Review Frequency | Monthly |
| Next Review | 2026-03-01 |
| Classification | Internal - SOC Staff Only |

---

**End of Runbook**
