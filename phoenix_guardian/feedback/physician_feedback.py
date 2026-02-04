"""
Phoenix Guardian - Physician Feedback System
Captures structured feedback from physicians during pilot.

Critical for: physician satisfaction tracking, UX improvements, MVP validation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import json
import logging
import uuid

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class FeedbackType(Enum):
    """Types of feedback physicians can provide."""
    RATING = "rating"                        # 1-5 star rating
    THUMBS = "thumbs"                        # Thumbs up/down
    SUGGESTION = "suggestion"                # Feature/improvement suggestion
    BUG_REPORT = "bug_report"               # Something went wrong
    FALSE_POSITIVE = "false_positive"       # Security blocked incorrectly
    FALSE_NEGATIVE = "false_negative"       # Should have been blocked
    QUALITY_ISSUE = "quality_issue"         # SOAP note quality problem
    PERFORMANCE = "performance"             # Too slow, timeouts
    USABILITY = "usability"                 # UI/UX issue
    PRAISE = "praise"                       # Positive feedback


class FeedbackCategory(Enum):
    """Categories for organizing feedback."""
    AI_SCRIBE = "ai_scribe"                 # SOAP note generation
    CLINICAL_NAVIGATION = "clinical_nav"    # Clinical decision support
    SAFETY_AGENT = "safety_agent"           # Patient safety alerts
    SECURITY = "security"                   # Security system
    PERFORMANCE = "performance"             # Speed/responsiveness
    UI_UX = "ui_ux"                         # User interface
    INTEGRATION = "integration"             # EHR/system integration
    GENERAL = "general"                     # Other


class FeedbackPriority(Enum):
    """Priority levels for feedback handling."""
    CRITICAL = "critical"                   # Immediate action needed
    HIGH = "high"                           # Address this week
    MEDIUM = "medium"                       # Address this sprint
    LOW = "low"                             # Backlog
    INFORMATIONAL = "informational"         # FYI only


class FeedbackStatus(Enum):
    """Status of feedback handling."""
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"
    DUPLICATE = "duplicate"


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class PhysicianFeedback:
    """
    Structured feedback from a physician.
    
    Captures the complete context needed to act on feedback.
    """
    # Identity
    feedback_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    physician_id: str = ""
    encounter_id: Optional[str] = None       # May be encounter-specific
    
    # Classification
    feedback_type: FeedbackType = FeedbackType.RATING
    category: FeedbackCategory = FeedbackCategory.GENERAL
    priority: FeedbackPriority = FeedbackPriority.MEDIUM
    status: FeedbackStatus = FeedbackStatus.NEW
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    
    # Content
    rating: Optional[int] = None             # 1-5 for RATING type
    thumbs_up: Optional[bool] = None         # For THUMBS type
    summary: str = ""                        # Brief description
    details: str = ""                        # Full description
    
    # Context capture
    agent_involved: Optional[str] = None     # Which agent was used
    input_sample: Optional[str] = None       # Input that caused issue (PHI-safe)
    output_sample: Optional[str] = None      # Output that was problematic
    expected_behavior: str = ""              # What physician expected
    
    # Resolution
    resolution_notes: str = ""
    resolved_by: str = ""
    linked_issue: str = ""                   # JIRA/GitHub issue
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    sentiment_score: float = 0.0             # -1 to 1, auto-analyzed
    physician_specialty: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "feedback_id": self.feedback_id,
            "tenant_id": self.tenant_id,
            "physician_id": self.physician_id,
            "encounter_id": self.encounter_id,
            "feedback_type": self.feedback_type.value,
            "category": self.category.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "rating": self.rating,
            "thumbs_up": self.thumbs_up,
            "summary": self.summary,
            "details": self.details,
            "agent_involved": self.agent_involved,
            "input_sample": self.input_sample,
            "output_sample": self.output_sample,
            "expected_behavior": self.expected_behavior,
            "resolution_notes": self.resolution_notes,
            "resolved_by": self.resolved_by,
            "linked_issue": self.linked_issue,
            "tags": self.tags,
            "sentiment_score": self.sentiment_score,
            "physician_specialty": self.physician_specialty,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhysicianFeedback":
        """Create from dictionary."""
        return cls(
            feedback_id=data.get("feedback_id", str(uuid.uuid4())),
            tenant_id=data.get("tenant_id", ""),
            physician_id=data.get("physician_id", ""),
            encounter_id=data.get("encounter_id"),
            feedback_type=FeedbackType(data.get("feedback_type", "rating")),
            category=FeedbackCategory(data.get("category", "general")),
            priority=FeedbackPriority(data.get("priority", "medium")),
            status=FeedbackStatus(data.get("status", "new")),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            rating=data.get("rating"),
            thumbs_up=data.get("thumbs_up"),
            summary=data.get("summary", ""),
            details=data.get("details", ""),
            agent_involved=data.get("agent_involved"),
            input_sample=data.get("input_sample"),
            output_sample=data.get("output_sample"),
            expected_behavior=data.get("expected_behavior", ""),
            resolution_notes=data.get("resolution_notes", ""),
            resolved_by=data.get("resolved_by", ""),
            linked_issue=data.get("linked_issue", ""),
            tags=data.get("tags", []),
            sentiment_score=data.get("sentiment_score", 0.0),
            physician_specialty=data.get("physician_specialty", ""),
        )
    
    def is_actionable(self) -> bool:
        """Check if feedback requires action."""
        return self.status in [FeedbackStatus.NEW, FeedbackStatus.ACKNOWLEDGED, FeedbackStatus.IN_PROGRESS]
    
    def is_positive(self) -> bool:
        """Check if feedback is positive."""
        if self.feedback_type == FeedbackType.RATING:
            return self.rating is not None and self.rating >= 4
        elif self.feedback_type == FeedbackType.THUMBS:
            return self.thumbs_up is True
        elif self.feedback_type == FeedbackType.PRAISE:
            return True
        return self.sentiment_score > 0.3
    
    def is_negative(self) -> bool:
        """Check if feedback is negative."""
        if self.feedback_type == FeedbackType.RATING:
            return self.rating is not None and self.rating <= 2
        elif self.feedback_type == FeedbackType.THUMBS:
            return self.thumbs_up is False
        elif self.feedback_type in [
            FeedbackType.BUG_REPORT,
            FeedbackType.FALSE_POSITIVE,
            FeedbackType.FALSE_NEGATIVE,
            FeedbackType.QUALITY_ISSUE,
        ]:
            return True
        return self.sentiment_score < -0.3


@dataclass
class FeedbackAggregation:
    """
    Aggregated feedback metrics for reporting.
    """
    tenant_id: str
    period_start: datetime
    period_end: datetime
    
    # Volume
    total_feedback: int = 0
    feedback_by_type: Dict[str, int] = field(default_factory=dict)
    feedback_by_category: Dict[str, int] = field(default_factory=dict)
    
    # Ratings
    average_rating: float = 0.0
    rating_distribution: Dict[int, int] = field(default_factory=dict)  # 1-5 counts
    thumbs_up_rate: float = 0.0
    
    # Sentiment
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    net_promoter_estimate: float = 0.0       # Estimated NPS
    
    # Response
    average_resolution_hours: float = 0.0
    open_count: int = 0
    resolved_count: int = 0
    
    # Top issues
    top_tags: List[tuple] = field(default_factory=list)  # (tag, count)
    common_issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
            },
            "volume": {
                "total": self.total_feedback,
                "by_type": self.feedback_by_type,
                "by_category": self.feedback_by_category,
            },
            "ratings": {
                "average": round(self.average_rating, 2),
                "distribution": self.rating_distribution,
                "thumbs_up_rate": round(self.thumbs_up_rate, 2),
            },
            "sentiment": {
                "positive": self.positive_count,
                "negative": self.negative_count,
                "neutral": self.neutral_count,
                "net_promoter_estimate": round(self.net_promoter_estimate, 1),
            },
            "response": {
                "average_resolution_hours": round(self.average_resolution_hours, 1),
                "open": self.open_count,
                "resolved": self.resolved_count,
            },
            "insights": {
                "top_tags": self.top_tags[:10],
                "common_issues": self.common_issues[:5],
            },
        }


# ==============================================================================
# Feedback Collector
# ==============================================================================

class FeedbackCollector:
    """
    Collects and manages physician feedback during pilot.
    
    Example:
        collector = FeedbackCollector(storage_backend=redis_client)
        
        # Record quick rating
        feedback = collector.record_rating(
            tenant_id="pilot_hospital_001",
            physician_id="dr_smith_001",
            encounter_id="enc-123",
            rating=5,
            summary="SOAP notes are excellent!"
        )
        
        # Record issue
        issue = collector.record_issue(
            tenant_id="pilot_hospital_001",
            physician_id="dr_smith_001",
            category=FeedbackCategory.AI_SCRIBE,
            summary="Assessment section missing differential",
            details="Expected 3-4 differentials but only got 2"
        )
        
        # Get aggregation
        report = collector.aggregate(
            tenant_id="pilot_hospital_001",
            period_start=week_start,
            period_end=week_end
        )
    """
    
    def __init__(
        self,
        storage_backend: Optional[Any] = None,
        auto_prioritize: bool = True,
        sentiment_analyzer: Optional[Any] = None,
    ):
        self._storage = storage_backend
        self._feedback_buffer: List[PhysicianFeedback] = []
        self._auto_prioritize = auto_prioritize
        self._sentiment_analyzer = sentiment_analyzer
        
        # Priority rules
        self._priority_rules = {
            FeedbackType.FALSE_POSITIVE: FeedbackPriority.HIGH,
            FeedbackType.FALSE_NEGATIVE: FeedbackPriority.CRITICAL,
            FeedbackType.BUG_REPORT: FeedbackPriority.HIGH,
            FeedbackType.QUALITY_ISSUE: FeedbackPriority.MEDIUM,
            FeedbackType.SUGGESTION: FeedbackPriority.LOW,
            FeedbackType.PRAISE: FeedbackPriority.INFORMATIONAL,
        }
        
        # Stats
        self._total_collected = 0
        self._positive_count = 0
        self._negative_count = 0
    
    # =========================================================================
    # Quick Recording Methods
    # =========================================================================
    
    def record_rating(
        self,
        tenant_id: str,
        physician_id: str,
        rating: int,
        encounter_id: Optional[str] = None,
        summary: str = "",
        agent_involved: Optional[str] = None,
        specialty: str = "",
    ) -> PhysicianFeedback:
        """
        Record a simple 1-5 rating.
        
        This is the most common feedback type for MVP pilots.
        """
        feedback = PhysicianFeedback(
            tenant_id=tenant_id,
            physician_id=physician_id,
            encounter_id=encounter_id,
            feedback_type=FeedbackType.RATING,
            category=FeedbackCategory.GENERAL,
            rating=rating,
            summary=summary or f"Rating: {rating}/5",
            agent_involved=agent_involved,
            physician_specialty=specialty,
        )
        
        return self._record(feedback)
    
    def record_thumbs(
        self,
        tenant_id: str,
        physician_id: str,
        thumbs_up: bool,
        encounter_id: Optional[str] = None,
        context: str = "",
        agent_involved: Optional[str] = None,
    ) -> PhysicianFeedback:
        """Record a thumbs up/down."""
        feedback = PhysicianFeedback(
            tenant_id=tenant_id,
            physician_id=physician_id,
            encounter_id=encounter_id,
            feedback_type=FeedbackType.THUMBS,
            category=FeedbackCategory.GENERAL,
            thumbs_up=thumbs_up,
            summary=f"Thumbs {'up' if thumbs_up else 'down'}: {context}" if context else f"Thumbs {'up' if thumbs_up else 'down'}",
            agent_involved=agent_involved,
        )
        
        return self._record(feedback)
    
    def record_issue(
        self,
        tenant_id: str,
        physician_id: str,
        summary: str,
        category: FeedbackCategory = FeedbackCategory.GENERAL,
        details: str = "",
        encounter_id: Optional[str] = None,
        agent_involved: Optional[str] = None,
        input_sample: Optional[str] = None,
        output_sample: Optional[str] = None,
        expected_behavior: str = "",
        tags: Optional[List[str]] = None,
    ) -> PhysicianFeedback:
        """Record an issue or bug report."""
        feedback = PhysicianFeedback(
            tenant_id=tenant_id,
            physician_id=physician_id,
            encounter_id=encounter_id,
            feedback_type=FeedbackType.BUG_REPORT,
            category=category,
            summary=summary,
            details=details,
            agent_involved=agent_involved,
            input_sample=input_sample,
            output_sample=output_sample,
            expected_behavior=expected_behavior,
            tags=tags or [],
        )
        
        return self._record(feedback)
    
    def record_false_positive(
        self,
        tenant_id: str,
        physician_id: str,
        encounter_id: str,
        summary: str,
        details: str = "",
        input_sample: Optional[str] = None,
        output_sample: Optional[str] = None,
    ) -> PhysicianFeedback:
        """
        Record a security false positive.
        
        This is CRITICAL for ML retraining - routed to FalsePositiveLoop.
        """
        feedback = PhysicianFeedback(
            tenant_id=tenant_id,
            physician_id=physician_id,
            encounter_id=encounter_id,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            category=FeedbackCategory.SECURITY,
            priority=FeedbackPriority.HIGH,
            summary=summary,
            details=details,
            input_sample=input_sample,
            output_sample=output_sample,
            expected_behavior="Request should have been allowed",
            tags=["false_positive", "ml_retraining"],
        )
        
        return self._record(feedback)
    
    def record_suggestion(
        self,
        tenant_id: str,
        physician_id: str,
        summary: str,
        details: str = "",
        category: FeedbackCategory = FeedbackCategory.GENERAL,
        tags: Optional[List[str]] = None,
    ) -> PhysicianFeedback:
        """Record a feature suggestion."""
        feedback = PhysicianFeedback(
            tenant_id=tenant_id,
            physician_id=physician_id,
            feedback_type=FeedbackType.SUGGESTION,
            category=category,
            priority=FeedbackPriority.LOW,
            summary=summary,
            details=details,
            tags=tags or ["suggestion"],
        )
        
        return self._record(feedback)
    
    def record_praise(
        self,
        tenant_id: str,
        physician_id: str,
        summary: str,
        details: str = "",
        encounter_id: Optional[str] = None,
        agent_involved: Optional[str] = None,
    ) -> PhysicianFeedback:
        """Record positive feedback."""
        feedback = PhysicianFeedback(
            tenant_id=tenant_id,
            physician_id=physician_id,
            encounter_id=encounter_id,
            feedback_type=FeedbackType.PRAISE,
            category=FeedbackCategory.GENERAL,
            priority=FeedbackPriority.INFORMATIONAL,
            summary=summary,
            details=details,
            agent_involved=agent_involved,
            tags=["praise", "testimonial"],
        )
        
        return self._record(feedback)
    
    # =========================================================================
    # Recording Core
    # =========================================================================
    
    def _record(self, feedback: PhysicianFeedback) -> PhysicianFeedback:
        """Core recording logic."""
        # Auto-prioritize
        if self._auto_prioritize and feedback.priority == FeedbackPriority.MEDIUM:
            if feedback.feedback_type in self._priority_rules:
                feedback.priority = self._priority_rules[feedback.feedback_type]
            
            # Low ratings get higher priority
            if feedback.rating is not None and feedback.rating <= 2:
                feedback.priority = FeedbackPriority.HIGH
        
        # Analyze sentiment if analyzer available
        if self._sentiment_analyzer:
            try:
                feedback.sentiment_score = self._analyze_sentiment(feedback)
            except Exception as e:
                logger.warning(f"Sentiment analysis failed: {e}")
        
        # Update stats
        self._total_collected += 1
        if feedback.is_positive():
            self._positive_count += 1
        elif feedback.is_negative():
            self._negative_count += 1
        
        # Store
        self._feedback_buffer.append(feedback)
        
        if self._storage:
            try:
                self._persist(feedback)
            except Exception as e:
                logger.error(f"Failed to persist feedback: {e}")
        
        logger.info(
            f"Recorded {feedback.feedback_type.value} feedback "
            f"from {feedback.physician_id}: {feedback.summary[:50]}"
        )
        
        return feedback
    
    def _analyze_sentiment(self, feedback: PhysicianFeedback) -> float:
        """Analyze sentiment of feedback text."""
        # In production, use a real sentiment analyzer
        text = f"{feedback.summary} {feedback.details}".lower()
        
        positive_words = ["great", "excellent", "love", "amazing", "helpful", "fast", "accurate"]
        negative_words = ["slow", "wrong", "bad", "broken", "missing", "error", "frustrated"]
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count + negative_count == 0:
            return 0.0
        
        return (positive_count - negative_count) / (positive_count + negative_count)
    
    def _persist(self, feedback: PhysicianFeedback) -> None:
        """Persist feedback to storage backend."""
        # Implementation depends on storage backend
        pass
    
    # =========================================================================
    # Retrieval
    # =========================================================================
    
    def get_feedback(self, feedback_id: str) -> Optional[PhysicianFeedback]:
        """Get feedback by ID."""
        for f in self._feedback_buffer:
            if f.feedback_id == feedback_id:
                return f
        return None
    
    def get_physician_feedback(
        self,
        physician_id: str,
        limit: int = 50,
    ) -> List[PhysicianFeedback]:
        """Get all feedback from a physician."""
        return [
            f for f in self._feedback_buffer
            if f.physician_id == physician_id
        ][:limit]
    
    def get_encounter_feedback(self, encounter_id: str) -> List[PhysicianFeedback]:
        """Get all feedback for an encounter."""
        return [
            f for f in self._feedback_buffer
            if f.encounter_id == encounter_id
        ]
    
    def get_actionable(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[PhysicianFeedback]:
        """Get all actionable feedback."""
        result = [
            f for f in self._feedback_buffer
            if f.is_actionable()
            and (tenant_id is None or f.tenant_id == tenant_id)
        ]
        
        # Sort by priority
        priority_order = {
            FeedbackPriority.CRITICAL: 0,
            FeedbackPriority.HIGH: 1,
            FeedbackPriority.MEDIUM: 2,
            FeedbackPriority.LOW: 3,
            FeedbackPriority.INFORMATIONAL: 4,
        }
        
        result.sort(key=lambda f: (priority_order.get(f.priority, 5), f.created_at))
        
        return result[:limit]
    
    def get_false_positives(
        self,
        tenant_id: Optional[str] = None,
    ) -> List[PhysicianFeedback]:
        """Get all false positive reports for ML retraining."""
        return [
            f for f in self._feedback_buffer
            if f.feedback_type == FeedbackType.FALSE_POSITIVE
            and (tenant_id is None or f.tenant_id == tenant_id)
        ]
    
    # =========================================================================
    # Aggregation
    # =========================================================================
    
    def aggregate(
        self,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> FeedbackAggregation:
        """
        Aggregate feedback for reporting.
        
        Used for weekly pilot reports.
        """
        relevant = [
            f for f in self._feedback_buffer
            if f.tenant_id == tenant_id
            and period_start <= f.created_at <= period_end
        ]
        
        agg = FeedbackAggregation(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            total_feedback=len(relevant),
        )
        
        if not relevant:
            return agg
        
        # By type
        for f in relevant:
            type_key = f.feedback_type.value
            agg.feedback_by_type[type_key] = agg.feedback_by_type.get(type_key, 0) + 1
        
        # By category
        for f in relevant:
            cat_key = f.category.value
            agg.feedback_by_category[cat_key] = agg.feedback_by_category.get(cat_key, 0) + 1
        
        # Ratings
        ratings = [f.rating for f in relevant if f.rating is not None]
        if ratings:
            agg.average_rating = sum(ratings) / len(ratings)
            for r in ratings:
                agg.rating_distribution[r] = agg.rating_distribution.get(r, 0) + 1
        
        # Thumbs
        thumbs = [f.thumbs_up for f in relevant if f.thumbs_up is not None]
        if thumbs:
            agg.thumbs_up_rate = sum(1 for t in thumbs if t) / len(thumbs)
        
        # Sentiment
        agg.positive_count = sum(1 for f in relevant if f.is_positive())
        agg.negative_count = sum(1 for f in relevant if f.is_negative())
        agg.neutral_count = len(relevant) - agg.positive_count - agg.negative_count
        
        # Estimated NPS (simplified)
        if agg.total_feedback > 0:
            promoter_rate = agg.positive_count / agg.total_feedback
            detractor_rate = agg.negative_count / agg.total_feedback
            agg.net_promoter_estimate = (promoter_rate - detractor_rate) * 100
        
        # Resolution stats
        agg.open_count = sum(1 for f in relevant if f.is_actionable())
        agg.resolved_count = sum(1 for f in relevant if f.status == FeedbackStatus.RESOLVED)
        
        resolved = [f for f in relevant if f.resolved_at and f.created_at]
        if resolved:
            resolution_times = [
                (f.resolved_at - f.created_at).total_seconds() / 3600
                for f in resolved
            ]
            agg.average_resolution_hours = sum(resolution_times) / len(resolution_times)
        
        # Top tags
        tag_counts: Dict[str, int] = {}
        for f in relevant:
            for tag in f.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        agg.top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Common issues (from negative feedback summaries)
        agg.common_issues = [
            f.summary for f in relevant
            if f.is_negative()
        ][:5]
        
        return agg
    
    # =========================================================================
    # Status Updates
    # =========================================================================
    
    def update_status(
        self,
        feedback_id: str,
        status: FeedbackStatus,
        notes: str = "",
        resolved_by: str = "",
    ) -> Optional[PhysicianFeedback]:
        """Update feedback status."""
        feedback = self.get_feedback(feedback_id)
        if not feedback:
            return None
        
        feedback.status = status
        feedback.updated_at = datetime.now()
        
        if status == FeedbackStatus.RESOLVED:
            feedback.resolved_at = datetime.now()
            feedback.resolution_notes = notes
            feedback.resolved_by = resolved_by
        
        logger.info(f"Updated feedback {feedback_id} to {status.value}")
        
        return feedback
    
    def link_issue(
        self,
        feedback_id: str,
        issue_url: str,
    ) -> Optional[PhysicianFeedback]:
        """Link feedback to a JIRA/GitHub issue."""
        feedback = self.get_feedback(feedback_id)
        if not feedback:
            return None
        
        feedback.linked_issue = issue_url
        feedback.updated_at = datetime.now()
        
        if feedback.status == FeedbackStatus.NEW:
            feedback.status = FeedbackStatus.ACKNOWLEDGED
        
        return feedback
    
    # =========================================================================
    # Stats
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        return {
            "total_collected": self._total_collected,
            "buffer_size": len(self._feedback_buffer),
            "positive_count": self._positive_count,
            "negative_count": self._negative_count,
            "neutral_count": self._total_collected - self._positive_count - self._negative_count,
            "positive_rate": (
                self._positive_count / self._total_collected
                if self._total_collected > 0 else 0.0
            ),
        }
