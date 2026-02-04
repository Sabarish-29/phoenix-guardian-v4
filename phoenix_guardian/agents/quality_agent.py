"""
Clinical Guideline Adherence Agent (QualityAgent)

The QualityAgent checks clinical documentation against evidence-based
guidelines (AHA, ADA, USPSTF, CMS) and flags quality issues, care gaps,
and overutilization.

Supported Guidelines:
- American Heart Association (AHA) - Cardiovascular care
- American Diabetes Association (ADA) - Diabetes management
- USPSTF - Preventive screening guidelines
- CMS Quality Measures - Medicare star ratings
- CDC/IDSA - Antibiotic stewardship
"""

import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

from phoenix_guardian.agents.base_agent import BaseAgent

logger = structlog.get_logger(__name__)


class Severity(Enum):
    """Severity level for quality flags."""
    CRITICAL = "critical"  # Immediate patient safety issue
    HIGH = "high"  # Significant quality gap
    MEDIUM = "medium"  # Moderate issue
    LOW = "low"  # Minor optimization opportunity


class GuidelineSource(Enum):
    """Source of clinical guideline."""
    AHA = "AHA"  # American Heart Association
    ADA = "ADA"  # American Diabetes Association
    USPSTF = "USPSTF"  # US Preventive Services Task Force
    CMS = "CMS"  # Centers for Medicare & Medicaid Services
    CDC = "CDC"  # Centers for Disease Control
    IDSA = "IDSA"  # Infectious Diseases Society of America


class QualityCategory(Enum):
    """Category of quality issue."""
    DIABETES_MANAGEMENT = "diabetes_management"
    HYPERTENSION_MANAGEMENT = "hypertension_management"
    PREVENTIVE_CARE = "preventive_care"
    MEDICATION_SAFETY = "medication_safety"
    ANTIBIOTIC_STEWARDSHIP = "antibiotic_stewardship"
    CHRONIC_DISEASE = "chronic_disease"
    PATIENT_SAFETY = "patient_safety"
    OVERUTILIZATION = "overutilization"


@dataclass
class QualityFlag:
    """Individual quality issue or care gap."""
    severity: Severity
    category: QualityCategory
    guideline: GuidelineSource
    issue: str
    recommendation: str
    reference: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "severity": self.severity.value,
            "category": self.category.value,
            "guideline": self.guideline.value,
            "issue": self.issue,
            "recommendation": self.recommendation,
            "reference": self.reference,
        }


@dataclass
class PatientInfo:
    """Patient demographic and clinical information."""
    age: int
    sex: str  # "M", "F"
    diagnoses: List[str]  # ICD-10 codes
    medications: List[str]
    allergies: List[str] = field(default_factory=list)
    smoking_status: Optional[str] = None  # "current", "former", "never"
    last_visit_date: Optional[date] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class LabResult:
    """Laboratory test result."""
    test_name: str
    value: float
    unit: str
    date: date
    reference_range: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result["date"] = self.date.isoformat() if self.date else None
        return result


@dataclass
class QualityResult:
    """Result of quality assessment."""
    guideline_adherence_score: float  # 0.0 to 1.0
    quality_flags: List[QualityFlag]
    met_guidelines: List[str]
    care_gaps: List[str]
    overutilization_alerts: List[str]
    preventive_care_due: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "guideline_adherence_score": round(self.guideline_adherence_score, 2),
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "met_guidelines": self.met_guidelines,
            "care_gaps": self.care_gaps,
            "overutilization_alerts": self.overutilization_alerts,
            "preventive_care_due": self.preventive_care_due,
        }


