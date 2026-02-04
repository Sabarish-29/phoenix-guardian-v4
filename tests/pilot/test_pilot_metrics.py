"""
Tests for Hospital Pilot Metrics tracking.

These tests verify the pilot metrics system works correctly for
tracking hospital onboarding progress and KPIs.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, str(__file__).replace("\\", "/").rsplit("/", 3)[0])

from analytics.pilot_metrics import (
    PilotMetrics,
    PilotPhase,
    MetricStatus,
    PilotMetricsCollector,
    PilotDashboardExporter,
)


class TestPilotMetrics:
    """Test PilotMetrics dataclass functionality."""
    
    def test_create_pilot_metrics(self):
        """Test creating a PilotMetrics instance."""
        metrics = PilotMetrics(
            hospital_id="hospital-001",
            hospital_name="Memorial General Hospital",
            start_date=datetime(2026, 2, 10),
        )
        
        assert metrics.hospital_id == "hospital-001"
        assert metrics.hospital_name == "Memorial General Hospital"
        assert metrics.phase == PilotPhase.PRE_DEPLOYMENT
        assert metrics.total_physicians == 0
        assert metrics.uptime_percent == 100.0
    
    def test_default_targets(self):
        """Test that default targets are set correctly."""
        metrics = PilotMetrics(
            hospital_id="test",
            hospital_name="Test Hospital",
            start_date=datetime.utcnow(),
        )
        
        assert metrics.targets["soap_completeness"] == 95.0
        assert metrics.targets["generation_time_ms"] == 5000.0
        assert metrics.targets["physician_satisfaction"] == 4.0
        assert metrics.targets["uptime_percent"] == 99.5
        assert metrics.targets["support_tickets_week"] == 10
    
    def test_calculate_status_higher_is_better(self):
        """Test status calculation for metrics where higher is better."""
        metrics = PilotMetrics(
            hospital_id="test",
            hospital_name="Test",
            start_date=datetime.utcnow(),
        )
        
        # Uptime target is 99.5%
        assert metrics.calculate_status("uptime_percent", 99.9) == MetricStatus.EXCEEDS
        assert metrics.calculate_status("uptime_percent", 99.5) == MetricStatus.MEETS
        assert metrics.calculate_status("uptime_percent", 99.0) == MetricStatus.AT_RISK
        assert metrics.calculate_status("uptime_percent", 85.0) == MetricStatus.CRITICAL
    
    def test_calculate_status_lower_is_better(self):
        """Test status calculation for metrics where lower is better."""
        metrics = PilotMetrics(
            hospital_id="test",
            hospital_name="Test",
            start_date=datetime.utcnow(),
        )
        
        # Generation time target is 5000ms
        assert metrics.calculate_status("generation_time_ms", 3000) == MetricStatus.EXCEEDS
        assert metrics.calculate_status("generation_time_ms", 4500) == MetricStatus.MEETS
        assert metrics.calculate_status("generation_time_ms", 5500) == MetricStatus.AT_RISK
        assert metrics.calculate_status("generation_time_ms", 8000) == MetricStatus.CRITICAL
    
    def test_health_summary(self):
        """Test getting health summary across all metrics."""
        metrics = PilotMetrics(
            hospital_id="test",
            hospital_name="Test",
            start_date=datetime.utcnow(),
            avg_generation_time_ms=2500,
            p95_latency_ms=2800,
            error_rate_percent=0.05,
            soap_completeness_score=97.0,
            physician_satisfaction=4.5,
            uptime_percent=99.9,
            support_tickets_week=5,
            physician_edit_rate=20.0,
        )
        
        health = metrics.get_health_summary()
        
        assert health["generation_time"] == MetricStatus.EXCEEDS
        assert health["latency_p95"] == MetricStatus.EXCEEDS
        assert health["error_rate"] == MetricStatus.EXCEEDS
        assert health["soap_completeness"] == MetricStatus.MEETS
        assert health["satisfaction"] == MetricStatus.EXCEEDS
        assert health["uptime"] == MetricStatus.EXCEEDS
        assert health["support_load"] == MetricStatus.EXCEEDS
    
    def test_production_ready_success(self):
        """Test production readiness check when all criteria met."""
        metrics = PilotMetrics(
            hospital_id="test",
            hospital_name="Test",
            start_date=datetime.utcnow() - timedelta(days=14),
            phase=PilotPhase.BETA,
            total_physicians=25,
            active_physicians_24h=10,
            total_encounters_processed=150,
            p0_incidents=0,
            p1_incidents=1,
            uptime_percent=99.8,
            physician_satisfaction=4.2,
        )
        
        ready, blockers = metrics.is_ready_for_production()
        
        assert ready is True
        assert len(blockers) == 0
    
    def test_production_ready_failure_p0_incidents(self):
        """Test production readiness fails with P0 incidents."""
        metrics = PilotMetrics(
            hospital_id="test",
            hospital_name="Test",
            start_date=datetime.utcnow(),
            active_physicians_24h=5,
            total_encounters_processed=100,
            p0_incidents=1,
            uptime_percent=99.9,
            physician_satisfaction=4.5,
        )
        
        ready, blockers = metrics.is_ready_for_production()
        
        assert ready is False
        assert any("P0" in b for b in blockers)
    
    def test_production_ready_failure_low_uptime(self):
        """Test production readiness fails with low uptime."""
        metrics = PilotMetrics(
            hospital_id="test",
            hospital_name="Test",
            start_date=datetime.utcnow(),
            active_physicians_24h=5,
            total_encounters_processed=100,
            p0_incidents=0,
            p1_incidents=0,
            uptime_percent=95.0,
            physician_satisfaction=4.5,
        )
        
        ready, blockers = metrics.is_ready_for_production()
        
        assert ready is False
        assert any("Uptime" in b for b in blockers)
    
    def test_production_ready_failure_low_satisfaction(self):
        """Test production readiness fails with low satisfaction."""
        metrics = PilotMetrics(
            hospital_id="test",
            hospital_name="Test",
            start_date=datetime.utcnow(),
            active_physicians_24h=5,
            total_encounters_processed=100,
            p0_incidents=0,
            uptime_percent=99.9,
            physician_satisfaction=2.5,
        )
        
        ready, blockers = metrics.is_ready_for_production()
        
        assert ready is False
        assert any("Satisfaction" in b for b in blockers)
    
    def test_production_ready_failure_insufficient_testing(self):
        """Test production readiness fails with insufficient testing."""
        metrics = PilotMetrics(
            hospital_id="test",
            hospital_name="Test",
            start_date=datetime.utcnow(),
            active_physicians_24h=1,  # Too few
            total_encounters_processed=20,  # Too few
            p0_incidents=0,
            uptime_percent=99.9,
            physician_satisfaction=4.5,
        )
        
        ready, blockers = metrics.is_ready_for_production()
        
        assert ready is False
        assert any("Active physicians" in b for b in blockers)
        assert any("Encounters" in b for b in blockers)
    
    def test_to_dict_serialization(self):
        """Test metrics serialize to dictionary correctly."""
        metrics = PilotMetrics(
            hospital_id="hospital-001",
            hospital_name="Memorial General",
            start_date=datetime(2026, 2, 10),
            phase=PilotPhase.BETA,
            total_physicians=25,
            active_physicians_24h=10,
            total_encounters_processed=150,
            encounters_today=25,
            avg_generation_time_ms=2500,
            p95_latency_ms=4000,
            soap_completeness_score=96.5,
            physician_satisfaction=4.3,
            uptime_percent=99.8,
            federated_learning_enabled=True,
        )
        
        data = metrics.to_dict()
        
        assert data["hospital_id"] == "hospital-001"
        assert data["phase"] == "beta"
        assert data["usage"]["total_physicians"] == 25
        assert data["performance"]["avg_generation_time_ms"] == 2500
        assert data["quality"]["soap_completeness"] == 96.5
        assert data["satisfaction"]["physician_rating"] == 4.3
        assert data["operations"]["uptime_percent"] == 99.8
        assert data["federated_learning"]["enabled"] is True
        assert "health" in data
        assert "production_ready" in data


class TestPilotMetricsCollector:
    """Test PilotMetricsCollector functionality."""
    
    def test_register_hospital(self):
        """Test registering a new hospital in the pilot program."""
        collector = PilotMetricsCollector(
            db_connection=MagicMock(),
            redis_client=MagicMock(),
            prometheus_url="http://prometheus:9090",
        )
        
        metrics = collector.register_hospital(
            hospital_id="hospital-002",
            hospital_name="City Medical Center",
            start_date=datetime(2026, 3, 1),
            total_physicians=40,
        )
        
        assert metrics.hospital_id == "hospital-002"
        assert metrics.hospital_name == "City Medical Center"
        assert metrics.total_physicians == 40
        assert metrics.phase == PilotPhase.PRE_DEPLOYMENT
    
    def test_register_hospital_with_custom_targets(self):
        """Test registering hospital with custom metric targets."""
        collector = PilotMetricsCollector(
            db_connection=MagicMock(),
            redis_client=MagicMock(),
            prometheus_url="http://prometheus:9090",
        )
        
        custom_targets = {
            "soap_completeness": 98.0,  # Higher than default
            "generation_time_ms": 3000.0,  # Stricter than default
        }
        
        metrics = collector.register_hospital(
            hospital_id="hospital-003",
            hospital_name="Academic Medical Center",
            start_date=datetime(2026, 4, 1),
            total_physicians=100,
            custom_targets=custom_targets,
        )
        
        assert metrics.targets["soap_completeness"] == 98.0
        assert metrics.targets["generation_time_ms"] == 3000.0
        # Other targets should remain default
        assert metrics.targets["physician_satisfaction"] == 4.0
    
    def test_update_phase(self):
        """Test updating a hospital's pilot phase."""
        collector = PilotMetricsCollector(
            db_connection=MagicMock(),
            redis_client=MagicMock(),
            prometheus_url="http://prometheus:9090",
        )
        
        collector.register_hospital(
            hospital_id="hospital-001",
            hospital_name="Test Hospital",
            start_date=datetime.utcnow(),
            total_physicians=20,
        )
        
        collector.update_phase("hospital-001", PilotPhase.BETA)
        
        hospitals = collector.get_all_hospitals()
        assert hospitals[0].phase == PilotPhase.BETA
    
    def test_update_phase_invalid_hospital(self):
        """Test updating phase for non-existent hospital raises error."""
        collector = PilotMetricsCollector(
            db_connection=MagicMock(),
            redis_client=MagicMock(),
            prometheus_url="http://prometheus:9090",
        )
        
        with pytest.raises(ValueError, match="not found"):
            collector.update_phase("nonexistent", PilotPhase.PRODUCTION)
    
    def test_get_aggregate_metrics(self):
        """Test getting aggregate metrics across all hospitals."""
        collector = PilotMetricsCollector(
            db_connection=MagicMock(),
            redis_client=MagicMock(),
            prometheus_url="http://prometheus:9090",
        )
        
        # Register multiple hospitals
        m1 = collector.register_hospital(
            hospital_id="h1",
            hospital_name="Hospital 1",
            start_date=datetime.utcnow(),
            total_physicians=20,
        )
        m1.active_physicians_24h = 15
        m1.total_encounters_processed = 500
        m1.encounters_today = 50
        m1.physician_satisfaction = 4.2
        m1.uptime_percent = 99.8
        m1.total_hours_saved = 100
        
        m2 = collector.register_hospital(
            hospital_id="h2",
            hospital_name="Hospital 2",
            start_date=datetime.utcnow(),
            total_physicians=30,
        )
        m2.active_physicians_24h = 25
        m2.total_encounters_processed = 800
        m2.encounters_today = 80
        m2.physician_satisfaction = 4.5
        m2.uptime_percent = 99.9
        m2.total_hours_saved = 150
        
        aggregate = collector.get_aggregate_metrics()
        
        assert aggregate["total_hospitals"] == 2
        assert aggregate["total_physicians"] == 50
        assert aggregate["active_physicians_24h"] == 40
        assert aggregate["total_encounters"] == 1300
        assert aggregate["encounters_today"] == 130
        assert aggregate["avg_satisfaction"] == 4.35
        assert aggregate["total_hours_saved"] == 250


