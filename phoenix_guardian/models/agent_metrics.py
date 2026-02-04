"""
Agent metrics model for performance tracking.

Tracks AI agent execution metrics including timing,
token usage, memory consumption, and quality scores.
"""

from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from .base import BaseModel


class AgentMetric(BaseModel):
    """
    AI agent performance metrics.

    Tracks execution metrics for BaseAgent subclasses.
    Used for performance monitoring and optimization.

    Attributes:
        agent_name: Name of the agent (scribe, navigator, safety)
        agent_version: Version of the agent
        execution_time_ms: Execution time in milliseconds
        success: Whether execution was successful
        token_count: Token count (input + output)
        input_tokens: Input token count
        output_tokens: Output token count
        memory_mb: Memory usage in MB
        quality_score: Agent-assigned quality score
        physician_rating: Physician rating (1-5)
        encounter_id: Associated encounter
        request_id: Request ID for correlation
        metadata_json: Additional metrics as JSON
        error_message: Error message if failed
    """

    __tablename__ = "agent_metrics"

    # Agent identification
    agent_name = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Name of the agent",
    )

    agent_version = Column(
        String(20),
        nullable=True,
        default="1.0.0",
        comment="Version of the agent",
    )

    # Performance metrics
    execution_time_ms = Column(
        Integer,
        nullable=False,
        comment="Execution time in milliseconds",
    )

    success = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether execution was successful",
    )

    # Token usage
    token_count = Column(
        Integer,
        nullable=True,
        comment="Total token count (input + output)",
    )

    input_tokens = Column(
        Integer,
        nullable=True,
        comment="Input token count",
    )

    output_tokens = Column(
        Integer,
        nullable=True,
        comment="Output token count",
    )

    # Resource usage
    memory_mb = Column(
        Float,
        nullable=True,
        comment="Memory usage in MB",
    )

    # Quality metrics
    quality_score = Column(
        Float,
        nullable=True,
        comment="Agent-assigned quality score (0.0-1.0)",
    )

    physician_rating = Column(
        Integer,
        nullable=True,
        comment="Physician rating (1-5 stars)",
    )

    # Context
    encounter_id = Column(
        Integer,
        ForeignKey("encounters.id"),
        nullable=True,
        index=True,
        comment="Associated encounter",
    )

    request_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Request ID for correlation",
    )

    # Additional metadata
    metadata_json = Column(
        "metadata",
        JSON,
        nullable=True,
        comment="Additional metrics as JSON",
    )

    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if failed",
    )

    # Relationships
    encounter = relationship(
        "Encounter",
        back_populates="agent_metrics",
        foreign_keys=[encounter_id],
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<AgentMetric(id={self.id}, agent='{self.agent_name}', "
            f"time={self.execution_time_ms}ms, success={self.success})>"
        )

    @classmethod
    def from_agent_result(
        cls,
        agent_name: str,
        result: Dict[str, Any],
        encounter_id: Optional[int] = None,
        request_id: Optional[str] = None,
        agent_version: Optional[str] = "1.0.0",
    ) -> "AgentMetric":
        """
        Create AgentMetric from agent execution result.

        Args:
            agent_name: Name of the agent
            result: Result from BaseAgent.execute()
            encounter_id: Associated encounter ID
            request_id: Request ID for correlation
            agent_version: Version of the agent

        Returns:
            AgentMetric instance
        """
        metadata = result.get("metadata", {})
        data = result.get("data", {})

        # Calculate execution time
        execution_time_ms = int(metadata.get("execution_time_seconds", 0) * 1000)

        # Extract token counts if available
        token_count = data.get("token_count")
        input_tokens = None
        output_tokens = None

        if isinstance(token_count, dict):
            input_tokens = token_count.get("input")
            output_tokens = token_count.get("output")
            token_count = (input_tokens or 0) + (output_tokens or 0)

        return cls(
            agent_name=agent_name,
            agent_version=agent_version,
            execution_time_ms=execution_time_ms,
            success=result.get("status") == "success",
            token_count=token_count if isinstance(token_count, int) else None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            quality_score=data.get("quality_score"),
            encounter_id=encounter_id,
            request_id=request_id,
            metadata_json={
                "agent": metadata.get("agent"),
                "version": metadata.get("version"),
                "model": data.get("model"),
            },
            error_message=result.get("error") if result.get("status") != "success" else None,
        )

    def rate(self, rating: int) -> None:
        """
        Add physician rating to metrics.

        Args:
            rating: Rating value (1-5 stars)

        Raises:
            ValueError: If rating is not 1-5
        """
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        self.physician_rating = rating

    def is_slow(self, threshold_ms: int = 5000) -> bool:
        """
        Check if execution was slow.

        Args:
            threshold_ms: Threshold in milliseconds

        Returns:
            True if execution_time_ms exceeds threshold
        """
        return self.execution_time_ms > threshold_ms

    def is_high_quality(self, threshold: float = 0.8) -> bool:
        """
        Check if quality score is above threshold.

        Args:
            threshold: Quality score threshold

        Returns:
            True if quality_score exceeds threshold
        """
        return self.quality_score is not None and self.quality_score >= threshold
