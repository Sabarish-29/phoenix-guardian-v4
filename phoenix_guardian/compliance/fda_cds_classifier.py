"""
Phoenix Guardian - FDA Clinical Decision Support (CDS) Classification Module.

Implements FDA guidance for Clinical Decision Support software classification
per 21 CFR Part 820 and FDA Digital Health Software Precertification Program.

FDA CDS Categories:
- Non-Device CDS: Software that meets all 4 criteria (not regulated)
- Device CDS: Software that doesn't meet all 4 criteria (regulated as medical device)

The 4 Criteria for Non-Device CDS (must meet ALL):
1. Not intended to acquire, process, or analyze medical images/signals
2. Intended for displaying, analyzing, or printing medical information
3. Intended for supporting/providing recommendations to HCP
4. Intended for HCP to independently review basis for recommendations

References:
- FDA Guidance: Clinical Decision Support Software (Sept 2022)
- 21 CFR 820 - Quality System Regulation
- IEC 62304 - Medical Device Software Lifecycle
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# FDA CDS Classification Types
# =============================================================================


class CDSCategory(str, Enum):
    """FDA CDS software categories."""
    
    NON_DEVICE = "non_device_cds"  # Meets all 4 criteria - not FDA regulated
    DEVICE_CLASS_I = "device_class_i"  # Low risk - general controls
    DEVICE_CLASS_II = "device_class_ii"  # Moderate risk - special controls (510k)
    DEVICE_CLASS_III = "device_class_iii"  # High risk - PMA required
    EXEMPT = "exempt"  # Enforcement discretion


class CDSRiskLevel(str, Enum):
    """Risk levels for CDS functions."""
    
    MINIMAL = "minimal"  # Administrative, non-clinical
    LOW = "low"  # Clinical support, HCP review required
    MODERATE = "moderate"  # Clinical recommendations, some autonomy
    HIGH = "high"  # Direct patient impact, limited HCP review
    CRITICAL = "critical"  # Life-threatening decisions


class CDSFunctionType(str, Enum):
    """Types of CDS functions per FDA guidance."""
    
    # Non-Device Functions (meet all 4 criteria)
    CLINICAL_GUIDELINES = "clinical_guidelines"
    DRUG_DRUG_INTERACTION = "drug_drug_interaction"
    DRUG_ALLERGY_CHECK = "drug_allergy_check"
    LAB_REFERENCE_RANGES = "lab_reference_ranges"
    DOSAGE_CALCULATOR = "dosage_calculator"
    CLINICAL_REMINDERS = "clinical_reminders"
    
    # Device Functions (don't meet all 4 criteria)
    IMAGE_ANALYSIS = "image_analysis"
    DIAGNOSTIC_PREDICTION = "diagnostic_prediction"
    TREATMENT_RECOMMENDATION = "treatment_recommendation"
    RISK_PREDICTION = "risk_prediction"
    AUTONOMOUS_DECISION = "autonomous_decision"


class Criterion(str, Enum):
    """The 4 FDA criteria for Non-Device CDS."""
    
    NO_IMAGE_SIGNAL_PROCESSING = "criterion_1"  # Not for images/signals
    DISPLAYS_MEDICAL_INFO = "criterion_2"  # Displays/analyzes/prints info
    SUPPORTS_HCP = "criterion_3"  # Supports HCP recommendations
    HCP_INDEPENDENT_REVIEW = "criterion_4"  # HCP can independently review


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CDSFunction:
    """Represents a single CDS function to be classified."""
    
    function_id: str
    name: str
    description: str
    function_type: CDSFunctionType
    
    # Input/Output characteristics
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    
    # Clinical context
    clinical_domain: str = ""
    target_users: List[str] = field(default_factory=list)
    patient_population: str = ""
    
    # Risk factors
    time_criticality: str = "non_urgent"  # urgent, time_sensitive, non_urgent
    reversibility: str = "reversible"  # reversible, partially_reversible, irreversible
    
    # FDA criteria assessment
    processes_images_signals: bool = False
    provides_recommendations: bool = True
    requires_hcp_review: bool = True
    hcp_can_review_basis: bool = True
    
    # Metadata
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_assessed: Optional[datetime] = None


@dataclass
class CDSAssessment:
    """Result of FDA CDS classification assessment."""
    
    function_id: str
    function_name: str
    
    # Classification result
    category: CDSCategory
    risk_level: CDSRiskLevel
    
    # Criteria evaluation
    criteria_met: Dict[Criterion, bool] = field(default_factory=dict)
    criteria_rationale: Dict[Criterion, str] = field(default_factory=dict)
    
    # Risk scoring
    risk_score: float = 0.0
    risk_factors: List[str] = field(default_factory=list)
    mitigating_factors: List[str] = field(default_factory=list)
    
    # Regulatory requirements
    regulatory_pathway: str = ""
    required_documentation: List[str] = field(default_factory=list)
    required_controls: List[str] = field(default_factory=list)
    
    # Audit trail
    assessed_by: str = "phoenix_guardian_cds_classifier"
    assessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    assessment_version: str = "1.0.0"
    signature_hash: str = ""
    
    def __post_init__(self) -> None:
        """Generate signature hash after initialization."""
        if not self.signature_hash:
            self.signature_hash = self._generate_signature()
    
    def _generate_signature(self) -> str:
        """Generate SHA-256 signature for audit trail."""
        content = json.dumps({
            "function_id": self.function_id,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "criteria_met": {k.value: v for k, v in self.criteria_met.items()},
            "risk_score": self.risk_score,
            "assessed_at": self.assessed_at.isoformat(),
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class CDSClassificationReport:
    """Complete classification report for a CDS system."""
    
    system_name: str
    system_version: str
    
    # Functions assessed
    functions: List[CDSFunction] = field(default_factory=list)
    assessments: List[CDSAssessment] = field(default_factory=list)
    
    # Overall classification
    highest_risk_level: CDSRiskLevel = CDSRiskLevel.MINIMAL
    overall_category: CDSCategory = CDSCategory.NON_DEVICE
    
    # Compliance status
    fda_compliant: bool = False
    hipaa_compliant: bool = False
    requires_510k: bool = False
    requires_pma: bool = False
    
    # Metadata
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    generated_by: str = "phoenix_guardian_cds_classifier"
    report_hash: str = ""


# =============================================================================
# FDA CDS Classifier
# =============================================================================


class FDACDSClassifier:
    """
    FDA Clinical Decision Support Classification Engine.
    
    Evaluates CDS functions against FDA guidance to determine:
    - Whether function qualifies as Non-Device CDS
    - Risk classification (Class I, II, III)
    - Required regulatory pathway
    - Documentation requirements
    """
    
    # Risk weights for scoring
    RISK_WEIGHTS = {
        "time_criticality": {
            "urgent": 0.4,
            "time_sensitive": 0.2,
            "non_urgent": 0.0,
        },
        "reversibility": {
            "irreversible": 0.4,
            "partially_reversible": 0.2,
            "reversible": 0.0,
        },
        "autonomy": {
            "autonomous": 0.5,
            "semi_autonomous": 0.25,
            "advisory": 0.0,
        },
    }
    
    # Function type to base risk mapping
    FUNCTION_RISK_MAP: Dict[CDSFunctionType, CDSRiskLevel] = {
        CDSFunctionType.CLINICAL_GUIDELINES: CDSRiskLevel.MINIMAL,
        CDSFunctionType.DRUG_DRUG_INTERACTION: CDSRiskLevel.LOW,
        CDSFunctionType.DRUG_ALLERGY_CHECK: CDSRiskLevel.LOW,
        CDSFunctionType.LAB_REFERENCE_RANGES: CDSRiskLevel.MINIMAL,
        CDSFunctionType.DOSAGE_CALCULATOR: CDSRiskLevel.MODERATE,
        CDSFunctionType.CLINICAL_REMINDERS: CDSRiskLevel.MINIMAL,
        CDSFunctionType.IMAGE_ANALYSIS: CDSRiskLevel.HIGH,
        CDSFunctionType.DIAGNOSTIC_PREDICTION: CDSRiskLevel.HIGH,
        CDSFunctionType.TREATMENT_RECOMMENDATION: CDSRiskLevel.MODERATE,
        CDSFunctionType.RISK_PREDICTION: CDSRiskLevel.MODERATE,
        CDSFunctionType.AUTONOMOUS_DECISION: CDSRiskLevel.CRITICAL,
    }
    
    def __init__(self) -> None:
        """Initialize the FDA CDS Classifier."""
        self.classification_history: List[CDSAssessment] = []
        logger.info("FDA CDS Classifier initialized")
    
    def classify_function(self, function: CDSFunction) -> CDSAssessment:
        """
        Classify a single CDS function per FDA guidance.
        
        Args:
            function: The CDS function to classify
            
        Returns:
            CDSAssessment with classification results
        """
        logger.info(f"Classifying CDS function: {function.name}")
        
        # Evaluate the 4 FDA criteria
        criteria_met, criteria_rationale = self._evaluate_criteria(function)
        
        # Determine if Non-Device CDS (all 4 criteria met)
        is_non_device = all(criteria_met.values())
        
        # Calculate risk score
        risk_score, risk_factors, mitigating_factors = self._calculate_risk_score(function)
        
        # Determine risk level
        risk_level = self._determine_risk_level(function, risk_score)
        
        # Determine category
        category = self._determine_category(is_non_device, risk_level)
        
        # Determine regulatory pathway
        pathway, docs, controls = self._determine_regulatory_requirements(
            category, risk_level
        )
        
        assessment = CDSAssessment(
            function_id=function.function_id,
            function_name=function.name,
            category=category,
            risk_level=risk_level,
            criteria_met=criteria_met,
            criteria_rationale=criteria_rationale,
            risk_score=risk_score,
            risk_factors=risk_factors,
            mitigating_factors=mitigating_factors,
            regulatory_pathway=pathway,
            required_documentation=docs,
            required_controls=controls,
        )
        
        self.classification_history.append(assessment)
        
        logger.info(
            f"Function '{function.name}' classified as {category.value} "
            f"with risk level {risk_level.value}"
        )
        
        return assessment
    
    def _evaluate_criteria(
        self, function: CDSFunction
    ) -> Tuple[Dict[Criterion, bool], Dict[Criterion, str]]:
        """Evaluate the 4 FDA criteria for Non-Device CDS."""
        
        criteria_met: Dict[Criterion, bool] = {}
        criteria_rationale: Dict[Criterion, str] = {}
        
        # Criterion 1: Not intended for image/signal processing
        criterion_1 = not function.processes_images_signals
        criteria_met[Criterion.NO_IMAGE_SIGNAL_PROCESSING] = criterion_1
        criteria_rationale[Criterion.NO_IMAGE_SIGNAL_PROCESSING] = (
            "Function does not process medical images or signals"
            if criterion_1
            else "Function processes medical images or signals - does not meet criterion"
        )
        
        # Criterion 2: Displays, analyzes, or prints medical information
        criterion_2 = function.function_type in [
            CDSFunctionType.CLINICAL_GUIDELINES,
            CDSFunctionType.LAB_REFERENCE_RANGES,
            CDSFunctionType.DRUG_DRUG_INTERACTION,
            CDSFunctionType.DRUG_ALLERGY_CHECK,
            CDSFunctionType.DOSAGE_CALCULATOR,
            CDSFunctionType.CLINICAL_REMINDERS,
        ]
        criteria_met[Criterion.DISPLAYS_MEDICAL_INFO] = criterion_2
        criteria_rationale[Criterion.DISPLAYS_MEDICAL_INFO] = (
            "Function displays/analyzes medical information for HCP review"
            if criterion_2
            else "Function provides diagnostic/treatment decisions beyond information display"
        )
        
        # Criterion 3: Supports or provides recommendations to HCP
        criterion_3 = function.provides_recommendations and "physician" in [
            u.lower() for u in function.target_users
        ] or "hcp" in [u.lower() for u in function.target_users]
        
        # Also check if target_users includes any healthcare professional
        hcp_keywords = ["physician", "doctor", "nurse", "pharmacist", "hcp", "clinician"]
        has_hcp_user = any(
            any(kw in u.lower() for kw in hcp_keywords)
            for u in function.target_users
        )
        criterion_3 = function.provides_recommendations and has_hcp_user
        criteria_met[Criterion.SUPPORTS_HCP] = criterion_3
        criteria_rationale[Criterion.SUPPORTS_HCP] = (
            "Function provides recommendations to healthcare professionals"
            if criterion_3
            else "Function not primarily intended for HCP use or doesn't provide recommendations"
        )
        
        # Criterion 4: HCP can independently review basis for recommendations
        criterion_4 = function.hcp_can_review_basis and function.requires_hcp_review
        criteria_met[Criterion.HCP_INDEPENDENT_REVIEW] = criterion_4
        criteria_rationale[Criterion.HCP_INDEPENDENT_REVIEW] = (
            "HCP can independently review the basis for all recommendations"
            if criterion_4
            else "HCP cannot fully review recommendation basis (black box or autonomous)"
        )
        
        return criteria_met, criteria_rationale
    
    def _calculate_risk_score(
        self, function: CDSFunction
    ) -> Tuple[float, List[str], List[str]]:
        """Calculate risk score based on function characteristics."""
        
        risk_score = 0.0
        risk_factors: List[str] = []
        mitigating_factors: List[str] = []
        
        # Base risk from function type
        base_risk = self.FUNCTION_RISK_MAP.get(
            function.function_type, CDSRiskLevel.MODERATE
        )
        base_score = {
            CDSRiskLevel.MINIMAL: 0.1,
            CDSRiskLevel.LOW: 0.25,
            CDSRiskLevel.MODERATE: 0.5,
            CDSRiskLevel.HIGH: 0.75,
            CDSRiskLevel.CRITICAL: 1.0,
        }[base_risk]
        risk_score += base_score * 0.4  # 40% weight for base risk
        
        # Time criticality
        time_weight = self.RISK_WEIGHTS["time_criticality"].get(
            function.time_criticality, 0.0
        )
        risk_score += time_weight * 0.2
        if time_weight > 0.2:
            risk_factors.append(f"Time-critical function: {function.time_criticality}")
        
        # Reversibility
        rev_weight = self.RISK_WEIGHTS["reversibility"].get(
            function.reversibility, 0.0
        )
        risk_score += rev_weight * 0.2
        if rev_weight > 0.2:
            risk_factors.append(f"Consequences may be {function.reversibility}")
        
        # Autonomy level
        if not function.requires_hcp_review:
            risk_score += 0.3
            risk_factors.append("Operates without required HCP review")
        
        if not function.hcp_can_review_basis:
            risk_score += 0.2
            risk_factors.append("HCP cannot review recommendation basis")
        
        # Image/signal processing
        if function.processes_images_signals:
            risk_score += 0.15
            risk_factors.append("Processes medical images or signals")
        
        # Mitigating factors
        if function.requires_hcp_review:
            mitigating_factors.append("Requires HCP review before action")
            risk_score -= 0.1
        
        if function.hcp_can_review_basis:
            mitigating_factors.append("Transparent recommendation basis")
            risk_score -= 0.05
        
        if "physician" in [u.lower() for u in function.target_users]:
            mitigating_factors.append("Primary users are licensed physicians")
            risk_score -= 0.05
        
        # Clamp to 0-1 range
        risk_score = max(0.0, min(1.0, risk_score))
        
        return risk_score, risk_factors, mitigating_factors
    
    def _determine_risk_level(
        self, function: CDSFunction, risk_score: float
    ) -> CDSRiskLevel:
        """Determine risk level from score and function type."""
        
        # Start with base risk from function type
        base_risk = self.FUNCTION_RISK_MAP.get(
            function.function_type, CDSRiskLevel.MODERATE
        )
        
        # Adjust based on calculated score
        if risk_score < 0.2:
            return CDSRiskLevel.MINIMAL
        elif risk_score < 0.35:
            return CDSRiskLevel.LOW
        elif risk_score < 0.55:
            return CDSRiskLevel.MODERATE
        elif risk_score < 0.8:
            return CDSRiskLevel.HIGH
        else:
            return CDSRiskLevel.CRITICAL
    
    def _determine_category(
        self, is_non_device: bool, risk_level: CDSRiskLevel
    ) -> CDSCategory:
        """Determine FDA category based on criteria and risk."""
        
        if is_non_device:
            return CDSCategory.NON_DEVICE
        
        # Device classification based on risk
        if risk_level in [CDSRiskLevel.MINIMAL, CDSRiskLevel.LOW]:
            return CDSCategory.DEVICE_CLASS_I
        elif risk_level == CDSRiskLevel.MODERATE:
            return CDSCategory.DEVICE_CLASS_II
        else:
            return CDSCategory.DEVICE_CLASS_III
    
    def _determine_regulatory_requirements(
        self, category: CDSCategory, risk_level: CDSRiskLevel
    ) -> Tuple[str, List[str], List[str]]:
        """Determine regulatory pathway and requirements."""
        
        if category == CDSCategory.NON_DEVICE:
            return (
                "Not FDA regulated as medical device",
                [
                    "Software documentation",
                    "User manual",
                    "Clinical validation evidence",
                ],
                [
                    "Quality management practices",
                    "Change control procedures",
                    "User training materials",
                ],
            )
        
        elif category == CDSCategory.DEVICE_CLASS_I:
            return (
                "Class I - General Controls (usually exempt from 510(k))",
                [
                    "Design history file (DHF)",
                    "Device master record (DMR)",
                    "Software documentation per IEC 62304",
                    "Labeling",
                    "Establishment registration",
                ],
                [
                    "Quality System Regulation (21 CFR 820)",
                    "Medical Device Reporting (MDR)",
                    "Corrections and removals",
                ],
            )
        
        elif category == CDSCategory.DEVICE_CLASS_II:
            return (
                "Class II - 510(k) Premarket Notification Required",
                [
                    "510(k) submission",
                    "Predicate device comparison",
                    "Software documentation (IEC 62304 Level B/C)",
                    "Clinical validation study",
                    "Cybersecurity documentation",
                    "Design history file",
                    "Risk analysis (ISO 14971)",
                ],
                [
                    "Quality System Regulation (21 CFR 820)",
                    "Unique Device Identification (UDI)",
                    "Medical Device Reporting",
                    "Post-market surveillance",
                    "Software validation",
                ],
            )
        
        else:  # Class III
            return (
                "Class III - Premarket Approval (PMA) Required",
                [
                    "PMA application",
                    "Clinical trial data",
                    "Manufacturing information",
                    "Complete software documentation (IEC 62304 Level A)",
                    "Risk management file (ISO 14971)",
                    "Cybersecurity analysis",
                    "Human factors engineering",
                ],
                [
                    "Full Quality System Regulation",
                    "Mandatory MDR reporting",
                    "Annual reports",
                    "Post-approval studies",
                    "Real-world evidence collection",
                ],
            )
    
    def generate_report(
        self,
        system_name: str,
        system_version: str,
        functions: List[CDSFunction],
    ) -> CDSClassificationReport:
        """
        Generate complete classification report for a CDS system.
        
        Args:
            system_name: Name of the CDS system
            system_version: Version of the system
            functions: List of CDS functions to classify
            
        Returns:
            Complete classification report
        """
        logger.info(f"Generating classification report for {system_name} v{system_version}")
        
        assessments = [self.classify_function(f) for f in functions]
        
        # Determine highest risk level
        risk_order = [
            CDSRiskLevel.MINIMAL,
            CDSRiskLevel.LOW,
            CDSRiskLevel.MODERATE,
            CDSRiskLevel.HIGH,
            CDSRiskLevel.CRITICAL,
        ]
        highest_risk = max(
            (a.risk_level for a in assessments),
            key=lambda r: risk_order.index(r),
            default=CDSRiskLevel.MINIMAL,
        )
        
        # Determine overall category (most restrictive)
        category_order = [
            CDSCategory.NON_DEVICE,
            CDSCategory.EXEMPT,
            CDSCategory.DEVICE_CLASS_I,
            CDSCategory.DEVICE_CLASS_II,
            CDSCategory.DEVICE_CLASS_III,
        ]
        overall_category = max(
            (a.category for a in assessments),
            key=lambda c: category_order.index(c),
            default=CDSCategory.NON_DEVICE,
        )
        
        report = CDSClassificationReport(
            system_name=system_name,
            system_version=system_version,
            functions=functions,
            assessments=assessments,
            highest_risk_level=highest_risk,
            overall_category=overall_category,
            fda_compliant=True,  # Assuming compliant if classified
            hipaa_compliant=True,
            requires_510k=overall_category == CDSCategory.DEVICE_CLASS_II,
            requires_pma=overall_category == CDSCategory.DEVICE_CLASS_III,
        )
        
        # Generate report hash
        report.report_hash = hashlib.sha256(
            json.dumps({
                "system": system_name,
                "version": system_version,
                "category": overall_category.value,
                "risk": highest_risk.value,
                "generated": report.generated_at.isoformat(),
            }, sort_keys=True).encode()
        ).hexdigest()
        
        logger.info(
            f"Report generated: {overall_category.value}, "
            f"510(k)={report.requires_510k}, PMA={report.requires_pma}"
        )
        
        return report


# =============================================================================
# Phoenix Guardian CDS Functions Registry
# =============================================================================


def get_phoenix_guardian_cds_functions() -> List[CDSFunction]:
    """
    Define all CDS functions in Phoenix Guardian for classification.
    
    Returns:
        List of CDSFunction definitions for the platform
    """
    return [
        CDSFunction(
            function_id="pg-cds-001",
            name="Drug-Drug Interaction Checker",
            description="Checks prescribed medications against patient's current "
                       "medication list for potential interactions",
            function_type=CDSFunctionType.DRUG_DRUG_INTERACTION,
            inputs=["current_medications", "new_prescription"],
            outputs=["interaction_alerts", "severity_levels", "recommendations"],
            clinical_domain="Pharmacy",
            target_users=["Physician", "Pharmacist", "Nurse"],
            patient_population="All patients",
            time_criticality="time_sensitive",
            reversibility="reversible",
            processes_images_signals=False,
            provides_recommendations=True,
            requires_hcp_review=True,
            hcp_can_review_basis=True,
        ),
        CDSFunction(
            function_id="pg-cds-002",
            name="Drug-Allergy Alert System",
            description="Alerts prescribers when a medication may cause allergic "
                       "reaction based on documented allergies",
            function_type=CDSFunctionType.DRUG_ALLERGY_CHECK,
            inputs=["documented_allergies", "new_prescription"],
            outputs=["allergy_alerts", "cross_sensitivity_warnings"],
            clinical_domain="Pharmacy",
            target_users=["Physician", "Pharmacist"],
            patient_population="All patients",
            time_criticality="urgent",
            reversibility="reversible",
            processes_images_signals=False,
            provides_recommendations=True,
            requires_hcp_review=True,
            hcp_can_review_basis=True,
        ),
        CDSFunction(
            function_id="pg-cds-003",
            name="SOAP Note Generator",
            description="Generates structured SOAP notes from clinical encounter "
                       "transcripts for physician review and editing",
            function_type=CDSFunctionType.CLINICAL_GUIDELINES,
            inputs=["encounter_transcript", "patient_context"],
            outputs=["soap_note_draft", "suggested_diagnoses", "suggested_procedures"],
            clinical_domain="Documentation",
            target_users=["Physician", "Nurse Practitioner"],
            patient_population="All patients",
            time_criticality="non_urgent",
            reversibility="reversible",
            processes_images_signals=False,
            provides_recommendations=True,
            requires_hcp_review=True,
            hcp_can_review_basis=True,
        ),
        CDSFunction(
            function_id="pg-cds-004",
            name="Readmission Risk Predictor",
            description="Predicts 30-day hospital readmission risk to support "
                       "discharge planning decisions",
            function_type=CDSFunctionType.RISK_PREDICTION,
            inputs=["patient_demographics", "diagnoses", "lab_results", "social_factors"],
            outputs=["risk_score", "risk_factors", "intervention_suggestions"],
            clinical_domain="Care Coordination",
            target_users=["Physician", "Care Coordinator", "Discharge Planner"],
            patient_population="Hospitalized patients",
            time_criticality="time_sensitive",
            reversibility="reversible",
            processes_images_signals=False,
            provides_recommendations=True,
            requires_hcp_review=True,
            hcp_can_review_basis=True,  # Model explains contributing factors
        ),
        CDSFunction(
            function_id="pg-cds-005",
            name="Prior Authorization Assistant",
            description="Automates prior authorization documentation gathering "
                       "and submission for physician review",
            function_type=CDSFunctionType.CLINICAL_GUIDELINES,
            inputs=["procedure_code", "diagnosis", "clinical_notes"],
            outputs=["auth_form_draft", "required_documentation", "payer_criteria"],
            clinical_domain="Revenue Cycle",
            target_users=["Physician", "Staff"],
            patient_population="All patients",
            time_criticality="non_urgent",
            reversibility="reversible",
            processes_images_signals=False,
            provides_recommendations=True,
            requires_hcp_review=True,
            hcp_can_review_basis=True,
        ),
        CDSFunction(
            function_id="pg-cds-006",
            name="Dosage Calculator",
            description="Calculates medication dosages based on patient weight, "
                       "age, renal function, and clinical guidelines",
            function_type=CDSFunctionType.DOSAGE_CALCULATOR,
            inputs=["patient_weight", "patient_age", "renal_function", "medication"],
            outputs=["recommended_dose", "dose_range", "adjustment_rationale"],
            clinical_domain="Pharmacy",
            target_users=["Physician", "Pharmacist"],
            patient_population="All patients",
            time_criticality="time_sensitive",
            reversibility="reversible",
            processes_images_signals=False,
            provides_recommendations=True,
            requires_hcp_review=True,
            hcp_can_review_basis=True,
        ),
        CDSFunction(
            function_id="pg-cds-007",
            name="ICD-10 Coding Assistant",
            description="Suggests appropriate ICD-10 codes based on clinical "
                       "documentation for coder review",
            function_type=CDSFunctionType.CLINICAL_GUIDELINES,
            inputs=["clinical_documentation", "procedures_performed"],
            outputs=["suggested_codes", "code_rationale", "documentation_gaps"],
            clinical_domain="Coding",
            target_users=["Physician", "Medical Coder"],
            patient_population="All patients",
            time_criticality="non_urgent",
            reversibility="reversible",
            processes_images_signals=False,
            provides_recommendations=True,
            requires_hcp_review=True,
            hcp_can_review_basis=True,
        ),
        CDSFunction(
            function_id="pg-cds-008",
            name="Sepsis Early Warning",
            description="Monitors vital signs and lab results to alert clinicians "
                       "of potential sepsis for evaluation",
            function_type=CDSFunctionType.RISK_PREDICTION,
            inputs=["vital_signs", "lab_results", "clinical_notes"],
            outputs=["sepsis_risk_score", "qsofa_score", "alert_level"],
            clinical_domain="Critical Care",
            target_users=["Physician", "Nurse", "Rapid Response Team"],
            patient_population="Hospitalized patients",
            time_criticality="urgent",
            reversibility="partially_reversible",
            processes_images_signals=False,
            provides_recommendations=True,
            requires_hcp_review=True,
            hcp_can_review_basis=True,
        ),
    ]


# =============================================================================
# Module Entry Point
# =============================================================================


def classify_phoenix_guardian() -> CDSClassificationReport:
    """
    Classify all Phoenix Guardian CDS functions.
    
    Returns:
        Complete FDA CDS classification report
    """
    classifier = FDACDSClassifier()
    functions = get_phoenix_guardian_cds_functions()
    
    report = classifier.generate_report(
        system_name="Phoenix Guardian",
        system_version="4.0.0",
        functions=functions,
    )
    
    return report


if __name__ == "__main__":
    # Run classification - use logging for production compliance
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    report = classify_phoenix_guardian()
    
    logger.info(f"FDA CDS Classification Report: {report.system_name}")
    logger.info(f"Version: {report.system_version}")
    logger.info(f"Overall Category: {report.overall_category.value}")
    logger.info(f"Highest Risk Level: {report.highest_risk_level.value}")
    logger.info(f"Requires 510(k): {report.requires_510k}")
    logger.info(f"Requires PMA: {report.requires_pma}")
    logger.info(f"Functions Assessed: {len(report.functions)}")
    
    for assessment in report.assessments:
        logger.info(f"  - {assessment.function_name}")
        logger.info(f"    Category: {assessment.category.value}")
        logger.info(f"    Risk Level: {assessment.risk_level.value}")
        criteria_status = "PASS" if all(assessment.criteria_met.values()) else "FAIL"
        logger.info(f"    All 4 Criteria Met: {criteria_status}")