class TestPilotDashboardExporter:
    """Test PilotDashboardExporter functionality."""
    
    def test_generate_executive_summary(self):
        """Test generating executive summary report."""
        collector = PilotMetricsCollector(
            db_connection=MagicMock(),
            redis_client=MagicMock(),
            prometheus_url="http://prometheus:9090",
        )
        
        m1 = collector.register_hospital(
            hospital_id="h1",
            hospital_name="Hospital 1",
            start_date=datetime.utcnow() - timedelta(days=14),
            total_physicians=20,
        )
        m1.phase = PilotPhase.PRODUCTION
        m1.active_physicians_24h = 15
        m1.total_encounters_processed = 500
        m1.physician_satisfaction = 4.2
        m1.uptime_percent = 99.8
        
        exporter = PilotDashboardExporter(collector)
        summary = exporter.generate_executive_summary()
        
        assert "Phoenix Guardian Pilot Program" in summary
        assert "Hospital 1" in summary
        assert "Total Pilot Hospitals | 1" in summary
        assert "Production" in summary
    
    def test_export_to_csv(self, tmp_path):
        """Test exporting metrics to CSV file."""
        collector = PilotMetricsCollector(
            db_connection=MagicMock(),
            redis_client=MagicMock(),
            prometheus_url="http://prometheus:9090",
        )
        
        m1 = collector.register_hospital(
            hospital_id="h1",
            hospital_name="Test Hospital",
            start_date=datetime(2026, 2, 1),
            total_physicians=25,
        )
        m1.phase = PilotPhase.BETA
        m1.active_physicians_24h = 20
        m1.total_encounters_processed = 300
        m1.avg_generation_time_ms = 2500
        m1.physician_satisfaction = 4.3
        m1.uptime_percent = 99.8
        
        exporter = PilotDashboardExporter(collector)
        output_file = tmp_path / "pilot_metrics.csv"
        exporter.export_to_csv(str(output_file))
        
        assert output_file.exists()
        content = output_file.read_text()
        assert "Hospital ID" in content
        assert "h1" in content
        assert "Test Hospital" in content
        assert "beta" in content


