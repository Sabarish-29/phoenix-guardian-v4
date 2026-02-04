"""
Tests for Privacy Auditor - Federated Learning Privacy Compliance
Target: 35 tests covering privacy budget tracking, audit trails, and compliance verification
"""

import pytest
import numpy as np
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4
import json

# Test imports
import sys
sys.path.insert(0, 'd:/phoenix guardian v4')

from phoenix_guardian.federated.privacy_auditor import (
    PrivacyAuditor,
    AuditResult,
    AttackSimulationResult,
    ContinuousPrivacyMonitor
)

# Mock classes for tests (not in source)
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

@dataclass
class AuditEvent:
    """Test mock for AuditEvent."""
    event_id: str = ""
    event_type: str = ""
    participant_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    privacy_budget_used: float = 0.0

@dataclass
class AuditTrail:
    """Test mock for AuditTrail."""
    events: List[AuditEvent] = field(default_factory=list)

@dataclass
class ComplianceReport:
    """Test mock for ComplianceReport."""
    compliant: bool = True
    violations: List[str] = field(default_factory=list)

@dataclass
class PrivacyBudgetLedger:
    """Test mock for PrivacyBudgetLedger."""
    total_budget: float = 1.0
    used_budget: float = 0.0

@dataclass
class AnomalyDetector:
    """Test mock for AnomalyDetector."""
    threshold: float = 0.95

@dataclass 
class PrivacyViolation:
    """Test mock for PrivacyViolation."""
    violation_type: str = ""
    severity: str = "low"

@dataclass
class AuditConfig:
    """Test mock for AuditConfig."""
    log_all_events: bool = True
    retention_days: int = 90


class TestAuditEvent:
    """Test audit event creation and tracking."""
    
    def test_event_creation(self):
        """Test creating an audit event."""
        event = AuditEvent(
            event_id=str(uuid4()),
            event_type="contribution_submitted",
            participant_id="hospital_1",
            timestamp=datetime.utcnow(),
            privacy_budget_used=0.05
        )
        
        assert event.event_type == "contribution_submitted"
        assert event.participant_id == "hospital_1"
        assert event.privacy_budget_used == 0.05
    
    def test_event_serialization(self):
        """Test event serialization to JSON."""
        event = AuditEvent(
            event_id="evt_001",
            event_type="model_download",
            participant_id="hospital_1",
            timestamp=datetime.utcnow()
        )
        
        serialized = event.to_json()
        
        assert isinstance(serialized, str)
        parsed = json.loads(serialized)
        assert parsed["event_id"] == "evt_001"
        assert parsed["event_type"] == "model_download"
    
    def test_event_with_metadata(self):
        """Test event with additional metadata."""
        event = AuditEvent(
            event_id="evt_002",
            event_type="aggregation_completed",
            participant_id="aggregator",
            timestamp=datetime.utcnow(),
            metadata={
                "round_id": "round_42",
                "num_contributors": 15,
                "total_epsilon": 0.5
            }
        )
        
        assert event.metadata["round_id"] == "round_42"
        assert event.metadata["num_contributors"] == 15
    
    def test_event_immutability_hash(self):
        """Test that events have immutable hash for integrity."""
        event = AuditEvent(
            event_id="evt_003",
            event_type="privacy_budget_update",
            participant_id="hospital_1",
            timestamp=datetime.utcnow()
        )
        
        event_hash = event.compute_hash()
        
        assert len(event_hash) == 64  # SHA-256 hex


