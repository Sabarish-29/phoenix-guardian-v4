"""
Phoenix Guardian - Feature Engineering for Readmission Prediction.

Extracts clinical features from encounter records for 30-day readmission
risk prediction. Implements evidence-based risk factors from:
- CMS Hospital Readmissions Reduction Program (HRRP)
- Charlson Comorbidity Index (simplified)
- LACE Index components

Compliance:
- HIPAA: No PHI in feature vectors (uses encoded IDs)
- FDA 21 CFR Part 820: Documented feature definitions
- IEC 62304: Class B software component

Feature Set (12 features):
1. num_diagnoses - Total diagnosis count
2. has_heart_failure - HF indicator (ICD-10 I50.x)
3. has_diabetes - DM indicator (ICD-10 E10-E14)
4. has_copd - COPD indicator (ICD-10 J44.x)
5. has_pneumonia - Pneumonia indicator (ICD-10 J18.x)
6. comorbidity_index - Simplified Charlson score
7. visits_30d - Prior visits in 30 days
8. visits_60d - Prior visits in 60 days
9. visits_90d - Prior visits in 90 days
10. length_of_stay - Current LOS in days
11. discharge_disposition_encoded - Discharge destination
12. specialty_encoded - Attending physician specialty
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# ICD-10 Code Mappings for Condition Detection
# =============================================================================


# Heart Failure: I50.x family
HEART_FAILURE_CODES = frozenset([
    "I50", "I50.1", "I50.2", "I50.20", "I50.21", "I50.22", "I50.23",
    "I50.3", "I50.30", "I50.31", "I50.32", "I50.33",
    "I50.4", "I50.40", "I50.41", "I50.42", "I50.43",
    "I50.8", "I50.81", "I50.810", "I50.811", "I50.812", "I50.813", "I50.814",
    "I50.82", "I50.83", "I50.84", "I50.89", "I50.9",
])

# Diabetes: E10-E14 families
DIABETES_CODES = frozenset([
    "E10", "E10.1", "E10.2", "E10.3", "E10.4", "E10.5", "E10.6", "E10.8", "E10.9",
    "E11", "E11.0", "E11.1", "E11.2", "E11.3", "E11.4", "E11.5", "E11.6", "E11.8", "E11.9",
    "E13", "E13.0", "E13.1", "E13.2", "E13.3", "E13.4", "E13.5", "E13.6", "E13.8", "E13.9",
])

# COPD: J44.x family
COPD_CODES = frozenset([
    "J44", "J44.0", "J44.1", "J44.9",
])

# Pneumonia: J18.x family (and related)
PNEUMONIA_CODES = frozenset([
    "J18", "J18.0", "J18.1", "J18.2", "J18.8", "J18.9",
    "J15", "J15.0", "J15.1", "J15.2", "J15.3", "J15.4", "J15.5", "J15.6", "J15.7", "J15.8", "J15.9",
    "J13", "J14", "J16", "J17",
])

# Cancer codes for comorbidity (simplified C00-C97)
CANCER_CODES_PREFIX = ("C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9")

# Liver disease (K70-K77)
LIVER_CODES_PREFIX = ("K70", "K71", "K72", "K73", "K74", "K75", "K76", "K77")

# Renal disease (N17-N19)
RENAL_CODES_PREFIX = ("N17", "N18", "N19")


# =============================================================================
# Discharge Disposition Encoding
# =============================================================================


DISCHARGE_DISPOSITION_MAP = {
    "home": 0,
    "home_health": 1,
    "snf": 2,                  # Skilled Nursing Facility
    "rehab": 3,
    "ltach": 4,                # Long-Term Acute Care Hospital
    "hospice": 5,
    "ama": 6,                  # Against Medical Advice (high risk)
    "expired": 7,
    "other": 8,
}


# =============================================================================
# Specialty Encoding
# =============================================================================


SPECIALTY_MAP = {
    "internal_medicine": 0,
    "family_medicine": 1,
    "cardiology": 2,
    "pulmonology": 3,
    "nephrology": 4,
    "oncology": 5,
    "hospitalist": 6,
    "surgery": 7,
    "emergency": 8,
    "other": 9,
}


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class EncounterRecord:
    """
    A single hospital encounter record.
    
    Represents an inpatient or observation stay with associated
    clinical data for feature extraction.
    """
    
    patient_id: str
    encounter_id: str
    encounter_date: datetime
    discharge_disposition: str
    diagnosis_codes: List[str] = field(default_factory=list)  # ICD-10
    procedure_codes: List[str] = field(default_factory=list)  # CPT
    length_of_stay_days: int = 1
    attending_specialty: str = "other"
    
    def __post_init__(self) -> None:
        """Validate encounter record."""
        if not self.patient_id:
            raise ValueError("patient_id is required")
        if not self.encounter_id:
            raise ValueError("encounter_id is required")
        if self.length_of_stay_days < 0:
            raise ValueError("length_of_stay_days cannot be negative")


@dataclass
class PatientFeatures:
    """
    Extracted features for readmission prediction.
    
    Contains exactly 12 features in a fixed order for model input.
    All features are numeric for XGBoost compatibility.
    """
    
    patient_id: str
    
    # Diagnosis features (5)
    num_diagnoses: int = 0
    has_heart_failure: bool = False
    has_diabetes: bool = False
    has_copd: bool = False
    has_pneumonia: bool = False
    
    # Comorbidity score (1)
    comorbidity_index: int = 0
    
    # Utilization features (3)
    visits_30d: int = 0
    visits_60d: int = 0
    visits_90d: int = 0
    
    # Encounter features (3)
    length_of_stay: int = 0
    discharge_disposition_encoded: int = 0
    specialty_encoded: int = 0


# =============================================================================
# Feature Extraction Functions
# =============================================================================


def has_condition_codes(
    diagnosis_codes: List[str],
    condition_codes: frozenset,
) -> bool:
    """Check if any diagnosis code matches a condition set."""
    for code in diagnosis_codes:
        # Normalize code (uppercase, no dots for matching)
        normalized = code.upper().replace(".", "")
        
        # Check exact match
        if code.upper() in condition_codes:
            return True
        
        # Check with dot variations
        for condition_code in condition_codes:
            if code.upper().startswith(condition_code.replace(".", "")):
                return True
    
    return False


def has_prefix_condition(
    diagnosis_codes: List[str],
    prefixes: tuple,
) -> bool:
    """Check if any diagnosis code starts with given prefixes."""
    for code in diagnosis_codes:
        normalized = code.upper()
        if normalized.startswith(prefixes):
            return True
    return False


def compute_comorbidity_index(diagnosis_codes: List[str]) -> int:
    """
    Compute simplified Charlson Comorbidity Index.
    
    Scoring:
    - Heart Failure: 1 point
    - Diabetes: 1 point
    - COPD: 1 point
    - Cancer: 2 points
    - Liver Disease: 2 points
    - Renal Disease: 2 points
    
    Args:
        diagnosis_codes: List of ICD-10 diagnosis codes
        
    Returns:
        Integer comorbidity score (0-9 typical range)
    """
    score = 0
    
    # 1-point conditions
    if has_condition_codes(diagnosis_codes, HEART_FAILURE_CODES):
        score += 1
    
    if has_condition_codes(diagnosis_codes, DIABETES_CODES):
        score += 1
    
    if has_condition_codes(diagnosis_codes, COPD_CODES):
        score += 1
    
    # 2-point conditions
    if has_prefix_condition(diagnosis_codes, CANCER_CODES_PREFIX):
        score += 2
    
    if has_prefix_condition(diagnosis_codes, LIVER_CODES_PREFIX):
        score += 2
    
    if has_prefix_condition(diagnosis_codes, RENAL_CODES_PREFIX):
        score += 2
    
    return score


def count_prior_visits(
    history: List[EncounterRecord],
    reference_date: datetime,
    days_back: int,
) -> int:
    """
    Count encounters within a time window before reference date.
    
    Args:
        history: List of prior encounters
        reference_date: Date to count back from
        days_back: Number of days to look back
        
    Returns:
        Count of encounters in window
    """
    cutoff_date = reference_date - timedelta(days=days_back)
    
    count = 0
    for encounter in history:
        if cutoff_date <= encounter.encounter_date < reference_date:
            count += 1
    
    return count


def encode_discharge_disposition(disposition: str) -> int:
    """Encode discharge disposition to integer."""
    normalized = disposition.lower().strip().replace(" ", "_")
    return DISCHARGE_DISPOSITION_MAP.get(normalized, DISCHARGE_DISPOSITION_MAP["other"])


def encode_specialty(specialty: str) -> int:
    """Encode attending specialty to integer."""
    normalized = specialty.lower().strip().replace(" ", "_")
    return SPECIALTY_MAP.get(normalized, SPECIALTY_MAP["other"])


def extract_features(
    current_encounter: EncounterRecord,
    history: List[EncounterRecord],
    reference_date: Optional[datetime] = None,
) -> PatientFeatures:
    """
    Extract all features from an encounter for readmission prediction.
    
    Args:
        current_encounter: The index encounter to predict readmission for
        history: List of prior encounters for this patient
        reference_date: Date to use for time-based features (defaults to encounter_date)
        
    Returns:
        PatientFeatures with 12 extracted features
    """
    ref_date = reference_date or current_encounter.encounter_date
    dx_codes = current_encounter.diagnosis_codes
    
    # Filter history to only this patient's prior encounters
    patient_history = [
        enc for enc in history
        if enc.patient_id == current_encounter.patient_id
        and enc.encounter_date < ref_date
    ]
    
    features = PatientFeatures(
        patient_id=current_encounter.patient_id,
        
        # Diagnosis features
        num_diagnoses=len(dx_codes),
        has_heart_failure=has_condition_codes(dx_codes, HEART_FAILURE_CODES),
        has_diabetes=has_condition_codes(dx_codes, DIABETES_CODES),
        has_copd=has_condition_codes(dx_codes, COPD_CODES),
        has_pneumonia=has_condition_codes(dx_codes, PNEUMONIA_CODES),
        
        # Comorbidity
        comorbidity_index=compute_comorbidity_index(dx_codes),
        
        # Utilization
        visits_30d=count_prior_visits(patient_history, ref_date, 30),
        visits_60d=count_prior_visits(patient_history, ref_date, 60),
        visits_90d=count_prior_visits(patient_history, ref_date, 90),
        
        # Encounter details
        length_of_stay=current_encounter.length_of_stay_days,
        discharge_disposition_encoded=encode_discharge_disposition(
            current_encounter.discharge_disposition
        ),
        specialty_encoded=encode_specialty(current_encounter.attending_specialty),
    )
    
    return features


def features_to_array(features: PatientFeatures) -> List[float]:
    """
    Convert PatientFeatures to a fixed-order array for model input.
    
    Order matches FEATURE_NAMES in ReadmissionModel.
    
    Args:
        features: PatientFeatures dataclass
        
    Returns:
        List of exactly 12 floats in fixed order
    """
    return [
        float(features.num_diagnoses),
        float(features.has_heart_failure),
        float(features.has_diabetes),
        float(features.has_copd),
        float(features.has_pneumonia),
        float(features.comorbidity_index),
        float(features.visits_30d),
        float(features.visits_60d),
        float(features.visits_90d),
        float(features.length_of_stay),
        float(features.discharge_disposition_encoded),
        float(features.specialty_encoded),
    ]


def array_to_features(
    patient_id: str,
    array: List[float],
) -> PatientFeatures:
    """
    Convert feature array back to PatientFeatures.
    
    Args:
        patient_id: Patient identifier
        array: List of 12 floats in standard order
        
    Returns:
        PatientFeatures dataclass
    """
    if len(array) != 12:
        raise ValueError(f"Expected 12 features, got {len(array)}")
    
    return PatientFeatures(
        patient_id=patient_id,
        num_diagnoses=int(array[0]),
        has_heart_failure=bool(array[1]),
        has_diabetes=bool(array[2]),
        has_copd=bool(array[3]),
        has_pneumonia=bool(array[4]),
        comorbidity_index=int(array[5]),
        visits_30d=int(array[6]),
        visits_60d=int(array[7]),
        visits_90d=int(array[8]),
        length_of_stay=int(array[9]),
        discharge_disposition_encoded=int(array[10]),
        specialty_encoded=int(array[11]),
    )


# =============================================================================
# Feature Validation
# =============================================================================


def validate_features(features: PatientFeatures) -> List[str]:
    """
    Validate feature values are within expected ranges.
    
    Returns:
        List of validation warnings (empty if all valid)
    """
    warnings = []
    
    if features.num_diagnoses < 0:
        warnings.append("num_diagnoses is negative")
    
    if features.num_diagnoses > 50:
        warnings.append("num_diagnoses unusually high (>50)")
    
    if features.comorbidity_index < 0:
        warnings.append("comorbidity_index is negative")
    
    if features.comorbidity_index > 9:
        warnings.append("comorbidity_index unusually high (>9)")
    
    if features.length_of_stay < 0:
        warnings.append("length_of_stay is negative")
    
    if features.length_of_stay > 365:
        warnings.append("length_of_stay unusually high (>365 days)")
    
    if features.visits_30d > features.visits_60d:
        warnings.append("visits_30d > visits_60d (impossible)")
    
    if features.visits_60d > features.visits_90d:
        warnings.append("visits_60d > visits_90d (impossible)")
    
    return warnings


# =============================================================================
# Module Entry Point
# =============================================================================


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Demo usage
    encounter = EncounterRecord(
        patient_id="P001",
        encounter_id="E001",
        encounter_date=datetime(2026, 1, 15),
        discharge_disposition="home",
        diagnosis_codes=["I50.9", "E11.9", "J44.1"],  # HF, DM, COPD
        procedure_codes=["99213"],
        length_of_stay_days=5,
        attending_specialty="cardiology",
    )
    
    # Prior encounters
    history = [
        EncounterRecord(
            patient_id="P001",
            encounter_id="E000",
            encounter_date=datetime(2025, 12, 20),
            discharge_disposition="home",
            diagnosis_codes=["I50.9"],
            length_of_stay_days=3,
            attending_specialty="hospitalist",
        ),
    ]
    
    features = extract_features(encounter, history)
    logger.info(f"Extracted features: {features}")
    
    array = features_to_array(features)
    logger.info(f"Feature array ({len(array)} values): {array}")
    
    comorbidity = compute_comorbidity_index(encounter.diagnosis_codes)
    logger.info(f"Comorbidity index: {comorbidity}")
