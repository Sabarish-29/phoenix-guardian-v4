"""
Phoenix Guardian - FDA CDS Risk Scoring Engine.

Implements quantitative risk scoring for Clinical Decision Support functions
based on FDA guidance, IEC 62304, and ISO 14971.

Risk Dimensions:
1. Clinical Impact - Potential harm from incorrect recommendations
2. Autonomy Level - Degree of human oversight required
3. Decision Criticality - Time sensitivity and reversibility
4. Population Vulnerability - Patient population characteristics
5. Data Quality - Input data reliability and validation

References:
- FDA Guidance: Clinical Decision Support Software (Sept 2022)
- IEC 62304:2006+A1:2015 - Medical Device Software Lifecycle
- ISO 14971:2019 - Medical Device Risk Management
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import logging
import math

logger = logging.getLogger(__name__)


# =============================================================================
# Risk Dimension Enums
# =============================================================================


class ClinicalImpactLevel(str, Enum):
    """Potential clinical impact of CDS function."""
    
    NEGLIGIBLE = "negligible"  # No clinical impact
    MINOR = "minor"  # Minor discomfort or inconvenience
    MODERATE = "moderate"  # Temporary harm, recoverable
    MAJOR = "major"  # Permanent harm or prolonged hospitalization
    CATASTROPHIC = "catastrophic"  # Death or life-threatening


class AutonomyLevel(str, Enum):
    """Level of human oversight for CDS function."""
    
    INFORMATIONAL = "informational"  # Display only, no recommendations
    ADVISORY = "advisory"  # Recommendations with full HCP control
    ASSISTIVE = "assistive"  # Pre-populates decisions, HCP confirms
    SEMI_AUTONOMOUS = "semi_autonomous"  # Acts unless HCP intervenes
    FULLY_AUTONOMOUS = "fully_autonomous"  # Acts without HCP review


class PopulationVulnerability(str, Enum):
    """Vulnerability level of target patient population."""
    
    GENERAL = "general"  # General adult population
    ELDERLY = "elderly"  # Geriatric patients (65+)
    PEDIATRIC = "pediatric"  # Children and adolescents
    NEONATAL = "neonatal"  # Newborns and infants
    CRITICAL = "critical"  # ICU/critically ill patients
    IMMUNOCOMPROMISED = "immunocompromised"  # Vulnerable immune systems


class DataQualityLevel(str, Enum):
    """Quality and reliability of input data."""
    
    HIGH = "high"  # Validated, structured, from verified sources
    MODERATE = "moderate"  # Generally reliable, some validation
    LOW = "low"  # Unvalidated, potentially incomplete
    UNKNOWN = "unknown"  # Quality cannot be determined


class IEC62304SafetyClass(str, Enum):
    """IEC 62304 software safety classifications."""
    
    CLASS_A = "class_a"  # No injury or damage to health possible
    CLASS_B = "class_b"  # Non-serious injury possible
    CLASS_C = "class_c"  # Death or serious injury possible


# =============================================================================
# Risk Assessment Data Classes
# =============================================================================


@dataclass
class RiskDimensionScore:
    """Score for a single risk dimension."""
    
    dimension: str
    raw_score: float  # 0.0 to 1.0
    weight: float  # Dimension weight in overall score
    weighted_score: float  # raw_score * weight
    rationale: str
    evidence: List[str] = field(default_factory=list)


@dataclass
class RiskMitigation:
    """A risk mitigation measure."""
    
    mitigation_id: str
    description: str
    effectiveness: float  # 0.0 to 1.0 reduction in risk
    implementation_status: str  # planned, implemented, verified
    verification_evidence: Optional[str] = None


@dataclass
class RiskScoreResult:
    """Complete risk score calculation result."""
    
    function_id: str
    function_name: str
    
    # Dimension scores
    dimension_scores: List[RiskDimensionScore] = field(default_factory=list)
    
    # Overall scores
    raw_risk_score: float = 0.0  # Before mitigations
    residual_risk_score: float = 0.0  # After mitigations
    
    # IEC 62304 classification
    iec_62304_class: IEC62304SafetyClass = IEC62304SafetyClass.CLASS_A
    
    # Risk acceptability
    risk_acceptable: bool = True
    acceptability_rationale: str = ""
    
    # Mitigations
    mitigations: List[RiskMitigation] = field(default_factory=list)
    
    # Metadata
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    calculator_version: str = "1.0.0"
    signature: str = ""
    
    def __post_init__(self) -> None:
        """Generate signature after init."""
        if not self.signature:
            self.signature = self._generate_signature()
    
    def _generate_signature(self) -> str:
        """Generate SHA-256 signature for audit."""
        content = json.dumps({
            "function_id": self.function_id,
            "raw_risk": self.raw_risk_score,
            "residual_risk": self.residual_risk_score,
            "iec_class": self.iec_62304_class.value,
            "calculated_at": self.calculated_at.isoformat(),
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class CDSRiskProfile:
    """Risk profile input for a CDS function."""
    
    function_id: str
    function_name: str
    
    # Clinical impact
    clinical_impact: ClinicalImpactLevel = ClinicalImpactLevel.MINOR
    impact_description: str = ""
    
    # Autonomy
    autonomy_level: AutonomyLevel = AutonomyLevel.ADVISORY
    human_review_required: bool = True
    
    # Decision characteristics
    time_critical: bool = False
    decision_reversible: bool = True
    frequency_of_use: str = "occasional"  # rare, occasional, frequent, continuous
    
    # Population
    target_population: PopulationVulnerability = PopulationVulnerability.GENERAL
    population_size: str = "small"  # small, medium, large, enterprise
    
    # Data quality
    input_data_quality: DataQualityLevel = DataQualityLevel.MODERATE
    data_validation_present: bool = True
    
    # Existing controls
    existing_mitigations: List[str] = field(default_factory=list)


# =============================================================================
# Risk Scoring Engine
# =============================================================================


class CDSRiskScoringEngine:
    """
    Quantitative risk scoring engine for CDS functions.
    
    Implements multi-dimensional risk assessment based on:
    - FDA CDS guidance
    - IEC 62304 safety classification
    - ISO 14971 risk management principles
    """
    
    # Risk dimension weights (must sum to 1.0)
    DIMENSION_WEIGHTS = {
        "clinical_impact": 0.30,
        "autonomy": 0.25,
        "decision_criticality": 0.20,
        "population_vulnerability": 0.15,
        "data_quality": 0.10,
    }
    
    # Clinical impact severity scores
    IMPACT_SCORES = {
        ClinicalImpactLevel.NEGLIGIBLE: 0.05,
        ClinicalImpactLevel.MINOR: 0.20,
        ClinicalImpactLevel.MODERATE: 0.45,
        ClinicalImpactLevel.MAJOR: 0.75,
        ClinicalImpactLevel.CATASTROPHIC: 1.00,
    }
    
    # Autonomy level scores
    AUTONOMY_SCORES = {
        AutonomyLevel.INFORMATIONAL: 0.05,
        AutonomyLevel.ADVISORY: 0.20,
        AutonomyLevel.ASSISTIVE: 0.40,
        AutonomyLevel.SEMI_AUTONOMOUS: 0.70,
        AutonomyLevel.FULLY_AUTONOMOUS: 1.00,
    }
    
    # Population vulnerability scores
    POPULATION_SCORES = {
        PopulationVulnerability.GENERAL: 0.20,
        PopulationVulnerability.ELDERLY: 0.50,
        PopulationVulnerability.PEDIATRIC: 0.60,
        PopulationVulnerability.NEONATAL: 0.80,
        PopulationVulnerability.CRITICAL: 0.90,
        PopulationVulnerability.IMMUNOCOMPROMISED: 0.70,
    }
    
    # Data quality scores (inverted - lower quality = higher risk)
    DATA_QUALITY_SCORES = {
        DataQualityLevel.HIGH: 0.10,
        DataQualityLevel.MODERATE: 0.35,
        DataQualityLevel.LOW: 0.70,
        DataQualityLevel.UNKNOWN: 0.90,
    }
    
    # Risk acceptability thresholds
    RISK_THRESHOLDS = {
        "acceptable": 0.30,  # Below this is acceptable
        "alara_required": 0.50,  # Requires ALARA (As Low As Reasonably Achievable)
        "unacceptable": 0.70,  # Above this requires redesign
    }
    
    def __init__(self) -> None:
        """Initialize the risk scoring engine."""
        self.scoring_history: List[RiskScoreResult] = []
        logger.info("CDS Risk Scoring Engine initialized")
    
    def calculate_risk_score(
        self,
        profile: CDSRiskProfile,
        mitigations: Optional[List[RiskMitigation]] = None,
    ) -> RiskScoreResult:
        """
        Calculate comprehensive risk score for a CDS function.
        
        Args:
            profile: Risk profile for the function
            mitigations: Optional list of risk mitigations
            
        Returns:
            Complete risk score result
        """
        logger.info(f"Calculating risk score for: {profile.function_name}")
        
        dimension_scores: List[RiskDimensionScore] = []
        
        # Calculate each dimension
        dimension_scores.append(self._score_clinical_impact(profile))
        dimension_scores.append(self._score_autonomy(profile))
        dimension_scores.append(self._score_decision_criticality(profile))
        dimension_scores.append(self._score_population_vulnerability(profile))
        dimension_scores.append(self._score_data_quality(profile))
        
        # Calculate raw risk score (weighted sum)
        raw_risk_score = sum(d.weighted_score for d in dimension_scores)
        
        # Apply mitigations
        mitigations = mitigations or []
        residual_risk_score = self._apply_mitigations(raw_risk_score, mitigations)
        
        # Determine IEC 62304 class
        iec_class = self._determine_iec_class(raw_risk_score, profile)
        
        # Assess acceptability
        acceptable, rationale = self._assess_acceptability(residual_risk_score)
        
        result = RiskScoreResult(
            function_id=profile.function_id,
            function_name=profile.function_name,
            dimension_scores=dimension_scores,
            raw_risk_score=raw_risk_score,
            residual_risk_score=residual_risk_score,
            iec_62304_class=iec_class,
            risk_acceptable=acceptable,
            acceptability_rationale=rationale,
            mitigations=mitigations,
        )
        
        self.scoring_history.append(result)
        
        logger.info(
            f"Risk score calculated: raw={raw_risk_score:.3f}, "
            f"residual={residual_risk_score:.3f}, class={iec_class.value}"
        )
        
        return result
    
    def _score_clinical_impact(self, profile: CDSRiskProfile) -> RiskDimensionScore:
        """Score the clinical impact dimension."""
        
        raw_score = self.IMPACT_SCORES[profile.clinical_impact]
        weight = self.DIMENSION_WEIGHTS["clinical_impact"]
        
        evidence = [f"Clinical impact level: {profile.clinical_impact.value}"]
        if profile.impact_description:
            evidence.append(f"Description: {profile.impact_description}")
        
        rationale = self._get_impact_rationale(profile.clinical_impact)
        
        return RiskDimensionScore(
            dimension="clinical_impact",
            raw_score=raw_score,
            weight=weight,
            weighted_score=raw_score * weight,
            rationale=rationale,
            evidence=evidence,
        )
    
    def _score_autonomy(self, profile: CDSRiskProfile) -> RiskDimensionScore:
        """Score the autonomy level dimension."""
        
        raw_score = self.AUTONOMY_SCORES[profile.autonomy_level]
        
        # Reduce score if human review is enforced
        if profile.human_review_required and profile.autonomy_level != AutonomyLevel.FULLY_AUTONOMOUS:
            raw_score *= 0.7
        
        weight = self.DIMENSION_WEIGHTS["autonomy"]
        
        evidence = [
            f"Autonomy level: {profile.autonomy_level.value}",
            f"Human review required: {profile.human_review_required}",
        ]
        
        rationale = (
            f"Function operates at {profile.autonomy_level.value} level "
            f"{'with' if profile.human_review_required else 'without'} mandatory human review"
        )
        
        return RiskDimensionScore(
            dimension="autonomy",
            raw_score=raw_score,
            weight=weight,
            weighted_score=raw_score * weight,
            rationale=rationale,
            evidence=evidence,
        )
    
    def _score_decision_criticality(self, profile: CDSRiskProfile) -> RiskDimensionScore:
        """Score the decision criticality dimension."""
        
        # Base score from reversibility
        raw_score = 0.3 if profile.decision_reversible else 0.7
        
        # Adjust for time criticality
        if profile.time_critical:
            raw_score += 0.2
        
        # Adjust for frequency
        frequency_adjustments = {
            "rare": -0.1,
            "occasional": 0.0,
            "frequent": 0.1,
            "continuous": 0.2,
        }
        raw_score += frequency_adjustments.get(profile.frequency_of_use, 0.0)
        
        raw_score = max(0.0, min(1.0, raw_score))
        weight = self.DIMENSION_WEIGHTS["decision_criticality"]
        
        evidence = [
            f"Time critical: {profile.time_critical}",
            f"Decision reversible: {profile.decision_reversible}",
            f"Frequency of use: {profile.frequency_of_use}",
        ]
        
        rationale = self._get_criticality_rationale(profile)
        
        return RiskDimensionScore(
            dimension="decision_criticality",
            raw_score=raw_score,
            weight=weight,
            weighted_score=raw_score * weight,
            rationale=rationale,
            evidence=evidence,
        )
    
    def _score_population_vulnerability(
        self, profile: CDSRiskProfile
    ) -> RiskDimensionScore:
        """Score the population vulnerability dimension."""
        
        raw_score = self.POPULATION_SCORES[profile.target_population]
        
        # Adjust for population size (larger = higher risk due to exposure)
        size_adjustments = {
            "small": 0.0,
            "medium": 0.05,
            "large": 0.10,
            "enterprise": 0.15,
        }
        raw_score += size_adjustments.get(profile.population_size, 0.0)
        raw_score = min(1.0, raw_score)
        
        weight = self.DIMENSION_WEIGHTS["population_vulnerability"]
        
        evidence = [
            f"Target population: {profile.target_population.value}",
            f"Population size: {profile.population_size}",
        ]
        
        rationale = (
            f"Function targets {profile.target_population.value} population "
            f"with {profile.population_size} deployment scale"
        )
        
        return RiskDimensionScore(
            dimension="population_vulnerability",
            raw_score=raw_score,
            weight=weight,
            weighted_score=raw_score * weight,
            rationale=rationale,
            evidence=evidence,
        )
    
    def _score_data_quality(self, profile: CDSRiskProfile) -> RiskDimensionScore:
        """Score the data quality dimension."""
        
        raw_score = self.DATA_QUALITY_SCORES[profile.input_data_quality]
        
        # Reduce score if validation is present
        if profile.data_validation_present:
            raw_score *= 0.7
        
        weight = self.DIMENSION_WEIGHTS["data_quality"]
        
        evidence = [
            f"Input data quality: {profile.input_data_quality.value}",
            f"Data validation present: {profile.data_validation_present}",
        ]
        
        rationale = (
            f"Input data quality is {profile.input_data_quality.value} "
            f"{'with' if profile.data_validation_present else 'without'} validation"
        )
        
        return RiskDimensionScore(
            dimension="data_quality",
            raw_score=raw_score,
            weight=weight,
            weighted_score=raw_score * weight,
            rationale=rationale,
            evidence=evidence,
        )
    
    def _apply_mitigations(
        self, raw_score: float, mitigations: List[RiskMitigation]
    ) -> float:
        """Apply risk mitigations to calculate residual risk."""
        
        residual = raw_score
        
        for mitigation in mitigations:
            if mitigation.implementation_status in ["implemented", "verified"]:
                # Reduce risk by effectiveness percentage
                reduction = raw_score * mitigation.effectiveness
                residual -= reduction
                
                logger.debug(
                    f"Mitigation '{mitigation.description}' reduced risk by {reduction:.3f}"
                )
        
        return max(0.0, residual)
    
    def _determine_iec_class(
        self, risk_score: float, profile: CDSRiskProfile
    ) -> IEC62304SafetyClass:
        """Determine IEC 62304 software safety class."""
        
        # Class C: Death or serious injury possible
        if (
            profile.clinical_impact in [ClinicalImpactLevel.MAJOR, ClinicalImpactLevel.CATASTROPHIC]
            or risk_score >= 0.6
        ):
            return IEC62304SafetyClass.CLASS_C
        
        # Class B: Non-serious injury possible
        if (
            profile.clinical_impact == ClinicalImpactLevel.MODERATE
            or risk_score >= 0.3
        ):
            return IEC62304SafetyClass.CLASS_B
        
        # Class A: No injury or damage possible
        return IEC62304SafetyClass.CLASS_A
    
    def _assess_acceptability(self, residual_risk: float) -> Tuple[bool, str]:
        """Assess if residual risk is acceptable."""
        
        if residual_risk <= self.RISK_THRESHOLDS["acceptable"]:
            return True, "Residual risk is within acceptable limits"
        
        if residual_risk <= self.RISK_THRESHOLDS["alara_required"]:
            return True, (
                "Risk requires ALARA (As Low As Reasonably Achievable) approach. "
                "Document justification for residual risk."
            )
        
        if residual_risk <= self.RISK_THRESHOLDS["unacceptable"]:
            return False, (
                "Risk exceeds acceptable threshold. Additional mitigations required "
                "or function redesign needed."
            )
        
        return False, (
            "Risk is unacceptable. Function should not be deployed without "
            "significant redesign and additional controls."
        )
    
    def _get_impact_rationale(self, impact: ClinicalImpactLevel) -> str:
        """Get rationale text for clinical impact level."""
        
        rationales = {
            ClinicalImpactLevel.NEGLIGIBLE: 
                "Function has no direct clinical impact on patient care",
            ClinicalImpactLevel.MINOR:
                "Incorrect recommendations may cause minor inconvenience but no harm",
            ClinicalImpactLevel.MODERATE:
                "Incorrect recommendations could lead to temporary harm requiring intervention",
            ClinicalImpactLevel.MAJOR:
                "Incorrect recommendations could lead to permanent harm or extended hospitalization",
            ClinicalImpactLevel.CATASTROPHIC:
                "Incorrect recommendations could directly lead to patient death or life-threatening harm",
        }
        return rationales.get(impact, "Impact level not specified")
    
    def _get_criticality_rationale(self, profile: CDSRiskProfile) -> str:
        """Get rationale for decision criticality."""
        
        parts = []
        
        if profile.time_critical:
            parts.append("Time-critical decisions require rapid response")
        
        if not profile.decision_reversible:
            parts.append("decisions are not easily reversible")
        else:
            parts.append("decisions can be reversed if needed")
        
        parts.append(f"function is used {profile.frequency_of_use}")
        
        return "; ".join(parts).capitalize()
    
    def generate_risk_matrix(
        self, results: List[RiskScoreResult]
    ) -> Dict[str, Any]:
        """
        Generate risk matrix visualization data.
        
        Args:
            results: List of risk score results
            
        Returns:
            Risk matrix data structure for visualization
        """
        matrix = {
            "title": "CDS Function Risk Matrix",
            "axes": {
                "x": "Likelihood/Frequency",
                "y": "Severity/Impact",
            },
            "zones": {
                "low": {"color": "#22c55e", "threshold": 0.30},
                "medium": {"color": "#eab308", "threshold": 0.50},
                "high": {"color": "#f97316", "threshold": 0.70},
                "critical": {"color": "#ef4444", "threshold": 1.00},
            },
            "functions": [],
        }
        
        for result in results:
            # Get relevant dimension scores
            impact_score = next(
                (d.raw_score for d in result.dimension_scores if d.dimension == "clinical_impact"),
                0.5,
            )
            criticality_score = next(
                (d.raw_score for d in result.dimension_scores if d.dimension == "decision_criticality"),
                0.5,
            )
            
            matrix["functions"].append({
                "id": result.function_id,
                "name": result.function_name,
                "x": criticality_score,
                "y": impact_score,
                "risk_score": result.residual_risk_score,
                "iec_class": result.iec_62304_class.value,
                "acceptable": result.risk_acceptable,
            })
        
        return matrix


# =============================================================================
# Standard Mitigations Library
# =============================================================================


def get_standard_mitigations() -> List[RiskMitigation]:
    """Get library of standard CDS risk mitigations."""
    
    return [
        RiskMitigation(
            mitigation_id="MIT-001",
            description="Mandatory physician review before any clinical action",
            effectiveness=0.25,
            implementation_status="implemented",
            verification_evidence="Workflow audit confirms 100% physician sign-off",
        ),
        RiskMitigation(
            mitigation_id="MIT-002",
            description="Display of recommendation basis and supporting evidence",
            effectiveness=0.15,
            implementation_status="implemented",
            verification_evidence="UI review confirmed transparency features",
        ),
        RiskMitigation(
            mitigation_id="MIT-003",
            description="Input data validation and completeness checks",
            effectiveness=0.10,
            implementation_status="implemented",
            verification_evidence="Validation rules documented and tested",
        ),
        RiskMitigation(
            mitigation_id="MIT-004",
            description="Alert fatigue reduction through smart filtering",
            effectiveness=0.08,
            implementation_status="implemented",
            verification_evidence="Alert suppression logic validated",
        ),
        RiskMitigation(
            mitigation_id="MIT-005",
            description="Real-time monitoring and anomaly detection",
            effectiveness=0.12,
            implementation_status="implemented",
            verification_evidence="Monitoring dashboard active with 24/7 coverage",
        ),
        RiskMitigation(
            mitigation_id="MIT-006",
            description="Comprehensive user training and competency verification",
            effectiveness=0.10,
            implementation_status="implemented",
            verification_evidence="Training completion records for all users",
        ),
        RiskMitigation(
            mitigation_id="MIT-007",
            description="Fail-safe defaults when data is incomplete",
            effectiveness=0.08,
            implementation_status="implemented",
            verification_evidence="Fail-safe behavior documented and tested",
        ),
        RiskMitigation(
            mitigation_id="MIT-008",
            description="Audit trail for all CDS recommendations and actions",
            effectiveness=0.05,
            implementation_status="implemented",
            verification_evidence="Audit logs reviewed and complete",
        ),
    ]


# =============================================================================
# Module Entry Point
# =============================================================================


if __name__ == "__main__":
    # Example usage - use logging instead of print for production compliance
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    engine = CDSRiskScoringEngine()
    
    # Create sample risk profile
    profile = CDSRiskProfile(
        function_id="pg-cds-001",
        function_name="Drug-Drug Interaction Checker",
        clinical_impact=ClinicalImpactLevel.MODERATE,
        impact_description="Missed interactions could lead to adverse drug events",
        autonomy_level=AutonomyLevel.ADVISORY,
        human_review_required=True,
        time_critical=True,
        decision_reversible=True,
        frequency_of_use="frequent",
        target_population=PopulationVulnerability.GENERAL,
        population_size="large",
        input_data_quality=DataQualityLevel.MODERATE,
        data_validation_present=True,
    )
    
    # Get standard mitigations
    mitigations = get_standard_mitigations()
    
    # Calculate risk score
    result = engine.calculate_risk_score(profile, mitigations)
    
    logger.info(f"Risk Score Result: {result.function_name}")
    logger.info(f"Raw Risk Score: {result.raw_risk_score:.3f}")
    logger.info(f"Residual Risk Score: {result.residual_risk_score:.3f}")
    logger.info(f"IEC 62304 Class: {result.iec_62304_class.value}")
    logger.info(f"Risk Acceptable: {result.risk_acceptable}")
    logger.info(f"Rationale: {result.acceptability_rationale}")
    
    logger.info("Dimension Scores:")
    for dim in result.dimension_scores:
        logger.info(f"  - {dim.dimension}: {dim.raw_score:.3f} (weighted: {dim.weighted_score:.3f})")