class TestPilotPhases:
    """Test pilot phase transitions and validation."""
    
    def test_all_phases_defined(self):
        """Test all expected phases are defined."""
        phases = list(PilotPhase)
        
        assert PilotPhase.PRE_DEPLOYMENT in phases
        assert PilotPhase.BETA in phases
        assert PilotPhase.PRODUCTION in phases
        assert PilotPhase.SCALING in phases
        assert PilotPhase.STEADY_STATE in phases
    
    def test_phase_values(self):
        """Test phase string values are correct."""
        assert PilotPhase.PRE_DEPLOYMENT.value == "pre_deployment"
        assert PilotPhase.BETA.value == "beta"
        assert PilotPhase.PRODUCTION.value == "production"
        assert PilotPhase.SCALING.value == "scaling"
        assert PilotPhase.STEADY_STATE.value == "steady_state"


class TestMetricStatus:
    """Test metric status indicators."""
    
    def test_all_statuses_defined(self):
        """Test all expected statuses are defined."""
        statuses = list(MetricStatus)
        
        assert MetricStatus.EXCEEDS in statuses
        assert MetricStatus.MEETS in statuses
        assert MetricStatus.AT_RISK in statuses
        assert MetricStatus.CRITICAL in statuses
    
    def test_status_values(self):
        """Test status string values."""
        assert MetricStatus.EXCEEDS.value == "exceeds"
        assert MetricStatus.MEETS.value == "meets"
        assert MetricStatus.AT_RISK.value == "at_risk"
        assert MetricStatus.CRITICAL.value == "critical"


