"""
Phoenix Guardian - Pilot Hospital Metrics & Tracking

This module tracks key performance indicators for each hospital pilot site.
All metrics are aggregated in real-time and fed to the executive dashboard.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
import json
import logging
from collections import defaultdict
import asyncio
import aiohttp

logger = logging.getLogger(__name__)


class PilotPhase(Enum):
    """Pilot program phases."""
    PRE_DEPLOYMENT = "pre_deployment"
    BETA = "beta"
    PRODUCTION = "production"
    SCALING = "scaling"
    STEADY_STATE = "steady_state"


class MetricStatus(Enum):
    """Status indicators for metric thresholds."""
    EXCEEDS = "exceeds"  # Better than target
    MEETS = "meets"      # At or near target
    AT_RISK = "at_risk"  # Below target but recoverable
    CRITICAL = "critical"  # Significantly below target


@dataclass
class PilotMetrics:
    """
    Core metrics tracked for each hospital pilot.
    
    All targets are based on pilot program success criteria:
    - >95% SOAP note completeness
    - <5 seconds generation time
    - Physician satisfaction >4.0
    - System uptime >99.5%
    - <10 support tickets per week
    """
    
    hospital_id: str
    hospital_name: str
    start_date: datetime
    phase: PilotPhase = PilotPhase.PRE_DEPLOYMENT
    
    # Usage metrics
    total_physicians: int = 0
    active_physicians_24h: int = 0
    total_encounters_processed: int = 0
    encounters_today: int = 0
    
    # Performance metrics
    avg_generation_time_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    error_rate_percent: float = 0.0
    
    # Quality metrics
    soap_completeness_score: float = 0.0  # 0-100%
    physician_edit_rate: float = 0.0       # % of notes requiring edits
    clinical_accuracy_score: float = 0.0   # 0-100%
    
    # Satisfaction metrics
    physician_satisfaction: float = 0.0   # 1-5 scale
    nps_score: int = 0                     # -100 to 100
    
    # Operational metrics
    uptime_percent: float = 100.0
    support_tickets_open: int = 0
    support_tickets_week: int = 0
    p0_incidents: int = 0
    p1_incidents: int = 0
    
    # Time savings
    avg_time_saved_minutes: float = 0.0
    total_hours_saved: float = 0.0
    
    # Federated learning (optional participation)
    federated_learning_enabled: bool = False
    model_updates_contributed: int = 0
    privacy_budget_remaining: float = 1.0  # epsilon budget
    
    # Timestamps
    last_updated: datetime = field(default_factory=datetime.utcnow)
    last_encounter: Optional[datetime] = None
    
    # Targets for this pilot
    targets: Dict[str, float] = field(default_factory=lambda: {
        "soap_completeness": 95.0,
        "generation_time_ms": 5000.0,
        "physician_satisfaction": 4.0,
        "uptime_percent": 99.5,
        "support_tickets_week": 10,
        "p95_latency_ms": 3000.0,
        "error_rate_percent": 0.1,
        "physician_edit_rate": 30.0,
    })

    def calculate_status(self, metric_name: str, value: float) -> MetricStatus:
        """Calculate status for a metric based on its target."""
        if metric_name not in self.targets:
            return MetricStatus.MEETS
            
        target = self.targets[metric_name]
        
        # Some metrics are "lower is better"
        lower_is_better = metric_name in [
            "generation_time_ms", "p95_latency_ms", "error_rate_percent",
            "support_tickets_week", "physician_edit_rate"
        ]
        
        if lower_is_better:
            if value < target * 0.8:
                return MetricStatus.EXCEEDS
            elif value <= target:
                return MetricStatus.MEETS
            elif value <= target * 1.2:
                return MetricStatus.AT_RISK
            else:
                return MetricStatus.CRITICAL
        else:
            if value > target * 1.1:
                return MetricStatus.EXCEEDS
            elif value >= target:
                return MetricStatus.MEETS
            elif value >= target * 0.9:
                return MetricStatus.AT_RISK
            else:
                return MetricStatus.CRITICAL

    def get_health_summary(self) -> Dict[str, MetricStatus]:
        """Get overall health summary across all tracked metrics."""
        return {
            "soap_completeness": self.calculate_status("soap_completeness", self.soap_completeness_score),
            "generation_time": self.calculate_status("generation_time_ms", self.avg_generation_time_ms),
            "latency_p95": self.calculate_status("p95_latency_ms", self.p95_latency_ms),
            "error_rate": self.calculate_status("error_rate_percent", self.error_rate_percent),
            "satisfaction": self.calculate_status("physician_satisfaction", self.physician_satisfaction),
            "uptime": self.calculate_status("uptime_percent", self.uptime_percent),
            "support_load": self.calculate_status("support_tickets_week", self.support_tickets_week),
            "edit_rate": self.calculate_status("physician_edit_rate", self.physician_edit_rate),
        }

    def is_ready_for_production(self) -> tuple[bool, List[str]]:
        """Check if pilot is ready to graduate from beta to production."""
        blockers = []
        
        if self.p0_incidents > 0:
            blockers.append(f"P0 incidents: {self.p0_incidents}")
        if self.p1_incidents > 2:
            blockers.append(f"P1 incidents: {self.p1_incidents} (max 2)")
        if self.uptime_percent < 99.0:
            blockers.append(f"Uptime {self.uptime_percent:.1f}% < 99%")
        if self.physician_satisfaction < 3.5:
            blockers.append(f"Satisfaction {self.physician_satisfaction:.1f} < 3.5")
        if self.active_physicians_24h < 3:
            blockers.append(f"Active physicians {self.active_physicians_24h} < 3")
        if self.total_encounters_processed < 50:
            blockers.append(f"Encounters {self.total_encounters_processed} < 50")
            
        return len(blockers) == 0, blockers

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metrics to dictionary for API responses."""
        return {
            "hospital_id": self.hospital_id,
            "hospital_name": self.hospital_name,
            "phase": self.phase.value,
            "start_date": self.start_date.isoformat(),
            "usage": {
                "total_physicians": self.total_physicians,
                "active_physicians_24h": self.active_physicians_24h,
                "total_encounters": self.total_encounters_processed,
                "encounters_today": self.encounters_today,
            },
            "performance": {
                "avg_generation_time_ms": self.avg_generation_time_ms,
                "p95_latency_ms": self.p95_latency_ms,
                "p99_latency_ms": self.p99_latency_ms,
                "error_rate_percent": self.error_rate_percent,
            },
            "quality": {
                "soap_completeness": self.soap_completeness_score,
                "physician_edit_rate": self.physician_edit_rate,
                "clinical_accuracy": self.clinical_accuracy_score,
            },
            "satisfaction": {
                "physician_rating": self.physician_satisfaction,
                "nps_score": self.nps_score,
            },
            "operations": {
                "uptime_percent": self.uptime_percent,
                "support_tickets_open": self.support_tickets_open,
                "support_tickets_week": self.support_tickets_week,
                "p0_incidents": self.p0_incidents,
                "p1_incidents": self.p1_incidents,
            },
            "time_savings": {
                "avg_minutes_per_encounter": self.avg_time_saved_minutes,
                "total_hours_saved": self.total_hours_saved,
            },
            "federated_learning": {
                "enabled": self.federated_learning_enabled,
                "updates_contributed": self.model_updates_contributed,
                "privacy_budget_remaining": self.privacy_budget_remaining,
            },
            "health": {
                k: v.value for k, v in self.get_health_summary().items()
            },
            "production_ready": {
                "ready": self.is_ready_for_production()[0],
                "blockers": self.is_ready_for_production()[1],
            },
            "last_updated": self.last_updated.isoformat(),
            "last_encounter": self.last_encounter.isoformat() if self.last_encounter else None,
        }


