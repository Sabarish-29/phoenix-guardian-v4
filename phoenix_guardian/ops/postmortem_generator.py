"""
Phoenix Guardian - Postmortem Generator
Automated postmortem document generation from incidents.

Creates structured RCA documents for learning and compliance.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class PostmortemSection(Enum):
    """Sections of a postmortem document."""
    SUMMARY = "summary"
    TIMELINE = "timeline"
    ROOT_CAUSE = "root_cause"
    IMPACT = "impact"
    DETECTION = "detection"
    RESPONSE = "response"
    RESOLUTION = "resolution"
    LESSONS_LEARNED = "lessons_learned"
    ACTION_ITEMS = "action_items"
    APPENDIX = "appendix"


class ActionItemStatus(Enum):
    """Status of action items."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WONT_DO = "wont_do"


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class ActionItem:
    """
    An action item from a postmortem.
    """
    action_id: str = ""
    description: str = ""
    owner: str = ""
    due_date: Optional[datetime] = None
    status: ActionItemStatus = ActionItemStatus.OPEN
    priority: str = "medium"                 # high, medium, low
    category: str = ""                       # prevention, detection, response
    linked_issue: str = ""                   # JIRA/GitHub issue
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action_id": self.action_id,
            "description": self.description,
            "owner": self.owner,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status.value,
            "priority": self.priority,
            "category": self.category,
            "linked_issue": self.linked_issue,
        }


