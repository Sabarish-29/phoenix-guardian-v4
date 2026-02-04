"""
Phoenix Guardian - Telemetry Collector
Capture, buffer, and export telemetry data from pilot deployments.

This module provides:
- TelemetryBuffer: In-memory buffer with automatic flushing
- TelemetryCollector: Main interface for capturing metrics
- TelemetryExporter: Export to various backends (Prometheus, TimescaleDB)
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import logging
import threading
import time
from collections import defaultdict

from phoenix_guardian.telemetry.encounter_metrics import (
    EncounterMetrics,
    EncounterPhase,
    AgentInvocation,
    SecurityEvent,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class ExportDestination(Enum):
    """Telemetry export destinations."""
    PROMETHEUS = "prometheus"
    TIMESCALEDB = "timescaledb"
    KAFKA = "kafka"
    ELASTICSEARCH = "elasticsearch"
    CONSOLE = "console"


class BufferFlushTrigger(Enum):
    """What triggers a buffer flush."""
    SIZE = "size"                # Buffer reached size limit
    TIME = "time"                # Time interval elapsed
    MANUAL = "manual"            # Manual flush request
    SHUTDOWN = "shutdown"        # System shutdown


# ==============================================================================
# Telemetry Buffer
# ==============================================================================

@dataclass
class BufferConfig:
    """Configuration for telemetry buffer."""
    max_size: int = 1000                      # Max items before flush
    flush_interval_seconds: int = 30          # Flush every N seconds
    retry_on_failure: bool = True
    max_retries: int = 3
    retry_delay_seconds: float = 1.0


class TelemetryBuffer:
    """
    In-memory buffer for telemetry data with automatic flushing.
    
    Batches telemetry for efficient export to backends.
    Thread-safe for concurrent access.
    """
    
    def __init__(
        self,
        config: Optional[BufferConfig] = None,
        on_flush: Optional[Callable[[List[EncounterMetrics]], bool]] = None,
    ):
        self.config = config or BufferConfig()
        self.on_flush = on_flush
        
        self._buffer: List[EncounterMetrics] = []
        self._lock = threading.Lock()
        self._last_flush = datetime.now()
        self._flush_count = 0
        self._total_items_flushed = 0
        self._failed_flushes = 0
        
        # Background flush timer
        self._flush_timer: Optional[threading.Timer] = None
        self._running = False
    
    def start(self) -> None:
        """Start the automatic flush timer."""
        self._running = True
        self._schedule_flush()
        logger.info(f"Telemetry buffer started (flush interval: {self.config.flush_interval_seconds}s)")
    
    def stop(self) -> None:
        """Stop the buffer and flush remaining items."""
        self._running = False
        if self._flush_timer:
            self._flush_timer.cancel()
        self.flush(BufferFlushTrigger.SHUTDOWN)
        logger.info("Telemetry buffer stopped")
    
    def _schedule_flush(self) -> None:
        """Schedule the next automatic flush."""
        if not self._running:
            return
        
        self._flush_timer = threading.Timer(
            self.config.flush_interval_seconds,
            self._auto_flush
        )
        self._flush_timer.daemon = True
        self._flush_timer.start()
    
    def _auto_flush(self) -> None:
        """Called by timer for automatic flush."""
        self.flush(BufferFlushTrigger.TIME)
        self._schedule_flush()
    
    def add(self, metrics: EncounterMetrics) -> None:
        """
        Add encounter metrics to the buffer.
        
        Triggers flush if buffer reaches max size.
        """
        with self._lock:
            self._buffer.append(metrics)
            
            if len(self._buffer) >= self.config.max_size:
                # Release lock before flushing
                items = self._buffer.copy()
                self._buffer.clear()
        
            # Flush outside lock if needed
            if len(self._buffer) >= self.config.max_size:
                self._do_flush(items, BufferFlushTrigger.SIZE)
    
    def flush(self, trigger: BufferFlushTrigger = BufferFlushTrigger.MANUAL) -> int:
        """
        Flush all buffered items.
        
        Returns:
            Number of items flushed
        """
        with self._lock:
            if not self._buffer:
                return 0
            
            items = self._buffer.copy()
            self._buffer.clear()
        
        return self._do_flush(items, trigger)
    
    def _do_flush(self, items: List[EncounterMetrics], trigger: BufferFlushTrigger) -> int:
        """Execute the flush operation with retry logic."""
        if not items:
            return 0
        
        success = False
        attempts = 0
        
        while not success and attempts < self.config.max_retries:
            attempts += 1
            
            try:
                if self.on_flush:
                    success = self.on_flush(items)
                else:
                    # Default: just log
                    logger.info(f"Flushing {len(items)} telemetry items (trigger: {trigger.value})")
                    success = True
                
            except Exception as e:
                logger.error(f"Flush attempt {attempts} failed: {e}")
                if self.config.retry_on_failure and attempts < self.config.max_retries:
                    time.sleep(self.config.retry_delay_seconds)
        
        if success:
            self._flush_count += 1
            self._total_items_flushed += len(items)
            self._last_flush = datetime.now()
        else:
            self._failed_flushes += 1
            logger.error(f"Failed to flush {len(items)} items after {attempts} attempts")
        
        return len(items) if success else 0
    
    @property
    def size(self) -> int:
        """Current buffer size."""
        with self._lock:
            return len(self._buffer)
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Buffer statistics."""
        return {
            "current_size": self.size,
            "max_size": self.config.max_size,
            "flush_count": self._flush_count,
            "total_items_flushed": self._total_items_flushed,
            "failed_flushes": self._failed_flushes,
            "last_flush": self._last_flush.isoformat(),
        }