class PilotMetricsCollector:
    """
    Collects and aggregates metrics from multiple sources.
    
    Data sources:
    - PostgreSQL: Encounter counts, SOAP note metrics
    - Redis: Real-time latency percentiles, active users
    - Prometheus: System metrics, uptime
    - Zendesk/ServiceNow: Support tickets
    - Survey results: Satisfaction scores
    """
    
    def __init__(
        self,
        db_connection: Any,
        redis_client: Any,
        prometheus_url: str,
        datadog_api_key: Optional[str] = None,
    ):
        self.db = db_connection
        self.redis = redis_client
        self.prometheus_url = prometheus_url
        self.datadog_api_key = datadog_api_key
        self._hospitals: Dict[str, PilotMetrics] = {}
        
    async def collect_all_metrics(self, hospital_id: str) -> PilotMetrics:
        """Collect all metrics for a hospital from various sources."""
        metrics = self._hospitals.get(hospital_id)
        if not metrics:
            raise ValueError(f"Hospital {hospital_id} not found in pilot program")
        
        # Collect in parallel for efficiency
        await asyncio.gather(
            self._collect_usage_metrics(metrics),
            self._collect_performance_metrics(metrics),
            self._collect_quality_metrics(metrics),
            self._collect_operational_metrics(metrics),
        )
        
        metrics.last_updated = datetime.utcnow()
        return metrics
    
    async def _collect_usage_metrics(self, metrics: PilotMetrics):
        """Collect usage metrics from database."""
        # Active physicians in last 24 hours
        query = """
            SELECT COUNT(DISTINCT physician_id)
            FROM encounters
            WHERE hospital_id = $1
              AND created_at >= NOW() - INTERVAL '24 hours'
        """
        result = await self.db.fetchval(query, metrics.hospital_id)
        metrics.active_physicians_24h = result or 0
        
        # Today's encounters
        query = """
            SELECT COUNT(*)
            FROM encounters
            WHERE hospital_id = $1
              AND DATE(created_at) = CURRENT_DATE
        """
        result = await self.db.fetchval(query, metrics.hospital_id)
        metrics.encounters_today = result or 0
        
        # Total encounters
        query = """
            SELECT COUNT(*)
            FROM encounters
            WHERE hospital_id = $1
        """
        result = await self.db.fetchval(query, metrics.hospital_id)
        metrics.total_encounters_processed = result or 0
        
        # Last encounter timestamp
        query = """
            SELECT MAX(created_at)
            FROM encounters
            WHERE hospital_id = $1
        """
        result = await self.db.fetchval(query, metrics.hospital_id)
        metrics.last_encounter = result
    
    async def _collect_performance_metrics(self, metrics: PilotMetrics):
        """Collect latency and error metrics from Redis/Prometheus."""
        # Get percentiles from Redis (stored by our API middleware)
        key = f"metrics:latency:{metrics.hospital_id}"
        
        p50 = await self.redis.hget(key, "p50")
        p95 = await self.redis.hget(key, "p95")
        p99 = await self.redis.hget(key, "p99")
        
        if p50:
            metrics.avg_generation_time_ms = float(p50)
        if p95:
            metrics.p95_latency_ms = float(p95)
        if p99:
            metrics.p99_latency_ms = float(p99)
        
        # Get error rate from Prometheus
        query = f'sum(rate(http_requests_total{{hospital_id="{metrics.hospital_id}",status=~"5.."}}[1h])) / sum(rate(http_requests_total{{hospital_id="{metrics.hospital_id}"}}[1h])) * 100'
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": query}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data["data"]["result"]:
                        metrics.error_rate_percent = float(data["data"]["result"][0]["value"][1])
    
    async def _collect_quality_metrics(self, metrics: PilotMetrics):
        """Collect quality metrics from database."""
        # SOAP completeness (based on section scores)
        query = """
            SELECT AVG(completeness_score) * 100
            FROM soap_notes
            WHERE hospital_id = $1
              AND created_at >= NOW() - INTERVAL '7 days'
        """
        result = await self.db.fetchval(query, metrics.hospital_id)
        metrics.soap_completeness_score = result or 0.0
        
        # Physician edit rate
        query = """
            SELECT 
                COUNT(*) FILTER (WHERE was_edited) * 100.0 / NULLIF(COUNT(*), 0)
            FROM soap_notes
            WHERE hospital_id = $1
              AND created_at >= NOW() - INTERVAL '7 days'
        """
        result = await self.db.fetchval(query, metrics.hospital_id)
        metrics.physician_edit_rate = result or 0.0
        
        # Average time saved per encounter
        query = """
            SELECT AVG(time_saved_seconds) / 60.0
            FROM soap_notes
            WHERE hospital_id = $1
              AND time_saved_seconds IS NOT NULL
        """
        result = await self.db.fetchval(query, metrics.hospital_id)
        metrics.avg_time_saved_minutes = result or 0.0
        
        # Total hours saved
        query = """
            SELECT SUM(time_saved_seconds) / 3600.0
            FROM soap_notes
            WHERE hospital_id = $1
        """
        result = await self.db.fetchval(query, metrics.hospital_id)
        metrics.total_hours_saved = result or 0.0
    
    async def _collect_operational_metrics(self, metrics: PilotMetrics):
        """Collect uptime and support metrics."""
        # Uptime from Prometheus (via uptime robot or synthetic checks)
        query = f'avg_over_time(probe_success{{hospital_id="{metrics.hospital_id}"}}[7d]) * 100'
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": query}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data["data"]["result"]:
                        metrics.uptime_percent = float(data["data"]["result"][0]["value"][1])
        
        # Support tickets from database (or could integrate with Zendesk API)
        query = """
            SELECT 
                COUNT(*) FILTER (WHERE status = 'open'),
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days'),
                COUNT(*) FILTER (WHERE severity = 'P0'),
                COUNT(*) FILTER (WHERE severity = 'P1')
            FROM support_tickets
            WHERE hospital_id = $1
        """
        result = await self.db.fetchrow(query, metrics.hospital_id)
        if result:
            metrics.support_tickets_open = result[0] or 0
            metrics.support_tickets_week = result[1] or 0
            metrics.p0_incidents = result[2] or 0
            metrics.p1_incidents = result[3] or 0
    
    def register_hospital(
        self,
        hospital_id: str,
        hospital_name: str,
        start_date: datetime,
        total_physicians: int,
        custom_targets: Optional[Dict[str, float]] = None,
    ) -> PilotMetrics:
        """Register a new hospital in the pilot program."""
        metrics = PilotMetrics(
            hospital_id=hospital_id,
            hospital_name=hospital_name,
            start_date=start_date,
            total_physicians=total_physicians,
        )
        
        if custom_targets:
            metrics.targets.update(custom_targets)
        
        self._hospitals[hospital_id] = metrics
        logger.info(f"Registered hospital {hospital_id} ({hospital_name}) for pilot program")
        
        return metrics
    
    def update_phase(self, hospital_id: str, new_phase: PilotPhase):
        """Update the pilot phase for a hospital."""
        if hospital_id not in self._hospitals:
            raise ValueError(f"Hospital {hospital_id} not found")
        
        old_phase = self._hospitals[hospital_id].phase
        self._hospitals[hospital_id].phase = new_phase
        
        logger.info(f"Hospital {hospital_id} phase changed: {old_phase.value} -> {new_phase.value}")
    
    def get_all_hospitals(self) -> List[PilotMetrics]:
        """Get metrics for all hospitals in the pilot program."""
        return list(self._hospitals.values())
    
    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all pilot hospitals."""
        hospitals = self.get_all_hospitals()
        
        if not hospitals:
            return {"error": "No hospitals in pilot program"}
        
        return {
            "total_hospitals": len(hospitals),
            "hospitals_by_phase": {
                phase.value: len([h for h in hospitals if h.phase == phase])
                for phase in PilotPhase
            },
            "total_physicians": sum(h.total_physicians for h in hospitals),
            "active_physicians_24h": sum(h.active_physicians_24h for h in hospitals),
            "total_encounters": sum(h.total_encounters_processed for h in hospitals),
            "encounters_today": sum(h.encounters_today for h in hospitals),
            "avg_satisfaction": (
                sum(h.physician_satisfaction for h in hospitals) / len(hospitals)
                if hospitals else 0
            ),
            "avg_uptime": (
                sum(h.uptime_percent for h in hospitals) / len(hospitals)
                if hospitals else 0
            ),
            "total_hours_saved": sum(h.total_hours_saved for h in hospitals),
            "hospitals_production_ready": len([
                h for h in hospitals if h.is_ready_for_production()[0]
            ]),
            "hospitals_with_issues": len([
                h for h in hospitals 
                if MetricStatus.CRITICAL in h.get_health_summary().values()
            ]),
        }


class PilotDashboardExporter:
    """
    Exports pilot metrics to various dashboards and reporting systems.
    """
    
    def __init__(self, collector: PilotMetricsCollector):
        self.collector = collector
    
    async def export_to_datadog(self, hospital_id: str):
        """Export metrics to Datadog for visualization."""
        metrics = self.collector._hospitals.get(hospital_id)
        if not metrics:
            return
        
        # This would use Datadog's API to submit custom metrics
        # For now, we just log what we would send
        datadog_metrics = [
            ("phoenix.pilot.encounters.total", metrics.total_encounters_processed),
            ("phoenix.pilot.latency.p95", metrics.p95_latency_ms),
            ("phoenix.pilot.satisfaction", metrics.physician_satisfaction),
            ("phoenix.pilot.uptime", metrics.uptime_percent),
            ("phoenix.pilot.time_saved_hours", metrics.total_hours_saved),
        ]
        
        for metric_name, value in datadog_metrics:
            logger.debug(f"Datadog: {metric_name}={value} hospital:{hospital_id}")
    
    def export_to_csv(self, output_path: str):
        """Export all pilot metrics to CSV for executive reporting."""
        import csv
        
        hospitals = self.collector.get_all_hospitals()
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                "Hospital ID", "Hospital Name", "Phase", "Start Date",
                "Total Physicians", "Active (24h)", "Total Encounters", "Today",
                "Avg Gen Time (ms)", "P95 Latency (ms)", "Error Rate %",
                "SOAP Completeness %", "Edit Rate %", "Satisfaction",
                "Uptime %", "Support Tickets (Week)", "P0 Incidents", "P1 Incidents",
                "Time Saved (hours)", "Production Ready",
            ])
            
            # Data rows
            for h in hospitals:
                ready, _ = h.is_ready_for_production()
                writer.writerow([
                    h.hospital_id, h.hospital_name, h.phase.value, h.start_date.date(),
                    h.total_physicians, h.active_physicians_24h, h.total_encounters_processed, h.encounters_today,
                    f"{h.avg_generation_time_ms:.1f}", f"{h.p95_latency_ms:.1f}", f"{h.error_rate_percent:.3f}",
                    f"{h.soap_completeness_score:.1f}", f"{h.physician_edit_rate:.1f}", f"{h.physician_satisfaction:.2f}",
                    f"{h.uptime_percent:.2f}", h.support_tickets_week, h.p0_incidents, h.p1_incidents,
                    f"{h.total_hours_saved:.1f}", "Yes" if ready else "No",
                ])
        
        logger.info(f"Exported pilot metrics to {output_path}")
    
    def generate_executive_summary(self) -> str:
        """Generate an executive summary of the pilot program."""
        aggregate = self.collector.get_aggregate_metrics()
        hospitals = self.collector.get_all_hospitals()
        
        summary = f"""