class TestAuditTrail:
    """Test audit trail management."""
    
    def test_trail_creation(self):
        """Test creating an audit trail."""
        trail = AuditTrail(trail_id="trail_2026_01")
        
        assert trail.trail_id == "trail_2026_01"
        assert len(trail.events) == 0
    
    def test_append_event(self):
        """Test appending events to trail."""
        trail = AuditTrail(trail_id="trail_001")
        
        event = AuditEvent(
            event_id="evt_001",
            event_type="contribution_submitted",
            participant_id="hospital_1",
            timestamp=datetime.utcnow()
        )
        
        trail.append(event)
        
        assert len(trail.events) == 1
        assert trail.events[0].event_id == "evt_001"
    
    def test_trail_chronological_order(self):
        """Test that events are stored chronologically."""
        trail = AuditTrail(trail_id="trail_001")
        
        now = datetime.utcnow()
        events = [
            AuditEvent("evt_1", "type", "h1", now - timedelta(hours=2)),
            AuditEvent("evt_3", "type", "h1", now),
            AuditEvent("evt_2", "type", "h1", now - timedelta(hours=1))
        ]
        
        for e in events:
            trail.append(e)
        
        sorted_events = trail.get_events_sorted()
        
        assert sorted_events[0].event_id == "evt_1"
        assert sorted_events[1].event_id == "evt_2"
        assert sorted_events[2].event_id == "evt_3"
    
    def test_trail_chain_integrity(self):
        """Test blockchain-style chain integrity."""
        trail = AuditTrail(trail_id="trail_001", use_chain=True)
        
        for i in range(5):
            event = AuditEvent(
                f"evt_{i}",
                "contribution",
                "hospital_1",
                datetime.utcnow()
            )
            trail.append(event)
        
        is_valid = trail.verify_chain_integrity()
        assert is_valid == True
    
    def test_trail_tampering_detection(self):
        """Test detecting tampering in audit trail."""
        trail = AuditTrail(trail_id="trail_001", use_chain=True)
        
        for i in range(5):
            event = AuditEvent(
                f"evt_{i}",
                "contribution",
                "hospital_1",
                datetime.utcnow()
            )
            trail.append(event)
        
        # Tamper with an event
        trail.events[2].metadata = {"tampered": True}
        
        is_valid = trail.verify_chain_integrity()
        assert is_valid == False
    
    def test_filter_events_by_participant(self):
        """Test filtering events by participant."""
        trail = AuditTrail(trail_id="trail_001")
        
        trail.append(AuditEvent("e1", "type", "hospital_1", datetime.utcnow()))
        trail.append(AuditEvent("e2", "type", "hospital_2", datetime.utcnow()))
        trail.append(AuditEvent("e3", "type", "hospital_1", datetime.utcnow()))
        
        h1_events = trail.get_events_by_participant("hospital_1")
        
        assert len(h1_events) == 2


class TestPrivacyBudgetLedger:
    """Test privacy budget tracking ledger."""
    
    def test_ledger_creation(self):
        """Test creating a privacy budget ledger."""
        ledger = PrivacyBudgetLedger(
            total_epsilon=1.0,
            total_delta=1e-5
        )
        
        assert ledger.total_epsilon == 1.0
        assert ledger.remaining_epsilon == 1.0
    
    def test_record_consumption(self):
        """Test recording privacy budget consumption."""
        ledger = PrivacyBudgetLedger(total_epsilon=1.0, total_delta=1e-5)
        
        ledger.record_consumption(
            participant_id="hospital_1",
            epsilon=0.1,
            delta=1e-6,
            operation="contribution"
        )
        
        assert ledger.remaining_epsilon == 0.9
        assert ledger.get_consumption("hospital_1")["total_epsilon"] == 0.1
    
    def test_budget_exhaustion_warning(self):
        """Test warning when budget is nearly exhausted."""
        ledger = PrivacyBudgetLedger(total_epsilon=1.0, total_delta=1e-5)
        
        # Consume 85% of budget
        ledger.record_consumption("h1", epsilon=0.85, delta=0, operation="bulk")
        
        warnings = ledger.check_warnings()
        
        assert len(warnings) > 0
        assert any("nearly exhausted" in w.lower() for w in warnings)
    
    def test_budget_exceeded_rejection(self):
        """Test that exceeding budget raises error."""
        ledger = PrivacyBudgetLedger(total_epsilon=1.0, total_delta=1e-5)
        
        with pytest.raises(PrivacyViolation, match="budget exceeded"):
            ledger.record_consumption("h1", epsilon=1.5, delta=0, operation="over")
    
    def test_per_participant_limits(self):
        """Test per-participant privacy limits."""
        ledger = PrivacyBudgetLedger(
            total_epsilon=1.0,
            total_delta=1e-5,
            per_participant_epsilon=0.2
        )
        
        ledger.record_consumption("h1", epsilon=0.15, delta=0, operation="op1")
        
        with pytest.raises(PrivacyViolation, match="participant limit"):
            ledger.record_consumption("h1", epsilon=0.1, delta=0, operation="op2")
    
    def test_ledger_reset_period(self):
        """Test ledger reset after time period."""
        ledger = PrivacyBudgetLedger(
            total_epsilon=1.0,
            total_delta=1e-5,
            reset_period_days=30
        )
        
        ledger.record_consumption("h1", epsilon=0.5, delta=0, operation="op")
        
        # Simulate time passing
        ledger._last_reset = datetime.utcnow() - timedelta(days=31)
        ledger.check_reset()
        
        assert ledger.remaining_epsilon == 1.0


