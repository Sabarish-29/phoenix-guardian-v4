"""
Audit log model for HIPAA compliance.

Records every action in the system with comprehensive details.
NEVER soft-delete audit logs - they must be immutable.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Relationship, Session, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .encounter import Encounter
    from .user import User


class AuditAction(str, Enum):
    """Types of audited actions.

    Categories:
    - Authentication: login, logout, failed login
    - Data access: viewing records
    - Data modification: create, update, delete
    - Security: threat detection events
    - Administrative: user management
    """

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"

    # Data access - General
    PHI_ACCESSED = "phi_accessed"
    VIEW_ENCOUNTER = "view_encounter"
    VIEW_SOAP_NOTE = "view_soap_note"
    VIEW_PATIENT_DATA = "view_patient_data"
    EXPORT_DATA = "export_data"
    SEARCH_PATIENTS = "search_patients"

    # Data modification - Encounters
    ENCOUNTER_CREATED = "encounter_created"
    CREATE_ENCOUNTER = "create_encounter"
    UPDATE_ENCOUNTER = "update_encounter"
    DELETE_ENCOUNTER = "delete_encounter"

    # Data modification - SOAP Notes
    NOTE_CREATED = "note_created"
    NOTE_MODIFIED = "note_modified"
    NOTE_SIGNED = "note_signed"
    CREATE_SOAP_NOTE = "create_soap_note"
    EDIT_SOAP_NOTE = "edit_soap_note"
    SIGN_SOAP_NOTE = "sign_soap_note"

    # Security
    SECURITY_THREAT_DETECTED = "security_threat_detected"
    SECURITY_THREAT_BLOCKED = "security_threat_blocked"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"

    # Administrative
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    ROLE_CHANGED = "role_changed"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"


class AuditLog(Base, TimestampMixin):
    """
    Comprehensive audit log for HIPAA compliance.

    Records every action in the system with:
    - Who (user)
    - What (action)
    - When (timestamp)
    - Where (IP address)
    - Why (purpose/context)
    - What data (resource accessed)

    NEVER soft-delete audit logs - they must be immutable.

    Attributes:
        user_id: User who performed action
        user_email: User email at time of action
        action: Action performed
        action_description: Human-readable description
        resource_type: Type of resource accessed
        resource_id: ID of resource accessed
        encounter_id: Associated encounter
        patient_mrn: Patient MRN if PHI accessed
        ip_address: Client IP address
        user_agent: Client user agent string
        request_id: Unique request ID for correlation
        session_id: User session ID
        metadata: Additional action-specific metadata
        success: Whether action succeeded
        error_message: Error message if failed
    """

    __tablename__ = "audit_logs"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Who
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,  # Nullable for unauthenticated actions
        index=True,
        comment="User who performed action",
    )

    user_email = Column(
        String(255),
        nullable=True,
        comment="User email at time of action (for audit trail)",
    )

    # What
    action = Column(
        SQLEnum(AuditAction),
        nullable=False,
        index=True,
        comment="Action performed",
    )

    action_description = Column(
        String(500),
        nullable=True,
        comment="Human-readable description of action",
    )

    # What data
    resource_type = Column(
        String(50),
        nullable=True,
        comment="Type of resource accessed (encounter, soap_note, etc.)",
    )

    resource_id = Column(
        Integer,
        nullable=True,
        comment="ID of resource accessed",
    )

    encounter_id = Column(
        Integer,
        ForeignKey("encounters.id"),
        nullable=True,
        index=True,
        comment="Associated encounter (if applicable)",
    )

    patient_mrn = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Patient MRN (if PHI accessed)",
    )

    # Where
    ip_address = Column(
        String(45),  # IPv6 max length
        nullable=True,
        comment="Client IP address",
    )

    user_agent = Column(
        String(500),
        nullable=True,
        comment="Client user agent string",
    )

    # Context
    request_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Unique request ID for correlation",
    )

    session_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="User session ID",
    )

    # Additional metadata (using JSON for cross-database compatibility)
    metadata_json = Column(
        "metadata",
        JSON,
        nullable=True,
        comment="Additional action-specific metadata",
    )

    # Success/failure
    success = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether action succeeded",
    )

    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if action failed",
    )

    # Relationships
    user: Relationship[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
        foreign_keys=[user_id],
    )

    encounter: Relationship[Optional["Encounter"]] = relationship(
        "Encounter",
        back_populates="audit_logs",
        foreign_keys=[encounter_id],
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<AuditLog(id={self.id}, action='{self.action.value}', "
            f"user_id={self.user_id}, timestamp={self.created_at})>"
        )

    @classmethod
    def log_action(
        cls,
        session: Session,
        action: AuditAction,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        encounter_id: Optional[int] = None,
        patient_mrn: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        description: Optional[str] = None,
        commit: bool = True,
    ) -> "AuditLog":
        """
        Convenience method to create audit log entry.

        Args:
            session: Database session
            action: Action being logged
            user_id: User performing action
            user_email: User email for audit trail
            resource_type: Type of resource accessed
            resource_id: ID of resource accessed
            encounter_id: Associated encounter ID
            patient_mrn: Patient MRN if PHI accessed
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Request correlation ID
            session_id: User session ID
            metadata: Additional metadata
            success: Whether action succeeded
            error_message: Error message if failed
            description: Human-readable description
            commit: Whether to commit transaction

        Returns:
            Created AuditLog instance

        Example:
            AuditLog.log_action(
                session=db_session,
                action=AuditAction.VIEW_ENCOUNTER,
                user_id=current_user.id,
                encounter_id=123,
                patient_mrn="MRN001234",
                ip_address=request.remote_addr
            )
        """
        log_entry = cls(
            user_id=user_id,
            user_email=user_email,
            action=action,
            action_description=description,
            resource_type=resource_type,
            resource_id=resource_id,
            encounter_id=encounter_id,
            patient_mrn=patient_mrn,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            session_id=session_id,
            metadata_json=metadata,
            success=success,
            error_message=error_message,
        )

        session.add(log_entry)

        if commit:
            session.commit()

        return log_entry
