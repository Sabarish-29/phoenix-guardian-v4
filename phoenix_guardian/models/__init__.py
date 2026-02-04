"""
Phoenix Guardian Database Models Package.

Provides SQLAlchemy ORM models for HIPAA-compliant data storage:
- User: Authentication and authorization
- Encounter: Patient visit records (PHI)
- SOAPNote: Clinical documentation (PHI)
- AuditLog: HIPAA compliance audit trail
- SecurityEvent: Threat detection events
- AgentMetric: AI agent performance tracking

All PHI-containing models include:
- Soft deletes (never hard delete PHI)
- Audit trails via AuditableMixin
- Timestamp tracking
"""

from .agent_metrics import AgentMetric
from .audit_log import AuditAction, AuditLog
from .base import AuditableMixin, Base, BaseModel, SoftDeleteMixin, TimestampMixin
from .encounter import Encounter, EncounterStatus, EncounterType
from .security_event import SecurityEvent, ThreatSeverity
from .soap_note import SOAPNote
from .user import ROLE_HIERARCHY, User, UserRole

__all__ = [
    # Base classes
    "Base",
    "BaseModel",
    "TimestampMixin",
    "SoftDeleteMixin",
    "AuditableMixin",
    # User
    "User",
    "UserRole",
    "ROLE_HIERARCHY",
    # Encounter
    "Encounter",
    "EncounterStatus",
    "EncounterType",
    # SOAP Note
    "SOAPNote",
    # Audit
    "AuditLog",
    "AuditAction",
    # Security
    "SecurityEvent",
    "ThreatSeverity",
    # Metrics
    "AgentMetric",
]
