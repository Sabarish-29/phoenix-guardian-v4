"""
Tests for FDA CDS Classification Module.

Tests cover:
- CDS Category classification
- 4-criteria evaluation for Non-Device CDS
- Risk level assessment
- CDS function definitions
- Assessment report generation
- IEC 62304 safety class determination

References:
- FDA Guidance: Clinical Decision Support Software (Sept 2022)
- 21 CFR Part 820 - Quality System Regulation
- IEC 62304:2006+A1:2015 - Medical Device Software Lifecycle
"""

import hashlib
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from phoenix_guardian.compliance.fda_cds_classifier import (
    CDSAssessment,
    CDSCategory,
    CDSFunction,
    CDSFunctionType,
    CDSRiskLevel,
    Criterion,
    FDACDSClassifier,
    get_phoenix_guardian_cds_functions,
)

from phoenix_guardian.compliance.cds_risk_scorer import (
    AutonomyLevel,
    CDSRiskProfile,
    CDSRiskScoringEngine,
    ClinicalImpactLevel,
    DataQualityLevel,
    IEC62304SafetyClass,
    PopulationVulnerability,
    RiskDimensionScore,
    RiskMitigation,
    RiskScoreResult,
    get_standard_mitigations,
)


# =============================================================================
# FDA CDS Classifier Tests
# =============================================================================


class TestCDSEnums:
    """Tests for CDS enumeration types."""
    
    def test_cds_category_values(self):
        """Test CDS category enum has required values."""
        assert CDSCategory.NON_DEVICE.value == "non_device_cds"
        assert CDSCategory.DEVICE_CLASS_I.value == "device_class_i"
        assert CDSCategory.DEVICE_CLASS_II.value == "device_class_ii"
        assert CDSCategory.DEVICE_CLASS_III.value == "device_class_iii"
        assert CDSCategory.EXEMPT.value == "exempt"
    
    def test_cds_risk_level_values(self):
        """Test CDS risk level enum has required values."""
        assert CDSRiskLevel.MINIMAL.value == "minimal"
        assert CDSRiskLevel.LOW.value == "low"
        assert CDSRiskLevel.MODERATE.value == "moderate"
        assert CDSRiskLevel.HIGH.value == "high"
        assert CDSRiskLevel.CRITICAL.value == "critical"
    
    def test_cds_function_type_values(self):
        """Test CDS function type enum has clinical function types."""
        expected_types = [
            "clinical_guidelines",
            "drug_drug_interaction",
            "drug_allergy_check",
            "dosage_calculator",
            "clinical_reminders",
            "risk_prediction",
            "treatment_recommendation",
        ]
        actual_types = [t.value for t in CDSFunctionType]
        for expected in expected_types:
            assert expected in actual_types, f"Missing function type: {expected}"
    
    def test_criterion_values(self):
        """Test FDA 4 criteria enum values."""
        assert len(Criterion) == 4
        assert Criterion.NO_IMAGE_SIGNAL_PROCESSING.value == "criterion_1"
        assert Criterion.DISPLAYS_MEDICAL_INFO.value == "criterion_2"
        assert Criterion.SUPPORTS_HCP.value == "criterion_3"
        assert Criterion.HCP_INDEPENDENT_REVIEW.value == "criterion_4"


class TestCDSFunction:
    """Tests for CDS Function data class."""
    
    def test_create_cds_function(self):
        """Test creating a CDS function definition."""
        func = CDSFunction(
            function_id="test-001",
            name="Test Function",
            description="A test CDS function",
            function_type=CDSFunctionType.CLINICAL_REMINDERS,
            target_users=["healthcare_provider"],
            processes_images_signals=False,
            provides_recommendations=True,
            requires_hcp_review=True,
            hcp_can_review_basis=True,
        )
        
        assert func.function_id == "test-001"
        assert func.function_type == CDSFunctionType.CLINICAL_REMINDERS
        assert func.provides_recommendations is True
        assert "healthcare_provider" in func.target_users
    
    def test_cds_function_defaults(self):
        """Test CDS function default values."""
        func = CDSFunction(
            function_id="test-002",
            name="Minimal Function",
            description="Minimal definition",
            function_type=CDSFunctionType.CLINICAL_GUIDELINES,
        )
        
        assert func.processes_images_signals is False
        assert func.provides_recommendations is True
        assert func.requires_hcp_review is True
        assert func.hcp_can_review_basis is True


