#!/usr/bin/env python3
"""
Phoenix Guardian - Weekly Pilot Report Generator
Generates comprehensive weekly reports for pilot hospital stakeholders.

This script:
- Aggregates Phase 2 benchmark metrics
- Compares performance vs. targets
- Generates executive summary
- Creates trend analysis
- Exports to multiple formats (HTML, PDF, JSON)
"""

import argparse
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from phoenix_guardian.telemetry.benchmark_comparator import PHASE2_BENCHMARKS

logger = logging.getLogger(__name__)


# ==============================================================================
# Constants
# ==============================================================================

REPORT_VERSION = "1.0.0"

# Benchmark targets
TARGETS = {
    "time_saved_minutes": 12.3,
    "physician_satisfaction": 4.3,
    "attack_detection_rate": 0.974,
    "p95_latency_ms": 200,
    "ai_acceptance_rate": 0.85,
}


# ==============================================================================
# Data Classes
# ==============================================================================

class MetricStatus(Enum):
    """Status of a metric vs target."""
    EXCEEDS = "exceeds"          # > 110% of target
    MEETS = "meets"               # 95-110% of target
    BELOW = "below"               # 80-95% of target
    CRITICAL = "critical"         # < 80% of target


@dataclass
class MetricSummary:
    """Summary of a single metric for the week."""
    name: str
    display_name: str
    value: float
    target: float
    unit: str
    status: MetricStatus
    
    # Trend
    previous_value: Optional[float] = None
    trend_percent: Optional[float] = None
    
    # Distribution
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    p50_value: Optional[float] = None
    p95_value: Optional[float] = None
    
    @property
    def target_percent(self) -> float:
        """Percentage of target achieved."""
        if self.target == 0:
            return 100.0
        return (self.value / self.target) * 100
    
    def get_status_emoji(self) -> str:
        """Get emoji for status."""
        return {
            MetricStatus.EXCEEDS: "🟢",
            MetricStatus.MEETS: "✅",
            MetricStatus.BELOW: "🟡",
            MetricStatus.CRITICAL: "🔴",
        }[self.status]


@dataclass
class IncidentSummary:
    """Summary of incidents for the week."""
    total_incidents: int = 0
    p1_incidents: int = 0
    p2_incidents: int = 0
    p3_incidents: int = 0
    p4_incidents: int = 0
    
    mttr_minutes: float = 0.0
    sla_compliance_percent: float = 100.0
    
    notable_incidents: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FeedbackSummary:
    """Summary of physician feedback for the week."""
    total_responses: int = 0
    average_rating: float = 0.0
    nps_score: int = 0
    
    # Breakdown
    positive_percent: float = 0.0
    neutral_percent: float = 0.0
    negative_percent: float = 0.0
    
    # Issues
    false_positives_reported: int = 0
    feature_requests: int = 0
    
    # Top themes
    top_positive_themes: List[str] = field(default_factory=list)
    top_improvement_themes: List[str] = field(default_factory=list)


@dataclass
class WeeklyReport:
    """Complete weekly pilot report."""
    report_id: str
    hospital_id: str
    hospital_name: str
    
    # Time range
    week_number: int
    start_date: datetime
    end_date: datetime
    generated_at: datetime
    
    # Content
    executive_summary: str = ""
    metrics: List[MetricSummary] = field(default_factory=list)
    incidents: IncidentSummary = field(default_factory=IncidentSummary)
    feedback: FeedbackSummary = field(default_factory=FeedbackSummary)
    
    # Trends
    week_over_week_highlights: List[str] = field(default_factory=list)
    
    # Actions
    recommendations: List[str] = field(default_factory=list)
    next_week_focus: List[str] = field(default_factory=list)


# ==============================================================================
# Report Generator
# ==============================================================================

