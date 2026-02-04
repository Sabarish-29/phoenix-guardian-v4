"""
Phoenix Guardian - Advanced Observability
Sprint 69-70: OpenTelemetry Integration

Distributed tracing, metrics, and logging with OpenTelemetry.
"""

import asyncio
import functools
import logging
import os
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

# OpenTelemetry imports
from opentelemetry import trace, metrics, baggage
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import Status, StatusCode, SpanKind

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class ServiceType(Enum):
    """Service types for semantic conventions."""
    
    API = "api"
    WORKER = "worker"
    ML_INFERENCE = "ml_inference"
    FEDERATED_TRAINER = "federated_trainer"
    CDS_ENGINE = "cds_engine"


@dataclass
class TracingConfig:
    """Configuration for distributed tracing."""
    
    # Service identification
    service_name: str = "phoenix-guardian"
    service_version: str = "5.0.0"
    service_type: ServiceType = ServiceType.API
    environment: str = "production"
    
    # OTLP exporter settings
    otlp_endpoint: str = "http://otel-collector:4317"
    otlp_insecure: bool = True
    
    # Sampling
    sample_rate: float = 1.0  # 100% for now, adjust in production
    
    # Batch processing
    batch_size: int = 512
    export_timeout_ms: int = 30000
    
    # Custom attributes
    hospital_id: Optional[str] = None
    region: str = "us-east-1"
    
    def get_resource(self) -> Resource:
        """Create OpenTelemetry resource with service attributes."""
        attributes = {
            SERVICE_NAME: self.service_name,
            SERVICE_VERSION: self.service_version,
            "service.type": self.service_type.value,
            "deployment.environment": self.environment,
            "cloud.region": self.region,
            "cloud.provider": "aws",
        }
        
        if self.hospital_id:
            attributes["phoenix.hospital_id"] = self.hospital_id
        
        return Resource.create(attributes)


class PhoenixTracer:
    """
    Centralized tracer for Phoenix Guardian.
    
    Provides distributed tracing with healthcare-specific conventions.
    """
    
    def __init__(self, config: TracingConfig):
        self.config = config
        self._tracer: Optional[trace.Tracer] = None
        self._meter: Optional[metrics.Meter] = None
        self._initialized = False
    
    def initialize(self) -> None:
        """Initialize OpenTelemetry with OTLP export."""
        if self._initialized:
            return
        
        resource = self.config.get_resource()
        
        # Configure tracer provider
        tracer_provider = TracerProvider(resource=resource)
        
        # Add OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=self.config.otlp_endpoint,
            insecure=self.config.otlp_insecure,
        )
        
        span_processor = BatchSpanProcessor(
            otlp_exporter,
            max_queue_size=self.config.batch_size * 2,
            max_export_batch_size=self.config.batch_size,
            export_timeout_millis=self.config.export_timeout_ms,
        )
        
        tracer_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(tracer_provider)
        
        # Configure meter provider
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(
                endpoint=self.config.otlp_endpoint,
                insecure=self.config.otlp_insecure,
            ),
            export_interval_millis=60000,  # Export every minute
        )
        
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader],
        )
        metrics.set_meter_provider(meter_provider)
        
        # Set B3 propagation for cross-service tracing
        set_global_textmap(B3MultiFormat())
        
        # Get tracer and meter
        self._tracer = trace.get_tracer(
            self.config.service_name,
            self.config.service_version,
        )
        self._meter = metrics.get_meter(
            self.config.service_name,
            self.config.service_version,
        )
        
        self._initialized = True
        logger.info(f"OpenTelemetry initialized for {self.config.service_name}")
    
    @property
    def tracer(self) -> trace.Tracer:
        """Get the tracer instance."""
        if not self._initialized:
            self.initialize()
        return self._tracer
    
    @property
    def meter(self) -> metrics.Meter:
        """Get the meter instance."""
        if not self._initialized:
            self.initialize()
        return self._meter
    
    def instrument_fastapi(self, app) -> None:
        """Instrument FastAPI application."""
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/health,/ready,/metrics",
        )
        logger.info("FastAPI instrumented")
    
    def instrument_sqlalchemy(self, engine) -> None:
        """Instrument SQLAlchemy engine."""
        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.info("SQLAlchemy instrumented")
    
    def instrument_redis(self) -> None:
        """Instrument Redis client."""
        RedisInstrumentor().instrument()
        logger.info("Redis instrumented")
    
    def instrument_httpx(self) -> None:
        """Instrument HTTPX client."""
        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX instrumented")
    
    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[dict[str, Any]] = None,
    ):
        """Create a tracing span context manager."""
        with self.tracer.start_as_current_span(
            name,
            kind=kind,
            attributes=attributes or {},
        ) as span:
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    
    @asynccontextmanager
    async def async_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[dict[str, Any]] = None,
    ):
        """Create an async tracing span context manager."""
        with self.tracer.start_as_current_span(
            name,
            kind=kind,
            attributes=attributes or {},
        ) as span:
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise


