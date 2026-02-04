"""
Phoenix Guardian - Prometheus Exporters
Custom Prometheus metrics for Phoenix Guardian pilot monitoring.

Exports the key Phase 2 validation metrics to Prometheus.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class MetricType(Enum):
    """Prometheus metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class MetricDefinition:
    """
    Definition of a Prometheus metric.
    """
    name: str
    metric_type: MetricType
    description: str
    labels: List[str] = field(default_factory=list)
    buckets: Optional[List[float]] = None    # For histograms
    
    def to_prometheus_format(self) -> str:
        """Generate Prometheus metric definition."""
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} {self.metric_type.value}",
        ]
        return "\n".join(lines)


@dataclass
class MetricValue:
    """
    A metric value with labels.
    """
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: Optional[float] = None
    
    def to_prometheus_format(self) -> str:
        """Format as Prometheus exposition format."""
        if self.labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in self.labels.items())
            metric_line = f"{self.name}{{{label_str}}} {self.value}"
        else:
            metric_line = f"{self.name} {self.value}"
        
        if self.timestamp:
            metric_line += f" {int(self.timestamp * 1000)}"
        
        return metric_line


# ==============================================================================
# Phoenix Metrics Definitions
# ==============================================================================

class PhoenixMetrics:
    """
    Pre-defined Phoenix Guardian metrics.
    
    These metrics track the Phase 2 validation promises.
    """
    
    # Encounter metrics
    ENCOUNTERS_TOTAL = MetricDefinition(
        name="phoenix_encounters_total",
        metric_type=MetricType.COUNTER,
        description="Total number of encounters processed",
        labels=["tenant_id", "specialty", "status"],
    )
    
    ENCOUNTERS_ACTIVE = MetricDefinition(
        name="phoenix_encounters_active",
        metric_type=MetricType.GAUGE,
        description="Number of currently active encounters",
        labels=["tenant_id"],
    )
    
    ENCOUNTER_DURATION_SECONDS = MetricDefinition(
        name="phoenix_encounter_duration_seconds",
        metric_type=MetricType.HISTOGRAM,
        description="Duration of encounters in seconds",
        labels=["tenant_id", "specialty"],
        buckets=[60, 120, 300, 600, 900, 1200, 1800, 3600],
    )
    
    # Time saved (key Phase 2 metric: 12.3 minutes)
    TIME_SAVED_MINUTES = MetricDefinition(
        name="phoenix_time_saved_minutes",
        metric_type=MetricType.HISTOGRAM,
        description="Documentation time saved per encounter in minutes",
        labels=["tenant_id", "specialty"],
        buckets=[0, 5, 10, 12, 15, 20, 25, 30],
    )
    
    TIME_SAVED_TOTAL_MINUTES = MetricDefinition(
        name="phoenix_time_saved_total_minutes",
        metric_type=MetricType.COUNTER,
        description="Total documentation time saved in minutes",
        labels=["tenant_id"],
    )
    
    # Satisfaction (key Phase 2 metric: 4.3/5)
    PHYSICIAN_RATING = MetricDefinition(
        name="phoenix_physician_rating",
        metric_type=MetricType.HISTOGRAM,
        description="Physician satisfaction rating (1-5)",
        labels=["tenant_id", "specialty"],
        buckets=[1, 2, 3, 4, 5],
    )
    
    PHYSICIAN_RATING_AVERAGE = MetricDefinition(
        name="phoenix_physician_rating_average",
        metric_type=MetricType.GAUGE,
        description="Average physician satisfaction rating",
        labels=["tenant_id"],
    )
    
    # Agent performance
    AGENT_INVOCATIONS_TOTAL = MetricDefinition(
        name="phoenix_agent_invocations_total",
        metric_type=MetricType.COUNTER,
        description="Total agent invocations",
        labels=["tenant_id", "agent_type", "status"],
    )
    
    AGENT_LATENCY_SECONDS = MetricDefinition(
        name="phoenix_agent_latency_seconds",
        metric_type=MetricType.HISTOGRAM,
        description="Agent response latency in seconds",
        labels=["tenant_id", "agent_type"],
        buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0],
    )
    
    # P95 latency (key Phase 2 metric: < 200ms)
    REQUEST_LATENCY_SECONDS = MetricDefinition(
        name="phoenix_request_latency_seconds",
        metric_type=MetricType.HISTOGRAM,
        description="End-to-end request latency in seconds",
        labels=["tenant_id", "endpoint"],
        buckets=[0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.0],
    )
    
    # Security metrics (key Phase 2 metric: 97.4% detection)
    SECURITY_EVENTS_TOTAL = MetricDefinition(
        name="phoenix_security_events_total",
        metric_type=MetricType.COUNTER,
        description="Total security events detected",
        labels=["tenant_id", "event_type", "blocked"],
    )
    
    ATTACK_DETECTION_RATE = MetricDefinition(
        name="phoenix_attack_detection_rate",
        metric_type=MetricType.GAUGE,
        description="Current attack detection rate (0-1)",
        labels=["tenant_id"],
    )
    
    FALSE_POSITIVES_TOTAL = MetricDefinition(
        name="phoenix_false_positives_total",
        metric_type=MetricType.COUNTER,
        description="Total false positive security events",
        labels=["tenant_id", "attack_type"],
    )
    
    # AI acceptance (key Phase 2 metric: 85%)
    AI_SUGGESTIONS_TOTAL = MetricDefinition(
        name="phoenix_ai_suggestions_total",
        metric_type=MetricType.COUNTER,
        description="Total AI suggestions made",
        labels=["tenant_id", "agent_type"],
    )
    
    AI_SUGGESTIONS_ACCEPTED = MetricDefinition(
        name="phoenix_ai_suggestions_accepted_total",
        metric_type=MetricType.COUNTER,
        description="Total AI suggestions accepted by physicians",
        labels=["tenant_id", "agent_type"],
    )
    
    AI_ACCEPTANCE_RATE = MetricDefinition(
        name="phoenix_ai_acceptance_rate",
        metric_type=MetricType.GAUGE,
        description="Current AI suggestion acceptance rate (0-1)",
        labels=["tenant_id"],
    )
    
    # SOAP note quality
    SOAP_QUALITY_SCORE = MetricDefinition(
        name="phoenix_soap_quality_score",
        metric_type=MetricType.HISTOGRAM,
        description="SOAP note quality score (0-1)",
        labels=["tenant_id", "section"],
        buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0],
    )
    
    # Feedback
    FEEDBACK_TOTAL = MetricDefinition(
        name="phoenix_feedback_total",
        metric_type=MetricType.COUNTER,
        description="Total feedback submissions",
        labels=["tenant_id", "feedback_type", "sentiment"],
    )
    
    # Incidents
    INCIDENTS_TOTAL = MetricDefinition(
        name="phoenix_incidents_total",
        metric_type=MetricType.COUNTER,
        description="Total incidents",
        labels=["tenant_id", "priority", "type"],
    )
    
    INCIDENTS_ACTIVE = MetricDefinition(
        name="phoenix_incidents_active",
        metric_type=MetricType.GAUGE,
        description="Currently active incidents",
        labels=["tenant_id", "priority"],
    )
    
    @classmethod
    def all_metrics(cls) -> List[MetricDefinition]:
        """Get all metric definitions."""
        return [
            cls.ENCOUNTERS_TOTAL,
            cls.ENCOUNTERS_ACTIVE,
            cls.ENCOUNTER_DURATION_SECONDS,
            cls.TIME_SAVED_MINUTES,
            cls.TIME_SAVED_TOTAL_MINUTES,
            cls.PHYSICIAN_RATING,
            cls.PHYSICIAN_RATING_AVERAGE,
            cls.AGENT_INVOCATIONS_TOTAL,
            cls.AGENT_LATENCY_SECONDS,
            cls.REQUEST_LATENCY_SECONDS,
            cls.SECURITY_EVENTS_TOTAL,
            cls.ATTACK_DETECTION_RATE,
            cls.FALSE_POSITIVES_TOTAL,
            cls.AI_SUGGESTIONS_TOTAL,
            cls.AI_SUGGESTIONS_ACCEPTED,
            cls.AI_ACCEPTANCE_RATE,
            cls.SOAP_QUALITY_SCORE,
            cls.FEEDBACK_TOTAL,
            cls.INCIDENTS_TOTAL,
            cls.INCIDENTS_ACTIVE,
        ]


