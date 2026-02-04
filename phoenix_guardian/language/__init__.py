"""
Multi-language support for Phoenix Guardian.

Enables clinical documentation for Spanish and Mandarin-speaking patients.

Supported Languages:
- English (en-US) - Primary clinical language
- Spanish (es-MX, es-US) - 44M speakers in US
- Mandarin (zh-CN) - 3.5M speakers in US

Architecture:
1. Language Detection → Auto-detect patient's language
2. Speech-to-Text → Transcribe in source language
3. Medical NER → Extract clinical entities
4. Translation → Convert to English for SOAP note
5. Back-translation → Patient instructions in their language
"""

from phoenix_guardian.language.language_detector import (
    LanguageDetector,
    DetectedLanguage,
    Language,
)
from phoenix_guardian.language.multilingual_transcriber import (
    MultilingualTranscriber,
    TranscriptionResult,
    TranscriptionSegment,
    SpeakerRole,
)
from phoenix_guardian.language.medical_ner_multilingual import (
    MedicalNERMultilingual,
    MedicalEntity,
    EntityType,
    NERResult,
)
from phoenix_guardian.language.medical_translator import (
    MedicalTranslator,
    TranslationResult,
    TranslationQuality,
)
from phoenix_guardian.language.translation_quality_scorer import (
    TranslationQualityScorer,
    QualityScore,
    QualityDimension,
)
from phoenix_guardian.language.patient_communication_generator import (
    PatientCommunicationGenerator,
    DischargeInstructions,
    CommunicationType,
)

__all__ = [
    # Language Detection
    'LanguageDetector',
    'DetectedLanguage',
    'Language',
    # Transcription
    'MultilingualTranscriber',
    'TranscriptionResult',
    'TranscriptionSegment',
    'SpeakerRole',
    # Medical NER
    'MedicalNERMultilingual',
    'MedicalEntity',
    'EntityType',
    'NERResult',
    # Translation
    'MedicalTranslator',
    'TranslationResult',
    'TranslationQuality',
    # Quality Scoring
    'TranslationQualityScorer',
    'QualityScore',
    'QualityDimension',
    # Patient Communication
    'PatientCommunicationGenerator',
    'DischargeInstructions',
    'CommunicationType',
]
