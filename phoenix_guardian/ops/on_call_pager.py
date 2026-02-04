"""
Phoenix Guardian - On-Call Pager
PagerDuty-style alerting for incident response.

Handles alert routing, escalation, and acknowledgment tracking.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"                    # Page immediately
    HIGH = "high"                            # Page with 5 min delay
    WARNING = "warning"                      # Notify, no page
    INFO = "info"                            # Log only


class AlertStatus(Enum):
    """Alert lifecycle status."""
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class OnCallSchedule:
    """
    On-call rotation schedule.
    """
    schedule_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    team: str = ""
    
    # Current on-call
    primary_oncall: str = ""
    secondary_oncall: str = ""
    manager_oncall: str = ""
    
    # Contact info
    contacts: Dict[str, Dict[str, str]] = field(default_factory=dict)
    # e.g., {"engineer_001": {"phone": "+1...", "email": "...", "slack": "@..."}}
    
    # Schedule
    rotation_start: datetime = field(default_factory=datetime.now)
    rotation_duration_hours: int = 168       # 1 week default
    
    def get_primary(self) -> str:
        """Get current primary on-call."""
        return self.primary_oncall
    
    def get_secondary(self) -> str:
        """Get current secondary on-call."""
        return self.secondary_oncall
    
    def get_contact(self, person_id: str, method: str = "phone") -> Optional[str]:
        """Get contact info for a person."""
        if person_id in self.contacts:
            return self.contacts[person_id].get(method)
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "schedule_id": self.schedule_id,
            "team": self.team,
            "primary_oncall": self.primary_oncall,
            "secondary_oncall": self.secondary_oncall,
            "manager_oncall": self.manager_oncall,
            "rotation_start": self.rotation_start.isoformat(),
            "rotation_duration_hours": self.rotation_duration_hours,
        }


@dataclass
class EscalationPolicy:
    """
    Escalation policy for alerts.
    
    Defines escalation chain and timing.
    """
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    
    # Escalation levels (in order)
    # Each level: {"target": "role or person", "delay_minutes": int, "methods": ["phone", "sms", "email"]}
    levels: List[Dict[str, Any]] = field(default_factory=list)
    
    # Repeat settings
    repeat_enabled: bool = True
    repeat_interval_minutes: int = 10
    max_repeats: int = 3
    
    def __post_init__(self):
        """Set defaults if no levels provided."""
        if not self.levels:
            self.levels = [
                {"target": "primary", "delay_minutes": 0, "methods": ["phone", "sms"]},
                {"target": "secondary", "delay_minutes": 5, "methods": ["phone", "sms"]},
                {"target": "manager", "delay_minutes": 15, "methods": ["phone", "sms", "email"]},
            ]
    
    def get_level(self, level_index: int) -> Optional[Dict[str, Any]]:
        """Get escalation level by index."""
        if 0 <= level_index < len(self.levels):
            return self.levels[level_index]
        return None
    
    def get_next_escalation_delay(self, current_level: int) -> Optional[int]:
        """Get delay until next escalation in minutes."""
        if current_level + 1 < len(self.levels):
            return self.levels[current_level + 1]["delay_minutes"]
        return None


@dataclass
class PagerAlert:
    """
    A pager alert.
    """
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Source
    incident_id: str = ""
    tenant_id: str = ""
    
    # Content
    title: str = ""
    message: str = ""
    severity: AlertSeverity = AlertSeverity.HIGH
    status: AlertStatus = AlertStatus.TRIGGERED
    
    # Routing
    escalation_policy_id: str = ""
    current_escalation_level: int = 0
    
    # Timing
    triggered_at: datetime = field(default_factory=datetime.now)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    next_escalation_at: Optional[datetime] = None
    
    # Assignment
    paged_to: List[str] = field(default_factory=list)
    acknowledged_by: str = ""
    
    # Repeat tracking
    repeat_count: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_active(self) -> bool:
        """Check if alert is still active."""
        return self.status in [AlertStatus.TRIGGERED, AlertStatus.ACKNOWLEDGED]
    
    def should_escalate(self) -> bool:
        """Check if alert should escalate."""
        if self.status != AlertStatus.TRIGGERED:
            return False
        if not self.next_escalation_at:
            return False
        return datetime.now() >= self.next_escalation_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "incident_id": self.incident_id,
            "tenant_id": self.tenant_id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "status": self.status.value,
            "current_escalation_level": self.current_escalation_level,
            "triggered_at": self.triggered_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "paged_to": self.paged_to,
            "acknowledged_by": self.acknowledged_by,
            "repeat_count": self.repeat_count,
            "metadata": self.metadata,
        }


# ==============================================================================
# On-Call Pager
# ==============================================================================

class OnCallPager:
    """
    On-call paging system.
    
    Example:
        pager = OnCallPager()
        
        # Set up schedule
        pager.set_schedule(OnCallSchedule(
            team="platform",
            primary_oncall="engineer_001",
            secondary_oncall="engineer_002",
            manager_oncall="manager_001",
            contacts={
                "engineer_001": {"phone": "+1...", "sms": "+1...", "email": "..."},
                ...
            }
        ))
        
        # Send alert
        alert = pager.trigger_alert(
            incident_id="INC-123",
            title="P1: Database down",
            message="Production database unreachable",
            severity=AlertSeverity.CRITICAL,
        )
        
        # Acknowledge
        pager.acknowledge(alert.alert_id, "engineer_001")
        
        # Resolve
        pager.resolve(alert.alert_id)
    """
    
    def __init__(
        self,
        phone_callback: Optional[Callable[[str, str], None]] = None,
        sms_callback: Optional[Callable[[str, str], None]] = None,
        email_callback: Optional[Callable[[str, str, str], None]] = None,
        slack_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self._alerts: Dict[str, PagerAlert] = {}
        self._schedules: Dict[str, OnCallSchedule] = {}
        self._policies: Dict[str, EscalationPolicy] = {}
        
        # Callbacks for actual notifications
        self._phone_callback = phone_callback
        self._sms_callback = sms_callback
        self._email_callback = email_callback
        self._slack_callback = slack_callback
        
        # Default policy
        self._default_policy = EscalationPolicy(name="default")
        self._policies[self._default_policy.policy_id] = self._default_policy
        
        # Stats
        self._total_alerts = 0
        self._acknowledged_count = 0
        self._escalated_count = 0
    
    # =========================================================================
    # Schedule Management
    # =========================================================================
    
    def set_schedule(self, schedule: OnCallSchedule) -> None:
        """Set on-call schedule for a team."""
        self._schedules[schedule.team] = schedule
        logger.info(f"Set schedule for team {schedule.team}: primary={schedule.primary_oncall}")
    
    def get_schedule(self, team: str) -> Optional[OnCallSchedule]:
        """Get schedule for a team."""
        return self._schedules.get(team)
    
    def get_oncall(self, team: str, level: str = "primary") -> Optional[str]:
        """Get current on-call for team."""
        schedule = self._schedules.get(team)
        if not schedule:
            return None
        
        if level == "primary":
            return schedule.primary_oncall
        elif level == "secondary":
            return schedule.secondary_oncall
        elif level == "manager":
            return schedule.manager_oncall
        return None
    
    # =========================================================================
    # Policy Management
    # =========================================================================
    
    def add_policy(self, policy: EscalationPolicy) -> None:
        """Add escalation policy."""
        self._policies[policy.policy_id] = policy
    
    def get_policy(self, policy_id: str) -> Optional[EscalationPolicy]:
        """Get escalation policy."""
        return self._policies.get(policy_id)
    
    # =========================================================================
    # Alert Lifecycle
    # =========================================================================
    
    def trigger_alert(
        self,
        incident_id: str,
        title: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.HIGH,
        tenant_id: str = "",
        team: str = "default",
        policy_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PagerAlert:
        """
        Trigger a pager alert.
        
        Immediately notifies on-call based on escalation policy.
        """
        policy = self._policies.get(policy_id) if policy_id else self._default_policy
        
        alert = PagerAlert(
            incident_id=incident_id,
            tenant_id=tenant_id,
            title=title,
            message=message,
            severity=severity,
            escalation_policy_id=policy.policy_id if policy else "",
            metadata=metadata or {},
        )
        
        # Calculate next escalation time
        if policy:
            next_delay = policy.get_next_escalation_delay(0)
            if next_delay is not None:
                alert.next_escalation_at = alert.triggered_at + timedelta(minutes=next_delay)
        
        self._alerts[alert.alert_id] = alert
        self._total_alerts += 1
        
        logger.info(f"Alert triggered: {alert.alert_id} - {title}")
        
        # Page immediately based on policy level 0
        self._page_level(alert, team, 0)
        
        return alert
    
    def _page_level(
        self,
        alert: PagerAlert,
        team: str,
        level: int,
    ) -> None:
        """Page the specified escalation level."""
        policy = self._policies.get(alert.escalation_policy_id, self._default_policy)
        level_config = policy.get_level(level) if policy else None
        
        if not level_config:
            logger.warning(f"No escalation level {level} for alert {alert.alert_id}")
            return
        
        schedule = self._schedules.get(team)
        
        # Determine who to page
        target = level_config.get("target", "primary")
        person_id = None
        
        if schedule:
            if target == "primary":
                person_id = schedule.primary_oncall
            elif target == "secondary":
                person_id = schedule.secondary_oncall
            elif target == "manager":
                person_id = schedule.manager_oncall
            else:
                person_id = target  # Specific person ID
        else:
            person_id = target
        
        if not person_id:
            logger.warning(f"No on-call found for {target} on team {team}")
            return
        
        # Record who was paged
        if person_id not in alert.paged_to:
            alert.paged_to.append(person_id)
        
        # Send notifications via configured methods
        methods = level_config.get("methods", ["phone", "sms"])
        
        for method in methods:
            self._send_notification(alert, person_id, method, schedule)
        
        logger.info(f"Paged {person_id} via {methods} for alert {alert.alert_id}")
    
    def _send_notification(
        self,
        alert: PagerAlert,
        person_id: str,
        method: str,
        schedule: Optional[OnCallSchedule],
    ) -> None:
        """Send notification via specified method."""
        contact = schedule.get_contact(person_id, method) if schedule else None
        
        message = f"[{alert.severity.value.upper()}] {alert.title}\n{alert.message}"
        
        if method == "phone" and self._phone_callback and contact:
            try:
                self._phone_callback(contact, message)
            except Exception as e:
                logger.error(f"Phone callback failed: {e}")
        
        elif method == "sms" and self._sms_callback and contact:
            try:
                self._sms_callback(contact, message)
            except Exception as e:
                logger.error(f"SMS callback failed: {e}")
        
        elif method == "email" and self._email_callback and contact:
            try:
                self._email_callback(contact, alert.title, message)
            except Exception as e:
                logger.error(f"Email callback failed: {e}")
        
        elif method == "slack" and self._slack_callback and contact:
            try:
                self._slack_callback(contact, message)
            except Exception as e:
                logger.error(f"Slack callback failed: {e}")
    
    def acknowledge(
        self,
        alert_id: str,
        acknowledger: str,
    ) -> Optional[PagerAlert]:
        """
        Acknowledge an alert.
        
        Stops escalation but keeps alert active until resolved.
        """
        alert = self._alerts.get(alert_id)
        if not alert:
            return None
        
        if alert.status != AlertStatus.TRIGGERED:
            logger.warning(f"Cannot acknowledge alert {alert_id} in status {alert.status.value}")
            return alert
        
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now()
        alert.acknowledged_by = acknowledger
        alert.next_escalation_at = None      # Stop escalation
        
        self._acknowledged_count += 1
        
        logger.info(f"Alert {alert_id} acknowledged by {acknowledger}")
        
        return alert
    
    def resolve(self, alert_id: str) -> Optional[PagerAlert]:
        """Resolve an alert."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return None
        
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now()
        alert.next_escalation_at = None
        
        logger.info(f"Alert {alert_id} resolved")
        
        return alert
    
    def suppress(
        self,
        alert_id: str,
        reason: str = "",
    ) -> Optional[PagerAlert]:
        """Suppress an alert (e.g., during maintenance)."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return None
        
        alert.status = AlertStatus.SUPPRESSED
        alert.next_escalation_at = None
        alert.metadata["suppress_reason"] = reason
        
        logger.info(f"Alert {alert_id} suppressed: {reason}")
        
        return alert
    
    def escalate(
        self,
        alert_id: str,
        team: str = "default",
    ) -> Optional[PagerAlert]:
        """Manually escalate an alert."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return None
        
        alert.current_escalation_level += 1
        self._escalated_count += 1
        
        policy = self._policies.get(alert.escalation_policy_id, self._default_policy)
        
        # Check if there's another level
        if policy and alert.current_escalation_level < len(policy.levels):
            self._page_level(alert, team, alert.current_escalation_level)
            
            # Set next escalation
            next_delay = policy.get_next_escalation_delay(alert.current_escalation_level)
            if next_delay is not None:
                alert.next_escalation_at = datetime.now() + timedelta(minutes=next_delay)
        else:
            logger.warning(f"No more escalation levels for alert {alert_id}")
        
        return alert
    
    # =========================================================================
    # Background Processing
    # =========================================================================
    
    def process_escalations(self, team: str = "default") -> List[PagerAlert]:
        """
        Process pending escalations.
        
        Call this periodically (e.g., every minute) to handle escalations.
        """
        escalated = []
        
        for alert in self._alerts.values():
            if alert.should_escalate():
                self.escalate(alert.alert_id, team)
                escalated.append(alert)
        
        return escalated
    
    def process_repeats(self, team: str = "default") -> List[PagerAlert]:
        """
        Process repeat notifications.
        
        Re-pages if alert not acknowledged within repeat interval.
        """
        repeated = []
        
        for alert in self._alerts.values():
            if alert.status != AlertStatus.TRIGGERED:
                continue
            
            policy = self._policies.get(alert.escalation_policy_id, self._default_policy)
            if not policy or not policy.repeat_enabled:
                continue
            
            if alert.repeat_count >= policy.max_repeats:
                continue
            
            # Check if repeat interval has passed
            last_page = alert.triggered_at
            if alert.repeat_count > 0:
                # Calculate when last repeat was
                last_page = alert.triggered_at + timedelta(
                    minutes=policy.repeat_interval_minutes * alert.repeat_count
                )
            
            if datetime.now() >= last_page + timedelta(minutes=policy.repeat_interval_minutes):
                # Re-page current level
                self._page_level(alert, team, alert.current_escalation_level)
                alert.repeat_count += 1
                repeated.append(alert)
        
        return repeated
    
    # =========================================================================
    # Queries
    # =========================================================================
    
    def get_alert(self, alert_id: str) -> Optional[PagerAlert]:
        """Get alert by ID."""
        return self._alerts.get(alert_id)
    
    def get_active_alerts(self) -> List[PagerAlert]:
        """Get all active alerts."""
        return [a for a in self._alerts.values() if a.is_active()]
    
    def get_alerts_for_incident(self, incident_id: str) -> List[PagerAlert]:
        """Get all alerts for an incident."""
        return [a for a in self._alerts.values() if a.incident_id == incident_id]
    
    def get_alerts_for_person(self, person_id: str) -> List[PagerAlert]:
        """Get alerts paged to a person."""
        return [a for a in self._alerts.values() if person_id in a.paged_to and a.is_active()]
    
    # =========================================================================
    # Stats
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pager statistics."""
        all_alerts = list(self._alerts.values())
        active = [a for a in all_alerts if a.is_active()]
        
        # Acknowledgment time stats
        ack_times = []
        for a in all_alerts:
            if a.acknowledged_at and a.triggered_at:
                ack_time = (a.acknowledged_at - a.triggered_at).total_seconds() / 60
                ack_times.append(ack_time)
        
        avg_ack_time = sum(ack_times) / len(ack_times) if ack_times else 0
        
        return {
            "total_alerts": self._total_alerts,
            "active_alerts": len(active),
            "acknowledged_count": self._acknowledged_count,
            "escalated_count": self._escalated_count,
            "avg_ack_time_minutes": round(avg_ack_time, 2),
            "by_severity": {
                s.value: len([a for a in all_alerts if a.severity == s])
                for s in AlertSeverity
            },
        }
