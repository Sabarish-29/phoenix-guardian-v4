"""
Tests for Translation Quality Scorer (15 tests).

Tests:
1. Initialization
2. Overall scoring
3. Dimension scoring
4. Safety scoring
5. Clinical grade determination
6. Recommendations generation
"""

import pytest

from phoenix_guardian.language.translation_quality_scorer import (
    TranslationQualityScorer,
    QualityScore,
    QualityDimension,
    DimensionScore,
)
from phoenix_guardian.language.language_detector import Language


class TestScorerInitialization:
    """Tests for scorer initialization."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        scorer = TranslationQualityScorer()
        
        assert scorer is not None
        assert scorer.pass_threshold == 90.0
    
    def test_initialization_custom_threshold(self):
        """Test initialization with custom threshold."""
        scorer = TranslationQualityScorer(pass_threshold=85.0)
        
        assert scorer.pass_threshold == 85.0


class TestOverallScoring:
    """Tests for overall quality scoring."""
    
    def test_score_returns_quality_score(self):
        """Test scoring returns QualityScore object."""
        scorer = TranslationQualityScorer()
        
        result = scorer.score(
            source_text="Take aspirin 325mg twice daily",
            target_text="Tome aspirina 325mg dos veces al día",
            source_language=Language.ENGLISH,
            target_language=Language.SPANISH_MX
        )
        
        assert isinstance(result, QualityScore)
        assert 0 <= result.overall_score <= 100
    
    def test_score_with_back_translation(self):
        """Test scoring with back-translation."""
        scorer = TranslationQualityScorer()
        
        result = scorer.score(
            source_text="Take aspirin daily",
            target_text="Tome aspirina diariamente",
            source_language=Language.ENGLISH,
            target_language=Language.SPANISH_MX,
            back_translation="Take aspirin daily"
        )
        
        # Should have higher accuracy with matching back-translation
        assert result.overall_score > 0


class TestDimensionScoring:
    """Tests for individual dimension scoring."""
    
    def test_all_dimensions_scored(self):
        """Test all dimensions are scored."""
        scorer = TranslationQualityScorer()
        
        result = scorer.score(
            source_text="Test text",
            target_text="Texto de prueba",
            source_language=Language.ENGLISH,
            target_language=Language.SPANISH_MX
        )
        
        dimensions = [ds.dimension for ds in result.dimension_scores]
        
        assert QualityDimension.ACCURACY in dimensions
        assert QualityDimension.COMPLETENESS in dimensions
        assert QualityDimension.FLUENCY in dimensions
        assert QualityDimension.TERMINOLOGY in dimensions
        assert QualityDimension.SAFETY in dimensions
    
    def test_get_dimension_score(self):
        """Test getting specific dimension score."""
        scorer = TranslationQualityScorer()
        
        result = scorer.score(
            source_text="Test",
            target_text="Prueba",
            source_language=Language.ENGLISH,
            target_language=Language.SPANISH_MX
        )
        
        accuracy = result.get_dimension_score(QualityDimension.ACCURACY)
        
        assert accuracy is not None
        assert 0 <= accuracy.score <= 100
    
    def test_dimension_weights_sum_to_one(self):
        """Test dimension weights sum to approximately 1.0."""
        scorer = TranslationQualityScorer()
        
        total_weight = sum(scorer.DIMENSION_WEIGHTS.values())
        
        assert abs(total_weight - 1.0) < 0.01


class TestSafetyScoring:
    """Tests for safety dimension scoring."""
    
    def test_numbers_preserved_high_safety(self):
        """Test numbers preserved gives high safety score."""
        scorer = TranslationQualityScorer()
        
        result = scorer.score(
            source_text="Take 500mg twice daily",
            target_text="Tome 500mg dos veces al día",
            source_language=Language.ENGLISH,
            target_language=Language.SPANISH_MX
        )
        
        safety = result.get_dimension_score(QualityDimension.SAFETY)
        assert safety.score >= 80  # Numbers preserved
    
    def test_numbers_missing_low_safety(self):
        """Test missing numbers gives low safety score."""
        scorer = TranslationQualityScorer()
        
        result = scorer.score(
            source_text="Take 500mg twice daily",
            target_text="Tome dos veces al día",  # Missing 500mg
            source_language=Language.ENGLISH,
            target_language=Language.SPANISH_MX
        )
        
        safety = result.get_dimension_score(QualityDimension.SAFETY)
        # Safety should be lower due to missing dosage
        assert safety.score < 100


class TestClinicalGradeDetermination:
    """Tests for clinical grade determination."""
    
    def test_is_acceptable(self):
        """Test is_acceptable method."""
        scorer = TranslationQualityScorer()
        
        result = scorer.score(
            source_text="Take aspirin 325mg",
            target_text="Tome aspirina 325mg",
            source_language=Language.ENGLISH,
            target_language=Language.SPANISH_MX
        )
        
        # Should return boolean
        assert isinstance(result.is_acceptable(), bool)
    
    def test_is_clinical_grade(self):
        """Test is_clinical_grade method."""
        scorer = TranslationQualityScorer()
        
        result = scorer.score(
            source_text="Take aspirin",
            target_text="Tome aspirina",
            source_language=Language.ENGLISH,
            target_language=Language.SPANISH_MX,
            back_translation="Take aspirin"
        )
        
        assert isinstance(result.is_clinical_grade(), bool)
    
    def test_clinical_safe_flag(self):
        """Test clinical_safe flag is set."""
        scorer = TranslationQualityScorer()
        
        result = scorer.score(
            source_text="Emergency call 911",
            target_text="Emergencia llame al 911",
            source_language=Language.ENGLISH,
            target_language=Language.SPANISH_MX
        )
        
        assert isinstance(result.clinical_safe, bool)


class TestRecommendationsGeneration:
    """Tests for recommendations generation."""
    
    def test_recommendations_generated(self):
        """Test recommendations are generated."""
        scorer = TranslationQualityScorer()
        
        result = scorer.score(
            source_text="Take aspirin",
            target_text="Tome aspirina",
            source_language=Language.ENGLISH,
            target_language=Language.SPANISH_MX
        )
        
        assert isinstance(result.recommendations, list)
    
    def test_low_score_generates_recommendations(self):
        """Test low scores generate recommendations."""
        scorer = TranslationQualityScorer()
        
        # Intentionally poor translation
        result = scorer.score(
            source_text="Take 500mg aspirin twice daily for pain",
            target_text="Tome",  # Very incomplete
            source_language=Language.ENGLISH,
            target_language=Language.SPANISH_MX
        )
        
        # Should have recommendations due to poor translation
        assert len(result.recommendations) > 0


class TestDimensionIssues:
    """Tests for dimension issues tracking."""
    
    def test_issues_tracked(self):
        """Test issues are tracked per dimension."""
        scorer = TranslationQualityScorer()
        
        result = scorer.score(
            source_text="Take 500mg daily",
            target_text="Tome daily",  # Missing number
            source_language=Language.ENGLISH,
            target_language=Language.SPANISH_MX
        )
        
        # Some dimension should have issues
        all_issues = []
        for ds in result.dimension_scores:
            all_issues.extend(ds.issues)
        
        assert len(all_issues) > 0
