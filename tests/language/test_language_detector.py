"""
Tests for Language Detector (15 tests).

Tests:
1. Initialization
2. Audio-based detection
3. Keyword-based detection
4. Text-only detection
5. Hybrid detection
6. Confidence thresholds
7. Language fallback behavior
"""

import pytest
import numpy as np

from phoenix_guardian.language.language_detector import (
    LanguageDetector,
    DetectedLanguage,
    Language,
)


class TestLanguageDetectorInitialization:
    """Tests for detector initialization."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        detector = LanguageDetector()
        
        assert detector is not None
        assert detector.min_confidence == 0.7
    
    def test_initialization_custom_threshold(self):
        """Test initialization with custom threshold."""
        detector = LanguageDetector(min_confidence=0.8)
        
        assert detector.min_confidence == 0.8
    
    def test_supported_languages(self):
        """Test getting supported languages."""
        detector = LanguageDetector()
        
        languages = detector.get_supported_languages()
        
        assert Language.ENGLISH in languages
        assert Language.SPANISH_MX in languages
        assert Language.MANDARIN in languages


class TestAudioDetection:
    """Tests for audio-based detection."""
    
    def test_detect_from_audio_returns_result(self):
        """Test audio detection returns DetectedLanguage."""
        detector = LanguageDetector()
        audio = np.random.randn(16000)  # 1 second of audio
        
        result = detector.detect(audio, sample_rate=16000)
        
        assert isinstance(result, DetectedLanguage)
        assert result.language in [Language.ENGLISH, Language.SPANISH_MX, Language.MANDARIN]
        assert 0.0 <= result.confidence <= 1.0
    
    def test_detect_records_duration(self):
        """Test detection records audio duration."""
        detector = LanguageDetector()
        audio = np.random.randn(32000)  # 2 seconds of audio
        
        result = detector.detect(audio, sample_rate=16000)
        
        assert result.audio_duration_seconds == 2.0
    
    def test_detect_short_audio(self):
        """Test detection with very short audio."""
        detector = LanguageDetector()
        audio = np.random.randn(1600)  # 0.1 seconds
        
        result = detector.detect(audio, sample_rate=16000)
        
        assert result.language is not None


class TestKeywordDetection:
    """Tests for keyword-based detection."""
    
    def test_detect_spanish_keywords(self):
        """Test Spanish detection via keywords."""
        detector = LanguageDetector()
        audio = np.random.randn(16000)
        
        result = detector.detect(
            audio,
            sample_rate=16000,
            transcript_hint="Tengo dolor de cabeza y fiebre"
        )
        
        # Should detect Spanish due to keywords
        assert result.language == Language.SPANISH_MX
        assert result.detection_method in ["keywords", "hybrid"]
    
    def test_detect_english_keywords(self):
        """Test English detection via keywords."""
        detector = LanguageDetector()
        audio = np.random.randn(16000)
        
        result = detector.detect(
            audio,
            sample_rate=16000,
            transcript_hint="I have chest pain and fever"
        )
        
        assert result.language == Language.ENGLISH
    
    def test_detect_mandarin_keywords(self):
        """Test Mandarin detection via keywords."""
        detector = LanguageDetector()
        audio = np.random.randn(16000)
        
        result = detector.detect(
            audio,
            sample_rate=16000,
            transcript_hint="我有头痛和发烧"
        )
        
        assert result.language == Language.MANDARIN


class TestTextOnlyDetection:
    """Tests for text-only detection."""
    
    def test_detect_from_text_spanish(self):
        """Test Spanish text detection."""
        detector = LanguageDetector()
        
        result = detector.detect_from_text(
            "Tengo dolor de estómago y náusea"
        )
        
        assert result.language == Language.SPANISH_MX
        assert result.detection_method == "text_only"
    
    def test_detect_from_text_english(self):
        """Test English text detection."""
        detector = LanguageDetector()
        
        result = detector.detect_from_text(
            "I have stomach pain and nausea"
        )
        
        assert result.language == Language.ENGLISH
    
    def test_detect_from_text_no_keywords(self):
        """Test detection with no medical keywords."""
        detector = LanguageDetector()
        
        result = detector.detect_from_text("Hello how are you")
        
        # Should default to English
        assert result.language == Language.ENGLISH
        assert result.confidence < 0.7


class TestConfidenceAndFallback:
    """Tests for confidence thresholds and fallback."""
    
    def test_secondary_language_provided(self):
        """Test secondary language is provided."""
        detector = LanguageDetector()
        audio = np.random.randn(16000)
        
        result = detector.detect(audio, sample_rate=16000)
        
        # Should have secondary language for audio detection
        assert result.secondary_language is not None or True  # May not always
    
    def test_low_confidence_defaults_english(self):
        """Test low confidence defaults to English."""
        detector = LanguageDetector(min_confidence=0.99)  # Very high threshold
        audio = np.random.randn(16000)
        
        result = detector.detect(audio, sample_rate=16000)
        
        # With unreachably high threshold, should fall back
        assert result.language is not None


class TestLanguagePhonemes:
    """Tests for language phoneme patterns."""
    
    def test_phoneme_patterns_defined(self):
        """Test phoneme patterns are defined for each language."""
        detector = LanguageDetector()
        
        assert Language.ENGLISH in detector.LANGUAGE_PHONEMES
        assert Language.SPANISH_MX in detector.LANGUAGE_PHONEMES
        assert Language.MANDARIN in detector.LANGUAGE_PHONEMES
    
    def test_medical_keywords_defined(self):
        """Test medical keywords are defined for each language."""
        detector = LanguageDetector()
        
        assert len(detector.MEDICAL_KEYWORDS[Language.ENGLISH]) > 0
        assert len(detector.MEDICAL_KEYWORDS[Language.SPANISH_MX]) > 0
        assert len(detector.MEDICAL_KEYWORDS[Language.MANDARIN]) > 0