class TestFederatedLearningMetrics:
    """Test federated learning related metrics."""
    
    def test_federated_learning_disabled_by_default(self):
        """Test FL is disabled by default."""
        metrics = PilotMetrics(
            hospital_id="test",
            hospital_name="Test",
            start_date=datetime.utcnow(),
        )
        
        assert metrics.federated_learning_enabled is False
        assert metrics.model_updates_contributed == 0
        assert metrics.privacy_budget_remaining == 1.0
    
    def test_federated_learning_metrics_in_dict(self):
        """Test FL metrics are included in serialization."""
        metrics = PilotMetrics(
            hospital_id="test",
            hospital_name="Test",
            start_date=datetime.utcnow(),
            federated_learning_enabled=True,
            model_updates_contributed=15,
            privacy_budget_remaining=0.75,
        )
        
        data = metrics.to_dict()
        
        assert data["federated_learning"]["enabled"] is True
        assert data["federated_learning"]["updates_contributed"] == 15
        assert data["federated_learning"]["privacy_budget_remaining"] == 0.75


class TestTimeSavingsMetrics:
    """Test time savings tracking."""
    
    def test_time_savings_calculation(self):
        """Test time savings metrics are tracked correctly."""
        metrics = PilotMetrics(
            hospital_id="test",
            hospital_name="Test",
            start_date=datetime.utcnow(),
            avg_time_saved_minutes=8.5,
            total_hours_saved=150.0,
        )
        
        data = metrics.to_dict()
        
        assert data["time_savings"]["avg_minutes_per_encounter"] == 8.5
        assert data["time_savings"]["total_hours_saved"] == 150.0
    
    def test_time_savings_default_zero(self):
        """Test time savings default to zero."""
        metrics = PilotMetrics(
            hospital_id="test",
            hospital_name="Test",
            start_date=datetime.utcnow(),
        )
        
        assert metrics.avg_time_saved_minutes == 0.0
        assert metrics.total_hours_saved == 0.0