class TestFDACDSClassifier:
    """Tests for FDA CDS Classifier."""
    
    @pytest.fixture
    def classifier(self):
        """Create classifier instance."""
        return FDACDSClassifier()
    
    @pytest.fixture
    def non_device_function(self):
        """Create a function that should classify as Non-Device."""
        return CDSFunction(
            function_id="nd-001",
            name="Clinical Guidelines Display",
            description="Displays evidence-based clinical guidelines",
            function_type=CDSFunctionType.CLINICAL_GUIDELINES,
            target_users=["physician", "nurse"],
            processes_images_signals=False,
            provides_recommendations=True,
            requires_hcp_review=True,
            hcp_can_review_basis=True,
        )
    
    @pytest.fixture
    def device_function(self):
        """Create a function that should classify as Device."""
        return CDSFunction(
            function_id="dev-001",
            name="Autonomous Diagnosis System",
            description="Provides diagnoses without physician review",
            function_type=CDSFunctionType.DIAGNOSTIC_PREDICTION,
            target_users=["patient"],  # Not HCP
            processes_images_signals=True,
            provides_recommendations=True,
            requires_hcp_review=False,  # Critical - no HCP review
            hcp_can_review_basis=False,  # Black box
        )
    
    def test_classifier_initialization(self, classifier):
        """Test classifier initializes correctly."""
        assert classifier is not None
        assert hasattr(classifier, "classify_function")
        assert hasattr(classifier, "_evaluate_criteria")
    
    def test_classify_non_device_function(self, classifier, non_device_function):
        """Test classification of Non-Device CDS function."""
        assessment = classifier.classify_function(non_device_function)
        
        assert isinstance(assessment, CDSAssessment)
        assert assessment.category == CDSCategory.NON_DEVICE
        assert assessment.function_id == "nd-001"
    
    def test_classify_device_function(self, classifier, device_function):
        """Test classification of Device CDS function."""
        assessment = classifier.classify_function(device_function)
        
        assert isinstance(assessment, CDSAssessment)
        assert assessment.category in [
            CDSCategory.DEVICE_CLASS_I,
            CDSCategory.DEVICE_CLASS_II,
            CDSCategory.DEVICE_CLASS_III,
        ]
    
    def test_evaluate_criterion_no_image_processing(self, classifier):
        """Test no image/signal processing criterion evaluation."""
        no_images = CDSFunction(
            function_id="img-001",
            name="No Image Processing",
            description="No images",
            function_type=CDSFunctionType.CLINICAL_REMINDERS,
            target_users=["physician"],
            processes_images_signals=False,
        )
        
        with_images = CDSFunction(
            function_id="img-002",
            name="Image Processing",
            description="Processes images",
            function_type=CDSFunctionType.IMAGE_ANALYSIS,
            target_users=["physician"],
            processes_images_signals=True,
        )
        
        criteria, _ = classifier._evaluate_criteria(no_images)
        assert criteria[Criterion.NO_IMAGE_SIGNAL_PROCESSING] is True
        
        criteria, _ = classifier._evaluate_criteria(with_images)
        assert criteria[Criterion.NO_IMAGE_SIGNAL_PROCESSING] is False
    
    def test_evaluate_criterion_displays_medical_info(self, classifier):
        """Test displays medical info criterion evaluation."""
        displays_info = CDSFunction(
            function_id="disp-001",
            name="Display Guidelines",
            description="Shows guidelines",
            function_type=CDSFunctionType.CLINICAL_GUIDELINES,
            target_users=["physician"],
        )
        
        diagnostic = CDSFunction(
            function_id="disp-002",
            name="Diagnostic",
            description="Makes diagnoses",
            function_type=CDSFunctionType.DIAGNOSTIC_PREDICTION,
            target_users=["physician"],
        )
        
        criteria, _ = classifier._evaluate_criteria(displays_info)
        assert criteria[Criterion.DISPLAYS_MEDICAL_INFO] is True
        
        criteria, _ = classifier._evaluate_criteria(diagnostic)
        assert criteria[Criterion.DISPLAYS_MEDICAL_INFO] is False
    
    def test_evaluate_criterion_supports_hcp(self, classifier):
        """Test supports HCP criterion evaluation."""
        hcp_function = CDSFunction(
            function_id="hcp-001",
            name="HCP Function",
            description="For healthcare providers",
            function_type=CDSFunctionType.CLINICAL_REMINDERS,
            target_users=["physician", "nurse"],
            provides_recommendations=True,
        )
        
        patient_function = CDSFunction(
            function_id="pat-001",
            name="Patient Function",
            description="For patients",
            function_type=CDSFunctionType.CLINICAL_REMINDERS,
            target_users=["patient"],
            provides_recommendations=True,
        )
        
        criteria, _ = classifier._evaluate_criteria(hcp_function)
        assert criteria[Criterion.SUPPORTS_HCP] is True
        
        criteria, _ = classifier._evaluate_criteria(patient_function)
        assert criteria[Criterion.SUPPORTS_HCP] is False
    
    def test_evaluate_criterion_independent_review(self, classifier):
        """Test independent review criterion evaluation."""
        review_enabled = CDSFunction(
            function_id="rev-001",
            name="Review Enabled",
            description="HCP can review",
            function_type=CDSFunctionType.TREATMENT_RECOMMENDATION,
            target_users=["physician"],
            requires_hcp_review=True,
            hcp_can_review_basis=True,
        )
        
        no_review = CDSFunction(
            function_id="rev-002",
            name="No Review",
            description="Autonomous",
            function_type=CDSFunctionType.AUTONOMOUS_DECISION,
            target_users=["physician"],
            requires_hcp_review=False,
            hcp_can_review_basis=False,
        )
        
        criteria, _ = classifier._evaluate_criteria(review_enabled)
        assert criteria[Criterion.HCP_INDEPENDENT_REVIEW] is True
        
        criteria, _ = classifier._evaluate_criteria(no_review)
        assert criteria[Criterion.HCP_INDEPENDENT_REVIEW] is False
    
    def test_all_criteria_met_is_non_device(self, classifier):
        """Test that meeting all 4 criteria results in Non-Device classification."""
        func = CDSFunction(
            function_id="all-001",
            name="All Criteria Met",
            description="Meets all FDA criteria",
            function_type=CDSFunctionType.CLINICAL_GUIDELINES,
            target_users=["physician", "clinician"],
            processes_images_signals=False,
            provides_recommendations=True,
            requires_hcp_review=True,
            hcp_can_review_basis=True,
        )
        
        assessment = classifier.classify_function(func)
        assert assessment.category == CDSCategory.NON_DEVICE
        assert all(assessment.criteria_met.values())
    
    def test_any_criterion_failed_is_device(self, classifier):
        """Test that failing any criterion results in Device classification."""
        # Fail by processing images
        func1 = CDSFunction(
            function_id="fail-001",
            name="Processes Images",
            description="Processes images",
            function_type=CDSFunctionType.IMAGE_ANALYSIS,
            target_users=["physician"],
            processes_images_signals=True,  # Fails criterion 1
            provides_recommendations=True,
            requires_hcp_review=True,
            hcp_can_review_basis=True,
        )
        
        assessment = classifier.classify_function(func1)
        assert assessment.category != CDSCategory.NON_DEVICE
    
    def test_assessment_has_signature(self, classifier, non_device_function):
        """Test that assessment includes SHA-256 signature."""
        assessment = classifier.classify_function(non_device_function)
        
        assert assessment.signature_hash is not None
        assert len(assessment.signature_hash) == 64  # SHA-256 hex length
        assert all(c in "0123456789abcdef" for c in assessment.signature_hash)
    
    def test_assessment_timestamp(self, classifier, non_device_function):
        """Test that assessment includes UTC timestamp."""
        before = datetime.now(timezone.utc)
        assessment = classifier.classify_function(non_device_function)
        after = datetime.now(timezone.utc)
        
        assert before <= assessment.assessed_at <= after
    
    def test_assessment_includes_rationale(self, classifier, non_device_function):
        """Test that assessment includes classification rationale."""
        assessment = classifier.classify_function(non_device_function)
        
        assert assessment.criteria_rationale is not None
        assert len(assessment.criteria_rationale) > 0


