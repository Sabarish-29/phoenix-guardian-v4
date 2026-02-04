"""
Encounter model for patient visits.

Contains PHI - must be encrypted at rest and audited.
"""

from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Relationship, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .agent_metrics import AgentMetric
    from .audit_log import AuditLog
    from .soap_note import SOAPNote
    from .user import User


class EncounterStatus(str, Enum):
    """Status of patient encounter.

    Workflow: IN_PROGRESS -> AWAITING_REVIEW -> REVIEWED -> SIGNED
              (can be CANCELLED at any point)
    """

    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    REVIEWED = "reviewed"
    SIGNED = "signed"
    CANCELLED = "cancelled"


class EncounterType(str, Enum):
    """Types of clinical encounters."""

    OFFICE_VISIT = "office_visit"
    TELEHEALTH = "telehealth"
    URGENT_CARE = "urgent_care"
    EMERGENCY = "emergency"
    FOLLOW_UP = "follow_up"
    ANNUAL_PHYSICAL = "annual_physical"
    PROCEDURE = "procedure"


class Encounter(BaseModel):
    """
    Patient encounter (visit) record.

    Contains PHI - must be encrypted at rest and audited.

    Attributes:
        patient_mrn: Patient Medical Record Number
        encounter_type: Type of encounter
        status: Current encounter status
        provider_id: Physician/provider who saw patient
        transcript: Voice-to-text transcript
        transcript_length: Length of transcript
        processing_time_ms: Total processing time
        safety_check_passed: SafetyAgent validation result
        threat_score: Security threat score
    """

    __tablename__ = "encounters"

    # Patient identification (should be encrypted)
    patient_mrn = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Patient Medical Record Number (encrypted)",
    )

    patient_first_name = Column(
        String(100),
        nullable=True,
        comment="Patient first name (encrypted PHI)",
    )

    patient_last_name = Column(
        String(100),
        nullable=True,
        comment="Patient last name (encrypted PHI)",
    )

    patient_dob = Column(
        String(20),
        nullable=True,
        comment="Patient date of birth (encrypted PHI)",
    )

    chief_complaint = Column(
        String(500),
        nullable=True,
        comment="Chief complaint / reason for visit",
    )

    # Encounter details
    encounter_type = Column(
        String(50),
        nullable=False,
        comment="Type of encounter (office visit, ER, telehealth, etc.)",
    )

    status = Column(
        SQLEnum(EncounterStatus),
        nullable=False,
        default=EncounterStatus.IN_PROGRESS,
        index=True,
        comment="Current encounter status",
    )

    # Provider
    provider_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="Physician/provider who saw patient",
    )

    # Transcript (encrypted PHI)
    transcript = Column(
        Text,
        nullable=False,
        comment="Voice-to-text transcript of encounter (encrypted)",
    )

    transcript_length = Column(
        Integer,
        nullable=False,
        comment="Length of transcript in characters",
    )

    # Processing metadata
    processing_time_ms = Column(
        Float,
        nullable=True,
        comment="Total processing time in milliseconds",
    )

    safety_check_passed = Column(
        Boolean,
        nullable=True,
        comment="SafetyAgent validation result",
    )

    threat_score = Column(
        Float,
        nullable=True,
        comment="Security threat score (0.0-1.0)",
    )

    # Relationships
    provider: Relationship["User"] = relationship(
        "User",
        back_populates="encounters",
        foreign_keys=[provider_id],
    )

    soap_note: Relationship[Optional["SOAPNote"]] = relationship(
        "SOAPNote",
        back_populates="encounter",
        uselist=False,  # One-to-one
        cascade="all, delete-orphan",
    )

    audit_logs: Relationship[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="encounter",
        foreign_keys="AuditLog.encounter_id",
    )

    agent_metrics: Relationship[List["AgentMetric"]] = relationship(
        "AgentMetric",
        back_populates="encounter",
        foreign_keys="AgentMetric.encounter_id",
    )

    def __repr__(self) -> str:
        """Return string representation (hide PHI)."""
        return (
            f"<Encounter(id={self.id}, patient_mrn='***', "
            f"status='{self.status.value}')>"
        )

    def is_editable(self) -> bool:
        """Check if encounter can still be edited.

        Returns:
            True if not yet signed or cancelled
        """
        return self.status not in [
            EncounterStatus.SIGNED,
            EncounterStatus.CANCELLED,
        ]

    def mark_for_review(self) -> None:
        """Mark encounter as awaiting review."""
        if self.is_editable():
            self.status = EncounterStatus.AWAITING_REVIEW

    def mark_reviewed(self) -> None:
        """Mark encounter as reviewed."""
        if self.status == EncounterStatus.AWAITING_REVIEW:
            self.status = EncounterStatus.REVIEWED

    def sign(self) -> None:
        """Sign the encounter (final)."""
        if self.status == EncounterStatus.REVIEWED:
            self.status = EncounterStatus.SIGNED

    def cancel(self) -> None:
        """Cancel the encounter."""
        if self.is_editable():
            self.status = EncounterStatus.CANCELLED
