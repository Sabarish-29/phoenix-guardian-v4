"""
Access Control Evidence Collector (CC6).

Collects evidence of logical access controls:
- User authentication events
- Authorization decisions
- Access reviews
- Privilege escalation logs
- Failed login attempts

DEMONSTRATES:
- Multi-factor authentication enforced
- Role-based access control (RBAC)
- Least privilege principle
- Regular access reviews
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import uuid

from phoenix_guardian.compliance.evidence_types import (
    Evidence,
    AccessLogEvidence,
    AuthenticationEvidence,
    TSCCriterion,
    EvidenceType,
    EvidenceSource,
)

logger = logging.getLogger(__name__)


class AccessControlCollector:
    """
    Collects CC6 (Logical Access Control) evidence.
    
    Sources:
    - Application authentication logs
    - Database audit logs
    - Kubernetes audit logs
    - OAuth/OIDC provider logs
    """
    
    # Control descriptions for auditor
    CONTROL_DESCRIPTIONS = {
        "authentication": "Multi-factor authentication enforced for all users accessing the system",
        "authorization": "Role-based access control (RBAC) enforces least privilege principle",
        "failed_login": "Failed login attempts are logged and account lockout enforced after 5 failures",
        "privilege_change": "All privilege escalations are logged and require approval",
        "access_review": "Quarterly access reviews ensure appropriate access rights",
    }
    
    async def collect(
        self,
        start_date: str,
        end_date: str,
        tenant_id: Optional[str] = None
    ) -> List[Evidence]:
        """
        Collect all access control evidence for period.
        """
        evidence: List[Evidence] = []
        
        # Authentication events
        auth_evidence = await self._collect_authentication_events(
            start_date, end_date, tenant_id
        )
        evidence.extend(auth_evidence)
        
        # Authorization checks
        authz_evidence = await self._collect_authorization_events(
            start_date, end_date, tenant_id
        )
        evidence.extend(authz_evidence)
        
        # Failed login attempts
        failed_login_evidence = await self._collect_failed_logins(
            start_date, end_date, tenant_id
        )
        evidence.extend(failed_login_evidence)
        
        # Privilege escalation
        privilege_evidence = await self._collect_privilege_changes(
            start_date, end_date, tenant_id
        )
        evidence.extend(privilege_evidence)
        
        # Access reviews
        review_evidence = await self._collect_access_reviews(
            start_date, end_date, tenant_id
        )
        evidence.extend(review_evidence)
        
        logger.info(f"Collected {len(evidence)} access control evidence items")
        return evidence
    
    async def _collect_authentication_events(
        self,
        start_date: str,
        end_date: str,
        tenant_id: Optional[str]
    ) -> List[AuthenticationEvidence]:
        """
        Collect successful authentication events.
        
        SOURCE: Application logs, OAuth provider
        DEMONSTRATES: MFA enforced, secure authentication
        """
        # In production: Query from auth provider API or database
        # For now: Generate realistic mock data
        
        events: List[AuthenticationEvidence] = []
        
        # Mock: Generate sample authentication events
        for i in range(15):
            event = AuthenticationEvidence(
                evidence_id=f"auth_{uuid.uuid4().hex[:12]}",
                evidence_type=EvidenceType.AUTHENTICATION_EVENT,
                evidence_source=EvidenceSource.APPLICATION_LOG,
                tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
                control_description=self.CONTROL_DESCRIPTIONS["authentication"],
                collected_at=datetime.now().isoformat(),
                event_timestamp=start_date,
                data_hash="",
                data={
                    "event_type": "user_login",
                    "auth_method": "oauth2",
                    "mfa_verified": True,
                },
                tenant_id=tenant_id,
                user_id=f"user_{i:03d}",
                auth_method="oauth2",
                mfa_type="totp",
                success=True,
                ip_address=f"10.0.1.{i + 1}",
            )
            event.data_hash = event.compute_hash()
            events.append(event)
        
        return events
    
    async def _collect_authorization_events(
        self,
        start_date: str,
        end_date: str,
        tenant_id: Optional[str]
    ) -> List[AccessLogEvidence]:
        """
        Collect authorization decision events.
        
        DEMONSTRATES: RBAC enforced, least privilege
        """
        events: List[AccessLogEvidence] = []
        
        # Mock: Authorization checks showing RBAC enforcement
        resources = [
            ("/api/patients", "read"),
            ("/api/patients", "write"),
            ("/api/admin/users", "read"),
            ("/api/admin/settings", "write"),
        ]
        
        for i, (resource, action) in enumerate(resources):
            event = AccessLogEvidence(
                evidence_id=f"authz_{uuid.uuid4().hex[:12]}",
                evidence_type=EvidenceType.AUTHORIZATION_CHECK,
                evidence_source=EvidenceSource.APPLICATION_LOG,
                tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
                control_description=self.CONTROL_DESCRIPTIONS["authorization"],
                collected_at=datetime.now().isoformat(),
                event_timestamp=start_date,
                data_hash="",
                data={
                    "authorization_decision": "allowed",
                    "role": "physician" if i < 2 else "admin",
                    "policy_evaluated": f"policy_{i:03d}",
                },
                tenant_id=tenant_id,
                user_id=f"user_{i:03d}",
                resource_accessed=resource,
                action=action,
                result="allowed",
                mfa_used=True,
            )
            event.data_hash = event.compute_hash()
            events.append(event)
        
        return events
    
    async def _collect_failed_logins(
        self,
        start_date: str,
        end_date: str,
        tenant_id: Optional[str]
    ) -> List[AuthenticationEvidence]:
        """
        Collect failed login attempts.
        
        DEMONSTRATES: Account lockout after N failures, attack detection
        """
        events: List[AuthenticationEvidence] = []
        
        # Mock: Failed login attempts
        for i in range(3):
            event = AuthenticationEvidence(
                evidence_id=f"failed_login_{uuid.uuid4().hex[:12]}",
                evidence_type=EvidenceType.AUTHENTICATION_EVENT,
                evidence_source=EvidenceSource.APPLICATION_LOG,
                tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
                control_description=self.CONTROL_DESCRIPTIONS["failed_login"],
                collected_at=datetime.now().isoformat(),
                event_timestamp=start_date,
                data_hash="",
                data={
                    "event_type": "failed_login",
                    "attempt_number": i + 1,
                    "lockout_triggered": i >= 4,
                },
                tenant_id=tenant_id,
                user_id=f"user_{100 + i:03d}",
                auth_method="password",
                success=False,
                failure_reason="invalid_credentials",
                ip_address=f"192.168.1.{i + 100}",
            )
            event.data_hash = event.compute_hash()
            events.append(event)
        
        return events
    
    async def _collect_privilege_changes(
        self,
        start_date: str,
        end_date: str,
        tenant_id: Optional[str]
    ) -> List[AccessLogEvidence]:
        """
        Collect privilege escalation logs.
        
        DEMONSTRATES: Privilege changes are logged and reviewed
        """
        events: List[AccessLogEvidence] = []
        
        # Mock: Role changes
        event = AccessLogEvidence(
            evidence_id=f"priv_change_{uuid.uuid4().hex[:12]}",
            evidence_type=EvidenceType.ACCESS_LOG,
            evidence_source=EvidenceSource.APPLICATION_LOG,
            tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
            control_description=self.CONTROL_DESCRIPTIONS["privilege_change"],
            collected_at=datetime.now().isoformat(),
            event_timestamp=start_date,
            data_hash="",
            data={
                "event_type": "role_assignment",
                "old_role": "viewer",
                "new_role": "physician",
                "approved_by": "admin_001",
                "approval_timestamp": datetime.now().isoformat(),
            },
            tenant_id=tenant_id,
            user_id="user_050",
            resource_accessed="/api/admin/roles",
            action="update",
            result="allowed",
        )
        event.data_hash = event.compute_hash()
        events.append(event)
        
        return events
    
    async def _collect_access_reviews(
        self,
        start_date: str,
        end_date: str,
        tenant_id: Optional[str]
    ) -> List[Evidence]:
        """
        Collect access review evidence.
        
        DEMONSTRATES: Regular access reviews performed
        """
        events: List[Evidence] = []
        
        # Mock: Quarterly access review
        event = Evidence(
            evidence_id=f"access_review_{uuid.uuid4().hex[:12]}",
            evidence_type=EvidenceType.ACCESS_LOG,
            evidence_source=EvidenceSource.MANUAL_UPLOAD,
            tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
            control_description=self.CONTROL_DESCRIPTIONS["access_review"],
            collected_at=datetime.now().isoformat(),
            event_timestamp=start_date,
            data_hash="",
            data={
                "review_type": "quarterly_access_review",
                "reviewer": "security_team",
                "users_reviewed": 150,
                "access_revoked": 5,
                "access_modified": 12,
                "review_completed": True,
            },
            tenant_id=tenant_id,
        )
        event.data_hash = event.compute_hash()
        events.append(event)
        
        return events
    
    async def collect_mfa_enrollment(
        self,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get MFA enrollment statistics.
        
        DEMONSTRATES: MFA coverage across organization
        """
        # Mock: MFA stats
        return {
            "total_users": 150,
            "mfa_enrolled": 148,
            "mfa_percentage": 98.67,
            "mfa_types": {
                "totp": 120,
                "sms": 15,
                "hardware_key": 13,
            },
            "pending_enrollment": 2,
        }
