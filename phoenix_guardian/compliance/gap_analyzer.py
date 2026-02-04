"""
Gap Analyzer for SOC 2.

Identifies missing evidence before audit:
- TSC criteria without evidence
- Time periods without coverage
- Evidence type gaps
- Remediation recommendations

CRITICAL: Run gap analysis before audit to identify missing evidence.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
import logging

from phoenix_guardian.compliance.evidence_types import (
    Evidence,
    EvidenceType,
    TSCCriterion,
)

logger = logging.getLogger(__name__)


class GapSeverity(Enum):
    """Severity of evidence gaps."""
    CRITICAL = "critical"  # Will fail audit
    HIGH = "high"          # Likely auditor finding
    MEDIUM = "medium"      # May be questioned
    LOW = "low"            # Nice to have


class GapType(Enum):
    """Types of evidence gaps."""
    MISSING_TSC = "missing_tsc"
    TEMPORAL_GAP = "temporal_gap"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    MISSING_EVIDENCE_TYPE = "missing_evidence_type"
    STALE_EVIDENCE = "stale_evidence"


@dataclass
class EvidenceGap:
    """A gap in evidence coverage."""
    gap_id: str
    gap_type: GapType
    severity: GapSeverity
    tsc_criterion: Optional[TSCCriterion]
    description: str
    remediation: str
    evidence_required: Optional[str] = None
    deadline: Optional[str] = None


@dataclass
class GapAnalysisResult:
    """Result of gap analysis."""
    analysis_id: str
    analyzed_at: str
    audit_period_start: str
    audit_period_end: str
    
    # Gaps found
    gaps: List[EvidenceGap] = field(default_factory=list)
    
    # Statistics
    total_evidence: int = 0
    tsc_coverage: Dict[str, bool] = field(default_factory=dict)
    
    @property
    def critical_gaps(self) -> int:
        return sum(1 for g in self.gaps if g.severity == GapSeverity.CRITICAL)
    
    @property
    def high_gaps(self) -> int:
        return sum(1 for g in self.gaps if g.severity == GapSeverity.HIGH)
    
    @property
    def is_audit_ready(self) -> bool:
        """Check if ready for audit (no critical gaps)."""
        return self.critical_gaps == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "analysis_id": self.analysis_id,
            "analyzed_at": self.analyzed_at,
            "audit_period": {
                "start": self.audit_period_start,
                "end": self.audit_period_end,
            },
            "is_audit_ready": self.is_audit_ready,
            "gap_summary": {
                "total": len(self.gaps),
                "critical": self.critical_gaps,
                "high": self.high_gaps,
                "medium": sum(1 for g in self.gaps if g.severity == GapSeverity.MEDIUM),
                "low": sum(1 for g in self.gaps if g.severity == GapSeverity.LOW),
            },
            "tsc_coverage": self.tsc_coverage,
            "gaps": [
                {
                    "gap_id": g.gap_id,
                    "gap_type": g.gap_type.value,
                    "severity": g.severity.value,
                    "tsc_criterion": g.tsc_criterion.value if g.tsc_criterion else None,
                    "description": g.description,
                    "remediation": g.remediation,
                    "evidence_required": g.evidence_required,
                    "deadline": g.deadline,
                }
                for g in self.gaps
            ],
        }


class GapAnalyzer:
    """
    Analyzes evidence for gaps before SOC 2 audit.
    
    Identifies:
    - Missing TSC coverage
    - Temporal gaps in evidence
    - Insufficient evidence volume
    - Stale evidence that needs refresh
    """
    
    # Minimum evidence required per TSC
    MIN_EVIDENCE_PER_TSC = {
        TSCCriterion.CC3_RISK_ASSESSMENT: 5,
        TSCCriterion.CC4_MONITORING: 10,
        TSCCriterion.CC6_LOGICAL_ACCESS: 20,
        TSCCriterion.CC7_SYSTEM_OPERATIONS: 15,
        TSCCriterion.CC8_CHANGE_MANAGEMENT: 10,
    }
    
    # Required evidence types per TSC
    REQUIRED_EVIDENCE_TYPES: Dict[TSCCriterion, Set[EvidenceType]] = {
        TSCCriterion.CC3_RISK_ASSESSMENT: {
            EvidenceType.VULNERABILITY_SCAN,
            EvidenceType.PENETRATION_TEST,
        },
        TSCCriterion.CC4_MONITORING: {
            EvidenceType.PERFORMANCE_METRIC,
            EvidenceType.SYSTEM_AVAILABILITY,
        },
        TSCCriterion.CC6_LOGICAL_ACCESS: {
            EvidenceType.AUTHENTICATION_EVENT,
            EvidenceType.AUTHORIZATION_CHECK,
        },
        TSCCriterion.CC7_SYSTEM_OPERATIONS: {
            EvidenceType.INCIDENT_REPORT,
            EvidenceType.BACKUP_VERIFICATION,
        },
        TSCCriterion.CC8_CHANGE_MANAGEMENT: {
            EvidenceType.DEPLOYMENT_RECORD,
            EvidenceType.CHANGE_APPROVAL,
            EvidenceType.CODE_REVIEW,
        },
    }
    
    # Maximum gap allowed in continuous evidence (days)
    MAX_TEMPORAL_GAP_DAYS = 7
    
    def __init__(self):
        self.analysis_history: List[GapAnalysisResult] = []
    
    def analyze(
        self,
        evidence_items: List[Evidence],
        audit_period_start: str,
        audit_period_end: str
    ) -> GapAnalysisResult:
        """
        Analyze evidence for gaps.
        
        Args:
            evidence_items: Evidence to analyze
            audit_period_start: Start of audit period
            audit_period_end: End of audit period
        
        Returns:
            GapAnalysisResult with all gaps found
        """
        analysis_id = f"gap_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        gaps: List[EvidenceGap] = []
        gap_counter = 0
        
        logger.info(f"Starting gap analysis: {analysis_id}")
        
        # Analyze TSC coverage
        tsc_gaps, tsc_coverage = self._analyze_tsc_coverage(evidence_items)
        for gap in tsc_gaps:
            gap_counter += 1
            gap.gap_id = f"GAP-{gap_counter:04d}"
        gaps.extend(tsc_gaps)
        
        # Analyze evidence types
        type_gaps = self._analyze_evidence_types(evidence_items)
        for gap in type_gaps:
            gap_counter += 1
            gap.gap_id = f"GAP-{gap_counter:04d}"
        gaps.extend(type_gaps)
        
        # Analyze temporal coverage
        temporal_gaps = self._analyze_temporal_coverage(
            evidence_items, audit_period_start, audit_period_end
        )
        for gap in temporal_gaps:
            gap_counter += 1
            gap.gap_id = f"GAP-{gap_counter:04d}"
        gaps.extend(temporal_gaps)
        
        # Analyze evidence volume
        volume_gaps = self._analyze_evidence_volume(evidence_items)
        for gap in volume_gaps:
            gap_counter += 1
            gap.gap_id = f"GAP-{gap_counter:04d}"
        gaps.extend(volume_gaps)
        
        # Analyze evidence freshness
        freshness_gaps = self._analyze_freshness(evidence_items)
        for gap in freshness_gaps:
            gap_counter += 1
            gap.gap_id = f"GAP-{gap_counter:04d}"
        gaps.extend(freshness_gaps)
        
        result = GapAnalysisResult(
            analysis_id=analysis_id,
            analyzed_at=datetime.now().isoformat(),
            audit_period_start=audit_period_start,
            audit_period_end=audit_period_end,
            gaps=gaps,
            total_evidence=len(evidence_items),
            tsc_coverage=tsc_coverage,
        )
        
        self.analysis_history.append(result)
        
        logger.info(
            f"Gap analysis complete: {len(gaps)} gaps found "
            f"({result.critical_gaps} critical, {result.high_gaps} high)"
        )
        
        return result
    
    def _analyze_tsc_coverage(
        self,
        evidence_items: List[Evidence]
    ) -> tuple[List[EvidenceGap], Dict[str, bool]]:
        """Check which TSC criteria have evidence."""
        gaps: List[EvidenceGap] = []
        coverage: Dict[str, bool] = {}
        
        # Count evidence per TSC
        tsc_counts: Dict[TSCCriterion, int] = {tsc: 0 for tsc in TSCCriterion}
        for evidence in evidence_items:
            for tsc in evidence.tsc_criteria:
                tsc_counts[tsc] = tsc_counts.get(tsc, 0) + 1
        
        # Check each automatable TSC
        for tsc in TSCCriterion:
            if not tsc.is_automatable:
                coverage[tsc.value] = True  # Manual, not our concern
                continue
            
            count = tsc_counts.get(tsc, 0)
            coverage[tsc.value] = count > 0
            
            if count == 0:
                gaps.append(EvidenceGap(
                    gap_id="",  # Will be assigned later
                    gap_type=GapType.MISSING_TSC,
                    severity=GapSeverity.CRITICAL,
                    tsc_criterion=tsc,
                    description=f"No evidence for {tsc.value}: {tsc.description}",
                    remediation=f"Collect evidence demonstrating {tsc.description} controls",
                    evidence_required=", ".join(
                        et.value for et in self.REQUIRED_EVIDENCE_TYPES.get(tsc, [])
                    ),
                ))
        
        return gaps, coverage
    
    def _analyze_evidence_types(
        self,
        evidence_items: List[Evidence]
    ) -> List[EvidenceGap]:
        """Check for missing evidence types per TSC."""
        gaps: List[EvidenceGap] = []
        
        # Get evidence types present per TSC
        tsc_types: Dict[TSCCriterion, Set[EvidenceType]] = {
            tsc: set() for tsc in TSCCriterion
        }
        for evidence in evidence_items:
            for tsc in evidence.tsc_criteria:
                tsc_types[tsc].add(evidence.evidence_type)
        
        # Check required types
        for tsc, required_types in self.REQUIRED_EVIDENCE_TYPES.items():
            present_types = tsc_types.get(tsc, set())
            missing_types = required_types - present_types
            
            for missing_type in missing_types:
                gaps.append(EvidenceGap(
                    gap_id="",
                    gap_type=GapType.MISSING_EVIDENCE_TYPE,
                    severity=GapSeverity.HIGH,
                    tsc_criterion=tsc,
                    description=f"Missing {missing_type.value} evidence for {tsc.value}",
                    remediation=f"Collect {missing_type.value} evidence",
                    evidence_required=missing_type.value,
                ))
        
        return gaps
    
    def _analyze_temporal_coverage(
        self,
        evidence_items: List[Evidence],
        audit_start: str,
        audit_end: str
    ) -> List[EvidenceGap]:
        """Check for gaps in temporal coverage."""
        gaps: List[EvidenceGap] = []
        
        audit_start_dt = datetime.fromisoformat(audit_start)
        audit_end_dt = datetime.fromisoformat(audit_end)
        
        # Get all evidence timestamps
        timestamps: List[datetime] = []
        for evidence in evidence_items:
            try:
                dt = datetime.fromisoformat(evidence.event_timestamp)
                timestamps.append(dt)
            except (ValueError, TypeError):
                pass
        
        if not timestamps:
            gaps.append(EvidenceGap(
                gap_id="",
                gap_type=GapType.TEMPORAL_GAP,
                severity=GapSeverity.CRITICAL,
                tsc_criterion=None,
                description="No evidence with valid timestamps found",
                remediation="Ensure all evidence has valid event_timestamp",
            ))
            return gaps
        
        timestamps.sort()
        
        # Check coverage at start of audit period
        earliest = min(timestamps)
        if earliest > audit_start_dt + timedelta(days=self.MAX_TEMPORAL_GAP_DAYS):
            gaps.append(EvidenceGap(
                gap_id="",
                gap_type=GapType.TEMPORAL_GAP,
                severity=GapSeverity.HIGH,
                tsc_criterion=None,
                description=f"Evidence gap at start of audit period ({(earliest - audit_start_dt).days} days)",
                remediation="Collect evidence from start of audit period",
            ))
        
        # Check coverage at end of audit period
        latest = max(timestamps)
        if latest < audit_end_dt - timedelta(days=self.MAX_TEMPORAL_GAP_DAYS):
            gaps.append(EvidenceGap(
                gap_id="",
                gap_type=GapType.TEMPORAL_GAP,
                severity=GapSeverity.HIGH,
                tsc_criterion=None,
                description=f"Evidence gap at end of audit period ({(audit_end_dt - latest).days} days)",
                remediation="Collect evidence through end of audit period",
            ))
        
        return gaps
    
    def _analyze_evidence_volume(
        self,
        evidence_items: List[Evidence]
    ) -> List[EvidenceGap]:
        """Check evidence volume per TSC."""
        gaps: List[EvidenceGap] = []
        
        # Count per TSC
        tsc_counts: Dict[TSCCriterion, int] = {}
        for evidence in evidence_items:
            for tsc in evidence.tsc_criteria:
                tsc_counts[tsc] = tsc_counts.get(tsc, 0) + 1
        
        # Check minimums
        for tsc, minimum in self.MIN_EVIDENCE_PER_TSC.items():
            count = tsc_counts.get(tsc, 0)
            if 0 < count < minimum:
                gaps.append(EvidenceGap(
                    gap_id="",
                    gap_type=GapType.INSUFFICIENT_EVIDENCE,
                    severity=GapSeverity.MEDIUM,
                    tsc_criterion=tsc,
                    description=f"Only {count} evidence items for {tsc.value} (minimum: {minimum})",
                    remediation=f"Collect at least {minimum - count} more evidence items",
                ))
        
        return gaps
    
    def _analyze_freshness(
        self,
        evidence_items: List[Evidence]
    ) -> List[EvidenceGap]:
        """Check for stale evidence."""
        gaps: List[EvidenceGap] = []
        now = datetime.now()
        stale_threshold = 90  # days
        
        stale_count = 0
        for evidence in evidence_items:
            try:
                collected = datetime.fromisoformat(evidence.collected_at)
                age = (now - collected).days
                if age > stale_threshold:
                    stale_count += 1
            except (ValueError, TypeError):
                pass
        
        if stale_count > len(evidence_items) * 0.3:  # More than 30% stale
            gaps.append(EvidenceGap(
                gap_id="",
                gap_type=GapType.STALE_EVIDENCE,
                severity=GapSeverity.MEDIUM,
                tsc_criterion=None,
                description=f"{stale_count} evidence items are older than {stale_threshold} days",
                remediation="Run fresh evidence collection",
            ))
        
        return gaps
    
    def generate_remediation_plan(
        self,
        result: GapAnalysisResult
    ) -> Dict[str, Any]:
        """Generate a remediation plan for identified gaps."""
        plan = {
            "analysis_id": result.analysis_id,
            "generated_at": datetime.now().isoformat(),
            "is_audit_ready": result.is_audit_ready,
            "priority_actions": [],
            "detailed_actions": [],
        }
        
        # Sort gaps by severity
        sorted_gaps = sorted(
            result.gaps,
            key=lambda g: ["critical", "high", "medium", "low"].index(g.severity.value)
        )
        
        for gap in sorted_gaps:
            action = {
                "gap_id": gap.gap_id,
                "priority": gap.severity.value,
                "tsc": gap.tsc_criterion.value if gap.tsc_criterion else "N/A",
                "issue": gap.description,
                "action": gap.remediation,
                "evidence_needed": gap.evidence_required,
                "deadline": gap.deadline or self._calculate_deadline(gap.severity),
            }
            
            if gap.severity in [GapSeverity.CRITICAL, GapSeverity.HIGH]:
                plan["priority_actions"].append(action)
            
            plan["detailed_actions"].append(action)
        
        return plan
    
    def _calculate_deadline(self, severity: GapSeverity) -> str:
        """Calculate remediation deadline based on severity."""
        days = {
            GapSeverity.CRITICAL: 7,
            GapSeverity.HIGH: 14,
            GapSeverity.MEDIUM: 30,
            GapSeverity.LOW: 60,
        }
        deadline = datetime.now() + timedelta(days=days.get(severity, 30))
        return deadline.isoformat()