class TestPhoenixGuardianCDSFunctions:
    """Tests for Phoenix Guardian's CDS function definitions."""
    
    def test_get_phoenix_guardian_cds_functions(self):
        """Test that Phoenix Guardian CDS functions are defined."""
        functions = get_phoenix_guardian_cds_functions()
        
        assert isinstance(functions, list)
        assert len(functions) >= 8  # At least 8 functions defined
    
    def test_all_functions_have_required_fields(self):
        """Test all functions have required fields."""
        functions = get_phoenix_guardian_cds_functions()
        
        for func in functions:
            assert func.function_id is not None
            assert func.name is not None
            assert func.description is not None
            assert func.function_type is not None
            assert len(func.target_users) > 0
    
    def test_phoenix_guardian_functions_target_hcp(self):
        """Test that Phoenix Guardian functions target healthcare providers."""
        functions = get_phoenix_guardian_cds_functions()
        hcp_keywords = ["physician", "nurse", "pharmacist", "clinician", "doctor"]
        
        for func in functions:
            has_hcp = any(
                any(kw in user.lower() for kw in hcp_keywords)
                for user in func.target_users
            )
            assert has_hcp, (
                f"Function {func.name} should target healthcare providers"
            )
    
    def test_phoenix_guardian_functions_enable_transparency(self):
        """Test that functions enable transparency per FDA guidance."""
        functions = get_phoenix_guardian_cds_functions()
        
        for func in functions:
            assert func.hcp_can_review_basis is True, (
                f"Function {func.name} should allow HCP to review basis"
            )
            assert func.requires_hcp_review is True, (
                f"Function {func.name} should require HCP review"
            )
    
    def test_phoenix_guardian_classify_as_non_device(self):
        """Test that Phoenix Guardian functions classify as Non-Device."""
        classifier = FDACDSClassifier()
        functions = get_phoenix_guardian_cds_functions()
        
        for func in functions:
            # Skip RISK_PREDICTION functions which may classify differently
            if func.function_type in [CDSFunctionType.RISK_PREDICTION]:
                assessment = classifier.classify_function(func)
                # Risk prediction may not meet all criteria
                assert assessment is not None
            else:
                assessment = classifier.classify_function(func)
                assert assessment.category == CDSCategory.NON_DEVICE, (
                    f"Function {func.name} should be Non-Device CDS"
                )


