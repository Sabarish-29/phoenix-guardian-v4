"""
Risk Stratifier.

Stratifies patients by risk level for care management prioritization.

RISK MODELS:
1. 30-Day Readmission Risk
   - Hospital Readmissions Reduction Program (HRRP) target
   - Based on: diagnosis, comorbidities, recent utilization, social factors

2. 90-Day Hospitalization Risk
   - Preventable admission prediction
   - Based on: chronic conditions, ED visits, medication adherence

3. 12-Month Mortality Risk
   - High-risk patient identification
   - Based on: age, conditions, functional status, frailty markers

RISK FACTORS CONSIDERED:
    Clinical:
    - Chronic conditions (CHF, COPD, CKD, diabetes, CAD)
    - Polypharmacy (>5 medications)
    - Recent hospitalizations (30/90/365 days)
    - ED visits
    - Medication non-adherence
    
    Social Determinants:
    - Food insecurity
    - Housing instability
    - Transportation barriers
    - Social isolation
    - Health literacy
    - Financial barriers
    
    Functional:
    - ADL limitations
    - Cognitive impairment
    - Fall risk
    - Frailty score

CARE MANAGEMENT LEVELS:
    Level 1 (Low Risk): Annual wellness, gap closure outreach
    Level 2 (Moderate Risk): Quarterly check-ins, care coordination
    Level 3 (High Risk): Monthly case management, transitions of care
    Level 4 (Critical Risk): Weekly intensive case management, home visits
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime, date, timedelta
import logging
import math

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Patient risk stratification levels."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PatientRiskProfile:
    """Risk profile for a patient."""
    patient_id: str
    risk_level: RiskLevel
    risk_score: float  # 0.0 - 1.0
    
    chronic_conditions: List[str] = field(default_factory=list)
    social_determinants: List[str] = field(default_factory=list)
    recent_utilization: Dict[str, int] = field(default_factory=dict)
    
    readmission_risk_30day: float = 0.0
    hospitalization_risk_90day: float = 0.0
    mortality_risk_12month: float = 0.0
    
    care_management_level: str = ""
    recommended_interventions: List[str] = field(default_factory=list)
    
    last_updated: datetime = field(default_factory=datetime.now)


# Risk weights for conditions
CONDITION_RISK_WEIGHTS = {
    # High-impact conditions
    "chf": 0.15,
    "congestive_heart_failure": 0.15,
    "heart_failure": 0.15,
    "copd": 0.12,
    "chronic_obstructive_pulmonary_disease": 0.12,
    "ckd": 0.12,
    "chronic_kidney_disease": 0.12,
    "esrd": 0.18,
    "end_stage_renal_disease": 0.18,
    "diabetes": 0.08,
    "cad": 0.10,
    "coronary_artery_disease": 0.10,
    "stroke": 0.12,
    "cva": 0.12,
    
    # Moderate-impact conditions
    "hypertension": 0.04,
    "atrial_fibrillation": 0.08,
    "afib": 0.08,
    "cancer": 0.10,
    "dementia": 0.12,
    "alzheimers": 0.12,
    "depression": 0.05,
    "anxiety": 0.03,
    "asthma": 0.04,
    "obesity": 0.03,
    
    # Lower-impact conditions
    "hyperlipidemia": 0.02,
    "hypothyroidism": 0.01,
    "gerd": 0.01,
    "osteoarthritis": 0.02,
}

# Social determinant risk weights
SOCIAL_RISK_WEIGHTS = {
    "food_insecurity": 0.08,
    "housing_instability": 0.10,
    "homelessness": 0.15,
    "transportation_barriers": 0.05,
    "social_isolation": 0.06,
    "low_health_literacy": 0.04,
    "financial_barriers": 0.05,
    "no_insurance": 0.08,
    "underinsured": 0.04,
    "substance_abuse": 0.10,
    "tobacco_use": 0.04,
    "alcohol_abuse": 0.06,
    "caregiver_burnout": 0.05,
    "non_english_speaking": 0.03,
}

# Utilization risk weights
UTILIZATION_RISK_WEIGHTS = {
    "hospital_admissions_30d": 0.15,
    "hospital_admissions_90d": 0.10,
    "hospital_admissions_365d": 0.05,
    "ed_visits_30d": 0.08,
    "ed_visits_90d": 0.05,
    "ed_visits_365d": 0.03,
    "observation_stays_90d": 0.06,
    "snf_stays_365d": 0.08,
}

# Care management level thresholds
CARE_MANAGEMENT_THRESHOLDS = {
    RiskLevel.LOW: "Level 1: Annual wellness, gap closure outreach",
    RiskLevel.MODERATE: "Level 2: Quarterly check-ins, care coordination",
    RiskLevel.HIGH: "Level 3: Monthly case management, transitions of care",
    RiskLevel.CRITICAL: "Level 4: Weekly intensive case management, home visits",
}

# Intervention recommendations by risk factor
INTERVENTIONS = {
    "chf": ["Cardiology referral", "Heart failure clinic enrollment", "Daily weight monitoring", "Fluid restriction education"],
    "copd": ["Pulmonology referral", "Pulmonary rehab", "Smoking cessation if applicable", "Inhaler technique review"],
    "diabetes": ["Endocrinology referral if uncontrolled", "Diabetes education", "Foot exam", "Eye exam"],
    "ckd": ["Nephrology referral", "Dietary counseling", "Medication review for renal dosing"],
    "food_insecurity": ["SNAP application assistance", "Food bank referral", "Meals on Wheels"],
    "housing_instability": ["Social work referral", "Housing assistance programs", "Medical respite care"],
    "transportation_barriers": ["Medical transportation services", "Telehealth when appropriate"],
    "social_isolation": ["Community resource connection", "Support group referral", "Senior center programs"],
    "polypharmacy": ["Pharmacist medication review", "Deprescribing evaluation", "Medication synchronization"],
    "fall_risk": ["PT/OT evaluation", "Home safety assessment", "Balance program"],
    "hospital_admission": ["Transition of care call", "Post-discharge visit within 7 days", "Medication reconciliation"],
}


class RiskStratifier:
    """
    Stratifies patients by risk level using multiple risk models.
    
    This is a simplified implementation. In production, this would use
    machine learning models trained on historical data, or integrate
    with commercial risk stratification tools (e.g., Johns Hopkins ACG,
    Milliman, 3M CRGs).
    """
    
    def __init__(self):
        """Initialize risk stratifier."""
        self.condition_weights = CONDITION_RISK_WEIGHTS
        self.social_weights = SOCIAL_RISK_WEIGHTS
        self.utilization_weights = UTILIZATION_RISK_WEIGHTS
    
    async def stratify(
        self,
        patient_id: str,
        patient_data: Optional[Dict[str, Any]] = None
    ) -> PatientRiskProfile:
        """
        Stratify risk for a patient.
        
        Args:
            patient_id: Patient identifier
            patient_data: Patient data including:
                - age: int
                - conditions: List[str]
                - social_determinants: List[str]
                - utilization: Dict[str, int]
                - medications_count: int
                - functional_status: Dict[str, Any]
        
        Returns:
            PatientRiskProfile with comprehensive risk assessment
        """
        if patient_data is None:
            patient_data = {}
        
        age = patient_data.get("age", 50)
        conditions = patient_data.get("conditions", [])
        social_factors = patient_data.get("social_determinants", [])
        utilization = patient_data.get("utilization", {})
        med_count = patient_data.get("medications_count", 0)
        functional = patient_data.get("functional_status", {})
        
        # Calculate component scores
        condition_score = self._calculate_condition_score(conditions)
        social_score = self._calculate_social_score(social_factors)
        utilization_score = self._calculate_utilization_score(utilization)
        age_score = self._calculate_age_score(age)
        polypharmacy_score = self._calculate_polypharmacy_score(med_count)
        functional_score = self._calculate_functional_score(functional)
        
        # Combined risk score (weighted average)
        total_score = (
            condition_score * 0.35 +
            social_score * 0.15 +
            utilization_score * 0.25 +
            age_score * 0.10 +
            polypharmacy_score * 0.05 +
            functional_score * 0.10
        )
        
        # Normalize to 0-1
        risk_score = min(1.0, max(0.0, total_score))
        
        # Determine risk level
        risk_level = self._determine_risk_level(risk_score)
        
        # Calculate specific risk predictions
        readmission_risk = self._calculate_readmission_risk(
            conditions, utilization, social_factors
        )
        hospitalization_risk = self._calculate_hospitalization_risk(
            conditions, utilization, age
        )
        mortality_risk = self._calculate_mortality_risk(
            conditions, age, functional
        )
        
        # Determine care management level
        care_level = CARE_MANAGEMENT_THRESHOLDS[risk_level]
        
        # Generate intervention recommendations
        interventions = self._generate_interventions(
            conditions, social_factors, utilization
        )
        
        profile = PatientRiskProfile(
            patient_id=patient_id,
            risk_level=risk_level,
            risk_score=round(risk_score, 3),
            chronic_conditions=conditions,
            social_determinants=social_factors,
            recent_utilization=utilization,
            readmission_risk_30day=round(readmission_risk, 3),
            hospitalization_risk_90day=round(hospitalization_risk, 3),
            mortality_risk_12month=round(mortality_risk, 3),
            care_management_level=care_level,
            recommended_interventions=interventions,
            last_updated=datetime.now()
        )
        
        logger.info(
            f"Stratified patient {patient_id}: "
            f"risk_level={risk_level.value}, score={risk_score:.3f}"
        )
        
        return profile
    
    def _calculate_condition_score(self, conditions: List[str]) -> float:
        """Calculate risk score from chronic conditions."""
        score = 0.0
        conditions_lower = [c.lower().replace(" ", "_") for c in conditions]
        
        for condition in conditions_lower:
            if condition in self.condition_weights:
                score += self.condition_weights[condition]
            else:
                # Check for partial matches
                for key, weight in self.condition_weights.items():
                    if key in condition or condition in key:
                        score += weight
                        break
        
        # Comorbidity multiplier (exponential risk with multiple conditions)
        if len(conditions) > 3:
            score *= 1.0 + (len(conditions) - 3) * 0.1
        
        return min(1.0, score)
    
    def _calculate_social_score(self, social_factors: List[str]) -> float:
        """Calculate risk score from social determinants."""
        score = 0.0
        factors_lower = [f.lower().replace(" ", "_") for f in social_factors]
        
        for factor in factors_lower:
            if factor in self.social_weights:
                score += self.social_weights[factor]
            else:
                # Check for partial matches
                for key, weight in self.social_weights.items():
                    if key in factor or factor in key:
                        score += weight
                        break
        
        return min(1.0, score)
    
    def _calculate_utilization_score(self, utilization: Dict[str, int]) -> float:
        """Calculate risk score from recent healthcare utilization."""
        score = 0.0
        
        for key, count in utilization.items():
            key_lower = key.lower()
            if key_lower in self.utilization_weights:
                # Each occurrence adds the weight
                score += self.utilization_weights[key_lower] * min(count, 5)
        
        return min(1.0, score)
    
    def _calculate_age_score(self, age: int) -> float:
        """Calculate risk score based on age."""
        if age < 18:
            return 0.1  # Pediatric has different risk profile
        elif age < 45:
            return 0.05
        elif age < 55:
            return 0.10
        elif age < 65:
            return 0.15
        elif age < 75:
            return 0.25
        elif age < 85:
            return 0.40
        else:
            return 0.60
    
    def _calculate_polypharmacy_score(self, med_count: int) -> float:
        """Calculate risk score from medication count."""
        if med_count <= 4:
            return 0.0
        elif med_count <= 8:
            return 0.10
        elif med_count <= 12:
            return 0.25
        elif med_count <= 16:
            return 0.40
        else:
            return 0.60
    
    def _calculate_functional_score(self, functional: Dict[str, Any]) -> float:
        """Calculate risk score from functional status."""
        score = 0.0
        
        # ADL limitations
        adl_limitations = functional.get("adl_limitations", 0)
        score += min(0.3, adl_limitations * 0.05)
        
        # Cognitive impairment
        if functional.get("cognitive_impairment"):
            score += 0.15
        
        # Fall risk
        if functional.get("fall_risk"):
            score += 0.10
        
        # Frailty
        frailty_score = functional.get("frailty_score", 0)
        if frailty_score >= 3:  # Frail
            score += 0.20
        elif frailty_score >= 2:  # Pre-frail
            score += 0.10
        
        return min(1.0, score)
    
    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """Determine risk level from overall score."""
        if risk_score >= 0.7:
            return RiskLevel.CRITICAL
        elif risk_score >= 0.5:
            return RiskLevel.HIGH
        elif risk_score >= 0.25:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW
    
    def _calculate_readmission_risk(
        self,
        conditions: List[str],
        utilization: Dict[str, int],
        social_factors: List[str]
    ) -> float:
        """
        Calculate 30-day readmission risk.
        
        Simplified LACE-like model.
        """
        risk = 0.05  # Baseline
        
        # Recent admission is biggest risk factor
        recent_admissions = utilization.get("hospital_admissions_30d", 0)
        risk += recent_admissions * 0.15
        
        # High-risk conditions
        high_risk_conditions = ["chf", "copd", "pneumonia", "heart_failure"]
        conditions_lower = [c.lower() for c in conditions]
        for hrc in high_risk_conditions:
            if any(hrc in c for c in conditions_lower):
                risk += 0.08
        
        # Social factors
        if "housing_instability" in [s.lower() for s in social_factors]:
            risk += 0.10
        if "food_insecurity" in [s.lower() for s in social_factors]:
            risk += 0.05
        
        return min(0.9, risk)  # Cap at 90%
    
    def _calculate_hospitalization_risk(
        self,
        conditions: List[str],
        utilization: Dict[str, int],
        age: int
    ) -> float:
        """Calculate 90-day hospitalization risk."""
        risk = 0.03  # Baseline
        
        # Age factor
        if age >= 75:
            risk += 0.08
        elif age >= 65:
            risk += 0.04
        
        # ED visits predict hospitalization
        ed_visits = utilization.get("ed_visits_90d", 0)
        risk += ed_visits * 0.05
        
        # Chronic conditions
        conditions_lower = [c.lower() for c in conditions]
        if any("chf" in c or "heart_failure" in c for c in conditions_lower):
            risk += 0.12
        if any("copd" in c for c in conditions_lower):
            risk += 0.10
        if any("ckd" in c or "kidney" in c for c in conditions_lower):
            risk += 0.08
        
        return min(0.85, risk)
    
    def _calculate_mortality_risk(
        self,
        conditions: List[str],
        age: int,
        functional: Dict[str, Any]
    ) -> float:
        """Calculate 12-month mortality risk."""
        risk = 0.01  # Baseline
        
        # Age is major factor
        if age >= 90:
            risk += 0.20
        elif age >= 85:
            risk += 0.12
        elif age >= 80:
            risk += 0.08
        elif age >= 75:
            risk += 0.04
        
        # High-mortality conditions
        conditions_lower = [c.lower() for c in conditions]
        if any("esrd" in c or "end_stage" in c for c in conditions_lower):
            risk += 0.25
        if any("cancer" in c or "malignant" in c for c in conditions_lower):
            risk += 0.15
        if any("dementia" in c or "alzheimer" in c for c in conditions_lower):
            risk += 0.12
        if any("chf" in c or "heart_failure" in c for c in conditions_lower):
            risk += 0.10
        
        # Frailty
        if functional.get("frailty_score", 0) >= 3:
            risk += 0.15
        
        return min(0.80, risk)
    
    def _generate_interventions(
        self,
        conditions: List[str],
        social_factors: List[str],
        utilization: Dict[str, int]
    ) -> List[str]:
        """Generate recommended interventions based on risk factors."""
        interventions = []
        
        conditions_lower = [c.lower() for c in conditions]
        social_lower = [s.lower().replace(" ", "_") for s in social_factors]
        
        # Condition-based interventions
        for condition_key, intervention_list in INTERVENTIONS.items():
            if any(condition_key in c for c in conditions_lower):
                interventions.extend(intervention_list[:2])  # Top 2 per condition
        
        # Social-based interventions
        for social_key, intervention_list in INTERVENTIONS.items():
            if any(social_key in s for s in social_lower):
                interventions.extend(intervention_list[:2])
        
        # Utilization-based interventions
        if utilization.get("hospital_admissions_30d", 0) > 0:
            interventions.extend(INTERVENTIONS.get("hospital_admission", [])[:2])
        
        # Deduplicate while preserving order
        seen = set()
        unique_interventions = []
        for i in interventions:
            if i not in seen:
                seen.add(i)
                unique_interventions.append(i)
        
        return unique_interventions[:10]  # Limit to top 10
    
    def get_risk_thresholds(self) -> Dict[str, float]:
        """Get risk level thresholds."""
        return {
            "low": 0.0,
            "moderate": 0.25,
            "high": 0.50,
            "critical": 0.70
        }