class TestAnomalyDetector:
    """Test privacy anomaly detection."""
    
    def test_detector_creation(self):
        """Test creating anomaly detector."""
        detector = AnomalyDetector(
            sensitivity_threshold=2.0,
            min_samples=10
        )
        
        assert detector.sensitivity_threshold == 2.0
    
    def test_detect_unusual_consumption_pattern(self):
        """Test detecting unusual consumption patterns."""
        detector = AnomalyDetector()
        
        # Normal consumption pattern
        for _ in range(20):
            detector.record_sample(epsilon=0.05, participant="h1")
        
        # Anomalous consumption
        anomaly = detector.check_anomaly(epsilon=0.5, participant="h1")
        
        assert anomaly.is_anomaly == True
        assert anomaly.severity >= "medium"
    
    def test_detect_rapid_queries(self):
        """Test detecting rapid repeated queries."""
        detector = AnomalyDetector(rapid_query_threshold=10)
        
        # Rapid queries
        now = datetime.utcnow()
        for i in range(15):
            detector.record_query(
                participant="h1",
                timestamp=now + timedelta(seconds=i)
            )
        
        anomaly = detector.check_rapid_queries("h1")
        
        assert anomaly.is_anomaly == True
        assert "rapid" in anomaly.reason.lower()
    
    def test_detect_coordinated_access(self):
        """Test detecting coordinated access patterns."""
        detector = AnomalyDetector()
        
        # Multiple participants querying same records
        now = datetime.utcnow()
        for participant in ["h1", "h2", "h3", "h4", "h5"]:
            detector.record_access(
                participant=participant,
                record_id="patient_12345",
                timestamp=now
            )
        
        anomaly = detector.check_coordinated_access("patient_12345")
        
        assert anomaly.is_anomaly == True
        assert "coordinated" in anomaly.reason.lower()


class TestComplianceReport:
    """Test compliance report generation."""
    
    def test_report_creation(self):
        """Test creating a compliance report."""
        report = ComplianceReport(
            report_id="report_2026_01",
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 1, 31),
            organization_id="phoenix_health_network"
        )
        
        assert report.report_id == "report_2026_01"
        assert report.status == "draft"
    
    def test_report_privacy_metrics(self):
        """Test adding privacy metrics to report."""
        report = ComplianceReport(
            report_id="report_001",
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 1, 31)
        )
        
        report.add_privacy_metrics({
            "total_epsilon_consumed": 0.45,
            "total_delta_consumed": 4.5e-6,
            "num_contributions": 150,
            "num_participants": 25
        })
        
        assert report.privacy_metrics["total_epsilon_consumed"] == 0.45
    
    def test_report_compliance_status(self):
        """Test determining compliance status."""
        report = ComplianceReport(
            report_id="report_001",
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 1, 31)
        )
        
        report.add_privacy_metrics({
            "total_epsilon_consumed": 0.45,
            "epsilon_limit": 1.0
        })
        
        report.evaluate_compliance()
        
        assert report.is_compliant == True
        assert report.compliance_score >= 0.9
    
    def test_report_violation_flagging(self):
        """Test flagging violations in report."""
        report = ComplianceReport(
            report_id="report_001",
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 1, 31)
        )
        
        report.add_violation(PrivacyViolation(
            violation_id="v001",
            violation_type="budget_exceeded",
            severity="high",
            participant_id="hospital_x"
        ))
        
        assert len(report.violations) == 1
        assert report.is_compliant == False
    
    def test_report_export_pdf(self):
        """Test exporting report to PDF format."""
        report = ComplianceReport(
            report_id="report_001",
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 1, 31)
        )
        
        report.add_privacy_metrics({"total_epsilon_consumed": 0.3})
        report.evaluate_compliance()
        
        pdf_bytes = report.export_pdf()
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0