# =============================================================================
# HEALTHCARE-SPECIFIC SEMANTIC CONVENTIONS
# =============================================================================

class HealthcareSpanAttributes:
    """Healthcare-specific span attributes following semantic conventions."""
    
    # Patient context (anonymized IDs only)
    PATIENT_ID_HASH = "phoenix.patient.id_hash"
    ENCOUNTER_ID = "phoenix.encounter.id"
    
    # SOAP note processing
    SOAP_NOTE_ID = "phoenix.soap.note_id"
    SOAP_SECTION = "phoenix.soap.section"
    SOAP_GENERATION_TIME_MS = "phoenix.soap.generation_time_ms"
    
    # ML inference
    MODEL_ID = "phoenix.ml.model_id"
    MODEL_VERSION = "phoenix.ml.model_version"
    INFERENCE_TIME_MS = "phoenix.ml.inference_time_ms"
    TOKEN_COUNT = "phoenix.ml.token_count"
    
    # Federated learning
    FL_ROUND = "phoenix.fl.round"
    FL_HOSPITALS = "phoenix.fl.hospital_count"
    FL_EPSILON = "phoenix.fl.epsilon"
    FL_DELTA = "phoenix.fl.delta"
    
    # CDS
    CDS_HOOK = "phoenix.cds.hook"
    CDS_CARDS_GENERATED = "phoenix.cds.cards_count"
    CDS_RULES_EVALUATED = "phoenix.cds.rules_evaluated"
    
    # Tenant context
    HOSPITAL_ID = "phoenix.hospital.id"
    HOSPITAL_NAME = "phoenix.hospital.name"
    TENANT_TIER = "phoenix.tenant.tier"
    
    # Compliance
    HIPAA_AUDIT_ID = "phoenix.hipaa.audit_id"
    PHI_ACCESSED = "phoenix.hipaa.phi_accessed"


# =============================================================================
# CUSTOM METRICS
# =============================================================================

