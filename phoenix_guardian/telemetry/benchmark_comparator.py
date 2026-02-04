"""
Phoenix Guardian - Benchmark Comparator
Compare actual pilot metrics to Phase 2 promises.

This is the CRITICAL validation tool that proves Phoenix Guardian works.

Phase 2 Promises (from UIP17 submission):
- Time saved: 12.3 minutes per patient encounter
- Physician satisfaction: 4.3/5.0
- Attack detection rate: 97.4%
- P95 API latency: <200ms
- AI acceptance rate: 85% (without major edits)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import statistics
import logging

from phoenix_guardian.telemetry.encounter_metrics import EncounterMetrics

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class BenchmarkStatus(Enum):
    """Status of benchmark comparison."""
    EXCEEDING = "exceeding"      # Better than promised (>10% margin)
    MEETING = "meeting"          # Within acceptable range (±10%)
    BELOW = "below"              # Below promised (>10% worse)
    INSUFFICIENT_DATA = "insufficient_data"  # Not enough data


class MetricTrend(Enum):
    """Trend direction for a metric."""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    UNKNOWN = "unknown"


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class BenchmarkResult:
    """
    Comparison of actual metric vs Phase 2 promise.
    
    Includes statistical confidence and trend analysis.
    """
    metric_name: str
    metric_label: str                          # Human-readable label
    
    # Values
    phase2_promise: float
    actual_value: float
    delta: float                               # actual - promise
    delta_percentage: float                    # (actual - promise) / promise * 100
    
    # Status
    status: BenchmarkStatus
    higher_is_better: bool = True              # For latency, higher is worse
    
    # Statistical confidence
    sample_size: int = 0
    confidence_interval: Tuple[float, float] = (0.0, 0.0)  # 95% CI
    standard_deviation: float = 0.0
    
    # Trend
    trend: MetricTrend = MetricTrend.UNKNOWN
    trend_percentage: float = 0.0              # % change over period
    
    # Alerts
    alert_triggered: bool = False
    alert_message: Optional[str] = None
    
    def __post_init__(self):
        """Calculate derived values."""
        if self.phase2_promise != 0:
            self.delta_percentage = (
                (self.actual_value - self.phase2_promise) / self.phase2_promise * 100
            )
        
        # Determine alert status
        if self.status == BenchmarkStatus.BELOW:
            self.alert_triggered = True
            self.alert_message = (
                f"{self.metric_label} is {abs(self.delta_percentage):.1f}% "
                f"{'below' if self.higher_is_better else 'above'} target"
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "metric_name": self.metric_name,
            "metric_label": self.metric_label,
            "phase2_promise": self.phase2_promise,
            "actual_value": round(self.actual_value, 2),
            "delta": round(self.delta, 2),
            "delta_percentage": round(self.delta_percentage, 1),
            "status": self.status.value,
            "sample_size": self.sample_size,
            "confidence_interval": [round(ci, 2) for ci in self.confidence_interval],
            "standard_deviation": round(self.standard_deviation, 2),
            "trend": self.trend.value,
            "trend_percentage": round(self.trend_percentage, 1),
            "alert_triggered": self.alert_triggered,
            "alert_message": self.alert_message,
        }


@dataclass
class BenchmarkReport:
    """
    Complete benchmark comparison report.
    
    Generated weekly for pilot hospital contacts.
    """
    tenant_id: str
    hospital_name: str
    report_period_start: datetime
    report_period_end: datetime
    generated_at: datetime = field(default_factory=datetime.now)
    
    # Results
    results: Dict[str, BenchmarkResult] = field(default_factory=dict)
    
    # Summary
    total_encounters: int = 0
    completed_encounters: int = 0
    failed_encounters: int = 0
    
    # Overall status
    overall_status: BenchmarkStatus = BenchmarkStatus.INSUFFICIENT_DATA
    benchmarks_met: int = 0
    benchmarks_exceeded: int = 0
    benchmarks_below: int = 0
    
    def __post_init__(self):
        """Calculate summary statistics."""
        self._calculate_overall_status()
    
    def _calculate_overall_status(self):
        """Determine overall benchmark status."""
        if not self.results:
            self.overall_status = BenchmarkStatus.INSUFFICIENT_DATA
            return
        
        for result in self.results.values():
            if result.status == BenchmarkStatus.EXCEEDING:
                self.benchmarks_exceeded += 1
            elif result.status == BenchmarkStatus.MEETING:
                self.benchmarks_met += 1
            elif result.status == BenchmarkStatus.BELOW:
                self.benchmarks_below += 1
        
        if self.benchmarks_below > 0:
            self.overall_status = BenchmarkStatus.BELOW
        elif self.benchmarks_exceeded >= len(self.results) // 2:
            self.overall_status = BenchmarkStatus.EXCEEDING
        else:
            self.overall_status = BenchmarkStatus.MEETING
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "hospital_name": self.hospital_name,
            "report_period_start": self.report_period_start.isoformat(),
            "report_period_end": self.report_period_end.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "total_encounters": self.total_encounters,
            "completed_encounters": self.completed_encounters,
            "failed_encounters": self.failed_encounters,
            "overall_status": self.overall_status.value,
            "benchmarks_met": self.benchmarks_met,
            "benchmarks_exceeded": self.benchmarks_exceeded,
            "benchmarks_below": self.benchmarks_below,
        }


# ==============================================================================
# Benchmark Comparator
# ==============================================================================

class BenchmarkComparator:
    """
    Compare pilot metrics to Phase 2 promises.
    
    Phase 2 Promises (from UIP17 submission):
    - Time saved: 12.3 minutes per patient
    - Physician satisfaction: 4.3/5.0
    - Attack detection rate: 97.4%
    - P95 latency: <200ms
    - AI acceptance rate: 85%
    
    Example:
        comparator = BenchmarkComparator(tenant_id="pilot_hospital_001")
        
        for encounter in encounters:
            comparator.add_encounter(encounter)
        
        report = comparator.generate_report(
            hospital_name="Test Hospital",
            period_start=datetime(2026, 2, 1),
            period_end=datetime(2026, 2, 7)
        )
        
        print(report.overall_status)  # MEETING, EXCEEDING, or BELOW
    """
    
    # Phase 2 benchmark promises
    PHASE2_BENCHMARKS = {
        "time_saved_minutes": {
            "value": 12.3,
            "label": "Time Saved Per Patient",
            "higher_is_better": True,
            "margin": 0.10,  # 10% acceptable margin
        },
        "physician_satisfaction": {
            "value": 4.3,
            "label": "Physician Satisfaction",
            "higher_is_better": True,
            "margin": 0.10,
        },
        "attack_detection_rate": {
            "value": 0.974,
            "label": "Attack Detection Rate",
            "higher_is_better": True,
            "margin": 0.05,  # Stricter for security
        },
        "p95_latency_ms": {
            "value": 200.0,
            "label": "P95 API Latency (ms)",
            "higher_is_better": False,  # Lower is better
            "margin": 0.10,
        },
        "ai_acceptance_rate": {
            "value": 0.85,
            "label": "AI Acceptance Rate",
            "higher_is_better": True,
            "margin": 0.10,
        },
    }
    
    # Minimum sample size for reliable statistics
    MIN_SAMPLE_SIZE = 30
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.encounters: List[EncounterMetrics] = []
        self._historical_values: Dict[str, List[float]] = {}  # For trend analysis
    
    def add_encounter(self, encounter: EncounterMetrics) -> None:
        """Add an encounter to the comparison set."""
        self.encounters.append(encounter)
    
    def add_encounters(self, encounters: List[EncounterMetrics]) -> None:
        """Add multiple encounters."""
        self.encounters.extend(encounters)
    
    def clear(self) -> None:
        """Clear all encounters."""
        self.encounters.clear()
    
    # =========================================================================
    # Benchmark Comparison
    # =========================================================================
    
    def compare_benchmarks(self) -> Dict[str, BenchmarkResult]:
        """
        Compare all benchmarks to Phase 2 promises.
        
        Returns:
            Dict of metric_name -> BenchmarkResult
        """
        if not self.encounters:
            return {}
        
        results = {}
        
        # Time Saved
        time_saved_values = [e.time_saved_minutes for e in self.encounters]
        results["time_saved_minutes"] = self._compare_metric(
            "time_saved_minutes",
            time_saved_values
        )
        
        # Physician Satisfaction
        rated_encounters = [e for e in self.encounters if e.physician_rating is not None]
        if rated_encounters:
            satisfaction_values = [float(e.physician_rating) for e in rated_encounters]
            results["physician_satisfaction"] = self._compare_metric(
                "physician_satisfaction",
                satisfaction_values
            )
        
        # Attack Detection Rate
        attack_detection = self._calculate_attack_detection_rate()
        if attack_detection is not None:
            results["attack_detection_rate"] = self._compare_metric(
                "attack_detection_rate",
                [attack_detection],
                is_rate=True
            )
        
        # P95 Latency
        latency_values = [
            e.api_latency_p95_ms for e in self.encounters
            if e.api_latency_p95_ms > 0
        ]
        if latency_values:
            results["p95_latency_ms"] = self._compare_metric(
                "p95_latency_ms",
                latency_values
            )
        
        # AI Acceptance Rate
        acceptance_values = [e.ai_acceptance_rate for e in self.encounters]
        results["ai_acceptance_rate"] = self._compare_metric(
            "ai_acceptance_rate",
            acceptance_values
        )
        
        return results
    
    def _compare_metric(
        self,
        metric_name: str,
        values: List[float],
        is_rate: bool = False,
    ) -> BenchmarkResult:
        """Compare a single metric to its benchmark."""
        benchmark = self.PHASE2_BENCHMARKS[metric_name]
        promise = benchmark["value"]
        higher_is_better = benchmark["higher_is_better"]
        margin = benchmark["margin"]
        
        # Calculate actual value
        if is_rate:
            actual = values[0] if values else 0.0
        else:
            actual = statistics.mean(values) if values else 0.0
        
        # Calculate delta
        delta = actual - promise
        
        # Determine status
        if len(values) < self.MIN_SAMPLE_SIZE and not is_rate:
            status = BenchmarkStatus.INSUFFICIENT_DATA
        elif higher_is_better:
            if actual >= promise * (1 + margin):
                status = BenchmarkStatus.EXCEEDING
            elif actual >= promise * (1 - margin):
                status = BenchmarkStatus.MEETING
            else:
                status = BenchmarkStatus.BELOW
        else:
            # Lower is better (e.g., latency)
            if actual <= promise * (1 - margin):
                status = BenchmarkStatus.EXCEEDING
            elif actual <= promise * (1 + margin):
                status = BenchmarkStatus.MEETING
            else:
                status = BenchmarkStatus.BELOW
        
        # Calculate confidence interval
        ci = self._calculate_confidence_interval(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
        
        # Calculate trend
        trend, trend_pct = self._calculate_trend(metric_name, actual)
        
        return BenchmarkResult(
            metric_name=metric_name,
            metric_label=benchmark["label"],
            phase2_promise=promise,
            actual_value=actual,
            delta=delta,
            delta_percentage=0.0,  # Calculated in __post_init__
            status=status,
            higher_is_better=higher_is_better,
            sample_size=len(values),
            confidence_interval=ci,
            standard_deviation=std_dev,
            trend=trend,
            trend_percentage=trend_pct,
        )
    
    def _calculate_attack_detection_rate(self) -> Optional[float]:
        """Calculate attack detection rate from encounters."""
        # Count encounters with security events (attacks)
        encounters_with_attacks = [
            e for e in self.encounters
            if len(e.security_events) > 0
        ]
        
        if not encounters_with_attacks:
            return None
        
        # Count detected attacks
        detected = sum(
            1 for e in encounters_with_attacks
            if e.attack_detected and not any(
                se.marked_false_positive for se in e.security_events
            )
        )
        
        return detected / len(encounters_with_attacks)
    
    def _calculate_confidence_interval(
        self,
        values: List[float],
        confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """Calculate confidence interval for a set of values."""
        if len(values) < 2:
            return (0.0, 0.0)
        
        try:
            import scipy.stats as stats
            import numpy as np
            
            mean = np.mean(values)
            sem = stats.sem(values)
            
            if sem == 0:
                return (mean, mean)
            
            ci = stats.t.interval(
                confidence,
                len(values) - 1,
                loc=mean,
                scale=sem
            )
            return (float(ci[0]), float(ci[1]))
            
        except ImportError:
            # Fallback without scipy
            mean = statistics.mean(values)
            std = statistics.stdev(values)
            margin = 1.96 * (std / len(values) ** 0.5)
            return (mean - margin, mean + margin)
    
    def _calculate_trend(
        self,
        metric_name: str,
        current_value: float,
    ) -> Tuple[MetricTrend, float]:
        """Calculate trend for a metric based on historical values."""
        historical = self._historical_values.get(metric_name, [])
        
        if len(historical) < 2:
            # Store current value for next comparison
            if metric_name not in self._historical_values:
                self._historical_values[metric_name] = []
            self._historical_values[metric_name].append(current_value)
            return (MetricTrend.UNKNOWN, 0.0)
        
        # Compare to previous period
        previous = historical[-1]
        
        if previous == 0:
            trend_pct = 0.0
        else:
            trend_pct = ((current_value - previous) / previous) * 100
        
        higher_is_better = self.PHASE2_BENCHMARKS[metric_name]["higher_is_better"]
        
        if abs(trend_pct) < 5:
            trend = MetricTrend.STABLE
        elif (trend_pct > 0 and higher_is_better) or (trend_pct < 0 and not higher_is_better):
            trend = MetricTrend.IMPROVING
        else:
            trend = MetricTrend.DECLINING
        
        # Update historical values
        self._historical_values[metric_name].append(current_value)
        
        return (trend, trend_pct)
    
    # =========================================================================
    # Report Generation
    # =========================================================================
    
    def generate_report(
        self,
        hospital_name: str,
        period_start: datetime,
        period_end: datetime,
    ) -> BenchmarkReport:
        """
        Generate a complete benchmark comparison report.
        
        Args:
            hospital_name: Name of the pilot hospital
            period_start: Start of reporting period
            period_end: End of reporting period
        
        Returns:
            BenchmarkReport with all comparisons
        """
        # Filter encounters to period
        period_encounters = [
            e for e in self.encounters
            if period_start <= e.created_at <= period_end
        ]
        
        # Create comparator with period data
        period_comparator = BenchmarkComparator(self.tenant_id)
        period_comparator.add_encounters(period_encounters)
        period_comparator._historical_values = self._historical_values
        
        # Generate comparisons
        results = period_comparator.compare_benchmarks()
        
        # Count encounter outcomes
        completed = sum(
            1 for e in period_encounters
            if e.phase.value == "completed"
        )
        failed = sum(
            1 for e in period_encounters
            if e.phase.value == "failed"
        )
        
        report = BenchmarkReport(
            tenant_id=self.tenant_id,
            hospital_name=hospital_name,
            report_period_start=period_start,
            report_period_end=period_end,
            results=results,
            total_encounters=len(period_encounters),
            completed_encounters=completed,
            failed_encounters=failed,
        )
        
        return report
    
    def generate_weekly_report(self, hospital_name: str) -> BenchmarkReport:
        """Generate report for the past week."""
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        return self.generate_report(hospital_name, week_ago, now)
    
    # =========================================================================
    # Alert Checking
    # =========================================================================
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """
        Check for any benchmark violations that require alerts.
        
        Returns:
            List of alert dictionaries
        """
        results = self.compare_benchmarks()
        alerts = []
        
        for metric_name, result in results.items():
            if result.alert_triggered:
                alerts.append({
                    "metric": metric_name,
                    "severity": self._get_alert_severity(result),
                    "message": result.alert_message,
                    "actual_value": result.actual_value,
                    "target_value": result.phase2_promise,
                    "delta_percentage": result.delta_percentage,
                    "timestamp": datetime.now().isoformat(),
                })
        
        return alerts
    
    def _get_alert_severity(self, result: BenchmarkResult) -> str:
        """Determine alert severity based on how far below target."""
        if abs(result.delta_percentage) > 30:
            return "critical"
        elif abs(result.delta_percentage) > 20:
            return "high"
        elif abs(result.delta_percentage) > 10:
            return "medium"
        else:
            return "low"
    
    # =========================================================================
    # Summary Methods
    # =========================================================================
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of benchmark status."""
        results = self.compare_benchmarks()
        
        meeting = sum(1 for r in results.values() if r.status == BenchmarkStatus.MEETING)
        exceeding = sum(1 for r in results.values() if r.status == BenchmarkStatus.EXCEEDING)
        below = sum(1 for r in results.values() if r.status == BenchmarkStatus.BELOW)
        
        return {
            "tenant_id": self.tenant_id,
            "total_encounters": len(self.encounters),
            "benchmarks_evaluated": len(results),
            "benchmarks_meeting": meeting,
            "benchmarks_exceeding": exceeding,
            "benchmarks_below": below,
            "overall_health": "healthy" if below == 0 else "attention_needed",
            "alerts": self.check_alerts(),
        }
    
    def print_comparison(self) -> None:
        """Print benchmark comparison to console."""
        results = self.compare_benchmarks()
        
        print("\n" + "=" * 70)
        print("  PHOENIX GUARDIAN - PHASE 2 BENCHMARK COMPARISON")
        print("=" * 70)
        print(f"  Tenant: {self.tenant_id}")
        print(f"  Encounters: {len(self.encounters)}")
        print("-" * 70)
        
        for metric_name, result in results.items():
            status_emoji = {
                BenchmarkStatus.EXCEEDING: "✅ EXCEEDING",
                BenchmarkStatus.MEETING: "✓ MEETING",
                BenchmarkStatus.BELOW: "❌ BELOW",
                BenchmarkStatus.INSUFFICIENT_DATA: "⏳ INSUFFICIENT DATA",
            }[result.status]
            
            print(f"\n  {result.metric_label}")
            print(f"    Promise: {result.phase2_promise}")
            print(f"    Actual:  {result.actual_value:.2f} ({result.delta_percentage:+.1f}%)")
            print(f"    Status:  {status_emoji}")
            print(f"    Samples: {result.sample_size}")
        
        print("\n" + "=" * 70)
