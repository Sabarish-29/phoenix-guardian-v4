"""
Phoenix Guardian - Aggregate Dashboard for Multi-Tenant Analytics

This module provides aggregated analytics across all hospital tenants
while maintaining strict data isolation. Individual hospital PHI is
never combined - only aggregate statistics are computed.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import asyncio
import logging
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class AggregationLevel(Enum):
    """Levels of aggregation for dashboard metrics."""
    SYSTEM = "system"        # All hospitals combined
    REGION = "region"        # By geographic region
    EHR_VENDOR = "ehr_vendor"  # By EHR system (Epic, Cerner, etc.)
    TIER = "tier"            # By hospital size/tier
    PHASE = "phase"          # By pilot phase


@dataclass
class HospitalSummary:
    """Summary metrics for a single hospital (no PHI)."""
    hospital_id: str
    hospital_name: str
    region: str
    ehr_vendor: str
    tier: str
    phase: str
    
    # Counts only - no identifiable data
    total_physicians: int = 0
    active_physicians_24h: int = 0
    total_encounters: int = 0
    encounters_today: int = 0
    
    # Performance (aggregated)
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    error_rate_percent: float = 0.0
    
    # Quality (aggregated)
    soap_completeness: float = 0.0
    edit_rate_percent: float = 0.0
    
    # Satisfaction (aggregated)
    satisfaction_score: float = 0.0
    nps_score: int = 0
    
    # Operational
    uptime_percent: float = 100.0
    support_tickets_open: int = 0


@dataclass
class AggregateMetrics:
    """Aggregated metrics across multiple hospitals."""
    aggregation_key: str  # e.g., "system", "region:northeast", "ehr:epic"
    hospital_count: int = 0
    
    # Usage totals
    total_physicians: int = 0
    active_physicians_24h: int = 0
    total_encounters: int = 0
    encounters_today: int = 0
    
    # Performance averages
    avg_latency_ms: float = 0.0
    avg_p95_latency_ms: float = 0.0
    avg_error_rate: float = 0.0
    
    # Quality averages
    avg_soap_completeness: float = 0.0
    avg_edit_rate: float = 0.0
    
    # Satisfaction averages
    avg_satisfaction: float = 0.0
    avg_nps: float = 0.0
    
    # Operational totals
    avg_uptime: float = 0.0
    total_support_tickets: int = 0
    
    # Distribution metrics
    latency_min: float = 0.0
    latency_max: float = 0.0
    latency_std: float = 0.0
    
    satisfaction_min: float = 0.0
    satisfaction_max: float = 0.0
    
    # Computed
    computed_at: datetime = field(default_factory=datetime.utcnow)


class AggregateDashboard:
    """
    Multi-tenant aggregate dashboard.
    
    PRIVACY GUARANTEE: This class NEVER accesses or combines PHI.
    It only works with pre-aggregated metrics at the hospital level.
    All data is already anonymized before reaching this class.
    """
    
    def __init__(self, metrics_store: Any):
        """
        Initialize dashboard with metrics store.
        
        Args:
            metrics_store: Backend store for hospital metrics
                          (Redis, PostgreSQL, or in-memory for testing)
        """
        self.metrics_store = metrics_store
        self._cache: Dict[str, AggregateMetrics] = {}
        self._cache_ttl = timedelta(minutes=5)
        self._last_cache_update: Optional[datetime] = None
    
    async def get_hospital_summaries(self) -> List[HospitalSummary]:
        """
        Fetch summary metrics for all hospitals.
        
        Returns only pre-aggregated metrics - no PHI access.
        """
        # In production, this would query the metrics database
        # Here we show the expected interface
        summaries = await self.metrics_store.get_all_hospital_summaries()
        return summaries
    
    async def compute_aggregate(
        self,
        level: AggregationLevel,
        filter_value: Optional[str] = None
    ) -> AggregateMetrics:
        """
        Compute aggregate metrics at the specified level.
        
        Args:
            level: Aggregation level (SYSTEM, REGION, etc.)
            filter_value: Optional filter (e.g., "northeast" for REGION)
        
        Returns:
            AggregateMetrics with combined statistics
        """
        # Check cache first
        cache_key = f"{level.value}:{filter_value or 'all'}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        # Get all hospital summaries
        summaries = await self.get_hospital_summaries()
        
        # Filter by level if needed
        if level == AggregationLevel.REGION and filter_value:
            summaries = [s for s in summaries if s.region == filter_value]
        elif level == AggregationLevel.EHR_VENDOR and filter_value:
            summaries = [s for s in summaries if s.ehr_vendor == filter_value]
        elif level == AggregationLevel.TIER and filter_value:
            summaries = [s for s in summaries if s.tier == filter_value]
        elif level == AggregationLevel.PHASE and filter_value:
            summaries = [s for s in summaries if s.phase == filter_value]
        
        # Compute aggregates
        aggregate = self._compute_aggregates(cache_key, summaries)
        
        # Cache result
        self._cache[cache_key] = aggregate
        self._last_cache_update = datetime.utcnow()
        
        return aggregate
    
    def _compute_aggregates(
        self,
        aggregation_key: str,
        summaries: List[HospitalSummary]
    ) -> AggregateMetrics:
        """Compute aggregate metrics from hospital summaries."""
        if not summaries:
            return AggregateMetrics(aggregation_key=aggregation_key)
        
        # Extract values for statistical computation
        latencies = [s.avg_latency_ms for s in summaries if s.avg_latency_ms > 0]
        p95_latencies = [s.p95_latency_ms for s in summaries if s.p95_latency_ms > 0]
        error_rates = [s.error_rate_percent for s in summaries]
        completeness = [s.soap_completeness for s in summaries if s.soap_completeness > 0]
        edit_rates = [s.edit_rate_percent for s in summaries]
        satisfaction = [s.satisfaction_score for s in summaries if s.satisfaction_score > 0]
        nps_scores = [s.nps_score for s in summaries]
        uptimes = [s.uptime_percent for s in summaries]
        
        return AggregateMetrics(
            aggregation_key=aggregation_key,
            hospital_count=len(summaries),
            
            # Totals
            total_physicians=sum(s.total_physicians for s in summaries),
            active_physicians_24h=sum(s.active_physicians_24h for s in summaries),
            total_encounters=sum(s.total_encounters for s in summaries),
            encounters_today=sum(s.encounters_today for s in summaries),
            total_support_tickets=sum(s.support_tickets_open for s in summaries),
            
            # Averages
            avg_latency_ms=statistics.mean(latencies) if latencies else 0,
            avg_p95_latency_ms=statistics.mean(p95_latencies) if p95_latencies else 0,
            avg_error_rate=statistics.mean(error_rates) if error_rates else 0,
            avg_soap_completeness=statistics.mean(completeness) if completeness else 0,
            avg_edit_rate=statistics.mean(edit_rates) if edit_rates else 0,
            avg_satisfaction=statistics.mean(satisfaction) if satisfaction else 0,
            avg_nps=statistics.mean(nps_scores) if nps_scores else 0,
            avg_uptime=statistics.mean(uptimes) if uptimes else 0,
            
            # Distribution
            latency_min=min(latencies) if latencies else 0,
            latency_max=max(latencies) if latencies else 0,
            latency_std=statistics.stdev(latencies) if len(latencies) > 1 else 0,
            satisfaction_min=min(satisfaction) if satisfaction else 0,
            satisfaction_max=max(satisfaction) if satisfaction else 0,
            
            computed_at=datetime.utcnow(),
        )
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached value is still valid."""
        if cache_key not in self._cache:
            return False
        if self._last_cache_update is None:
            return False
        return datetime.utcnow() - self._last_cache_update < self._cache_ttl
    
    async def get_system_overview(self) -> Dict[str, Any]:
        """
        Get complete system overview for executive dashboard.
        
        Returns high-level KPIs across the entire deployment.
        """
        system_metrics = await self.compute_aggregate(AggregationLevel.SYSTEM)
        
        # Get breakdowns by different dimensions
        regions = await self._get_breakdown(AggregationLevel.REGION)
        ehr_vendors = await self._get_breakdown(AggregationLevel.EHR_VENDOR)
        phases = await self._get_breakdown(AggregationLevel.PHASE)
        
        return {
            "overview": {
                "total_hospitals": system_metrics.hospital_count,
                "total_physicians": system_metrics.total_physicians,
                "active_physicians_24h": system_metrics.active_physicians_24h,
                "total_encounters": system_metrics.total_encounters,
                "encounters_today": system_metrics.encounters_today,
            },
            "performance": {
                "avg_latency_ms": round(system_metrics.avg_latency_ms, 1),
                "avg_p95_latency_ms": round(system_metrics.avg_p95_latency_ms, 1),
                "avg_error_rate": round(system_metrics.avg_error_rate, 4),
                "avg_uptime": round(system_metrics.avg_uptime, 2),
            },
            "quality": {
                "avg_soap_completeness": round(system_metrics.avg_soap_completeness, 1),
                "avg_edit_rate": round(system_metrics.avg_edit_rate, 1),
            },
            "satisfaction": {
                "avg_score": round(system_metrics.avg_satisfaction, 2),
                "avg_nps": round(system_metrics.avg_nps, 0),
                "range": {
                    "min": system_metrics.satisfaction_min,
                    "max": system_metrics.satisfaction_max,
                }
            },
            "breakdowns": {
                "by_region": regions,
                "by_ehr_vendor": ehr_vendors,
                "by_phase": phases,
            },
            "computed_at": system_metrics.computed_at.isoformat(),
        }
    
    async def _get_breakdown(
        self,
        level: AggregationLevel
    ) -> Dict[str, Dict[str, Any]]:
        """Get metrics breakdown by a specific dimension."""
        summaries = await self.get_hospital_summaries()
        
        # Group by the dimension
        groups: Dict[str, List[HospitalSummary]] = defaultdict(list)
        for s in summaries:
            if level == AggregationLevel.REGION:
                groups[s.region].append(s)
            elif level == AggregationLevel.EHR_VENDOR:
                groups[s.ehr_vendor].append(s)
            elif level == AggregationLevel.TIER:
                groups[s.tier].append(s)
            elif level == AggregationLevel.PHASE:
                groups[s.phase].append(s)
        
        # Compute aggregates for each group
        result = {}
        for key, group_summaries in groups.items():
            agg = self._compute_aggregates(f"{level.value}:{key}", group_summaries)
            result[key] = {
                "hospital_count": agg.hospital_count,
                "total_encounters": agg.total_encounters,
                "avg_satisfaction": round(agg.avg_satisfaction, 2),
                "avg_latency_ms": round(agg.avg_latency_ms, 1),
            }
        
        return result
    
    async def get_trend_data(
        self,
        metric: str,
        days: int = 30,
        level: AggregationLevel = AggregationLevel.SYSTEM,
        filter_value: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get historical trend data for a specific metric.
        
        Args:
            metric: Metric name (e.g., "encounters", "satisfaction")
            days: Number of days of history
            level: Aggregation level
            filter_value: Optional filter
        
        Returns:
            List of daily data points
        """
        # In production, this would query time-series data from
        # InfluxDB, TimescaleDB, or CloudWatch metrics
        
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)
        
        # Query historical data (placeholder - would hit real DB)
        trend_data = await self.metrics_store.get_metric_history(
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            aggregation_level=level.value,
            filter_value=filter_value,
        )
        
        return trend_data
    
    async def get_comparison_report(
        self,
        hospital_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Generate comparison report for specific hospitals.
        
        Used by executives to compare pilot sites.
        All data is pre-aggregated - no PHI included.
        """
        summaries = await self.get_hospital_summaries()
        selected = [s for s in summaries if s.hospital_id in hospital_ids]
        
        if not selected:
            return {"error": "No matching hospitals found"}
        
        comparison = {
            "hospitals": [],
            "rankings": {},
            "generated_at": datetime.utcnow().isoformat(),
        }
        
        for s in selected:
            comparison["hospitals"].append({
                "hospital_id": s.hospital_id,
                "hospital_name": s.hospital_name,
                "metrics": {
                    "total_encounters": s.total_encounters,
                    "avg_latency_ms": s.avg_latency_ms,
                    "soap_completeness": s.soap_completeness,
                    "satisfaction_score": s.satisfaction_score,
                    "uptime_percent": s.uptime_percent,
                }
            })
        
        # Compute rankings
        comparison["rankings"] = {
            "by_encounters": sorted(
                [h["hospital_id"] for h in comparison["hospitals"]],
                key=lambda x: next(
                    h["metrics"]["total_encounters"]
                    for h in comparison["hospitals"]
                    if h["hospital_id"] == x
                ),
                reverse=True
            ),
            "by_satisfaction": sorted(
                [h["hospital_id"] for h in comparison["hospitals"]],
                key=lambda x: next(
                    h["metrics"]["satisfaction_score"]
                    for h in comparison["hospitals"]
                    if h["hospital_id"] == x
                ),
                reverse=True
            ),
        }
        
        return comparison
    
    async def get_alerts(self) -> List[Dict[str, Any]]:
        """
        Get system-wide alerts across all hospitals.
        
        Returns alerts for:
        - Hospitals with critical metrics
        - Significant deviations from baselines
        - SLA violations
        """
        summaries = await self.get_hospital_summaries()
        alerts = []
        
        for s in summaries:
            # Check for critical conditions
            if s.uptime_percent < 99.0:
                alerts.append({
                    "severity": "high",
                    "hospital_id": s.hospital_id,
                    "hospital_name": s.hospital_name,
                    "type": "uptime_degradation",
                    "message": f"Uptime {s.uptime_percent:.1f}% below 99% SLA",
                    "value": s.uptime_percent,
                    "threshold": 99.0,
                })
            
            if s.error_rate_percent > 1.0:
                alerts.append({
                    "severity": "high",
                    "hospital_id": s.hospital_id,
                    "hospital_name": s.hospital_name,
                    "type": "high_error_rate",
                    "message": f"Error rate {s.error_rate_percent:.2f}% exceeds 1%",
                    "value": s.error_rate_percent,
                    "threshold": 1.0,
                })
            
            if s.satisfaction_score < 3.5:
                alerts.append({
                    "severity": "medium",
                    "hospital_id": s.hospital_id,
                    "hospital_name": s.hospital_name,
                    "type": "low_satisfaction",
                    "message": f"Satisfaction {s.satisfaction_score:.1f}/5 below threshold",
                    "value": s.satisfaction_score,
                    "threshold": 3.5,
                })
            
            if s.p95_latency_ms > 5000:
                alerts.append({
                    "severity": "medium",
                    "hospital_id": s.hospital_id,
                    "hospital_name": s.hospital_name,
                    "type": "high_latency",
                    "message": f"P95 latency {s.p95_latency_ms:.0f}ms exceeds 5000ms",
                    "value": s.p95_latency_ms,
                    "threshold": 5000,
                })
        
        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda x: severity_order.get(x["severity"], 4))
        
        return alerts


