"""
Phoenix Guardian - Synthetic Data Generator for Readmission Model.

Generates realistic synthetic patient encounter data for training
and testing the readmission prediction model.

Clinical Realism:
- Condition-specific readmission rates from CMS/literature
- Correlated features (e.g., HF patients have more visits)
- Realistic length of stay distributions
- Appropriate comorbidity patterns

Usage:
    X, y = generate_patient_encounters(num_patients=2000, seed=42)
    # X: (N, 12) feature matrix
    # y: (N,) binary labels (1=readmitted within 30 days)

Privacy:
- No real patient data used
- Fully synthetic, no HIPAA concerns
- Suitable for model development and testing
"""

import logging
from typing import Tuple

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Clinical Readmission Rates (from CMS/literature)
# =============================================================================


CONDITION_READMISSION_RATES = {
    "heart_failure": 0.22,     # CMS HRRP target condition
    "pneumonia": 0.15,         # CMS HRRP target condition
    "copd": 0.18,              # CMS HRRP target condition
    "diabetes": 0.08,          # Lower baseline
    "baseline": 0.03,          # No major conditions
}


# =============================================================================
# Distribution Parameters
# =============================================================================


# Length of stay distributions (mean, std) by condition
LOS_DISTRIBUTIONS = {
    "heart_failure": (5.5, 3.0),
    "pneumonia": (4.5, 2.5),
    "copd": (4.0, 2.0),
    "diabetes": (3.5, 1.5),
    "baseline": (2.5, 1.5),
}

# Prior visit distributions (mean, std) - higher for chronic conditions
VISIT_DISTRIBUTIONS = {
    "heart_failure": (2.5, 1.5),
    "copd": (2.0, 1.2),
    "diabetes": (1.5, 1.0),
    "baseline": (0.5, 0.5),
}


# =============================================================================
# Synthetic Data Generator
# =============================================================================


