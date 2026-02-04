"""
Phoenix Guardian - Telemetry Module
Real-time metrics collection and benchmark validation for pilot deployments.

This module provides:
- EncounterMetrics: Complete metrics for physician-patient encounters
- TelemetryCollector: Capture and store telemetry data
- BenchmarkComparator: Validate Phase 2 promises against actual metrics
- DashboardFeed: WebSocket streaming for live dashboards
"""

from phoenix_guardian.telemetry.encounter_metrics import (
    EncounterMetrics,
    EncounterPhase,
    AgentInvocation,
    SecurityEvent,
    TimingBreakdown,
)
from phoenix_guardian.telemetry.telemetry_collector import (
    TelemetryCollector,
    TelemetryBuffer,
    TelemetryExporter,
)
from phoenix_guardian.telemetry.benchmark_comparator import (
    BenchmarkComparator,
    BenchmarkResult,
    BenchmarkStatus,
)
from phoenix_guardian.telemetry.dashboard_feed import (
    DashboardFeed,
    MetricSnapshot,
    LiveMetric,
)

__all__ = [
    # Encounter Metrics
    "EncounterMetrics",
    "EncounterPhase",
    "AgentInvocation",
    "SecurityEvent",
    "TimingBreakdown",
    # Telemetry Collector
    "TelemetryCollector",
    "TelemetryBuffer",
    "TelemetryExporter",
    # Benchmark Comparator
    "BenchmarkComparator",
    "BenchmarkResult",
    "BenchmarkStatus",
    # Dashboard Feed
    "DashboardFeed",
    "MetricSnapshot",
    "LiveMetric",
]
