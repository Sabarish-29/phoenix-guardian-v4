"""
HIPAA Compliance Module for Phoenix Guardian.

Provides HIPAA-compliant logging, audit events, and compliance checks
for protected health information (PHI) handling.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import hashlib
import json
import logging


class AuditEventType(Enum):
    """Types of HIPAA audit events."""
    
    # Access events
    PHI_ACCESS = "phi_access"
    PHI_VIEW = "phi_view"
    PHI_DOWNLOAD = "phi_download"
    PHI_PRINT = "phi_print"
    
    # Modification events
    PHI_CREATE = "phi_create"
    PHI_UPDATE = "phi_update"
    PHI_DELETE = "phi_delete"
    
    # Disclosure events
    PHI_DISCLOSURE = "phi_disclosure"
    PHI_TRANSMISSION = "phi_transmission"
    
    # Security events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    SESSION_TIMEOUT = "session_timeout"
    
    # Administrative events
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DISABLE = "user_disable"
    ROLE_CHANGE = "role_change"
    PERMISSION_CHANGE = "permission_change"
    
    # Emergency access
    EMERGENCY_ACCESS = "emergency_access"
    BREAK_GLASS = "break_glass"


class PHISensitivity(Enum):
    """Sensitivity levels for PHI data."""
    
    STANDARD = "standard"
    SENSITIVE = "sensitive"  # Mental health, HIV, substance abuse
    HIGHLY_SENSITIVE = "highly_sensitive"  # Psychotherapy notes


@dataclass
class AuditEvent:
    """HIPAA-compliant audit event."""
    
    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    user_id: str
    tenant_id: str
    patient_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: str = ""
    outcome: str = "success"
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    phi_accessed: bool = False
    phi_sensitivity: PHISensitivity = PHISensitivity.STANDARD
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "patient_id": self._hash_phi(self.patient_id) if self.patient_id else None,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "outcome": self.outcome,
            "source_ip": self.source_ip,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "phi_accessed": self.phi_accessed,
            "phi_sensitivity": self.phi_sensitivity.value,
            "details": self._sanitize_details(self.details),
        }
    
    @staticmethod
    def _hash_phi(value: str) -> str:
        """Hash PHI for audit log storage (one-way)."""
        return hashlib.sha256(f"phoenix_{value}".encode()).hexdigest()[:16]
    
    @staticmethod
    def _sanitize_details(details: Dict[str, Any]) -> Dict[str, Any]:
        """Remove any PHI from details before logging."""
        sanitized = {}
        phi_fields = {"ssn", "mrn", "dob", "address", "phone", "email", "name"}
        
        for key, value in details.items():
            if key.lower() in phi_fields:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = AuditEvent._sanitize_details(value)
            else:
                sanitized[key] = value
        
        return sanitized


class HIPAALogger:
    """HIPAA-compliant logger with audit trail support."""
    
    def __init__(
        self,
        tenant_id: str,
        logger_name: str = "phoenix_guardian.hipaa",
        audit_store: Optional[Any] = None,
    ):
        """Initialize HIPAA logger.
        
        Args:
            tenant_id: Tenant identifier for multi-tenant isolation
            logger_name: Name for the logger
            audit_store: Optional audit store for persistent logging
        """
        self.tenant_id = tenant_id
        self.logger = logging.getLogger(logger_name)
        self.audit_store = audit_store
        self._event_buffer: List[AuditEvent] = []
        self._buffer_limit = 100
    
    def log_access(
        self,
        user_id: str,
        patient_id: str,
        resource_type: str,
        resource_id: str,
        action: str = "view",
        **kwargs: Any,
    ) -> AuditEvent:
        """Log PHI access event.
        
        Args:
            user_id: User accessing PHI
            patient_id: Patient whose data is accessed
            resource_type: Type of resource (e.g., 'encounter', 'lab_result')
            resource_id: Specific resource ID
            action: Action performed
            **kwargs: Additional event details
        
        Returns:
            Created audit event
        """
        event = AuditEvent(
            event_id=self._generate_event_id(),
            event_type=AuditEventType.PHI_ACCESS,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            tenant_id=self.tenant_id,
            patient_id=patient_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            phi_accessed=True,
            details=kwargs,
        )
        
        self._record_event(event)
        return event
    
    def log_disclosure(
        self,
        user_id: str,
        patient_id: str,
        recipient: str,
        purpose: str,
        data_disclosed: List[str],
        **kwargs: Any,
    ) -> AuditEvent:
        """Log PHI disclosure event.
        
        Args:
            user_id: User making disclosure
            patient_id: Patient whose data is disclosed
            recipient: Recipient of disclosed data
            purpose: Purpose of disclosure
            data_disclosed: Types of data disclosed
            **kwargs: Additional details
        
        Returns:
            Created audit event
        """
        event = AuditEvent(
            event_id=self._generate_event_id(),
            event_type=AuditEventType.PHI_DISCLOSURE,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            tenant_id=self.tenant_id,
            patient_id=patient_id,
            action="disclosure",
            phi_accessed=True,
            details={
                "recipient": recipient,
                "purpose": purpose,
                "data_types": data_disclosed,
                **kwargs,
            },
        )
        
        self._record_event(event)
        return event
    
    def log_security_event(
        self,
        user_id: str,
        event_type: AuditEventType,
        outcome: str = "success",
        **kwargs: Any,
    ) -> AuditEvent:
        """Log security-related event.
        
        Args:
            user_id: User involved
            event_type: Type of security event
            outcome: Event outcome
            **kwargs: Additional details
        
        Returns:
            Created audit event
        """
        event = AuditEvent(
            event_id=self._generate_event_id(),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            tenant_id=self.tenant_id,
            outcome=outcome,
            details=kwargs,
        )
        
        self._record_event(event)
        return event
    
    def log_emergency_access(
        self,
        user_id: str,
        patient_id: str,
        reason: str,
        **kwargs: Any,
    ) -> AuditEvent:
        """Log emergency/break-glass access event.
        
        Args:
            user_id: User invoking emergency access
            patient_id: Patient whose data is accessed
            reason: Reason for emergency access
            **kwargs: Additional details
        
        Returns:
            Created audit event
        """
        event = AuditEvent(
            event_id=self._generate_event_id(),
            event_type=AuditEventType.BREAK_GLASS,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            tenant_id=self.tenant_id,
            patient_id=patient_id,
            action="break_glass_access",
            phi_accessed=True,
            phi_sensitivity=PHISensitivity.HIGHLY_SENSITIVE,
            details={
                "reason": reason,
                "requires_review": True,
                **kwargs,
            },
        )
        
        self._record_event(event)
        self.logger.warning(
            f"BREAK GLASS ACCESS: User {user_id} accessed patient {event._hash_phi(patient_id)} - {reason}"
        )
        return event
    
    def _record_event(self, event: AuditEvent) -> None:
        """Record audit event to storage."""
        self._event_buffer.append(event)
        
        self.logger.info(
            f"AUDIT: {event.event_type.value} by {event.user_id} - {event.outcome}"
        )
        
        if len(self._event_buffer) >= self._buffer_limit:
            self.flush()
    
    def flush(self) -> None:
        """Flush buffered events to persistent storage."""
        if self.audit_store and self._event_buffer:
            for event in self._event_buffer:
                try:
                    self.audit_store.store(event.to_dict())
                except Exception as e:
                    self.logger.error(f"Failed to persist audit event: {e}")
        
        self._event_buffer = []
    
    @staticmethod
    def _generate_event_id() -> str:
        """Generate unique event ID."""
        import uuid
        return str(uuid.uuid4())
    
    def get_audit_trail(
        self,
        patient_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[AuditEvent]:
        """Retrieve audit trail (from buffer only - production would query store).
        
        Args:
            patient_id: Filter by patient
            user_id: Filter by user
            start_date: Filter from date
            end_date: Filter to date
        
        Returns:
            List of matching audit events
        """
        events = self._event_buffer.copy()
        
        if patient_id:
            events = [e for e in events if e.patient_id == patient_id]
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        if start_date:
            events = [e for e in events if e.timestamp >= start_date]
        if end_date:
            events = [e for e in events if e.timestamp <= end_date]
        
        return events


class HIPAACompliance:
    """HIPAA compliance checker and enforcer."""
    
    # Minimum password requirements per HIPAA
    MIN_PASSWORD_LENGTH = 12
    PASSWORD_COMPLEXITY_REQUIRED = True
    
    # Session timeout in minutes (HIPAA recommends 15-30)
    SESSION_TIMEOUT_MINUTES = 15
    
    # Required encryption standards
    REQUIRED_ENCRYPTION = "AES-256"
    REQUIRED_TLS_VERSION = "1.2"
    
    # Audit retention period (HIPAA requires 6 years)
    AUDIT_RETENTION_YEARS = 6
    
    def __init__(self, tenant_id: str):
        """Initialize HIPAA compliance checker.
        
        Args:
            tenant_id: Tenant identifier
        """
        self.tenant_id = tenant_id
        self.logger = HIPAALogger(tenant_id)
        self._violations: List[Dict[str, Any]] = []
    
    def check_access_authorization(
        self,
        user_id: str,
        patient_id: str,
        resource_type: str,
        user_roles: List[str],
        relationship: Optional[str] = None,
    ) -> bool:
        """Check if user is authorized to access patient data.
        
        Args:
            user_id: User requesting access
            patient_id: Patient whose data is requested
            resource_type: Type of resource
            user_roles: User's roles
            relationship: User's relationship to patient (e.g., 'treating_provider')
        
        Returns:
            True if authorized
        """
        # Treatment, Payment, Healthcare Operations (TPO)
        authorized_relationships = {
            "treating_provider",
            "consulting_provider", 
            "care_team_member",
            "billing_staff",
            "quality_reviewer",
        }
        
        # Check relationship-based access
        if relationship in authorized_relationships:
            return True
        
        # Check role-based access
        authorized_roles = {"admin", "provider", "nurse", "care_coordinator"}
        if any(role in authorized_roles for role in user_roles):
            return True
        
        # Log unauthorized access attempt
        self._record_violation({
            "type": "unauthorized_access_attempt",
            "user_id": user_id,
            "patient_id": patient_id,
            "resource_type": resource_type,
        })
        
        return False
    
    def validate_minimum_necessary(
        self,
        requested_fields: List[str],
        purpose: str,
        user_role: str,
    ) -> List[str]:
        """Apply minimum necessary rule to data access.
        
        Args:
            requested_fields: Fields requested
            purpose: Purpose of access
            user_role: User's role
        
        Returns:
            List of approved fields
        """
        # Define field access by purpose/role
        purpose_fields = {
            "treatment": {
                "provider": ["*"],  # Full access for treatment
                "nurse": ["vitals", "medications", "allergies", "diagnosis"],
            },
            "billing": {
                "billing_staff": ["demographics", "insurance", "procedures", "diagnosis_codes"],
            },
            "quality_review": {
                "quality_reviewer": ["outcomes", "procedures", "diagnosis", "length_of_stay"],
            },
        }
        
        allowed = purpose_fields.get(purpose, {}).get(user_role, [])
        
        if "*" in allowed:
            return requested_fields
        
        return [f for f in requested_fields if f in allowed]
    
    def check_password_compliance(self, password: str) -> Dict[str, Any]:
        """Check if password meets HIPAA requirements.
        
        Args:
            password: Password to check
        
        Returns:
            Compliance check result
        """
        issues = []
        
        if len(password) < self.MIN_PASSWORD_LENGTH:
            issues.append(f"Password must be at least {self.MIN_PASSWORD_LENGTH} characters")
        
        if self.PASSWORD_COMPLEXITY_REQUIRED:
            if not any(c.isupper() for c in password):
                issues.append("Password must contain uppercase letter")
            if not any(c.islower() for c in password):
                issues.append("Password must contain lowercase letter")
            if not any(c.isdigit() for c in password):
                issues.append("Password must contain digit")
            if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
                issues.append("Password must contain special character")
        
        return {
            "compliant": len(issues) == 0,
            "issues": issues,
        }
    
    def validate_encryption(
        self,
        encryption_type: str,
        key_length: int,
    ) -> bool:
        """Validate encryption meets HIPAA requirements.
        
        Args:
            encryption_type: Type of encryption (e.g., 'AES')
            key_length: Key length in bits
        
        Returns:
            True if compliant
        """
        valid_encryptions = {
            "AES": [128, 192, 256],
            "3DES": [168],
        }
        
        if encryption_type not in valid_encryptions:
            return False
        
        return key_length in valid_encryptions[encryption_type]
    
    def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate HIPAA compliance report.
        
        Returns:
            Compliance report
        """
        return {
            "tenant_id": self.tenant_id,
            "report_date": datetime.utcnow().isoformat(),
            "violations": self._violations,
            "violation_count": len(self._violations),
            "settings": {
                "password_min_length": self.MIN_PASSWORD_LENGTH,
                "session_timeout_minutes": self.SESSION_TIMEOUT_MINUTES,
                "encryption_standard": self.REQUIRED_ENCRYPTION,
                "tls_version": self.REQUIRED_TLS_VERSION,
                "audit_retention_years": self.AUDIT_RETENTION_YEARS,
            },
        }
    
    def _record_violation(self, violation: Dict[str, Any]) -> None:
        """Record compliance violation."""
        violation["timestamp"] = datetime.utcnow().isoformat()
        violation["tenant_id"] = self.tenant_id
        self._violations.append(violation)


# Convenience exports
__all__ = [
    "HIPAACompliance",
    "HIPAALogger", 
    "AuditEvent",
    "AuditEventType",
    "PHISensitivity",
]