# ==============================================================================
# Prometheus Exporter
# ==============================================================================

class PrometheusExporter:
    """
    Prometheus metrics exporter for Phoenix Guardian.
    
    Example:
        exporter = PrometheusExporter(port=9090)
        
        # Record metrics
        exporter.inc_counter(
            "phoenix_encounters_total",
            labels={"tenant_id": "hospital_001", "specialty": "internal_medicine", "status": "completed"}
        )
        
        exporter.observe_histogram(
            "phoenix_time_saved_minutes",
            value=14.5,
            labels={"tenant_id": "hospital_001", "specialty": "internal_medicine"}
        )
        
        exporter.set_gauge(
            "phoenix_physician_rating_average",
            value=4.5,
            labels={"tenant_id": "hospital_001"}
        )
        
        # Get exposition format
        metrics_text = exporter.get_metrics()
        
        # Or start HTTP server
        exporter.start_server()
    """
    
    def __init__(self, port: int = 9090, prefix: str = ""):
        self._port = port
        self._prefix = prefix
        
        # Metric storage
        self._counters: Dict[str, Dict[str, float]] = {}
        self._gauges: Dict[str, Dict[str, float]] = {}
        self._histograms: Dict[str, Dict[str, List[float]]] = {}
        
        # Metric definitions
        self._definitions: Dict[str, MetricDefinition] = {}
        
        # Register Phoenix metrics
        for metric in PhoenixMetrics.all_metrics():
            self.register_metric(metric)
        
        # Server reference
        self._server = None
    
    def register_metric(self, definition: MetricDefinition) -> None:
        """Register a metric definition."""
        name = self._prefix + definition.name if self._prefix else definition.name
        self._definitions[name] = definition
        
        if definition.metric_type == MetricType.COUNTER:
            self._counters[name] = {}
        elif definition.metric_type == MetricType.GAUGE:
            self._gauges[name] = {}
        elif definition.metric_type in [MetricType.HISTOGRAM, MetricType.SUMMARY]:
            self._histograms[name] = {}
    
    def _labels_key(self, labels: Dict[str, str]) -> str:
        """Create a key from labels."""
        if not labels:
            return ""
        return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    
    # =========================================================================
    # Counter Operations
    # =========================================================================
    
    def inc_counter(
        self,
        name: str,
        value: float = 1,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment a counter."""
        name = self._prefix + name if self._prefix else name
        key = self._labels_key(labels or {})
        
        if name not in self._counters:
            self._counters[name] = {}
        
        self._counters[name][key] = self._counters[name].get(key, 0) + value
    
    def get_counter(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> float:
        """Get counter value."""
        name = self._prefix + name if self._prefix else name
        key = self._labels_key(labels or {})
        return self._counters.get(name, {}).get(key, 0)
    
    # =========================================================================
    # Gauge Operations
    # =========================================================================
    
    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set a gauge value."""
        name = self._prefix + name if self._prefix else name
        key = self._labels_key(labels or {})
        
        if name not in self._gauges:
            self._gauges[name] = {}
        
        self._gauges[name][key] = value
    
    def inc_gauge(
        self,
        name: str,
        value: float = 1,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment a gauge."""
        name = self._prefix + name if self._prefix else name
        key = self._labels_key(labels or {})
        
        if name not in self._gauges:
            self._gauges[name] = {}
        
        self._gauges[name][key] = self._gauges[name].get(key, 0) + value
    
    def dec_gauge(
        self,
        name: str,
        value: float = 1,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Decrement a gauge."""
        self.inc_gauge(name, -value, labels)
    
    def get_gauge(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> float:
        """Get gauge value."""
        name = self._prefix + name if self._prefix else name
        key = self._labels_key(labels or {})
        return self._gauges.get(name, {}).get(key, 0)
    
    # =========================================================================
    # Histogram Operations
    # =========================================================================
    
    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a histogram observation."""
        name = self._prefix + name if self._prefix else name
        key = self._labels_key(labels or {})
        
        if name not in self._histograms:
            self._histograms[name] = {}
        
        if key not in self._histograms[name]:
            self._histograms[name][key] = []
        
        self._histograms[name][key].append(value)
    
    def get_histogram_stats(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> Dict[str, float]:
        """Get histogram statistics."""
        name = self._prefix + name if self._prefix else name
        key = self._labels_key(labels or {})
        
        observations = self._histograms.get(name, {}).get(key, [])
        
        if not observations:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
        
        return {
            "count": len(observations),
            "sum": sum(observations),
            "avg": sum(observations) / len(observations),
            "min": min(observations),
            "max": max(observations),
        }
    
    # =========================================================================
    # Exposition
    # =========================================================================
    
    def get_metrics(self) -> str:
        """
        Get all metrics in Prometheus exposition format.
        
        This is what /metrics endpoint returns.
        """
        lines = []
        
        # Counters
        for name, values in self._counters.items():
            definition = self._definitions.get(name)
            if definition:
                lines.append(definition.to_prometheus_format())
            
            for labels_key, value in values.items():
                if labels_key:
                    lines.append(f"{name}{{{labels_key}}} {value}")
                else:
                    lines.append(f"{name} {value}")
            lines.append("")
        
        # Gauges
        for name, values in self._gauges.items():
            definition = self._definitions.get(name)
            if definition:
                lines.append(definition.to_prometheus_format())
            
            for labels_key, value in values.items():
                if labels_key:
                    lines.append(f"{name}{{{labels_key}}} {value}")
                else:
                    lines.append(f"{name} {value}")
            lines.append("")
        
        # Histograms
        for name, values in self._histograms.items():
            definition = self._definitions.get(name)
            if definition:
                lines.append(definition.to_prometheus_format())
            
            buckets = definition.buckets if definition else [0.1, 0.5, 1.0, 5.0, 10.0]
            
            for labels_key, observations in values.items():
                if not observations:
                    continue
                
                # Generate bucket counts
                for bucket in buckets:
                    count = sum(1 for o in observations if o <= bucket)
                    if labels_key:
                        lines.append(f'{name}_bucket{{{labels_key},le="{bucket}"}} {count}')
                    else:
                        lines.append(f'{name}_bucket{{le="{bucket}"}} {count}')
                
                # +Inf bucket
                if labels_key:
                    lines.append(f'{name}_bucket{{{labels_key},le="+Inf"}} {len(observations)}')
                    lines.append(f'{name}_sum{{{labels_key}}} {sum(observations)}')
                    lines.append(f'{name}_count{{{labels_key}}} {len(observations)}')
                else:
                    lines.append(f'{name}_bucket{{le="+Inf"}} {len(observations)}')
                    lines.append(f'{name}_sum {sum(observations)}')
                    lines.append(f'{name}_count {len(observations)}')
            
            lines.append("")
        
        return "\n".join(lines)
    
    # =========================================================================
    # HTTP Server
    # =========================================================================
    
    def start_server(self) -> None:
        """
        Start HTTP server for /metrics endpoint.
        
        Note: In production, use prometheus_client library.
        This is a simplified implementation for testing.
        """
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            
            exporter = self
            
            class MetricsHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == "/metrics":
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(exporter.get_metrics().encode())
                    else:
                        self.send_response(404)
                        self.end_headers()
                
                def log_message(self, format, *args):
                    pass  # Suppress logging
            
            self._server = HTTPServer(("", self._port), MetricsHandler)
            logger.info(f"Prometheus exporter started on port {self._port}")
            self._server.serve_forever()
            
        except Exception as e:
            logger.error(f"Failed to start Prometheus server: {e}")
    
    def stop_server(self) -> None:
        """Stop the HTTP server."""
        if self._server:
            self._server.shutdown()
            logger.info("Prometheus exporter stopped")
    
    # =========================================================================
    # Convenience Methods for Phoenix Metrics
    # =========================================================================
    
    def record_encounter_completed(
        self,
        tenant_id: str,
        specialty: str,
        duration_seconds: float,
        time_saved_minutes: float,
        rating: Optional[int] = None,
    ) -> None:
        """Record encounter completion metrics."""
        labels = {"tenant_id": tenant_id, "specialty": specialty, "status": "completed"}
        
        self.inc_counter("phoenix_encounters_total", labels=labels)
        self.observe_histogram("phoenix_encounter_duration_seconds", duration_seconds, 
                              labels={"tenant_id": tenant_id, "specialty": specialty})
        self.observe_histogram("phoenix_time_saved_minutes", time_saved_minutes,
                              labels={"tenant_id": tenant_id, "specialty": specialty})
        self.inc_counter("phoenix_time_saved_total_minutes", time_saved_minutes,
                        labels={"tenant_id": tenant_id})
        
        if rating is not None:
            self.observe_histogram("phoenix_physician_rating", float(rating),
                                  labels={"tenant_id": tenant_id, "specialty": specialty})
    
    def record_agent_invocation(
        self,
        tenant_id: str,
        agent_type: str,
        latency_seconds: float,
        success: bool,
    ) -> None:
        """Record agent invocation metrics."""
        status = "success" if success else "failure"
        
        self.inc_counter("phoenix_agent_invocations_total",
                        labels={"tenant_id": tenant_id, "agent_type": agent_type, "status": status})
        self.observe_histogram("phoenix_agent_latency_seconds", latency_seconds,
                              labels={"tenant_id": tenant_id, "agent_type": agent_type})
    
    def record_security_event(
        self,
        tenant_id: str,
        event_type: str,
        blocked: bool,
        is_false_positive: bool = False,
    ) -> None:
        """Record security event metrics."""
        self.inc_counter("phoenix_security_events_total",
                        labels={"tenant_id": tenant_id, "event_type": event_type, 
                               "blocked": str(blocked).lower()})
        
        if is_false_positive:
            self.inc_counter("phoenix_false_positives_total",
                            labels={"tenant_id": tenant_id, "attack_type": event_type})
    
    def update_benchmark_gauges(
        self,
        tenant_id: str,
        avg_rating: float,
        detection_rate: float,
        acceptance_rate: float,
        active_encounters: int,
    ) -> None:
        """Update benchmark gauge metrics."""
        self.set_gauge("phoenix_physician_rating_average", avg_rating,
                      labels={"tenant_id": tenant_id})
        self.set_gauge("phoenix_attack_detection_rate", detection_rate,
                      labels={"tenant_id": tenant_id})
        self.set_gauge("phoenix_ai_acceptance_rate", acceptance_rate,
                      labels={"tenant_id": tenant_id})
        self.set_gauge("phoenix_encounters_active", float(active_encounters),
                      labels={"tenant_id": tenant_id})
