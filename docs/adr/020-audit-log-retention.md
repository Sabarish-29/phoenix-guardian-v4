# ADR-020: Audit Log Retention Policy

## Status
Accepted

## Date
Day 152 (Phase 3)

## Context

Phoenix Guardian must maintain audit logs for:
1. HIPAA compliance (6 years minimum)
2. SOC 2 evidence (7 years)
3. Security incident investigation
4. User activity tracking
5. System debugging

We need to balance compliance requirements with storage costs and query performance.

## Decision

We will implement a tiered retention policy with hot, warm, and cold storage.

### Retention Tiers

```
┌────────────────────────────────────────────────────────────────┐
│                  Audit Log Retention Architecture               │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    HOT (0-30 days)                       │   │
│  │  Storage: PostgreSQL                                     │   │
│  │  Query: Full-text search, complex queries                │   │
│  │  Latency: <100ms                                         │   │
│  │  Use: Real-time monitoring, recent investigation         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                   Archive (nightly)                             │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   WARM (30-365 days)                     │   │
│  │  Storage: Elasticsearch (compressed)                     │   │
│  │  Query: Full-text, aggregations                          │   │
│  │  Latency: <1s                                            │   │
│  │  Use: Compliance queries, trend analysis                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│               Archive (monthly, compressed)                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   COLD (1-7 years)                       │   │
│  │  Storage: S3 Glacier Deep Archive                        │   │
│  │  Query: On-demand restore (12-48 hours)                  │   │
│  │  Latency: Hours                                          │   │
│  │  Use: Legal discovery, historical compliance             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

### Audit Log Schema

```python
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, Any

class AuditAction(str, Enum):
    # Authentication
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    LOGIN_FAILED = "auth.login_failed"
    PASSWORD_CHANGE = "auth.password_change"
    MFA_ENABLED = "auth.mfa_enabled"
    
    # Patient Data
    PATIENT_VIEW = "patient.view"
    PATIENT_CREATE = "patient.create"
    PATIENT_UPDATE = "patient.update"
    
    # Encounters
    ENCOUNTER_CREATE = "encounter.create"
    ENCOUNTER_VIEW = "encounter.view"
    ENCOUNTER_UPDATE = "encounter.update"
    ENCOUNTER_COMPLETE = "encounter.complete"
    
    # SOAP Notes
    SOAP_GENERATE = "soap.generate"
    SOAP_VIEW = "soap.view"
    SOAP_EDIT = "soap.edit"
    SOAP_SIGN = "soap.sign"
    
    # Security
    THREAT_DETECTED = "security.threat_detected"
    THREAT_RESOLVED = "security.threat_resolved"
    ACCESS_DENIED = "security.access_denied"
    
    # Admin
    USER_CREATE = "admin.user_create"
    USER_DELETE = "admin.user_delete"
    ROLE_CHANGE = "admin.role_change"
    CONFIG_CHANGE = "admin.config_change"

class AuditLog(BaseModel):
    id: str
    timestamp: datetime
    tenant_id: str
    user_id: Optional[str]
    session_id: Optional[str]
    action: AuditAction
    resource_type: str
    resource_id: Optional[str]
    ip_address: str
    user_agent: Optional[str]
    request_id: str
    outcome: str  # success, failure, denied
    details: Dict[str, Any]
    
    # PHI indicator for special handling
    contains_phi: bool = False
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

### Retention Implementation

```python
from datetime import datetime, timedelta
import boto3
from elasticsearch import AsyncElasticsearch

class AuditLogArchiver:
    def __init__(self):
        self.db = get_database()
        self.es = AsyncElasticsearch(ES_HOSTS)
        self.s3 = boto3.client('s3')
        
    async def archive_to_warm(self):
        """Move logs older than 30 days to Elasticsearch."""
        cutoff = datetime.utcnow() - timedelta(days=30)
        
        # Query old logs from PostgreSQL
        logs = await self.db.fetch_all(
            """
            SELECT * FROM audit_logs 
            WHERE timestamp < :cutoff 
            ORDER BY timestamp
            LIMIT 10000
            """,
            {"cutoff": cutoff}
        )
        
        if not logs:
            return
        
        # Index to Elasticsearch
        actions = [
            {
                "_index": f"audit-logs-{log['timestamp'].strftime('%Y-%m')}",
                "_id": log['id'],
                "_source": dict(log)
            }
            for log in logs
        ]
        await self.es.bulk(actions)
        
        # Delete from PostgreSQL
        ids = [log['id'] for log in logs]
        await self.db.execute(
            "DELETE FROM audit_logs WHERE id = ANY(:ids)",
            {"ids": ids}
        )
    
    async def archive_to_cold(self):
        """Move logs older than 1 year to S3 Glacier."""
        cutoff = datetime.utcnow() - timedelta(days=365)
        
        # Query old indices from Elasticsearch
        indices = await self.es.cat.indices(index="audit-logs-*", format="json")
        
        for index in indices:
            index_date = self._parse_index_date(index['index'])
            if index_date < cutoff:
                # Export to S3
                await self._export_index_to_s3(index['index'])
                
                # Delete from Elasticsearch
                await self.es.indices.delete(index=index['index'])
    
    async def _export_index_to_s3(self, index_name: str):
        """Export Elasticsearch index to S3 Glacier."""
        # Stream all documents from index
        async for doc in self._scroll_index(index_name):
            # Write to S3 with Glacier storage class
            self.s3.put_object(
                Bucket='phoenix-guardian-audit-archive',
                Key=f"audit-logs/{index_name}/{doc['_id']}.json",
                Body=json.dumps(doc['_source']),
                StorageClass='DEEP_ARCHIVE'
            )
```

### Retention Schedule

| Log Type | Hot (PostgreSQL) | Warm (ES) | Cold (Glacier) | Delete |
|----------|------------------|-----------|----------------|--------|
| Security events | 30 days | 1 year | 7 years | 7 years |
| PHI access | 30 days | 1 year | 7 years | 7 years |
| Auth events | 30 days | 1 year | 6 years | 6 years |
| System events | 7 days | 90 days | 1 year | 1 year |

## Consequences

### Positive
- Meets HIPAA 6-year requirement
- Meets SOC 2 7-year requirement
- Optimized storage costs
- Fast queries for recent data

### Negative
- Complex multi-tier architecture
- Glacier retrieval delays for old data
- Migration between tiers needs monitoring

## References
- HIPAA §164.530(j): 6-year retention
- SOC 2 CC1.1: Record retention
- AWS Glacier Pricing: https://aws.amazon.com/s3/glacier/pricing/