# Phoenix Guardian Pilot Program - Executive Summary

Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

## Overview

| Metric | Value |
|--------|-------|
| Total Pilot Hospitals | {aggregate['total_hospitals']} |
| Total Physicians | {aggregate['total_physicians']} |
| Active Physicians (24h) | {aggregate['active_physicians_24h']} |
| Total Encounters Processed | {aggregate['total_encounters']:,} |
| Encounters Today | {aggregate['encounters_today']:,} |
| Avg Physician Satisfaction | {aggregate['avg_satisfaction']:.2f}/5.0 |
| Avg Uptime | {aggregate['avg_uptime']:.2f}% |
| Total Hours Saved | {aggregate['total_hours_saved']:,.1f} |

## Hospital Status by Phase

| Phase | Count |
|-------|-------|
"""
        for phase, count in aggregate['hospitals_by_phase'].items():
            if count > 0:
                summary += f"| {phase.replace('_', ' ').title()} | {count} |\n"
        
        summary += f"""
## Production Readiness

- Ready for production: **{aggregate['hospitals_production_ready']}** hospitals
- Hospitals with critical issues: **{aggregate['hospitals_with_issues']}**

## Individual Hospital Status

"""
        for h in hospitals:
            ready, blockers = h.is_ready_for_production()
            status_emoji = "✅" if ready else "⚠️"
            summary += f"### {status_emoji} {h.hospital_name} ({h.hospital_id})\n"
            summary += f"- Phase: {h.phase.value.replace('_', ' ').title()}\n"
            summary += f"- Encounters: {h.total_encounters_processed:,} total, {h.encounters_today} today\n"
            summary += f"- Satisfaction: {h.physician_satisfaction:.2f}/5.0\n"
            if not ready:
                summary += f"- Blockers: {', '.join(blockers)}\n"
            summary += "\n"
        
        return summary


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    # Create mock metrics for testing
    metrics = PilotMetrics(
        hospital_id="hospital-001",
        hospital_name="Memorial General Hospital",
        start_date=datetime.utcnow() - timedelta(days=14),
        phase=PilotPhase.BETA,
        total_physicians=25,
        active_physicians_24h=18,
        total_encounters_processed=847,
        encounters_today=42,
        avg_generation_time_ms=2340.5,
        p95_latency_ms=4120.3,
        p99_latency_ms=6890.1,
        error_rate_percent=0.08,
        soap_completeness_score=96.4,
        physician_edit_rate=22.5,
        clinical_accuracy_score=94.2,
        physician_satisfaction=4.3,
        nps_score=45,
        uptime_percent=99.87,
        support_tickets_open=3,
        support_tickets_week=7,
        p0_incidents=0,
        p1_incidents=1,
        avg_time_saved_minutes=8.5,
        total_hours_saved=119.8,
        federated_learning_enabled=True,
        model_updates_contributed=12,
        privacy_budget_remaining=0.82,
    )
    
    print("=== Pilot Metrics ===")
    print(json.dumps(metrics.to_dict(), indent=2, default=str))
    
    print("\n=== Health Summary ===")
    for metric, status in metrics.get_health_summary().items():
        print(f"  {metric}: {status.value}")
    
    print("\n=== Production Readiness ===")
    ready, blockers = metrics.is_ready_for_production()
    print(f"  Ready: {ready}")
    if blockers:
        print(f"  Blockers: {blockers}")