class QualityAgent(BaseAgent):
    """
    Clinical guideline adherence agent.
    
    Checks documentation against AHA, ADA, USPSTF, CMS guidelines
    and identifies quality issues, care gaps, and overutilization.
    """
    
    # Diagnosis codes mapping
    DIAGNOSIS_CATEGORIES: Dict[str, List[str]] = {
        "diabetes": ["E10", "E11", "E13"],  # Type 1, Type 2, Other DM
        "hypertension": ["I10", "I11", "I12", "I13", "I15"],
        "hyperlipidemia": ["E78"],
        "ckd": ["N18"],
        "heart_failure": ["I50"],
        "cad": ["I25"],
        "atrial_fibrillation": ["I48"],
        "copd": ["J44"],
        "asthma": ["J45"],
    }
    
    # Medication classes for checking
    MEDICATION_CLASSES: Dict[str, List[str]] = {
        "metformin": ["metformin"],
        "sglt2": ["empagliflozin", "dapagliflozin", "canagliflozin", "ertugliflozin", "jardiance", "farxiga", "invokana"],
        "glp1": ["semaglutide", "liraglutide", "dulaglutide", "tirzepatide", "ozempic", "trulicity", "wegovy", "mounjaro"],
        "ace_inhibitor": ["lisinopril", "enalapril", "ramipril", "benazepril", "captopril", "quinapril", "fosinopril"],
        "arb": ["losartan", "valsartan", "irbesartan", "olmesartan", "telmisartan", "candesartan"],
        "statin": ["atorvastatin", "rosuvastatin", "simvastatin", "pravastatin", "lovastatin", "lipitor", "crestor"],
        "ccb": ["amlodipine", "diltiazem", "verapamil", "nifedipine", "norvasc"],
        "thiazide": ["hydrochlorothiazide", "hctz", "chlorthalidone", "indapamide"],
        "beta_blocker": ["metoprolol", "carvedilol", "bisoprolol", "atenolol", "propranolol"],
        "benzodiazepine": ["lorazepam", "diazepam", "alprazolam", "clonazepam", "temazepam", "ativan", "xanax", "valium"],
        "nsaid": ["ibuprofen", "naproxen", "meloxicam", "diclofenac", "celecoxib", "advil", "aleve", "celebrex"],
        "anticholinergic": ["diphenhydramine", "benadryl", "oxybutynin", "tolterodine", "hydroxyzine"],
        "opioid": ["oxycodone", "hydrocodone", "morphine", "tramadol", "fentanyl", "codeine"],
        "antibiotic": ["amoxicillin", "azithromycin", "ciprofloxacin", "levofloxacin", "doxycycline", "nitrofurantoin", "cephalexin"],
    }
    
    # Preventive care schedules (age ranges and frequency in days)
    PREVENTIVE_SCHEDULES: Dict[str, Dict[str, Any]] = {
        "diabetic_eye_exam": {
            "condition": "diabetes",
            "frequency_days": 365,
            "description": "Annual dilated retinal exam",
            "reference": "ADA 2024 Standards of Care",
        },
        "diabetic_foot_exam": {
            "condition": "diabetes",
            "frequency_days": 365,
            "description": "Annual comprehensive foot exam",
            "reference": "ADA 2024 Standards of Care",
        },
        "mammography": {
            "sex": "F",
            "min_age": 50,
            "max_age": 74,
            "frequency_days": 730,  # Biennial
            "description": "Breast cancer screening",
            "reference": "USPSTF Breast Cancer Screening",
        },
        "colonoscopy": {
            "min_age": 45,
            "max_age": 75,
            "frequency_days": 3650,  # Every 10 years
            "description": "Colorectal cancer screening",
            "reference": "USPSTF Colorectal Cancer Screening",
        },
        "cervical_cancer_screening": {
            "sex": "F",
            "min_age": 21,
            "max_age": 65,
            "frequency_days": 1095,  # Every 3 years for Pap alone
            "description": "Pap smear/cervical cancer screening",
            "reference": "USPSTF Cervical Cancer Screening",
        },
        "lung_cancer_screening": {
            "min_age": 50,
            "max_age": 80,
            "smoking_required": True,
            "frequency_days": 365,
            "description": "Low-dose CT for lung cancer",
            "reference": "USPSTF Lung Cancer Screening",
        },
    }
    
    # Beers Criteria - high-risk medications in elderly
    BEERS_CRITERIA: Dict[str, Dict[str, Any]] = {
        "benzodiazepine": {
            "min_age": 65,
            "severity": Severity.HIGH,
            "issue": "Benzodiazepines increase risk of falls, fractures, and cognitive impairment in elderly",
            "recommendation": "Consider tapering and discontinuing. Use non-pharmacologic alternatives for insomnia/anxiety.",
        },
        "anticholinergic": {
            "min_age": 65,
            "severity": Severity.MEDIUM,
            "issue": "Anticholinergic medications increase risk of delirium and cognitive decline in elderly",
            "recommendation": "Discontinue if possible. Use alternatives with lower anticholinergic burden.",
        },
        "nsaid": {
            "min_age": 65,
            "severity": Severity.MEDIUM,
            "issue": "NSAIDs increase risk of GI bleeding, renal injury, and cardiovascular events in elderly",
            "recommendation": "Use acetaminophen as first-line for pain. If NSAID needed, use lowest effective dose for shortest duration.",
        },
    }
    
    def __init__(self, **kwargs: Any) -> None:
        """Initialize QualityAgent."""
        super().__init__(name="Quality", **kwargs)
        logger.info("QualityAgent initialized")
    
    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check clinical quality and guideline adherence.
        
        Args:
            context: Must contain:
                - 'patient' (dict): Patient demographics and diagnoses
                - 'labs' (list, optional): Lab results
                - 'last_preventive_care' (dict, optional): Last preventive services
                - 'encounter_date' (str, optional): Current encounter date
        
        Returns:
            Dict with QualityResult data and reasoning
        """
        start_time = time.perf_counter()
        
        # Parse patient info
        patient_data = context.get("patient", {})
        if not patient_data:
            raise ValueError("Patient information is required for guideline checking")
        
        age = patient_data.get("age")
        sex = patient_data.get("sex")
        
        if age is None or sex is None:
            raise ValueError("Patient age and sex required for guideline checking")
        
        patient = PatientInfo(
            age=age,
            sex=sex.upper() if sex else "U",
            diagnoses=patient_data.get("diagnoses", []),
            medications=patient_data.get("medications", []),
            allergies=patient_data.get("allergies", []),
            smoking_status=patient_data.get("smoking_status"),
            last_visit_date=self._parse_date(patient_data.get("last_visit_date")),
        )
        
        # Parse labs
        labs = self._parse_labs(context.get("labs", []))
        
        # Parse preventive care dates
        last_preventive = context.get("last_preventive_care", {})
        
        # Parse encounter date
        encounter_date_str = context.get("encounter_date")
        encounter_date = self._parse_date(encounter_date_str) or date.today()
        
        # Initialize results
        quality_flags: List[QualityFlag] = []
        met_guidelines: List[str] = []
        care_gaps: List[str] = []
        overutilization_alerts: List[str] = []
        preventive_care_due: List[Dict[str, Any]] = []
        
        # Check if patient has chronic diseases
        has_diabetes = self._has_diagnosis(patient.diagnoses, "diabetes")
        has_hypertension = self._has_diagnosis(patient.diagnoses, "hypertension")
        has_ckd = self._has_diagnosis(patient.diagnoses, "ckd")
        has_cvd = self._has_diagnosis(patient.diagnoses, "cad") or self._has_diagnosis(patient.diagnoses, "heart_failure")
        
        # Check diabetes guidelines
        if has_diabetes:
            dm_flags, dm_met = self._check_diabetes_guidelines(patient, labs, encounter_date)
            quality_flags.extend(dm_flags)
            met_guidelines.extend(dm_met)
            
            # Check diabetes preventive care
            dm_gaps, dm_preventive = self._check_diabetes_preventive_care(
                patient, last_preventive, encounter_date
            )
            care_gaps.extend(dm_gaps)
            preventive_care_due.extend(dm_preventive)
        
        # Check hypertension guidelines
        if has_hypertension:
            htn_flags, htn_met = self._check_hypertension_guidelines(
                patient, labs, has_diabetes, encounter_date
            )
            quality_flags.extend(htn_flags)
            met_guidelines.extend(htn_met)
        
        # Check general preventive care (screening)
        general_gaps, general_preventive = self._check_preventive_care(
            patient, last_preventive, encounter_date
        )
        care_gaps.extend(general_gaps)
        preventive_care_due.extend(general_preventive)
        
        # Check medication safety
        safety_flags = self._check_medication_safety(patient, labs)
        quality_flags.extend(safety_flags)
        
        if not safety_flags:
            met_guidelines.append("No medication safety concerns identified")
        
        # Check for overutilization
        overutilization = self._check_overutilization(context, labs, encounter_date)
        overutilization_alerts.extend(overutilization)
        
        # Calculate adherence score
        adherence_score = self._calculate_adherence_score(
            quality_flags, met_guidelines, care_gaps, patient.diagnoses
        )
        
        # Build result
        result = QualityResult(
            guideline_adherence_score=adherence_score,
            quality_flags=quality_flags,
            met_guidelines=met_guidelines,
            care_gaps=care_gaps,
            overutilization_alerts=overutilization_alerts,
            preventive_care_due=preventive_care_due,
        )
        
        # Build reasoning
        reasoning = self._build_reasoning(
            patient, has_diabetes, has_hypertension, quality_flags,
            met_guidelines, care_gaps, adherence_score
        )
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            "Quality check complete",
            patient_age=patient.age,
            adherence_score=f"{adherence_score:.2f}",
            quality_flags=len(quality_flags),
            care_gaps=len(care_gaps),
            processing_time_ms=f"{processing_time:.2f}",
        )
        
        return {
            "data": result.to_dict(),
            "reasoning": reasoning,
        }
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string flexibly."""
        if not date_str:
            return None
        
        formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        return None
    
    def _parse_labs(self, labs_data: List[Dict[str, Any]]) -> List[LabResult]:
        """Parse lab data into LabResult objects."""
        labs = []
        for lab in labs_data:
            try:
                lab_date = self._parse_date(lab.get("date"))
                if lab_date is None:
                    lab_date = date.today()
                
                labs.append(LabResult(
                    test_name=lab.get("test_name", ""),
                    value=float(lab.get("value", 0)),
                    unit=lab.get("unit", ""),
                    date=lab_date,
                    reference_range=lab.get("reference_range"),
                ))
            except (ValueError, TypeError):
                continue
        
        return labs
    
    def _has_diagnosis(self, diagnoses: List[str], category: str) -> bool:
        """Check if patient has diagnosis in category."""
        prefixes = self.DIAGNOSIS_CATEGORIES.get(category, [])
        return any(
            any(dx.upper().startswith(prefix) for prefix in prefixes)
            for dx in diagnoses
        )
    
    def _is_on_medication(self, medications: List[str], drug_class: str) -> bool:
        """Check if patient is on medication from drug class."""
        drug_names = self.MEDICATION_CLASSES.get(drug_class, [])
        meds_lower = " ".join(medications).lower()
        return any(drug in meds_lower for drug in drug_names)
    
    def _get_lab_value(self, labs: List[LabResult], test_name: str) -> Optional[LabResult]:
        """Get most recent lab result for test."""
        matching = [
            lab for lab in labs
            if test_name.lower() in lab.test_name.lower()
        ]
        if not matching:
            return None
        
        return max(matching, key=lambda x: x.date)
    
    def _check_diabetes_guidelines(
        self,
        patient: PatientInfo,
        labs: List[LabResult],
        encounter_date: date,
    ) -> Tuple[List[QualityFlag], List[str]]:
        """Check ADA diabetes guidelines."""
        flags: List[QualityFlag] = []
        met: List[str] = []
        
        # Determine HbA1c goal based on patient characteristics
        if patient.age >= 65:
            hba1c_goal = 8.0
            goal_description = "<8% (relaxed for elderly)"
        else:
            hba1c_goal = 7.0
            goal_description = "<7% for most adults"
        
        # Check HbA1c
        hba1c = self._get_lab_value(labs, "hba1c")
        if hba1c:
            if hba1c.value > hba1c_goal:
                flags.append(QualityFlag(
                    severity=Severity.HIGH,
                    category=QualityCategory.DIABETES_MANAGEMENT,
                    guideline=GuidelineSource.ADA,
                    issue=f"HbA1c {hba1c.value}% indicates poor glycemic control (goal {goal_description})",
                    recommendation="Intensify diabetes therapy. Consider adding GLP-1 agonist or SGLT2 inhibitor. Refer to diabetes educator.",
                    reference="ADA 2024 Standards of Care - Glycemic Targets",
                ))
            else:
                met.append(f"HbA1c at goal ({hba1c.value}% < {hba1c_goal}%)")
            
            # Check if HbA1c is recent (within 6 months)
            days_since_hba1c = (encounter_date - hba1c.date).days
            if days_since_hba1c <= 180:
                met.append("HbA1c checked within past 6 months")
        else:
            flags.append(QualityFlag(
                severity=Severity.MEDIUM,
                category=QualityCategory.DIABETES_MANAGEMENT,
                guideline=GuidelineSource.ADA,
                issue="No recent HbA1c result available",
                recommendation="Order HbA1c to assess glycemic control",
                reference="ADA 2024 Standards of Care",
            ))
        
        # Check LDL for diabetes patients
        ldl = self._get_lab_value(labs, "ldl")
        has_cvd = self._has_diagnosis(patient.diagnoses, "cad")
        ldl_goal = 70 if has_cvd else 100
        
        if ldl:
            if ldl.value <= ldl_goal:
                met.append(f"LDL cholesterol at goal ({ldl.value} mg/dL < {ldl_goal} mg/dL for diabetes)")
            else:
                flags.append(QualityFlag(
                    severity=Severity.MEDIUM,
                    category=QualityCategory.DIABETES_MANAGEMENT,
                    guideline=GuidelineSource.ADA,
                    issue=f"LDL {ldl.value} mg/dL above goal of <{ldl_goal} mg/dL for diabetes {'with CVD' if has_cvd else 'patients'}",
                    recommendation="Intensify statin therapy or add ezetimibe if on maximally tolerated statin",
                    reference="ADA 2024 Standards of Care - Lipid Management",
                ))
        
        # Check medications
        on_metformin = self._is_on_medication(patient.medications, "metformin")
        on_statin = self._is_on_medication(patient.medications, "statin")
        on_ace_arb = (
            self._is_on_medication(patient.medications, "ace_inhibitor") or
            self._is_on_medication(patient.medications, "arb")
        )
        on_sglt2 = self._is_on_medication(patient.medications, "sglt2")
        on_glp1 = self._is_on_medication(patient.medications, "glp1")
        
        if on_metformin:
            met.append("Patient on appropriate first-line diabetes medication (Metformin)")
        else:
            # Check if contraindicated
            egfr = self._get_lab_value(labs, "egfr")
            if egfr and egfr.value < 30:
                met.append("Metformin appropriately avoided (eGFR <30)")
            else:
                flags.append(QualityFlag(
                    severity=Severity.MEDIUM,
                    category=QualityCategory.DIABETES_MANAGEMENT,
                    guideline=GuidelineSource.ADA,
                    issue="Patient with diabetes not on Metformin (first-line therapy)",
                    recommendation="Start Metformin unless contraindicated (eGFR <30, unstable heart failure)",
                    reference="ADA 2024 Standards of Care - Pharmacologic Therapy",
                ))
        
        if on_statin:
            met.append("Patient on statin for cardiovascular risk reduction")
        elif patient.age >= 40:
            flags.append(QualityFlag(
                severity=Severity.MEDIUM,
                category=QualityCategory.DIABETES_MANAGEMENT,
                guideline=GuidelineSource.ADA,
                issue="Diabetes patient age 40+ not on statin therapy",
                recommendation="Start moderate-to-high intensity statin for cardiovascular risk reduction",
                reference="ADA 2024 Standards of Care - Lipid Management",
            ))
        
        if on_ace_arb:
            met.append("Patient on ACE inhibitor or ARB for diabetic nephropathy prevention")
        
        # Check for SGLT2/GLP-1 in patients with CKD or CVD
        has_ckd = self._has_diagnosis(patient.diagnoses, "ckd")
        has_hf = self._has_diagnosis(patient.diagnoses, "heart_failure")
        
        if (has_ckd or has_cvd or has_hf) and not on_sglt2:
            egfr = self._get_lab_value(labs, "egfr")
            if egfr:
                flags.append(QualityFlag(
                    severity=Severity.LOW,
                    category=QualityCategory.CHRONIC_DISEASE,
                    guideline=GuidelineSource.ADA,
                    issue=f"Patient with diabetes and {'CKD' if has_ckd else 'CVD'} (eGFR {egfr.value}) - consider SGLT2 inhibitor",
                    recommendation="Consider adding SGLT2 inhibitor (empagliflozin, dapagliflozin) for cardiovascular and renal benefits",
                    reference="ADA 2024 - CKD and Diabetes Management",
                ))
        
        return flags, met
    
    def _check_diabetes_preventive_care(
        self,
        patient: PatientInfo,
        last_preventive: Dict[str, str],
        encounter_date: date,
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Check diabetes-specific preventive care."""
        gaps: List[str] = []
        due: List[Dict[str, Any]] = []
        
        # Eye exam
        eye_exam_str = last_preventive.get("diabetic_eye_exam")
        eye_exam_date = self._parse_date(eye_exam_str)
        
        if eye_exam_date:
            days_since = (encounter_date - eye_exam_date).days
            if days_since > 365:
                gaps.append(f"Annual diabetic eye exam (overdue by {days_since - 365} days)")
                due.append({
                    "service": "Diabetic eye exam",
                    "due_date": (eye_exam_date + timedelta(days=365)).isoformat(),
                    "status": "overdue",
                    "priority": "high",
                })
        else:
            gaps.append("Diabetic eye exam - no record found")
            due.append({
                "service": "Diabetic eye exam",
                "due_date": "unknown",
                "status": "overdue",
                "priority": "high",
            })
        
        # Foot exam
        foot_exam_str = last_preventive.get("diabetic_foot_exam")
        foot_exam_date = self._parse_date(foot_exam_str)
        
        if foot_exam_date:
            days_since = (encounter_date - foot_exam_date).days
            if days_since > 365:
                gaps.append(f"Annual diabetic foot exam (overdue by {days_since - 365} days)")
                due.append({
                    "service": "Diabetic foot exam",
                    "due_date": (foot_exam_date + timedelta(days=365)).isoformat(),
                    "status": "overdue",
                    "priority": "medium",
                })
        
        return gaps, due
    
    def _check_hypertension_guidelines(
        self,
        patient: PatientInfo,
        labs: List[LabResult],
        has_diabetes: bool,
        encounter_date: date,
    ) -> Tuple[List[QualityFlag], List[str]]:
        """Check AHA hypertension guidelines."""
        flags: List[QualityFlag] = []
        met: List[str] = []
        
        # Determine BP goal
        if patient.age >= 65:
            systolic_goal = 140
            diastolic_goal = 90
            goal_description = "<140/90 mmHg (relaxed for elderly)"
        elif has_diabetes:
            systolic_goal = 130
            diastolic_goal = 80
            goal_description = "<130/80 mmHg (for diabetes patients)"
        else:
            systolic_goal = 130
            diastolic_goal = 80
            goal_description = "<130/80 mmHg"
        
        # Get BP values
        systolic = self._get_lab_value(labs, "bp_systolic") or self._get_lab_value(labs, "systolic")
        diastolic = self._get_lab_value(labs, "bp_diastolic") or self._get_lab_value(labs, "diastolic")
        
        if systolic and diastolic:
            bp_at_goal = systolic.value < systolic_goal and diastolic.value < diastolic_goal
            
            if bp_at_goal:
                met.append(f"Blood pressure at goal ({systolic.value}/{diastolic.value} < {systolic_goal}/{diastolic_goal} mmHg)")
            else:
                flags.append(QualityFlag(
                    severity=Severity.MEDIUM if systolic.value < 160 else Severity.HIGH,
                    category=QualityCategory.HYPERTENSION_MANAGEMENT,
                    guideline=GuidelineSource.AHA,
                    issue=f"Blood pressure {systolic.value}/{diastolic.value} mmHg above goal of {goal_description}",
                    recommendation="Uptitrate current antihypertensive or add second agent. Consider ACE-I/ARB, CCB, or thiazide.",
                    reference="AHA 2023 Hypertension Guidelines",
                ))
        
        # Check medications
        on_ace_arb = (
            self._is_on_medication(patient.medications, "ace_inhibitor") or
            self._is_on_medication(patient.medications, "arb")
        )
        on_ccb = self._is_on_medication(patient.medications, "ccb")
        on_thiazide = self._is_on_medication(patient.medications, "thiazide")
        on_beta_blocker = self._is_on_medication(patient.medications, "beta_blocker")
        
        on_any_antihypertensive = on_ace_arb or on_ccb or on_thiazide or on_beta_blocker
        
        if on_any_antihypertensive:
            med_names = []
            if on_ace_arb:
                med_names.append("ACE-I/ARB")
            if on_ccb:
                med_names.append("CCB")
            if on_thiazide:
                med_names.append("Thiazide")
            if on_beta_blocker:
                med_names.append("Beta-blocker")
            
            met.append(f"Patient on appropriate antihypertensive therapy ({', '.join(med_names)})")
        else:
            flags.append(QualityFlag(
                severity=Severity.MEDIUM,
                category=QualityCategory.HYPERTENSION_MANAGEMENT,
                guideline=GuidelineSource.AHA,
                issue="Patient with hypertension not on antihypertensive medication",
                recommendation="Start first-line antihypertensive: ACE-I/ARB (if diabetes/CKD), CCB, or thiazide",
                reference="AHA 2023 Hypertension Guidelines",
            ))
        
        return flags, met
    
    def _check_preventive_care(
        self,
        patient: PatientInfo,
        last_preventive: Dict[str, str],
        encounter_date: date,
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Check USPSTF preventive care guidelines."""
        gaps: List[str] = []
        due: List[Dict[str, Any]] = []
        
        # Mammography (women 50-74, biennial)
        if patient.sex == "F" and 50 <= patient.age <= 74:
            mammo_str = last_preventive.get("mammography")
            mammo_date = self._parse_date(mammo_str)
            
            if mammo_date:
                days_since = (encounter_date - mammo_date).days
                if days_since > 730:  # 2 years
                    gaps.append(f"Mammography screening (overdue by {days_since - 730} days)")
                    due.append({
                        "service": "Mammography",
                        "due_date": (mammo_date + timedelta(days=730)).isoformat(),
                        "status": "overdue",
                        "priority": "medium",
                    })
            else:
                gaps.append("Mammography screening - no record found")
                due.append({
                    "service": "Mammography",
                    "due_date": "unknown",
                    "status": "overdue",
                    "priority": "medium",
                })
        
        # Colonoscopy (age 45-75, every 10 years)
        if 45 <= patient.age <= 75:
            colonoscopy_str = last_preventive.get("colonoscopy")
            colonoscopy_date = self._parse_date(colonoscopy_str)
            
            if colonoscopy_date:
                days_since = (encounter_date - colonoscopy_date).days
                if days_since > 3650:  # 10 years
                    gaps.append(f"Colonoscopy (overdue by {(days_since - 3650) // 365} years)")
                    due.append({
                        "service": "Colonoscopy",
                        "due_date": (colonoscopy_date + timedelta(days=3650)).isoformat(),
                        "status": "overdue",
                        "priority": "medium",
                    })
            else:
                gaps.append("Colonoscopy - no record found")
                due.append({
                    "service": "Colonoscopy",
                    "due_date": "unknown",
                    "status": "overdue",
                    "priority": "medium",
                })
        
        # Lung cancer screening (smokers age 50-80)
        if (patient.smoking_status in ["current", "former"] and 
            50 <= patient.age <= 80):
            lung_screen_str = last_preventive.get("lung_cancer_screening")
            lung_screen_date = self._parse_date(lung_screen_str)
            
            if lung_screen_date:
                days_since = (encounter_date - lung_screen_date).days
                if days_since > 365:
                    gaps.append("Annual low-dose CT lung cancer screening (for smokers)")
            else:
                gaps.append("Lung cancer screening - consider for smoking history")
        
        # Influenza vaccine (check season)
        flu_str = last_preventive.get("influenza_vaccine")
        flu_date = self._parse_date(flu_str)
        
        # Flu season is roughly Oct-Mar
        if encounter_date.month >= 9 or encounter_date.month <= 3:
            current_season_start = date(
                encounter_date.year if encounter_date.month >= 9 else encounter_date.year - 1,
                9, 1
            )
            
            if not flu_date or flu_date < current_season_start:
                gaps.append("Influenza vaccine (current season)")
                due.append({
                    "service": "Influenza vaccine",
                    "due_date": current_season_start.isoformat(),
                    "status": "due",
                    "priority": "low",
                })
        
        # Pneumococcal vaccine (age >65)
        if patient.age >= 65:
            pneumo_str = last_preventive.get("pneumococcal_vaccine")
            if not pneumo_str:
                gaps.append("Pneumococcal vaccine (PCV20) - recommended for age 65+")
                due.append({
                    "service": "Pneumococcal vaccine",
                    "due_date": "due now",
                    "status": "due",
                    "priority": "low",
                })
        
        return gaps, due
    
    def _check_medication_safety(
        self,
        patient: PatientInfo,
        labs: List[LabResult],
    ) -> List[QualityFlag]:
        """Check for medication safety issues."""
        flags: List[QualityFlag] = []
        
        # Check Beers Criteria for elderly
        for drug_class, criteria in self.BEERS_CRITERIA.items():
            if patient.age >= criteria["min_age"] and self._is_on_medication(patient.medications, drug_class):
                flags.append(QualityFlag(
                    severity=criteria["severity"],
                    category=QualityCategory.MEDICATION_SAFETY,
                    guideline=GuidelineSource.CMS,
                    issue=criteria["issue"],
                    recommendation=criteria["recommendation"],
                    reference="AGS Beers Criteria 2023",
                ))
        
        # Check renal dosing
        egfr = self._get_lab_value(labs, "egfr")
        if egfr and egfr.value < 30:
            if self._is_on_medication(patient.medications, "metformin"):
                flags.append(QualityFlag(
                    severity=Severity.CRITICAL,
                    category=QualityCategory.MEDICATION_SAFETY,
                    guideline=GuidelineSource.ADA,
                    issue=f"Metformin contraindicated with eGFR {egfr.value} (<30 mL/min)",
                    recommendation="Discontinue Metformin. Consider alternative diabetes therapy (GLP-1, SGLT2 if eGFR >25).",
                    reference="FDA Metformin Label",
                ))
        
        if egfr and egfr.value < 60:
            if self._is_on_medication(patient.medications, "nsaid"):
                flags.append(QualityFlag(
                    severity=Severity.HIGH,
                    category=QualityCategory.MEDICATION_SAFETY,
                    guideline=GuidelineSource.CMS,
                    issue=f"NSAIDs should be avoided with eGFR {egfr.value} (<60) due to nephrotoxicity",
                    recommendation="Discontinue NSAIDs. Use acetaminophen for pain management.",
                    reference="KDIGO CKD Guidelines",
                ))
        
        # Check for ACE-I + ARB combination (dangerous)
        on_ace = self._is_on_medication(patient.medications, "ace_inhibitor")
        on_arb = self._is_on_medication(patient.medications, "arb")
        
        if on_ace and on_arb:
            flags.append(QualityFlag(
                severity=Severity.HIGH,
                category=QualityCategory.MEDICATION_SAFETY,
                guideline=GuidelineSource.AHA,
                issue="Concurrent ACE inhibitor and ARB increases risk of hyperkalemia and acute kidney injury",
                recommendation="Discontinue one agent. Use either ACE-I OR ARB, not both.",
                reference="AHA/ACC Heart Failure Guidelines",
            ))
        
        return flags
    
    def _check_overutilization(
        self,
        context: Dict[str, Any],
        labs: List[LabResult],
        encounter_date: date,
    ) -> List[str]:
        """Check for overutilization and low-value care."""
        alerts: List[str] = []
        
        # Check for duplicate labs
        lab_dates: Dict[str, List[date]] = {}
        for lab in labs:
            test = lab.test_name.lower()
            if test not in lab_dates:
                lab_dates[test] = []
            lab_dates[test].append(lab.date)
        
        for test, dates in lab_dates.items():
            if len(dates) >= 2:
                dates.sort()
                for i in range(1, len(dates)):
                    days_between = (dates[i] - dates[i-1]).days
                    if days_between <= 7 and test not in ["bp_systolic", "bp_diastolic"]:
                        alerts.append(f"Duplicate {test} ordered within {days_between} days")
        
        # Check for inappropriate imaging from context
        orders = context.get("orders", [])
        for order in orders:
            order_lower = str(order).lower()
            
            # MRI lumbar for acute back pain without red flags
            if "mri" in order_lower and "lumbar" in order_lower:
                # Would need duration of symptoms to properly evaluate
                pass
            
            # Preoperative chest X-ray in asymptomatic patient
            if "chest x-ray" in order_lower and "preoperative" in order_lower:
                alerts.append("Preoperative chest X-ray may be unnecessary for asymptomatic, low-risk patients")
        
        return alerts
    
    def _calculate_adherence_score(
        self,
        flags: List[QualityFlag],
        met_guidelines: List[str],
        care_gaps: List[str],
        diagnoses: List[str],
    ) -> float:
        """Calculate overall guideline adherence score (0.0-1.0)."""
        # Start with base score
        score = 1.0
        
        # Deduct for quality flags based on severity
        for flag in flags:
            if flag.severity == Severity.CRITICAL:
                score -= 0.20
            elif flag.severity == Severity.HIGH:
                score -= 0.10
            elif flag.severity == Severity.MEDIUM:
                score -= 0.05
            elif flag.severity == Severity.LOW:
                score -= 0.02
        
        # Deduct for care gaps
        score -= len(care_gaps) * 0.03
        
        # Bonus for met guidelines
        score += len(met_guidelines) * 0.02
        
        # If no chronic diseases, base score should remain high
        has_chronic = any(
            self._has_diagnosis(diagnoses, cat)
            for cat in ["diabetes", "hypertension", "ckd", "heart_failure", "cad"]
        )
        
        if not has_chronic and not diagnoses:
            score = max(score, 0.90)
        
        # Clamp to valid range
        return max(0.0, min(1.0, score))
    
    def _build_reasoning(
        self,
        patient: PatientInfo,
        has_diabetes: bool,
        has_hypertension: bool,
        flags: List[QualityFlag],
        met_guidelines: List[str],
        care_gaps: List[str],
        adherence_score: float,
    ) -> str:
        """Build human-readable reasoning."""
        parts = []
        
        # Patient summary
        conditions = []
        if has_diabetes:
            conditions.append("diabetes")
        if has_hypertension:
            conditions.append("hypertension")
        
        if conditions:
            parts.append(f"Patient with {', '.join(conditions)}.")
        
        # Key issues
        high_severity = [f for f in flags if f.severity in [Severity.CRITICAL, Severity.HIGH]]
        if high_severity:
            issues = [f.issue.split("(")[0].strip() for f in high_severity[:3]]
            parts.append(f"Key issues: {'; '.join(issues)}.")
        
        # Positive findings
        if met_guidelines:
            parts.append(f"Positive findings: {len(met_guidelines)} guidelines met.")
        
        # Care gaps
        if care_gaps:
            parts.append(f"Care gaps identified: {len(care_gaps)}.")
        
        # Score interpretation
        if adherence_score >= 0.8:
            interpretation = "Good adherence to clinical guidelines."
        elif adherence_score >= 0.6:
            interpretation = "Moderate adherence with room for improvement."
        else:
            interpretation = "Multiple guideline gaps requiring attention."
        
        parts.append(f"Guideline adherence score {adherence_score:.2f}/1.0. {interpretation}")
        
        return " ".join(parts)