class WeeklyReportGenerator:
    """
    Generates weekly pilot reports.
    
    Aggregates data from various sources:
    - TimescaleDB for metrics
    - Feedback database
    - Incident management system
    
    Example:
        generator = WeeklyReportGenerator(
            timescale_conn="postgresql://...",
            hospital_id="medsys"
        )
        
        report = generator.generate_report(
            start_date=datetime(2024, 1, 15),
            end_date=datetime(2024, 1, 21)
        )
        
        generator.export_html(report, Path("./reports/week3.html"))
    """
    
    def __init__(
        self,
        hospital_id: str,
        hospital_name: str,
        timescale_conn: Optional[str] = None,
    ):
        self._hospital_id = hospital_id
        self._hospital_name = hospital_name
        self._timescale_conn = timescale_conn
    
    def generate_report(
        self,
        start_date: datetime,
        end_date: datetime,
        week_number: int = 1,
    ) -> WeeklyReport:
        """Generate a complete weekly report."""
        report = WeeklyReport(
            report_id=f"{self._hospital_id}-week{week_number}-{start_date.strftime('%Y%m%d')}",
            hospital_id=self._hospital_id,
            hospital_name=self._hospital_name,
            week_number=week_number,
            start_date=start_date,
            end_date=end_date,
            generated_at=datetime.utcnow(),
        )
        
        # Gather metrics
        report.metrics = self._gather_metrics(start_date, end_date)
        
        # Gather incidents
        report.incidents = self._gather_incidents(start_date, end_date)
        
        # Gather feedback
        report.feedback = self._gather_feedback(start_date, end_date)
        
        # Generate executive summary
        report.executive_summary = self._generate_executive_summary(report)
        
        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)
        
        return report
    
    def _gather_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[MetricSummary]:
        """Gather metrics for the week."""
        # In production, query TimescaleDB
        # For now, return example data
        metrics = []
        
        # Time Saved
        time_saved = 13.2  # Example value
        metrics.append(self._create_metric_summary(
            name="time_saved_minutes",
            display_name="Time Saved per Encounter",
            value=time_saved,
            target=TARGETS["time_saved_minutes"],
            unit="minutes",
            previous_value=12.8,
        ))
        
        # Physician Satisfaction
        satisfaction = 4.4
        metrics.append(self._create_metric_summary(
            name="physician_satisfaction",
            display_name="Physician Satisfaction",
            value=satisfaction,
            target=TARGETS["physician_satisfaction"],
            unit="/5",
            previous_value=4.2,
        ))
        
        # Attack Detection Rate
        detection = 0.981
        metrics.append(self._create_metric_summary(
            name="attack_detection_rate",
            display_name="Attack Detection Rate",
            value=detection,
            target=TARGETS["attack_detection_rate"],
            unit="%",
            previous_value=0.975,
        ))
        
        # P95 Latency
        latency = 145
        metrics.append(self._create_metric_summary(
            name="p95_latency_ms",
            display_name="P95 Latency",
            value=latency,
            target=TARGETS["p95_latency_ms"],
            unit="ms",
            previous_value=158,
            lower_is_better=True,
        ))
        
        # AI Acceptance Rate
        acceptance = 0.88
        metrics.append(self._create_metric_summary(
            name="ai_acceptance_rate",
            display_name="AI Suggestion Acceptance",
            value=acceptance,
            target=TARGETS["ai_acceptance_rate"],
            unit="%",
            previous_value=0.84,
        ))
        
        return metrics
    
    def _create_metric_summary(
        self,
        name: str,
        display_name: str,
        value: float,
        target: float,
        unit: str,
        previous_value: Optional[float] = None,
        lower_is_better: bool = False,
    ) -> MetricSummary:
        """Create a metric summary with computed fields."""
        # Calculate status
        if lower_is_better:
            ratio = target / value if value > 0 else 1.0
        else:
            ratio = value / target if target > 0 else 1.0
        
        if ratio >= 1.1:
            status = MetricStatus.EXCEEDS
        elif ratio >= 0.95:
            status = MetricStatus.MEETS
        elif ratio >= 0.8:
            status = MetricStatus.BELOW
        else:
            status = MetricStatus.CRITICAL
        
        # Calculate trend
        trend = None
        if previous_value is not None and previous_value > 0:
            trend = ((value - previous_value) / previous_value) * 100
        
        return MetricSummary(
            name=name,
            display_name=display_name,
            value=value,
            target=target,
            unit=unit,
            status=status,
            previous_value=previous_value,
            trend_percent=trend,
        )
    
    def _gather_incidents(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> IncidentSummary:
        """Gather incident data for the week."""
        # In production, query incident management system
        return IncidentSummary(
            total_incidents=3,
            p1_incidents=0,
            p2_incidents=1,
            p3_incidents=2,
            p4_incidents=0,
            mttr_minutes=45.2,
            sla_compliance_percent=100.0,
            notable_incidents=[
                {
                    "id": "INC-1234",
                    "title": "Brief latency spike during peak hours",
                    "priority": "P2",
                    "resolved": True,
                    "root_cause": "Database connection pool exhaustion",
                }
            ],
        )
    
    def _gather_feedback(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> FeedbackSummary:
        """Gather feedback data for the week."""
        # In production, query feedback database
        return FeedbackSummary(
            total_responses=47,
            average_rating=4.4,
            nps_score=42,
            positive_percent=78.0,
            neutral_percent=15.0,
            negative_percent=7.0,
            false_positives_reported=3,
            feature_requests=5,
            top_positive_themes=[
                "Time savings on documentation",
                "Accurate clinical suggestions",
                "Easy to use interface",
            ],
            top_improvement_themes=[
                "Faster loading of patient history",
                "More specialty-specific templates",
            ],
        )
    
    def _generate_executive_summary(self, report: WeeklyReport) -> str:
        """Generate executive summary paragraph."""
        # Count metrics by status
        exceeds = sum(1 for m in report.metrics if m.status == MetricStatus.EXCEEDS)
        meets = sum(1 for m in report.metrics if m.status == MetricStatus.MEETS)
        below = sum(1 for m in report.metrics if m.status == MetricStatus.BELOW)
        critical = sum(1 for m in report.metrics if m.status == MetricStatus.CRITICAL)
        
        total = len(report.metrics)
        on_track = exceeds + meets
        
        summary = f"""Week {report.week_number} Pilot Performance Summary for {report.hospital_name}

Overall Status: {on_track}/{total} metrics meeting or exceeding Phase 2 targets.

"""
        
        # Add highlights
        if exceeds > 0:
            exceeding = [m for m in report.metrics if m.status == MetricStatus.EXCEEDS]
            summary += f"✨ Exceeding targets: {', '.join(m.display_name for m in exceeding)}\n"
        
        if critical > 0:
            critical_metrics = [m for m in report.metrics if m.status == MetricStatus.CRITICAL]
            summary += f"⚠️ Needs attention: {', '.join(m.display_name for m in critical_metrics)}\n"
        
        summary += f"""
Physician Engagement: {report.feedback.total_responses} feedback responses received with {report.feedback.average_rating:.1f}/5.0 average rating.

Operational Stability: {report.incidents.total_incidents} incidents this week, {report.incidents.sla_compliance_percent}% SLA compliance.
"""
        
        return summary.strip()
    
    def _generate_recommendations(self, report: WeeklyReport) -> List[str]:
        """Generate recommendations based on report data."""
        recommendations = []
        
        # Check for below-target metrics
        for metric in report.metrics:
            if metric.status == MetricStatus.BELOW:
                recommendations.append(
                    f"Review {metric.display_name}: Currently at {metric.value}{metric.unit}, "
                    f"target is {metric.target}{metric.unit}"
                )
            elif metric.status == MetricStatus.CRITICAL:
                recommendations.append(
                    f"PRIORITY: Improve {metric.display_name}: Currently at {metric.value}{metric.unit}, "
                    f"significantly below target of {metric.target}{metric.unit}"
                )
        
        # Check false positive rate
        if report.feedback.false_positives_reported > 5:
            recommendations.append(
                f"Investigate false positive rate: {report.feedback.false_positives_reported} "
                "reports this week, consider ML model retraining"
            )
        
        # Check incident trends
        if report.incidents.p1_incidents > 0:
            recommendations.append(
                f"Review P1 incidents: {report.incidents.p1_incidents} occurred this week"
            )
        
        return recommendations
    
    # =========================================================================
    # Export Methods
    # =========================================================================
    
    def export_html(self, report: WeeklyReport, output_path: Path) -> None:
        """Export report as HTML."""
        html = self._render_html_report(report)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info(f"HTML report exported to {output_path}")
    
    def export_json(self, report: WeeklyReport, output_path: Path) -> None:
        """Export report as JSON."""
        data = self._report_to_dict(report)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.info(f"JSON report exported to {output_path}")
    
    def _report_to_dict(self, report: WeeklyReport) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "report_id": report.report_id,
            "hospital_id": report.hospital_id,
            "hospital_name": report.hospital_name,
            "week_number": report.week_number,
            "start_date": report.start_date.isoformat(),
            "end_date": report.end_date.isoformat(),
            "generated_at": report.generated_at.isoformat(),
            "executive_summary": report.executive_summary,
            "metrics": [
                {
                    "name": m.name,
                    "display_name": m.display_name,
                    "value": m.value,
                    "target": m.target,
                    "unit": m.unit,
                    "status": m.status.value,
                    "target_percent": m.target_percent,
                    "trend_percent": m.trend_percent,
                }
                for m in report.metrics
            ],
            "incidents": {
                "total": report.incidents.total_incidents,
                "p1": report.incidents.p1_incidents,
                "p2": report.incidents.p2_incidents,
                "p3": report.incidents.p3_incidents,
                "p4": report.incidents.p4_incidents,
                "mttr_minutes": report.incidents.mttr_minutes,
                "sla_compliance": report.incidents.sla_compliance_percent,
            },
            "feedback": {
                "total_responses": report.feedback.total_responses,
                "average_rating": report.feedback.average_rating,
                "nps_score": report.feedback.nps_score,
                "false_positives": report.feedback.false_positives_reported,
            },
            "recommendations": report.recommendations,
        }
    
    def _render_html_report(self, report: WeeklyReport) -> str:
        """Render report as HTML."""
        metrics_html = ""
        for m in report.metrics:
            trend = ""
            if m.trend_percent is not None:
                arrow = "↑" if m.trend_percent > 0 else "↓" if m.trend_percent < 0 else "→"
                trend = f'<span class="trend">{arrow} {abs(m.trend_percent):.1f}%</span>'
            
            metrics_html += f"""
            <tr class="metric-row status-{m.status.value}">
                <td>{m.get_status_emoji()} {m.display_name}</td>
                <td class="value">{m.value}{m.unit}</td>
                <td class="target">{m.target}{m.unit}</td>
                <td class="percent">{m.target_percent:.1f}%</td>
                <td>{trend}</td>
            </tr>
            """
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phoenix Guardian - Week {report.week_number} Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }}
        .header h1 {{ margin: 0; font-size: 28px; }}
        .header .subtitle {{ opacity: 0.9; margin-top: 10px; }}
        .section {{ background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 20px; margin-bottom: 20px; }}
        .section h2 {{ margin-top: 0; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        .status-exceeds {{ background: #e8f5e9; }}
        .status-meets {{ background: #fff; }}
        .status-below {{ background: #fff8e1; }}
        .status-critical {{ background: #ffebee; }}
        .value {{ font-weight: bold; }}
        .trend {{ font-size: 14px; color: #666; }}
        .summary {{ white-space: pre-line; line-height: 1.6; }}
        .recommendations li {{ margin-bottom: 10px; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 40px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔥 Phoenix Guardian Weekly Report</h1>
        <div class="subtitle">
            {report.hospital_name} | Week {report.week_number} | {report.start_date.strftime('%B %d')} - {report.end_date.strftime('%B %d, %Y')}
        </div>
    </div>

    <div class="section">
        <h2>📊 Executive Summary</h2>
        <div class="summary">{report.executive_summary}</div>
    </div>

    <div class="section">
        <h2>📈 Phase 2 Benchmark Metrics</h2>
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                    <th>Target</th>
                    <th>% of Target</th>
                    <th>Trend</th>
                </tr>
            </thead>
            <tbody>
                {metrics_html}
            </tbody>
        </table>
    </div>

    <div class="section">
        <h2>👨‍⚕️ Physician Feedback</h2>
        <p><strong>Responses:</strong> {report.feedback.total_responses} | <strong>Avg Rating:</strong> {report.feedback.average_rating:.1f}/5.0 | <strong>NPS:</strong> {report.feedback.nps_score}</p>
        <p><strong>False Positives Reported:</strong> {report.feedback.false_positives_reported} | <strong>Feature Requests:</strong> {report.feedback.feature_requests}</p>
    </div>

    <div class="section">
        <h2>🔧 Operational Summary</h2>
        <p><strong>Incidents:</strong> {report.incidents.total_incidents} (P1: {report.incidents.p1_incidents}, P2: {report.incidents.p2_incidents}, P3: {report.incidents.p3_incidents})</p>
        <p><strong>MTTR:</strong> {report.incidents.mttr_minutes:.1f} minutes | <strong>SLA Compliance:</strong> {report.incidents.sla_compliance_percent}%</p>
    </div>

    <div class="section">
        <h2>💡 Recommendations</h2>
        <ul class="recommendations">
            {''.join(f'<li>{r}</li>' for r in report.recommendations) if report.recommendations else '<li>All metrics on track - continue current approach</li>'}
        </ul>
    </div>

    <div class="footer">
        Generated by Phoenix Guardian v{REPORT_VERSION} | Report ID: {report.report_id} | {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
    </div>
</body>
</html>"""


# ==============================================================================
# CLI
# ==============================================================================

def main():
    """Main entry point for weekly report generation."""
    parser = argparse.ArgumentParser(
        description="Generate Phoenix Guardian weekly pilot reports"
    )
    parser.add_argument(
        "--hospital-id",
        required=True,
        help="Hospital identifier (e.g., medsys, regional-health)"
    )
    parser.add_argument(
        "--hospital-name",
        required=True,
        help="Hospital display name"
    )
    parser.add_argument(
        "--week",
        type=int,
        default=1,
        help="Week number of the pilot"
    )
    parser.add_argument(
        "--start-date",
        help="Start date (YYYY-MM-DD), defaults to 7 days ago"
    )
    parser.add_argument(
        "--end-date",
        help="End date (YYYY-MM-DD), defaults to today"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./reports"),
        help="Output directory for reports"
    )
    parser.add_argument(
        "--format",
        choices=["html", "json", "both"],
        default="both",
        help="Output format"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    # Parse dates
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    else:
        end_date = datetime.utcnow()
    
    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    else:
        start_date = end_date - timedelta(days=7)
    
    # Generate report
    generator = WeeklyReportGenerator(
        hospital_id=args.hospital_id,
        hospital_name=args.hospital_name,
    )
    
    report = generator.generate_report(
        start_date=start_date,
        end_date=end_date,
        week_number=args.week,
    )
    
    # Export
    output_dir = args.output_dir / args.hospital_id
    
    if args.format in ("html", "both"):
        html_path = output_dir / f"week{args.week}_report.html"
        generator.export_html(report, html_path)
        print(f"✅ HTML report: {html_path}")
    
    if args.format in ("json", "both"):
        json_path = output_dir / f"week{args.week}_report.json"
        generator.export_json(report, json_path)
        print(f"✅ JSON report: {json_path}")
    
    print(f"\n📊 Report Summary for {args.hospital_name}:")
    print(f"   Week {args.week}: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    for m in report.metrics:
        print(f"   {m.get_status_emoji()} {m.display_name}: {m.value}{m.unit} ({m.target_percent:.0f}% of target)")


if __name__ == "__main__":
    main()
