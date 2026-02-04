"""
Phoenix Guardian - Feature Engineering Tests.

Comprehensive tests for clinical feature extraction for
readmission prediction.

Test Coverage:
- EncounterRecord validation
- Condition code detection (HF, DM, COPD, Pneumonia)
- Comorbidity index calculation
- Prior visit counting
- Discharge/specialty encoding
- Feature extraction pipeline
- Array conversion
"""

import pytest
from datetime import datetime, timedelta
from typing import List

from phoenix_guardian.ml.feature_engineering import (
    EncounterRecord,
    PatientFeatures,
    compute_comorbidity_index,
    count_prior_visits,
    encode_discharge_disposition,
    encode_specialty,
    extract_features,
    features_to_array,
    array_to_features,
    has_condition_codes,
    validate_features,
    HEART_FAILURE_CODES,
    DIABETES_CODES,
    COPD_CODES,
    PNEUMONIA_CODES,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_encounter() -> EncounterRecord:
    """Create a sample encounter record."""
    return EncounterRecord(
        patient_id="P001",
        encounter_id="E001",
        encounter_date=datetime(2026, 1, 15),
        discharge_disposition="home",
        diagnosis_codes=["I50.9", "E11.9"],  # HF + DM
        procedure_codes=["99213"],
        length_of_stay_days=5,
        attending_specialty="cardiology",
    )


@pytest.fixture
def patient_history() -> List[EncounterRecord]:
    """Create sample patient history."""
    base_date = datetime(2026, 1, 15)
    
    return [
        EncounterRecord(
            patient_id="P001",
            encounter_id="E000",
            encounter_date=base_date - timedelta(days=10),  # Within 30 days
            discharge_disposition="home",
            diagnosis_codes=["I50.9"],
            length_of_stay_days=3,
        ),
        EncounterRecord(
            patient_id="P001",
            encounter_id="E-1",
            encounter_date=base_date - timedelta(days=45),  # Within 60 days
            discharge_disposition="home_health",
            diagnosis_codes=["E11.9"],
            length_of_stay_days=2,
        ),
        EncounterRecord(
            patient_id="P001",
            encounter_id="E-2",
            encounter_date=base_date - timedelta(days=75),  # Within 90 days
            discharge_disposition="home",
            diagnosis_codes=["J44.9"],
            length_of_stay_days=4,
        ),
        EncounterRecord(
            patient_id="P001",
            encounter_id="E-3",
            encounter_date=base_date - timedelta(days=120),  # Outside 90 days
            discharge_disposition="home",
            diagnosis_codes=["J18.9"],
            length_of_stay_days=5,
        ),
        # Different patient (should be excluded)
        EncounterRecord(
            patient_id="P002",
            encounter_id="E100",
            encounter_date=base_date - timedelta(days=5),
            discharge_disposition="home",
            diagnosis_codes=["I50.9"],
            length_of_stay_days=3,
        ),
    ]


# =============================================================================
# EncounterRecord Tests
# =============================================================================


class TestEncounterRecord:
    """Tests for EncounterRecord dataclass."""
    
    def test_create_valid_encounter(self) -> None:
        """Test creating a valid encounter."""
        encounter = EncounterRecord(
            patient_id="P001",
            encounter_id="E001",
            encounter_date=datetime(2026, 1, 15),
            discharge_disposition="home",
        )
        
        assert encounter.patient_id == "P001"
        assert encounter.encounter_id == "E001"
        assert encounter.length_of_stay_days == 1  # Default
    
    def test_reject_empty_patient_id(self) -> None:
        """Test that empty patient_id is rejected."""
        with pytest.raises(ValueError, match="patient_id is required"):
            EncounterRecord(
                patient_id="",
                encounter_id="E001",
                encounter_date=datetime(2026, 1, 15),
                discharge_disposition="home",
            )
    
    def test_reject_empty_encounter_id(self) -> None:
        """Test that empty encounter_id is rejected."""
        with pytest.raises(ValueError, match="encounter_id is required"):
            EncounterRecord(
                patient_id="P001",
                encounter_id="",
                encounter_date=datetime(2026, 1, 15),
                discharge_disposition="home",
            )
    
    def test_reject_negative_los(self) -> None:
        """Test that negative LOS is rejected."""
        with pytest.raises(ValueError, match="cannot be negative"):
            EncounterRecord(
                patient_id="P001",
                encounter_id="E001",
                encounter_date=datetime(2026, 1, 15),
                discharge_disposition="home",
                length_of_stay_days=-1,
            )


# =============================================================================
# Condition Detection Tests
# =============================================================================


class TestConditionDetection:
    """Tests for condition code detection."""
    
    def test_detect_heart_failure(self) -> None:
        """Test heart failure detection."""
        hf_codes = ["I50.9", "I50.21", "I50.42"]
        
        for code in hf_codes:
            assert has_condition_codes([code], HEART_FAILURE_CODES), f"{code} not detected"
    
    def test_detect_diabetes(self) -> None:
        """Test diabetes detection."""
        dm_codes = ["E10.9", "E11.65", "E13.9"]
        
        for code in dm_codes:
            assert has_condition_codes([code], DIABETES_CODES), f"{code} not detected"
    
    def test_detect_copd(self) -> None:
        """Test COPD detection."""
        copd_codes = ["J44.0", "J44.1", "J44.9"]
        
        for code in copd_codes:
            assert has_condition_codes([code], COPD_CODES), f"{code} not detected"
    
    def test_detect_pneumonia(self) -> None:
        """Test pneumonia detection."""
        pna_codes = ["J18.9", "J15.9", "J13"]
        
        for code in pna_codes:
            assert has_condition_codes([code], PNEUMONIA_CODES), f"{code} not detected"
    
    def test_no_false_positives(self) -> None:
        """Test that unrelated codes are not detected."""
        unrelated = ["Z00.00", "M54.5", "R50.9"]  # Well visit, back pain, fever
        
        assert not has_condition_codes(unrelated, HEART_FAILURE_CODES)
        assert not has_condition_codes(unrelated, DIABETES_CODES)
        assert not has_condition_codes(unrelated, COPD_CODES)
        assert not has_condition_codes(unrelated, PNEUMONIA_CODES)
    
    def test_case_insensitive(self) -> None:
        """Test case insensitivity."""
        assert has_condition_codes(["i50.9"], HEART_FAILURE_CODES)
        assert has_condition_codes(["I50.9"], HEART_FAILURE_CODES)


# =============================================================================
# Comorbidity Index Tests
# =============================================================================


class TestComorbidityIndex:
    """Tests for comorbidity index calculation."""
    
    def test_empty_codes(self) -> None:
        """Test with no diagnosis codes."""
        score = compute_comorbidity_index([])
        assert score == 0
    
    def test_single_condition(self) -> None:
        """Test with single 1-point condition."""
        # Heart failure = 1 point
        score = compute_comorbidity_index(["I50.9"])
        assert score == 1
    
    def test_multiple_conditions(self) -> None:
        """Test with multiple conditions."""
        # HF (1) + DM (1) + COPD (1) = 3
        codes = ["I50.9", "E11.9", "J44.9"]
        score = compute_comorbidity_index(codes)
        assert score == 3
    
    def test_severe_conditions(self) -> None:
        """Test 2-point conditions."""
        # Cancer (C18) = 2 points
        score = compute_comorbidity_index(["C18.9"])
        assert score == 2
        
        # Renal (N18) = 2 points
        score = compute_comorbidity_index(["N18.3"])
        assert score == 2
        
        # Liver (K74) = 2 points
        score = compute_comorbidity_index(["K74.6"])
        assert score == 2
    
    def test_max_score(self) -> None:
        """Test maximum score scenario."""
        # HF + DM + COPD + Cancer + Liver + Renal = 1+1+1+2+2+2 = 9
        codes = ["I50.9", "E11.9", "J44.9", "C18.9", "K74.6", "N18.3"]
        score = compute_comorbidity_index(codes)
        assert score == 9


# =============================================================================
# Prior Visit Counting Tests
# =============================================================================


class TestPriorVisitCounting:
    """Tests for prior visit counting."""
    
    def test_count_30d_visits(self, patient_history: List[EncounterRecord]) -> None:
        """Test counting visits in 30-day window."""
        ref_date = datetime(2026, 1, 15)
        # Filter to P001 only (simulating pre-filtered history)
        p001_history = [e for e in patient_history if e.patient_id == "P001"]
        count = count_prior_visits(p001_history, ref_date, 30)
        
        # Only E000 is within 30 days for P001
        assert count == 1
    
    def test_count_60d_visits(self, patient_history: List[EncounterRecord]) -> None:
        """Test counting visits in 60-day window."""
        ref_date = datetime(2026, 1, 15)
        # Filter to P001 only (simulating pre-filtered history)
        p001_history = [e for e in patient_history if e.patient_id == "P001"]
        count = count_prior_visits(p001_history, ref_date, 60)
        
        # E000 (10d) and E-1 (45d) are within 60 days
        assert count == 2
    
    def test_count_90d_visits(self, patient_history: List[EncounterRecord]) -> None:
        """Test counting visits in 90-day window."""
        ref_date = datetime(2026, 1, 15)
        # Filter to P001 only (simulating pre-filtered history)
        p001_history = [e for e in patient_history if e.patient_id == "P001"]
        count = count_prior_visits(p001_history, ref_date, 90)
        
        # E000, E-1, E-2 are within 90 days
        assert count == 3
    
    def test_empty_history(self) -> None:
        """Test with no history."""
        count = count_prior_visits([], datetime(2026, 1, 15), 30)
        assert count == 0


# =============================================================================
# Encoding Tests
# =============================================================================


class TestEncoding:
    """Tests for categorical encoding."""
    
    def test_discharge_disposition_encoding(self) -> None:
        """Test discharge disposition encoding."""
        assert encode_discharge_disposition("home") == 0
        assert encode_discharge_disposition("home_health") == 1
        assert encode_discharge_disposition("snf") == 2
        assert encode_discharge_disposition("ama") == 6
        assert encode_discharge_disposition("unknown") == 8  # Default to "other"
    
    def test_discharge_case_insensitive(self) -> None:
        """Test case insensitivity."""
        assert encode_discharge_disposition("HOME") == 0
        assert encode_discharge_disposition("Home") == 0
    
    def test_specialty_encoding(self) -> None:
        """Test specialty encoding."""
        assert encode_specialty("internal_medicine") == 0
        assert encode_specialty("cardiology") == 2
        assert encode_specialty("pulmonology") == 3
        assert encode_specialty("hospitalist") == 6
        assert encode_specialty("unknown") == 9  # Default to "other"


# =============================================================================
# Feature Extraction Tests
# =============================================================================


class TestFeatureExtraction:
    """Tests for full feature extraction."""
    
    def test_extract_features_basic(
        self,
        sample_encounter: EncounterRecord,
        patient_history: List[EncounterRecord],
    ) -> None:
        """Test basic feature extraction."""
        features = extract_features(sample_encounter, patient_history)
        
        assert features.patient_id == "P001"
        assert features.num_diagnoses == 2
        assert features.has_heart_failure is True
        assert features.has_diabetes is True
        assert features.has_copd is False
        assert features.has_pneumonia is False
        assert features.length_of_stay == 5
        assert features.specialty_encoded == 2  # cardiology
    
    def test_extract_features_visits(
        self,
        sample_encounter: EncounterRecord,
        patient_history: List[EncounterRecord],
    ) -> None:
        """Test prior visit extraction."""
        features = extract_features(sample_encounter, patient_history)
        
        # Based on fixture: 1 visit in 30d, 2 in 60d, 3 in 90d
        assert features.visits_30d == 1
        assert features.visits_60d == 2
        assert features.visits_90d == 3
    
    def test_extract_features_no_history(
        self,
        sample_encounter: EncounterRecord,
    ) -> None:
        """Test extraction with no history."""
        features = extract_features(sample_encounter, [])
        
        assert features.visits_30d == 0
        assert features.visits_60d == 0
        assert features.visits_90d == 0


# =============================================================================
# Array Conversion Tests
# =============================================================================


class TestArrayConversion:
    """Tests for array conversion."""
    
    def test_features_to_array(self) -> None:
        """Test converting features to array."""
        features = PatientFeatures(
            patient_id="P001",
            num_diagnoses=5,
            has_heart_failure=True,
            has_diabetes=True,
            has_copd=False,
            has_pneumonia=False,
            comorbidity_index=3,
            visits_30d=2,
            visits_60d=3,
            visits_90d=4,
            length_of_stay=7,
            discharge_disposition_encoded=1,
            specialty_encoded=2,
        )
        
        array = features_to_array(features)
        
        assert len(array) == 12
        assert array[0] == 5.0  # num_diagnoses
        assert array[1] == 1.0  # has_heart_failure
        assert array[2] == 1.0  # has_diabetes
        assert array[3] == 0.0  # has_copd
        assert array[4] == 0.0  # has_pneumonia
        assert array[5] == 3.0  # comorbidity_index
    
    def test_array_to_features(self) -> None:
        """Test converting array back to features."""
        array = [5.0, 1.0, 1.0, 0.0, 0.0, 3.0, 2.0, 3.0, 4.0, 7.0, 1.0, 2.0]
        
        features = array_to_features("P001", array)
        
        assert features.patient_id == "P001"
        assert features.num_diagnoses == 5
        assert features.has_heart_failure is True
        assert features.has_diabetes is True
        assert features.comorbidity_index == 3
    
    def test_roundtrip(self) -> None:
        """Test roundtrip conversion."""
        original = PatientFeatures(
            patient_id="P001",
            num_diagnoses=8,
            has_heart_failure=True,
            has_diabetes=False,
            has_copd=True,
            has_pneumonia=True,
            comorbidity_index=5,
            visits_30d=3,
            visits_60d=5,
            visits_90d=7,
            length_of_stay=12,
            discharge_disposition_encoded=2,
            specialty_encoded=3,
        )
        
        array = features_to_array(original)
        restored = array_to_features(original.patient_id, array)
        
        assert restored.num_diagnoses == original.num_diagnoses
        assert restored.has_heart_failure == original.has_heart_failure
        assert restored.comorbidity_index == original.comorbidity_index
    
    def test_array_wrong_length(self) -> None:
        """Test array with wrong length."""
        with pytest.raises(ValueError, match="Expected 12 features"):
            array_to_features("P001", [1.0, 2.0, 3.0])


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidation:
    """Tests for feature validation."""
    
    def test_valid_features(self) -> None:
        """Test valid features pass validation."""
        features = PatientFeatures(
            patient_id="P001",
            num_diagnoses=5,
            comorbidity_index=3,
            length_of_stay=5,
            visits_30d=1,
            visits_60d=2,
            visits_90d=3,
        )
        
        warnings = validate_features(features)
        assert len(warnings) == 0
    
    def test_negative_values_warning(self) -> None:
        """Test negative values trigger warnings."""
        features = PatientFeatures(
            patient_id="P001",
            num_diagnoses=-1,
            comorbidity_index=-1,
            length_of_stay=-1,
        )
        
        warnings = validate_features(features)
        assert any("num_diagnoses is negative" in w for w in warnings)
        assert any("comorbidity_index is negative" in w for w in warnings)
        assert any("length_of_stay is negative" in w for w in warnings)
    
    def test_impossible_visits_warning(self) -> None:
        """Test impossible visit counts trigger warnings."""
        features = PatientFeatures(
            patient_id="P001",
            visits_30d=5,
            visits_60d=3,  # Less than 30d - impossible
            visits_90d=2,  # Less than 60d - impossible
        )
        
        warnings = validate_features(features)
        assert any("visits_30d > visits_60d" in w for w in warnings)
        assert any("visits_60d > visits_90d" in w for w in warnings)


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests."""
    
    def test_zero_length_of_stay(self) -> None:
        """Test zero LOS is allowed."""
        encounter = EncounterRecord(
            patient_id="P001",
            encounter_id="E001",
            encounter_date=datetime(2026, 1, 15),
            discharge_disposition="home",
            length_of_stay_days=0,
        )
        
        features = extract_features(encounter, [])
        assert features.length_of_stay == 0
    
    def test_many_diagnoses(self) -> None:
        """Test with many diagnosis codes."""
        codes = [f"Z{i:02d}.0" for i in range(50)]
        
        encounter = EncounterRecord(
            patient_id="P001",
            encounter_id="E001",
            encounter_date=datetime(2026, 1, 15),
            discharge_disposition="home",
            diagnosis_codes=codes,
        )
        
        features = extract_features(encounter, [])
        assert features.num_diagnoses == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