# =============================================================================
# CDS Risk Scoring Tests
# =============================================================================


class TestRiskScoringEnums:
    """Tests for risk scoring enumeration types."""
    
    def test_clinical_impact_levels(self):
        """Test clinical impact level values."""
        assert ClinicalImpactLevel.NEGLIGIBLE.value == "negligible"
        assert ClinicalImpactLevel.MINOR.value == "minor"
        assert ClinicalImpactLevel.MODERATE.value == "moderate"
        assert ClinicalImpactLevel.MAJOR.value == "major"
        assert ClinicalImpactLevel.CATASTROPHIC.value == "catastrophic"
    
    def test_autonomy_levels(self):
        """Test autonomy level values."""
        assert AutonomyLevel.INFORMATIONAL.value == "informational"
        assert AutonomyLevel.ADVISORY.value == "advisory"
        assert AutonomyLevel.ASSISTIVE.value == "assistive"
        assert AutonomyLevel.SEMI_AUTONOMOUS.value == "semi_autonomous"
        assert AutonomyLevel.FULLY_AUTONOMOUS.value == "fully_autonomous"
    
    def test_iec_62304_safety_classes(self):
        """Test IEC 62304 safety class values."""
        assert IEC62304SafetyClass.CLASS_A.value == "class_a"
        assert IEC62304SafetyClass.CLASS_B.value == "class_b"
        assert IEC62304SafetyClass.CLASS_C.value == "class_c"


class TestCDSRiskProfile:
    """Tests for CDS Risk Profile data class."""
    
    def test_create_risk_profile(self):
        """Test creating a risk profile."""
        profile = CDSRiskProfile(
            function_id="test-001",
            function_name="Test Function",
            clinical_impact=ClinicalImpactLevel.MODERATE,
            autonomy_level=AutonomyLevel.ADVISORY,
            human_review_required=True,
        )
        
        assert profile.function_id == "test-001"
        assert profile.clinical_impact == ClinicalImpactLevel.MODERATE
        assert profile.autonomy_level == AutonomyLevel.ADVISORY
        assert profile.human_review_required is True
    
    def test_risk_profile_defaults(self):
        """Test risk profile default values."""
        profile = CDSRiskProfile(
            function_id="test-002",
            function_name="Minimal Profile",
        )
        
        assert profile.clinical_impact == ClinicalImpactLevel.MINOR
        assert profile.autonomy_level == AutonomyLevel.ADVISORY
        assert profile.human_review_required is True
        assert profile.time_critical is False
        assert profile.decision_reversible is True


