"""
Population Health Agent.

STRATEGIC IMPORTANCE:
Value-based care is the future of hospital revenue. Instead of fee-for-service
(more procedures = more revenue), value-based care rewards OUTCOMES:
- Keeping patients healthy (preventive care)
- Avoiding unnecessary hospitalizations
- Managing chronic diseases effectively

This agent transforms Phoenix Guardian from "documentation tool" to 
"care improvement platform" by:
1. Identifying care gaps (missed screenings, overdue preventive care)
2. Stratifying patient risk (who needs extra attention)
3. Tracking quality metrics (HEDIS, MIPS)
4. Generating population-level insights (trends, interventions)

BUSINESS JUSTIFICATION:
- Hospitals lose millions in quality-based payment adjustments
- Medicare Advantage plans pay bonuses for Stars ratings
- Commercial payers increasingly use quality-tied contracts
- CMS penalties for poor outcomes can reach 9% of reimbursement

ARCHITECTURE:
    PopulationHealthAgent
    ├── CareGapAnalyzer       - Identifies missed/overdue care
    ├── RiskStratifier        - Stratifies patients by risk level
    ├── QualityMetricsEngine  - Tracks HEDIS/MIPS/Stars measures
    └── PopulationHealthReporter - Generates reports and insights
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from enum import Enum
from datetime import datetime, date, timedelta
import logging
import uuid

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Patient risk stratification levels."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class CareGapPriority(Enum):
    """Priority levels for care gaps."""
    ROUTINE = "routine"      # Due within 30 days
    OVERDUE = "overdue"      # Overdue but not urgent
    URGENT = "urgent"        # Significantly overdue or high-risk
    CRITICAL = "critical"    # Immediate intervention needed


class QualityProgram(Enum):
    """Quality measurement programs."""
    HEDIS = "hedis"
    MIPS = "mips"
    STARS = "medicare_stars"
    COMMERCIAL = "commercial_quality"


@dataclass
class CareGap:
    """
    Represents a gap in patient care.
    
    Examples:
    - Colonoscopy overdue (45-75 y/o, >10 years since last)
    - Mammogram overdue (50-74 y/o female, >2 years)
    - A1c not checked in 6 months (diabetic patient)
    - Blood pressure not checked in 12 months (hypertensive)
    """
    gap_id: str
    patient_id: str
    measure_id: str              # e.g., "BCS" (Breast Cancer Screening)
    measure_name: str
    gap_type: str                # e.g., "screening", "lab", "visit"
    priority: CareGapPriority
    
    due_date: Optional[date] = None
    last_completed: Optional[date] = None
    days_overdue: int = 0
    
    recommendation: str = ""
    evidence_grade: str = ""      # e.g., "A", "B", "C" (USPSTF)
    
    quality_program: Optional[QualityProgram] = None
    affects_stars_rating: bool = False
    
    patient_outreach_attempts: int = 0
    patient_declined: bool = False


@dataclass
class PatientRiskProfile:
    """
    Risk profile for a patient.
    
    Used for prioritizing care management and resource allocation.
    """
    patient_id: str
    risk_level: RiskLevel
    risk_score: float            # 0.0 - 1.0
    
    # Contributing factors
    chronic_conditions: List[str] = field(default_factory=list)
    social_determinants: List[str] = field(default_factory=list)
    recent_utilization: Dict[str, int] = field(default_factory=dict)
    
    # Predictions
    readmission_risk_30day: float = 0.0
    hospitalization_risk_90day: float = 0.0
    mortality_risk_12month: float = 0.0
    
    # Care management recommendations
    care_management_level: str = ""
    recommended_interventions: List[str] = field(default_factory=list)
    
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class QualityMeasureResult:
    """
    Result for a specific quality measure.
    """
    measure_id: str
    measure_name: str
    program: QualityProgram
    
    numerator: int = 0           # Patients meeting measure
    denominator: int = 0         # Patients eligible for measure
    rate: float = 0.0            # numerator / denominator
    
    benchmark: float = 0.0       # Target rate
    percentile: int = 0          # Performance percentile
    stars_rating: int = 0        # 1-5 stars if applicable
    
    trend: str = ""              # "improving", "declining", "stable"
    gap_count: int = 0           # Patients with open gaps


@dataclass
class PopulationHealthSummary:
    """
    Summary of population health metrics for a patient population.
    """
    population_id: str
    population_name: str
    total_patients: int
    
    # Risk distribution
    risk_distribution: Dict[str, int] = field(default_factory=dict)
    
    # Care gaps
    total_care_gaps: int = 0
    critical_gaps: int = 0
    gaps_by_measure: Dict[str, int] = field(default_factory=dict)
    
    # Quality metrics
    quality_measures: List[QualityMeasureResult] = field(default_factory=list)
    overall_quality_score: float = 0.0
    
    # Trends
    trend_period: str = ""       # e.g., "Q4 2024"
    improvement_areas: List[str] = field(default_factory=list)
    concern_areas: List[str] = field(default_factory=list)
    
    generated_at: datetime = field(default_factory=datetime.now)


class PopulationHealthAgent:
    """
    Agent for population health management and quality improvement.
    
    This agent works at the population level (not individual encounters)
    to identify care gaps, stratify risk, and track quality metrics.
    
    Usage:
        agent = PopulationHealthAgent()
        
        # Analyze a patient's care gaps
        gaps = await agent.analyze_patient_care_gaps(patient_id)
        
        # Stratify patient risk
        risk_profile = await agent.stratify_patient_risk(patient_id)
        
        # Generate population summary
        summary = await agent.generate_population_summary(population_id)
    """
    
    def __init__(
        self,
        organization_id: Optional[str] = None,
        quality_programs: Optional[List[QualityProgram]] = None
    ):
        """
        Initialize PopulationHealthAgent.
        
        Args:
            organization_id: Healthcare organization ID
            quality_programs: Quality programs to track (HEDIS, MIPS, etc.)
        """
        self.organization_id = organization_id or "default"
        self.quality_programs = quality_programs or [
            QualityProgram.HEDIS,
            QualityProgram.MIPS
        ]
        
        # Component initialization (lazy loading)
        self._care_gap_analyzer = None
        self._risk_stratifier = None
        self._quality_engine = None
        self._reporter = None
        
        # Cache
        self._patient_cache: Dict[str, PatientRiskProfile] = {}
        
        logger.info(
            f"PopulationHealthAgent initialized for org={organization_id}"
        )
    
    @property
    def care_gap_analyzer(self):
        """Lazy load CareGapAnalyzer."""
        if self._care_gap_analyzer is None:
            from phoenix_guardian.agents.care_gap_analyzer import CareGapAnalyzer
            self._care_gap_analyzer = CareGapAnalyzer()
        return self._care_gap_analyzer
    
    @property
    def risk_stratifier(self):
        """Lazy load RiskStratifier."""
        if self._risk_stratifier is None:
            from phoenix_guardian.agents.risk_stratifier import RiskStratifier
            self._risk_stratifier = RiskStratifier()
        return self._risk_stratifier
    
    @property
    def quality_engine(self):
        """Lazy load QualityMetricsEngine."""
        if self._quality_engine is None:
            from phoenix_guardian.agents.quality_metrics_engine import QualityMetricsEngine
            self._quality_engine = QualityMetricsEngine(self.quality_programs)
        return self._quality_engine
    
    @property
    def reporter(self):
        """Lazy load PopulationHealthReporter."""
        if self._reporter is None:
            from phoenix_guardian.agents.population_health_reporter import PopulationHealthReporter
            self._reporter = PopulationHealthReporter()
        return self._reporter
    
    async def analyze_patient_care_gaps(
        self,
        patient_id: str,
        patient_data: Optional[Dict[str, Any]] = None,
        include_completed: bool = False
    ) -> List[CareGap]:
        """
        Analyze care gaps for a specific patient.
        
        Args:
            patient_id: Patient identifier
            patient_data: Optional patient data (age, conditions, history)
            include_completed: Include recently completed measures
        
        Returns:
            List of CareGap objects
        """
        logger.info(f"Analyzing care gaps for patient {patient_id}")
        
        gaps = await self.care_gap_analyzer.analyze_patient(
            patient_id=patient_id,
            patient_data=patient_data,
            programs=self.quality_programs
        )
        
        if not include_completed:
            gaps = [g for g in gaps if g.days_overdue > 0 or g.due_date]
        
        # Sort by priority
        priority_order = {
            CareGapPriority.CRITICAL: 0,
            CareGapPriority.URGENT: 1,
            CareGapPriority.OVERDUE: 2,
            CareGapPriority.ROUTINE: 3
        }
        gaps.sort(key=lambda g: priority_order.get(g.priority, 99))
        
        logger.info(f"Found {len(gaps)} care gaps for patient {patient_id}")
        return gaps
    
    async def stratify_patient_risk(
        self,
        patient_id: str,
        patient_data: Optional[Dict[str, Any]] = None,
        refresh: bool = False
    ) -> PatientRiskProfile:
        """
        Stratify risk for a specific patient.
        
        Uses multiple risk models to create a comprehensive risk profile.
        
        Args:
            patient_id: Patient identifier
            patient_data: Optional patient data
            refresh: Force refresh even if cached
        
        Returns:
            PatientRiskProfile with risk scores and recommendations
        """
        # Check cache
        if not refresh and patient_id in self._patient_cache:
            cached = self._patient_cache[patient_id]
            if (datetime.now() - cached.last_updated).days < 1:
                return cached
        
        logger.info(f"Stratifying risk for patient {patient_id}")
        
        profile = await self.risk_stratifier.stratify(
            patient_id=patient_id,
            patient_data=patient_data
        )
        
        # Cache result
        self._patient_cache[patient_id] = profile
        
        return profile
    
    async def calculate_quality_metrics(
        self,
        population_ids: Optional[List[str]] = None,
        program: Optional[QualityProgram] = None,
        measure_ids: Optional[List[str]] = None
    ) -> List[QualityMeasureResult]:
        """
        Calculate quality metrics for a population.
        
        Args:
            population_ids: Optional list of patient IDs (None = all)
            program: Specific quality program or None for all
            measure_ids: Specific measures or None for all
        
        Returns:
            List of QualityMeasureResult objects
        """
        programs = [program] if program else self.quality_programs
        
        results = await self.quality_engine.calculate_metrics(
            population_ids=population_ids,
            programs=programs,
            measure_ids=measure_ids
        )
        
        return results
    
    async def generate_population_summary(
        self,
        population_id: str,
        population_name: str,
        patient_ids: List[str]
    ) -> PopulationHealthSummary:
        """
        Generate comprehensive population health summary.
        
        This is the main output for population health dashboards.
        
        Args:
            population_id: Identifier for this population
            population_name: Human-readable name
            patient_ids: List of patient IDs in population
        
        Returns:
            PopulationHealthSummary with all metrics
        """
        logger.info(
            f"Generating population summary for {population_name} "
            f"({len(patient_ids)} patients)"
        )
        
        # Get risk distribution
        risk_distribution = {"low": 0, "moderate": 0, "high": 0, "critical": 0}
        for patient_id in patient_ids:
            profile = await self.stratify_patient_risk(patient_id)
            risk_distribution[profile.risk_level.value] += 1
        
        # Get care gaps
        all_gaps = []
        for patient_id in patient_ids:
            gaps = await self.analyze_patient_care_gaps(patient_id)
            all_gaps.extend(gaps)
        
        gaps_by_measure = {}
        critical_gaps = 0
        for gap in all_gaps:
            gaps_by_measure[gap.measure_id] = gaps_by_measure.get(gap.measure_id, 0) + 1
            if gap.priority == CareGapPriority.CRITICAL:
                critical_gaps += 1
        
        # Get quality metrics
        quality_measures = await self.calculate_quality_metrics(
            population_ids=patient_ids
        )
        
        # Calculate overall quality score (weighted average)
        if quality_measures:
            total_weight = sum(m.denominator for m in quality_measures)
            if total_weight > 0:
                overall_score = sum(
                    m.rate * m.denominator for m in quality_measures
                ) / total_weight
            else:
                overall_score = 0.0
        else:
            overall_score = 0.0
        
        # Identify trends
        improvement_areas = [
            m.measure_name for m in quality_measures 
            if m.trend == "improving"
        ]
        concern_areas = [
            m.measure_name for m in quality_measures 
            if m.trend == "declining"
        ]
        
        summary = PopulationHealthSummary(
            population_id=population_id,
            population_name=population_name,
            total_patients=len(patient_ids),
            risk_distribution=risk_distribution,
            total_care_gaps=len(all_gaps),
            critical_gaps=critical_gaps,
            gaps_by_measure=gaps_by_measure,
            quality_measures=quality_measures,
            overall_quality_score=round(overall_score * 100, 1),
            improvement_areas=improvement_areas,
            concern_areas=concern_areas
        )
        
        return summary
    
    async def identify_high_risk_patients(
        self,
        patient_ids: Optional[List[str]] = None,
        risk_threshold: RiskLevel = RiskLevel.HIGH
    ) -> List[PatientRiskProfile]:
        """
        Identify patients at or above a risk threshold.
        
        Useful for care management team prioritization.
        
        Args:
            patient_ids: Optional list to filter, or all if None
            risk_threshold: Minimum risk level to include
        
        Returns:
            List of high-risk patient profiles
        """
        high_risk = []
        risk_order = {
            RiskLevel.LOW: 0,
            RiskLevel.MODERATE: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3
        }
        threshold_value = risk_order[risk_threshold]
        
        patients_to_check = patient_ids or list(self._patient_cache.keys())
        
        for patient_id in patients_to_check:
            profile = await self.stratify_patient_risk(patient_id)
            if risk_order[profile.risk_level] >= threshold_value:
                high_risk.append(profile)
        
        # Sort by risk score descending
        high_risk.sort(key=lambda p: p.risk_score, reverse=True)
        
        return high_risk
    
    async def get_critical_care_gaps(
        self,
        patient_ids: Optional[List[str]] = None,
        max_results: int = 100
    ) -> List[CareGap]:
        """
        Get the most critical care gaps across a population.
        
        Useful for population health outreach prioritization.
        
        Args:
            patient_ids: Optional list to filter
            max_results: Maximum gaps to return
        
        Returns:
            List of critical/urgent care gaps sorted by priority
        """
        all_gaps = []
        
        patients_to_check = patient_ids or []
        
        for patient_id in patients_to_check:
            gaps = await self.analyze_patient_care_gaps(patient_id)
            critical = [
                g for g in gaps 
                if g.priority in (CareGapPriority.CRITICAL, CareGapPriority.URGENT)
            ]
            all_gaps.extend(critical)
        
        # Sort by priority then days overdue
        all_gaps.sort(
            key=lambda g: (
                0 if g.priority == CareGapPriority.CRITICAL else 1,
                -g.days_overdue
            )
        )
        
        return all_gaps[:max_results]
    
    async def generate_quality_report(
        self,
        population_id: str,
        population_name: str,
        patient_ids: List[str],
        report_format: str = "summary"
    ) -> Dict[str, Any]:
        """
        Generate a quality report for a population.
        
        Args:
            population_id: Population identifier
            population_name: Human-readable name
            patient_ids: Patients in population
            report_format: "summary", "detailed", or "executive"
        
        Returns:
            Report as dictionary
        """
        summary = await self.generate_population_summary(
            population_id, population_name, patient_ids
        )
        
        return await self.reporter.generate_report(
            summary=summary,
            format=report_format
        )
    
    async def record_gap_closure(
        self,
        patient_id: str,
        measure_id: str,
        completion_date: date,
        result: Optional[str] = None
    ) -> bool:
        """
        Record that a care gap has been closed.
        
        Args:
            patient_id: Patient identifier
            measure_id: Quality measure ID
            completion_date: Date the measure was completed
            result: Optional result value (e.g., A1c value)
        
        Returns:
            True if gap was found and closed
        """
        logger.info(
            f"Recording gap closure: patient={patient_id}, "
            f"measure={measure_id}, date={completion_date}"
        )
        
        return await self.care_gap_analyzer.close_gap(
            patient_id=patient_id,
            measure_id=measure_id,
            completion_date=completion_date,
            result=result
        )
    
    async def record_patient_outreach(
        self,
        patient_id: str,
        gap_id: str,
        outreach_type: str,
        outcome: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Record patient outreach attempt for a care gap.
        
        Args:
            patient_id: Patient identifier
            gap_id: Care gap identifier
            outreach_type: Type of outreach (phone, letter, portal)
            outcome: Outcome (reached, voicemail, scheduled, declined)
            notes: Optional notes
        
        Returns:
            True if recorded successfully
        """
        logger.info(
            f"Recording outreach: patient={patient_id}, gap={gap_id}, "
            f"type={outreach_type}, outcome={outcome}"
        )
        
        return await self.care_gap_analyzer.record_outreach(
            patient_id=patient_id,
            gap_id=gap_id,
            outreach_type=outreach_type,
            outcome=outcome,
            notes=notes
        )