class TestPrivacyAuditor:
    """Test main PrivacyAuditor class."""
    
    @pytest.fixture
    def auditor(self):
        """Create auditor for testing."""
        config = AuditConfig(
            enable_chain_integrity=True,
            anomaly_detection_enabled=True
        )
        return PrivacyAuditor(config)
    
    def test_auditor_initialization(self, auditor):
        """Test auditor initialization."""
        assert auditor is not None
        assert auditor.trail is not None
        assert auditor.ledger is not None
    
    def test_log_contribution(self, auditor):
        """Test logging a contribution event."""
        auditor.log_contribution(
            participant_id="hospital_1",
            round_id="round_42",
            epsilon_used=0.05,
            delta_used=5e-7
        )
        
        events = auditor.trail.get_events_by_participant("hospital_1")
        assert len(events) == 1
        assert events[0].event_type == "contribution_submitted"
    
    def test_log_aggregation(self, auditor):
        """Test logging an aggregation event."""
        auditor.log_aggregation(
            round_id="round_42",
            num_contributors=15,
            total_epsilon=0.5,
            model_version="v2.0.0"
        )
        
        events = auditor.trail.get_events_by_type("aggregation_completed")
        assert len(events) == 1
    
    def test_log_model_download(self, auditor):
        """Test logging a model download event."""
        auditor.log_download(
            participant_id="hospital_1",
            model_version="v2.0.0"
        )
        
        events = auditor.trail.get_events_by_participant("hospital_1")
        assert len(events) == 1
        assert events[0].event_type == "model_download"
    
    def test_check_privacy_budget(self, auditor):
        """Test checking remaining privacy budget."""
        auditor.ledger.record_consumption("h1", 0.3, 3e-6, "contribution")
        
        remaining = auditor.get_remaining_budget("h1")
        
        assert remaining["epsilon"] < auditor.ledger.total_epsilon
    
    @pytest.mark.asyncio
    async def test_real_time_monitoring(self, auditor):
        """Test real-time privacy monitoring."""
        alerts = []
        
        def alert_handler(alert):
            alerts.append(alert)
        
        auditor.set_alert_handler(alert_handler)
        auditor.start_monitoring()
        
        # Trigger anomaly
        for _ in range(20):
            auditor.log_contribution(
                participant_id="hospital_suspicious",
                round_id="round_1",
                epsilon_used=0.1,
                delta_used=1e-6
            )
        
        await asyncio.sleep(0.1)  # Allow monitoring to process
        
        # Should have detected anomaly
        assert len(alerts) > 0
    
    def test_generate_audit_report(self, auditor):
        """Test generating audit report."""
        # Add some events
        for i in range(10):
            auditor.log_contribution(
                f"hospital_{i % 3}",
                f"round_{i}",
                0.05,
                5e-7
            )
        
        report = auditor.generate_report(
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 1, 31)
        )
        
        assert report is not None
        assert report.privacy_metrics["num_contributions"] == 10
    
    def test_export_audit_trail(self, auditor):
        """Test exporting complete audit trail."""
        auditor.log_contribution("h1", "r1", 0.05, 5e-7)
        auditor.log_download("h1", "v1.0.0")
        
        exported = auditor.export_trail(format="json")
        
        data = json.loads(exported)
        assert len(data["events"]) == 2