class DashboardAPIExporter:
    """
    Export dashboard data to various formats for consumption.
    """
    
    def __init__(self, dashboard: AggregateDashboard):
        self.dashboard = dashboard
    
    async def export_json(self) -> str:
        """Export dashboard data as JSON."""
        import json
        
        overview = await self.dashboard.get_system_overview()
        alerts = await self.dashboard.get_alerts()
        
        return json.dumps({
            "overview": overview,
            "alerts": alerts,
        }, indent=2, default=str)
    
    async def export_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus format.
        
        This allows the aggregate dashboard to be scraped
        by Prometheus for alerting and Grafana visualization.
        """
        metrics = await self.dashboard.compute_aggregate(AggregationLevel.SYSTEM)
        
        lines = [
            "# HELP phoenix_hospitals_total Total number of pilot hospitals",
            "# TYPE phoenix_hospitals_total gauge",
            f"phoenix_hospitals_total {metrics.hospital_count}",
            "",
            "# HELP phoenix_physicians_active Active physicians in last 24h",
            "# TYPE phoenix_physicians_active gauge",
            f"phoenix_physicians_active {metrics.active_physicians_24h}",
            "",
            "# HELP phoenix_encounters_total Total encounters processed",
            "# TYPE phoenix_encounters_total counter",
            f"phoenix_encounters_total {metrics.total_encounters}",
            "",
            "# HELP phoenix_encounters_today Encounters processed today",
            "# TYPE phoenix_encounters_today gauge",
            f"phoenix_encounters_today {metrics.encounters_today}",
            "",
            "# HELP phoenix_latency_avg_ms Average latency in milliseconds",
            "# TYPE phoenix_latency_avg_ms gauge",
            f"phoenix_latency_avg_ms {metrics.avg_latency_ms:.1f}",
            "",
            "# HELP phoenix_latency_p95_ms P95 latency in milliseconds",
            "# TYPE phoenix_latency_p95_ms gauge",
            f"phoenix_latency_p95_ms {metrics.avg_p95_latency_ms:.1f}",
            "",
            "# HELP phoenix_satisfaction_avg Average satisfaction score (1-5)",
            "# TYPE phoenix_satisfaction_avg gauge",
            f"phoenix_satisfaction_avg {metrics.avg_satisfaction:.2f}",
            "",
            "# HELP phoenix_uptime_avg Average uptime percentage",
            "# TYPE phoenix_uptime_avg gauge",
            f"phoenix_uptime_avg {metrics.avg_uptime:.2f}",
            "",
        ]
        
        return "\n".join(lines)


# Mock metrics store for testing
class InMemoryMetricsStore:
    """In-memory metrics store for testing."""
    
    def __init__(self):
        self.summaries: List[HospitalSummary] = []
    
    async def get_all_hospital_summaries(self) -> List[HospitalSummary]:
        return self.summaries
    
    async def get_metric_history(
        self,
        metric: str,
        start_date,
        end_date,
        aggregation_level: str,
        filter_value: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        # Return mock trend data
        from datetime import timedelta
        data = []
        current = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.min.time())
        
        while current <= end:
            data.append({
                "date": current.date().isoformat(),
                "value": 100 + (hash(str(current)) % 50),  # Mock value
            })
            current += timedelta(days=1)
        
        return data


if __name__ == "__main__":
    import asyncio
    
    async def demo():
        # Create in-memory store with sample data
        store = InMemoryMetricsStore()
        store.summaries = [
            HospitalSummary(
                hospital_id="hospital-001",
                hospital_name="Memorial General",
                region="northeast",
                ehr_vendor="epic",
                tier="large",
                phase="production",
                total_physicians=25,
                active_physicians_24h=20,
                total_encounters=850,
                encounters_today=45,
                avg_latency_ms=2500,
                p95_latency_ms=4200,
                error_rate_percent=0.05,
                soap_completeness=96.5,
                edit_rate_percent=22,
                satisfaction_score=4.3,
                nps_score=45,
                uptime_percent=99.8,
                support_tickets_open=2,
            ),
            HospitalSummary(
                hospital_id="hospital-002",
                hospital_name="City Medical Center",
                region="southeast",
                ehr_vendor="cerner",
                tier="medium",
                phase="beta",
                total_physicians=15,
                active_physicians_24h=12,
                total_encounters=320,
                encounters_today=28,
                avg_latency_ms=2800,
                p95_latency_ms=4800,
                error_rate_percent=0.08,
                soap_completeness=94.2,
                edit_rate_percent=28,
                satisfaction_score=4.1,
                nps_score=38,
                uptime_percent=99.5,
                support_tickets_open=4,
            ),
        ]
        
        dashboard = AggregateDashboard(store)
        
        print("=== System Overview ===")
        overview = await dashboard.get_system_overview()
        import json
        print(json.dumps(overview, indent=2, default=str))
        
        print("\n=== Alerts ===")
        alerts = await dashboard.get_alerts()
        print(json.dumps(alerts, indent=2))
        
        print("\n=== Prometheus Metrics ===")
        exporter = DashboardAPIExporter(dashboard)
        prometheus = await exporter.export_prometheus_metrics()
        print(prometheus)
    
    asyncio.run(demo())