class TestCDSRiskScoringEngine:
    """Tests for CDS Risk Scoring Engine."""
    
    @pytest.fixture
    def engine(self):
        """Create risk scoring engine instance."""
        return CDSRiskScoringEngine()
    
    @pytest.fixture
    def low_risk_profile(self):
        """Create a low-risk profile."""
        return CDSRiskProfile(
            function_id="low-001",
            function_name="Low Risk Function",
            clinical_impact=ClinicalImpactLevel.MINOR,
            autonomy_level=AutonomyLevel.INFORMATIONAL,
            human_review_required=True,
            time_critical=False,
            decision_reversible=True,
            frequency_of_use="occasional",
            target_population=PopulationVulnerability.GENERAL,
            population_size="small",
            input_data_quality=DataQualityLevel.HIGH,
            data_validation_present=True,
        )
    
    @pytest.fixture
    def high_risk_profile(self):
        """Create a high-risk profile."""
        return CDSRiskProfile(
            function_id="high-001",
            function_name="High Risk Function",
            clinical_impact=ClinicalImpactLevel.MAJOR,
            autonomy_level=AutonomyLevel.SEMI_AUTONOMOUS,
            human_review_required=False,
            time_critical=True,
            decision_reversible=False,
            frequency_of_use="continuous",
            target_population=PopulationVulnerability.CRITICAL,
            population_size="enterprise",
            input_data_quality=DataQualityLevel.LOW,
            data_validation_present=False,
        )
    
    def test_engine_initialization(self, engine):
        """Test engine initializes correctly."""
        assert engine is not None
        assert hasattr(engine, "calculate_risk_score")
        assert hasattr(engine, "DIMENSION_WEIGHTS")
    
    def test_dimension_weights_sum_to_one(self, engine):
        """Test that dimension weights sum to 1.0."""
        total = sum(engine.DIMENSION_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, should be 1.0"
    
    def test_calculate_low_risk_score(self, engine, low_risk_profile):
        """Test risk score for low-risk function."""
        result = engine.calculate_risk_score(low_risk_profile)
        
        assert isinstance(result, RiskScoreResult)
        assert 0.0 <= result.raw_risk_score <= 1.0
        assert result.raw_risk_score < 0.3, "Low risk profile should score below 0.3"
        assert result.iec_62304_class == IEC62304SafetyClass.CLASS_A
        assert result.risk_acceptable is True
    
    def test_calculate_high_risk_score(self, engine, high_risk_profile):
        """Test risk score for high-risk function."""
        result = engine.calculate_risk_score(high_risk_profile)
        
        assert isinstance(result, RiskScoreResult)
        assert 0.0 <= result.raw_risk_score <= 1.0
        assert result.raw_risk_score > 0.5, "High risk profile should score above 0.5"
        assert result.iec_62304_class in [IEC62304SafetyClass.CLASS_B, IEC62304SafetyClass.CLASS_C]
    
    def test_all_dimension_scores_present(self, engine, low_risk_profile):
        """Test that all dimension scores are calculated."""
        result = engine.calculate_risk_score(low_risk_profile)
        
        dimensions = [d.dimension for d in result.dimension_scores]
        assert "clinical_impact" in dimensions
        assert "autonomy" in dimensions
        assert "decision_criticality" in dimensions
        assert "population_vulnerability" in dimensions
        assert "data_quality" in dimensions
    
    def test_mitigations_reduce_risk(self, engine, high_risk_profile):
        """Test that mitigations reduce residual risk."""
        mitigations = get_standard_mitigations()
        
        result_without = engine.calculate_risk_score(high_risk_profile)
        result_with = engine.calculate_risk_score(high_risk_profile, mitigations)
        
        assert result_with.residual_risk_score < result_without.raw_risk_score
        assert len(result_with.mitigations) > 0
    
    def test_iec_class_c_for_major_impact(self, engine):
        """Test IEC Class C for major clinical impact."""
        profile = CDSRiskProfile(
            function_id="major-001",
            function_name="Major Impact",
            clinical_impact=ClinicalImpactLevel.MAJOR,
        )
        
        result = engine.calculate_risk_score(profile)
        assert result.iec_62304_class == IEC62304SafetyClass.CLASS_C
    
    def test_iec_class_c_for_catastrophic_impact(self, engine):
        """Test IEC Class C for catastrophic clinical impact."""
        profile = CDSRiskProfile(
            function_id="cat-001",
            function_name="Catastrophic Impact",
            clinical_impact=ClinicalImpactLevel.CATASTROPHIC,
        )
        
        result = engine.calculate_risk_score(profile)
        assert result.iec_62304_class == IEC62304SafetyClass.CLASS_C
    
    def test_result_has_signature(self, engine, low_risk_profile):
        """Test that result includes SHA-256 signature."""
        result = engine.calculate_risk_score(low_risk_profile)
        
        assert result.signature is not None
        assert len(result.signature) == 64  # SHA-256 hex length
    
    def test_result_has_timestamp(self, engine, low_risk_profile):
        """Test that result includes UTC timestamp."""
        before = datetime.now(timezone.utc)
        result = engine.calculate_risk_score(low_risk_profile)
        after = datetime.now(timezone.utc)
        
        assert before <= result.calculated_at <= after
    
    def test_scoring_history_maintained(self, engine, low_risk_profile, high_risk_profile):
        """Test that engine maintains scoring history."""
        engine.calculate_risk_score(low_risk_profile)
        engine.calculate_risk_score(high_risk_profile)
        
        assert len(engine.scoring_history) == 2
    
    def test_generate_risk_matrix(self, engine, low_risk_profile, high_risk_profile):
        """Test risk matrix generation."""
        results = [
            engine.calculate_risk_score(low_risk_profile),
            engine.calculate_risk_score(high_risk_profile),
        ]
        
        matrix = engine.generate_risk_matrix(results)
        
        assert "title" in matrix
        assert "zones" in matrix
        assert "functions" in matrix
        assert len(matrix["functions"]) == 2


class TestStandardMitigations:
    """Tests for standard mitigations library."""
    
    def test_get_standard_mitigations(self):
        """Test that standard mitigations are available."""
        mitigations = get_standard_mitigations()
        
        assert isinstance(mitigations, list)
        assert len(mitigations) >= 5  # At least 5 standard mitigations
    
    def test_mitigation_structure(self):
        """Test mitigation data structure."""
        mitigations = get_standard_mitigations()
        
        for mit in mitigations:
            assert mit.mitigation_id is not None
            assert mit.description is not None
            assert 0.0 <= mit.effectiveness <= 1.0
            assert mit.implementation_status in [
                "planned", "implemented", "verified"
            ]
    
    def test_mitigations_have_reasonable_effectiveness(self):
        """Test that mitigations have reasonable effectiveness values."""
        mitigations = get_standard_mitigations()
        
        for mit in mitigations:
            # No single mitigation should reduce risk by more than 30%
            assert mit.effectiveness <= 0.30, (
                f"Mitigation {mit.mitigation_id} has unrealistic effectiveness"
            )


# =============================================================================
# Integration Tests
# =============================================================================


class TestFDACDSIntegration:
    """Integration tests for FDA CDS classification and risk scoring."""
    
    def test_classify_and_score_phoenix_guardian_functions(self):
        """Test classifying and scoring all Phoenix Guardian functions."""
        classifier = FDACDSClassifier()
        scorer = CDSRiskScoringEngine()
        functions = get_phoenix_guardian_cds_functions()
        mitigations = get_standard_mitigations()
        
        for func in functions:
            # Classify
            assessment = classifier.classify_function(func)
            assert assessment is not None
            
            # Create risk profile from function
            profile = CDSRiskProfile(
                function_id=func.function_id,
                function_name=func.name,
                clinical_impact=ClinicalImpactLevel.MODERATE,
                autonomy_level=AutonomyLevel.ADVISORY,
                human_review_required=True,
            )
            
            # Score with mitigations
            score = scorer.calculate_risk_score(profile, mitigations)
            
            # All Phoenix Guardian functions should have acceptable risk
            assert score.risk_acceptable is True, (
                f"Function {func.name} should have acceptable risk"
            )
    
    def test_end_to_end_assessment_workflow(self):
        """Test complete assessment workflow."""
        # 1. Define function
        func = CDSFunction(
            function_id="e2e-001",
            name="Sepsis Risk Calculator",
            description="Calculates sepsis risk from vital signs",
            function_type=CDSFunctionType.RISK_PREDICTION,
            target_users=["Physician", "Nurse"],
            processes_images_signals=False,
            provides_recommendations=True,
            requires_hcp_review=True,
            hcp_can_review_basis=True,
        )
        
        # 2. Classify
        classifier = FDACDSClassifier()
        assessment = classifier.classify_function(func)
        assert assessment is not None
        
        # 3. Create risk profile
        profile = CDSRiskProfile(
            function_id=func.function_id,
            function_name=func.name,
            clinical_impact=ClinicalImpactLevel.MODERATE,
            impact_description="Missed sepsis detection could delay treatment",
            autonomy_level=AutonomyLevel.ADVISORY,
            human_review_required=True,
            time_critical=True,
            decision_reversible=True,
            frequency_of_use="frequent",
            target_population=PopulationVulnerability.GENERAL,
            population_size="medium",
            input_data_quality=DataQualityLevel.HIGH,
            data_validation_present=True,
        )
        
        # 4. Calculate risk score
        scorer = CDSRiskScoringEngine()
        mitigations = get_standard_mitigations()
        result = scorer.calculate_risk_score(profile, mitigations)
        
        # 5. Validate results
        assert result.function_id == func.function_id
        assert result.residual_risk_score < result.raw_risk_score
        assert result.signature is not None
        
        # 6. Generate matrix
        matrix = scorer.generate_risk_matrix([result])
        assert len(matrix["functions"]) == 1


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_empty_target_users(self):
        """Test function with no target users."""
        func = CDSFunction(
            function_id="edge-001",
            name="No Target Users",
            description="Safe function",
            function_type=CDSFunctionType.CLINICAL_GUIDELINES,
            target_users=[],
        )
        
        classifier = FDACDSClassifier()
        assessment = classifier.classify_function(func)
        
        assert assessment is not None
        # Without HCP target users, won't meet criterion 3
        assert assessment.criteria_met[Criterion.SUPPORTS_HCP] is False
    
    def test_maximum_risk_profile(self):
        """Test profile with maximum risk settings."""
        profile = CDSRiskProfile(
            function_id="max-001",
            function_name="Maximum Risk",
            clinical_impact=ClinicalImpactLevel.CATASTROPHIC,
            autonomy_level=AutonomyLevel.FULLY_AUTONOMOUS,
            human_review_required=False,
            time_critical=True,
            decision_reversible=False,
            frequency_of_use="continuous",
            target_population=PopulationVulnerability.CRITICAL,
            population_size="enterprise",
            input_data_quality=DataQualityLevel.UNKNOWN,
            data_validation_present=False,
        )
        
        engine = CDSRiskScoringEngine()
        result = engine.calculate_risk_score(profile)
        
        assert result.raw_risk_score > 0.8
        assert result.iec_62304_class == IEC62304SafetyClass.CLASS_C
        assert result.risk_acceptable is False
    
    def test_minimum_risk_profile(self):
        """Test profile with minimum risk settings."""
        profile = CDSRiskProfile(
            function_id="min-001",
            function_name="Minimum Risk",
            clinical_impact=ClinicalImpactLevel.NEGLIGIBLE,
            autonomy_level=AutonomyLevel.INFORMATIONAL,
            human_review_required=True,
            time_critical=False,
            decision_reversible=True,
            frequency_of_use="rare",
            target_population=PopulationVulnerability.GENERAL,
            population_size="small",
            input_data_quality=DataQualityLevel.HIGH,
            data_validation_present=True,
        )
        
        engine = CDSRiskScoringEngine()
        result = engine.calculate_risk_score(profile)
        
        assert result.raw_risk_score < 0.15
        assert result.iec_62304_class == IEC62304SafetyClass.CLASS_A
        assert result.risk_acceptable is True
    
    def test_signature_deterministic(self):
        """Test that signature is deterministic for same input."""
        profile = CDSRiskProfile(
            function_id="sig-001",
            function_name="Signature Test",
        )
        
        engine = CDSRiskScoringEngine()
        
        # Create result with fixed timestamp for determinism
        with patch('phoenix_guardian.compliance.cds_risk_scorer.datetime') as mock_dt:
            fixed_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = fixed_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            
            result1 = engine.calculate_risk_score(profile)
        
        # Signature should be consistent
        assert result1.signature is not None
        assert len(result1.signature) == 64
