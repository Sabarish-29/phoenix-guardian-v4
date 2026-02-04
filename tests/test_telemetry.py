"""
Tests for Phoenix Guardian Telemetry Module
Week 19-20: Pilot Instrumentation Tests

Tests encounter metrics tracking, collection, and benchmark validation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import json

from phoenix_guardian.telemetry.encounter_metrics import (
    EncounterMetrics,
    TimingBreakdown,
    AgentInvocation,
    SecurityEvent,
    SOAPNoteQuality,
    EncounterPhase,
    AgentType,
    SecurityEventType,
)
from phoenix_guardian.telemetry.telemetry_collector import (
    TelemetryBuffer,
    TelemetryExporter,
    TelemetryCollector,
    BufferConfig,
    BufferFlushTrigger,
    ExportDestination,
)
from phoenix_guardian.telemetry.benchmark_comparator import (
    BenchmarkComparator,
    BenchmarkResult,
    BenchmarkReport,
    BenchmarkStatus,
    MetricTrend,
)
from phoenix_guardian.telemetry.dashboard_feed import (
    LiveMetric,
    MetricSnapshot,
    DashboardFeed,
    StreamSubscription,
    StreamSubscriptionType,
    MetricType,
)


# ==============================================================================
# Encounter Metrics Tests
# ==============================================================================

class TestEncounterMetrics:
    """Tests for EncounterMetrics dataclass."""
    
    def test_create_encounter_metrics(self):
        """Test creating basic encounter metrics."""
        metrics = EncounterMetrics(
            encounter_id="enc-001",
            tenant_id="medsys",
            physician_id="dr-smith",
        )
        
        assert metrics.encounter_id == "enc-001"
        assert metrics.tenant_id == "medsys"
        assert metrics.physician_id == "dr-smith"
        assert metrics.phase == EncounterPhase.STARTED
    
    def test_encounter_lifecycle(self):
        """Test encounter lifecycle methods."""
        metrics = EncounterMetrics(
            encounter_id="enc-002",
            tenant_id="medsys",
            physician_id="dr-smith",
        )
        
        metrics.start_encounter()
        assert metrics.phase == EncounterPhase.STARTED
        assert metrics.timing.encounter_opened is not None
        
        metrics.start_recording()
        assert metrics.phase == EncounterPhase.RECORDING
        
        metrics.end_recording()
        assert metrics.phase == EncounterPhase.AI_PROCESSING
        
        metrics.draft_ready()
        assert metrics.phase == EncounterPhase.DRAFT_READY
        
        metrics.start_review()
        assert metrics.phase == EncounterPhase.PHYSICIAN_REVIEW
        
        metrics.approve_note()
        assert metrics.phase == EncounterPhase.APPROVED
        
        metrics.start_ehr_write()
        assert metrics.phase == EncounterPhase.EHR_WRITING
        
        metrics.complete_encounter()
        assert metrics.phase == EncounterPhase.COMPLETED
    
    def test_encounter_with_timing_breakdown(self):
        """Test encounter with timing breakdown."""
        timing = TimingBreakdown()
        timing.encounter_opened = datetime.now()
        timing.recording_started = datetime.now()
        
        metrics = EncounterMetrics(
            encounter_id="enc-003",
            tenant_id="medsys",
            physician_id="dr-jones",
            timing=timing,
        )
        
        assert metrics.timing.encounter_opened is not None
        assert metrics.timing.recording_started is not None
    
    def test_encounter_with_agent_invocations(self):
        """Test encounter tracking agent invocations."""
        metrics = EncounterMetrics(
            encounter_id="enc-004",
            tenant_id="medsys",
            physician_id="dr-smith",
        )
        
        invocation = AgentInvocation(
            agent_type=AgentType.SCRIBE,
            invoked_at=datetime.now(),
            success=True,
            latency_ms=450,
        )
        
        metrics.record_agent_invocation(invocation)
        
        assert len(metrics.agent_invocations) == 1
        assert metrics.agent_invocations[0].agent_type == AgentType.SCRIBE
    
    def test_encounter_with_security_events(self):
        """Test encounter tracking security events."""
        metrics = EncounterMetrics(
            encounter_id="enc-005",
            tenant_id="medsys",
            physician_id="dr-smith",
        )
        
        event = SecurityEvent(
            event_type=SecurityEventType.PROMPT_INJECTION,
            severity="high",
            blocked=True,
        )
        
        metrics.security_events.append(event)
        
        assert len(metrics.security_events) == 1
        assert metrics.security_events[0].blocked is True
        assert metrics.security_events[0].severity == "high"
    
    def test_encounter_time_saved_calculation(self):
        """Test time saved calculation vs baseline."""
        timing = TimingBreakdown()
        timing.encounter_opened = datetime.now() - timedelta(minutes=12)
        timing.encounter_completed = datetime.now()
        
        metrics = EncounterMetrics(
            encounter_id="enc-006",
            tenant_id="medsys",
            physician_id="dr-smith",
            timing=timing,
        )
        
        # Traditional time is 25 minutes, so ~13 minutes saved
        assert metrics.timing.time_saved_minutes > 10
    
    def test_encounter_soap_quality(self):
        """Test SOAP note quality metrics."""
        quality = SOAPNoteQuality(
            subjective_rating=5,
            objective_rating=4,
            assessment_rating=5,
            plan_rating=4,
            original_length_chars=1000,
            final_length_chars=1050,
        )
        
        metrics = EncounterMetrics(
            encounter_id="enc-007",
            tenant_id="medsys",
            physician_id="dr-jones",
            note_quality=quality,
        )
        
        assert metrics.note_quality.average_section_rating == 4.5


class TestTimingBreakdown:
    """Tests for TimingBreakdown dataclass."""
    
    def test_timing_breakdown_time_saved(self):
        """Test calculating time saved."""
        timing = TimingBreakdown()
        timing.encounter_opened = datetime.now() - timedelta(minutes=12)
        timing.encounter_completed = datetime.now()
        
        # Traditional baseline is 25 min, actual is ~12 min, so ~13 min saved
        assert timing.time_saved_minutes > 10
        assert timing.time_saved_minutes < 15
    
    def test_timing_breakdown_empty(self):
        """Test timing breakdown with no time recorded."""
        timing = TimingBreakdown()
        
        assert timing.total_time_seconds == 0.0
        assert timing.ai_processing_time_seconds == 0.0


class TestAgentInvocation:
    """Tests for AgentInvocation dataclass."""
    
    def test_agent_invocation_success(self):
        """Test successful agent invocation."""
        invocation = AgentInvocation(
            agent_type=AgentType.SCRIBE,
            invoked_at=datetime.now(),
            success=True,
            latency_ms=350,
        )
        
        assert invocation.success is True
        assert invocation.error_message is None
    
    def test_agent_invocation_failure(self):
        """Test failed agent invocation."""
        invocation = AgentInvocation(
            agent_type=AgentType.NAVIGATOR,
            invoked_at=datetime.now(),
            latency_ms=5000,
            success=False,
            error_message="Timeout exceeded",
            retry_count=3,
        )
        
        assert invocation.success is False
        assert invocation.error_message == "Timeout exceeded"
        assert invocation.retry_count == 3
    
    def test_agent_invocation_latency_calculation(self):
        """Test latency calculation from timestamps."""
        invoked_at = datetime.now()
        completed_at = invoked_at + timedelta(milliseconds=500)
        
        invocation = AgentInvocation(
            agent_type=AgentType.SCRIBE,
            invoked_at=invoked_at,
            completed_at=completed_at,
        )
        
        assert invocation.latency_ms == pytest.approx(500, rel=0.1)


class TestSecurityEvent:
    """Tests for SecurityEvent dataclass."""
    
    def test_security_event_blocked(self):
        """Test blocked security event."""
        event = SecurityEvent(
            event_type=SecurityEventType.DATA_EXFILTRATION,
            severity="critical",
            blocked=True,
        )
        
        assert event.blocked is True
        assert event.severity == "critical"
    
    def test_security_event_detected_not_blocked(self):
        """Test detected but not blocked event (false positive candidate)."""
        event = SecurityEvent(
            event_type=SecurityEventType.ANOMALOUS_BEHAVIOR,
            severity="low",
            blocked=False,
        )
        
        assert event.blocked is False
        assert event.severity == "low"


# ==============================================================================
# Telemetry Collector Tests
# ==============================================================================

class TestTelemetryBuffer:
    """Tests for TelemetryBuffer."""
    
    def test_buffer_add_metrics(self):
        """Test adding metrics to buffer."""
        config = BufferConfig(max_size=100)
        buffer = TelemetryBuffer(config=config)
        
        metrics = EncounterMetrics(
            encounter_id="enc-buf-001",
            tenant_id="medsys",
            physician_id="dr-smith",
        )
        
        buffer.add(metrics)
        
        assert buffer.size == 1
    
    def test_buffer_flush(self):
        """Test flushing buffer."""
        config = BufferConfig(max_size=100)
        flushed_items = []
        
        def on_flush(items):
            flushed_items.extend(items)
            return True
        
        buffer = TelemetryBuffer(config=config, on_flush=on_flush)
        
        for i in range(5):
            metrics = EncounterMetrics(
                encounter_id=f"enc-buf-{i}",
                tenant_id="medsys",
                physician_id="dr-smith",
            )
            buffer.add(metrics)
        
        count = buffer.flush()
        
        assert count == 5
        assert buffer.size == 0
    
    def test_buffer_auto_flush_on_size(self):
        """Test buffer flush behavior with size limit."""
        config = BufferConfig(max_size=3)
        flushed_items = []
        
        def on_flush(items):
            flushed_items.extend(items)
            return True
        
        buffer = TelemetryBuffer(config=config, on_flush=on_flush)
        
        # Add items to buffer
        for i in range(5):
            metrics = EncounterMetrics(
                encounter_id=f"enc-buf-{i}",
                tenant_id="medsys",
                physician_id="dr-smith",
            )
            buffer.add(metrics)
        
        # Buffer should have items (size is tracked)
        assert buffer.size <= config.max_size
        
        # Flush explicitly and verify callback works
        buffer.flush()
        
        # Combined with any auto-flushes, we should have all items
        assert buffer.size == 0
    
    def test_buffer_stats(self):
        """Test buffer statistics."""
        config = BufferConfig(max_size=100)
        buffer = TelemetryBuffer(config=config)
        
        stats = buffer.stats
        
        assert "current_size" in stats
        assert "max_size" in stats
        assert stats["max_size"] == 100


class TestTelemetryExporter:
    """Tests for TelemetryExporter."""
    
    def test_exporter_creation(self):
        """Test creating exporter with destination."""
        exporter = TelemetryExporter(destination=ExportDestination.PROMETHEUS)
        
        assert exporter.destination == ExportDestination.PROMETHEUS
    
    def test_exporter_console_export(self):
        """Test exporting to console."""
        exporter = TelemetryExporter(destination=ExportDestination.CONSOLE)
        
        metrics = EncounterMetrics(
            encounter_id="enc-exp-001",
            tenant_id="medsys",
            physician_id="dr-smith",
        )
        
        result = exporter.export([metrics])
        
        assert result is True
    
    def test_exporter_timescaledb_config(self):
        """Test exporter with TimescaleDB config."""
        config = {
            "host": "localhost",
            "port": 5432,
            "database": "phoenix_telemetry",
        }
        exporter = TelemetryExporter(
            destination=ExportDestination.TIMESCALEDB,
            config=config
        )
        
        assert exporter.config["host"] == "localhost"
        assert exporter.config["port"] == 5432


class TestTelemetryCollector:
    """Tests for TelemetryCollector."""
    
    def test_collector_start_encounter(self):
        """Test starting an encounter."""
        collector = TelemetryCollector(tenant_id="medsys")
        
        metrics = collector.start_encounter(
            physician_id="dr-smith",
            specialty="Cardiology"
        )
        
        assert metrics.tenant_id == "medsys"
        assert metrics.physician_id == "dr-smith"
        assert metrics.specialty == "Cardiology"
    
    def test_collector_complete_encounter(self):
        """Test completing an encounter."""
        collector = TelemetryCollector(tenant_id="medsys")
        
        metrics = collector.start_encounter(
            physician_id="dr-smith",
            specialty="General"
        )
        
        completed = collector.complete_encounter(
            metrics.encounter_id,
            rating=5
        )
        
        assert completed is not None
        assert completed.phase == EncounterPhase.COMPLETED
    
    def test_collector_with_exporter(self):
        """Test collector with exporter."""
        exporter = TelemetryExporter(destination=ExportDestination.CONSOLE)
        collector = TelemetryCollector(
            tenant_id="medsys",
            exporters=[exporter]
        )
        
        assert len(collector.exporters) == 1
    
    def test_collector_get_stats(self):
        """Test getting collector statistics."""
        collector = TelemetryCollector(tenant_id="medsys")
        
        # Start and complete some encounters
        for i in range(3):
            metrics = collector.start_encounter(
                physician_id=f"dr-{i}",
                specialty="General"
            )
            collector.complete_encounter(metrics.encounter_id, rating=4)
        
        stats = collector.get_stats()
        
        assert stats["total_encounters"] == 3
        assert stats["completed_encounters"] == 3
    
    def test_collector_fail_encounter(self):
        """Test failing an encounter."""
        collector = TelemetryCollector(tenant_id="medsys")
        
        metrics = collector.start_encounter(
            physician_id="dr-smith",
            specialty="General"
        )
        
        failed = collector.fail_encounter(
            metrics.encounter_id,
            error="Network timeout"
        )
        
        assert failed is not None
        assert failed.phase == EncounterPhase.FAILED


# ==============================================================================
# Benchmark Comparator Tests
# ==============================================================================

class TestBenchmarkComparator:
    """Tests for BenchmarkComparator."""
    
    def test_phase2_benchmarks_defined(self):
        """Test Phase 2 benchmarks are properly defined."""
        comparator = BenchmarkComparator(tenant_id="test")
        benchmarks = comparator.PHASE2_BENCHMARKS
        
        assert "time_saved_minutes" in benchmarks
        assert benchmarks["time_saved_minutes"]["value"] == 12.3
        assert benchmarks["physician_satisfaction"]["value"] == 4.3
        assert benchmarks["attack_detection_rate"]["value"] == 0.974
        assert benchmarks["p95_latency_ms"]["value"] == 200.0
        assert benchmarks["ai_acceptance_rate"]["value"] == 0.85
    
    def test_add_encounters(self):
        """Test adding encounters to comparator."""
        comparator = BenchmarkComparator(tenant_id="test")
        
        metrics = EncounterMetrics(
            encounter_id="enc-001",
            tenant_id="test",
            physician_id="dr-smith",
        )
        
        comparator.add_encounter(metrics)
        
        assert len(comparator.encounters) == 1
    
    def test_compare_benchmarks(self):
        """Test comparing benchmarks."""
        comparator = BenchmarkComparator(tenant_id="test")
        
        # Add enough encounters for stats
        for i in range(35):
            metrics = EncounterMetrics(
                encounter_id=f"enc-{i}",
                tenant_id="test",
                physician_id="dr-smith",
            )
            # Set timing data for time saved calculation
            metrics.timing.encounter_opened = datetime.now() - timedelta(minutes=12)
            metrics.timing.encounter_completed = datetime.now()
            metrics.api_latency_p95_ms = 150.0
            
            comparator.add_encounter(metrics)
        
        results = comparator.compare_benchmarks()
        
        assert "time_saved_minutes" in results
        assert isinstance(results["time_saved_minutes"], BenchmarkResult)
    
    def test_generate_report(self):
        """Test generating benchmark report."""
        comparator = BenchmarkComparator(tenant_id="test")
        
        # Add encounters
        for i in range(35):
            metrics = EncounterMetrics(
                encounter_id=f"enc-{i}",
                tenant_id="test",
                physician_id="dr-smith",
            )
            metrics.timing.encounter_opened = datetime.now() - timedelta(minutes=10)
            metrics.timing.encounter_completed = datetime.now()
            comparator.add_encounter(metrics)
        
        report = comparator.generate_report(
            hospital_name="Test Hospital",
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now()
        )
        
        assert report.tenant_id == "test"
        assert report.hospital_name == "Test Hospital"
        assert isinstance(report.overall_status, BenchmarkStatus)


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""
    
    def test_benchmark_result_meeting_target(self):
        """Test result when meeting target."""
        result = BenchmarkResult(
            metric_name="time_saved_minutes",
            metric_label="Time Saved Per Patient",
            phase2_promise=12.3,
            actual_value=12.5,
            delta=0.2,
            delta_percentage=1.6,
            status=BenchmarkStatus.MEETING,
        )
        
        assert result.status == BenchmarkStatus.MEETING
        assert result.actual_value > result.phase2_promise
    
    def test_benchmark_result_exceeding(self):
        """Test result when exceeding target."""
        result = BenchmarkResult(
            metric_name="time_saved_minutes",
            metric_label="Time Saved Per Patient",
            phase2_promise=12.3,
            actual_value=15.0,
            delta=2.7,
            delta_percentage=22.0,
            status=BenchmarkStatus.EXCEEDING,
        )
        
        assert result.status == BenchmarkStatus.EXCEEDING
    
    def test_benchmark_result_below(self):
        """Test result when below target."""
        result = BenchmarkResult(
            metric_name="attack_detection_rate",
            metric_label="Attack Detection Rate",
            phase2_promise=0.974,
            actual_value=0.85,
            delta=-0.124,
            delta_percentage=-12.7,
            status=BenchmarkStatus.BELOW,
        )
        
        assert result.status == BenchmarkStatus.BELOW
        assert result.alert_triggered is True
    
    def test_benchmark_result_to_dict(self):
        """Test serializing result to dict."""
        result = BenchmarkResult(
            metric_name="p95_latency_ms",
            metric_label="P95 API Latency (ms)",
            phase2_promise=200.0,
            actual_value=150.0,
            delta=-50.0,
            delta_percentage=-25.0,
            status=BenchmarkStatus.EXCEEDING,
            higher_is_better=False,
        )
        
        data = result.to_dict()
        
        assert data["metric_name"] == "p95_latency_ms"
        assert data["status"] == "exceeding"


class TestBenchmarkReport:
    """Tests for BenchmarkReport."""
    
    def test_report_creation(self):
        """Test creating benchmark report."""
        report = BenchmarkReport(
            tenant_id="test",
            hospital_name="Test Hospital",
            report_period_start=datetime.now() - timedelta(days=7),
            report_period_end=datetime.now(),
        )
        
        assert report.tenant_id == "test"
        assert report.hospital_name == "Test Hospital"
    
    def test_report_with_results(self):
        """Test report with benchmark results."""
        results = {
            "time_saved_minutes": BenchmarkResult(
                metric_name="time_saved_minutes",
                metric_label="Time Saved",
                phase2_promise=12.3,
                actual_value=13.0,
                delta=0.7,
                delta_percentage=5.7,
                status=BenchmarkStatus.MEETING,
            ),
        }
        
        report = BenchmarkReport(
            tenant_id="test",
            hospital_name="Test Hospital",
            report_period_start=datetime.now() - timedelta(days=7),
            report_period_end=datetime.now(),
            results=results,
        )
        
        assert len(report.results) == 1
        assert report.benchmarks_met == 1
    
    def test_report_overall_status(self):
        """Test report overall status calculation."""
        results = {
            "metric1": BenchmarkResult(
                metric_name="metric1",
                metric_label="Metric 1",
                phase2_promise=10.0,
                actual_value=12.0,
                delta=2.0,
                delta_percentage=20.0,
                status=BenchmarkStatus.EXCEEDING,
            ),
            "metric2": BenchmarkResult(
                metric_name="metric2",
                metric_label="Metric 2",
                phase2_promise=10.0,
                actual_value=11.0,
                delta=1.0,
                delta_percentage=10.0,
                status=BenchmarkStatus.MEETING,
            ),
        }
        
        report = BenchmarkReport(
            tenant_id="test",
            hospital_name="Test Hospital",
            report_period_start=datetime.now() - timedelta(days=7),
            report_period_end=datetime.now(),
            results=results,
        )
        
        # Recalculate with actual results
        report._calculate_overall_status()
        
        assert report.benchmarks_below == 0
    
    def test_report_to_dict(self):
        """Test serializing report to dict."""
        report = BenchmarkReport(
            tenant_id="test",
            hospital_name="Test Hospital",
            report_period_start=datetime.now() - timedelta(days=7),
            report_period_end=datetime.now(),
            total_encounters=100,
            completed_encounters=95,
        )
        
        data = report.to_dict()
        
        assert data["tenant_id"] == "test"
        assert data["total_encounters"] == 100


# ==============================================================================
# Dashboard Feed Tests
# ==============================================================================

class TestLiveMetric:
    """Tests for LiveMetric dataclass."""
    
    def test_live_metric_creation(self):
        """Test creating live metric."""
        metric = LiveMetric(
            metric_type=MetricType.ENCOUNTER_COMPLETED,
            tenant_id="medsys",
            data={"time_saved": 13.2},
        )
        
        assert metric.metric_type == MetricType.ENCOUNTER_COMPLETED
        assert metric.tenant_id == "medsys"
        assert metric.data["time_saved"] == 13.2
    
    def test_live_metric_to_json(self):
        """Test serializing metric to JSON."""
        metric = LiveMetric(
            metric_type=MetricType.BENCHMARK_UPDATE,
            tenant_id="test",
            data={"encounters_active": 42},
        )
        
        json_str = metric.to_json()
        data = json.loads(json_str)
        
        assert data["type"] == "benchmark_update"
        assert "timestamp" in data
    
    def test_live_metric_from_json(self):
        """Test deserializing metric from JSON."""
        json_str = json.dumps({
            "metric_id": "test-123",
            "type": "alert",
            "tenant_id": "medsys",
            "timestamp": datetime.now().isoformat(),
            "data": {"level": "warning"},
        })
        
        metric = LiveMetric.from_json(json_str)
        
        assert metric.metric_type == MetricType.ALERT
        assert metric.tenant_id == "medsys"


class TestMetricSnapshot:
    """Tests for MetricSnapshot."""
    
    def test_snapshot_creation(self):
        """Test creating metric snapshot."""
        snapshot = MetricSnapshot(
            tenant_id="medsys",
            active_encounters=15,
            encounters_today=100,
            average_time_saved_minutes=13.2,
            average_rating=4.4,
        )
        
        assert snapshot.tenant_id == "medsys"
        assert snapshot.active_encounters == 15
        assert snapshot.average_rating == 4.4
    
    def test_snapshot_to_json(self):
        """Test serializing snapshot to JSON."""
        snapshot = MetricSnapshot(
            tenant_id="regional",
            active_encounters=10,
            encounters_today=50,
            p95_latency_ms=145.0,
        )
        
        json_str = snapshot.to_json()
        data = json.loads(json_str)
        
        assert data["tenant_id"] == "regional"
        assert data["encounters"]["active"] == 10
        assert data["performance"]["p95_latency_ms"] == 145.0


class TestStreamSubscription:
    """Tests for StreamSubscription."""
    
    def test_subscription_creation(self):
        """Test creating stream subscription."""
        subscription = StreamSubscription(
            client_id="dashboard-1",
            subscription_type=StreamSubscriptionType.ALL,
            tenant_filter="medsys",
        )
        
        assert subscription.client_id == "dashboard-1"
        assert subscription.subscription_type == StreamSubscriptionType.ALL
        assert subscription.tenant_filter == "medsys"
    
    def test_subscription_matches_metric(self):
        """Test subscription metric matching."""
        subscription = StreamSubscription(
            client_id="dashboard-2",
            subscription_type=StreamSubscriptionType.ENCOUNTERS,
            tenant_filter="medsys",
        )
        
        # Should match encounter events
        metric = LiveMetric(
            metric_type=MetricType.ENCOUNTER_COMPLETED,
            tenant_id="medsys",
        )
        assert subscription.matches(metric) is True
        
        # Should not match wrong tenant
        metric2 = LiveMetric(
            metric_type=MetricType.ENCOUNTER_COMPLETED,
            tenant_id="regional",
        )
        assert subscription.matches(metric2) is False
        
        # Should not match non-encounter events
        metric3 = LiveMetric(
            metric_type=MetricType.ALERT,
            tenant_id="medsys",
        )
        assert subscription.matches(metric3) is False
    
    def test_subscription_all_type(self):
        """Test subscription with ALL type matches everything."""
        subscription = StreamSubscription(
            client_id="admin",
            subscription_type=StreamSubscriptionType.ALL,
        )
        
        for metric_type in MetricType:
            metric = LiveMetric(
                metric_type=metric_type,
                tenant_id="test",
            )
            assert subscription.matches(metric) is True


class TestDashboardFeed:
    """Tests for DashboardFeed."""
    
    def test_feed_creation(self):
        """Test creating dashboard feed."""
        feed = DashboardFeed()
        
        assert feed.get_subscriber_count() == 0
    
    @pytest.mark.asyncio
    async def test_feed_subscribe(self):
        """Test subscribing to feed."""
        feed = DashboardFeed()
        
        async def mock_send(msg):
            pass
        
        subscription = await feed.subscribe(
            client_id="client-001",
            send_callback=mock_send,
        )
        
        assert subscription is not None
        assert feed.get_subscriber_count() == 1
    
    @pytest.mark.asyncio
    async def test_feed_unsubscribe(self):
        """Test unsubscribing from feed."""
        feed = DashboardFeed()
        
        async def mock_send(msg):
            pass
        
        subscription = await feed.subscribe(
            client_id="client-001",
            send_callback=mock_send,
        )
        
        result = feed.unsubscribe(subscription.subscription_id)
        
        assert result is True
        assert feed.get_subscriber_count() == 0
    
    @pytest.mark.asyncio
    async def test_feed_publish_metric(self):
        """Test publishing metric to feed."""
        feed = DashboardFeed()
        
        metric = LiveMetric(
            metric_type=MetricType.ENCOUNTER_COMPLETED,
            tenant_id="medsys",
            data={"time_saved": 13.5},
        )
        
        # Use publish_async in async test
        delivered = await feed.publish_async(metric)
        
        # No subscribers, so delivered should be 0
        assert feed._total_published == 1
    
    @pytest.mark.asyncio
    async def test_feed_publish_async(self):
        """Test async publishing."""
        feed = DashboardFeed()
        received = []
        
        async def mock_send(msg):
            received.append(msg)
        
        await feed.subscribe(
            client_id="client-001",
            send_callback=mock_send,
            subscription_type=StreamSubscriptionType.ALL,
        )
        
        metric = LiveMetric(
            metric_type=MetricType.RATING_RECEIVED,
            tenant_id="test",
            data={"rating": 5},
        )
        
        delivered = await feed.publish_async(metric)
        
        assert delivered == 1
        assert len(received) == 1


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestTelemetryIntegration:
    """Integration tests for telemetry pipeline."""
    
    def test_full_encounter_pipeline(self):
        """Test full encounter metrics pipeline."""
        # Create collector
        collector = TelemetryCollector(tenant_id="medsys")
        
        # Start encounter
        metrics = collector.start_encounter(
            physician_id="dr-smith",
            specialty="Cardiology"
        )
        
        # Record agent invocation
        invocation = AgentInvocation(
            agent_type=AgentType.SCRIBE,
            invoked_at=datetime.now(),
            success=True,
            latency_ms=350,
        )
        collector.record_agent_invocation(metrics.encounter_id, invocation)
        
        # Complete encounter
        completed = collector.complete_encounter(
            metrics.encounter_id,
            rating=5
        )
        
        assert completed is not None
        assert completed.phase == EncounterPhase.COMPLETED
        assert len(completed.agent_invocations) == 1
    
    def test_benchmark_validation_pipeline(self):
        """Test benchmark validation pipeline."""
        comparator = BenchmarkComparator(tenant_id="medsys")
        
        # Add enough encounters
        for i in range(35):
            metrics = EncounterMetrics(
                encounter_id=f"enc-{i}",
                tenant_id="medsys",
                physician_id="dr-smith",
            )
            # Set timing for time saved
            metrics.timing.encounter_opened = datetime.now() - timedelta(minutes=12)
            metrics.timing.encounter_completed = datetime.now()
            metrics.api_latency_p95_ms = 155.0
            metrics.physician_rating = 4
            
            comparator.add_encounter(metrics)
        
        # Compare benchmarks
        results = comparator.compare_benchmarks()
        
        assert "time_saved_minutes" in results
        assert results["time_saved_minutes"].actual_value > 10
    
    def test_collector_stats_pipeline(self):
        """Test collector statistics aggregation."""
        collector = TelemetryCollector(tenant_id="medsys")
        
        # Process multiple encounters
        for i in range(5):
            metrics = collector.start_encounter(
                physician_id=f"dr-{i}",
                specialty="General"
            )
            collector.complete_encounter(metrics.encounter_id, rating=4)
        
        stats = collector.get_stats()
        
        assert stats["total_encounters"] == 5
        assert stats["completed_encounters"] == 5
        assert stats["total_ratings"] == 5
    
    @pytest.mark.asyncio
    async def test_dashboard_feed_pipeline(self):
        """Test dashboard feed pipeline."""
        feed = DashboardFeed()
        received = []
        
        async def on_metric(msg):
            received.append(msg)
        
        await feed.subscribe(
            client_id="exec-dashboard",
            send_callback=on_metric,
            subscription_type=StreamSubscriptionType.ALL,
        )
        
        # Publish metrics
        for metric_type in [MetricType.ENCOUNTER_STARTED, MetricType.ENCOUNTER_COMPLETED]:
            metric = LiveMetric(
                metric_type=metric_type,
                tenant_id="medsys",
                data={"encounter_id": "enc-123"},
            )
            await feed.publish_async(metric)
        
        assert len(received) == 2
