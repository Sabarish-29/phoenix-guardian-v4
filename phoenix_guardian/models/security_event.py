"""
Security event model for threat tracking.

Logged by SafetyAgent when threats are detected.
Used for security monitoring and incident response.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, JSON, String, Text

from .base import BaseModel


class ThreatSeverity(str, Enum):
    """Severity levels for security threats.

    Maps to SafetyAgent ThreatLevel:
    - NONE: No threat detected
    - LOW: Minor concern, allow with monitoring
    - MEDIUM: Moderate concern, may need review
    - HIGH: Serious threat, block input
    - CRITICAL: Attack detected, block and alert
    """

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEvent(BaseModel):
    """
    Security threat detection events.

    Logged by SafetyAgent when threats detected.
    Used for security monitoring and incident response.

    Attributes:
        threat_type: Type of threat detected
        severity: Threat severity level
        threat_score: Calculated threat score (0.0-1.0)
        confidence: Detection confidence (0.0-1.0)
        input_text: Input that triggered detection
        input_length: Length of input
        detection_method: Method used for detection
        patterns_matched: List of patterns matched
        evidence: Evidence of threat
        was_blocked: Whether input was blocked
        action_taken: Action taken in response
        user_id: User who submitted input
        ip_address: Source IP address
        session_id: Session ID
        request_id: Request ID for correlation
    """

    __tablename__ = "security_events"

    # Threat classification
    threat_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of threat (prompt_injection, sql_injection, etc.)",
    )

    severity = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Threat severity level",
    )

    threat_score = Column(
        Float,
        nullable=False,
        comment="Calculated threat score (0.0-1.0)",
    )

    confidence = Column(
        Float,
        nullable=False,
        comment="Detection confidence (0.0-1.0)",
    )

    # Input details
    input_text = Column(
        Text,
        nullable=False,
        comment="Input that triggered detection",
    )

    input_length = Column(
        Integer,
        nullable=False,
        comment="Length of input in characters",
    )

    # Detection details
    detection_method = Column(
        String(50),
        nullable=False,
        default="pattern",
        comment="Method used for detection (pattern, ml_model, etc.)",
    )

    patterns_matched = Column(
        JSON,
        nullable=True,
        comment="List of patterns that matched",
    )

    evidence = Column(
        Text,
        nullable=True,
        comment="Evidence of threat",
    )

    # Response
    was_blocked = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether input was blocked",
    )

    action_taken = Column(
        String(100),
        nullable=True,
        comment="Action taken (rejected, sanitized, flagged)",
    )

    # Context
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
        comment="User who submitted input",
    )

    ip_address = Column(
        String(45),
        nullable=True,
        comment="Source IP address",
    )

    session_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Session ID",
    )

    request_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Request ID for correlation",
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<SecurityEvent(id={self.id}, type='{self.threat_type}', "
            f"severity='{self.severity}')>"
        )

    @classmethod
    def from_safety_result(
        cls,
        safety_result: Dict[str, Any],
        input_text: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> "SecurityEvent":
        """
        Create SecurityEvent from SafetyAgent result.

        Args:
            safety_result: Result from SafetyAgent.execute()
            input_text: Original input text
            user_id: User who submitted input
            ip_address: Source IP address
            session_id: Session ID
            request_id: Request ID

        Returns:
            SecurityEvent instance
        """
        data = safety_result.get("data", {})
        detections = data.get("detections", [])

        # Get primary threat type and evidence
        threat_type = "unknown"
        evidence = None
        patterns: List[str] = []

        if detections:
            primary = detections[0]
            threat_type = primary.get("type", "unknown")
            evidence = primary.get("evidence")
            patterns = [d.get("type", "") for d in detections]

        return cls(
            threat_type=threat_type,
            severity=data.get("threat_level", "medium"),
            threat_score=data.get("threat_score", 0.5),
            confidence=detections[0].get("confidence", 0.85) if detections else 0.5,
            input_text=input_text,
            input_length=len(input_text),
            detection_method="pattern",
            patterns_matched=patterns,
            evidence=evidence,
            was_blocked=not data.get("is_safe", True),
            action_taken="blocked" if not data.get("is_safe", True) else "allowed",
            user_id=user_id,
            ip_address=ip_address,
            session_id=session_id,
            request_id=request_id,
        )

    def is_critical(self) -> bool:
        """Check if this is a critical security event.

        Returns:
            True if severity is HIGH or CRITICAL
        """
        return self.severity in [
            ThreatSeverity.HIGH.value,
            ThreatSeverity.CRITICAL.value,
        ]