class PhoenixMetrics:
    """Custom metrics for Phoenix Guardian."""
    
    def __init__(self, tracer: PhoenixTracer):
        self.tracer = tracer
        self._counters: dict[str, metrics.Counter] = {}
        self._histograms: dict[str, metrics.Histogram] = {}
        self._gauges: dict[str, metrics.ObservableGauge] = {}
    
    def _get_counter(self, name: str, description: str, unit: str = "1") -> metrics.Counter:
        """Get or create a counter."""
        if name not in self._counters:
            self._counters[name] = self.tracer.meter.create_counter(
                name=name,
                description=description,
                unit=unit,
            )
        return self._counters[name]
    
    def _get_histogram(self, name: str, description: str, unit: str = "ms") -> metrics.Histogram:
        """Get or create a histogram."""
        if name not in self._histograms:
            self._histograms[name] = self.tracer.meter.create_histogram(
                name=name,
                description=description,
                unit=unit,
            )
        return self._histograms[name]
    
    # SOAP Note Metrics
    def record_soap_generation(
        self,
        duration_ms: float,
        hospital_id: str,
        section: str,
        success: bool,
    ) -> None:
        """Record SOAP note generation metrics."""
        attributes = {
            "hospital_id": hospital_id,
            "section": section,
            "success": str(success),
        }
        
        histogram = self._get_histogram(
            "phoenix.soap.generation_duration",
            "Time to generate SOAP note section",
        )
        histogram.record(duration_ms, attributes)
        
        counter = self._get_counter(
            "phoenix.soap.generations_total",
            "Total SOAP note generations",
        )
        counter.add(1, attributes)
    
    # ML Inference Metrics
    def record_inference(
        self,
        model_id: str,
        duration_ms: float,
        tokens: int,
        success: bool,
    ) -> None:
        """Record ML inference metrics."""
        attributes = {
            "model_id": model_id,
            "success": str(success),
        }
        
        # Latency histogram
        histogram = self._get_histogram(
            "phoenix.ml.inference_duration",
            "ML inference duration",
        )
        histogram.record(duration_ms, attributes)
        
        # Token histogram
        token_histogram = self._get_histogram(
            "phoenix.ml.tokens_processed",
            "Tokens processed per inference",
            unit="tokens",
        )
        token_histogram.record(tokens, attributes)
        
        # Counter
        counter = self._get_counter(
            "phoenix.ml.inferences_total",
            "Total ML inferences",
        )
        counter.add(1, attributes)
    
    # Federated Learning Metrics
    def record_fl_round(
        self,
        round_number: int,
        hospital_count: int,
        epsilon_spent: float,
        duration_s: float,
    ) -> None:
        """Record federated learning round metrics."""
        attributes = {
            "round": str(round_number),
            "hospitals": str(hospital_count),
        }
        
        # Duration
        histogram = self._get_histogram(
            "phoenix.fl.round_duration",
            "Federated learning round duration",
            unit="s",
        )
        histogram.record(duration_s, attributes)
        
        # Epsilon histogram
        epsilon_histogram = self._get_histogram(
            "phoenix.fl.epsilon_per_round",
            "Privacy epsilon spent per round",
            unit="epsilon",
        )
        epsilon_histogram.record(epsilon_spent, attributes)
        
        # Round counter
        counter = self._get_counter(
            "phoenix.fl.rounds_total",
            "Total federated learning rounds",
        )
        counter.add(1, attributes)
    
    # CDS Metrics
    def record_cds_evaluation(
        self,
        hook: str,
        cards_generated: int,
        rules_evaluated: int,
        duration_ms: float,
    ) -> None:
        """Record CDS evaluation metrics."""
        attributes = {
            "hook": hook,
        }
        
        # Duration
        histogram = self._get_histogram(
            "phoenix.cds.evaluation_duration",
            "CDS hook evaluation duration",
        )
        histogram.record(duration_ms, attributes)
        
        # Cards histogram
        cards_histogram = self._get_histogram(
            "phoenix.cds.cards_per_evaluation",
            "CDS cards generated per evaluation",
            unit="cards",
        )
        cards_histogram.record(cards_generated, attributes)
        
        # Counter
        counter = self._get_counter(
            "phoenix.cds.evaluations_total",
            "Total CDS evaluations",
        )
        counter.add(1, attributes)
    
    # Request Metrics
    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        hospital_id: Optional[str] = None,
    ) -> None:
        """Record HTTP request metrics."""
        attributes = {
            "method": method,
            "path": path,
            "status_code": str(status_code),
        }
        if hospital_id:
            attributes["hospital_id"] = hospital_id
        
        # Duration
        histogram = self._get_histogram(
            "phoenix.http.request_duration",
            "HTTP request duration",
        )
        histogram.record(duration_ms, attributes)
        
        # Counter
        counter = self._get_counter(
            "phoenix.http.requests_total",
            "Total HTTP requests",
        )
        counter.add(1, attributes)


# =============================================================================
# SLO/SLI MONITORING
# =============================================================================

@dataclass
class SLO:
    """Service Level Objective definition."""
    
    name: str
    description: str
    target: float  # Target percentage (e.g., 99.9)
    window_days: int = 30
    
    # Metric to track
    metric_name: str = ""
    good_events_filter: str = ""
    total_events_filter: str = ""


class SLOMonitor:
    """
    Monitor Service Level Objectives.
    
    Tracks SLIs and alerts on SLO violations.
    """
    
    # Phoenix Guardian SLOs
    SLOS = [
        SLO(
            name="api_availability",
            description="API availability (successful responses)",
            target=99.9,
            metric_name="phoenix.http.requests_total",
            good_events_filter="status_code=~'2..'",
        ),
        SLO(
            name="soap_generation_latency",
            description="SOAP generation under 5 seconds",
            target=95.0,
            metric_name="phoenix.soap.generation_duration",
        ),
        SLO(
            name="ml_inference_latency",
            description="ML inference under 2 seconds",
            target=99.0,
            metric_name="phoenix.ml.inference_duration",
        ),
        SLO(
            name="cds_evaluation_latency",
            description="CDS evaluation under 500ms",
            target=99.5,
            metric_name="phoenix.cds.evaluation_duration",
        ),
    ]
    
    def __init__(self, metrics: PhoenixMetrics):
        self.metrics = metrics
        self._error_budgets: dict[str, float] = {}
    
    def calculate_error_budget(self, slo: SLO, current_sli: float) -> float:
        """
        Calculate remaining error budget.
        
        Error budget = 100% - SLO target
        Remaining = Error budget - (100% - current SLI)
        """
        error_budget = 100.0 - slo.target
        consumed = 100.0 - current_sli
        remaining = error_budget - consumed
        
        return max(0.0, remaining)
    
    def get_slo_status(self) -> list[dict[str, Any]]:
        """Get current SLO status for all objectives."""
        # In production, this would query Prometheus/CloudWatch
        return [
            {
                "name": slo.name,
                "target": slo.target,
                "window_days": slo.window_days,
                "current_sli": 99.95,  # Placeholder
                "error_budget_remaining": 0.05,
            }
            for slo in self.SLOS
        ]


