"""
Evidence Type Definitions for SOC 2.

Defines schemas for all evidence types collected.
Each evidence item includes:
- What control it demonstrates
- When it was collected
- Cryptographic hash (integrity proof)
- Source system
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import hashlib
import json


class TSCCriterion(Enum):
    """
    Trust Service Criteria from SOC 2 framework.
    """
    CC1_CONTROL_ENVIRONMENT = "CC1"
    CC2_COMMUNICATION = "CC2"
    CC3_RISK_ASSESSMENT = "CC3"
    CC4_MONITORING = "CC4"
    CC5_CONTROL_ACTIVITIES = "CC5"
    CC6_LOGICAL_ACCESS = "CC6"
    CC7_SYSTEM_OPERATIONS = "CC7"
    CC8_CHANGE_MANAGEMENT = "CC8"
    CC9_RISK_MITIGATION = "CC9"
    
    @property
    def description(self) -> str:
        """Human-readable description of TSC."""
        descriptions = {
            self.CC1_CONTROL_ENVIRONMENT: "Control Environment",
            self.CC2_COMMUNICATION: "Communication & Information",
            self.CC3_RISK_ASSESSMENT: "Risk Assessment",
            self.CC4_MONITORING: "Monitoring Activities",
            self.CC5_CONTROL_ACTIVITIES: "Control Activities",
            self.CC6_LOGICAL_ACCESS: "Logical & Physical Access Controls",
            self.CC7_SYSTEM_OPERATIONS: "System Operations",
            self.CC8_CHANGE_MANAGEMENT: "Change Management",
            self.CC9_RISK_MITIGATION: "Risk Mitigation",
        }
        return descriptions.get(self, self.value)
    
    @property
    def is_automatable(self) -> bool:
        """Whether this TSC can be automated."""
        automatable = {
            self.CC3_RISK_ASSESSMENT,
            self.CC4_MONITORING,
            self.CC6_LOGICAL_ACCESS,
            self.CC7_SYSTEM_OPERATIONS,
            self.CC8_CHANGE_MANAGEMENT,
        }
        return self in automatable


class EvidenceType(Enum):
    """Types of evidence we collect."""
    ACCESS_LOG = "access_log"
    AUTHENTICATION_EVENT = "authentication_event"
    AUTHORIZATION_CHECK = "authorization_check"
    DEPLOYMENT_RECORD = "deployment_record"
    CHANGE_APPROVAL = "change_approval"
    CODE_REVIEW = "code_review"
    SYSTEM_AVAILABILITY = "system_availability"
    PERFORMANCE_METRIC = "performance_metric"
    INCIDENT_REPORT = "incident_report"
    INCIDENT_RESOLUTION = "incident_resolution"
    VULNERABILITY_SCAN = "vulnerability_scan"
    PENETRATION_TEST = "penetration_test"
    BACKUP_VERIFICATION = "backup_verification"
    CAPACITY_METRIC = "capacity_metric"
    
    @property
    def tsc_criteria(self) -> List['TSCCriterion']:
        """Get TSC criteria this evidence type supports."""
        mapping = {
            self.ACCESS_LOG: [TSCCriterion.CC6_LOGICAL_ACCESS],
            self.AUTHENTICATION_EVENT: [TSCCriterion.CC6_LOGICAL_ACCESS],
            self.AUTHORIZATION_CHECK: [TSCCriterion.CC6_LOGICAL_ACCESS],
            self.DEPLOYMENT_RECORD: [TSCCriterion.CC8_CHANGE_MANAGEMENT],
            self.CHANGE_APPROVAL: [TSCCriterion.CC8_CHANGE_MANAGEMENT],
            self.CODE_REVIEW: [TSCCriterion.CC8_CHANGE_MANAGEMENT],
            self.SYSTEM_AVAILABILITY: [TSCCriterion.CC7_SYSTEM_OPERATIONS, TSCCriterion.CC4_MONITORING],
            self.PERFORMANCE_METRIC: [TSCCriterion.CC4_MONITORING],
            self.INCIDENT_REPORT: [TSCCriterion.CC7_SYSTEM_OPERATIONS],
            self.INCIDENT_RESOLUTION: [TSCCriterion.CC7_SYSTEM_OPERATIONS],
            self.VULNERABILITY_SCAN: [TSCCriterion.CC3_RISK_ASSESSMENT],
            self.PENETRATION_TEST: [TSCCriterion.CC3_RISK_ASSESSMENT],
            self.BACKUP_VERIFICATION: [TSCCriterion.CC7_SYSTEM_OPERATIONS],
            self.CAPACITY_METRIC: [TSCCriterion.CC7_SYSTEM_OPERATIONS],
        }
        return mapping.get(self, [])


class EvidenceSource(Enum):
    """Where evidence came from."""
    APPLICATION_LOG = "application_log"
    DATABASE_AUDIT_LOG = "database_audit_log"
    KUBERNETES_AUDIT_LOG = "k8s_audit_log"
    GITHUB_ACTIONS = "github_actions"
    PROMETHEUS = "prometheus"
    SECURITY_SCANNER = "security_scanner"
    INCIDENT_MANAGER = "incident_manager"
    MANUAL_UPLOAD = "manual_upload"
    BACKUP_SYSTEM = "backup_system"
    CLOUD_PROVIDER = "cloud_provider"


@dataclass
class Evidence:
    """
    Base class for all evidence items.
    
    Every piece of evidence includes cryptographic hash
    for tamper detection.
    """
    evidence_id: str
    evidence_type: EvidenceType
    evidence_source: EvidenceSource
    
    # SOC 2 mapping
    tsc_criteria: List[TSCCriterion]
    control_description: str
    
    # Temporal
    collected_at: str
    event_timestamp: str
    
    # Integrity
    data_hash: str
    
    # Content
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    tenant_id: Optional[str] = None
    auditor_notes: Optional[str] = None
    
    def compute_hash(self) -> str:
        """
        Compute SHA-256 hash of evidence data.
        
        This proves evidence hasn't been tampered with.
        """
        # Serialize data deterministically
        data_str = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def verify_integrity(self) -> bool:
        """Verify evidence hasn't been tampered with."""
        return self.compute_hash() == self.data_hash
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type.value,
            "evidence_source": self.evidence_source.value,
            "tsc_criteria": [tsc.value for tsc in self.tsc_criteria],
            "control_description": self.control_description,
            "collected_at": self.collected_at,
            "event_timestamp": self.event_timestamp,
            "data_hash": self.data_hash,
            "data": self.data,
            "tenant_id": self.tenant_id,
            "auditor_notes": self.auditor_notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Evidence':
        """Create Evidence from dictionary."""
        return cls(
            evidence_id=data["evidence_id"],
            evidence_type=EvidenceType(data["evidence_type"]),
            evidence_source=EvidenceSource(data["evidence_source"]),
            tsc_criteria=[TSCCriterion(tsc) for tsc in data["tsc_criteria"]],
            control_description=data["control_description"],
            collected_at=data["collected_at"],
            event_timestamp=data["event_timestamp"],
            data_hash=data["data_hash"],
            data=data.get("data", {}),
            tenant_id=data.get("tenant_id"),
            auditor_notes=data.get("auditor_notes"),
        )