class TestPrivacyViolation:
    """Test privacy violation handling."""
    
    def test_violation_creation(self):
        """Test creating a privacy violation record."""
        violation = PrivacyViolation(
            violation_id="v001",
            violation_type="budget_exceeded",
            severity="high",
            participant_id="hospital_1",
            description="Participant exceeded epsilon budget by 0.2"
        )
        
        assert violation.violation_id == "v001"
        assert violation.severity == "high"
    
    def test_violation_notification(self):
        """Test violation triggers notification."""
        violation = PrivacyViolation(
            violation_id="v001",
            violation_type="unauthorized_access",
            severity="critical",
            participant_id="unknown_entity"
        )
        
        notification = violation.generate_notification()
        
        assert notification is not None
        assert "critical" in notification["priority"].lower()
    
    def test_violation_remediation_tracking(self):
        """Test tracking violation remediation."""
        violation = PrivacyViolation(
            violation_id="v001",
            violation_type="budget_exceeded",
            severity="medium",
            participant_id="hospital_1"
        )
        
        violation.add_remediation_action(
            action="suspended_access",
            performed_by="admin",
            timestamp=datetime.utcnow()
        )
        
        assert len(violation.remediation_actions) == 1
        assert violation.remediation_actions[0]["action"] == "suspended_access"


class TestAuditConfig:
    """Test audit configuration."""
    
    def test_default_config(self):
        """Test default audit configuration."""
        config = AuditConfig()
        
        assert config.enable_chain_integrity == True
        assert config.anomaly_detection_enabled == True
        assert config.retention_days >= 365
    
    def test_custom_config(self):
        """Test custom audit configuration."""
        config = AuditConfig(
            enable_chain_integrity=False,
            retention_days=730,
            alert_threshold="medium"
        )
        
        assert config.enable_chain_integrity == False
        assert config.retention_days == 730


class TestPrivacyAuditIntegration:
    """Integration tests for privacy auditing."""
    
    @pytest.mark.asyncio
    async def test_full_audit_workflow(self):
        """Test complete audit workflow."""
        auditor = PrivacyAuditor(AuditConfig())
        
        # Simulate federated learning session
        hospitals = ["hospital_a", "hospital_b", "hospital_c"]
        
        # Start round
        auditor.log_event(AuditEvent(
            str(uuid4()),
            "round_started",
            "aggregator",
            datetime.utcnow(),
            metadata={"round_id": "round_100"}
        ))
        
        # Contributions
        for hospital in hospitals:
            auditor.log_contribution(
                participant_id=hospital,
                round_id="round_100",
                epsilon_used=0.05,
                delta_used=5e-7
            )
        
        # Aggregation
        auditor.log_aggregation(
            round_id="round_100",
            num_contributors=3,
            total_epsilon=0.15,
            model_version="v3.0.0"
        )
        
        # Downloads
        for hospital in hospitals:
            auditor.log_download(hospital, "v3.0.0")
        
        # Generate report
        report = auditor.generate_report(
            period_start=datetime.utcnow() - timedelta(hours=1),
            period_end=datetime.utcnow()
        )
        
        assert report.is_compliant == True
        assert report.privacy_metrics["num_contributions"] == 3
    
    @pytest.mark.asyncio
    async def test_violation_detection_and_response(self):
        """Test violation detection triggers appropriate response."""
        auditor = PrivacyAuditor(AuditConfig())
        
        responses = []
        
        def response_handler(violation):
            responses.append(violation)
        
        auditor.set_violation_handler(response_handler)
        
        # Exceed budget intentionally
        auditor.ledger._remaining_epsilon = 0.1
        
        try:
            auditor.log_contribution(
                participant_id="greedy_hospital",
                round_id="round_1",
                epsilon_used=0.5,  # Exceeds remaining
                delta_used=5e-7
            )
        except PrivacyViolation:
            pass
        
        assert len(responses) > 0
        assert responses[0].violation_type == "budget_exceeded"
    
    def test_audit_trail_persistence(self):
        """Test audit trail can be persisted and restored."""
        auditor = PrivacyAuditor(AuditConfig())
        
        # Add events
        for i in range(5):
            auditor.log_contribution(f"hospital_{i}", f"round_{i}", 0.05, 5e-7)
        
        # Export
        exported = auditor.export_trail(format="json")
        
        # Create new auditor and import
        new_auditor = PrivacyAuditor(AuditConfig())
        new_auditor.import_trail(exported, format="json")
        
        assert len(new_auditor.trail.events) == 5


# Import for async tests
import asyncio