def generate_patient_encounters(
    num_patients: int = 1000,
    readmission_rate: float = 0.15,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic patient encounter data for readmission prediction.
    
    Creates realistic feature distributions with condition-specific
    readmission rates that correlate with known risk factors.
    
    Args:
        num_patients: Number of patient encounters to generate
        readmission_rate: Overall target readmission rate (approximate)
        seed: Random seed for reproducibility
        
    Returns:
        Tuple of (X, y):
            - X: Feature matrix (N, 12) as numpy array
            - y: Labels (N,) - 1=readmitted, 0=not readmitted
    
    Features generated (in order):
        0. num_diagnoses - Number of diagnoses (1-15)
        1. has_heart_failure - Binary (0/1)
        2. has_diabetes - Binary (0/1)
        3. has_copd - Binary (0/1)
        4. has_pneumonia - Binary (0/1)
        5. comorbidity_index - Score (0-9)
        6. visits_30d - Prior visits in 30 days (0-5)
        7. visits_60d - Prior visits in 60 days (0-8)
        8. visits_90d - Prior visits in 90 days (0-12)
        9. length_of_stay - Days (1-30)
        10. discharge_disposition_encoded - (0-8)
        11. specialty_encoded - (0-9)
    """
    rng = np.random.default_rng(seed)
    
    # Initialize feature arrays
    num_diagnoses = np.zeros(num_patients, dtype=np.float32)
    has_heart_failure = np.zeros(num_patients, dtype=np.float32)
    has_diabetes = np.zeros(num_patients, dtype=np.float32)
    has_copd = np.zeros(num_patients, dtype=np.float32)
    has_pneumonia = np.zeros(num_patients, dtype=np.float32)
    comorbidity_index = np.zeros(num_patients, dtype=np.float32)
    visits_30d = np.zeros(num_patients, dtype=np.float32)
    visits_60d = np.zeros(num_patients, dtype=np.float32)
    visits_90d = np.zeros(num_patients, dtype=np.float32)
    length_of_stay = np.zeros(num_patients, dtype=np.float32)
    discharge_disposition = np.zeros(num_patients, dtype=np.float32)
    specialty = np.zeros(num_patients, dtype=np.float32)
    
    # Initialize labels
    labels = np.zeros(num_patients, dtype=np.int32)
    
    # Generate each patient
    for i in range(num_patients):
        # Assign conditions (with some correlation)
        base_sick = rng.random()  # Overall sickness level
        
        # Heart failure (10% prevalence, higher in sicker patients)
        hf = 1.0 if rng.random() < (0.10 + base_sick * 0.15) else 0.0
        has_heart_failure[i] = hf
        
        # Diabetes (15% prevalence, slight correlation with HF)
        dm = 1.0 if rng.random() < (0.15 + hf * 0.10) else 0.0
        has_diabetes[i] = dm
        
        # COPD (8% prevalence)
        copd = 1.0 if rng.random() < (0.08 + base_sick * 0.08) else 0.0
        has_copd[i] = copd
        
        # Pneumonia (5% prevalence, higher with COPD)
        pna = 1.0 if rng.random() < (0.05 + copd * 0.15) else 0.0
        has_pneumonia[i] = pna
        
        # Number of diagnoses (correlated with conditions)
        base_dx = 3 + int(hf * 2 + dm * 2 + copd * 2 + pna * 1)
        num_diagnoses[i] = min(15, max(1, base_dx + rng.integers(-2, 4)))
        
        # Comorbidity index (based on conditions)
        ci = int(hf) + int(dm) + int(copd)
        # Add some random severe comorbidities
        if rng.random() < 0.05:  # Cancer
            ci += 2
        if rng.random() < 0.03:  # Renal
            ci += 2
        if rng.random() < 0.02:  # Liver
            ci += 2
        comorbidity_index[i] = min(9, ci)
        
        # Determine primary condition for distributions
        if hf:
            condition = "heart_failure"
        elif copd:
            condition = "copd"
        elif pna:
            condition = "pneumonia"
        elif dm:
            condition = "diabetes"
        else:
            condition = "baseline"
        
        # Length of stay
        los_mean, los_std = LOS_DISTRIBUTIONS[condition]
        los = max(1, int(rng.normal(los_mean, los_std)))
        length_of_stay[i] = min(30, los)
        
        # Prior visits (correlated with chronic conditions)
        visit_mean, visit_std = VISIT_DISTRIBUTIONS.get(
            condition, VISIT_DISTRIBUTIONS["baseline"]
        )
        v30 = max(0, int(rng.normal(visit_mean, visit_std)))
        v60 = v30 + max(0, int(rng.normal(visit_mean * 0.5, visit_std * 0.5)))
        v90 = v60 + max(0, int(rng.normal(visit_mean * 0.3, visit_std * 0.3)))
        
        visits_30d[i] = min(5, v30)
        visits_60d[i] = min(8, v60)
        visits_90d[i] = min(12, v90)
        
        # Discharge disposition (weighted by condition severity)
        # 0=home, 1=home_health, 2=snf, 3=rehab, 4=ltach, 5=hospice, 6=ama
        if rng.random() < 0.6:
            disp = 0  # Home
        elif rng.random() < 0.3:
            disp = 1  # Home health
        elif rng.random() < 0.5:
            disp = 2 if hf or copd else 0  # SNF
        elif rng.random() < 0.1:
            disp = 6  # AMA (high risk)
        else:
            disp = rng.integers(0, 5)
        discharge_disposition[i] = disp
        
        # Specialty (weighted by condition)
        if hf:
            spec = 2 if rng.random() < 0.6 else 6  # Cardiology or hospitalist
        elif copd or pna:
            spec = 3 if rng.random() < 0.4 else 6  # Pulmonology or hospitalist
        else:
            spec = rng.choice([0, 1, 6, 8])  # IM, FM, hospitalist, ED
        specialty[i] = spec
        
        # Calculate readmission probability
        base_rate = CONDITION_READMISSION_RATES[condition]
        
        # Modifiers
        if v30 > 2:
            base_rate += 0.10  # High prior utilization
        if los > 7:
            base_rate += 0.05  # Long LOS
        if disp == 6:  # AMA
            base_rate += 0.20  # Against medical advice
        if ci >= 3:
            base_rate += 0.08  # High comorbidity
        
        # Cap at 0.95
        final_rate = min(0.95, base_rate)
        
        # Assign label
        labels[i] = 1 if rng.random() < final_rate else 0
    
    # Stack features into matrix
    X = np.column_stack([
        num_diagnoses,
        has_heart_failure,
        has_diabetes,
        has_copd,
        has_pneumonia,
        comorbidity_index,
        visits_30d,
        visits_60d,
        visits_90d,
        length_of_stay,
        discharge_disposition,
        specialty,
    ])
    
    actual_readmission_rate = labels.mean()
    logger.info(
        f"Generated {num_patients} encounters, "
        f"readmission rate: {actual_readmission_rate:.1%}"
    )
    
    return X, labels


def generate_high_risk_patient() -> np.ndarray:
    """
    Generate a single high-risk patient feature vector.
    
    Useful for testing high-risk prediction scenarios.
    
    Returns:
        Feature array (12,)
    """
    return np.array([
        8.0,   # num_diagnoses
        1.0,   # has_heart_failure
        1.0,   # has_diabetes
        1.0,   # has_copd
        0.0,   # has_pneumonia
        5.0,   # comorbidity_index
        3.0,   # visits_30d
        5.0,   # visits_60d
        7.0,   # visits_90d
        9.0,   # length_of_stay
        2.0,   # discharge_disposition (SNF)
        2.0,   # specialty (cardiology)
    ], dtype=np.float32)


def generate_low_risk_patient() -> np.ndarray:
    """
    Generate a single low-risk patient feature vector.
    
    Useful for testing low-risk prediction scenarios.
    
    Returns:
        Feature array (12,)
    """
    return np.array([
        2.0,   # num_diagnoses
        0.0,   # has_heart_failure
        0.0,   # has_diabetes
        0.0,   # has_copd
        0.0,   # has_pneumonia
        0.0,   # comorbidity_index
        0.0,   # visits_30d
        0.0,   # visits_60d
        0.0,   # visits_90d
        2.0,   # length_of_stay
        0.0,   # discharge_disposition (home)
        1.0,   # specialty (family medicine)
    ], dtype=np.float32)


def get_feature_statistics(X: np.ndarray) -> dict:
    """
    Calculate summary statistics for feature matrix.
    
    Args:
        X: Feature matrix (N, 12)
        
    Returns:
        Dictionary with min, max, mean, std per feature
    """
    from phoenix_guardian.ml.readmission_model import ReadmissionModel
    
    stats = {}
    for i, name in enumerate(ReadmissionModel.FEATURE_NAMES):
        stats[name] = {
            "min": float(X[:, i].min()),
            "max": float(X[:, i].max()),
            "mean": float(X[:, i].mean()),
            "std": float(X[:, i].std()),
        }
    
    return stats


# =============================================================================
# Module Entry Point
# =============================================================================


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Generate sample data
    X, y = generate_patient_encounters(num_patients=2000, seed=42)
    
    logger.info(f"X shape: {X.shape}")
    logger.info(f"y shape: {y.shape}")
    logger.info(f"Readmission rate: {y.mean():.1%}")
    
    # Show feature statistics
    stats = get_feature_statistics(X)
    for name, s in stats.items():
        logger.info(f"{name}: min={s['min']:.1f}, max={s['max']:.1f}, mean={s['mean']:.2f}")
    
    # Show sample high/low risk patients
    high_risk = generate_high_risk_patient()
    low_risk = generate_low_risk_patient()
    logger.info(f"High-risk patient features: {high_risk}")
    logger.info(f"Low-risk patient features: {low_risk}")