@dataclass
class AccessLogEvidence(Evidence):
    """
    Evidence of access control (CC6).
    
    Demonstrates: User authentication, authorization checks
    """
    user_id: str = ""
    resource_accessed: str = ""
    action: str = ""
    result: str = ""
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    mfa_used: bool = False
    session_id: Optional[str] = None


@dataclass
class AuthenticationEvidence(Evidence):
    """
    Evidence of authentication events (CC6).
    
    Demonstrates: MFA enforced, secure authentication
    """
    user_id: str = ""
    auth_method: str = ""
    mfa_type: Optional[str] = None
    success: bool = True
    failure_reason: Optional[str] = None
    ip_address: Optional[str] = None


@dataclass
class DeploymentEvidence(Evidence):
    """
    Evidence of change management (CC8).
    
    Demonstrates: Code review, testing, approval before production
    """
    deployment_id: str = ""
    git_commit_sha: str = ""
    pull_request_number: Optional[str] = None
    approver_ids: List[str] = field(default_factory=list)
    tests_passed: bool = False
    test_coverage_percent: Optional[float] = None
    environment: str = "production"
    rollback_available: bool = True


@dataclass
class ChangeApprovalEvidence(Evidence):
    """
    Evidence of change approval (CC8).
    
    Demonstrates: Changes require approval before production
    """
    change_id: str = ""
    change_type: str = ""
    requestor_id: str = ""
    approver_ids: List[str] = field(default_factory=list)
    approval_timestamp: Optional[str] = None
    justification: Optional[str] = None


@dataclass
class AvailabilityEvidence(Evidence):
    """
    Evidence of system availability (CC7).
    
    Demonstrates: System uptime, SLA compliance
    """
    service_name: str = ""
    availability_percentage: float = 0.0
    measurement_period_hours: int = 0
    sla_target: float = 99.9
    sla_met: bool = True
    downtime_incidents: List[str] = field(default_factory=list)


@dataclass
class PerformanceEvidence(Evidence):
    """
    Evidence of system performance (CC4).
    
    Demonstrates: System performance monitoring
    """
    service_name: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    metric_unit: str = ""
    threshold: Optional[float] = None
    within_threshold: bool = True
    measurement_period_hours: int = 1


@dataclass
class IncidentEvidence(Evidence):
    """
    Evidence of incident response (CC7).
    
    Demonstrates: Incidents detected, responded to, resolved
    """
    incident_id: str = ""
    incident_type: str = ""
    severity: str = ""
    detected_at: str = ""
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    resolution_time_minutes: Optional[int] = None
    root_cause: Optional[str] = None
    affected_services: List[str] = field(default_factory=list)


@dataclass
class ResolutionEvidence(Evidence):
    """
    Evidence of incident resolution (CC7).
    
    Demonstrates: Incidents properly resolved
    """
    incident_id: str = ""
    resolution_type: str = ""
    resolved_by: str = ""
    resolution_notes: str = ""
    preventive_measures: List[str] = field(default_factory=list)
    post_mortem_completed: bool = False


@dataclass
class VulnerabilityScanEvidence(Evidence):
    """
    Evidence of vulnerability management (CC3).
    
    Demonstrates: Regular vulnerability scanning
    """
    scan_id: str = ""
    scanner_name: str = ""
    scan_target: str = ""
    vulnerabilities_found: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    remediation_required: List[str] = field(default_factory=list)
    scan_duration_seconds: Optional[int] = None


@dataclass
class PenetrationTestEvidence(Evidence):
    """
    Evidence of penetration testing (CC3).
    
    Demonstrates: Regular security testing
    """
    test_id: str = ""
    tester_name: str = ""
    test_scope: str = ""
    findings_count: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0
    test_start_date: str = ""
    test_end_date: str = ""
    remediation_deadline: Optional[str] = None