# =============================================================================
# DECORATORS FOR AUTOMATIC TRACING
# =============================================================================

def traced(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[dict[str, Any]] = None,
):
    """
    Decorator for automatic tracing of functions.
    
    Usage:
        @traced("my_operation")
        def my_function():
            pass
    """
    def decorator(func: F) -> F:
        span_name = name or func.__name__
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(
                span_name,
                kind=kind,
                attributes=attributes or {},
            ) as span:
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(
                span_name,
                kind=kind,
                attributes=attributes or {},
            ) as span:
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def traced_soap_generation(section: str):
    """Decorator for SOAP generation tracing with healthcare semantics."""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            
            # Extract context from args/kwargs
            hospital_id = kwargs.get("hospital_id", "unknown")
            patient_hash = kwargs.get("patient_hash", "")
            
            attributes = {
                HealthcareSpanAttributes.SOAP_SECTION: section,
                HealthcareSpanAttributes.HOSPITAL_ID: hospital_id,
            }
            if patient_hash:
                attributes[HealthcareSpanAttributes.PATIENT_ID_HASH] = patient_hash
            
            with tracer.start_as_current_span(
                f"soap.generate.{section}",
                kind=SpanKind.INTERNAL,
                attributes=attributes,
            ) as span:
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    
                    duration_ms = (time.time() - start_time) * 1000
                    span.set_attribute(
                        HealthcareSpanAttributes.SOAP_GENERATION_TIME_MS,
                        duration_ms,
                    )
                    
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator


# =============================================================================
# FACTORY AND SINGLETON
# =============================================================================

_tracer_instance: Optional[PhoenixTracer] = None
_metrics_instance: Optional[PhoenixMetrics] = None


def get_tracer(config: Optional[TracingConfig] = None) -> PhoenixTracer:
    """Get or create the global tracer instance."""
    global _tracer_instance
    
    if _tracer_instance is None:
        if config is None:
            config = TracingConfig(
                service_name=os.getenv("OTEL_SERVICE_NAME", "phoenix-guardian"),
                service_version=os.getenv("SERVICE_VERSION", "5.0.0"),
                otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
                environment=os.getenv("ENVIRONMENT", "production"),
                region=os.getenv("AWS_REGION", "us-east-1"),
            )
        _tracer_instance = PhoenixTracer(config)
        _tracer_instance.initialize()
    
    return _tracer_instance


def get_metrics() -> PhoenixMetrics:
    """Get or create the global metrics instance."""
    global _metrics_instance
    
    if _metrics_instance is None:
        tracer = get_tracer()
        _metrics_instance = PhoenixMetrics(tracer)
    
    return _metrics_instance


# =============================================================================
# FASTAPI MIDDLEWARE
# =============================================================================

def create_observability_middleware():
    """Create FastAPI middleware for observability."""
    from fastapi import Request
    from starlette.middleware.base import BaseHTTPMiddleware
    
    class ObservabilityMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            tracer = get_tracer()
            metrics = get_metrics()
            
            start_time = time.time()
            
            # Extract tenant context
            hospital_id = request.headers.get("X-Hospital-ID")
            
            # Add to baggage for propagation
            if hospital_id:
                ctx = baggage.set_baggage("hospital_id", hospital_id)
            
            response = await call_next(request)
            
            # Record metrics
            duration_ms = (time.time() - start_time) * 1000
            metrics.record_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                hospital_id=hospital_id,
            )
            
            return response
    
    return ObservabilityMiddleware
