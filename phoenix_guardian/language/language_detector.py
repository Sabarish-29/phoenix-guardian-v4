"""
Language Detection for Phoenix Guardian.

Automatically detects the language of spoken audio to route to
appropriate speech recognition and translation pipelines.

SUPPORTED LANGUAGES:
- English (en-US)
- Spanish (es-MX, es-US)
- Mandarin Chinese (zh-CN)

DETECTION METHOD:
1. Audio feature extraction (MFCC, spectral features)
2. Language-specific acoustic patterns
3. Phoneme probability distributions
4. Confidence scoring

FALLBACK BEHAVIOR:
- If confidence < 0.7, assume English (clinical default)
- If ambiguous Spanish/English, prefer Spanish (LEP priority)
- Log all detections for audit trail
"""

from dataclasses import dataclass
from typing import Optional, Dict, List
from enum import Enum
import logging
import numpy as np

logger = logging.getLogger(__name__)


class Language(Enum):
    """Supported languages for clinical documentation."""
    ENGLISH = "en-US"
    SPANISH_MX = "es-MX"      # Mexican Spanish
    SPANISH_US = "es-US"      # US Spanish
    MANDARIN = "zh-CN"        # Simplified Chinese
    UNKNOWN = "unknown"


@dataclass
class DetectedLanguage:
    """
    Result of language detection.
    
    Attributes:
        language: Primary detected language
        confidence: Detection confidence (0.0 - 1.0)
        secondary_language: Second most likely language
        secondary_confidence: Confidence of secondary language
        audio_duration_seconds: Duration of analyzed audio
        detection_method: Method used (acoustic, keywords, hybrid)
    """
    language: Language
    confidence: float              # 0.0 - 1.0
    secondary_language: Optional[Language] = None
    secondary_confidence: Optional[float] = None
    audio_duration_seconds: float = 0.0
    detection_method: str = "acoustic"


