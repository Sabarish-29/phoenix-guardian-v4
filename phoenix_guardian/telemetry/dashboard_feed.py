"""
Phoenix Guardian - Dashboard Feed
WebSocket streaming for real-time dashboard updates.

Provides live metrics to executive and operational dashboards.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import logging
import uuid

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class MetricType(Enum):
    """Types of metrics for streaming."""
    ENCOUNTER_STARTED = "encounter_started"
    ENCOUNTER_COMPLETED = "encounter_completed"
    ENCOUNTER_FAILED = "encounter_failed"
    AGENT_INVOCATION = "agent_invocation"
    SECURITY_EVENT = "security_event"
    RATING_RECEIVED = "rating_received"
    BENCHMARK_UPDATE = "benchmark_update"
    ALERT = "alert"
    HEARTBEAT = "heartbeat"


class StreamSubscriptionType(Enum):
    """Types of stream subscriptions."""
    ALL = "all"                              # All metrics
    ENCOUNTERS = "encounters"                # Encounter lifecycle
    SECURITY = "security"                    # Security events only
    PERFORMANCE = "performance"              # Performance metrics
    ALERTS = "alerts"                        # Alerts only


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class LiveMetric:
    """
    A single live metric update for streaming.
    
    Sent to connected dashboard clients via WebSocket.
    """
    metric_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    metric_type: MetricType = MetricType.HEARTBEAT
    tenant_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Metric data
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    priority: str = "normal"                 # low, normal, high, critical
    ttl_seconds: int = 60                    # Time-to-live
    
    def to_json(self) -> str:
        """Serialize to JSON for WebSocket transmission."""
        return json.dumps({
            "metric_id": self.metric_id,
            "type": self.metric_type.value,
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "priority": self.priority,
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> "LiveMetric":
        """Deserialize from JSON."""
        data = json.loads(json_str)
        return cls(
            metric_id=data.get("metric_id", str(uuid.uuid4())[:8]),
            metric_type=MetricType(data["type"]),
            tenant_id=data.get("tenant_id", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            data=data.get("data", {}),
            priority=data.get("priority", "normal"),
        )


@dataclass
class MetricSnapshot:
    """
    Point-in-time snapshot of all metrics.
    
    Sent when a new client connects to provide current state.
    """
    tenant_id: str
    snapshot_at: datetime = field(default_factory=datetime.now)
    
    # Current counts
    active_encounters: int = 0
    encounters_today: int = 0
    encounters_this_hour: int = 0
    
    # Performance
    average_time_saved_minutes: float = 0.0
    average_rating: float = 0.0
    p95_latency_ms: float = 0.0
    
    # Security
    attacks_detected_today: int = 0
    attacks_blocked_today: int = 0
    false_positives_today: int = 0
    
    # Agent stats
    agent_invocations: Dict[str, int] = field(default_factory=dict)
    agent_success_rates: Dict[str, float] = field(default_factory=dict)
    
    # Benchmark status
    benchmarks_meeting: int = 0
    benchmarks_below: int = 0
    overall_health: str = "healthy"
    
    # Recent alerts
    recent_alerts: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps({
            "type": "snapshot",
            "tenant_id": self.tenant_id,
            "snapshot_at": self.snapshot_at.isoformat(),
            "encounters": {
                "active": self.active_encounters,
                "today": self.encounters_today,
                "this_hour": self.encounters_this_hour,
            },
            "performance": {
                "average_time_saved_minutes": round(self.average_time_saved_minutes, 1),
                "average_rating": round(self.average_rating, 2),
                "p95_latency_ms": round(self.p95_latency_ms, 1),
            },
            "security": {
                "attacks_detected_today": self.attacks_detected_today,
                "attacks_blocked_today": self.attacks_blocked_today,
                "false_positives_today": self.false_positives_today,
            },
            "agents": {
                "invocations": self.agent_invocations,
                "success_rates": {k: round(v, 2) for k, v in self.agent_success_rates.items()},
            },
            "benchmarks": {
                "meeting": self.benchmarks_meeting,
                "below": self.benchmarks_below,
                "overall_health": self.overall_health,
            },
            "recent_alerts": self.recent_alerts[-10:],  # Last 10 alerts
        })


@dataclass
class StreamSubscription:
    """
    A client's subscription to the metric stream.
    """
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str = ""
    subscription_type: StreamSubscriptionType = StreamSubscriptionType.ALL
    tenant_filter: Optional[str] = None      # None = all tenants
    created_at: datetime = field(default_factory=datetime.now)
    
    # Callback for sending messages
    send_callback: Optional[Callable[[str], asyncio.Future]] = None
    
    def matches(self, metric: LiveMetric) -> bool:
        """Check if this subscription should receive the metric."""
        # Check tenant filter
        if self.tenant_filter and metric.tenant_id != self.tenant_filter:
            return False
        
        # Check subscription type
        if self.subscription_type == StreamSubscriptionType.ALL:
            return True
        elif self.subscription_type == StreamSubscriptionType.ENCOUNTERS:
            return metric.metric_type in [
                MetricType.ENCOUNTER_STARTED,
                MetricType.ENCOUNTER_COMPLETED,
                MetricType.ENCOUNTER_FAILED,
            ]
        elif self.subscription_type == StreamSubscriptionType.SECURITY:
            return metric.metric_type == MetricType.SECURITY_EVENT
        elif self.subscription_type == StreamSubscriptionType.PERFORMANCE:
            return metric.metric_type in [
                MetricType.BENCHMARK_UPDATE,
                MetricType.AGENT_INVOCATION,
            ]
        elif self.subscription_type == StreamSubscriptionType.ALERTS:
            return metric.metric_type == MetricType.ALERT
        
        return True


# ==============================================================================
# Dashboard Feed
# ==============================================================================

class DashboardFeed:
    """
    WebSocket streaming feed for real-time dashboard updates.
    
    Manages subscriptions and broadcasts metrics to connected clients.
    
    Example:
        feed = DashboardFeed()
        
        # Subscribe a client
        subscription = await feed.subscribe(
            client_id="dashboard-123",
            subscription_type=StreamSubscriptionType.ALL,
            tenant_filter="pilot_hospital_001",
            send_callback=websocket.send
        )
        
        # Publish metrics
        feed.publish(LiveMetric(
            metric_type=MetricType.ENCOUNTER_COMPLETED,
            tenant_id="pilot_hospital_001",
            data={"encounter_id": "enc-123", "time_saved": 14.5}
        ))
        
        # Unsubscribe
        feed.unsubscribe(subscription.subscription_id)
    """
    
    def __init__(self, heartbeat_interval_seconds: int = 30):
        self._subscriptions: Dict[str, StreamSubscription] = {}
        self._metrics_buffer: List[LiveMetric] = []
        self._max_buffer_size = 1000
        
        self._heartbeat_interval = heartbeat_interval_seconds
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Stats
        self._total_published = 0
        self._total_delivered = 0
        
        # Snapshot cache (refreshed periodically)
        self._snapshots: Dict[str, MetricSnapshot] = {}
    
    async def start(self) -> None:
        """Start the dashboard feed."""
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Dashboard feed started")
    
    async def stop(self) -> None:
        """Stop the dashboard feed."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.info("Dashboard feed stopped")
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to all subscribers."""
        while self._running:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                
                heartbeat = LiveMetric(
                    metric_type=MetricType.HEARTBEAT,
                    data={
                        "subscribers": len(self._subscriptions),
                        "total_published": self._total_published,
                    }
                )
                
                await self._broadcast(heartbeat)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    # =========================================================================
    # Subscription Management
    # =========================================================================
    
    async def subscribe(
        self,
        client_id: str,
        send_callback: Callable[[str], asyncio.Future],
        subscription_type: StreamSubscriptionType = StreamSubscriptionType.ALL,
        tenant_filter: Optional[str] = None,
    ) -> StreamSubscription:
        """
        Subscribe a client to the metric stream.
        
        Args:
            client_id: Unique identifier for the client
            send_callback: Async function to send messages to client
            subscription_type: Type of metrics to receive
            tenant_filter: Only receive metrics for this tenant
        
        Returns:
            StreamSubscription object
        """
        subscription = StreamSubscription(
            client_id=client_id,
            subscription_type=subscription_type,
            tenant_filter=tenant_filter,
            send_callback=send_callback,
        )
        
        self._subscriptions[subscription.subscription_id] = subscription
        
        logger.info(
            f"Client {client_id} subscribed ({subscription_type.value})"
            f"{f' for tenant {tenant_filter}' if tenant_filter else ''}"
        )
        
        # Send initial snapshot
        if tenant_filter and tenant_filter in self._snapshots:
            snapshot = self._snapshots[tenant_filter]
            try:
                await send_callback(snapshot.to_json())
            except Exception as e:
                logger.error(f"Failed to send snapshot: {e}")
        
        return subscription
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe a client.
        
        Args:
            subscription_id: The subscription to remove
        
        Returns:
            True if subscription was removed
        """
        if subscription_id in self._subscriptions:
            sub = self._subscriptions.pop(subscription_id)
            logger.info(f"Client {sub.client_id} unsubscribed")
            return True
        return False
    
    def get_subscriber_count(self) -> int:
        """Get number of active subscribers."""
        return len(self._subscriptions)
    
    # =========================================================================
    # Publishing
    # =========================================================================
    
    def publish(self, metric: LiveMetric) -> None:
        """
        Publish a metric to all matching subscribers.
        
        Non-async version that queues for async delivery.
        """
        self._metrics_buffer.append(metric)
        self._total_published += 1
        
        # Trim buffer if needed
        if len(self._metrics_buffer) > self._max_buffer_size:
            self._metrics_buffer = self._metrics_buffer[-self._max_buffer_size:]
        
        # Schedule async broadcast
        asyncio.create_task(self._broadcast(metric))
    
    async def publish_async(self, metric: LiveMetric) -> int:
        """
        Publish a metric and wait for delivery.
        
        Returns:
            Number of subscribers that received the metric
        """
        self._metrics_buffer.append(metric)
        self._total_published += 1
        
        return await self._broadcast(metric)
    
    async def _broadcast(self, metric: LiveMetric) -> int:
        """Broadcast metric to all matching subscribers."""
        delivered = 0
        failed_subscriptions = []
        
        for sub_id, subscription in self._subscriptions.items():
            if not subscription.matches(metric):
                continue
            
            if subscription.send_callback:
                try:
                    await subscription.send_callback(metric.to_json())
                    delivered += 1
                    self._total_delivered += 1
                except Exception as e:
                    logger.warning(f"Failed to deliver to {subscription.client_id}: {e}")
                    failed_subscriptions.append(sub_id)
        
        # Clean up failed subscriptions
        for sub_id in failed_subscriptions:
            self.unsubscribe(sub_id)
        
        return delivered
    
    # =========================================================================
    # Convenience Publishers
    # =========================================================================
    
    def publish_encounter_started(
        self,
        tenant_id: str,
        encounter_id: str,
        physician_id: str,
        specialty: str,
    ) -> None:
        """Publish encounter started event."""
        self.publish(LiveMetric(
            metric_type=MetricType.ENCOUNTER_STARTED,
            tenant_id=tenant_id,
            data={
                "encounter_id": encounter_id,
                "physician_id": physician_id,
                "specialty": specialty,
            }
        ))
    
    def publish_encounter_completed(
        self,
        tenant_id: str,
        encounter_id: str,
        time_saved_minutes: float,
        rating: Optional[int] = None,
    ) -> None:
        """Publish encounter completed event."""
        self.publish(LiveMetric(
            metric_type=MetricType.ENCOUNTER_COMPLETED,
            tenant_id=tenant_id,
            data={
                "encounter_id": encounter_id,
                "time_saved_minutes": time_saved_minutes,
                "rating": rating,
            }
        ))
    
    def publish_security_event(
        self,
        tenant_id: str,
        event_type: str,
        severity: str,
        blocked: bool,
    ) -> None:
        """Publish security event."""
        self.publish(LiveMetric(
            metric_type=MetricType.SECURITY_EVENT,
            tenant_id=tenant_id,
            priority="high" if severity in ["critical", "high"] else "normal",
            data={
                "event_type": event_type,
                "severity": severity,
                "blocked": blocked,
            }
        ))
    
    def publish_alert(
        self,
        tenant_id: str,
        alert_type: str,
        message: str,
        severity: str,
    ) -> None:
        """Publish an alert."""
        self.publish(LiveMetric(
            metric_type=MetricType.ALERT,
            tenant_id=tenant_id,
            priority="critical" if severity == "critical" else "high",
            data={
                "alert_type": alert_type,
                "message": message,
                "severity": severity,
            }
        ))
    
    def publish_benchmark_update(
        self,
        tenant_id: str,
        metric_name: str,
        actual_value: float,
        target_value: float,
        status: str,
    ) -> None:
        """Publish benchmark update."""
        self.publish(LiveMetric(
            metric_type=MetricType.BENCHMARK_UPDATE,
            tenant_id=tenant_id,
            data={
                "metric_name": metric_name,
                "actual_value": actual_value,
                "target_value": target_value,
                "status": status,
            }
        ))
    
    # =========================================================================
    # Snapshot Management
    # =========================================================================
    
    def update_snapshot(self, snapshot: MetricSnapshot) -> None:
        """Update the cached snapshot for a tenant."""
        self._snapshots[snapshot.tenant_id] = snapshot
    
    def get_snapshot(self, tenant_id: str) -> Optional[MetricSnapshot]:
        """Get the cached snapshot for a tenant."""
        return self._snapshots.get(tenant_id)
    
    # =========================================================================
    # Stats
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get feed statistics."""
        return {
            "subscribers": len(self._subscriptions),
            "buffer_size": len(self._metrics_buffer),
            "total_published": self._total_published,
            "total_delivered": self._total_delivered,
            "delivery_rate": (
                self._total_delivered / self._total_published
                if self._total_published > 0 else 0.0
            ),
            "snapshots_cached": len(self._snapshots),
        }
