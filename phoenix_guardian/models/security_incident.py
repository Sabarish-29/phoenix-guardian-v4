"""
Security incident tracking model for HIPAA compliance.

Logs security incidents including honeytoken access, failed logins,
and other security-relevant events that require tracking and response.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from .base import BaseModel


class IncidentSeverity(str, Enum):
    """Severity levels for security incidents."""
    
    LOW = "LOW"           # Minor concern, monitor
    MODERATE = "MODERATE" # Elevated concern, review within 24 hours
    HIGH = "HIGH"         # Serious incident, review within 4 hours
    CRITICAL = "CRITICAL" # Emergency, immediate action required


class IncidentStatus(str, Enum):
    """Status of incident investigation."""
    
    OPEN = "OPEN"                   # New incident, not yet investigated
    INVESTIGATING = "INVESTIGATING" # Under active investigation
    RESOLVED = "RESOLVED"           # Root cause identified and addressed
    FALSE_POSITIVE = "FALSE_POSITIVE" # Determined to be non-issue
    ESCALATED = "ESCALATED"         # Escalated to external party (legal, law enforcement)


class IncidentType(str, Enum):
    """Types of security incidents."""
    
    # Honeytoken related
    HONEYTOKEN_ACCESS = "HONEYTOKEN_ACCESS"
    HONEYTOKEN_EXPORT = "HONEYTOKEN_EXPORT"
    
    # Authentication related
    FAILED_LOGIN = "FAILED_LOGIN"
    BRUTE_FORCE_ATTEMPT = "BRUTE_FORCE_ATTEMPT"
    ACCOUNT_LOCKOUT = "ACCOUNT_LOCKOUT"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    
    # Data related
    SUSPICIOUS_EXPORT = "SUSPICIOUS_EXPORT"
    EXCESSIVE_ACCESS = "EXCESSIVE_ACCESS"
    AFTER_HOURS_ACCESS = "AFTER_HOURS_ACCESS"
    
    # System related
    THREAT_DETECTED = "THREAT_DETECTED"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"
    PRIVILEGE_ESCALATION = "PRIVILEGE_ESCALATION"


class SecurityIncident(BaseModel):
    """
    Security incident log for HIPAA compliance.
    
    Records security-relevant events that may indicate:
    - Unauthorized access attempts
    - Insider threats (honeytoken access)
    - Brute force attacks
    - Suspicious activity patterns
    
    All incidents must be reviewed and dispositioned per HIPAA requirements.
    
    Attributes:
        incident_type: Type of security incident
        severity: Incident severity level
        status: Investigation status
        user_id: User involved (if known)
        patient_id: Patient record accessed (if applicable)
        ip_address: Source IP address
        details: Additional incident details (JSON)
        resolution_notes: Notes from investigation/resolution
        resolved_by: User who resolved the incident
        resolved_at: When incident was resolved
    """
    
    __tablename__ = "security_incidents"
    
    # Incident classification
    incident_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of security incident"
    )
    
    severity = Column(
        String(20),
        nullable=False,
        index=True,
        default=IncidentSeverity.MODERATE.value,
        comment="Incident severity level"
    )
    
    status = Column(
        String(20),
        nullable=False,
        default=IncidentStatus.OPEN.value,
        index=True,
        comment="Investigation status"
    )
    
    # User context
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
        comment="User involved in incident"
    )
    
    user_email = Column(
        String(255),
        nullable=True,
        comment="User email at time of incident"
    )
    
    # Resource context
    patient_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Patient ID if PHI accessed"
    )
    
    resource_type = Column(
        String(50),
        nullable=True,
        comment="Type of resource accessed"
    )
    
    resource_id = Column(
        String(100),
        nullable=True,
        comment="ID of resource accessed"
    )
    
    # Network context
    ip_address = Column(
        String(45),  # IPv6 max length
        nullable=False,
        index=True,
        comment="Source IP address"
    )
    
    user_agent = Column(
        String(500),
        nullable=True,
        comment="User agent string"
    )
    
    # Incident details
    timestamp = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
        comment="When incident occurred"
    )
    
    details = Column(
        JSON,
        nullable=True,
        comment="Additional incident context"
    )
    
    evidence = Column(
        Text,
        nullable=True,
        comment="Evidence collected"
    )
    
    # Resolution
    resolution_notes = Column(
        Text,
        nullable=True,
        comment="Investigation notes and resolution"
    )
    
    resolved_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        comment="User who resolved incident"
    )
    
    resolved_at = Column(
        DateTime,
        nullable=True,
        comment="When incident was resolved"
    )
    
    # Notification tracking
    notification_sent = Column(
        Boolean,
        default=False,
        comment="Whether alert notification was sent"
    )
    
    # Relationships
    user = relationship(
        "User",
        foreign_keys=[user_id],
        backref="security_incidents_as_subject"
    )
    
    resolver = relationship(
        "User",
        foreign_keys=[resolved_by],
        backref="resolved_incidents"
    )
    
    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<SecurityIncident(id={self.id}, type='{self.incident_type}', "
            f"severity='{self.severity}', status='{self.status}')>"
        )
    
    @classmethod
    def create_honeytoken_incident(
        cls,
        patient_id: str,
        user_id: Optional[int],
        user_email: Optional[str],
        ip_address: str,
        action: str = "access",
        user_agent: Optional[str] = None
    ) -> "SecurityIncident":
        """
        Create a honeytoken access incident.
        
        Args:
            patient_id: The honeytoken patient ID
            user_id: ID of user who accessed it
            user_email: Email of user
            ip_address: Source IP address
            action: Type of action (access, read, update, delete, export)
            user_agent: Browser user agent
            
        Returns:
            SecurityIncident instance ready to be added to session
        """
        return cls(
            incident_type=IncidentType.HONEYTOKEN_ACCESS.value,
            severity=IncidentSeverity.HIGH.value,
            status=IncidentStatus.OPEN.value,
            user_id=user_id,
            user_email=user_email,
            patient_id=patient_id,
            resource_type="patient",
            resource_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.utcnow(),
            details={
                "action": action,
                "honeytoken_triggered": True,
                "alert": "Potential insider threat or unauthorized access detected",
                "evidence": f"Patient ID {patient_id} is a honeytoken record"
            }
        )
    
    @classmethod
    def create_failed_login_incident(
        cls,
        email: str,
        ip_address: str,
        attempt_count: int = 1,
        user_agent: Optional[str] = None
    ) -> "SecurityIncident":
        """
        Create a failed login incident.
        
        Args:
            email: Email attempting login
            ip_address: Source IP address
            attempt_count: Number of failed attempts
            user_agent: Browser user agent
            
        Returns:
            SecurityIncident instance
        """
        # Escalate severity based on attempt count
        if attempt_count >= 10:
            severity = IncidentSeverity.HIGH
            incident_type = IncidentType.BRUTE_FORCE_ATTEMPT
        elif attempt_count >= 5:
            severity = IncidentSeverity.MODERATE
            incident_type = IncidentType.BRUTE_FORCE_ATTEMPT
        else:
            severity = IncidentSeverity.LOW
            incident_type = IncidentType.FAILED_LOGIN
        
        return cls(
            incident_type=incident_type.value,
            severity=severity.value,
            status=IncidentStatus.OPEN.value,
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.utcnow(),
            details={
                "email_attempted": email,
                "attempt_count": attempt_count,
                "alert": f"Multiple failed login attempts ({attempt_count}) from {ip_address}"
            }
        )
    
    def resolve(
        self,
        resolver_id: int,
        notes: str,
        status: IncidentStatus = IncidentStatus.RESOLVED
    ) -> None:
        """
        Mark incident as resolved.
        
        Args:
            resolver_id: User ID of person resolving
            notes: Resolution notes
            status: Final status (RESOLVED or FALSE_POSITIVE)
        """
        self.status = status.value
        self.resolved_by = resolver_id
        self.resolved_at = datetime.utcnow()
        self.resolution_notes = notes
    
    def is_critical(self) -> bool:
        """Check if this is a critical incident requiring immediate action."""
        return self.severity in [
            IncidentSeverity.HIGH.value,
            IncidentSeverity.CRITICAL.value
        ]
    
    def to_alert_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for alerting systems.
        
        Returns:
            Dictionary suitable for Slack/email/PagerDuty alerts
        """
        return {
            "incident_id": str(self.id) if self.id else "pending",
            "type": self.incident_type,
            "severity": self.severity,
            "status": self.status,
            "user_email": self.user_email,
            "patient_id": self.patient_id,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "details": self.details,
            "evidence": self.evidence
        }
