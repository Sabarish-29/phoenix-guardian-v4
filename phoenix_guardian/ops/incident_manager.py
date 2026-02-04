"""
Phoenix Guardian - Incident Manager
Complete incident lifecycle management with P1-P4 SLAs.

Handles incident creation, tracking, escalation, and resolution.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
import uuid

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class IncidentPriority(Enum):
    """Incident priority levels with SLA requirements."""
    P1 = "P1"  # Critical: 15 min response, 1 hour resolution
    P2 = "P2"  # High: 30 min response, 4 hour resolution
    P3 = "P3"  # Medium: 4 hour response, 24 hour resolution
    P4 = "P4"  # Low: 24 hour response, 1 week resolution


class IncidentStatus(Enum):
    """Incident lifecycle status."""
    DETECTED = "detected"                    # Alert triggered
    ACKNOWLEDGED = "acknowledged"            # Someone is looking
    INVESTIGATING = "investigating"          # Active investigation
    IDENTIFIED = "identified"                # Root cause found
    MITIGATING = "mitigating"               # Fix in progress
    RESOLVED = "resolved"                    # Issue fixed
    CLOSED = "closed"                        # Postmortem complete
    
    # Special statuses
    ESCALATED = "escalated"                  # Escalated to higher tier
    FALSE_ALARM = "false_alarm"             # Not a real incident


class IncidentType(Enum):
    """Types of incidents."""
    SECURITY = "security"                    # Security breach/attack
    PERFORMANCE = "performance"              # Latency/throughput issues
    AVAILABILITY = "availability"            # Service down
    DATA_QUALITY = "data_quality"           # Incorrect outputs
    INTEGRATION = "integration"              # External system issues
    COMPLIANCE = "compliance"                # Regulatory concern
    OTHER = "other"


class TimelineEventType(Enum):
    """Types of timeline events."""
    CREATED = "created"
    STATUS_CHANGE = "status_change"
    PRIORITY_CHANGE = "priority_change"
    ASSIGNEE_CHANGE = "assignee_change"
    COMMENT = "comment"
    ESCALATION = "escalation"
    MITIGATION_STARTED = "mitigation_started"
    MITIGATION_COMPLETED = "mitigation_completed"
    ROOT_CAUSE_IDENTIFIED = "root_cause_identified"
    CUSTOMER_COMMUNICATED = "customer_communicated"
    RESOLVED = "resolved"
    CLOSED = "closed"


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class TimelineEvent:
    """A single event in the incident timeline."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    event_type: TimelineEventType = TimelineEventType.COMMENT
    timestamp: datetime = field(default_factory=datetime.now)
    actor: str = ""                          # Who performed action
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "description": self.description,
            "metadata": self.metadata,
        }


@dataclass
class IncidentTimeline:
    """Complete timeline of an incident."""
    incident_id: str
    events: List[TimelineEvent] = field(default_factory=list)
    
    def add_event(
        self,
        event_type: TimelineEventType,
        actor: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TimelineEvent:
        """Add event to timeline."""
        event = TimelineEvent(
            event_type=event_type,
            actor=actor,
            description=description,
            metadata=metadata or {},
        )
        self.events.append(event)
        return event
    
    def get_duration(self) -> Optional[timedelta]:
        """Get incident duration (first to last event)."""
        if len(self.events) < 2:
            return None
        
        timestamps = [e.timestamp for e in self.events]
        return max(timestamps) - min(timestamps)
    
    def get_time_to_acknowledge(self) -> Optional[timedelta]:
        """Get time from detection to acknowledgment."""
        created = next((e for e in self.events if e.event_type == TimelineEventType.CREATED), None)
        acked = next((e for e in self.events if e.event_type == TimelineEventType.STATUS_CHANGE 
                      and e.metadata.get("new_status") == "acknowledged"), None)
        
        if created and acked:
            return acked.timestamp - created.timestamp
        return None
    
    def get_time_to_resolve(self) -> Optional[timedelta]:
        """Get time from detection to resolution."""
        created = next((e for e in self.events if e.event_type == TimelineEventType.CREATED), None)
        resolved = next((e for e in self.events if e.event_type == TimelineEventType.RESOLVED), None)
        
        if created and resolved:
            return resolved.timestamp - created.timestamp
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "incident_id": self.incident_id,
            "events": [e.to_dict() for e in self.events],
            "duration_seconds": self.get_duration().total_seconds() if self.get_duration() else None,
        }


