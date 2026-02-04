"""
Quality Metrics Engine.

Calculates quality metrics for HEDIS, MIPS, Medicare Stars, and commercial programs.

SUPPORTED QUALITY PROGRAMS:

HEDIS (Healthcare Effectiveness Data and Information Set):
    - Used by health plans for quality measurement
    - ~90 measures across 6 domains
    - Affects plan Star ratings and accreditation
    
MIPS (Merit-based Incentive Payment System):
    - CMS program for Medicare Part B providers
    - 4 categories: Quality, Cost, PI, IA
    - Payment adjustments from -9% to +9%
    
Medicare Stars (5-Star Quality Rating System):
    - Used for Medicare Advantage and Part D plans
    - 1-5 star ratings affect plan bonuses
    - Key measures: HEDIS + CAHPS + HOS + admin

MEASURE SPECIFICATIONS:

Each measure has:
    - Denominator: Eligible population
    - Numerator: Those meeting the measure
    - Exclusions: Valid reasons to exclude from denominator
    - Data sources: Claims, EHR, patient surveys
    - Reporting period: Usually calendar year

BENCHMARKS:

Rates are compared to national/regional benchmarks:
    - Below 25th percentile: Poor
    - 25th-50th percentile: Below average
    - 50th-75th percentile: Average
    - 75th-90th percentile: Good
    - Above 90th percentile: Excellent
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


class QualityProgram(Enum):
    """Quality measurement programs."""
    HEDIS = "hedis"
    MIPS = "mips"
    STARS = "medicare_stars"
    COMMERCIAL = "commercial_quality"


@dataclass
class QualityMeasureResult:
    """Result for a specific quality measure."""
    measure_id: str
    measure_name: str
    program: QualityProgram
    
    numerator: int = 0
    denominator: int = 0
    rate: float = 0.0
    
    benchmark: float = 0.0
    percentile: int = 0
    stars_rating: int = 0
    
    trend: str = ""
    gap_count: int = 0


@dataclass
class MeasureSpecification:
    """Specification for a quality measure."""
    measure_id: str
    measure_name: str
    description: str
    
    programs: List[QualityProgram]
    domain: str  # e.g., "Prevention", "Chronic Care", "Behavioral Health"
    
    # Eligibility criteria
    age_min: int
    age_max: int
    gender: Optional[str] = None
    conditions: List[str] = field(default_factory=list)
    
    # Benchmarks (national percentiles)
    benchmark_25th: float = 0.0
    benchmark_50th: float = 0.0
    benchmark_75th: float = 0.0
    benchmark_90th: float = 0.0
    
    # Stars thresholds (for STARS program)
    stars_1: float = 0.0
    stars_2: float = 0.0
    stars_3: float = 0.0
    stars_4: float = 0.0
    stars_5: float = 0.0
    
    # Weighting
    weight: float = 1.0  # For composite scores


# Quality measure specifications
MEASURE_SPECIFICATIONS = {
    "BCS": MeasureSpecification(
        measure_id="BCS",
        measure_name="Breast Cancer Screening",
        description="Mammogram within 2 years for women 50-74",
        programs=[QualityProgram.HEDIS, QualityProgram.STARS, QualityProgram.MIPS],
        domain="Prevention",
        age_min=50,
        age_max=74,
        gender="F",
        benchmark_25th=0.65,
        benchmark_50th=0.72,
        benchmark_75th=0.78,
        benchmark_90th=0.84,
        stars_1=0.50,
        stars_2=0.60,
        stars_3=0.70,
        stars_4=0.77,
        stars_5=0.84,
        weight=3.0
    ),
    "COL": MeasureSpecification(
        measure_id="COL",
        measure_name="Colorectal Cancer Screening",
        description="Appropriate screening for ages 45-75",
        programs=[QualityProgram.HEDIS, QualityProgram.STARS, QualityProgram.MIPS],
        domain="Prevention",
        age_min=45,
        age_max=75,
        benchmark_25th=0.58,
        benchmark_50th=0.66,
        benchmark_75th=0.73,
        benchmark_90th=0.80,
        stars_1=0.40,
        stars_2=0.52,
        stars_3=0.64,
        stars_4=0.72,
        stars_5=0.80,
        weight=3.0
    ),
    "CCS": MeasureSpecification(
        measure_id="CCS",
        measure_name="Cervical Cancer Screening",
        description="Pap test or HPV test for women 21-64",
        programs=[QualityProgram.HEDIS, QualityProgram.STARS],
        domain="Prevention",
        age_min=21,
        age_max=64,
        gender="F",
        benchmark_25th=0.68,
        benchmark_50th=0.75,
        benchmark_75th=0.81,
        benchmark_90th=0.86,
        stars_1=0.55,
        stars_2=0.65,
        stars_3=0.73,
        stars_4=0.80,
        stars_5=0.86,
        weight=1.0
    ),
    "DCA": MeasureSpecification(
        measure_id="DCA",
        measure_name="Hemoglobin A1c Control (<8%)",
        description="Diabetic patients with A1c < 8%",
        programs=[QualityProgram.HEDIS, QualityProgram.STARS, QualityProgram.MIPS],
        domain="Chronic Care",
        age_min=18,
        age_max=75,
        conditions=["diabetes"],
        benchmark_25th=0.55,
        benchmark_50th=0.63,
        benchmark_75th=0.70,
        benchmark_90th=0.77,
        stars_1=0.40,
        stars_2=0.52,
        stars_3=0.60,
        stars_4=0.68,
        stars_5=0.77,
        weight=3.0
    ),
    "CBP": MeasureSpecification(
        measure_id="CBP",
        measure_name="Controlling Blood Pressure",
        description="Hypertensive patients with BP < 140/90",
        programs=[QualityProgram.HEDIS, QualityProgram.STARS, QualityProgram.MIPS],
        domain="Chronic Care",
        age_min=18,
        age_max=85,
        conditions=["hypertension"],
        benchmark_25th=0.58,
        benchmark_50th=0.66,
        benchmark_75th=0.73,
        benchmark_90th=0.80,
        stars_1=0.45,
        stars_2=0.55,
        stars_3=0.64,
        stars_4=0.72,
        stars_5=0.80,
        weight=3.0
    ),
    "IMA": MeasureSpecification(
        measure_id="IMA",
        measure_name="Immunizations for Adolescents",
        description="Tdap, HPV, and meningococcal vaccines by age 13",
        programs=[QualityProgram.HEDIS],
        domain="Prevention",
        age_min=13,
        age_max=17,
        benchmark_25th=0.25,
        benchmark_50th=0.35,
        benchmark_75th=0.45,
        benchmark_90th=0.55,
        weight=1.0
    ),
    "DEP": MeasureSpecification(
        measure_id="DEP",
        measure_name="Screening for Depression",
        description="PHQ-9 or equivalent within measurement year",
        programs=[QualityProgram.HEDIS, QualityProgram.MIPS],
        domain="Behavioral Health",
        age_min=12,
        age_max=120,
        benchmark_25th=0.50,
        benchmark_50th=0.60,
        benchmark_75th=0.70,
        benchmark_90th=0.80,
        weight=1.0
    ),
    "AAB": MeasureSpecification(
        measure_id="AAB",
        measure_name="Avoidance of Antibiotic Treatment for Acute Bronchitis",
        description="No antibiotic prescribed for acute bronchitis",
        programs=[QualityProgram.HEDIS],
        domain="Overuse/Appropriateness",
        age_min=3,
        age_max=120,
        benchmark_25th=0.30,
        benchmark_50th=0.40,
        benchmark_75th=0.50,
        benchmark_90th=0.60,
        weight=1.0
    ),
    "MRP": MeasureSpecification(
        measure_id="MRP",
        measure_name="Medication Reconciliation Post-Discharge",
        description="Med rec within 30 days of hospital discharge",
        programs=[QualityProgram.HEDIS, QualityProgram.MIPS],
        domain="Transitions of Care",
        age_min=18,
        age_max=120,
        benchmark_25th=0.40,
        benchmark_50th=0.50,
        benchmark_75th=0.60,
        benchmark_90th=0.70,
        weight=2.0
    ),
    "FMC": MeasureSpecification(
        measure_id="FMC",
        measure_name="Follow-up After Emergency Department Visit",
        description="Outpatient follow-up within 7 days of ED visit",
        programs=[QualityProgram.HEDIS],
        domain="Access/Availability",
        age_min=18,
        age_max=120,
        benchmark_25th=0.35,
        benchmark_50th=0.45,
        benchmark_75th=0.55,
        benchmark_90th=0.65,
        weight=1.5
    ),
}


class QualityMetricsEngine:
    """
    Engine for calculating quality metrics across programs.
    
    This is the core calculation engine that takes patient data
    and produces quality measure results with benchmarking.
    """
    
    def __init__(self, programs: Optional[List[QualityProgram]] = None):
        """
        Initialize quality metrics engine.
        
        Args:
            programs: Quality programs to calculate (default: all)
        """
        self.programs = programs or list(QualityProgram)
        self.specifications = MEASURE_SPECIFICATIONS
        
        # Mock data store for patient measure status
        self._patient_measures: Dict[str, Dict[str, bool]] = {}
        self._historical_rates: Dict[str, List[float]] = {}
    
    async def calculate_metrics(
        self,
        population_ids: Optional[List[str]] = None,
        programs: Optional[List[QualityProgram]] = None,
        measure_ids: Optional[List[str]] = None
    ) -> List[QualityMeasureResult]:
        """
        Calculate quality metrics for a population.
        
        Args:
            population_ids: Patient IDs to include (None = all)
            programs: Programs to calculate (None = use instance default)
            measure_ids: Specific measures (None = all applicable)
        
        Returns:
            List of QualityMeasureResult objects
        """
        programs = programs or self.programs
        results = []
        
        # Filter measures by program and measure_ids
        applicable_measures = {}
        for mid, spec in self.specifications.items():
            if measure_ids and mid not in measure_ids:
                continue
            if any(p in programs for p in spec.programs):
                applicable_measures[mid] = spec
        
        for measure_id, spec in applicable_measures.items():
            result = await self._calculate_measure(
                measure_id, spec, population_ids
            )
            results.append(result)
        
        logger.info(f"Calculated {len(results)} quality measures")
        return results
    
    async def _calculate_measure(
        self,
        measure_id: str,
        spec: MeasureSpecification,
        population_ids: Optional[List[str]]
    ) -> QualityMeasureResult:
        """Calculate a single quality measure."""
        # In production, this would query patient data
        # For now, use mock data
        
        if population_ids:
            denominator = len(population_ids)
            # Mock: assume 70% meet the measure
            numerator = int(denominator * 0.70)
        else:
            denominator = 1000  # Default population size
            numerator = 700
        
        if denominator > 0:
            rate = numerator / denominator
        else:
            rate = 0.0
        
        # Determine percentile
        percentile = self._calculate_percentile(rate, spec)
        
        # Determine stars rating
        stars = self._calculate_stars(rate, spec)
        
        # Determine trend
        trend = self._calculate_trend(measure_id, rate)
        
        # Gap count (patients not meeting measure)
        gap_count = denominator - numerator
        
        result = QualityMeasureResult(
            measure_id=measure_id,
            measure_name=spec.measure_name,
            program=spec.programs[0],  # Primary program
            numerator=numerator,
            denominator=denominator,
            rate=round(rate, 4),
            benchmark=spec.benchmark_50th,
            percentile=percentile,
            stars_rating=stars,
            trend=trend,
            gap_count=gap_count
        )
        
        return result
    
    def _calculate_percentile(
        self,
        rate: float,
        spec: MeasureSpecification
    ) -> int:
        """Calculate percentile based on benchmarks."""
        if rate >= spec.benchmark_90th:
            return 95
        elif rate >= spec.benchmark_75th:
            return 75 + int((rate - spec.benchmark_75th) / 
                           (spec.benchmark_90th - spec.benchmark_75th) * 15)
        elif rate >= spec.benchmark_50th:
            return 50 + int((rate - spec.benchmark_50th) / 
                           (spec.benchmark_75th - spec.benchmark_50th) * 25)
        elif rate >= spec.benchmark_25th:
            return 25 + int((rate - spec.benchmark_25th) / 
                           (spec.benchmark_50th - spec.benchmark_25th) * 25)
        else:
            return int(rate / spec.benchmark_25th * 25)
    
    def _calculate_stars(
        self,
        rate: float,
        spec: MeasureSpecification
    ) -> int:
        """Calculate Medicare Stars rating (1-5)."""
        if spec.stars_5 and rate >= spec.stars_5:
            return 5
        elif spec.stars_4 and rate >= spec.stars_4:
            return 4
        elif spec.stars_3 and rate >= spec.stars_3:
            return 3
        elif spec.stars_2 and rate >= spec.stars_2:
            return 2
        elif spec.stars_1 and rate >= spec.stars_1:
            return 1
        else:
            return 0
    
    def _calculate_trend(self, measure_id: str, current_rate: float) -> str:
        """Calculate trend based on historical rates."""
        historical = self._historical_rates.get(measure_id, [])
        
        if len(historical) < 2:
            # Store current and return stable
            if measure_id not in self._historical_rates:
                self._historical_rates[measure_id] = []
            self._historical_rates[measure_id].append(current_rate)
            return "stable"
        
        # Compare to average of last 3 periods
        recent_avg = sum(historical[-3:]) / len(historical[-3:])
        
        if current_rate > recent_avg * 1.05:
            return "improving"
        elif current_rate < recent_avg * 0.95:
            return "declining"
        else:
            return "stable"
    
    async def calculate_composite_score(
        self,
        results: List[QualityMeasureResult]
    ) -> float:
        """
        Calculate weighted composite quality score.
        
        Args:
            results: List of measure results
        
        Returns:
            Weighted composite score (0-100)
        """
        if not results:
            return 0.0
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for result in results:
            spec = self.specifications.get(result.measure_id)
            weight = spec.weight if spec else 1.0
            
            total_weight += weight
            weighted_sum += result.rate * weight * 100
        
        if total_weight > 0:
            return round(weighted_sum / total_weight, 1)
        return 0.0
    
    async def get_measure_details(
        self,
        measure_id: str
    ) -> Optional[MeasureSpecification]:
        """Get detailed specification for a measure."""
        return self.specifications.get(measure_id)
    
    async def get_program_measures(
        self,
        program: QualityProgram
    ) -> List[str]:
        """Get all measure IDs for a specific program."""
        return [
            mid for mid, spec in self.specifications.items()
            if program in spec.programs
        ]
    
    async def get_domain_measures(self, domain: str) -> List[str]:
        """Get all measure IDs for a specific domain."""
        return [
            mid for mid, spec in self.specifications.items()
            if spec.domain.lower() == domain.lower()
        ]
    
    async def simulate_improvement(
        self,
        measure_id: str,
        current_rate: float,
        target_rate: float,
        population_size: int
    ) -> Dict[str, Any]:
        """
        Simulate impact of improving a measure.
        
        Args:
            measure_id: Measure to improve
            current_rate: Current performance rate
            target_rate: Target performance rate
            population_size: Size of eligible population
        
        Returns:
            Dict with impact analysis
        """
        spec = self.specifications.get(measure_id)
        if not spec:
            return {"error": "Measure not found"}
        
        current_numerator = int(population_size * current_rate)
        target_numerator = int(population_size * target_rate)
        patients_to_close = target_numerator - current_numerator
        
        current_percentile = self._calculate_percentile(current_rate, spec)
        target_percentile = self._calculate_percentile(target_rate, spec)
        
        current_stars = self._calculate_stars(current_rate, spec)
        target_stars = self._calculate_stars(target_rate, spec)
        
        return {
            "measure_id": measure_id,
            "measure_name": spec.measure_name,
            "current_rate": current_rate,
            "target_rate": target_rate,
            "patients_to_close": patients_to_close,
            "current_percentile": current_percentile,
            "target_percentile": target_percentile,
            "percentile_improvement": target_percentile - current_percentile,
            "current_stars": current_stars,
            "target_stars": target_stars,
            "stars_improvement": target_stars - current_stars
        }
