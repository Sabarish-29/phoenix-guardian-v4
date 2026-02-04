"""
Tests for Phoenix Guardian Monitoring Module
Week 19-20: Observability Stack Tests

Tests Prometheus exporters, Grafana dashboards, and alert rules.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import json

from phoenix_guardian.monitoring.prometheus_exporters import (
    PrometheusExporter,
    MetricDefinition,
    MetricType,
    MetricValue,
    PhoenixMetrics,
)
from phoenix_guardian.monitoring.grafana_dashboards import (
    DashboardGenerator,
    GrafanaDashboard,
    DashboardPanel,
    PanelType,
)
from phoenix_guardian.monitoring.alert_rules import (
    AlertRule,
    AlertRuleSet,
    AlertSeverity,
    AlertCategory,
    PhoenixAlertRules,
)


# ==============================================================================
# Metric Type Tests
# ==============================================================================

class TestMetricType:
    """Tests for MetricType enum."""
    
    def test_metric_types_defined(self):
        """Test all metric types are defined."""
        assert MetricType.COUNTER
        assert MetricType.GAUGE
        assert MetricType.HISTOGRAM
        assert MetricType.SUMMARY
    
    def test_metric_type_values(self):
        """Test metric type values."""
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"


# ==============================================================================
# Metric Definition Tests
# ==============================================================================

class TestMetricDefinition:
    """Tests for MetricDefinition."""
    
    def test_create_counter_definition(self):
        """Test creating a counter metric definition."""
        definition = MetricDefinition(
            name="test_counter",
            metric_type=MetricType.COUNTER,
            description="A test counter",
        )
        
        assert definition.name == "test_counter"
        assert definition.metric_type == MetricType.COUNTER
    
    def test_create_histogram_with_buckets(self):
        """Test creating a histogram with buckets."""
        definition = MetricDefinition(
            name="test_histogram",
            metric_type=MetricType.HISTOGRAM,
            description="A test histogram",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0],
        )
        
        assert len(definition.buckets) == 5
    
    def test_metric_with_labels(self):
        """Test metric with labels."""
        definition = MetricDefinition(
            name="test_metric",
            metric_type=MetricType.GAUGE,
            description="Test with labels",
            labels=["tenant_id", "specialty"],
        )
        
        assert "tenant_id" in definition.labels
        assert "specialty" in definition.labels
    
    def test_definition_to_prometheus_format(self):
        """Test generating Prometheus format."""
        definition = MetricDefinition(
            name="test_metric",
            metric_type=MetricType.COUNTER,
            description="Test description",
        )
        
        text = definition.to_prometheus_format()
        assert "# HELP test_metric" in text
        assert "# TYPE test_metric counter" in text


# ==============================================================================
# Metric Value Tests
# ==============================================================================

class TestMetricValue:
    """Tests for MetricValue."""
    
    def test_create_metric_value(self):
        """Test creating a metric value."""
        value = MetricValue(
            name="test_metric",
            value=42.0,
        )
        
        assert value.name == "test_metric"
        assert value.value == 42.0
    
    def test_metric_value_with_labels(self):
        """Test metric value with labels."""
        value = MetricValue(
            name="test_metric",
            value=10.5,
            labels={"tenant_id": "hospital_001", "status": "active"},
        )
        
        assert value.labels["tenant_id"] == "hospital_001"
    
    def test_metric_value_to_prometheus_format(self):
        """Test formatting as Prometheus exposition."""
        value = MetricValue(
            name="test_counter",
            value=100.0,
            labels={"env": "prod"},
        )
        
        text = value.to_prometheus_format()
        assert "test_counter" in text
        assert "100" in text


# ==============================================================================
# Phoenix Metrics Tests  
# ==============================================================================

class TestPhoenixMetrics:
    """Tests for pre-defined Phoenix metrics."""
    
    def test_encounters_metrics_defined(self):
        """Test encounter metrics are defined."""
        assert PhoenixMetrics.ENCOUNTERS_TOTAL
        assert PhoenixMetrics.ENCOUNTERS_ACTIVE
        assert PhoenixMetrics.ENCOUNTER_DURATION_SECONDS
    
    def test_time_saved_metrics_defined(self):
        """Test time saved metrics are defined."""
        assert PhoenixMetrics.TIME_SAVED_MINUTES
        assert PhoenixMetrics.TIME_SAVED_TOTAL_MINUTES
    
    def test_satisfaction_metrics_defined(self):
        """Test satisfaction metrics are defined."""
        assert PhoenixMetrics.PHYSICIAN_RATING
        assert PhoenixMetrics.PHYSICIAN_RATING_AVERAGE
    
    def test_agent_metrics_defined(self):
        """Test agent metrics are defined."""
        assert PhoenixMetrics.AGENT_INVOCATIONS_TOTAL
    
    def test_all_metrics_method(self):
        """Test all_metrics class method."""
        all_metrics = PhoenixMetrics.all_metrics()
        assert len(all_metrics) > 0
        assert all(isinstance(m, MetricDefinition) for m in all_metrics)


# ==============================================================================
# Prometheus Exporter Tests
# ==============================================================================

class TestPrometheusExporter:
    """Tests for PrometheusExporter."""
    
    def test_exporter_creation(self):
        """Test exporter creation."""
        exporter = PrometheusExporter()
        assert exporter is not None
    
    def test_exporter_with_port(self):
        """Test exporter with custom port."""
        exporter = PrometheusExporter(port=9191)
        assert exporter._port == 9191
    
    def test_exporter_with_prefix(self):
        """Test exporter with prefix."""
        exporter = PrometheusExporter(prefix="test_")
        assert exporter._prefix == "test_"
    
    def test_exporter_register_metric(self):
        """Test registering a metric."""
        exporter = PrometheusExporter()
        
        custom_metric = MetricDefinition(
            name="custom_counter",
            metric_type=MetricType.COUNTER,
            description="A custom counter",
        )
        exporter.register_metric(custom_metric)
        
        assert "custom_counter" in exporter._definitions
    
    def test_exporter_inc_counter(self):
        """Test incrementing a counter."""
        exporter = PrometheusExporter()
        
        exporter.inc_counter(
            "phoenix_encounters_total",
            labels={"tenant_id": "medsys", "specialty": "internal", "status": "completed"},
        )
        
        value = exporter.get_counter(
            "phoenix_encounters_total",
            labels={"tenant_id": "medsys", "specialty": "internal", "status": "completed"},
        )
        assert value == 1
    
    def test_exporter_inc_counter_multiple(self):
        """Test incrementing counter multiple times."""
        exporter = PrometheusExporter()
        
        labels = {"tenant_id": "medsys", "specialty": "internal", "status": "completed"}
        exporter.inc_counter("phoenix_encounters_total", labels=labels)
        exporter.inc_counter("phoenix_encounters_total", value=5, labels=labels)
        
        value = exporter.get_counter("phoenix_encounters_total", labels=labels)
        assert value == 6
    
    def test_exporter_set_gauge(self):
        """Test setting a gauge."""
        exporter = PrometheusExporter()
        
        exporter.set_gauge(
            "phoenix_physician_rating_average",
            value=4.5,
            labels={"tenant_id": "medsys"},
        )
        
        value = exporter.get_gauge(
            "phoenix_physician_rating_average",
            labels={"tenant_id": "medsys"},
        )
        assert value == 4.5
    
    def test_exporter_observe_histogram(self):
        """Test observing a histogram value."""
        exporter = PrometheusExporter()
        
        labels = {"tenant_id": "medsys", "specialty": "internal"}
        exporter.observe_histogram(
            "phoenix_time_saved_minutes",
            value=12.5,
            labels=labels,
        )
        
        stats = exporter.get_histogram_stats(
            "phoenix_time_saved_minutes",
            labels=labels,
        )
        assert stats["count"] == 1
        assert stats["sum"] == 12.5


# ==============================================================================
# Panel Type Tests
# ==============================================================================

class TestPanelType:
    """Tests for PanelType enum."""
    
    def test_panel_types_defined(self):
        """Test panel types are defined."""
        assert PanelType.GRAPH
        assert PanelType.STAT
        assert PanelType.GAUGE
        assert PanelType.TABLE
        assert PanelType.TIMESERIES
        assert PanelType.BAR_GAUGE


# ==============================================================================
# Dashboard Panel Tests
# ==============================================================================

class TestDashboardPanel:
    """Tests for DashboardPanel."""
    
    def test_create_stat_panel(self):
        """Test creating a stat panel."""
        panel = DashboardPanel(
            id=1,
            title="Total Encounters",
            panel_type=PanelType.STAT,
            query="sum(phoenix_encounters_total)",
        )
        
        assert panel.id == 1
        assert panel.title == "Total Encounters"
        assert panel.panel_type == PanelType.STAT
    
    def test_create_timeseries_panel(self):
        """Test creating a timeseries panel."""
        panel = DashboardPanel(
            id=2,
            title="Encounter Rate",
            panel_type=PanelType.TIMESERIES,
            query="rate(phoenix_encounters_total[5m])",
            width=24,
            height=10,
        )
        
        assert panel.width == 24
        assert panel.height == 10
    
    def test_panel_with_thresholds(self):
        """Test panel with thresholds."""
        panel = DashboardPanel(
            id=3,
            title="Satisfaction Score",
            panel_type=PanelType.GAUGE,
            query="phoenix_physician_rating_average",
            thresholds=[
                {"color": "red", "value": None},
                {"color": "yellow", "value": 3},
                {"color": "green", "value": 4},
            ],
        )
        
        assert len(panel.thresholds) == 3
    
    def test_panel_to_grafana_json(self):
        """Test converting panel to Grafana JSON format."""
        panel = DashboardPanel(
            id=1,
            title="Test Panel",
            panel_type=PanelType.STAT,
            query="test_metric",
        )
        
        json_data = panel.to_grafana_json()
        assert json_data["id"] == 1
        assert json_data["title"] == "Test Panel"
        assert json_data["type"] == "stat"
        assert "gridPos" in json_data


# ==============================================================================
# Grafana Dashboard Tests
# ==============================================================================

class TestGrafanaDashboard:
    """Tests for GrafanaDashboard."""
    
    def test_create_dashboard(self):
        """Test creating a dashboard."""
        dashboard = GrafanaDashboard(
            uid="test-dashboard",
            title="Test Dashboard",
        )
        
        assert dashboard.uid == "test-dashboard"
        assert dashboard.title == "Test Dashboard"
    
    def test_dashboard_add_panel(self):
        """Test adding panels to dashboard."""
        dashboard = GrafanaDashboard(
            uid="test-dashboard",
            title="Test Dashboard",
        )
        
        panel = DashboardPanel(
            id=1,
            title="Test Panel",
            panel_type=PanelType.STAT,
        )
        dashboard.add_panel(panel)
        
        assert len(dashboard.panels) == 1
    
    def test_dashboard_with_variables(self):
        """Test dashboard with template variables."""
        dashboard = GrafanaDashboard(
            uid="test-dashboard",
            title="Test Dashboard",
            variables=[
                {"name": "tenant_id", "type": "query"},
            ],
        )
        
        assert len(dashboard.variables) == 1
    
    def test_dashboard_to_grafana_json(self):
        """Test converting dashboard to Grafana JSON."""
        dashboard = GrafanaDashboard(
            uid="test-dashboard",
            title="Test Dashboard",
            tags=["test", "monitoring"],
        )
        
        panel = DashboardPanel(
            id=1,
            title="Test Panel",
            panel_type=PanelType.STAT,
            query="test_metric",
        )
        dashboard.add_panel(panel)
        
        json_data = dashboard.to_grafana_json()
        assert json_data["uid"] == "test-dashboard"
        assert json_data["title"] == "Test Dashboard"
        assert len(json_data["panels"]) == 1
    
    def test_dashboard_to_json_string(self):
        """Test exporting dashboard as JSON string."""
        dashboard = GrafanaDashboard(
            uid="test-dashboard",
            title="Test Dashboard",
        )
        
        json_str = dashboard.to_json_string()
        assert isinstance(json_str, str)
        assert "test-dashboard" in json_str


# ==============================================================================
# Dashboard Generator Tests
# ==============================================================================

class TestDashboardGenerator:
    """Tests for DashboardGenerator."""
    
    def test_generator_creation(self):
        """Test generator creation."""
        generator = DashboardGenerator()
        assert generator is not None
    
    def test_generator_with_datasource(self):
        """Test generator with custom datasource."""
        generator = DashboardGenerator(datasource="CustomPrometheus")
        assert generator._datasource == "CustomPrometheus"
    
    def test_generate_executive_dashboard(self):
        """Test generating executive dashboard."""
        generator = DashboardGenerator()
        dashboard = generator.create_executive_dashboard()
        
        assert dashboard.uid == "phoenix-executive"
        assert "Executive" in dashboard.title
        assert len(dashboard.panels) > 0
    
    def test_generate_operations_dashboard(self):
        """Test generating operations dashboard."""
        generator = DashboardGenerator()
        dashboard = generator.create_operations_dashboard()
        
        assert dashboard.uid == "phoenix-operations"
        assert len(dashboard.panels) > 0
    
    def test_generate_pilot_hospital_dashboard(self):
        """Test generating pilot hospital dashboard."""
        generator = DashboardGenerator()
        dashboard = generator.create_pilot_hospital_dashboard(
            hospital_id="medsys",
            hospital_name="Medsys Hospital",
        )
        
        assert "medsys" in dashboard.uid
        assert "Medsys Hospital" in dashboard.title


# ==============================================================================
# Alert Severity Tests
# ==============================================================================

class TestAlertSeverity:
    """Tests for AlertSeverity enum."""
    
    def test_severity_values(self):
        """Test alert severity values."""
        assert AlertSeverity.CRITICAL
        assert AlertSeverity.HIGH
        assert AlertSeverity.WARNING
        assert AlertSeverity.INFO


# ==============================================================================
# Alert Category Tests
# ==============================================================================

class TestAlertCategory:
    """Tests for AlertCategory enum."""
    
    def test_category_values(self):
        """Test alert category values."""
        assert AlertCategory.AVAILABILITY
        assert AlertCategory.PERFORMANCE
        assert AlertCategory.SECURITY
        assert AlertCategory.QUALITY
        assert AlertCategory.SLA


# ==============================================================================
# Alert Rule Tests
# ==============================================================================

class TestAlertRule:
    """Tests for AlertRule."""
    
    def test_create_alert_rule(self):
        """Test creating an alert rule."""
        rule = AlertRule(
            name="HighLatency",
            expression="phoenix_agent_latency_p95_seconds > 0.2",
            severity=AlertSeverity.WARNING,
            summary="High latency detected",
            description="P95 latency exceeds 200ms threshold",
            category=AlertCategory.PERFORMANCE,
        )
        
        assert rule.name == "HighLatency"
        assert rule.severity == AlertSeverity.WARNING
    
    def test_alert_rule_with_labels(self):
        """Test alert rule with labels."""
        rule = AlertRule(
            name="ServiceDown",
            expression="up == 0",
            severity=AlertSeverity.CRITICAL,
            summary="Service is down",
            description="A service is not responding",
            category=AlertCategory.AVAILABILITY,
            labels={"team": "platform", "environment": "production"},
        )
        
        assert rule.labels["team"] == "platform"
    
    def test_alert_rule_with_duration(self):
        """Test alert rule with 'for' duration."""
        rule = AlertRule(
            name="HighErrorRate",
            expression="rate(errors_total[5m]) > 0.1",
            severity=AlertSeverity.HIGH,
            summary="High error rate",
            description="Error rate exceeds 10%",
            category=AlertCategory.AVAILABILITY,
            for_duration="5m",
        )
        
        assert rule.for_duration == "5m"


# ==============================================================================
# Alert Rule Set Tests
# ==============================================================================

class TestAlertRuleSet:
    """Tests for AlertRuleSet."""
    
    def test_create_ruleset(self):
        """Test creating an alert rule set."""
        ruleset = AlertRuleSet(
            name="phoenix-alerts",
            rules=[],
        )
        
        assert ruleset.name == "phoenix-alerts"
    
    def test_ruleset_add_rule(self):
        """Test adding rules to a ruleset."""
        ruleset = AlertRuleSet(name="test-alerts", rules=[])
        
        rule = AlertRule(
            name="TestAlert",
            expression="test_metric > 100",
            severity=AlertSeverity.WARNING,
            summary="Test alert triggered",
            description="Test metric exceeded threshold",
            category=AlertCategory.PERFORMANCE,
        )
        ruleset.add_rule(rule)
        
        assert len(ruleset.rules) == 1
    
    def test_ruleset_to_prometheus_format(self):
        """Test exporting ruleset in Prometheus format."""
        ruleset = AlertRuleSet(name="test-alerts", rules=[])
        
        rule = AlertRule(
            name="TestAlert",
            expression="test_metric > 100",
            severity=AlertSeverity.WARNING,
            summary="Test alert",
            description="Test description",
            category=AlertCategory.PERFORMANCE,
        )
        ruleset.add_rule(rule)
        
        output = ruleset.to_yaml_string()
        assert "test-alerts" in output
        assert "TestAlert" in output


# ==============================================================================
# Phoenix Alert Rules Tests
# ==============================================================================

class TestPhoenixAlertRules:
    """Tests for pre-defined Phoenix alert rules."""
    
    def test_benchmark_rules_defined(self):
        """Test benchmark alert rules are defined."""
        alert_rules = PhoenixAlertRules()
        ruleset = alert_rules.get_benchmark_rules()
        assert len(ruleset.rules) > 0
    
    def test_performance_rules_defined(self):
        """Test performance alerts are defined."""
        alert_rules = PhoenixAlertRules()
        ruleset = alert_rules.get_performance_rules()
        assert len(ruleset.rules) > 0
    
    def test_security_rules_defined(self):
        """Test security alerts are defined."""
        alert_rules = PhoenixAlertRules()
        ruleset = alert_rules.get_security_rules()
        assert len(ruleset.rules) > 0
    
    def test_all_rule_sets(self):
        """Test getting all rule sets."""
        alert_rules = PhoenixAlertRules()
        all_rulesets = alert_rules.get_all_rule_sets()
        assert len(all_rulesets) > 0


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestMonitoringIntegration:
    """Integration tests for monitoring module."""
    
    def test_exporter_with_phoenix_metrics(self):
        """Test exporter with Phoenix metrics."""
        exporter = PrometheusExporter()
        
        # Record various metrics
        exporter.inc_counter(
            "phoenix_encounters_total",
            labels={"tenant_id": "medsys", "specialty": "internal", "status": "completed"},
        )
        exporter.set_gauge(
            "phoenix_physician_rating_average",
            value=4.3,
            labels={"tenant_id": "medsys"},
        )
        exporter.observe_histogram(
            "phoenix_time_saved_minutes",
            value=12.5,
            labels={"tenant_id": "medsys", "specialty": "internal"},
        )
        
        # Verify
        counter = exporter.get_counter(
            "phoenix_encounters_total",
            labels={"tenant_id": "medsys", "specialty": "internal", "status": "completed"},
        )
        assert counter == 1
    
    def test_dashboard_with_multiple_panels(self):
        """Test dashboard with multiple panels."""
        dashboard = GrafanaDashboard(
            uid="test-dashboard",
            title="Multi-Panel Dashboard",
        )
        
        panels = [
            DashboardPanel(
                id=1,
                title="Encounters",
                panel_type=PanelType.STAT,
                query="sum(phoenix_encounters_total)",
                x=0, y=0,
            ),
            DashboardPanel(
                id=2,
                title="Satisfaction",
                panel_type=PanelType.GAUGE,
                query="phoenix_physician_rating_average",
                x=12, y=0,
            ),
            DashboardPanel(
                id=3,
                title="Time Saved Trend",
                panel_type=PanelType.TIMESERIES,
                query="phoenix_time_saved_minutes",
                x=0, y=8, width=24,
            ),
        ]
        
        for panel in panels:
            dashboard.add_panel(panel)
        
        assert len(dashboard.panels) == 3
        
        json_data = dashboard.to_grafana_json()
        assert len(json_data["panels"]) == 3
    
    def test_complete_alert_ruleset(self):
        """Test creating a complete alert ruleset."""
        ruleset = AlertRuleSet(name="phoenix-production-alerts", rules=[])
        
        # Add various alerts
        rules = [
            AlertRule(
                name="EncounterSLABreach",
                expression="phoenix_encounter_sla_breach_total > 0",
                severity=AlertSeverity.CRITICAL,
                summary="SLA breach detected",
                description="Encounter SLA has been breached",
                category=AlertCategory.SLA,
                for_duration="5m",
            ),
            AlertRule(
                name="HighLatency",
                expression="histogram_quantile(0.95, phoenix_agent_latency_seconds) > 0.2",
                severity=AlertSeverity.WARNING,
                summary="High latency detected",
                description="P95 latency exceeds threshold",
                category=AlertCategory.PERFORMANCE,
                for_duration="10m",
            ),
            AlertRule(
                name="LowSatisfaction",
                expression="phoenix_physician_rating_average < 4.0",
                severity=AlertSeverity.WARNING,
                summary="Low satisfaction score",
                description="Physician satisfaction below target",
                category=AlertCategory.QUALITY,
                for_duration="1h",
            ),
        ]
        
        for rule in rules:
            ruleset.add_rule(rule)
        
        assert len(ruleset.rules) == 3
        
        output = ruleset.to_yaml_string()
        assert "EncounterSLABreach" in output
        assert "HighLatency" in output