@dataclass
class Incident:
    """
    A production incident with full lifecycle tracking.
    
    Includes SLA tracking, escalation, and resolution management.
    """
    # Identity
    incident_id: str = field(default_factory=lambda: f"INC-{str(uuid.uuid4())[:8].upper()}")
    tenant_id: str = ""
    
    # Classification
    priority: IncidentPriority = IncidentPriority.P3
    incident_type: IncidentType = IncidentType.OTHER
    status: IncidentStatus = IncidentStatus.DETECTED
    
    # Description
    title: str = ""
    description: str = ""
    impact: str = ""                         # What's affected
    scope: str = ""                          # How many users/encounters
    
    # Assignment
    assignee: str = ""
    team: str = ""
    escalation_level: int = 0                # 0 = primary, 1 = secondary, etc.
    
    # Timing
    detected_at: datetime = field(default_factory=datetime.now)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # SLA
    response_sla_at: Optional[datetime] = None
    resolution_sla_at: Optional[datetime] = None
    sla_breached: bool = False
    
    # Resolution
    root_cause: str = ""
    resolution: str = ""
    lessons_learned: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    
    # Related
    related_alerts: List[str] = field(default_factory=list)
    related_incidents: List[str] = field(default_factory=list)
    affected_encounters: List[str] = field(default_factory=list)
    
    # Timeline
    timeline: IncidentTimeline = field(default_factory=lambda: IncidentTimeline(incident_id=""))
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    source: str = ""                         # alert/manual/customer
    
    def __post_init__(self):
        """Initialize after dataclass creation."""
        if not self.timeline.incident_id:
            self.timeline = IncidentTimeline(incident_id=self.incident_id)
        
        # Set SLA deadlines
        if not self.response_sla_at:
            self.response_sla_at = self._calculate_response_sla()
        if not self.resolution_sla_at:
            self.resolution_sla_at = self._calculate_resolution_sla()
    
    def _calculate_response_sla(self) -> datetime:
        """Calculate response SLA deadline."""
        sla_minutes = {
            IncidentPriority.P1: 15,
            IncidentPriority.P2: 30,
            IncidentPriority.P3: 240,
            IncidentPriority.P4: 1440,
        }
        return self.detected_at + timedelta(minutes=sla_minutes[self.priority])
    
    def _calculate_resolution_sla(self) -> datetime:
        """Calculate resolution SLA deadline."""
        sla_hours = {
            IncidentPriority.P1: 1,
            IncidentPriority.P2: 4,
            IncidentPriority.P3: 24,
            IncidentPriority.P4: 168,  # 1 week
        }
        return self.detected_at + timedelta(hours=sla_hours[self.priority])
    
    def is_sla_breached(self) -> bool:
        """Check if SLA has been breached."""
        now = datetime.now()
        
        # Response SLA
        if self.status == IncidentStatus.DETECTED:
            if self.response_sla_at and now > self.response_sla_at:
                return True
        
        # Resolution SLA
        if self.status not in [IncidentStatus.RESOLVED, IncidentStatus.CLOSED, IncidentStatus.FALSE_ALARM]:
            if self.resolution_sla_at and now > self.resolution_sla_at:
                return True
        
        return False
    
    def get_time_remaining_response(self) -> Optional[timedelta]:
        """Get time remaining until response SLA breach."""
        if not self.response_sla_at:
            return None
        if self.acknowledged_at:
            return None  # Already acknowledged
        return self.response_sla_at - datetime.now()
    
    def get_time_remaining_resolution(self) -> Optional[timedelta]:
        """Get time remaining until resolution SLA breach."""
        if not self.resolution_sla_at:
            return None
        if self.resolved_at:
            return None  # Already resolved
        return self.resolution_sla_at - datetime.now()
    
    def is_active(self) -> bool:
        """Check if incident is still active."""
        return self.status not in [
            IncidentStatus.RESOLVED,
            IncidentStatus.CLOSED,
            IncidentStatus.FALSE_ALARM,
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "incident_id": self.incident_id,
            "tenant_id": self.tenant_id,
            "priority": self.priority.value,
            "incident_type": self.incident_type.value,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "impact": self.impact,
            "scope": self.scope,
            "assignee": self.assignee,
            "team": self.team,
            "escalation_level": self.escalation_level,
            "detected_at": self.detected_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "response_sla_at": self.response_sla_at.isoformat() if self.response_sla_at else None,
            "resolution_sla_at": self.resolution_sla_at.isoformat() if self.resolution_sla_at else None,
            "sla_breached": self.sla_breached or self.is_sla_breached(),
            "root_cause": self.root_cause,
            "resolution": self.resolution,
            "lessons_learned": self.lessons_learned,
            "action_items": self.action_items,
            "related_alerts": self.related_alerts,
            "related_incidents": self.related_incidents,
            "affected_encounters": self.affected_encounters,
            "tags": self.tags,
            "source": self.source,
            "timeline": self.timeline.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Incident":
        """Create from dictionary."""
        incident = cls(
            incident_id=data.get("incident_id", f"INC-{str(uuid.uuid4())[:8].upper()}"),
            tenant_id=data.get("tenant_id", ""),
            priority=IncidentPriority(data.get("priority", "P3")),
            incident_type=IncidentType(data.get("incident_type", "other")),
            status=IncidentStatus(data.get("status", "detected")),
            title=data.get("title", ""),
            description=data.get("description", ""),
            impact=data.get("impact", ""),
            scope=data.get("scope", ""),
            assignee=data.get("assignee", ""),
            team=data.get("team", ""),
            escalation_level=data.get("escalation_level", 0),
            detected_at=datetime.fromisoformat(data["detected_at"]) if "detected_at" in data else datetime.now(),
            acknowledged_at=datetime.fromisoformat(data["acknowledged_at"]) if data.get("acknowledged_at") else None,
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
            root_cause=data.get("root_cause", ""),
            resolution=data.get("resolution", ""),
            lessons_learned=data.get("lessons_learned", []),
            action_items=data.get("action_items", []),
            related_alerts=data.get("related_alerts", []),
            related_incidents=data.get("related_incidents", []),
            affected_encounters=data.get("affected_encounters", []),
            tags=data.get("tags", []),
            source=data.get("source", ""),
        )
        return incident


# ==============================================================================
# Incident Manager
# ==============================================================================

class IncidentManager:
    """
    Manages incident lifecycle from detection to closure.
    
    Example:
        manager = IncidentManager(
            pager_callback=pager.send_alert,
            slack_callback=slack.post_incident,
        )
        
        # Create incident from alert
        incident = manager.create_incident(
            tenant_id="pilot_hospital_001",
            title="High latency on AI Scribe",
            priority=IncidentPriority.P2,
            incident_type=IncidentType.PERFORMANCE,
            description="P95 latency > 500ms for past 5 minutes",
            impact="AI Scribe responses delayed",
            source="prometheus_alert",
        )
        
        # Acknowledge
        manager.acknowledge(incident.incident_id, assignee="oncall_engineer_001")
        
        # Update status
        manager.update_status(
            incident.incident_id,
            status=IncidentStatus.INVESTIGATING,
            actor="oncall_engineer_001",
            comment="Investigating database connection pool"
        )
        
        # Resolve
        manager.resolve(
            incident.incident_id,
            actor="oncall_engineer_001",
            root_cause="Database connection leak in scribe service",
            resolution="Deployed connection pool fix"
        )
    """
    
    # SLA thresholds (minutes for response, hours for resolution)
    SLA_RESPONSE = {
        IncidentPriority.P1: 15,
        IncidentPriority.P2: 30,
        IncidentPriority.P3: 240,
        IncidentPriority.P4: 1440,
    }
    
    SLA_RESOLUTION = {
        IncidentPriority.P1: 1,
        IncidentPriority.P2: 4,
        IncidentPriority.P3: 24,
        IncidentPriority.P4: 168,
    }
    
    def __init__(
        self,
        pager_callback: Optional[Callable[[Incident], None]] = None,
        slack_callback: Optional[Callable[[Incident, str], None]] = None,
        storage_backend: Optional[Any] = None,
    ):
        self._incidents: Dict[str, Incident] = {}
        self._pager_callback = pager_callback
        self._slack_callback = slack_callback
        self._storage = storage_backend
        
        # Stats
        self._total_incidents = 0
        self._sla_breaches = 0
    
    # =========================================================================
    # Incident Creation
    # =========================================================================
    
    def create_incident(
        self,
        tenant_id: str,
        title: str,
        priority: IncidentPriority,
        incident_type: IncidentType,
        description: str = "",
        impact: str = "",
        scope: str = "",
        source: str = "manual",
        related_alerts: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> Incident:
        """
        Create a new incident.
        
        Automatically pages on-call for P1/P2.
        """
        incident = Incident(
            tenant_id=tenant_id,
            title=title,
            priority=priority,
            incident_type=incident_type,
            description=description,
            impact=impact,
            scope=scope,
            source=source,
            related_alerts=related_alerts or [],
            tags=tags or [],
        )
        
        # Add creation event to timeline
        incident.timeline.add_event(
            event_type=TimelineEventType.CREATED,
            actor="system",
            description=f"Incident created: {title}",
            metadata={"priority": priority.value, "type": incident_type.value},
        )
        
        self._incidents[incident.incident_id] = incident
        self._total_incidents += 1
        
        logger.info(f"Created {priority.value} incident: {incident.incident_id} - {title}")
        
        # Page on-call for P1/P2
        if priority in [IncidentPriority.P1, IncidentPriority.P2]:
            self._trigger_pager(incident)
        
        # Post to Slack
        self._notify_slack(incident, f"🚨 New {priority.value} Incident: {title}")
        
        return incident
    
    def create_from_alert(
        self,
        tenant_id: str,
        alert_name: str,
        alert_severity: str,
        alert_description: str,
        alert_id: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> Incident:
        """
        Create incident from Prometheus/Grafana alert.
        """
        # Map alert severity to priority
        priority_map = {
            "critical": IncidentPriority.P1,
            "high": IncidentPriority.P2,
            "warning": IncidentPriority.P3,
            "info": IncidentPriority.P4,
        }
        priority = priority_map.get(alert_severity.lower(), IncidentPriority.P3)
        
        # Infer incident type from labels
        incident_type = IncidentType.OTHER
        if labels:
            if "security" in str(labels.values()).lower():
                incident_type = IncidentType.SECURITY
            elif "latency" in str(labels.values()).lower() or "performance" in str(labels.values()).lower():
                incident_type = IncidentType.PERFORMANCE
            elif "error" in str(labels.values()).lower() or "down" in str(labels.values()).lower():
                incident_type = IncidentType.AVAILABILITY
        
        return self.create_incident(
            tenant_id=tenant_id,
            title=f"[Alert] {alert_name}",
            priority=priority,
            incident_type=incident_type,
            description=alert_description,
            source="prometheus_alert",
            related_alerts=[alert_id],
            tags=list(labels.keys()) if labels else [],
        )
    
    # =========================================================================
    # Status Updates
    # =========================================================================
    
    def acknowledge(
        self,
        incident_id: str,
        assignee: str,
        team: str = "",
        comment: str = "",
    ) -> Optional[Incident]:
        """
        Acknowledge an incident.
        
        Stops the response SLA timer.
        """
        incident = self._incidents.get(incident_id)
        if not incident:
            return None
        
        incident.status = IncidentStatus.ACKNOWLEDGED
        incident.acknowledged_at = datetime.now()
        incident.assignee = assignee
        if team:
            incident.team = team
        
        incident.timeline.add_event(
            event_type=TimelineEventType.STATUS_CHANGE,
            actor=assignee,
            description=f"Incident acknowledged by {assignee}" + (f": {comment}" if comment else ""),
            metadata={"new_status": "acknowledged"},
        )
        
        logger.info(f"Incident {incident_id} acknowledged by {assignee}")
        self._notify_slack(incident, f"✅ Acknowledged by {assignee}")
        
        return incident
    
    def update_status(
        self,
        incident_id: str,
        status: IncidentStatus,
        actor: str,
        comment: str = "",
    ) -> Optional[Incident]:
        """Update incident status."""
        incident = self._incidents.get(incident_id)
        if not incident:
            return None
        
        old_status = incident.status
        incident.status = status
        
        incident.timeline.add_event(
            event_type=TimelineEventType.STATUS_CHANGE,
            actor=actor,
            description=f"Status changed from {old_status.value} to {status.value}" + (f": {comment}" if comment else ""),
            metadata={"old_status": old_status.value, "new_status": status.value},
        )
        
        logger.info(f"Incident {incident_id} status: {old_status.value} -> {status.value}")
        
        return incident
    
    def escalate(
        self,
        incident_id: str,
        actor: str,
        reason: str = "",
    ) -> Optional[Incident]:
        """Escalate incident to next level."""
        incident = self._incidents.get(incident_id)
        if not incident:
            return None
        
        incident.escalation_level += 1
        incident.status = IncidentStatus.ESCALATED
        
        incident.timeline.add_event(
            event_type=TimelineEventType.ESCALATION,
            actor=actor,
            description=f"Escalated to level {incident.escalation_level}" + (f": {reason}" if reason else ""),
            metadata={"level": incident.escalation_level},
        )
        
        logger.info(f"Incident {incident_id} escalated to level {incident.escalation_level}")
        
        # Trigger pager for escalation
        self._trigger_pager(incident)
        self._notify_slack(incident, f"⬆️ Escalated to level {incident.escalation_level}: {reason}")
        
        return incident
    
    def add_comment(
        self,
        incident_id: str,
        actor: str,
        comment: str,
    ) -> Optional[Incident]:
        """Add comment to incident timeline."""
        incident = self._incidents.get(incident_id)
        if not incident:
            return None
        
        incident.timeline.add_event(
            event_type=TimelineEventType.COMMENT,
            actor=actor,
            description=comment,
        )
        
        return incident
    
    def update_assignee(
        self,
        incident_id: str,
        new_assignee: str,
        actor: str,
        reason: str = "",
    ) -> Optional[Incident]:
        """Reassign incident."""
        incident = self._incidents.get(incident_id)
        if not incident:
            return None
        
        old_assignee = incident.assignee
        incident.assignee = new_assignee
        
        incident.timeline.add_event(
            event_type=TimelineEventType.ASSIGNEE_CHANGE,
            actor=actor,
            description=f"Reassigned from {old_assignee} to {new_assignee}" + (f": {reason}" if reason else ""),
            metadata={"old_assignee": old_assignee, "new_assignee": new_assignee},
        )
        
        return incident
    
    # =========================================================================
    # Resolution
    # =========================================================================
    
    def resolve(
        self,
        incident_id: str,
        actor: str,
        root_cause: str,
        resolution: str,
        lessons_learned: Optional[List[str]] = None,
        action_items: Optional[List[str]] = None,
    ) -> Optional[Incident]:
        """
        Resolve an incident.
        
        Records root cause and resolution for postmortem.
        """
        incident = self._incidents.get(incident_id)
        if not incident:
            return None
        
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now()
        incident.root_cause = root_cause
        incident.resolution = resolution
        incident.lessons_learned = lessons_learned or []
        incident.action_items = action_items or []
        
        # Check if SLA was breached
        incident.sla_breached = incident.is_sla_breached()
        if incident.sla_breached:
            self._sla_breaches += 1
        
        incident.timeline.add_event(
            event_type=TimelineEventType.RESOLVED,
            actor=actor,
            description=f"Incident resolved: {resolution}",
            metadata={
                "root_cause": root_cause,
                "sla_breached": incident.sla_breached,
            },
        )
        
        # Calculate metrics
        duration = incident.timeline.get_time_to_resolve()
        duration_str = str(duration).split('.')[0] if duration else "unknown"
        
        logger.info(f"Incident {incident_id} resolved in {duration_str}")
        self._notify_slack(incident, f"✅ Resolved in {duration_str}: {resolution}")
        
        return incident
    
    def close(
        self,
        incident_id: str,
        actor: str,
        notes: str = "",
    ) -> Optional[Incident]:
        """
        Close an incident after postmortem.
        """
        incident = self._incidents.get(incident_id)
        if not incident:
            return None
        
        if incident.status != IncidentStatus.RESOLVED:
            logger.warning(f"Closing non-resolved incident {incident_id}")
        
        incident.status = IncidentStatus.CLOSED
        incident.closed_at = datetime.now()
        
        incident.timeline.add_event(
            event_type=TimelineEventType.CLOSED,
            actor=actor,
            description=f"Incident closed" + (f": {notes}" if notes else ""),
        )
        
        logger.info(f"Incident {incident_id} closed")
        
        return incident
    
    def mark_false_alarm(
        self,
        incident_id: str,
        actor: str,
        reason: str = "",
    ) -> Optional[Incident]:
        """Mark incident as false alarm."""
        incident = self._incidents.get(incident_id)
        if not incident:
            return None
        
        incident.status = IncidentStatus.FALSE_ALARM
        incident.resolved_at = datetime.now()
        
        incident.timeline.add_event(
            event_type=TimelineEventType.STATUS_CHANGE,
            actor=actor,
            description=f"Marked as false alarm" + (f": {reason}" if reason else ""),
            metadata={"new_status": "false_alarm"},
        )
        
        logger.info(f"Incident {incident_id} marked as false alarm")
        
        return incident
    
    # =========================================================================
    # Queries
    # =========================================================================
    
    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get incident by ID."""
        return self._incidents.get(incident_id)
    
    def get_active_incidents(
        self,
        tenant_id: Optional[str] = None,
        priority: Optional[IncidentPriority] = None,
    ) -> List[Incident]:
        """Get all active incidents."""
        incidents = [i for i in self._incidents.values() if i.is_active()]
        
        if tenant_id:
            incidents = [i for i in incidents if i.tenant_id == tenant_id]
        
        if priority:
            incidents = [i for i in incidents if i.priority == priority]
        
        # Sort by priority then age
        priority_order = {
            IncidentPriority.P1: 0,
            IncidentPriority.P2: 1,
            IncidentPriority.P3: 2,
            IncidentPriority.P4: 3,
        }
        incidents.sort(key=lambda i: (priority_order.get(i.priority, 4), i.detected_at))
        
        return incidents
    
    def get_sla_breaching(self) -> List[Incident]:
        """Get incidents currently breaching or about to breach SLA."""
        return [i for i in self._incidents.values() if i.is_active() and i.is_sla_breached()]
    
    def get_by_assignee(self, assignee: str) -> List[Incident]:
        """Get incidents assigned to a person."""
        return [i for i in self._incidents.values() if i.assignee == assignee and i.is_active()]
    
    def get_recent(self, days: int = 7) -> List[Incident]:
        """Get recent incidents."""
        cutoff = datetime.now() - timedelta(days=days)
        return [i for i in self._incidents.values() if i.detected_at >= cutoff]
    
    # =========================================================================
    # Callbacks
    # =========================================================================
    
    def _trigger_pager(self, incident: Incident) -> None:
        """Trigger pager for incident."""
        if self._pager_callback:
            try:
                self._pager_callback(incident)
            except Exception as e:
                logger.error(f"Pager callback failed: {e}")
    
    def _notify_slack(self, incident: Incident, message: str) -> None:
        """Send Slack notification."""
        if self._slack_callback:
            try:
                self._slack_callback(incident, message)
            except Exception as e:
                logger.error(f"Slack callback failed: {e}")
    
    # =========================================================================
    # Reporting
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get incident statistics."""
        all_incidents = list(self._incidents.values())
        active = [i for i in all_incidents if i.is_active()]
        resolved = [i for i in all_incidents if i.status == IncidentStatus.RESOLVED]
        
        # By priority
        by_priority = {}
        for p in IncidentPriority:
            by_priority[p.value] = len([i for i in all_incidents if i.priority == p])
        
        # By type
        by_type = {}
        for t in IncidentType:
            by_type[t.value] = len([i for i in all_incidents if i.incident_type == t])
        
        # MTTR (Mean Time To Resolve)
        resolution_times = []
        for i in resolved:
            duration = i.timeline.get_time_to_resolve()
            if duration:
                resolution_times.append(duration.total_seconds() / 3600)
        
        mttr = sum(resolution_times) / len(resolution_times) if resolution_times else 0
        
        return {
            "total_incidents": self._total_incidents,
            "active_count": len(active),
            "resolved_count": len(resolved),
            "sla_breaches": self._sla_breaches,
            "sla_breach_rate": self._sla_breaches / self._total_incidents if self._total_incidents > 0 else 0,
            "by_priority": by_priority,
            "by_type": by_type,
            "mttr_hours": round(mttr, 2),
        }
    
    def generate_weekly_report(self) -> Dict[str, Any]:
        """Generate weekly incident report."""
        week_ago = datetime.now() - timedelta(days=7)
        weekly = [i for i in self._incidents.values() if i.detected_at >= week_ago]
        
        return {
            "period": {
                "start": week_ago.isoformat(),
                "end": datetime.now().isoformat(),
            },
            "total_incidents": len(weekly),
            "by_priority": {
                p.value: len([i for i in weekly if i.priority == p])
                for p in IncidentPriority
            },
            "resolved": len([i for i in weekly if i.status == IncidentStatus.RESOLVED]),
            "active": len([i for i in weekly if i.is_active()]),
            "sla_breaches": len([i for i in weekly if i.sla_breached]),
            "false_alarms": len([i for i in weekly if i.status == IncidentStatus.FALSE_ALARM]),
        }
