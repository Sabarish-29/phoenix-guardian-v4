"""
Population Health Reporter.

Generates reports and insights for population health management.

REPORT TYPES:

1. Executive Summary
   - High-level KPIs for leadership
   - Trend arrows and benchmarks
   - Top 3 opportunities
   
2. Quality Dashboard
   - All quality measures with rates
   - Star ratings and percentiles
   - Gap counts and trends
   
3. Risk Stratification Report
   - Population distribution by risk level
   - High-risk patient list
   - Care management caseloads
   
4. Care Gap Report
   - Open gaps by measure
   - Outreach status
   - Closure rates
   
5. Provider Scorecard
   - Per-provider quality metrics
   - Panel comparison
   - Improvement opportunities

OUTPUT FORMATS:
    - Summary (for dashboards)
    - Detailed (for quality team)
    - Executive (for leadership)
    - CSV (for data export)
    - PDF (for formal reporting)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, date
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    """Available report formats."""
    SUMMARY = "summary"
    DETAILED = "detailed"
    EXECUTIVE = "executive"
    CSV = "csv"


class ReportType(Enum):
    """Types of population health reports."""
    EXECUTIVE_SUMMARY = "executive_summary"
    QUALITY_DASHBOARD = "quality_dashboard"
    RISK_STRATIFICATION = "risk_stratification"
    CARE_GAP = "care_gap"
    PROVIDER_SCORECARD = "provider_scorecard"


@dataclass
class ReportSection:
    """A section within a report."""
    title: str
    content: Any
    order: int = 0
    subsections: List['ReportSection'] = field(default_factory=list)


class PopulationHealthReporter:
    """
    Generates population health reports and insights.
    
    This is the presentation layer for population health data,
    transforming raw metrics into actionable reports.
    """
    
    def __init__(self):
        """Initialize reporter."""
        self.report_templates = {
            ReportFormat.SUMMARY: self._generate_summary_report,
            ReportFormat.DETAILED: self._generate_detailed_report,
            ReportFormat.EXECUTIVE: self._generate_executive_report,
        }
    
    async def generate_report(
        self,
        summary: Any,  # PopulationHealthSummary
        format: str = "summary"
    ) -> Dict[str, Any]:
        """
        Generate a report from population health summary.
        
        Args:
            summary: PopulationHealthSummary object
            format: Report format (summary, detailed, executive)
        
        Returns:
            Report as dictionary
        """
        try:
            report_format = ReportFormat(format)
        except ValueError:
            report_format = ReportFormat.SUMMARY
        
        generator = self.report_templates.get(
            report_format,
            self._generate_summary_report
        )
        
        report = await generator(summary)
        
        logger.info(
            f"Generated {format} report for population {summary.population_name}"
        )
        
        return report
    
    async def _generate_summary_report(self, summary: Any) -> Dict[str, Any]:
        """Generate summary report for dashboards."""
        return {
            "report_type": "summary",
            "generated_at": datetime.now().isoformat(),
            "population": {
                "id": summary.population_id,
                "name": summary.population_name,
                "size": summary.total_patients
            },
            "key_metrics": {
                "overall_quality_score": summary.overall_quality_score,
                "total_care_gaps": summary.total_care_gaps,
                "critical_gaps": summary.critical_gaps,
                "gaps_per_patient": round(
                    summary.total_care_gaps / max(1, summary.total_patients), 2
                )
            },
            "risk_distribution": summary.risk_distribution,
            "top_measures": self._get_top_measures(summary.quality_measures),
            "trends": {
                "improving": summary.improvement_areas,
                "declining": summary.concern_areas
            }
        }
    
    async def _generate_detailed_report(self, summary: Any) -> Dict[str, Any]:
        """Generate detailed report for quality team."""
        base = await self._generate_summary_report(summary)
        
        # Add detailed quality measures
        base["quality_measures"] = [
            {
                "measure_id": m.measure_id,
                "measure_name": m.measure_name,
                "rate": m.rate,
                "rate_display": f"{m.rate * 100:.1f}%",
                "numerator": m.numerator,
                "denominator": m.denominator,
                "benchmark": m.benchmark,
                "percentile": m.percentile,
                "stars": m.stars_rating,
                "trend": m.trend,
                "gap_count": m.gap_count,
                "status": self._get_measure_status(m)
            }
            for m in summary.quality_measures
        ]
        
        # Add gap details
        base["gaps_by_measure"] = [
            {
                "measure_id": mid,
                "count": count,
                "percentage": round(count / max(1, summary.total_care_gaps) * 100, 1)
            }
            for mid, count in sorted(
                summary.gaps_by_measure.items(),
                key=lambda x: x[1],
                reverse=True
            )
        ]
        
        # Add actionable recommendations
        base["recommendations"] = self._generate_recommendations(summary)
        
        base["report_type"] = "detailed"
        
        return base
    
    async def _generate_executive_report(self, summary: Any) -> Dict[str, Any]:
        """Generate executive report for leadership."""
        return {
            "report_type": "executive",
            "generated_at": datetime.now().isoformat(),
            "title": f"Population Health Executive Summary: {summary.population_name}",
            "period": summary.trend_period or "Current",
            
            "executive_summary": {
                "population_size": summary.total_patients,
                "quality_score": summary.overall_quality_score,
                "quality_rating": self._get_quality_rating(summary.overall_quality_score),
                "care_gaps": summary.total_care_gaps,
                "high_risk_patients": summary.risk_distribution.get("high", 0) + 
                                     summary.risk_distribution.get("critical", 0),
                "high_risk_percentage": round(
                    (summary.risk_distribution.get("high", 0) + 
                     summary.risk_distribution.get("critical", 0)) / 
                    max(1, summary.total_patients) * 100, 1
                )
            },
            
            "key_highlights": self._generate_highlights(summary),
            
            "priority_actions": self._generate_priority_actions(summary),
            
            "financial_impact": self._estimate_financial_impact(summary),
            
            "benchmarking": {
                "measures_above_benchmark": len([
                    m for m in summary.quality_measures 
                    if m.rate >= m.benchmark
                ]),
                "measures_below_benchmark": len([
                    m for m in summary.quality_measures 
                    if m.rate < m.benchmark
                ]),
                "total_measures": len(summary.quality_measures)
            }
        }
    
    def _get_top_measures(
        self,
        measures: List[Any],
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top performing measures."""
        sorted_measures = sorted(
            measures,
            key=lambda m: m.rate,
            reverse=True
        )
        
        return [
            {
                "measure_id": m.measure_id,
                "measure_name": m.measure_name,
                "rate": f"{m.rate * 100:.1f}%",
                "stars": m.stars_rating
            }
            for m in sorted_measures[:top_n]
        ]
    
    def _get_measure_status(self, measure: Any) -> str:
        """Get status indicator for a measure."""
        if measure.percentile >= 75:
            return "excellent"
        elif measure.percentile >= 50:
            return "good"
        elif measure.percentile >= 25:
            return "needs_improvement"
        else:
            return "critical"
    
    def _get_quality_rating(self, score: float) -> str:
        """Get quality rating label."""
        if score >= 85:
            return "Excellent"
        elif score >= 75:
            return "Good"
        elif score >= 60:
            return "Average"
        elif score >= 45:
            return "Below Average"
        else:
            return "Needs Improvement"
    
    def _generate_recommendations(self, summary: Any) -> List[Dict[str, str]]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Recommend based on concern areas
        for area in summary.concern_areas[:3]:
            recommendations.append({
                "priority": "high",
                "area": area,
                "action": f"Focus improvement efforts on {area} - trend is declining",
                "impact": "Quality score improvement"
            })
        
        # Recommend based on high-risk patients
        high_risk_count = (
            summary.risk_distribution.get("high", 0) +
            summary.risk_distribution.get("critical", 0)
        )
        if high_risk_count > summary.total_patients * 0.15:
            recommendations.append({
                "priority": "high",
                "area": "Risk Management",
                "action": "Expand care management program for high-risk patients",
                "impact": "Reduce hospitalizations and costs"
            })
        
        # Recommend based on care gaps
        if summary.critical_gaps > 0:
            recommendations.append({
                "priority": "urgent",
                "area": "Care Gaps",
                "action": f"Address {summary.critical_gaps} critical care gaps immediately",
                "impact": "Patient safety and quality scores"
            })
        
        return recommendations
    
    def _generate_highlights(self, summary: Any) -> List[str]:
        """Generate key highlights for executive summary."""
        highlights = []
        
        # Quality score highlight
        rating = self._get_quality_rating(summary.overall_quality_score)
        highlights.append(
            f"Overall quality score is {summary.overall_quality_score}% ({rating})"
        )
        
        # Risk distribution highlight
        low_moderate = (
            summary.risk_distribution.get("low", 0) +
            summary.risk_distribution.get("moderate", 0)
        )
        if summary.total_patients > 0:
            low_moderate_pct = low_moderate / summary.total_patients * 100
            highlights.append(
                f"{low_moderate_pct:.0f}% of patients are low or moderate risk"
            )
        
        # Improvement areas
        if summary.improvement_areas:
            highlights.append(
                f"Improving: {', '.join(summary.improvement_areas[:3])}"
            )
        
        # Concern areas
        if summary.concern_areas:
            highlights.append(
                f"Attention needed: {', '.join(summary.concern_areas[:2])}"
            )
        
        return highlights
    
    def _generate_priority_actions(self, summary: Any) -> List[Dict[str, str]]:
        """Generate priority action items."""
        actions = []
        
        # Critical gaps
        if summary.critical_gaps > 0:
            actions.append({
                "action": f"Close {summary.critical_gaps} critical care gaps",
                "owner": "Care Management",
                "timeline": "Immediate",
                "impact": "High"
            })
        
        # Declining measures
        for area in summary.concern_areas[:2]:
            actions.append({
                "action": f"Develop improvement plan for {area}",
                "owner": "Quality Team",
                "timeline": "30 days",
                "impact": "Medium"
            })
        
        # High-risk patients
        high_risk = (
            summary.risk_distribution.get("high", 0) +
            summary.risk_distribution.get("critical", 0)
        )
        if high_risk > 0:
            actions.append({
                "action": f"Review {high_risk} high/critical risk patients",
                "owner": "Care Coordinators",
                "timeline": "Weekly",
                "impact": "High"
            })
        
        return actions
    
    def _estimate_financial_impact(self, summary: Any) -> Dict[str, Any]:
        """Estimate financial impact of quality performance."""
        # Simplified financial model
        # In production, this would use actual payer contract terms
        
        # Assume $50 per gap closure (preventive care revenue)
        gap_closure_revenue = summary.total_care_gaps * 50
        
        # Assume quality bonus of $20 PMPM for 4+ stars
        stars_measures = [m for m in summary.quality_measures if m.stars_rating >= 4]
        potential_bonus = len(stars_measures) * 20 * summary.total_patients
        
        # Assume readmission penalty of $15,000 per readmission
        # High-risk patients have ~20% readmission rate, managed have ~12%
        high_risk = (
            summary.risk_distribution.get("high", 0) +
            summary.risk_distribution.get("critical", 0)
        )
        potential_avoided_readmissions = high_risk * 0.08  # 8% reduction
        readmission_savings = potential_avoided_readmissions * 15000
        
        return {
            "gap_closure_opportunity": f"${gap_closure_revenue:,.0f}",
            "quality_bonus_potential": f"${potential_bonus:,.0f}",
            "readmission_savings_potential": f"${readmission_savings:,.0f}",
            "total_opportunity": f"${gap_closure_revenue + potential_bonus + readmission_savings:,.0f}",
            "note": "Estimates based on industry averages. Actual impact depends on payer contracts."
        }
    
    async def generate_provider_scorecard(
        self,
        provider_id: str,
        provider_name: str,
        measures: List[Any],
        panel_size: int,
        comparison_data: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Generate provider-level scorecard.
        
        Args:
            provider_id: Provider identifier
            provider_name: Provider name
            measures: List of quality measure results for this provider
            panel_size: Number of patients on provider's panel
            comparison_data: Optional comparison to peers/benchmark
        
        Returns:
            Provider scorecard as dictionary
        """
        # Calculate provider composite score
        total_weight = 0.0
        weighted_sum = 0.0
        
        for m in measures:
            weight = 1.0  # Simplified
            total_weight += weight
            weighted_sum += m.rate * weight * 100
        
        composite_score = round(weighted_sum / max(1, total_weight), 1)
        
        # Identify opportunities
        opportunities = [
            {
                "measure": m.measure_name,
                "current_rate": f"{m.rate * 100:.1f}%",
                "gap_count": m.gap_count,
                "potential_improvement": f"{(m.benchmark - m.rate) * 100:.1f}%"
            }
            for m in measures
            if m.rate < m.benchmark
        ]
        
        return {
            "provider_id": provider_id,
            "provider_name": provider_name,
            "panel_size": panel_size,
            "generated_at": datetime.now().isoformat(),
            "composite_score": composite_score,
            "rating": self._get_quality_rating(composite_score),
            "measures": [
                {
                    "measure_id": m.measure_id,
                    "measure_name": m.measure_name,
                    "rate": f"{m.rate * 100:.1f}%",
                    "benchmark": f"{m.benchmark * 100:.1f}%",
                    "vs_benchmark": "above" if m.rate >= m.benchmark else "below",
                    "gap_count": m.gap_count
                }
                for m in measures
            ],
            "improvement_opportunities": opportunities[:5],
            "comparison": comparison_data or {}
        }