# ==============================================================================
# Telemetry Exporter
# ==============================================================================

class TelemetryExporter:
    """
    Export telemetry to various backends.
    
    Supports:
    - Prometheus (push gateway)
    - TimescaleDB (time-series storage)
    - Kafka (streaming)
    - Elasticsearch (search/analytics)
    """
    
    def __init__(self, destination: ExportDestination, config: Dict[str, Any] = None):
        self.destination = destination
        self.config = config or {}
        self._export_count = 0
        self._last_export = None
    
    def export(self, metrics: List[EncounterMetrics]) -> bool:
        """
        Export metrics to configured destination.
        
        Returns:
            True if export succeeded
        """
        if not metrics:
            return True
        
        try:
            if self.destination == ExportDestination.PROMETHEUS:
                return self._export_prometheus(metrics)
            elif self.destination == ExportDestination.TIMESCALEDB:
                return self._export_timescaledb(metrics)
            elif self.destination == ExportDestination.KAFKA:
                return self._export_kafka(metrics)
            elif self.destination == ExportDestination.ELASTICSEARCH:
                return self._export_elasticsearch(metrics)
            elif self.destination == ExportDestination.CONSOLE:
                return self._export_console(metrics)
            else:
                logger.error(f"Unknown export destination: {self.destination}")
                return False
                
        except Exception as e:
            logger.error(f"Export to {self.destination.value} failed: {e}")
            return False
    
    def _export_prometheus(self, metrics: List[EncounterMetrics]) -> bool:
        """Export to Prometheus push gateway."""
        from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
        
        registry = CollectorRegistry()
        
        # Create gauges for key metrics
        time_saved = Gauge(
            'phoenix_time_saved_minutes',
            'Time saved per encounter',
            ['tenant_id', 'specialty'],
            registry=registry
        )
        
        satisfaction = Gauge(
            'phoenix_physician_satisfaction',
            'Physician satisfaction rating',
            ['tenant_id', 'specialty'],
            registry=registry
        )
        
        latency_p95 = Gauge(
            'phoenix_api_latency_p95_ms',
            'API P95 latency in milliseconds',
            ['tenant_id'],
            registry=registry
        )
        
        # Aggregate metrics by tenant
        for m in metrics:
            time_saved.labels(
                tenant_id=m.tenant_id,
                specialty=m.specialty
            ).set(m.time_saved_minutes)
            
            if m.physician_rating:
                satisfaction.labels(
                    tenant_id=m.tenant_id,
                    specialty=m.specialty
                ).set(m.physician_rating)
            
            latency_p95.labels(tenant_id=m.tenant_id).set(m.api_latency_p95_ms)
        
        # Push to gateway
        gateway = self.config.get('gateway', 'localhost:9091')
        push_to_gateway(gateway, job='phoenix_guardian', registry=registry)
        
        self._export_count += len(metrics)
        self._last_export = datetime.now()
        
        logger.info(f"Exported {len(metrics)} metrics to Prometheus")
        return True
    
    def _export_timescaledb(self, metrics: List[EncounterMetrics]) -> bool:
        """Export to TimescaleDB for time-series storage."""
        import psycopg2
        from psycopg2.extras import execute_values
        
        conn = psycopg2.connect(
            host=self.config.get('host', 'localhost'),
            port=self.config.get('port', 5432),
            database=self.config.get('database', 'phoenix_telemetry'),
            user=self.config.get('user', 'phoenix'),
            password=self.config.get('password', ''),
        )
        
        try:
            with conn.cursor() as cur:
                # Prepare data for batch insert
                data = [
                    (
                        m.encounter_id,
                        m.tenant_id,
                        m.specialty,
                        m.created_at,
                        m.time_saved_minutes,
                        m.physician_rating,
                        m.api_latency_p95_ms,
                        m.attack_detected,
                        json.dumps(m.to_dict()),
                    )
                    for m in metrics
                ]
                
                execute_values(
                    cur,
                    """
                    INSERT INTO encounter_metrics 
                    (encounter_id, tenant_id, specialty, created_at, 
                     time_saved_minutes, physician_rating, latency_p95_ms,
                     attack_detected, raw_data)
                    VALUES %s
                    ON CONFLICT (encounter_id) DO UPDATE SET
                        raw_data = EXCLUDED.raw_data
                    """,
                    data
                )
                
                conn.commit()
                
        finally:
            conn.close()
        
        self._export_count += len(metrics)
        self._last_export = datetime.now()
        
        logger.info(f"Exported {len(metrics)} metrics to TimescaleDB")
        return True
    
    def _export_kafka(self, metrics: List[EncounterMetrics]) -> bool:
        """Export to Kafka for streaming analytics."""
        from kafka import KafkaProducer
        
        producer = KafkaProducer(
            bootstrap_servers=self.config.get('bootstrap_servers', 'localhost:9092'),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        topic = self.config.get('topic', 'phoenix-telemetry')
        
        for m in metrics:
            producer.send(topic, value=m.to_dict())
        
        producer.flush()
        producer.close()
        
        self._export_count += len(metrics)
        self._last_export = datetime.now()
        
        logger.info(f"Exported {len(metrics)} metrics to Kafka")
        return True
    
    def _export_elasticsearch(self, metrics: List[EncounterMetrics]) -> bool:
        """Export to Elasticsearch for search and analytics."""
        from elasticsearch import Elasticsearch
        from elasticsearch.helpers import bulk
        
        es = Elasticsearch(
            hosts=self.config.get('hosts', ['localhost:9200'])
        )
        
        index = self.config.get('index', 'phoenix-telemetry')
        
        actions = [
            {
                '_index': index,
                '_id': m.encounter_id,
                '_source': m.to_dict(),
            }
            for m in metrics
        ]
        
        bulk(es, actions)
        
        self._export_count += len(metrics)
        self._last_export = datetime.now()
        
        logger.info(f"Exported {len(metrics)} metrics to Elasticsearch")
        return True
    
    def _export_console(self, metrics: List[EncounterMetrics]) -> bool:
        """Export to console (for debugging)."""
        for m in metrics:
            print(m.generate_report())
        
        self._export_count += len(metrics)
        self._last_export = datetime.now()
        
        return True


# ==============================================================================
# Telemetry Collector
# ==============================================================================

class TelemetryCollector:
    """
    Main interface for capturing telemetry from Phoenix Guardian.
    
    Provides:
    - Real-time metric capture during encounters
    - Automatic buffering and export
    - Aggregation for dashboard display
    
    Example:
        collector = TelemetryCollector(tenant_id="pilot_hospital_001")
        
        # Start tracking an encounter
        metrics = collector.start_encounter(
            physician_id="phy-123",
            specialty="Cardiology"
        )
        
        # Record events
        collector.record_agent_invocation(metrics.encounter_id, agent_invocation)
        collector.record_security_event(metrics.encounter_id, security_event)
        
        # Complete encounter
        collector.complete_encounter(metrics.encounter_id, rating=5)
    """
    
    def __init__(
        self,
        tenant_id: str,
        buffer_config: Optional[BufferConfig] = None,
        exporters: Optional[List[TelemetryExporter]] = None,
    ):
        self.tenant_id = tenant_id
        self.exporters = exporters or []
        
        # Active encounters (in-progress)
        self._active_encounters: Dict[str, EncounterMetrics] = {}
        
        # Buffer for completed encounters
        self._buffer = TelemetryBuffer(
            config=buffer_config,
            on_flush=self._flush_to_exporters
        )
        
        # Aggregated stats
        self._stats = {
            "total_encounters": 0,
            "completed_encounters": 0,
            "failed_encounters": 0,
            "abandoned_encounters": 0,
            "total_time_saved_minutes": 0.0,
            "total_ratings": 0,
            "rating_sum": 0,
            "attacks_detected": 0,
            "false_positives": 0,
        }
        
        self._lock = threading.Lock()
    
    def start(self) -> None:
        """Start the telemetry collector."""
        self._buffer.start()
        logger.info(f"Telemetry collector started for tenant: {self.tenant_id}")
    
    def stop(self) -> None:
        """Stop the telemetry collector."""
        self._buffer.stop()
        logger.info(f"Telemetry collector stopped for tenant: {self.tenant_id}")
    
    def _flush_to_exporters(self, metrics: List[EncounterMetrics]) -> bool:
        """Flush metrics to all configured exporters."""
        if not self.exporters:
            logger.debug(f"No exporters configured, discarding {len(metrics)} metrics")
            return True
        
        success = True
        for exporter in self.exporters:
            try:
                if not exporter.export(metrics):
                    success = False
            except Exception as e:
                logger.error(f"Exporter {exporter.destination.value} failed: {e}")
                success = False
        
        return success
    
    # =========================================================================
    # Encounter Lifecycle
    # =========================================================================
    
    def start_encounter(
        self,
        physician_id: str,
        specialty: str = "General",
        patient_id_hash: str = "",
        encounter_id: Optional[str] = None,
    ) -> EncounterMetrics:
        """
        Start tracking a new encounter.
        
        Args:
            physician_id: Anonymized physician identifier
            specialty: Medical specialty
            patient_id_hash: Anonymized patient identifier
            encounter_id: Optional custom ID (auto-generated if not provided)
        
        Returns:
            EncounterMetrics object for tracking
        """
        import uuid
        
        enc_id = encounter_id or f"enc-{uuid.uuid4().hex[:12]}"
        
        metrics = EncounterMetrics(
            encounter_id=enc_id,
            tenant_id=self.tenant_id,
            physician_id=physician_id,
            specialty=specialty,
            patient_id_hash=patient_id_hash,
        )
        
        metrics.start_encounter()
        
        with self._lock:
            self._active_encounters[enc_id] = metrics
            self._stats["total_encounters"] += 1
        
        logger.debug(f"Started encounter: {enc_id}")
        return metrics
    
    def get_encounter(self, encounter_id: str) -> Optional[EncounterMetrics]:
        """Get an active encounter by ID."""
        with self._lock:
            return self._active_encounters.get(encounter_id)
    
    def complete_encounter(
        self,
        encounter_id: str,
        rating: Optional[int] = None,
        comment: Optional[str] = None,
    ) -> Optional[EncounterMetrics]:
        """
        Mark an encounter as completed and move to buffer.
        
        Args:
            encounter_id: The encounter to complete
            rating: Optional physician rating (1-5)
            comment: Optional physician comment
        
        Returns:
            The completed EncounterMetrics, or None if not found
        """
        with self._lock:
            metrics = self._active_encounters.pop(encounter_id, None)
        
        if not metrics:
            logger.warning(f"Encounter not found: {encounter_id}")
            return None
        
        metrics.complete_encounter()
        
        if rating:
            metrics.set_physician_rating(rating, comment)
        
        # Update stats
        with self._lock:
            self._stats["completed_encounters"] += 1
            self._stats["total_time_saved_minutes"] += metrics.time_saved_minutes
            
            if rating:
                self._stats["total_ratings"] += 1
                self._stats["rating_sum"] += rating
            
            if metrics.attack_detected:
                self._stats["attacks_detected"] += 1
        
        # Add to buffer for export
        self._buffer.add(metrics)
        
        logger.debug(f"Completed encounter: {encounter_id}")
        return metrics
    
    def fail_encounter(self, encounter_id: str, error: str) -> Optional[EncounterMetrics]:
        """Mark an encounter as failed."""
        with self._lock:
            metrics = self._active_encounters.pop(encounter_id, None)
        
        if not metrics:
            return None
        
        metrics.fail_encounter(error)
        
        with self._lock:
            self._stats["failed_encounters"] += 1
        
        self._buffer.add(metrics)
        
        logger.warning(f"Encounter failed: {encounter_id} - {error}")
        return metrics
    
    def abandon_encounter(self, encounter_id: str) -> Optional[EncounterMetrics]:
        """Mark an encounter as abandoned by physician."""
        with self._lock:
            metrics = self._active_encounters.pop(encounter_id, None)
        
        if not metrics:
            return None
        
        metrics.abandon_encounter()
        
        with self._lock:
            self._stats["abandoned_encounters"] += 1
        
        self._buffer.add(metrics)
        
        logger.info(f"Encounter abandoned: {encounter_id}")
        return metrics
    
    # =========================================================================
    # Event Recording
    # =========================================================================
    
    def record_agent_invocation(
        self,
        encounter_id: str,
        invocation: AgentInvocation,
    ) -> bool:
        """Record an agent invocation for an encounter."""
        with self._lock:
            metrics = self._active_encounters.get(encounter_id)
        
        if not metrics:
            logger.warning(f"Cannot record agent invocation - encounter not found: {encounter_id}")
            return False
        
        metrics.record_agent_invocation(invocation)
        return True
    
    def record_security_event(
        self,
        encounter_id: str,
        event: SecurityEvent,
    ) -> bool:
        """Record a security event for an encounter."""
        with self._lock:
            metrics = self._active_encounters.get(encounter_id)
        
        if not metrics:
            logger.warning(f"Cannot record security event - encounter not found: {encounter_id}")
            return False
        
        metrics.record_security_event(event)
        
        if event.marked_false_positive:
            with self._lock:
                self._stats["false_positives"] += 1
        
        return True
    
    def update_latencies(
        self,
        encounter_id: str,
        p50_ms: float,
        p95_ms: float,
        p99_ms: float,
    ) -> bool:
        """Update latency metrics for an encounter."""
        with self._lock:
            metrics = self._active_encounters.get(encounter_id)
        
        if not metrics:
            return False
        
        metrics.api_latency_p50_ms = p50_ms
        metrics.api_latency_p95_ms = p95_ms
        metrics.api_latency_p99_ms = p99_ms
        
        return True
    
    # =========================================================================
    # Aggregation & Reporting
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated statistics."""
        with self._lock:
            stats = self._stats.copy()
        
        # Calculate derived metrics
        if stats["total_ratings"] > 0:
            stats["average_rating"] = stats["rating_sum"] / stats["total_ratings"]
        else:
            stats["average_rating"] = 0.0
        
        if stats["completed_encounters"] > 0:
            stats["average_time_saved"] = (
                stats["total_time_saved_minutes"] / stats["completed_encounters"]
            )
        else:
            stats["average_time_saved"] = 0.0
        
        stats["active_encounters"] = len(self._active_encounters)
        stats["buffer_size"] = self._buffer.size
        stats["buffer_stats"] = self._buffer.stats
        
        return stats
    
    def get_real_time_metrics(self) -> Dict[str, Any]:
        """
        Get current real-time metrics for dashboard display.
        
        Returns metrics suitable for WebSocket streaming.
        """
        stats = self.get_stats()
        
        return {
            "tenant_id": self.tenant_id,
            "timestamp": datetime.now().isoformat(),
            "encounters": {
                "active": stats["active_encounters"],
                "completed_today": stats["completed_encounters"],
                "failed_today": stats["failed_encounters"],
            },
            "performance": {
                "average_time_saved_minutes": round(stats["average_time_saved"], 1),
                "average_rating": round(stats["average_rating"], 2),
            },
            "security": {
                "attacks_detected": stats["attacks_detected"],
                "false_positives": stats["false_positives"],
            },
        }
