"""
Phoenix Guardian - Grafana Dashboards
Programmatic Grafana dashboard generation for pilot monitoring.

Creates dashboards for Phase 2 validation metrics.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class PanelType(Enum):
    """Grafana panel types."""
    GRAPH = "graph"
    STAT = "stat"
    GAUGE = "gauge"
    TABLE = "table"
    HEATMAP = "heatmap"
    TEXT = "text"
    TIMESERIES = "timeseries"
    BAR_GAUGE = "bargauge"
    PIE = "piechart"


class DashboardTheme(Enum):
    """Dashboard color themes."""
    DARK = "dark"
    LIGHT = "light"


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class DashboardPanel:
    """
    A single Grafana panel.
    """
    id: int
    title: str
    panel_type: PanelType
    
    # Grid position
    x: int = 0
    y: int = 0
    width: int = 12
    height: int = 8
    
    # Query
    query: str = ""
    datasource: str = "Prometheus"
    legend: str = ""
    
    # Display options
    unit: str = ""                           # e.g., "s", "percent", "short"
    decimals: int = 2
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    
    # Thresholds for gauge/stat
    thresholds: List[Dict[str, Any]] = field(default_factory=list)
    
    # Colors
    colors: List[str] = field(default_factory=list)
    
    # Description
    description: str = ""
    
    def to_grafana_json(self) -> Dict[str, Any]:
        """Convert to Grafana JSON format."""
        panel = {
            "id": self.id,
            "title": self.title,
            "type": self.panel_type.value,
            "gridPos": {
                "x": self.x,
                "y": self.y,
                "w": self.width,
                "h": self.height,
            },
            "datasource": self.datasource,
            "description": self.description,
        }
        
        # Add targets (queries)
        if self.query:
            panel["targets"] = [{
                "expr": self.query,
                "legendFormat": self.legend,
                "refId": "A",
            }]
        
        # Field config for stat/gauge panels
        if self.panel_type in [PanelType.STAT, PanelType.GAUGE, PanelType.BAR_GAUGE]:
            panel["fieldConfig"] = {
                "defaults": {
                    "unit": self.unit,
                    "decimals": self.decimals,
                    "thresholds": {
                        "mode": "absolute",
                        "steps": self.thresholds or [
                            {"color": "red", "value": None},
                            {"color": "yellow", "value": 50},
                            {"color": "green", "value": 80},
                        ],
                    },
                },
            }
            
            if self.min_val is not None:
                panel["fieldConfig"]["defaults"]["min"] = self.min_val
            if self.max_val is not None:
                panel["fieldConfig"]["defaults"]["max"] = self.max_val
        
        # Options for timeseries
        if self.panel_type == PanelType.TIMESERIES:
            panel["options"] = {
                "legend": {"displayMode": "list", "placement": "bottom"},
                "tooltip": {"mode": "multi"},
            }
        
        return panel


@dataclass
class GrafanaDashboard:
    """
    A complete Grafana dashboard.
    """
    uid: str
    title: str
    
    panels: List[DashboardPanel] = field(default_factory=list)
    
    # Dashboard settings
    refresh: str = "30s"
    time_from: str = "now-1h"
    time_to: str = "now"
    timezone: str = "browser"
    
    # Variables/templating
    variables: List[Dict[str, Any]] = field(default_factory=list)
    
    # Tags
    tags: List[str] = field(default_factory=list)
    
    # Annotations
    annotations: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_panel(self, panel: DashboardPanel) -> None:
        """Add a panel to the dashboard."""
        self.panels.append(panel)
    
    def to_grafana_json(self) -> Dict[str, Any]:
        """Convert to Grafana JSON format."""
        return {
            "uid": self.uid,
            "title": self.title,
            "tags": self.tags,
            "timezone": self.timezone,
            "schemaVersion": 38,
            "refresh": self.refresh,
            "time": {
                "from": self.time_from,
                "to": self.time_to,
            },
            "panels": [p.to_grafana_json() for p in self.panels],
            "templating": {
                "list": self.variables,
            },
            "annotations": {
                "list": self.annotations,
            },
        }
    
    def to_json_string(self, indent: int = 2) -> str:
        """Export as JSON string."""
        return json.dumps(self.to_grafana_json(), indent=indent)


# ==============================================================================
# Dashboard Generator
# ==============================================================================

class DashboardGenerator:
    """
    Generates pre-built Grafana dashboards for Phoenix Guardian.
    
    Example:
        generator = DashboardGenerator()
        
        # Generate executive dashboard
        exec_dashboard = generator.create_executive_dashboard()
        
        # Generate operations dashboard
        ops_dashboard = generator.create_operations_dashboard()
        
        # Export to JSON
        with open("dashboard.json", "w") as f:
            f.write(exec_dashboard.to_json_string())
    """
    
    def __init__(self, datasource: str = "Prometheus"):
        self._datasource = datasource
        self._panel_id_counter = 1
    
    def _next_panel_id(self) -> int:
        """Get next panel ID."""
        pid = self._panel_id_counter
        self._panel_id_counter += 1
        return pid
    
    # =========================================================================
    # Executive Dashboard
    # =========================================================================
    
    def create_executive_dashboard(
        self,
        tenant_filter: str = ".*",
    ) -> GrafanaDashboard:
        """
        Create executive overview dashboard.
        
        Shows high-level Phase 2 validation metrics.
        """
        dashboard = GrafanaDashboard(
            uid="phoenix-executive",
            title="Phoenix Guardian - Executive Overview",
            tags=["phoenix", "executive", "pilot"],
            refresh="1m",
            time_from="now-24h",
        )
        
        # Variables
        dashboard.variables = [
            {
                "name": "tenant_id",
                "type": "query",
                "query": 'label_values(phoenix_encounters_total, tenant_id)',
                "refresh": 2,
                "includeAll": True,
                "current": {"text": "All", "value": "$__all"},
            },
        ]
        
        # Row 1: Key Metrics (stat panels)
        y_pos = 0
        
        # Encounters Today
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Encounters Today",
            panel_type=PanelType.STAT,
            x=0, y=y_pos, width=6, height=4,
            query='sum(increase(phoenix_encounters_total{tenant_id=~"$tenant_id"}[24h]))',
            unit="short",
            thresholds=[
                {"color": "blue", "value": None},
            ],
        ))
        
        # Time Saved (vs 12.3 min target)
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Avg Time Saved (Target: 12.3 min)",
            panel_type=PanelType.GAUGE,
            x=6, y=y_pos, width=6, height=4,
            query='avg(phoenix_time_saved_minutes_sum{tenant_id=~"$tenant_id"} / phoenix_time_saved_minutes_count{tenant_id=~"$tenant_id"})',
            unit="m",
            min_val=0,
            max_val=25,
            thresholds=[
                {"color": "red", "value": None},
                {"color": "yellow", "value": 10},
                {"color": "green", "value": 12.3},
            ],
        ))
        
        # Physician Satisfaction (vs 4.3 target)
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Physician Satisfaction (Target: 4.3/5)",
            panel_type=PanelType.GAUGE,
            x=12, y=y_pos, width=6, height=4,
            query='avg(phoenix_physician_rating_average{tenant_id=~"$tenant_id"})',
            unit="short",
            min_val=1,
            max_val=5,
            thresholds=[
                {"color": "red", "value": None},
                {"color": "yellow", "value": 3.5},
                {"color": "green", "value": 4.3},
            ],
        ))
        
        # Attack Detection (vs 97.4% target)
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Attack Detection Rate (Target: 97.4%)",
            panel_type=PanelType.GAUGE,
            x=18, y=y_pos, width=6, height=4,
            query='avg(phoenix_attack_detection_rate{tenant_id=~"$tenant_id"}) * 100',
            unit="percent",
            min_val=0,
            max_val=100,
            thresholds=[
                {"color": "red", "value": None},
                {"color": "yellow", "value": 90},
                {"color": "green", "value": 97.4},
            ],
        ))
        
        # Row 2: Trends
        y_pos = 4
        
        # Time Saved Trend
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Time Saved Trend",
            panel_type=PanelType.TIMESERIES,
            x=0, y=y_pos, width=12, height=8,
            query='avg(rate(phoenix_time_saved_minutes_sum{tenant_id=~"$tenant_id"}[5m]) / rate(phoenix_time_saved_minutes_count{tenant_id=~"$tenant_id"}[5m]))',
            unit="m",
            legend="{{tenant_id}}",
        ))
        
        # Satisfaction Trend
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Satisfaction Trend",
            panel_type=PanelType.TIMESERIES,
            x=12, y=y_pos, width=12, height=8,
            query='phoenix_physician_rating_average{tenant_id=~"$tenant_id"}',
            unit="short",
            legend="{{tenant_id}}",
        ))
        
        # Row 3: More metrics
        y_pos = 12
        
        # P95 Latency
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="P95 Latency (Target: <200ms)",
            panel_type=PanelType.STAT,
            x=0, y=y_pos, width=6, height=4,
            query='histogram_quantile(0.95, sum(rate(phoenix_request_latency_seconds_bucket{tenant_id=~"$tenant_id"}[5m])) by (le)) * 1000',
            unit="ms",
            thresholds=[
                {"color": "green", "value": None},
                {"color": "yellow", "value": 150},
                {"color": "red", "value": 200},
            ],
        ))
        
        # AI Acceptance Rate
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="AI Acceptance Rate (Target: 85%)",
            panel_type=PanelType.GAUGE,
            x=6, y=y_pos, width=6, height=4,
            query='avg(phoenix_ai_acceptance_rate{tenant_id=~"$tenant_id"}) * 100',
            unit="percent",
            min_val=0,
            max_val=100,
            thresholds=[
                {"color": "red", "value": None},
                {"color": "yellow", "value": 70},
                {"color": "green", "value": 85},
            ],
        ))
        
        # False Positives Today
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="False Positives (24h)",
            panel_type=PanelType.STAT,
            x=12, y=y_pos, width=6, height=4,
            query='sum(increase(phoenix_false_positives_total{tenant_id=~"$tenant_id"}[24h]))',
            unit="short",
            thresholds=[
                {"color": "green", "value": None},
                {"color": "yellow", "value": 5},
                {"color": "red", "value": 10},
            ],
        ))
        
        # Active Incidents
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Active Incidents",
            panel_type=PanelType.STAT,
            x=18, y=y_pos, width=6, height=4,
            query='sum(phoenix_incidents_active{tenant_id=~"$tenant_id"})',
            unit="short",
            thresholds=[
                {"color": "green", "value": None},
                {"color": "yellow", "value": 1},
                {"color": "red", "value": 3},
            ],
        ))
        
        return dashboard
    
    # =========================================================================
    # Operations Dashboard
    # =========================================================================
    
    def create_operations_dashboard(
        self,
        tenant_filter: str = ".*",
    ) -> GrafanaDashboard:
        """
        Create operations dashboard for on-call engineers.
        
        Shows detailed operational metrics and alerts.
        """
        dashboard = GrafanaDashboard(
            uid="phoenix-operations",
            title="Phoenix Guardian - Operations",
            tags=["phoenix", "operations", "oncall"],
            refresh="10s",
            time_from="now-1h",
        )
        
        # Variables
        dashboard.variables = [
            {
                "name": "tenant_id",
                "type": "query",
                "query": 'label_values(phoenix_encounters_total, tenant_id)',
                "refresh": 2,
                "includeAll": True,
            },
            {
                "name": "agent_type",
                "type": "query",
                "query": 'label_values(phoenix_agent_invocations_total, agent_type)',
                "refresh": 2,
                "includeAll": True,
            },
        ]
        
        y_pos = 0
        
        # Row 1: Real-time status
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Active Encounters",
            panel_type=PanelType.STAT,
            x=0, y=y_pos, width=4, height=4,
            query='sum(phoenix_encounters_active{tenant_id=~"$tenant_id"})',
            unit="short",
        ))
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Encounters/min",
            panel_type=PanelType.STAT,
            x=4, y=y_pos, width=4, height=4,
            query='sum(rate(phoenix_encounters_total{tenant_id=~"$tenant_id"}[1m])) * 60',
            unit="short",
        ))
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Error Rate",
            panel_type=PanelType.STAT,
            x=8, y=y_pos, width=4, height=4,
            query='sum(rate(phoenix_agent_invocations_total{tenant_id=~"$tenant_id",status="failure"}[5m])) / sum(rate(phoenix_agent_invocations_total{tenant_id=~"$tenant_id"}[5m])) * 100',
            unit="percent",
            thresholds=[
                {"color": "green", "value": None},
                {"color": "yellow", "value": 1},
                {"color": "red", "value": 5},
            ],
        ))
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="P95 Latency",
            panel_type=PanelType.STAT,
            x=12, y=y_pos, width=4, height=4,
            query='histogram_quantile(0.95, sum(rate(phoenix_request_latency_seconds_bucket{tenant_id=~"$tenant_id"}[5m])) by (le)) * 1000',
            unit="ms",
            thresholds=[
                {"color": "green", "value": None},
                {"color": "yellow", "value": 150},
                {"color": "red", "value": 200},
            ],
        ))
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="P99 Latency",
            panel_type=PanelType.STAT,
            x=16, y=y_pos, width=4, height=4,
            query='histogram_quantile(0.99, sum(rate(phoenix_request_latency_seconds_bucket{tenant_id=~"$tenant_id"}[5m])) by (le)) * 1000',
            unit="ms",
            thresholds=[
                {"color": "green", "value": None},
                {"color": "yellow", "value": 300},
                {"color": "red", "value": 500},
            ],
        ))
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Security Events/min",
            panel_type=PanelType.STAT,
            x=20, y=y_pos, width=4, height=4,
            query='sum(rate(phoenix_security_events_total{tenant_id=~"$tenant_id"}[1m])) * 60',
            unit="short",
        ))
        
        # Row 2: Latency details
        y_pos = 4
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Request Latency Distribution",
            panel_type=PanelType.HEATMAP,
            x=0, y=y_pos, width=12, height=8,
            query='sum(rate(phoenix_request_latency_seconds_bucket{tenant_id=~"$tenant_id"}[5m])) by (le)',
            unit="s",
        ))
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Agent Latency by Type",
            panel_type=PanelType.TIMESERIES,
            x=12, y=y_pos, width=12, height=8,
            query='histogram_quantile(0.95, sum(rate(phoenix_agent_latency_seconds_bucket{tenant_id=~"$tenant_id",agent_type=~"$agent_type"}[5m])) by (le, agent_type)) * 1000',
            unit="ms",
            legend="{{agent_type}}",
        ))
        
        # Row 3: Agent performance
        y_pos = 12
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Agent Invocations by Type",
            panel_type=PanelType.TIMESERIES,
            x=0, y=y_pos, width=12, height=6,
            query='sum(rate(phoenix_agent_invocations_total{tenant_id=~"$tenant_id",agent_type=~"$agent_type"}[5m])) by (agent_type) * 60',
            unit="short",
            legend="{{agent_type}}",
        ))
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Agent Success Rate by Type",
            panel_type=PanelType.TIMESERIES,
            x=12, y=y_pos, width=12, height=6,
            query='sum(rate(phoenix_agent_invocations_total{tenant_id=~"$tenant_id",agent_type=~"$agent_type",status="success"}[5m])) by (agent_type) / sum(rate(phoenix_agent_invocations_total{tenant_id=~"$tenant_id",agent_type=~"$agent_type"}[5m])) by (agent_type) * 100',
            unit="percent",
            legend="{{agent_type}}",
        ))
        
        return dashboard
    
    # =========================================================================
    # Security Dashboard
    # =========================================================================
    
    def create_security_dashboard(self) -> GrafanaDashboard:
        """
        Create security monitoring dashboard.
        
        Tracks attack detection and false positives.
        """
        dashboard = GrafanaDashboard(
            uid="phoenix-security",
            title="Phoenix Guardian - Security",
            tags=["phoenix", "security", "sentinelq"],
            refresh="30s",
            time_from="now-6h",
        )
        
        dashboard.variables = [
            {
                "name": "tenant_id",
                "type": "query",
                "query": 'label_values(phoenix_security_events_total, tenant_id)',
                "refresh": 2,
                "includeAll": True,
            },
        ]
        
        y_pos = 0
        
        # Key security stats
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Detection Rate",
            panel_type=PanelType.GAUGE,
            x=0, y=y_pos, width=6, height=4,
            query='avg(phoenix_attack_detection_rate{tenant_id=~"$tenant_id"}) * 100',
            unit="percent",
            min_val=0,
            max_val=100,
            thresholds=[
                {"color": "red", "value": None},
                {"color": "yellow", "value": 90},
                {"color": "green", "value": 97.4},
            ],
        ))
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Attacks Blocked (24h)",
            panel_type=PanelType.STAT,
            x=6, y=y_pos, width=6, height=4,
            query='sum(increase(phoenix_security_events_total{tenant_id=~"$tenant_id",blocked="true"}[24h]))',
            unit="short",
        ))
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="False Positives (24h)",
            panel_type=PanelType.STAT,
            x=12, y=y_pos, width=6, height=4,
            query='sum(increase(phoenix_false_positives_total{tenant_id=~"$tenant_id"}[24h]))',
            unit="short",
            thresholds=[
                {"color": "green", "value": None},
                {"color": "yellow", "value": 5},
                {"color": "red", "value": 10},
            ],
        ))
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="FP Rate",
            panel_type=PanelType.STAT,
            x=18, y=y_pos, width=6, height=4,
            query='sum(increase(phoenix_false_positives_total{tenant_id=~"$tenant_id"}[24h])) / sum(increase(phoenix_security_events_total{tenant_id=~"$tenant_id",blocked="true"}[24h])) * 100',
            unit="percent",
            thresholds=[
                {"color": "green", "value": None},
                {"color": "yellow", "value": 3},
                {"color": "red", "value": 5},
            ],
        ))
        
        # Security events over time
        y_pos = 4
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Security Events by Type",
            panel_type=PanelType.TIMESERIES,
            x=0, y=y_pos, width=24, height=8,
            query='sum(rate(phoenix_security_events_total{tenant_id=~"$tenant_id"}[5m])) by (event_type) * 60',
            unit="short",
            legend="{{event_type}}",
        ))
        
        return dashboard
    
    # =========================================================================
    # Pilot Hospital Dashboard
    # =========================================================================
    
    def create_pilot_hospital_dashboard(
        self,
        hospital_id: str,
        hospital_name: str,
    ) -> GrafanaDashboard:
        """
        Create dashboard for a specific pilot hospital.
        """
        dashboard = GrafanaDashboard(
            uid=f"phoenix-{hospital_id}",
            title=f"Phoenix Guardian - {hospital_name}",
            tags=["phoenix", "pilot", hospital_id],
            refresh="30s",
            time_from="now-24h",
        )
        
        y_pos = 0
        
        # Hospital-specific metrics with fixed tenant filter
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title=f"{hospital_name} - Encounters Today",
            panel_type=PanelType.STAT,
            x=0, y=y_pos, width=6, height=4,
            query=f'sum(increase(phoenix_encounters_total{{tenant_id="{hospital_id}"}}[24h]))',
            unit="short",
        ))
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Time Saved (min)",
            panel_type=PanelType.GAUGE,
            x=6, y=y_pos, width=6, height=4,
            query=f'avg(phoenix_time_saved_minutes_sum{{tenant_id="{hospital_id}"}} / phoenix_time_saved_minutes_count{{tenant_id="{hospital_id}"}})',
            unit="m",
            min_val=0,
            max_val=25,
            thresholds=[
                {"color": "red", "value": None},
                {"color": "yellow", "value": 10},
                {"color": "green", "value": 12.3},
            ],
        ))
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="Satisfaction",
            panel_type=PanelType.GAUGE,
            x=12, y=y_pos, width=6, height=4,
            query=f'avg(phoenix_physician_rating_average{{tenant_id="{hospital_id}"}})',
            unit="short",
            min_val=1,
            max_val=5,
            thresholds=[
                {"color": "red", "value": None},
                {"color": "yellow", "value": 3.5},
                {"color": "green", "value": 4.3},
            ],
        ))
        
        dashboard.add_panel(DashboardPanel(
            id=self._next_panel_id(),
            title="P95 Latency (ms)",
            panel_type=PanelType.STAT,
            x=18, y=y_pos, width=6, height=4,
            query=f'histogram_quantile(0.95, sum(rate(phoenix_request_latency_seconds_bucket{{tenant_id="{hospital_id}"}}[5m])) by (le)) * 1000',
            unit="ms",
            thresholds=[
                {"color": "green", "value": None},
                {"color": "yellow", "value": 150},
                {"color": "red", "value": 200},
            ],
        ))
        
        return dashboard
    
    # =========================================================================
    # Export All Dashboards
    # =========================================================================
    
    def export_all_dashboards(self) -> Dict[str, str]:
        """
        Export all dashboards as JSON strings.
        
        Returns dict of {dashboard_uid: json_string}.
        """
        dashboards = {
            "executive": self.create_executive_dashboard(),
            "operations": self.create_operations_dashboard(),
            "security": self.create_security_dashboard(),
        }
        
        return {
            uid: dashboard.to_json_string()
            for uid, dashboard in dashboards.items()
        }
