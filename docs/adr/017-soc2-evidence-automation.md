# ADR-017: SOC 2 Evidence Automation

## Status
Accepted

## Date
Day 148 (Phase 3)

## Context

Phoenix Guardian must maintain SOC 2 Type II compliance, requiring:
1. Continuous evidence collection for 5 trust service criteria
2. Quarterly audit readiness
3. Chain of custody for all evidence
4. Minimal manual effort for evidence generation

## Decision

We will implement automated evidence generation with scheduled collection and tamper-evident storage.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 SOC 2 Evidence Automation                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                 Evidence Collectors                          │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │ │
│  │  │   Access    │ │   Change    │ │   Incident  │            │ │
│  │  │   Control   │ │ Management  │ │  Response   │            │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘            │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │ │
│  │  │   Risk     │ │  Monitoring │ │   Vendor    │            │ │
│  │  │ Assessment │ │   Alerts    │ │ Management  │            │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘            │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │               Evidence Processing                            │ │
│  │  - Hash generation (SHA-256)                                │ │
│  │  - Metadata extraction                                      │ │
│  │  - Chain of custody tracking                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │               Evidence Storage (S3 + Glacier)                │ │
│  │  - Immutable storage                                        │ │
│  │  - 7-year retention                                         │ │
│  │  - Geographic redundancy                                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Evidence Collection

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any
import hashlib

@dataclass
class Evidence:
    id: str
    control_id: str  # SOC 2 control reference
    title: str
    description: str
    collected_at: datetime
    source: str
    data: Dict[str, Any]
    hash: str
    chain_of_custody: list

class SOC2EvidenceCollector:
    CONTROL_MAPPING = {
        "CC6.1": "access_control",
        "CC6.2": "access_provisioning",
        "CC6.3": "access_removal",
        "CC7.1": "change_detection",
        "CC7.2": "incident_response",
        "CC8.1": "change_management",
    }
    
    async def collect_access_control_evidence(self) -> Evidence:
        """Collect access control evidence for CC6.1."""
        
        # Query IAM policies
        iam_policies = await self._get_iam_policies()
        
        # Query RBAC configuration
        rbac_config = await self._get_rbac_config()
        
        # Query recent access reviews
        access_reviews = await self._get_access_reviews(days=90)
        
        data = {
            "iam_policies": iam_policies,
            "rbac_configuration": rbac_config,
            "access_reviews": access_reviews,
            "mfa_status": await self._get_mfa_status(),
        }
        
        return Evidence(
            id=str(uuid.uuid4()),
            control_id="CC6.1",
            title="Access Control Evidence",
            description="Evidence of logical access controls",
            collected_at=datetime.utcnow(),
            source="automated_collector",
            data=data,
            hash=self._compute_hash(data),
            chain_of_custody=[{
                "action": "collected",
                "timestamp": datetime.utcnow().isoformat(),
                "actor": "system",
            }]
        )
    
    def _compute_hash(self, data: dict) -> str:
        """Compute SHA-256 hash of evidence data."""
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
```

### Scheduled Collection

```yaml
# Kubernetes CronJob for evidence collection
apiVersion: batch/v1
kind: CronJob
metadata:
  name: soc2-evidence-collector
spec:
  schedule: "0 0 * * *"  # Daily at midnight
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: collector
              image: phoenix-guardian/soc2-collector:latest
              command:
                - python
                - -m
                - soc2_collector
                - --controls=all
              env:
                - name: EVIDENCE_BUCKET
                  value: "phoenix-guardian-soc2-evidence"
          restartPolicy: OnFailure
```

## Consequences

### Positive
- Continuous compliance monitoring
- Audit-ready at any time
- Tamper-evident evidence chain
- Reduced manual effort (95% automated)

### Negative
- Storage costs for evidence retention
- Complex evidence taxonomy
- Integration with multiple systems needed

## References
- SOC 2 Trust Services Criteria: AICPA
- HIPAA Security Rule: 45 CFR Part 164
