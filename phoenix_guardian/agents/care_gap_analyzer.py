"""
Care Gap Analyzer.

Identifies gaps in patient care based on:
1. USPSTF screening guidelines
2. HEDIS quality measures
3. Chronic disease management protocols
4. Preventive care schedules

SUPPORTED MEASURES:
    BCS - Breast Cancer Screening (Mammogram)
    COL - Colorectal Cancer Screening (Colonoscopy/FIT)
    CCS - Cervical Cancer Screening (Pap/HPV)
    DCA - Diabetes Care - A1c Testing
    DCE - Diabetes Care - Eye Exam
    DCN - Diabetes Care - Nephropathy Screening
    CBP - Controlling Blood Pressure
    IMA - Immunizations for Adolescents
    FLU - Flu Vaccine
    PNE - Pneumonia Vaccine
    AWC - Adolescent Well-Care Visit
    W34 - Well-Child Visits 3-6 years
    AMM - Antidepressant Medication Management
    DEP - Screening for Depression

EVIDENCE GRADING (USPSTF):
    A - Strongly recommends (high certainty of substantial benefit)
    B - Recommends (high certainty of moderate benefit)
    C - Selectively offer (net benefit is small)
    D - Recommends against
    I - Insufficient evidence
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import date, datetime, timedelta
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


@dataclass
class ScreeningGuideline:
    """
    Represents a clinical screening guideline.
    """
    measure_id: str
    measure_name: str
    description: str
    
    # Eligibility criteria
    min_age: int
    max_age: int
    gender: Optional[str] = None  # "M", "F", or None for all
    conditions: List[str] = field(default_factory=list)  # Required conditions
    exclusions: List[str] = field(default_factory=list)  # Exclusion conditions
    
    # Frequency
    interval_months: int = 12
    
    # Evidence
    evidence_grade: str = "B"
    source: str = "USPSTF"
    
    # Quality programs
    hedis_measure: bool = True
    mips_measure: bool = True
    stars_measure: bool = False


# USPSTF and HEDIS Screening Guidelines
SCREENING_GUIDELINES = {
    "BCS": ScreeningGuideline(
        measure_id="BCS",
        measure_name="Breast Cancer Screening",
        description="Mammogram for breast cancer screening",
        min_age=50,
        max_age=74,
        gender="F",
        interval_months=24,  # Every 2 years
        evidence_grade="B",
        source="USPSTF",
        hedis_measure=True,
        mips_measure=True,
        stars_measure=True
    ),
    "COL": ScreeningGuideline(
        measure_id="COL",
        measure_name="Colorectal Cancer Screening",
        description="Colonoscopy, FIT, or stool DNA test for colorectal cancer",
        min_age=45,
        max_age=75,
        gender=None,  # Both
        interval_months=120,  # 10 years for colonoscopy
        evidence_grade="A",
        source="USPSTF",
        hedis_measure=True,
        mips_measure=True,
        stars_measure=True
    ),
    "CCS": ScreeningGuideline(
        measure_id="CCS",
        measure_name="Cervical Cancer Screening",
        description="Pap smear and/or HPV testing",
        min_age=21,
        max_age=65,
        gender="F",
        interval_months=36,  # Every 3 years (Pap alone) or 5 years (Pap+HPV)
        evidence_grade="A",
        source="USPSTF",
        hedis_measure=True,
        mips_measure=True,
        stars_measure=True
    ),
    "DCA": ScreeningGuideline(
        measure_id="DCA",
        measure_name="Diabetes Care - A1c Testing",
        description="Hemoglobin A1c testing for diabetic patients",
        min_age=18,
        max_age=75,
        gender=None,
        conditions=["diabetes"],
        interval_months=6,  # Every 6 months
        evidence_grade="A",
        source="ADA/HEDIS",
        hedis_measure=True,
        mips_measure=True,
        stars_measure=True
    ),
    "DCE": ScreeningGuideline(
        measure_id="DCE",
        measure_name="Diabetes Care - Eye Exam",
        description="Dilated eye exam for diabetic retinopathy",
        min_age=18,
        max_age=75,
        gender=None,
        conditions=["diabetes"],
        interval_months=12,
        evidence_grade="A",
        source="ADA/HEDIS",
        hedis_measure=True,
        mips_measure=True
    ),
    "DCN": ScreeningGuideline(
        measure_id="DCN",
        measure_name="Diabetes Care - Nephropathy Screening",
        description="Urine albumin or nephropathy treatment",
        min_age=18,
        max_age=75,
        gender=None,
        conditions=["diabetes"],
        interval_months=12,
        evidence_grade="B",
        source="ADA/HEDIS",
        hedis_measure=True
    ),
    "CBP": ScreeningGuideline(
        measure_id="CBP",
        measure_name="Controlling High Blood Pressure",
        description="Blood pressure control for hypertensive patients",
        min_age=18,
        max_age=85,
        gender=None,
        conditions=["hypertension"],
        interval_months=6,
        evidence_grade="A",
        source="USPSTF/HEDIS",
        hedis_measure=True,
        mips_measure=True,
        stars_measure=True
    ),
    "IMA": ScreeningGuideline(
        measure_id="IMA",
        measure_name="Immunizations for Adolescents",
        description="Tdap, HPV, and Meningococcal vaccines",
        min_age=13,
        max_age=17,
        gender=None,
        interval_months=0,  # One-time (series)
        evidence_grade="A",
        source="ACIP/HEDIS",
        hedis_measure=True
    ),
    "FLU": ScreeningGuideline(
        measure_id="FLU",
        measure_name="Flu Vaccination",
        description="Annual influenza vaccination",
        min_age=6,  # months, but using years
        max_age=120,
        gender=None,
        interval_months=12,  # Annual
        evidence_grade="A",
        source="ACIP",
        hedis_measure=True,
        mips_measure=True
    ),
    "PNE": ScreeningGuideline(
        measure_id="PNE",
        measure_name="Pneumococcal Vaccination",
        description="Pneumonia vaccination for elderly/high-risk",
        min_age=65,
        max_age=120,
        gender=None,
        interval_months=0,  # One-time (or per schedule)
        evidence_grade="A",
        source="ACIP",
        hedis_measure=True
    ),
    "DEP": ScreeningGuideline(
        measure_id="DEP",
        measure_name="Screening for Depression",
        description="PHQ-2 or PHQ-9 depression screening",
        min_age=12,
        max_age=120,
        gender=None,
        interval_months=12,
        evidence_grade="B",
        source="USPSTF",
        hedis_measure=True,
        mips_measure=True
    ),
    "AAB": ScreeningGuideline(
        measure_id="AAB",
        measure_name="Avoidance of Antibiotic Treatment for Acute Bronchitis",
        description="Avoiding unnecessary antibiotics for viral bronchitis",
        min_age=3,
        max_age=120,
        gender=None,
        interval_months=0,
        evidence_grade="A",
        source="HEDIS",
        hedis_measure=True
    ),
    "AWC": ScreeningGuideline(
        measure_id="AWC",
        measure_name="Adolescent Well-Care Visit",
        description="Annual well-care visit for adolescents",
        min_age=12,
        max_age=21,
        gender=None,
        interval_months=12,
        evidence_grade="B",
        source="HEDIS",
        hedis_measure=True
    ),
    "LDL": ScreeningGuideline(
        measure_id="LDL",
        measure_name="LDL Cholesterol Screening",
        description="LDL cholesterol testing for cardiovascular risk",
        min_age=40,
        max_age=75,
        gender=None,
        interval_months=60,  # Every 5 years (or more frequent if elevated)
        evidence_grade="B",
        source="USPSTF",
        hedis_measure=False,
        mips_measure=True
    ),
    "OST": ScreeningGuideline(
        measure_id="OST",
        measure_name="Osteoporosis Screening",
        description="Bone density screening for postmenopausal women",
        min_age=65,
        max_age=120,
        gender="F",
        interval_months=0,  # Based on risk factors
        evidence_grade="B",
        source="USPSTF",
        hedis_measure=True
    ),
}


# Priority scoring based on evidence and clinical impact
PRIORITY_WEIGHTS = {
    "A": 10,  # Strong evidence
    "B": 7,
    "C": 3,
    "I": 1,
}

CONDITION_PRIORITY_BOOST = {
    "diabetes": 2,
    "hypertension": 2,
    "cancer_history": 3,
    "immunocompromised": 3,
}


class CareGapPriority(Enum):
    """Priority levels for care gaps."""
    ROUTINE = "routine"
    OVERDUE = "overdue"
    URGENT = "urgent"
    CRITICAL = "critical"


@dataclass
class CareGap:
    """Represents a gap in patient care."""
    gap_id: str
    patient_id: str
    measure_id: str
    measure_name: str
    gap_type: str
    priority: CareGapPriority
    
    due_date: Optional[date] = None
    last_completed: Optional[date] = None
    days_overdue: int = 0
    
    recommendation: str = ""
    evidence_grade: str = ""
    
    quality_program: Optional[str] = None
    affects_stars_rating: bool = False
    
    patient_outreach_attempts: int = 0
    patient_declined: bool = False


class CareGapAnalyzer:
    """
    Analyzes patient data to identify care gaps.
    
    Uses USPSTF guidelines and HEDIS measures to identify
    missing or overdue preventive care and chronic disease management.
    """
    
    def __init__(self):
        """Initialize analyzer with screening guidelines."""
        self.guidelines = SCREENING_GUIDELINES
        self._patient_history: Dict[str, Dict[str, date]] = {}  # patient_id -> {measure_id -> last_date}
        self._closed_gaps: Dict[str, List[str]] = {}  # patient_id -> [gap_ids]
        self._outreach_records: Dict[str, List[Dict]] = {}  # gap_id -> [outreach records]
    
    async def analyze_patient(
        self,
        patient_id: str,
        patient_data: Optional[Dict[str, Any]] = None,
        programs: Optional[List[Any]] = None
    ) -> List[CareGap]:
        """
        Analyze care gaps for a patient.
        
        Args:
            patient_id: Patient identifier
            patient_data: Patient demographics and conditions
                Expected keys: age, gender, conditions[], last_screenings{}
            programs: Quality programs to consider
        
        Returns:
            List of identified care gaps
        """
        gaps = []
        
        # Default patient data if not provided
        if patient_data is None:
            patient_data = {
                "age": 50,
                "gender": None,
                "conditions": [],
                "last_screenings": {}
            }
        
        age = patient_data.get("age", 50)
        gender = patient_data.get("gender")
        conditions = patient_data.get("conditions", [])
        last_screenings = patient_data.get("last_screenings", {})
        
        today = date.today()
        
        for measure_id, guideline in self.guidelines.items():
            # Check eligibility
            if not self._is_eligible(
                guideline, age, gender, conditions
            ):
                continue
            
            # Check if screening is due
            last_date = last_screenings.get(measure_id)
            if last_date:
                if isinstance(last_date, str):
                    last_date = datetime.strptime(last_date, "%Y-%m-%d").date()
                
                # Calculate when next is due
                next_due = last_date + timedelta(days=guideline.interval_months * 30)
                days_overdue = (today - next_due).days
            else:
                # Never done — assume very overdue
                next_due = None
                days_overdue = guideline.interval_months * 30  # Assume one cycle overdue
            
            # Skip if not yet due
            if last_date and days_overdue < -30:  # Not due for another month
                continue
            
            # Determine priority
            priority = self._calculate_priority(
                guideline, days_overdue, conditions
            )
            
            gap = CareGap(
                gap_id=f"{patient_id}_{measure_id}_{uuid.uuid4().hex[:8]}",
                patient_id=patient_id,
                measure_id=measure_id,
                measure_name=guideline.measure_name,
                gap_type="screening" if "screening" in guideline.measure_name.lower() else "care",
                priority=priority,
                due_date=next_due,
                last_completed=last_date,
                days_overdue=max(0, days_overdue),
                recommendation=self._generate_recommendation(guideline),
                evidence_grade=guideline.evidence_grade,
                quality_program="HEDIS" if guideline.hedis_measure else "MIPS",
                affects_stars_rating=guideline.stars_measure
            )
            
            gaps.append(gap)
        
        logger.info(f"Found {len(gaps)} care gaps for patient {patient_id}")
        return gaps
    
    def _is_eligible(
        self,
        guideline: ScreeningGuideline,
        age: int,
        gender: Optional[str],
        conditions: List[str]
    ) -> bool:
        """Check if patient is eligible for this screening."""
        # Age check
        if age < guideline.min_age or age > guideline.max_age:
            return False
        
        # Gender check
        if guideline.gender and gender and guideline.gender != gender:
            return False
        
        # Condition requirements
        if guideline.conditions:
            if not any(c.lower() in [cond.lower() for cond in conditions] 
                       for c in guideline.conditions):
                return False
        
        # Exclusion check
        if guideline.exclusions:
            if any(e.lower() in [cond.lower() for cond in conditions] 
                   for e in guideline.exclusions):
                return False
        
        return True
    
    def _calculate_priority(
        self,
        guideline: ScreeningGuideline,
        days_overdue: int,
        conditions: List[str]
    ) -> CareGapPriority:
        """Calculate priority based on overdue time and risk factors."""
        # Base priority on how overdue
        if days_overdue > 365 * 2:  # >2 years overdue
            base_priority = CareGapPriority.CRITICAL
        elif days_overdue > 365:  # >1 year overdue
            base_priority = CareGapPriority.URGENT
        elif days_overdue > 0:
            base_priority = CareGapPriority.OVERDUE
        else:
            base_priority = CareGapPriority.ROUTINE
        
        # Boost priority for high-risk conditions
        for condition in conditions:
            condition_lower = condition.lower()
            if condition_lower in CONDITION_PRIORITY_BOOST:
                if base_priority == CareGapPriority.OVERDUE:
                    base_priority = CareGapPriority.URGENT
                elif base_priority == CareGapPriority.ROUTINE:
                    base_priority = CareGapPriority.OVERDUE
        
        # Boost priority for high-evidence measures
        if guideline.evidence_grade == "A" and base_priority == CareGapPriority.OVERDUE:
            base_priority = CareGapPriority.URGENT
        
        return base_priority
    
    def _generate_recommendation(self, guideline: ScreeningGuideline) -> str:
        """Generate patient-friendly recommendation."""
        recommendations = {
            "BCS": "Schedule a mammogram for breast cancer screening.",
            "COL": "Schedule a colonoscopy or stool test for colorectal cancer screening.",
            "CCS": "Schedule a Pap smear for cervical cancer screening.",
            "DCA": "Schedule a lab visit to check your A1c level.",
            "DCE": "Schedule a dilated eye exam with an ophthalmologist.",
            "DCN": "Schedule a urine test to check kidney function.",
            "CBP": "Schedule a visit to check your blood pressure.",
            "IMA": "Schedule vaccination appointment for required adolescent immunizations.",
            "FLU": "Get your annual flu shot.",
            "PNE": "Get your pneumonia vaccine.",
            "DEP": "Complete a depression screening questionnaire at your next visit.",
            "LDL": "Schedule a fasting lipid panel to check cholesterol levels.",
            "OST": "Schedule a bone density scan (DEXA) to screen for osteoporosis.",
            "AWC": "Schedule an annual well-care visit.",
        }
        
        return recommendations.get(
            guideline.measure_id, 
            f"Schedule {guideline.measure_name}"
        )
    
    async def close_gap(
        self,
        patient_id: str,
        measure_id: str,
        completion_date: date,
        result: Optional[str] = None
    ) -> bool:
        """
        Record gap closure.
        
        Args:
            patient_id: Patient identifier
            measure_id: Quality measure ID
            completion_date: When completed
            result: Optional result value
        
        Returns:
            True if gap was found and closed
        """
        # Update patient history
        if patient_id not in self._patient_history:
            self._patient_history[patient_id] = {}
        
        self._patient_history[patient_id][measure_id] = completion_date
        
        logger.info(
            f"Closed gap: patient={patient_id}, measure={measure_id}, "
            f"date={completion_date}, result={result}"
        )
        
        return True
    
    async def record_outreach(
        self,
        patient_id: str,
        gap_id: str,
        outreach_type: str,
        outcome: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Record patient outreach attempt.
        
        Args:
            patient_id: Patient identifier
            gap_id: Care gap ID
            outreach_type: phone, letter, portal, sms
            outcome: reached, voicemail, scheduled, declined, no_answer
            notes: Optional notes
        
        Returns:
            True if recorded successfully
        """
        if gap_id not in self._outreach_records:
            self._outreach_records[gap_id] = []
        
        record = {
            "timestamp": datetime.now().isoformat(),
            "patient_id": patient_id,
            "type": outreach_type,
            "outcome": outcome,
            "notes": notes
        }
        
        self._outreach_records[gap_id].append(record)
        
        logger.info(
            f"Recorded outreach: gap={gap_id}, type={outreach_type}, outcome={outcome}"
        )
        
        return True
    
    def get_guideline(self, measure_id: str) -> Optional[ScreeningGuideline]:
        """Get guideline by measure ID."""
        return self.guidelines.get(measure_id)
    
    def get_all_guidelines(self) -> Dict[str, ScreeningGuideline]:
        """Get all screening guidelines."""
        return self.guidelines.copy()
    
    def get_hedis_measures(self) -> List[str]:
        """Get list of HEDIS measure IDs."""
        return [
            m for m, g in self.guidelines.items() if g.hedis_measure
        ]
    
    def get_stars_measures(self) -> List[str]:
        """Get list of Medicare Stars measure IDs."""
        return [
            m for m, g in self.guidelines.items() if g.stars_measure
        ]
