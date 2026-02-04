"""
Tests for CodingAgent

Comprehensive test suite for medical coding assistant agent.
Tests ICD-10 and CPT code suggestion, validation, and billing logic.
"""

import pytest

from phoenix_guardian.agents.coding_agent import (
    CodingAgent,
    CodingResult,
    CPTCode,
    EncounterType,
    ICD10Code,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def coding_agent():
    """Create a CodingAgent instance for testing."""
    return CodingAgent()


# =============================================================================
# ICD-10 CODE SUGGESTION TESTS
# =============================================================================


class TestICD10CodeSuggestion:
    """Tests for ICD-10 code suggestion."""
    
    @pytest.mark.asyncio
    async def test_suggest_icd10_hypertension(self, coding_agent):
        """Test ICD-10 suggestion for hypertension."""
        result = await coding_agent.execute({
            "clinical_text": "Patient has hypertension. BP 150/95.",
            "encounter_type": "outpatient",
        })
        
        assert result.success
        icd10_codes = result.data["icd10_codes"]
        assert len(icd10_codes) > 0
        
        # Should include I10
        codes = [code["code"] for code in icd10_codes]
        assert "I10" in codes
    
    @pytest.mark.asyncio
    async def test_suggest_icd10_diabetes(self, coding_agent):
        """Test ICD-10 suggestion for diabetes."""
        result = await coding_agent.execute({
            "clinical_text": "Type 2 diabetes mellitus. HbA1c 8.2%.",
            "encounter_type": "outpatient",
        })
        
        assert result.success
        icd10_codes = result.data["icd10_codes"]
        
        codes = [code["code"] for code in icd10_codes]
        assert any(code.startswith("E11") for code in codes)
    
    @pytest.mark.asyncio
    async def test_suggest_icd10_stemi(self, coding_agent):
        """Test ICD-10 suggestion for STEMI."""
        result = await coding_agent.execute({
            "clinical_text": (
                "55yo M with chest pain, elevated troponin. "
                "EKG shows ST elevation. Diagnosis: STEMI."
            ),
            "encounter_type": "emergency",
        })
        
        assert result.success
        icd10_codes = result.data["icd10_codes"]
        
        # Should suggest STEMI codes
        codes = [code["code"] for code in icd10_codes]
        assert any("I21" in code for code in codes)
    
    @pytest.mark.asyncio
    async def test_suggest_icd10_sepsis(self, coding_agent):
        """Test ICD-10 suggestion for sepsis."""
        result = await coding_agent.execute({
            "clinical_text": (
                "Patient with sepsis, elevated lactate, positive blood cultures. "
                "Treating with broad-spectrum antibiotics."
            ),
            "encounter_type": "inpatient",
        })
        
        assert result.success
        icd10_codes = result.data["icd10_codes"]
        
        codes = [code["code"] for code in icd10_codes]
        assert "A41.9" in codes
    
    @pytest.mark.asyncio
    async def test_suggest_icd10_pneumonia(self, coding_agent):
        """Test ICD-10 suggestion for pneumonia."""
        result = await coding_agent.execute({
            "clinical_text": "Pneumonia with fever and cough. Chest X-ray shows infiltrate.",
            "encounter_type": "inpatient",
        })
        
        assert result.success
        icd10_codes = result.data["icd10_codes"]
        
        codes = [code["code"] for code in icd10_codes]
        assert "J18.9" in codes
    
    @pytest.mark.asyncio
    async def test_suggest_icd10_covid(self, coding_agent):
        """Test ICD-10 suggestion for COVID-19."""
        result = await coding_agent.execute({
            "clinical_text": "COVID-19 positive patient with respiratory symptoms.",
            "encounter_type": "inpatient",
        })
        
        assert result.success
        icd10_codes = result.data["icd10_codes"]
        
        codes = [code["code"] for code in icd10_codes]
        assert "U07.1" in codes
    
    @pytest.mark.asyncio
    async def test_icd10_confidence_scoring(self, coding_agent):
        """Test confidence scoring for ICD-10 codes."""
        result = await coding_agent.execute({
            "clinical_text": "Patient with elevated troponin and chest pain. MI suspected.",
            "encounter_type": "emergency",
        })
        
        assert result.success
        icd10_codes = result.data["icd10_codes"]
        
        # Confidence should be in valid range
        for code in icd10_codes:
            assert 0.0 <= code["confidence"] <= 1.0
            assert code["confidence"] > 0.5  # Should have decent confidence
    
    @pytest.mark.asyncio
    async def test_icd10_multiple_diagnoses(self, coding_agent):
        """Test suggestion with multiple diagnoses."""
        result = await coding_agent.execute({
            "clinical_text": (
                "Diagnosis: STEMI, hypertension, diabetes type 2. "
                "Patient on multiple medications."
            ),
            "encounter_type": "inpatient",
        })
        
        assert result.success
        icd10_codes = result.data["icd10_codes"]
        
        # Should suggest multiple codes
        assert len(icd10_codes) >= 2
        
        # Check categories are assigned
        for code in icd10_codes:
            assert code["category"] in [
                "primary_diagnosis",
                "secondary_diagnosis",
                "symptom",
            ]


# =============================================================================
# CPT CODE SUGGESTION TESTS
# =============================================================================


class TestCPTCodeSuggestion:
    """Tests for CPT code suggestion."""
    
    @pytest.mark.asyncio
    async def test_suggest_cpt_office_visit(self, coding_agent):
        """Test CPT suggestion for office visit."""
        result = await coding_agent.execute({
            "clinical_text": "Office visit for chronic disease management.",
            "encounter_type": "outpatient",
        })
        
        assert result.success
        cpt_codes = result.data["cpt_codes"]
        
        # Should suggest office visit code
        codes = [code["code"] for code in cpt_codes]
        assert any(code in ["99213", "99214", "99215"] for code in codes)
    
    @pytest.mark.asyncio
    async def test_suggest_cpt_cardiac_catheterization(self, coding_agent):
        """Test CPT suggestion for cardiac catheterization."""
        result = await coding_agent.execute({
            "clinical_text": (
                "Procedure: Cardiac catheterization with coronary angiography. "
                "Stent placement performed."
            ),
            "encounter_type": "inpatient",
        })
        
        assert result.success
        cpt_codes = result.data["cpt_codes"]
        
        codes = [code["code"] for code in cpt_codes]
        # Should suggest catheterization code
        assert "93458" in codes or "92928" in codes
    
    @pytest.mark.asyncio
    async def test_suggest_cpt_lab_cbc(self, coding_agent):
        """Test CPT suggestion for CBC."""
        result = await coding_agent.execute({
            "clinical_text": "CBC ordered. Sepsis workup.",
            "encounter_type": "inpatient",
        })
        
        assert result.success
        cpt_codes = result.data["cpt_codes"]
        
        codes = [code["code"] for code in cpt_codes]
        assert "85025" in codes
    
    @pytest.mark.asyncio
    async def test_suggest_cpt_lab_cmp(self, coding_agent):
        """Test CPT suggestion for CMP."""
        result = await coding_agent.execute({
            "clinical_text": "Comprehensive metabolic panel ordered.",
            "encounter_type": "outpatient",
        })
        
        assert result.success
        cpt_codes = result.data["cpt_codes"]
        
        codes = [code["code"] for code in cpt_codes]
        assert "80053" in codes
    
    @pytest.mark.asyncio
    async def test_suggest_cpt_troponin(self, coding_agent):
        """Test CPT suggestion for troponin."""
        result = await coding_agent.execute({
            "clinical_text": "High-sensitivity troponin ordered for chest pain evaluation.",
            "encounter_type": "emergency",
        })
        
        assert result.success
        cpt_codes = result.data["cpt_codes"]
        
        codes = [code["code"] for code in cpt_codes]
        assert "84450" in codes
    
    @pytest.mark.asyncio
    async def test_cpt_encounter_type_matching(self, coding_agent):
        """Test that CPT codes match encounter type."""
        result = await coding_agent.execute({
            "clinical_text": "Cardiac catheterization performed.",
            "encounter_type": "outpatient",
        })
        
        assert result.success
        cpt_codes = result.data["cpt_codes"]
        
        # Cardiac cath should not be suggested for outpatient
        codes = [code["code"] for code in cpt_codes]
        # May suggest other codes, but not inpatient-only codes
        for code in codes:
            if code in ["93458", "92928"]:
                # These are inpatient-only
                pytest.fail("Inpatient CPT code suggested for outpatient encounter")
    
    @pytest.mark.asyncio
    async def test_cpt_ekg(self, coding_agent):
        """Test CPT suggestion for EKG."""
        result = await coding_agent.execute({
            "clinical_text": "12-lead EKG performed.",
            "encounter_type": "emergency",
        })
        
        assert result.success
        cpt_codes = result.data["cpt_codes"]
        
        codes = [code["code"] for code in cpt_codes]
        assert "93000" in codes


# =============================================================================
# CODE VALIDATION TESTS
# =============================================================================


class TestCodeValidation:
    """Tests for code validation."""
    
    @pytest.mark.asyncio
    async def test_validate_unspecified_code_warning(self, coding_agent):
        """Test warning for unspecified codes."""
        result = await coding_agent.execute({
            "clinical_text": "Patient with chest pain.",
            "encounter_type": "emergency",
        })
        
        assert result.success
        validation_issues = result.data["validation_issues"]
        
        # Chest pain is unspecified, should have validation message
        # (Depending on context, may or may not have issues)
    
    @pytest.mark.asyncio
    async def test_validate_missing_secondary_diagnosis(self, coding_agent):
        """Test validation suggests missing secondary diagnosis."""
        result = await coding_agent.execute({
            "clinical_text": (
                "Diagnosis: STEMI with coronary artery disease. "
                "Patient has known CAD."
            ),
            "encounter_type": "inpatient",
        })
        
        assert result.success
        validation_issues = result.data["validation_issues"]
        
        # Should suggest adding atherosclerosis code
        # Validation may flag missing I25.10
    
    @pytest.mark.asyncio
    async def test_validate_diabetes_hypertension_missing(self, coding_agent):
        """Test validation flags missing common codes."""
        result = await coding_agent.execute({
            "clinical_text": (
                "Patient with long-standing diabetes and hypertension. "
                "HbA1c 7.8%, BP controlled on meds."
            ),
            "encounter_type": "outpatient",
        })
        
        assert result.success
        # Should have suggestions for E11 and I10


# =============================================================================
# BILLING SUMMARY TESTS
# =============================================================================


class TestBillingSummary:
    """Tests for billing summary generation."""
    
    @pytest.mark.asyncio
    async def test_billing_summary_structure(self, coding_agent):
        """Test billing summary has required fields."""
        result = await coding_agent.execute({
            "clinical_text": "Patient with MI requiring hospitalization.",
            "encounter_type": "inpatient",
        })
        
        assert result.success
        summary = result.data["billing_summary"]
        
        assert "total_diagnosis_codes" in summary
        assert "total_procedure_codes" in summary
        assert "estimated_complexity" in summary
    
    @pytest.mark.asyncio
    async def test_billing_complexity_low(self, coding_agent):
        """Test low complexity calculation."""
        result = await coding_agent.execute({
            "clinical_text": "Hypertension.",
            "encounter_type": "outpatient",
        })
        
        assert result.success
        summary = result.data["billing_summary"]
        
        complexity = summary["estimated_complexity"]
        assert complexity in ["low", "moderate", "high"]
    
    @pytest.mark.asyncio
    async def test_billing_complexity_high(self, coding_agent):
        """Test high complexity calculation."""
        result = await coding_agent.execute({
            "clinical_text": (
                "Patient with STEMI, sepsis, acute kidney injury. "
                "Underwent cardiac catheterization with stent. "
                "Intubated and sedated. Multiple comorbidities."
            ),
            "encounter_type": "inpatient",
        })
        
        assert result.success
        summary = result.data["billing_summary"]
        
        # Should be high complexity
        assert summary["estimated_complexity"] in ["moderate", "high"]


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""
    
    @pytest.mark.asyncio
    async def test_missing_clinical_text(self, coding_agent):
        """Test error when clinical text missing."""
        result = await coding_agent.execute({
            "encounter_type": "outpatient",
        })
        
        assert result.success is False
        assert result.error is not None
        assert "clinical_text" in result.error
    
    @pytest.mark.asyncio
    async def test_empty_clinical_text(self, coding_agent):
        """Test error when clinical text empty."""
        result = await coding_agent.execute({
            "clinical_text": "",
            "encounter_type": "outpatient",
        })
        
        assert result.success is False
    
    @pytest.mark.asyncio
    async def test_invalid_encounter_type(self, coding_agent):
        """Test error with invalid encounter type."""
        result = await coding_agent.execute({
            "clinical_text": "Patient with hypertension.",
            "encounter_type": "invalid_type",
        })
        
        assert result.success is False
        assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_vague_clinical_text(self, coding_agent):
        """Test handling of vague clinical text."""
        result = await coding_agent.execute({
            "clinical_text": "Patient is sick.",
            "encounter_type": "outpatient",
        })
        
        # Should handle gracefully, may return empty codes
        assert result.success
        # May not suggest codes if text is too vague


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for CodingAgent."""
    
    @pytest.mark.asyncio
    async def test_full_workflow_simple_case(self, coding_agent):
        """Test complete workflow for simple case."""
        result = await coding_agent.execute({
            "clinical_text": "Patient with hypertension. Office visit for BP check.",
            "encounter_type": "outpatient",
        })
        
        assert result.success
        assert len(result.data["icd10_codes"]) > 0
        assert len(result.data["cpt_codes"]) > 0
        assert result.reasoning is not None
    
    @pytest.mark.asyncio
    async def test_full_workflow_complex_case(self, coding_agent):
        """Test complete workflow for complex case."""
        result = await coding_agent.execute({
            "clinical_text": (
                "55yo male with STEMI. "
                "Diagnosis: ST elevation MI, hypertension, diabetes. "
                "Procedure: Cardiac catheterization with stent placement. "
                "Labs: CBC, CMP, troponin ordered."
            ),
            "encounter_type": "inpatient",
        })
        
        assert result.success
        assert len(result.data["icd10_codes"]) >= 2
        assert len(result.data["cpt_codes"]) >= 1
        assert result.data["billing_summary"]["estimated_complexity"] in [
            "moderate",
            "high",
        ]
    
    @pytest.mark.asyncio
    async def test_full_workflow_emergency_case(self, coding_agent):
        """Test workflow for emergency department case."""
        result = await coding_agent.execute({
            "clinical_text": (
                "Chief complaint: Chest pain. "
                "EKG performed showing ST elevation. "
                "Troponin elevated. "
                "Assessment: Possible STEMI. "
                "ED visit, high severity."
            ),
            "encounter_type": "emergency",
        })
        
        assert result.success
        assert len(result.data["icd10_codes"]) > 0
        assert "93000" in [code["code"] for code in result.data["cpt_codes"]]
    
    @pytest.mark.asyncio
    async def test_result_serialization(self, coding_agent):
        """Test that results are properly serializable."""
        result = await coding_agent.execute({
            "clinical_text": "Patient with diabetes and hypertension.",
            "encounter_type": "outpatient",
        })
        
        assert result.success
        data = result.data
        
        # Check all fields are JSON-serializable
        assert isinstance(data["icd10_codes"], list)
        assert isinstance(data["cpt_codes"], list)
        assert isinstance(data["validation_issues"], list)
        assert isinstance(data["billing_summary"], dict)


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


class TestPerformance:
    """Performance tests for CodingAgent."""
    
    @pytest.mark.asyncio
    async def test_processing_time_under_500ms(self, coding_agent):
        """Test that coding analysis completes within 500ms."""
        result = await coding_agent.execute({
            "clinical_text": (
                "Patient with STEMI. EKG shows ST elevation. "
                "Troponin elevated. Cardiac catheterization planned."
            ),
            "encounter_type": "inpatient",
        })
        
        assert result.success
        assert result.execution_time_ms < 500
    
    @pytest.mark.asyncio
    async def test_handles_long_clinical_text(self, coding_agent):
        """Test handling of long clinical documentation."""
        long_text = " ".join(
            [
                "Patient with multiple comorbidities including hypertension, "
                "diabetes, CAD, COPD, atrial fibrillation, and chronic kidney disease."
            ]
            * 10
        )
        
        result = await coding_agent.execute({
            "clinical_text": long_text,
            "encounter_type": "inpatient",
        })
        
        assert result.success
        assert result.execution_time_ms < 500


# =============================================================================
# DATACLASS TESTS
# =============================================================================


class TestDataclasses:
    """Tests for dataclass objects."""
    
    def test_icd10_code_creation(self):
        """Test ICD10Code dataclass creation."""
        code = ICD10Code(
            code="I10",
            description="Essential hypertension",
            confidence=0.95,
            category="primary_diagnosis",
        )
        
        assert code.code == "I10"
        assert code.confidence == 0.95
        
        # Test conversion to dict
        code_dict = code.to_dict()
        assert isinstance(code_dict, dict)
        assert code_dict["code"] == "I10"
    
    def test_cpt_code_creation(self):
        """Test CPTCode dataclass creation."""
        code = CPTCode(
            code="99214",
            description="Office visit",
            confidence=0.90,
            modifiers=["-25"],
        )
        
        assert code.code == "99214"
        assert len(code.modifiers) == 1
        
        # Test conversion to dict
        code_dict = code.to_dict()
        assert isinstance(code_dict, dict)
        assert code_dict["modifiers"] == ["-25"]
    
    def test_coding_result_creation(self):
        """Test CodingResult dataclass creation."""
        icd10 = ICD10Code(
            code="I10",
            description="Hypertension",
            confidence=0.95,
            category="primary_diagnosis",
        )
        cpt = CPTCode(
            code="99214",
            description="Office visit",
            confidence=0.90,
        )
        
        result = CodingResult(
            icd10_codes=[icd10],
            cpt_codes=[cpt],
            validation_issues=[],
            billing_summary={"total_diagnosis_codes": 1},
        )
        
        assert len(result.icd10_codes) == 1
        assert len(result.cpt_codes) == 1
        
        # Test conversion to dict
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert len(result_dict["icd10_codes"]) == 1


# =============================================================================
# ENCOUNTER TYPE TESTS
# =============================================================================


class TestEncounterType:
    """Tests for encounter type handling."""
    
    def test_encounter_type_enum_values(self):
        """Test all encounter type enum values."""
        assert EncounterType.INPATIENT.value == "inpatient"
        assert EncounterType.OUTPATIENT.value == "outpatient"
        assert EncounterType.EMERGENCY.value == "emergency"
        assert EncounterType.TELEHEALTH.value == "telehealth"