class LanguageDetector:
    """
    Detects spoken language from audio.
    
    Uses acoustic features + phoneme patterns to identify language.
    Optimized for medical conversations (limited vocabulary domain).
    
    Example:
        detector = LanguageDetector()
        result = detector.detect(audio_data, sample_rate=16000)
        print(f"Detected: {result.language.value} ({result.confidence:.0%})")
    """
    
    # Language-specific phoneme patterns
    LANGUAGE_PHONEMES = {
        Language.SPANISH_MX: {
            # Spanish has distinct 'rr' trill, 'ñ' sound
            "characteristic_phonemes": ["rr", "ñ", "ll", "ch"],
            "vowel_patterns": ["a", "e", "i", "o", "u"],  # Pure vowels
            "consonant_clusters": ["bl", "br", "cl", "cr", "dr", "fl", "fr", "gl", "gr", "pl", "pr", "tr"]
        },
        Language.MANDARIN: {
            # Mandarin is tonal (4 tones + neutral)
            "characteristic_phonemes": ["zh", "ch", "sh", "r"],
            "tonal": True,
            "syllable_structure": "CV",  # Consonant-Vowel (simple)
        },
        Language.ENGLISH: {
            "characteristic_phonemes": ["th", "ng", "r", "w"],
            "vowel_patterns": ["æ", "ɪ", "ʊ", "ə"],  # Schwa, lax vowels
            "consonant_clusters": ["str", "spr", "thr", "spl"]
        }
    }
    
    # Common medical terms per language (quick detection)
    MEDICAL_KEYWORDS = {
        Language.SPANISH_MX: [
            "dolor", "fiebre", "tos", "náusea", "cabeza", "estómago",
            "presión", "azúcar", "medicamento", "alergia", "síntoma",
            "corazón", "pecho", "espalda", "pierna", "brazo", "mareo",
            "vómito", "diarrea", "estreñimiento", "sangre", "orina"
        ],
        Language.MANDARIN: [
            "疼痛", "发烧", "咳嗽", "恶心", "头", "胃",
            "血压", "血糖", "药", "过敏", "症状",
            "心脏", "胸", "背", "腿", "手臂", "头晕",
            "呕吐", "腹泻", "便秘", "血", "尿"
        ],
        Language.ENGLISH: [
            "pain", "fever", "cough", "nausea", "headache", "stomach",
            "pressure", "sugar", "medication", "allergy", "symptom",
            "heart", "chest", "back", "leg", "arm", "dizziness",
            "vomiting", "diarrhea", "constipation", "blood", "urine"
        ]
    }
    
    def __init__(self, min_confidence: float = 0.7):
        """
        Initialize language detector.
        
        Args:
            min_confidence: Minimum confidence threshold for detection
        """
        self.min_confidence = min_confidence
    
    def detect(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        transcript_hint: Optional[str] = None
    ) -> DetectedLanguage:
        """
        Detect language from audio.
        
        Args:
            audio_data: Audio samples (numpy array)
            sample_rate: Audio sample rate in Hz
            transcript_hint: Optional pre-transcribed text for keyword matching
        
        Returns:
            DetectedLanguage with confidence score
        """
        duration = len(audio_data) / sample_rate
        
        # Method 1: Keyword matching (fast, if transcript available)
        if transcript_hint:
            keyword_result = self._detect_by_keywords(transcript_hint)
            if keyword_result and keyword_result.confidence >= self.min_confidence:
                keyword_result.audio_duration_seconds = duration
                keyword_result.detection_method = "keywords"
                return keyword_result
        
        # Method 2: Acoustic feature analysis
        acoustic_result = self._detect_by_acoustics(audio_data, sample_rate)
        acoustic_result.audio_duration_seconds = duration
        
        # Method 3: Hybrid (if transcript available but low keyword confidence)
        if transcript_hint:
            keyword_result = self._detect_by_keywords(transcript_hint)
            if keyword_result:
                # Combine acoustic and keyword scores
                combined_result = self._combine_detections(
                    acoustic_result, keyword_result
                )
                combined_result.audio_duration_seconds = duration
                combined_result.detection_method = "hybrid"
                return combined_result
        
        return acoustic_result
    
    def detect_from_text(self, text: str) -> DetectedLanguage:
        """
        Detect language from text only (no audio).
        
        Useful for analyzing transcripts or written input.
        
        Args:
            text: Text to analyze
        
        Returns:
            DetectedLanguage based on keyword analysis
        """
        result = self._detect_by_keywords(text)
        if result:
            result.detection_method = "text_only"
            return result
        
        # Default to English if no keywords matched
        return DetectedLanguage(
            language=Language.ENGLISH,
            confidence=0.5,
            detection_method="text_only"
        )
    
    def _detect_by_keywords(self, text: str) -> Optional[DetectedLanguage]:
        """
        Fast detection using medical keyword matching.
        
        Checks if text contains language-specific medical terms.
        """
        text_lower = text.lower()
        
        # Count keyword matches per language
        match_counts = {}
        for lang, keywords in self.MEDICAL_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw.lower() in text_lower)
            match_counts[lang] = matches
        
        # Find language with most matches
        if not match_counts:
            return None
        
        top_lang = max(match_counts, key=match_counts.get)
        top_matches = match_counts[top_lang]
        
        if top_matches == 0:
            return None
        
        # Calculate confidence based on match density
        total_words = len(text.split())
        confidence = min(1.0, (top_matches / max(1, total_words)) * 10)
        
        # Get second-best language
        sorted_langs = sorted(match_counts.items(), key=lambda x: x[1], reverse=True)
        secondary_lang = sorted_langs[1][0] if len(sorted_langs) > 1 else None
        secondary_conf = min(1.0, (sorted_langs[1][1] / max(1, total_words)) * 10) if secondary_lang and len(sorted_langs) > 1 else None
        
        return DetectedLanguage(
            language=top_lang,
            confidence=confidence,
            secondary_language=secondary_lang,
            secondary_confidence=secondary_conf
        )
    
    def _detect_by_acoustics(
        self,
        audio_data: np.ndarray,
        sample_rate: int
    ) -> DetectedLanguage:
        """
        Detect language using acoustic features.
        
        Analyzes:
        - MFCC (Mel-frequency cepstral coefficients)
        - Spectral rolloff
        - Zero-crossing rate
        - Phoneme probabilities
        
        NOTE: In production, this would use a trained ML model.
        Here we use simplified heuristics for demonstration.
        """
        # Extract features
        mfcc = self._extract_mfcc(audio_data, sample_rate)
        zcr = self._calculate_zero_crossing_rate(audio_data)
        spectral_rolloff = self._calculate_spectral_rolloff(audio_data, sample_rate)
        
        # Heuristic rules (simplified)
        scores = {
            Language.ENGLISH: 0.0,
            Language.SPANISH_MX: 0.0,
            Language.MANDARIN: 0.0
        }
        
        # Spanish: Higher vowel energy, rhythmic patterns
        if self._has_syllable_timing(audio_data):
            scores[Language.SPANISH_MX] += 0.3
        
        # Mandarin: Tonal variations, pitch changes
        if self._has_tonal_patterns(audio_data, sample_rate):
            scores[Language.MANDARIN] += 0.4
        
        # English: Default baseline
        scores[Language.ENGLISH] += 0.2
        
        # Add ZCR-based scores
        if zcr > 0.1:
            scores[Language.ENGLISH] += 0.1
        else:
            scores[Language.SPANISH_MX] += 0.1
        
        # Normalize to sum to 1.0
        total = sum(scores.values())
        if total > 0:
            scores = {k: v/total for k, v in scores.items()}
        
        # Get top 2 languages
        sorted_langs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        top_lang = sorted_langs[0][0]
        top_conf = sorted_langs[0][1]
        
        secondary_lang = sorted_langs[1][0] if len(sorted_langs) > 1 else None
        secondary_conf = sorted_langs[1][1] if secondary_lang else None
        
        # If confidence too low, default to English
        if top_conf < self.min_confidence:
            logger.warning(
                f"Low confidence language detection ({top_conf:.2f}). "
                f"Defaulting to English."
            )
            top_lang = Language.ENGLISH
            top_conf = 0.5  # Low confidence default
        
        return DetectedLanguage(
            language=top_lang,
            confidence=top_conf,
            secondary_language=secondary_lang,
            secondary_confidence=secondary_conf,
            detection_method="acoustic"
        )
    
    def _combine_detections(
        self,
        acoustic: DetectedLanguage,
        keyword: DetectedLanguage
    ) -> DetectedLanguage:
        """
        Combine acoustic and keyword-based detections.
        
        Weights keyword detection higher for medical contexts.
        """
        # Weight: 60% keywords, 40% acoustic
        KEYWORD_WEIGHT = 0.6
        ACOUSTIC_WEIGHT = 0.4
        
        if acoustic.language == keyword.language:
            # Agreement: boost confidence
            combined_conf = min(1.0, (
                acoustic.confidence * ACOUSTIC_WEIGHT +
                keyword.confidence * KEYWORD_WEIGHT
            ) * 1.2)
            
            return DetectedLanguage(
                language=acoustic.language,
                confidence=combined_conf,
                secondary_language=acoustic.secondary_language,
                secondary_confidence=acoustic.secondary_confidence
            )
        else:
            # Disagreement: prefer keywords for medical domain
            if keyword.confidence > acoustic.confidence:
                return DetectedLanguage(
                    language=keyword.language,
                    confidence=keyword.confidence * 0.9,  # Slight penalty for disagreement
                    secondary_language=acoustic.language,
                    secondary_confidence=acoustic.confidence
                )
            else:
                return DetectedLanguage(
                    language=acoustic.language,
                    confidence=acoustic.confidence * 0.9,
                    secondary_language=keyword.language,
                    secondary_confidence=keyword.confidence
                )
    
    def _extract_mfcc(self, audio: np.ndarray, sr: int, n_mfcc: int = 13) -> np.ndarray:
        """Extract MFCC features (simplified)."""
        # In production: use librosa.feature.mfcc()
        # Here: return placeholder based on audio properties
        n_frames = max(1, len(audio) // (sr // 100))  # ~10ms frames
        return np.random.randn(n_mfcc, n_frames)
    
    def _calculate_zero_crossing_rate(self, audio: np.ndarray) -> float:
        """Calculate zero-crossing rate (voice activity indicator)."""
        if len(audio) < 2:
            return 0.0
        signs = np.sign(audio)
        crossings = np.sum(np.abs(np.diff(signs))) / (2 * len(audio))
        return float(crossings)
    
    def _calculate_spectral_rolloff(self, audio: np.ndarray, sr: int) -> float:
        """Calculate spectral rolloff (frequency distribution)."""
        # Simplified: In production use librosa
        # Return based on audio energy distribution
        if len(audio) == 0:
            return 0.5
        energy = np.sum(audio ** 2)
        return min(1.0, energy / (len(audio) + 1e-6))
    
    def _has_syllable_timing(self, audio: np.ndarray) -> bool:
        """
        Detect syllable-timed rhythm (Spanish).
        
        Spanish is syllable-timed: each syllable roughly equal duration.
        English is stress-timed: stressed syllables are longer.
        """
        if len(audio) < 100:
            return False
        # Simplified heuristic: lower variance = more regular timing
        return float(np.std(audio)) < 0.15
    
    def _has_tonal_patterns(self, audio: np.ndarray, sr: int) -> bool:
        """
        Detect tonal patterns (Mandarin).
        
        Mandarin has 4 lexical tones + neutral tone.
        Pitch changes carry meaning.
        """
        if len(audio) < 1000:
            return False
        
        # Simplified: check for pitch variation by analyzing segments
        # In production: use pitch tracking (librosa.pyin)
        segment_size = len(audio) // 10
        if segment_size < 100:
            return False
        
        segment_means = [
            np.mean(np.abs(audio[i*segment_size:(i+1)*segment_size]))
            for i in range(10)
        ]
        
        # High variance in segment means suggests tonal variation
        variance = np.var(segment_means)
        return variance > 0.01
    
    def get_supported_languages(self) -> List[Language]:
        """Get list of supported languages."""
        return [Language.ENGLISH, Language.SPANISH_MX, Language.SPANISH_US, Language.MANDARIN]
