"""
Tests for Phoenix Guardian Ops Module
Week 19-20: Incident Management & Operations Tests

Tests incident management, on-call paging, and postmortem generation.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
import json

from phoenix_guardian.ops.incident_manager import (
    Incident,
    IncidentPriority,
    IncidentStatus,
    IncidentManager,
    IncidentTimeline,
    TimelineEvent,
    IncidentType,
    TimelineEventType,
)
from phoenix_guardian.ops.on_call_pager import (
    OnCallPager,
    PagerAlert,
    EscalationPolicy,
    OnCallSchedule,
    AlertStatus,
    AlertSeverity,
)
from phoenix_guardian.ops.postmortem_generator import (
    PostmortemGenerator,
    Postmortem,
    ActionItem,
    ActionItemStatus,
    PostmortemSection,
)


# ==============================================================================
# Incident Priority Tests
# ==============================================================================

class TestIncidentPriority:
    """Tests for IncidentPriority enum."""
    
    def test_priority_levels_defined(self):
        """Test all priority levels are defined."""
        assert IncidentPriority.P1  # Critical
        assert IncidentPriority.P2  # High
        assert IncidentPriority.P3  # Medium
        assert IncidentPriority.P4  # Low
    
    def test_priority_values(self):
        """Test priority values."""
        assert IncidentPriority.P1.value == "P1"
        assert IncidentPriority.P2.value == "P2"
        assert IncidentPriority.P3.value == "P3"
        assert IncidentPriority.P4.value == "P4"


# ==============================================================================
# Incident Status Tests
# ==============================================================================

class TestIncidentStatus:
    """Tests for IncidentStatus enum."""
    
    def test_status_values(self):
        """Test status values are defined."""
        assert IncidentStatus.DETECTED
        assert IncidentStatus.ACKNOWLEDGED
        assert IncidentStatus.INVESTIGATING
        assert IncidentStatus.IDENTIFIED
        assert IncidentStatus.MITIGATING
        assert IncidentStatus.RESOLVED
        assert IncidentStatus.CLOSED
    
    def test_special_statuses(self):
        """Test special status values."""
        assert IncidentStatus.ESCALATED
        assert IncidentStatus.FALSE_ALARM


# ==============================================================================
# Incident Tests
# ==============================================================================

class TestIncident:
    """Tests for Incident dataclass."""
    
    def test_create_incident(self):
        """Test creating an incident."""
        incident = Incident(
            tenant_id="medsys",
            title="High latency detected",
            description="P95 latency exceeds 500ms",
            priority=IncidentPriority.P2,
            incident_type=IncidentType.PERFORMANCE,
        )
        
        assert incident.incident_id.startswith("INC-")
        assert incident.tenant_id == "medsys"
        assert incident.title == "High latency detected"
        assert incident.priority == IncidentPriority.P2
        assert incident.status == IncidentStatus.DETECTED
    
    def test_incident_with_assignee(self):
        """Test incident with assignee."""
        incident = Incident(
            tenant_id="medsys",
            title="Database connection issue",
            assignee="engineer_001",
            team="platform",
        )
        
        assert incident.assignee == "engineer_001"
        assert incident.team == "platform"
    
    def test_incident_sla_calculation(self):
        """Test SLA deadline calculation."""
        now = datetime.now()
        incident = Incident(
            tenant_id="medsys",
            title="P1 Critical",
            priority=IncidentPriority.P1,
            detected_at=now,
        )
        
        # P1: 15 min response, 1 hour resolution
        assert incident.response_sla_at is not None
        assert incident.resolution_sla_at is not None
        # Response SLA should be ~15 min from detection
        response_delta = (incident.response_sla_at - now).total_seconds()
        assert 14 * 60 <= response_delta <= 16 * 60
    
    def test_incident_is_active(self):
        """Test is_active method."""
        incident = Incident(tenant_id="medsys", title="Active")
        assert incident.is_active() is True
        
        incident.status = IncidentStatus.RESOLVED
        assert incident.is_active() is False
    
    def test_incident_tags(self):
        """Test incident with tags."""
        incident = Incident(
            tenant_id="medsys",
            title="Tagged incident",
            tags=["security", "pilot", "urgent"],
        )
        
        assert len(incident.tags) == 3
        assert "security" in incident.tags
    
    def test_incident_affected_encounters(self):
        """Test tracking affected encounters."""
        incident = Incident(
            tenant_id="medsys",
            title="Encounter impact",
            affected_encounters=["enc-001", "enc-002", "enc-003"],
        )
        
        assert len(incident.affected_encounters) == 3
    
    def test_incident_to_dict(self):
        """Test serialization."""
        incident = Incident(
            tenant_id="medsys",
            title="Serialization test",
            priority=IncidentPriority.P3,
        )
        
        data = incident.to_dict()
        assert data["tenant_id"] == "medsys"
        assert data["title"] == "Serialization test"
        assert data["priority"] == "P3"
        assert "timeline" in data


# ==============================================================================
# Incident Timeline Tests
# ==============================================================================

class TestIncidentTimeline:
    """Tests for IncidentTimeline."""
    
    def test_timeline_creation(self):
        """Test timeline creation."""
        timeline = IncidentTimeline(incident_id="INC-001")
        assert timeline.incident_id == "INC-001"
        assert len(timeline.events) == 0
    
    def test_timeline_add_event(self):
        """Test adding events to timeline."""
        timeline = IncidentTimeline(incident_id="INC-001")
        
        event = timeline.add_event(
            event_type=TimelineEventType.CREATED,
            actor="system",
            description="Incident created from alert",
        )
        
        assert len(timeline.events) == 1
        assert event.event_type == TimelineEventType.CREATED
        assert event.actor == "system"
    
    def test_timeline_chronological_order(self):
        """Test events maintain order."""
        timeline = IncidentTimeline(incident_id="INC-001")
        
        timeline.add_event(TimelineEventType.CREATED, "system", "Created")
        timeline.add_event(TimelineEventType.STATUS_CHANGE, "eng-001", "Acknowledged")
        timeline.add_event(TimelineEventType.COMMENT, "eng-001", "Investigating DB")
        
        assert len(timeline.events) == 3
        assert timeline.events[0].event_type == TimelineEventType.CREATED
        assert timeline.events[2].description == "Investigating DB"


# ==============================================================================
# Timeline Event Tests
# ==============================================================================

class TestTimelineEvent:
    """Tests for TimelineEvent."""
    
    def test_create_event(self):
        """Test creating a timeline event."""
        event = TimelineEvent(
            event_type=TimelineEventType.COMMENT,
            actor="engineer_001",
            description="Starting investigation",
        )
        
        assert event.event_id
        assert event.event_type == TimelineEventType.COMMENT
        assert event.actor == "engineer_001"
    
    def test_event_with_metadata(self):
        """Test event with metadata."""
        event = TimelineEvent(
            event_type=TimelineEventType.STATUS_CHANGE,
            actor="engineer_001",
            description="Status changed",
            metadata={"old_status": "detected", "new_status": "acknowledged"},
        )
        
        assert event.metadata["old_status"] == "detected"
        assert event.metadata["new_status"] == "acknowledged"
    
    def test_event_to_dict(self):
        """Test event serialization."""
        event = TimelineEvent(
            event_type=TimelineEventType.RESOLVED,
            actor="engineer_001",
            description="Issue resolved",
        )
        
        data = event.to_dict()
        assert data["event_type"] == "resolved"
        assert data["actor"] == "engineer_001"


# ==============================================================================
# Incident Manager Tests
# ==============================================================================

class TestIncidentManager:
    """Tests for IncidentManager."""
    
    def test_manager_creation(self):
        """Test manager creation."""
        manager = IncidentManager()
        assert manager is not None
        assert len(manager._incidents) == 0
    
    def test_manager_create_incident(self):
        """Test creating incident through manager."""
        manager = IncidentManager()
        
        incident = manager.create_incident(
            tenant_id="medsys",
            title="High latency",
            priority=IncidentPriority.P2,
            incident_type=IncidentType.PERFORMANCE,
            description="P95 > 500ms",
        )
        
        assert incident.incident_id in manager._incidents
        assert incident.title == "High latency"
    
    def test_manager_acknowledge_incident(self):
        """Test acknowledging an incident."""
        manager = IncidentManager()
        
        incident = manager.create_incident(
            tenant_id="medsys",
            title="Test incident",
            priority=IncidentPriority.P2,
            incident_type=IncidentType.PERFORMANCE,
        )
        
        manager.acknowledge(incident.incident_id, assignee="eng-001")
        
        updated = manager.get_incident(incident.incident_id)
        assert updated.status == IncidentStatus.ACKNOWLEDGED
        assert updated.acknowledged_at is not None
    
    def test_manager_resolve_incident(self):
        """Test resolving an incident."""
        manager = IncidentManager()
        
        incident = manager.create_incident(
            tenant_id="medsys",
            title="Resolvable incident",
            priority=IncidentPriority.P3,
            incident_type=IncidentType.PERFORMANCE,
        )
        
        manager.acknowledge(incident.incident_id, assignee="eng-001")
        manager.resolve(
            incident.incident_id,
            actor="eng-001",
            root_cause="Connection pool exhaustion",
            resolution="Increased pool size",
        )
        
        resolved = manager.get_incident(incident.incident_id)
        assert resolved.status == IncidentStatus.RESOLVED
        assert resolved.root_cause == "Connection pool exhaustion"
    
    def test_manager_get_by_priority(self):
        """Test getting incidents by priority."""
        manager = IncidentManager()
        
        manager.create_incident(
            tenant_id="medsys",
            title="P1 Critical",
            priority=IncidentPriority.P1,
            incident_type=IncidentType.AVAILABILITY,
        )
        manager.create_incident(
            tenant_id="medsys",
            title="P3 Medium",
            priority=IncidentPriority.P3,
            incident_type=IncidentType.PERFORMANCE,
        )
        
        p1_incidents = manager.get_active_incidents(priority=IncidentPriority.P1)
        assert len(p1_incidents) == 1
        assert p1_incidents[0].title == "P1 Critical"
    
    def test_manager_get_active(self):
        """Test getting active incidents."""
        manager = IncidentManager()
        
        inc1 = manager.create_incident(
            tenant_id="medsys",
            title="Active 1",
            priority=IncidentPriority.P2,
            incident_type=IncidentType.PERFORMANCE,
        )
        inc2 = manager.create_incident(
            tenant_id="medsys",
            title="Active 2",
            priority=IncidentPriority.P3,
            incident_type=IncidentType.PERFORMANCE,
        )
        
        manager.acknowledge(inc1.incident_id, "eng-001")
        manager.resolve(inc1.incident_id, "eng-001", "Fixed", "Done")
        
        active = manager.get_active_incidents()
        assert len(active) == 1
        assert active[0].title == "Active 2"
    
    def test_manager_get_by_tenant(self):
        """Test getting incidents by tenant."""
        manager = IncidentManager()
        
        manager.create_incident(
            tenant_id="tenant_a",
            title="Tenant A issue",
            priority=IncidentPriority.P3,
            incident_type=IncidentType.PERFORMANCE,
        )
        manager.create_incident(
            tenant_id="tenant_b",
            title="Tenant B issue",
            priority=IncidentPriority.P3,
            incident_type=IncidentType.PERFORMANCE,
        )
        
        tenant_a = manager.get_active_incidents(tenant_id="tenant_a")
        assert len(tenant_a) == 1
        assert tenant_a[0].tenant_id == "tenant_a"


# ==============================================================================
# Alert Severity Tests
# ==============================================================================

class TestAlertSeverity:
    """Tests for AlertSeverity enum."""
    
    def test_severity_values(self):
        """Test severity levels."""
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertSeverity.HIGH.value == "high"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.INFO.value == "info"


# ==============================================================================
# Alert Status Tests
# ==============================================================================

class TestAlertStatus:
    """Tests for AlertStatus enum."""
    
    def test_status_values(self):
        """Test alert status values."""
        assert AlertStatus.TRIGGERED.value == "triggered"
        assert AlertStatus.ACKNOWLEDGED.value == "acknowledged"
        assert AlertStatus.RESOLVED.value == "resolved"
        assert AlertStatus.SUPPRESSED.value == "suppressed"


# ==============================================================================
# Pager Alert Tests
# ==============================================================================

class TestPagerAlert:
    """Tests for PagerAlert dataclass."""
    
    def test_create_alert(self):
        """Test creating a pager alert."""
        alert = PagerAlert(
            incident_id="INC-001",
            tenant_id="medsys",
            title="P1: Service down",
            message="Production service unreachable",
            severity=AlertSeverity.CRITICAL,
        )
        
        assert alert.alert_id
        assert alert.incident_id == "INC-001"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.TRIGGERED
    
    def test_alert_is_active(self):
        """Test is_active method."""
        alert = PagerAlert(title="Active alert")
        assert alert.is_active() is True
        
        alert.status = AlertStatus.RESOLVED
        assert alert.is_active() is False
    
    def test_alert_to_dict(self):
        """Test alert serialization."""
        alert = PagerAlert(
            incident_id="INC-001",
            title="Test alert",
            severity=AlertSeverity.HIGH,
        )
        
        data = alert.to_dict()
        assert data["incident_id"] == "INC-001"
        assert data["severity"] == "high"


# ==============================================================================
# Escalation Policy Tests
# ==============================================================================

class TestEscalationPolicy:
    """Tests for EscalationPolicy."""
    
    def test_policy_creation(self):
        """Test creating escalation policy."""
        policy = EscalationPolicy(name="default")
        
        assert policy.policy_id
        assert policy.name == "default"
        assert len(policy.levels) > 0  # Has default levels
    
    def test_policy_with_custom_levels(self):
        """Test policy with custom escalation levels."""
        policy = EscalationPolicy(
            name="custom",
            levels=[
                {"target": "primary", "delay_minutes": 0, "methods": ["phone"]},
                {"target": "manager", "delay_minutes": 10, "methods": ["phone", "email"]},
            ],
        )
        
        assert len(policy.levels) == 2
        assert policy.levels[1]["target"] == "manager"
    
    def test_policy_get_level(self):
        """Test getting escalation level."""
        policy = EscalationPolicy(name="test")
        
        level = policy.get_level(0)
        assert level is not None
        assert level["target"] == "primary"
        
        # Invalid level
        assert policy.get_level(100) is None
    
    def test_policy_get_next_delay(self):
        """Test getting next escalation delay."""
        policy = EscalationPolicy(name="test")
        
        delay = policy.get_next_escalation_delay(0)
        assert delay is not None  # Should have next level
        
        # Last level has no next
        last_level = len(policy.levels) - 1
        assert policy.get_next_escalation_delay(last_level) is None


# ==============================================================================
# On-Call Schedule Tests
# ==============================================================================

class TestOnCallSchedule:
    """Tests for OnCallSchedule."""
    
    def test_create_schedule(self):
        """Test creating on-call schedule."""
        schedule = OnCallSchedule(
            team="platform",
            primary_oncall="engineer_001",
            secondary_oncall="engineer_002",
        )
        
        assert schedule.team == "platform"
        assert schedule.primary_oncall == "engineer_001"
    
    def test_schedule_get_primary(self):
        """Test getting primary on-call."""
        schedule = OnCallSchedule(
            team="platform",
            primary_oncall="eng-001",
            secondary_oncall="eng-002",
        )
        
        assert schedule.get_primary() == "eng-001"
        assert schedule.get_secondary() == "eng-002"
    
    def test_schedule_with_contacts(self):
        """Test schedule with contact info."""
        schedule = OnCallSchedule(
            team="platform",
            primary_oncall="eng-001",
            contacts={
                "eng-001": {"phone": "+1234567890", "email": "eng@test.com"},
            },
        )
        
        assert schedule.get_contact("eng-001", "phone") == "+1234567890"
        assert schedule.get_contact("eng-001", "email") == "eng@test.com"
        assert schedule.get_contact("unknown", "phone") is None


# ==============================================================================
# On-Call Pager Tests
# ==============================================================================

class TestOnCallPager:
    """Tests for OnCallPager."""
    
    def test_pager_creation(self):
        """Test pager creation."""
        pager = OnCallPager()
        assert pager is not None
        assert len(pager._alerts) == 0
    
    def test_pager_set_schedule(self):
        """Test setting on-call schedule."""
        pager = OnCallPager()
        
        schedule = OnCallSchedule(
            team="platform",
            primary_oncall="eng-001",
        )
        pager.set_schedule(schedule)
        
        retrieved = pager.get_schedule("platform")
        assert retrieved is not None
        assert retrieved.primary_oncall == "eng-001"
    
    def test_pager_trigger_alert(self):
        """Test triggering an alert."""
        pager = OnCallPager()
        
        schedule = OnCallSchedule(
            team="platform",
            primary_oncall="eng-001",
        )
        pager.set_schedule(schedule)
        
        alert = pager.trigger_alert(
            incident_id="INC-001",
            tenant_id="medsys",
            title="P1: Service down",
            message="Production unreachable",
            severity=AlertSeverity.CRITICAL,
            team="platform",
        )
        
        assert alert.alert_id in pager._alerts
        assert alert.status == AlertStatus.TRIGGERED
    
    def test_pager_acknowledge_alert(self):
        """Test acknowledging an alert."""
        pager = OnCallPager()
        pager.set_schedule(OnCallSchedule(team="platform", primary_oncall="eng-001"))
        
        alert = pager.trigger_alert(
            incident_id="INC-001",
            title="Test alert",
            message="Test message",
            severity=AlertSeverity.HIGH,
            team="platform",
        )
        
        pager.acknowledge(alert.alert_id, acknowledger="eng-001")
        
        updated = pager.get_alert(alert.alert_id)
        assert updated.status == AlertStatus.ACKNOWLEDGED
        assert updated.acknowledged_by == "eng-001"
    
    def test_pager_resolve_alert(self):
        """Test resolving an alert."""
        pager = OnCallPager()
        pager.set_schedule(OnCallSchedule(team="platform", primary_oncall="eng-001"))
        
        alert = pager.trigger_alert(
            incident_id="INC-001",
            title="Resolvable alert",
            message="Test message",
            severity=AlertSeverity.HIGH,
            team="platform",
        )
        
        pager.acknowledge(alert.alert_id, acknowledger="eng-001")
        pager.resolve(alert.alert_id)
        
        resolved = pager.get_alert(alert.alert_id)
        assert resolved.status == AlertStatus.RESOLVED


# ==============================================================================
# Action Item Tests
# ==============================================================================

class TestActionItem:
    """Tests for ActionItem dataclass."""
    
    def test_create_action_item(self):
        """Test creating an action item."""
        item = ActionItem(
            action_id="AI-001",
            description="Implement connection pool monitoring",
            owner="engineer_001",
            priority="high",
            category="prevention",
        )
        
        assert item.action_id == "AI-001"
        assert item.description == "Implement connection pool monitoring"
        assert item.status == ActionItemStatus.OPEN
    
    def test_action_item_with_due_date(self):
        """Test action item with due date."""
        due = datetime.now() + timedelta(days=7)
        item = ActionItem(
            action_id="AI-002",
            description="Add alerting",
            owner="eng-001",
            due_date=due,
        )
        
        assert item.due_date == due
    
    def test_action_item_status_change(self):
        """Test changing action item status."""
        item = ActionItem(action_id="AI-003", description="Task")
        assert item.status == ActionItemStatus.OPEN
        
        item.status = ActionItemStatus.IN_PROGRESS
        assert item.status == ActionItemStatus.IN_PROGRESS
        
        item.status = ActionItemStatus.COMPLETED
        assert item.status == ActionItemStatus.COMPLETED
    
    def test_action_item_to_dict(self):
        """Test action item serialization."""
        item = ActionItem(
            action_id="AI-004",
            description="Add monitoring",
            owner="eng-001",
            priority="medium",
        )
        
        data = item.to_dict()
        assert data["action_id"] == "AI-004"
        assert data["status"] == "open"


# ==============================================================================
# Postmortem Tests
# ==============================================================================

class TestPostmortem:
    """Tests for Postmortem dataclass."""
    
    def test_create_postmortem(self):
        """Test creating a postmortem."""
        postmortem = Postmortem(
            postmortem_id="PM-001",
            incident_id="INC-001",
            title="Database outage postmortem",
        )
        
        assert postmortem.postmortem_id == "PM-001"
        assert postmortem.incident_id == "INC-001"
    
    def test_postmortem_sections(self):
        """Test postmortem section enum."""
        assert PostmortemSection.SUMMARY
        assert PostmortemSection.TIMELINE
        assert PostmortemSection.ROOT_CAUSE
        assert PostmortemSection.IMPACT
        assert PostmortemSection.LESSONS_LEARNED
        assert PostmortemSection.ACTION_ITEMS


# ==============================================================================
# Postmortem Generator Tests
# ==============================================================================

class TestPostmortemGenerator:
    """Tests for PostmortemGenerator."""
    
    def test_generator_creation(self):
        """Test generator creation."""
        generator = PostmortemGenerator()
        assert generator is not None
    
    def test_generator_from_incident(self):
        """Test generating postmortem from incident."""
        generator = PostmortemGenerator()
        
        incident = Incident(
            tenant_id="medsys",
            title="Database connection exhaustion",
            description="Connection pool reached limit",
            priority=IncidentPriority.P2,
            incident_type=IncidentType.AVAILABILITY,
            root_cause="Connection leak in scribe service",
            resolution="Deployed pool fix",
        )
        
        postmortem = generator.generate_from_incident(incident, author="eng-001")
        
        assert postmortem.incident_id == incident.incident_id
        assert incident.title in postmortem.title  # Title is prefixed with priority
    
    def test_generator_add_action_items(self):
        """Test adding action items to postmortem."""
        generator = PostmortemGenerator()
        
        incident = Incident(
            tenant_id="medsys",
            title="Test incident",
            priority=IncidentPriority.P3,
        )
        
        postmortem = generator.generate_from_incident(incident, author="eng-001")
        
        action = ActionItem(
            description="Add connection pool alerting",
            owner="eng-001",
            priority="high",
        )
        generator.add_action_item(postmortem.postmortem_id, action)
        
        updated = generator.get_postmortem(postmortem.postmortem_id)
        assert len(updated.action_items) >= 1


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestOpsIntegration:
    """Integration tests for ops module."""
    
    def test_incident_to_alert_flow(self):
        """Test incident creation triggering alert."""
        pager = OnCallPager()
        pager.set_schedule(OnCallSchedule(
            team="platform",
            primary_oncall="eng-001",
        ))
        
        manager = IncidentManager(pager_callback=lambda i: pager.trigger_alert(
            incident_id=i.incident_id,
            title=i.title,
            message=i.description,
            severity=AlertSeverity.CRITICAL if i.priority == IncidentPriority.P1 else AlertSeverity.HIGH,
            team="platform",
        ))
        
        incident = manager.create_incident(
            tenant_id="medsys",
            title="P1 Critical",
            priority=IncidentPriority.P1,
            incident_type=IncidentType.AVAILABILITY,
        )
        
        # Alert should be created
        assert len(pager._alerts) >= 1
    
    def test_incident_lifecycle(self):
        """Test full incident lifecycle."""
        manager = IncidentManager()
        
        # Create
        incident = manager.create_incident(
            tenant_id="medsys",
            title="Lifecycle test",
            priority=IncidentPriority.P2,
            incident_type=IncidentType.PERFORMANCE,
        )
        assert incident.status == IncidentStatus.DETECTED
        
        # Acknowledge
        manager.acknowledge(incident.incident_id, assignee="eng-001")
        incident = manager.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.ACKNOWLEDGED
        
        # Resolve
        manager.resolve(
            incident.incident_id,
            actor="eng-001",
            root_cause="Test cause",
            resolution="Test resolution",
        )
        incident = manager.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.RESOLVED
    
    def test_incident_to_postmortem_flow(self):
        """Test creating postmortem from resolved incident."""
        manager = IncidentManager()
        generator = PostmortemGenerator()
        
        # Create and resolve incident
        incident = manager.create_incident(
            tenant_id="medsys",
            title="Postmortem test",
            priority=IncidentPriority.P2,
            incident_type=IncidentType.PERFORMANCE,
            description="High latency issue",
        )
        
        manager.acknowledge(incident.incident_id, "eng-001")
        manager.resolve(
            incident.incident_id,
            actor="eng-001",
            root_cause="Database query N+1",
            resolution="Added query batching",
        )
        
        # Create postmortem
        resolved = manager.get_incident(incident.incident_id)
        postmortem = generator.generate_from_incident(resolved, author="eng-001")
        
        assert postmortem.incident_id == incident.incident_id
        assert "Database query N+1" in resolved.root_cause
    
    def test_multi_tenant_incident_isolation(self):
        """Test incidents are isolated by tenant."""
        manager = IncidentManager()
        
        manager.create_incident(
            tenant_id="tenant_a",
            title="Tenant A issue",
            priority=IncidentPriority.P3,
            incident_type=IncidentType.PERFORMANCE,
        )
        manager.create_incident(
            tenant_id="tenant_b",
            title="Tenant B issue",
            priority=IncidentPriority.P3,
            incident_type=IncidentType.PERFORMANCE,
        )
        
        tenant_a = manager.get_active_incidents(tenant_id="tenant_a")
        tenant_b = manager.get_active_incidents(tenant_id="tenant_b")
        
        assert len(tenant_a) == 1
        assert len(tenant_b) == 1
        assert tenant_a[0].tenant_id == "tenant_a"
        assert tenant_b[0].tenant_id == "tenant_b"