@dataclass
class Postmortem:
    """
    A postmortem document.
    """
    postmortem_id: str = ""
    incident_id: str = ""
    title: str = ""
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""
    reviewed_by: List[str] = field(default_factory=list)
    status: str = "draft"                    # draft, review, published
    
    # Sections
    summary: str = ""
    timeline: str = ""                       # Markdown timeline
    root_cause: str = ""
    impact: str = ""
    detection: str = ""
    response: str = ""
    resolution: str = ""
    lessons_learned: List[str] = field(default_factory=list)
    
    # Action items
    action_items: List[ActionItem] = field(default_factory=list)
    
    # Metrics
    time_to_detect_minutes: float = 0
    time_to_respond_minutes: float = 0
    time_to_resolve_minutes: float = 0
    affected_users: int = 0
    affected_encounters: int = 0
    
    # Links
    incident_link: str = ""
    related_documents: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "postmortem_id": self.postmortem_id,
            "incident_id": self.incident_id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "reviewed_by": self.reviewed_by,
            "status": self.status,
            "summary": self.summary,
            "timeline": self.timeline,
            "root_cause": self.root_cause,
            "impact": self.impact,
            "detection": self.detection,
            "response": self.response,
            "resolution": self.resolution,
            "lessons_learned": self.lessons_learned,
            "action_items": [a.to_dict() for a in self.action_items],
            "metrics": {
                "time_to_detect_minutes": self.time_to_detect_minutes,
                "time_to_respond_minutes": self.time_to_respond_minutes,
                "time_to_resolve_minutes": self.time_to_resolve_minutes,
                "affected_users": self.affected_users,
                "affected_encounters": self.affected_encounters,
            },
            "incident_link": self.incident_link,
            "related_documents": self.related_documents,
        }
    
    def to_markdown(self) -> str:
        """Generate Markdown document."""
        lines = [
            f"# Postmortem: {self.title}",
            "",
            f"**Incident ID:** {self.incident_id}",
            f"**Date:** {self.created_at.strftime('%Y-%m-%d')}",
            f"**Author:** {self.created_by}",
            f"**Status:** {self.status}",
            "",
            "---",
            "",
            "## Summary",
            "",
            self.summary,
            "",
            "## Timeline",
            "",
            self.timeline,
            "",
            "## Root Cause",
            "",
            self.root_cause,
            "",
            "## Impact",
            "",
            self.impact,
            "",
            f"- **Affected Users:** {self.affected_users}",
            f"- **Affected Encounters:** {self.affected_encounters}",
            f"- **Time to Detect:** {self.time_to_detect_minutes:.0f} minutes",
            f"- **Time to Respond:** {self.time_to_respond_minutes:.0f} minutes",
            f"- **Time to Resolve:** {self.time_to_resolve_minutes:.0f} minutes",
            "",
            "## Detection",
            "",
            self.detection,
            "",
            "## Response",
            "",
            self.response,
            "",
            "## Resolution",
            "",
            self.resolution,
            "",
            "## Lessons Learned",
            "",
        ]
        
        for i, lesson in enumerate(self.lessons_learned, 1):
            lines.append(f"{i}. {lesson}")
        
        lines.extend([
            "",
            "## Action Items",
            "",
            "| ID | Description | Owner | Due Date | Priority | Status |",
            "|---|---|---|---|---|---|",
        ])
        
        for item in self.action_items:
            due = item.due_date.strftime('%Y-%m-%d') if item.due_date else "TBD"
            lines.append(
                f"| {item.action_id} | {item.description} | {item.owner} | "
                f"{due} | {item.priority} | {item.status.value} |"
            )
        
        lines.extend([
            "",
            "---",
            "",
            f"*Document generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        ])
        
        return "\n".join(lines)


# ==============================================================================
# Postmortem Generator
# ==============================================================================

class PostmortemGenerator:
    """
    Generates postmortem documents from incidents.
    
    Example:
        from phoenix_guardian.ops.incident_manager import Incident
        
        generator = PostmortemGenerator()
        
        # Generate from incident
        postmortem = generator.generate_from_incident(
            incident=resolved_incident,
            author="sre_engineer_001",
        )
        
        # Add lessons learned
        generator.add_lesson(
            postmortem.postmortem_id,
            "Connection pool exhaustion was not caught by monitoring"
        )
        
        # Add action items
        generator.add_action_item(
            postmortem.postmortem_id,
            ActionItem(
                description="Add connection pool monitoring",
                owner="platform_team",
                due_date=datetime.now() + timedelta(days=14),
                priority="high",
                category="detection",
            )
        )
        
        # Export to Markdown
        markdown = postmortem.to_markdown()
    """
    
    def __init__(self):
        self._postmortems: Dict[str, Postmortem] = {}
        self._action_counter = 0
    
    def generate_from_incident(
        self,
        incident: Any,  # Incident type from incident_manager
        author: str,
    ) -> Postmortem:
        """
        Generate postmortem from resolved incident.
        
        Automatically extracts timeline, metrics, and initial content.
        """
        postmortem_id = f"PM-{incident.incident_id}"
        
        # Extract timeline from incident
        timeline_md = self._format_timeline(incident)
        
        # Calculate metrics
        ttd = 0.0  # Time to detect (from first symptom to alert)
        ttr = 0.0  # Time to respond (from alert to ack)
        ttres = 0.0  # Time to resolve
        
        if hasattr(incident, 'timeline'):
            ttr_delta = incident.timeline.get_time_to_acknowledge()
            if ttr_delta:
                ttr = ttr_delta.total_seconds() / 60
            
            ttres_delta = incident.timeline.get_time_to_resolve()
            if ttres_delta:
                ttres = ttres_delta.total_seconds() / 60
        
        postmortem = Postmortem(
            postmortem_id=postmortem_id,
            incident_id=incident.incident_id,
            title=f"{incident.priority.value} - {incident.title}",
            created_by=author,
            summary=self._generate_summary(incident),
            timeline=timeline_md,
            root_cause=incident.root_cause if hasattr(incident, 'root_cause') else "",
            impact=incident.impact if hasattr(incident, 'impact') else "",
            detection=self._generate_detection_section(incident),
            response=self._generate_response_section(incident),
            resolution=incident.resolution if hasattr(incident, 'resolution') else "",
            lessons_learned=incident.lessons_learned if hasattr(incident, 'lessons_learned') else [],
            time_to_detect_minutes=ttd,
            time_to_respond_minutes=ttr,
            time_to_resolve_minutes=ttres,
            affected_encounters=len(incident.affected_encounters) if hasattr(incident, 'affected_encounters') else 0,
        )
        
        # Convert incident action items
        if hasattr(incident, 'action_items'):
            for i, item_text in enumerate(incident.action_items):
                self._action_counter += 1
                postmortem.action_items.append(ActionItem(
                    action_id=f"AI-{self._action_counter}",
                    description=item_text,
                ))
        
        self._postmortems[postmortem_id] = postmortem
        
        logger.info(f"Generated postmortem {postmortem_id} for incident {incident.incident_id}")
        
        return postmortem
    
    def _format_timeline(self, incident: Any) -> str:
        """Format incident timeline as Markdown."""
        lines = []
        
        if hasattr(incident, 'timeline') and hasattr(incident.timeline, 'events'):
            for event in incident.timeline.events:
                time_str = event.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                lines.append(f"- **{time_str}** - {event.description} ({event.actor})")
        else:
            lines.append("*Timeline not available*")
        
        return "\n".join(lines)
    
    def _generate_summary(self, incident: Any) -> str:
        """Generate summary section."""
        duration = ""
        if hasattr(incident, 'timeline'):
            dur = incident.timeline.get_time_to_resolve()
            if dur:
                hours = dur.total_seconds() / 3600
                duration = f" lasting {hours:.1f} hours"
        
        return (
            f"On {incident.detected_at.strftime('%Y-%m-%d')}, a {incident.priority.value} "
            f"{incident.incident_type.value} incident occurred{duration}. "
            f"{incident.description}"
        )
    
    def _generate_detection_section(self, incident: Any) -> str:
        """Generate detection section."""
        source = incident.source if hasattr(incident, 'source') else "unknown"
        
        if source == "prometheus_alert":
            return "The incident was detected by automated Prometheus alerting."
        elif source == "manual":
            return "The incident was reported manually by the team."
        elif source == "customer":
            return "The incident was reported by a customer/user."
        else:
            return f"The incident was detected via {source}."
    
    def _generate_response_section(self, incident: Any) -> str:
        """Generate response section."""
        lines = []
        
        if hasattr(incident, 'assignee') and incident.assignee:
            lines.append(f"The incident was handled by {incident.assignee}.")
        
        if hasattr(incident, 'escalation_level') and incident.escalation_level > 0:
            lines.append(f"The incident was escalated to level {incident.escalation_level}.")
        
        if not lines:
            lines.append("Response details to be filled in.")
        
        return " ".join(lines)
    
    # =========================================================================
    # Editing
    # =========================================================================
    
    def get_postmortem(self, postmortem_id: str) -> Optional[Postmortem]:
        """Get postmortem by ID."""
        return self._postmortems.get(postmortem_id)
    
    def update_section(
        self,
        postmortem_id: str,
        section: PostmortemSection,
        content: str,
    ) -> Optional[Postmortem]:
        """Update a section of the postmortem."""
        pm = self._postmortems.get(postmortem_id)
        if not pm:
            return None
        
        if section == PostmortemSection.SUMMARY:
            pm.summary = content
        elif section == PostmortemSection.TIMELINE:
            pm.timeline = content
        elif section == PostmortemSection.ROOT_CAUSE:
            pm.root_cause = content
        elif section == PostmortemSection.IMPACT:
            pm.impact = content
        elif section == PostmortemSection.DETECTION:
            pm.detection = content
        elif section == PostmortemSection.RESPONSE:
            pm.response = content
        elif section == PostmortemSection.RESOLUTION:
            pm.resolution = content
        
        return pm
    
    def add_lesson(
        self,
        postmortem_id: str,
        lesson: str,
    ) -> Optional[Postmortem]:
        """Add a lesson learned."""
        pm = self._postmortems.get(postmortem_id)
        if not pm:
            return None
        
        pm.lessons_learned.append(lesson)
        return pm
    
    def add_action_item(
        self,
        postmortem_id: str,
        action_item: ActionItem,
    ) -> Optional[Postmortem]:
        """Add an action item."""
        pm = self._postmortems.get(postmortem_id)
        if not pm:
            return None
        
        if not action_item.action_id:
            self._action_counter += 1
            action_item.action_id = f"AI-{self._action_counter}"
        
        pm.action_items.append(action_item)
        return pm
    
    def update_action_item_status(
        self,
        postmortem_id: str,
        action_id: str,
        status: ActionItemStatus,
        linked_issue: str = "",
    ) -> Optional[ActionItem]:
        """Update action item status."""
        pm = self._postmortems.get(postmortem_id)
        if not pm:
            return None
        
        for item in pm.action_items:
            if item.action_id == action_id:
                item.status = status
                if linked_issue:
                    item.linked_issue = linked_issue
                return item
        
        return None
    
    # =========================================================================
    # Publishing
    # =========================================================================
    
    def submit_for_review(
        self,
        postmortem_id: str,
        reviewers: List[str],
    ) -> Optional[Postmortem]:
        """Submit postmortem for review."""
        pm = self._postmortems.get(postmortem_id)
        if not pm:
            return None
        
        pm.status = "review"
        pm.reviewed_by = reviewers
        
        logger.info(f"Postmortem {postmortem_id} submitted for review to {reviewers}")
        
        return pm
    
    def publish(
        self,
        postmortem_id: str,
    ) -> Optional[Postmortem]:
        """Publish the postmortem."""
        pm = self._postmortems.get(postmortem_id)
        if not pm:
            return None
        
        pm.status = "published"
        
        logger.info(f"Postmortem {postmortem_id} published")
        
        return pm
    
    # =========================================================================
    # Export
    # =========================================================================
    
    def export_markdown(self, postmortem_id: str) -> Optional[str]:
        """Export postmortem as Markdown."""
        pm = self._postmortems.get(postmortem_id)
        if not pm:
            return None
        
        return pm.to_markdown()
    
    def export_json(self, postmortem_id: str) -> Optional[Dict[str, Any]]:
        """Export postmortem as JSON."""
        pm = self._postmortems.get(postmortem_id)
        if not pm:
            return None
        
        return pm.to_dict()
    
    # =========================================================================
    # Stats
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get postmortem statistics."""
        all_pms = list(self._postmortems.values())
        
        # Action item stats
        all_actions = []
        for pm in all_pms:
            all_actions.extend(pm.action_items)
        
        open_actions = len([a for a in all_actions if a.status == ActionItemStatus.OPEN])
        completed_actions = len([a for a in all_actions if a.status == ActionItemStatus.COMPLETED])
        
        # Average metrics
        ttrs = [pm.time_to_resolve_minutes for pm in all_pms if pm.time_to_resolve_minutes > 0]
        avg_ttr = sum(ttrs) / len(ttrs) if ttrs else 0
        
        return {
            "total_postmortems": len(all_pms),
            "by_status": {
                "draft": len([p for p in all_pms if p.status == "draft"]),
                "review": len([p for p in all_pms if p.status == "review"]),
                "published": len([p for p in all_pms if p.status == "published"]),
            },
            "action_items": {
                "total": len(all_actions),
                "open": open_actions,
                "completed": completed_actions,
                "completion_rate": completed_actions / len(all_actions) if all_actions else 0,
            },
            "avg_time_to_resolve_minutes": round(avg_ttr, 1),
        }
