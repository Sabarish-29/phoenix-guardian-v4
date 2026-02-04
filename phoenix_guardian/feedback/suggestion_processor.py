"""
Phoenix Guardian - Suggestion Processor
Processes feature suggestions from physician feedback into product backlog.

Converts raw physician suggestions into actionable product items.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class SuggestionPriority(Enum):
    """Priority for product backlog."""
    CRITICAL = "critical"                    # P0 - Must fix immediately
    HIGH = "high"                            # P1 - This sprint
    MEDIUM = "medium"                        # P2 - Next sprint
    LOW = "low"                              # P3 - Backlog
    WISHLIST = "wishlist"                    # P4 - Nice to have


class SuggestionCategory(Enum):
    """Categories for organizing suggestions."""
    AI_QUALITY = "ai_quality"                # AI output improvements
    WORKFLOW = "workflow"                    # Workflow enhancements
    UI_UX = "ui_ux"                         # Interface changes
    PERFORMANCE = "performance"              # Speed/reliability
    INTEGRATION = "integration"              # EHR/system integration
    CLINICAL = "clinical"                   # Clinical feature requests
    SECURITY = "security"                   # Security-related
    OTHER = "other"


class SuggestionStatus(Enum):
    """Status in product backlog."""
    NEW = "new"
    TRIAGED = "triaged"
    ACCEPTED = "accepted"
    IN_DEVELOPMENT = "in_development"
    RELEASED = "released"
    DECLINED = "declined"
    DUPLICATE = "duplicate"


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class FeatureSuggestion:
    """
    A feature suggestion from physician feedback.
    
    Structured for product backlog integration.
    """
    # Identity
    suggestion_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    
    # Source
    source_feedback_ids: List[str] = field(default_factory=list)
    physician_ids: List[str] = field(default_factory=list)
    vote_count: int = 1                      # How many physicians want this
    
    # Classification
    priority: SuggestionPriority = SuggestionPriority.MEDIUM
    category: SuggestionCategory = SuggestionCategory.OTHER
    status: SuggestionStatus = SuggestionStatus.NEW
    
    # Content
    title: str = ""
    description: str = ""
    use_case: str = ""                       # Physician's use case
    expected_benefit: str = ""               # Why they want it
    
    # Triage
    estimated_effort: str = ""               # XS, S, M, L, XL
    estimated_impact: str = ""               # Low, Medium, High
    triaged_by: str = ""
    triage_notes: str = ""
    
    # Development
    linked_issue: str = ""                   # JIRA/GitHub issue
    release_version: str = ""
    released_at: Optional[datetime] = None
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    specialties: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "suggestion_id": self.suggestion_id,
            "tenant_id": self.tenant_id,
            "source_feedback_ids": self.source_feedback_ids,
            "physician_ids": self.physician_ids,
            "vote_count": self.vote_count,
            "priority": self.priority.value,
            "category": self.category.value,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "use_case": self.use_case,
            "expected_benefit": self.expected_benefit,
            "estimated_effort": self.estimated_effort,
            "estimated_impact": self.estimated_impact,
            "triaged_by": self.triaged_by,
            "triage_notes": self.triage_notes,
            "linked_issue": self.linked_issue,
            "release_version": self.release_version,
            "released_at": self.released_at.isoformat() if self.released_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
            "specialties": self.specialties,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureSuggestion":
        """Create from dictionary."""
        return cls(
            suggestion_id=data.get("suggestion_id", str(uuid.uuid4())),
            tenant_id=data.get("tenant_id", ""),
            source_feedback_ids=data.get("source_feedback_ids", []),
            physician_ids=data.get("physician_ids", []),
            vote_count=data.get("vote_count", 1),
            priority=SuggestionPriority(data.get("priority", "medium")),
            category=SuggestionCategory(data.get("category", "other")),
            status=SuggestionStatus(data.get("status", "new")),
            title=data.get("title", ""),
            description=data.get("description", ""),
            use_case=data.get("use_case", ""),
            expected_benefit=data.get("expected_benefit", ""),
            estimated_effort=data.get("estimated_effort", ""),
            estimated_impact=data.get("estimated_impact", ""),
            triaged_by=data.get("triaged_by", ""),
            triage_notes=data.get("triage_notes", ""),
            linked_issue=data.get("linked_issue", ""),
            release_version=data.get("release_version", ""),
            released_at=datetime.fromisoformat(data["released_at"]) if data.get("released_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
            tags=data.get("tags", []),
            specialties=data.get("specialties", []),
        )
    
    def add_vote(self, physician_id: str, feedback_id: str) -> None:
        """Add a vote from another physician."""
        if physician_id not in self.physician_ids:
            self.physician_ids.append(physician_id)
            self.vote_count = len(self.physician_ids)
        
        if feedback_id not in self.source_feedback_ids:
            self.source_feedback_ids.append(feedback_id)
        
        self.updated_at = datetime.now()
    
    def is_actionable(self) -> bool:
        """Check if suggestion is actionable."""
        return self.status in [
            SuggestionStatus.NEW,
            SuggestionStatus.TRIAGED,
            SuggestionStatus.ACCEPTED,
        ]


# ==============================================================================
# Suggestion Processor
# ==============================================================================

class SuggestionProcessor:
    """
    Processes physician suggestions into product backlog items.
    
    Features:
    - Deduplication (merge similar suggestions)
    - Vote aggregation
    - Priority scoring
    - Backlog export
    
    Example:
        processor = SuggestionProcessor()
        
        # Add suggestion from feedback
        suggestion = processor.process_suggestion(
            tenant_id="pilot_hospital_001",
            physician_id="dr_smith_001",
            feedback_id="fb-123",
            title="Add voice recording option",
            description="Allow dictating SOAP notes via voice",
            category=SuggestionCategory.WORKFLOW,
            specialty="internal_medicine"
        )
        
        # Get prioritized backlog
        backlog = processor.get_prioritized_backlog()
        
        # Export to JIRA
        jira_items = processor.export_to_jira_format()
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.7,
        auto_prioritize: bool = True,
    ):
        self._suggestions: Dict[str, FeatureSuggestion] = {}
        self._similarity_threshold = similarity_threshold
        self._auto_prioritize = auto_prioritize
        
        # Priority scoring weights
        self._priority_weights = {
            "vote_count": 0.3,
            "impact": 0.3,
            "effort": 0.2,
            "age": 0.1,
            "category_weight": 0.1,
        }
        
        # Category weights (clinical features get boost)
        self._category_weights = {
            SuggestionCategory.CLINICAL: 1.2,
            SuggestionCategory.AI_QUALITY: 1.1,
            SuggestionCategory.WORKFLOW: 1.0,
            SuggestionCategory.PERFORMANCE: 1.0,
            SuggestionCategory.UI_UX: 0.9,
            SuggestionCategory.INTEGRATION: 0.9,
            SuggestionCategory.SECURITY: 1.1,
            SuggestionCategory.OTHER: 0.8,
        }
        
        # Stats
        self._total_processed = 0
        self._merged_count = 0
    
    # =========================================================================
    # Processing
    # =========================================================================
    
    def process_suggestion(
        self,
        tenant_id: str,
        physician_id: str,
        feedback_id: str,
        title: str,
        description: str = "",
        category: SuggestionCategory = SuggestionCategory.OTHER,
        use_case: str = "",
        expected_benefit: str = "",
        specialty: str = "",
        tags: Optional[List[str]] = None,
    ) -> FeatureSuggestion:
        """
        Process a new suggestion.
        
        May merge with existing similar suggestion.
        """
        self._total_processed += 1
        
        # Check for similar existing suggestions
        similar = self._find_similar(title, description, category)
        
        if similar:
            # Merge: add vote to existing
            similar.add_vote(physician_id, feedback_id)
            
            if specialty and specialty not in similar.specialties:
                similar.specialties.append(specialty)
            
            if tags:
                for tag in tags:
                    if tag not in similar.tags:
                        similar.tags.append(tag)
            
            self._merged_count += 1
            logger.info(f"Merged suggestion into {similar.suggestion_id} (votes: {similar.vote_count})")
            
            # Re-prioritize
            if self._auto_prioritize:
                self._update_priority(similar)
            
            return similar
        
        # Create new suggestion
        suggestion = FeatureSuggestion(
            tenant_id=tenant_id,
            source_feedback_ids=[feedback_id],
            physician_ids=[physician_id],
            category=category,
            title=title,
            description=description,
            use_case=use_case,
            expected_benefit=expected_benefit,
            tags=tags or [],
            specialties=[specialty] if specialty else [],
        )
        
        self._suggestions[suggestion.suggestion_id] = suggestion
        
        if self._auto_prioritize:
            self._update_priority(suggestion)
        
        logger.info(f"Created new suggestion: {suggestion.suggestion_id} - {title}")
        
        return suggestion
    
    def _find_similar(
        self,
        title: str,
        description: str,
        category: SuggestionCategory,
    ) -> Optional[FeatureSuggestion]:
        """Find similar existing suggestion."""
        for suggestion in self._suggestions.values():
            if suggestion.category != category:
                continue
            
            if suggestion.status in [SuggestionStatus.DECLINED, SuggestionStatus.DUPLICATE]:
                continue
            
            # Simple word-based similarity
            similarity = self._calculate_similarity(
                f"{title} {description}",
                f"{suggestion.title} {suggestion.description}",
            )
            
            if similarity >= self._similarity_threshold:
                return suggestion
        
        return None
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity (0-1)."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _update_priority(self, suggestion: FeatureSuggestion) -> None:
        """Update priority based on scoring."""
        score = self._calculate_priority_score(suggestion)
        
        if score >= 0.8:
            suggestion.priority = SuggestionPriority.HIGH
        elif score >= 0.6:
            suggestion.priority = SuggestionPriority.MEDIUM
        elif score >= 0.4:
            suggestion.priority = SuggestionPriority.LOW
        else:
            suggestion.priority = SuggestionPriority.WISHLIST
    
    def _calculate_priority_score(self, suggestion: FeatureSuggestion) -> float:
        """Calculate priority score (0-1)."""
        score = 0.0
        
        # Vote count (logarithmic, max at 10 votes)
        import math
        vote_score = min(1.0, math.log10(suggestion.vote_count + 1) / math.log10(11))
        score += vote_score * self._priority_weights["vote_count"]
        
        # Impact
        impact_scores = {"High": 1.0, "Medium": 0.6, "Low": 0.3}
        impact_score = impact_scores.get(suggestion.estimated_impact, 0.5)
        score += impact_score * self._priority_weights["impact"]
        
        # Effort (inverse - smaller effort = higher score)
        effort_scores = {"XS": 1.0, "S": 0.8, "M": 0.5, "L": 0.3, "XL": 0.1}
        effort_score = effort_scores.get(suggestion.estimated_effort, 0.5)
        score += effort_score * self._priority_weights["effort"]
        
        # Category weight
        category_weight = self._category_weights.get(suggestion.category, 1.0)
        score += (category_weight - 0.8) / 0.4 * self._priority_weights["category_weight"]
        
        return min(1.0, max(0.0, score))
    
    # =========================================================================
    # Triage
    # =========================================================================
    
    def triage(
        self,
        suggestion_id: str,
        triaged_by: str,
        estimated_effort: str,
        estimated_impact: str,
        notes: str = "",
        tags: Optional[List[str]] = None,
    ) -> Optional[FeatureSuggestion]:
        """
        Triage a suggestion.
        
        Sets effort/impact estimates and re-prioritizes.
        """
        if suggestion_id not in self._suggestions:
            return None
        
        suggestion = self._suggestions[suggestion_id]
        suggestion.status = SuggestionStatus.TRIAGED
        suggestion.triaged_by = triaged_by
        suggestion.estimated_effort = estimated_effort
        suggestion.estimated_impact = estimated_impact
        suggestion.triage_notes = notes
        suggestion.updated_at = datetime.now()
        
        if tags:
            for tag in tags:
                if tag not in suggestion.tags:
                    suggestion.tags.append(tag)
        
        # Re-prioritize with new info
        self._update_priority(suggestion)
        
        logger.info(f"Triaged suggestion {suggestion_id}: {estimated_effort}/{estimated_impact}")
        
        return suggestion
    
    def accept(
        self,
        suggestion_id: str,
        linked_issue: str = "",
    ) -> Optional[FeatureSuggestion]:
        """Accept suggestion for development."""
        if suggestion_id not in self._suggestions:
            return None
        
        suggestion = self._suggestions[suggestion_id]
        suggestion.status = SuggestionStatus.ACCEPTED
        suggestion.linked_issue = linked_issue
        suggestion.updated_at = datetime.now()
        
        return suggestion
    
    def decline(
        self,
        suggestion_id: str,
        reason: str = "",
    ) -> Optional[FeatureSuggestion]:
        """Decline a suggestion."""
        if suggestion_id not in self._suggestions:
            return None
        
        suggestion = self._suggestions[suggestion_id]
        suggestion.status = SuggestionStatus.DECLINED
        suggestion.triage_notes = f"{suggestion.triage_notes}\nDeclined: {reason}".strip()
        suggestion.updated_at = datetime.now()
        
        return suggestion
    
    def mark_released(
        self,
        suggestion_id: str,
        release_version: str,
    ) -> Optional[FeatureSuggestion]:
        """Mark suggestion as released."""
        if suggestion_id not in self._suggestions:
            return None
        
        suggestion = self._suggestions[suggestion_id]
        suggestion.status = SuggestionStatus.RELEASED
        suggestion.release_version = release_version
        suggestion.released_at = datetime.now()
        suggestion.updated_at = datetime.now()
        
        return suggestion
    
    # =========================================================================
    # Queries
    # =========================================================================
    
    def get_suggestion(self, suggestion_id: str) -> Optional[FeatureSuggestion]:
        """Get suggestion by ID."""
        return self._suggestions.get(suggestion_id)
    
    def get_by_status(self, status: SuggestionStatus) -> List[FeatureSuggestion]:
        """Get suggestions by status."""
        return [s for s in self._suggestions.values() if s.status == status]
    
    def get_by_category(self, category: SuggestionCategory) -> List[FeatureSuggestion]:
        """Get suggestions by category."""
        return [s for s in self._suggestions.values() if s.category == category]
    
    def get_top_voted(self, limit: int = 10) -> List[FeatureSuggestion]:
        """Get top voted suggestions."""
        suggestions = list(self._suggestions.values())
        suggestions.sort(key=lambda s: s.vote_count, reverse=True)
        return suggestions[:limit]
    
    def get_prioritized_backlog(self, limit: int = 50) -> List[FeatureSuggestion]:
        """
        Get prioritized backlog.
        
        Returns suggestions sorted by priority score.
        """
        actionable = [s for s in self._suggestions.values() if s.is_actionable()]
        
        # Sort by priority then by score
        priority_order = {
            SuggestionPriority.CRITICAL: 0,
            SuggestionPriority.HIGH: 1,
            SuggestionPriority.MEDIUM: 2,
            SuggestionPriority.LOW: 3,
            SuggestionPriority.WISHLIST: 4,
        }
        
        actionable.sort(
            key=lambda s: (
                priority_order.get(s.priority, 5),
                -s.vote_count,
                s.created_at,
            )
        )
        
        return actionable[:limit]
    
    # =========================================================================
    # Export
    # =========================================================================
    
    def export_to_jira_format(
        self,
        only_accepted: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Export suggestions to JIRA-compatible format.
        
        Can be used to bulk create JIRA issues.
        """
        suggestions = (
            self.get_by_status(SuggestionStatus.ACCEPTED)
            if only_accepted
            else list(self._suggestions.values())
        )
        
        priority_map = {
            SuggestionPriority.CRITICAL: "Highest",
            SuggestionPriority.HIGH: "High",
            SuggestionPriority.MEDIUM: "Medium",
            SuggestionPriority.LOW: "Low",
            SuggestionPriority.WISHLIST: "Lowest",
        }
        
        return [
            {
                "project": "PHOENIX",
                "issuetype": "Story",
                "summary": s.title,
                "description": (
                    f"{s.description}\n\n"
                    f"*Use Case:* {s.use_case}\n\n"
                    f"*Expected Benefit:* {s.expected_benefit}\n\n"
                    f"*Physician Votes:* {s.vote_count}\n"
                    f"*Specialties:* {', '.join(s.specialties)}\n\n"
                    f"_From Phoenix Guardian pilot feedback_"
                ),
                "priority": priority_map.get(s.priority, "Medium"),
                "labels": ["pilot-feedback", s.category.value] + s.tags,
                "customfield_effort": s.estimated_effort,
                "customfield_impact": s.estimated_impact,
                "customfield_physician_votes": s.vote_count,
            }
            for s in suggestions
        ]
    
    def export_to_csv(self) -> str:
        """Export suggestions to CSV format."""
        lines = [
            "suggestion_id,title,category,priority,status,vote_count,effort,impact,created_at"
        ]
        
        for s in self._suggestions.values():
            lines.append(
                f'"{s.suggestion_id}","{s.title}","{s.category.value}",'
                f'"{s.priority.value}","{s.status.value}",{s.vote_count},'
                f'"{s.estimated_effort}","{s.estimated_impact}","{s.created_at.isoformat()}"'
            )
        
        return "\n".join(lines)
    
    # =========================================================================
    # Stats
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        suggestions = list(self._suggestions.values())
        
        by_status = {}
        for s in suggestions:
            key = s.status.value
            by_status[key] = by_status.get(key, 0) + 1
        
        by_category = {}
        for s in suggestions:
            key = s.category.value
            by_category[key] = by_category.get(key, 0) + 1
        
        return {
            "total_processed": self._total_processed,
            "unique_suggestions": len(self._suggestions),
            "merged_count": self._merged_count,
            "merge_rate": (
                self._merged_count / self._total_processed
                if self._total_processed > 0 else 0.0
            ),
            "by_status": by_status,
            "by_category": by_category,
            "total_votes": sum(s.vote_count for s in suggestions),
            "avg_votes_per_suggestion": (
                sum(s.vote_count for s in suggestions) / len(suggestions)
                if suggestions else 0.0
            ),
        }
