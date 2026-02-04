"""
Translation Quality Scorer.

Evaluates translation quality for medical content using multiple dimensions:
- Accuracy: Medical terms correctly translated
- Completeness: No missing information
- Fluency: Natural language flow
- Terminology: Correct medical vocabulary
- Safety: Critical information preserved

QUALITY THRESHOLDS:
- Clinical use: Score >= 90
- Review required: Score 70-89
- Not suitable: Score < 70
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import logging
import re

from phoenix_guardian.language.language_detector import Language

logger = logging.getLogger(__name__)


class QualityDimension(Enum):
    """Dimensions of translation quality."""
    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
    FLUENCY = "fluency"
    TERMINOLOGY = "terminology"
    SAFETY = "safety"


@dataclass
class DimensionScore:
    """Score for a single quality dimension."""
    dimension: QualityDimension
    score: float  # 0-100
    weight: float  # Contribution to overall score
    issues: List[str] = field(default_factory=list)


@dataclass
class QualityScore:
    """
    Complete quality assessment for a translation.
    
    Attributes:
        overall_score: Weighted average score (0-100)
        dimension_scores: Individual dimension scores
        pass_threshold: Minimum score for clinical use
        clinical_safe: Whether translation is safe for clinical use
        recommendations: Suggestions for improvement
    """
    overall_score: float
    dimension_scores: List[DimensionScore]
    pass_threshold: float = 90.0
    clinical_safe: bool = False
    recommendations: List[str] = field(default_factory=list)
    
    def is_acceptable(self) -> bool:
        """Check if translation meets minimum quality threshold."""
        return self.overall_score >= 70.0
    
    def is_clinical_grade(self) -> bool:
        """Check if translation is safe for clinical use."""
        return self.clinical_safe and self.overall_score >= self.pass_threshold
    
    def get_dimension_score(self, dimension: QualityDimension) -> Optional[DimensionScore]:
        """Get score for a specific dimension."""
        for ds in self.dimension_scores:
            if ds.dimension == dimension:
                return ds
        return None


class TranslationQualityScorer:
    """
    Scores translation quality for medical content.
    
    Evaluates translations across multiple dimensions critical for
    healthcare communication accuracy.
    
    Example:
        scorer = TranslationQualityScorer()
        result = scorer.score(
            source_text="Take aspirin 325mg twice daily",
            target_text="Tome aspirina 325mg dos veces al día",
            source_language=Language.ENGLISH,
            target_language=Language.SPANISH_MX
        )
        print(f"Quality Score: {result.overall_score}")
        print(f"Clinical Safe: {result.clinical_safe}")
    """
    
    # Dimension weights for overall score
    DIMENSION_WEIGHTS = {
        QualityDimension.ACCURACY: 0.30,
        QualityDimension.COMPLETENESS: 0.25,
        QualityDimension.FLUENCY: 0.15,
        QualityDimension.TERMINOLOGY: 0.20,
        QualityDimension.SAFETY: 0.10,
    }
    
    # Critical terms that must be preserved
    CRITICAL_TERMS = {
        Language.ENGLISH: [
            "allergy", "allergic", "emergency", "immediately", "stop",
            "do not", "warning", "danger", "overdose", "poison",
            "call 911", "seek medical attention"
        ],
        Language.SPANISH_MX: [
            "alergia", "alérgico", "emergencia", "inmediatamente", "pare",
            "no", "advertencia", "peligro", "sobredosis", "veneno",
            "llame al 911", "busque atención médica"
        ],
        Language.MANDARIN: [
            "过敏", "紧急", "立即", "停止", "不要",
            "警告", "危险", "过量", "毒", "拨打急救电话"
        ]
    }
    
    # Dosage patterns that must be preserved exactly
    DOSAGE_PATTERNS = [
        r'\d+\s*mg',
        r'\d+\s*ml',
        r'\d+\s*mcg',
        r'\d+\s*g\b',
        r'\d+\s*units?',
        r'\d+\s*tablets?',
        r'\d+\s*pills?',
        r'\d+\s*capsules?',
        r'\d+\s*times?\s*(?:daily|a day|per day)',
        r'every\s*\d+\s*hours?',
        r'cada\s*\d+\s*horas?',
        r'每\d+小时',
    ]
    
    def __init__(self, pass_threshold: float = 90.0):
        """
        Initialize quality scorer.
        
        Args:
            pass_threshold: Minimum score for clinical-grade translation
        """
        self.pass_threshold = pass_threshold
    
    def score(
        self,
        source_text: str,
        target_text: str,
        source_language: Language,
        target_language: Language,
        back_translation: Optional[str] = None
    ) -> QualityScore:
        """
        Score translation quality.
        
        Args:
            source_text: Original text
            target_text: Translated text
            source_language: Source language
            target_language: Target language
            back_translation: Optional back-translation for verification
        
        Returns:
            QualityScore with detailed assessment
        """
        dimension_scores = []
        
        # Score each dimension
        accuracy = self._score_accuracy(
            source_text, target_text, back_translation
        )
        dimension_scores.append(accuracy)
        
        completeness = self._score_completeness(
            source_text, target_text, source_language, target_language
        )
        dimension_scores.append(completeness)
        
        fluency = self._score_fluency(target_text, target_language)
        dimension_scores.append(fluency)
        
        terminology = self._score_terminology(
            source_text, target_text, source_language, target_language
        )
        dimension_scores.append(terminology)
        
        safety = self._score_safety(
            source_text, target_text, source_language, target_language
        )
        dimension_scores.append(safety)
        
        # Calculate overall score
        overall_score = sum(
            ds.score * ds.weight for ds in dimension_scores
        )
        
        # Determine clinical safety
        clinical_safe = (
            overall_score >= self.pass_threshold and
            safety.score >= 90.0 and  # Safety must be high
            accuracy.score >= 80.0    # Accuracy must be acceptable
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(dimension_scores)
        
        return QualityScore(
            overall_score=round(overall_score, 1),
            dimension_scores=dimension_scores,
            pass_threshold=self.pass_threshold,
            clinical_safe=clinical_safe,
            recommendations=recommendations
        )
    
    def _score_accuracy(
        self,
        source_text: str,
        target_text: str,
        back_translation: Optional[str]
    ) -> DimensionScore:
        """Score translation accuracy."""
        issues = []
        score = 100.0
        
        # Check if back-translation is available
        if back_translation:
            # Compare source with back-translation
            similarity = self._calculate_similarity(source_text, back_translation)
            if similarity < 0.8:
                score -= 30
                issues.append("Back-translation differs significantly from source")
            elif similarity < 0.9:
                score -= 15
                issues.append("Minor differences in back-translation")
        else:
            # Without back-translation, deduct some points
            score -= 10
            issues.append("No back-translation verification")
        
        # Check length ratio (translations should be similar length)
        source_len = len(source_text)
        target_len = len(target_text)
        if source_len > 0:
            ratio = target_len / source_len
            if ratio < 0.5 or ratio > 2.0:
                score -= 20
                issues.append("Translation length significantly differs from source")
        
        return DimensionScore(
            dimension=QualityDimension.ACCURACY,
            score=max(0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.ACCURACY],
            issues=issues
        )
    
    def _score_completeness(
        self,
        source_text: str,
        target_text: str,
        source_language: Language,
        target_language: Language
    ) -> DimensionScore:
        """Score translation completeness."""
        issues = []
        score = 100.0
        
        # Extract numbers from source and target
        source_numbers = re.findall(r'\d+(?:\.\d+)?', source_text)
        target_numbers = re.findall(r'\d+(?:\.\d+)?', target_text)
        
        # All numbers should be preserved
        for num in source_numbers:
            if num not in target_numbers:
                score -= 15
                issues.append(f"Number '{num}' may be missing in translation")
        
        # Check for dosage preservation
        source_dosages = self._extract_dosages(source_text)
        target_dosages = self._extract_dosages(target_text)
        
        for dosage in source_dosages:
            # Extract just the number and unit
            dosage_num = re.search(r'\d+', dosage)
            if dosage_num and dosage_num.group() not in target_text:
                score -= 20
                issues.append(f"Dosage '{dosage}' may not be preserved")
        
        return DimensionScore(
            dimension=QualityDimension.COMPLETENESS,
            score=max(0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.COMPLETENESS],
            issues=issues
        )
    
    def _score_fluency(
        self,
        target_text: str,
        target_language: Language
    ) -> DimensionScore:
        """Score translation fluency."""
        issues = []
        score = 100.0
        
        # Check for untranslated text (mixing languages)
        if target_language == Language.SPANISH_MX:
            # Check for English words that shouldn't be there
            english_words = re.findall(r'\b(the|is|are|have|has|and|or|but)\b', target_text.lower())
            if english_words:
                score -= 10 * len(english_words)
                issues.append("Contains untranslated English words")
        
        elif target_language == Language.ENGLISH:
            # Check for Spanish words that shouldn't be there
            spanish_words = re.findall(r'\b(el|la|los|las|es|son|tiene|tienen|y|o|pero)\b', target_text.lower())
            if spanish_words:
                score -= 10 * len(spanish_words)
                issues.append("Contains untranslated Spanish words")
        
        # Check for proper capitalization
        sentences = target_text.split('.')
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and sentence[0].islower():
                score -= 5
                issues.append("Sentence does not start with capital letter")
                break
        
        return DimensionScore(
            dimension=QualityDimension.FLUENCY,
            score=max(0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.FLUENCY],
            issues=issues
        )
    
    def _score_terminology(
        self,
        source_text: str,
        target_text: str,
        source_language: Language,
        target_language: Language
    ) -> DimensionScore:
        """Score medical terminology accuracy."""
        issues = []
        score = 100.0
        
        # Check that medical terms are properly translated
        # (not left in source language)
        source_critical = self.CRITICAL_TERMS.get(source_language, [])
        target_critical = self.CRITICAL_TERMS.get(target_language, [])
        
        for i, source_term in enumerate(source_critical):
            if source_term.lower() in source_text.lower():
                # This term is in source - should be translated
                if i < len(target_critical):
                    expected_target = target_critical[i]
                    if source_term.lower() in target_text.lower() and source_language != target_language:
                        # Source term found in target (not translated)
                        score -= 15
                        issues.append(f"Term '{source_term}' may not be translated")
        
        return DimensionScore(
            dimension=QualityDimension.TERMINOLOGY,
            score=max(0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.TERMINOLOGY],
            issues=issues
        )
    
    def _score_safety(
        self,
        source_text: str,
        target_text: str,
        source_language: Language,
        target_language: Language
    ) -> DimensionScore:
        """Score safety-critical content preservation."""
        issues = []
        score = 100.0
        
        # Check critical safety terms
        source_critical = self.CRITICAL_TERMS.get(source_language, [])
        
        for term in source_critical:
            if term.lower() in source_text.lower():
                # This safety term exists in source - verify it's in target
                target_critical = self.CRITICAL_TERMS.get(target_language, [])
                
                # Check if any equivalent safety term is in target
                found_equivalent = False
                for target_term in target_critical:
                    if target_term.lower() in target_text.lower():
                        found_equivalent = True
                        break
                
                if not found_equivalent:
                    score -= 25
                    issues.append(f"Safety term '{term}' may not be translated")
        
        # Verify all numbers are preserved (critical for dosing)
        source_numbers = set(re.findall(r'\d+(?:\.\d+)?', source_text))
        target_numbers = set(re.findall(r'\d+(?:\.\d+)?', target_text))
        
        missing_numbers = source_numbers - target_numbers
        if missing_numbers:
            score -= 20 * len(missing_numbers)
            issues.append(f"Numbers {missing_numbers} missing - critical for dosing")
        
        return DimensionScore(
            dimension=QualityDimension.SAFETY,
            score=max(0, score),
            weight=self.DIMENSION_WEIGHTS[QualityDimension.SAFETY],
            issues=issues
        )
    
    def _extract_dosages(self, text: str) -> List[str]:
        """Extract dosage patterns from text."""
        dosages = []
        for pattern in self.DOSAGE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dosages.extend(matches)
        return dosages
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity (simplified)."""
        # Simple word overlap similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def _generate_recommendations(
        self,
        dimension_scores: List[DimensionScore]
    ) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []
        
        for ds in dimension_scores:
            if ds.score < 80:
                if ds.dimension == QualityDimension.ACCURACY:
                    recommendations.append(
                        "Review translation accuracy - consider professional review"
                    )
                elif ds.dimension == QualityDimension.COMPLETENESS:
                    recommendations.append(
                        "Verify all dosages and numbers are correctly preserved"
                    )
                elif ds.dimension == QualityDimension.SAFETY:
                    recommendations.append(
                        "CRITICAL: Safety terms may not be properly translated - requires review"
                    )
                elif ds.dimension == QualityDimension.TERMINOLOGY:
                    recommendations.append(
                        "Medical terminology may need correction by clinical staff"
                    )
        
        if not recommendations and all(ds.score >= 90 for ds in dimension_scores):
            recommendations.append("Translation meets clinical quality standards")
        
        return recommendations
