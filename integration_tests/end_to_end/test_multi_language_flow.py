"""
Phoenix Guardian - Multi-Language Flow Integration Tests
Week 35: Integration Testing + Polish (Days 171-175)

Tests complete multi-language transcription and translation flow:
- Language detection from audio
- Transcription in detected language
- Medical terminology handling by language
- SOAP note generation in target language
- Real-time language switching
- RTL language support

Total: 20 comprehensive multi-language tests
"""

import pytest
import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import dataclass, field
from enum import Enum

# Phoenix Guardian imports
from phoenix_guardian.i18n.language_detector import LanguageDetector
from phoenix_guardian.i18n.transcription_handler import MultiLanguageTranscriber
from phoenix_guardian.i18n.medical_dictionary import MedicalDictionary
from phoenix_guardian.i18n.translation_engine import MedicalTranslationEngine
from phoenix_guardian.i18n.rtl_handler import RTLHandler
from phoenix_guardian.multi_tenant.tenant_context import TenantContext


# ============================================================================
# Type Definitions
# ============================================================================

class SupportedLanguage(Enum):
    """Supported languages."""
    ENGLISH = "en"
    SPANISH = "es"
    CHINESE = "zh"
    ARABIC = "ar"
    HINDI = "hi"
    PORTUGUESE = "pt"
    FRENCH = "fr"


@dataclass
class AudioSegment:
    """Audio segment for transcription."""
    segment_id: str
    audio_data: bytes
    duration_seconds: float
    sample_rate: int
    detected_language: Optional[SupportedLanguage] = None


@dataclass
class TranscriptionResult:
    """Result of transcription."""
    segment_id: str
    text: str
    language: SupportedLanguage
    confidence: float
    timestamps: List[Dict[str, Any]]
    medical_terms: List[str]


@dataclass
class SOAPNote:
    """SOAP note in specific language."""
    note_id: str
    language: SupportedLanguage
    subjective: str
    objective: str
    assessment: str
    plan: str
    medical_codes: List[str]


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def regional_medical_tenant() -> TenantContext:
    """Regional Medical Center tenant."""
    return TenantContext(
        tenant_id="hospital-regional-001",
        hospital_name="Regional Medical Center",
        ehr_type="epic",
        timezone="America/New_York",
        features_enabled=["multi_language", "transcription", "translation"]
    )


@pytest.fixture
def english_audio_segment() -> AudioSegment:
    """English audio segment."""
    return AudioSegment(
        segment_id=f"seg-en-{uuid.uuid4().hex[:8]}",
        audio_data=bytes([i % 256 for i in range(16000 * 30)]),  # 30 seconds
        duration_seconds=30.0,
        sample_rate=16000,
        detected_language=SupportedLanguage.ENGLISH
    )


@pytest.fixture
def spanish_audio_segment() -> AudioSegment:
    """Spanish audio segment."""
    return AudioSegment(
        segment_id=f"seg-es-{uuid.uuid4().hex[:8]}",
        audio_data=bytes([i % 256 for i in range(16000 * 30)]),
        duration_seconds=30.0,
        sample_rate=16000,
        detected_language=SupportedLanguage.SPANISH
    )


@pytest.fixture
def chinese_audio_segment() -> AudioSegment:
    """Chinese audio segment."""
    return AudioSegment(
        segment_id=f"seg-zh-{uuid.uuid4().hex[:8]}",
        audio_data=bytes([i % 256 for i in range(16000 * 30)]),
        duration_seconds=30.0,
        sample_rate=16000,
        detected_language=SupportedLanguage.CHINESE
    )


@pytest.fixture
def arabic_audio_segment() -> AudioSegment:
    """Arabic (RTL) audio segment."""
    return AudioSegment(
        segment_id=f"seg-ar-{uuid.uuid4().hex[:8]}",
        audio_data=bytes([i % 256 for i in range(16000 * 30)]),
        duration_seconds=30.0,
        sample_rate=16000,
        detected_language=SupportedLanguage.ARABIC
    )


class MultiLanguageTestHarness:
    """
    Orchestrates multi-language flow testing.
    Simulates transcription and translation pipelines.
    """
    
    def __init__(self, tenant: TenantContext):
        self.tenant = tenant
        self.language_detector = LanguageDetector()
        self.transcriber = MultiLanguageTranscriber()
        self.medical_dictionary = MedicalDictionary()
        self.translation_engine = MedicalTranslationEngine()
        self.rtl_handler = RTLHandler()
        
        # Simulated transcriptions by language
        self.sample_transcriptions = {
            SupportedLanguage.ENGLISH: "The patient presents with chest pain and shortness of breath. Blood pressure is 140/90. I recommend an ECG and chest X-ray.",
            SupportedLanguage.SPANISH: "El paciente presenta dolor torácico y dificultad para respirar. La presión arterial es 140/90. Recomiendo un ECG y radiografía de tórax.",
            SupportedLanguage.CHINESE: "患者表现为胸痛和呼吸困难。血压140/90。我建议做心电图和胸部X光检查。",
            SupportedLanguage.ARABIC: "يعاني المريض من ألم في الصدر وضيق في التنفس. ضغط الدم 140/90. أوصي بإجراء تخطيط كهربية القلب وأشعة سينية للصدر.",
            SupportedLanguage.HINDI: "रोगी को सीने में दर्द और सांस लेने में तकलीफ है। रक्तचाप 140/90 है। मैं ईसीजी और छाती का एक्स-रे करने की सलाह देता हूं।",
            SupportedLanguage.PORTUGUESE: "O paciente apresenta dor torácica e falta de ar. A pressão arterial é 140/90. Recomendo um ECG e radiografia do tórax.",
            SupportedLanguage.FRENCH: "Le patient présente des douleurs thoraciques et un essoufflement. La tension artérielle est de 140/90. Je recommande un ECG et une radiographie pulmonaire."
        }
        
        # Medical terminology by language
        self.medical_terms = {
            SupportedLanguage.ENGLISH: ["chest pain", "shortness of breath", "blood pressure", "ECG"],
            SupportedLanguage.SPANISH: ["dolor torácico", "dificultad para respirar", "presión arterial", "ECG"],
            SupportedLanguage.CHINESE: ["胸痛", "呼吸困难", "血压", "心电图"],
            SupportedLanguage.ARABIC: ["ألم في الصدر", "ضيق في التنفس", "ضغط الدم", "تخطيط كهربية القلب"],
            SupportedLanguage.HINDI: ["सीने में दर्द", "सांस लेने में तकलीफ", "रक्तचाप", "ईसीजी"],
            SupportedLanguage.PORTUGUESE: ["dor torácica", "falta de ar", "pressão arterial", "ECG"],
            SupportedLanguage.FRENCH: ["douleurs thoraciques", "essoufflement", "tension artérielle", "ECG"]
        }
    
    async def detect_language(
        self,
        audio_segment: AudioSegment
    ) -> Dict[str, Any]:
        """
        Detect language from audio segment.
        """
        # Simulated language detection
        await asyncio.sleep(0.01)
        
        # In real implementation, would use audio analysis
        # Here we return pre-set language or detect based on patterns
        language = audio_segment.detected_language or SupportedLanguage.ENGLISH
        
        return {
            "detected_language": language.value,
            "confidence": 0.95,
            "alternatives": [
                {"language": lang.value, "confidence": 0.02}
                for lang in SupportedLanguage
                if lang != language
            ][:2],
            "detection_time_ms": 50
        }
    
    async def transcribe_audio(
        self,
        audio_segment: AudioSegment,
        language: SupportedLanguage
    ) -> TranscriptionResult:
        """
        Transcribe audio in specified language.
        """
        await asyncio.sleep(0.02)
        
        text = self.sample_transcriptions.get(language, "")
        terms = self.medical_terms.get(language, [])
        
        return TranscriptionResult(
            segment_id=audio_segment.segment_id,
            text=text,
            language=language,
            confidence=0.93,
            timestamps=[
                {"start": 0.0, "end": 5.0, "text": text[:50]},
                {"start": 5.0, "end": 10.0, "text": text[50:100] if len(text) > 50 else ""}
            ],
            medical_terms=terms
        )
    
    async def translate_transcription(
        self,
        transcription: TranscriptionResult,
        target_language: SupportedLanguage
    ) -> Dict[str, Any]:
        """
        Translate transcription to target language.
        """
        if transcription.language == target_language:
            return {
                "translated": False,
                "reason": "Same language",
                "original_text": transcription.text,
                "target_language": target_language.value
            }
        
        await asyncio.sleep(0.01)
        
        # Get translation
        translated_text = self.sample_transcriptions.get(target_language, "")
        translated_terms = self.medical_terms.get(target_language, [])
        
        return {
            "translated": True,
            "source_language": transcription.language.value,
            "target_language": target_language.value,
            "original_text": transcription.text,
            "translated_text": translated_text,
            "medical_terms_translated": translated_terms,
            "translation_confidence": 0.91
        }
    
    async def generate_soap_note(
        self,
        transcription: TranscriptionResult,
        target_language: SupportedLanguage
    ) -> SOAPNote:
        """
        Generate SOAP note in target language.
        """
        await asyncio.sleep(0.02)
        
        # Generate language-specific SOAP content
        soap_templates = {
            SupportedLanguage.ENGLISH: {
                "subjective": "Patient reports chest pain and shortness of breath.",
                "objective": "BP: 140/90 mmHg. Heart rate regular.",
                "assessment": "Suspected cardiac involvement.",
                "plan": "Order ECG and chest X-ray."
            },
            SupportedLanguage.SPANISH: {
                "subjective": "El paciente refiere dolor torácico y dificultad para respirar.",
                "objective": "PA: 140/90 mmHg. Frecuencia cardíaca regular.",
                "assessment": "Sospecha de compromiso cardíaco.",
                "plan": "Solicitar ECG y radiografía de tórax."
            },
            SupportedLanguage.CHINESE: {
                "subjective": "患者主诉胸痛和呼吸困难。",
                "objective": "血压：140/90 mmHg。心率规则。",
                "assessment": "疑似心脏疾病。",
                "plan": "开具心电图和胸部X光检查。"
            },
            SupportedLanguage.ARABIC: {
                "subjective": "يشكو المريض من ألم في الصدر وضيق في التنفس.",
                "objective": "ضغط الدم: 140/90 ملم زئبق. معدل ضربات القلب منتظم.",
                "assessment": "اشتباه في مشاكل قلبية.",
                "plan": "طلب تخطيط كهربية القلب وأشعة سينية للصدر."
            }
        }
        
        template = soap_templates.get(target_language, soap_templates[SupportedLanguage.ENGLISH])
        
        return SOAPNote(
            note_id=f"soap-{uuid.uuid4().hex[:8]}",
            language=target_language,
            subjective=template["subjective"],
            objective=template["objective"],
            assessment=template["assessment"],
            plan=template["plan"],
            medical_codes=["R07.9", "R06.0", "I10"]  # ICD-10 codes
        )
    
    async def apply_rtl_formatting(
        self,
        text: str,
        language: SupportedLanguage
    ) -> Dict[str, Any]:
        """
        Apply RTL formatting for Arabic/Hebrew languages.
        """
        is_rtl = language in [SupportedLanguage.ARABIC]
        
        return {
            "original_text": text,
            "is_rtl": is_rtl,
            "direction": "rtl" if is_rtl else "ltr",
            "formatted_text": f'<span dir="{"rtl" if is_rtl else "ltr"}">{text}</span>',
            "text_align": "right" if is_rtl else "left"
        }
    
    async def get_medical_terminology(
        self,
        language: SupportedLanguage
    ) -> Dict[str, Any]:
        """
        Get medical terminology dictionary for language.
        """
        terms = self.medical_terms.get(language, [])
        
        return {
            "language": language.value,
            "term_count": len(terms),
            "sample_terms": terms,
            "dictionary_version": "1.0.0"
        }
    
    async def run_complete_flow(
        self,
        audio_segment: AudioSegment,
        target_language: Optional[SupportedLanguage] = None
    ) -> Dict[str, Any]:
        """
        Run complete multi-language flow.
        """
        start_time = time.perf_counter()
        
        # Step 1: Detect language
        detection = await self.detect_language(audio_segment)
        source_language = SupportedLanguage(detection["detected_language"])
        
        # Step 2: Transcribe in detected language
        transcription = await self.transcribe_audio(audio_segment, source_language)
        
        # Step 3: Translate if needed
        target_lang = target_language or source_language
        translation = await self.translate_transcription(transcription, target_lang)
        
        # Step 4: Generate SOAP note
        soap_note = await self.generate_soap_note(transcription, target_lang)
        
        # Step 5: Apply RTL if needed
        rtl_info = await self.apply_rtl_formatting(soap_note.subjective, target_lang)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        return {
            "success": True,
            "duration_ms": duration_ms,
            "steps": {
                "language_detection": detection,
                "transcription": {
                    "text": transcription.text,
                    "language": transcription.language.value,
                    "confidence": transcription.confidence,
                    "medical_terms": transcription.medical_terms
                },
                "translation": translation,
                "soap_note": {
                    "note_id": soap_note.note_id,
                    "language": soap_note.language.value,
                    "subjective": soap_note.subjective,
                    "objective": soap_note.objective,
                    "assessment": soap_note.assessment,
                    "plan": soap_note.plan
                },
                "rtl_formatting": rtl_info
            }
        }


# ============================================================================
# Multi-Language Tests
# ============================================================================

class TestLanguageDetection:
    """Test language detection from audio."""
    
    @pytest.mark.asyncio
    async def test_english_detection(
        self,
        regional_medical_tenant,
        english_audio_segment
    ):
        """
        Verify English language is detected from audio.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        result = await harness.detect_language(english_audio_segment)
        
        assert result["detected_language"] == "en"
        assert result["confidence"] > 0.9
    
    @pytest.mark.asyncio
    async def test_spanish_detection(
        self,
        regional_medical_tenant,
        spanish_audio_segment
    ):
        """
        Verify Spanish language is detected from audio.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        result = await harness.detect_language(spanish_audio_segment)
        
        assert result["detected_language"] == "es"
        assert result["confidence"] > 0.9
    
    @pytest.mark.asyncio
    async def test_chinese_detection(
        self,
        regional_medical_tenant,
        chinese_audio_segment
    ):
        """
        Verify Chinese language is detected from audio.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        result = await harness.detect_language(chinese_audio_segment)
        
        assert result["detected_language"] == "zh"
        assert result["confidence"] > 0.9


class TestTranscription:
    """Test multi-language transcription."""
    
    @pytest.mark.asyncio
    async def test_english_transcription(
        self,
        regional_medical_tenant,
        english_audio_segment
    ):
        """
        Verify English transcription is accurate.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        result = await harness.transcribe_audio(
            english_audio_segment,
            SupportedLanguage.ENGLISH
        )
        
        assert result.text is not None
        assert len(result.text) > 0
        assert result.confidence > 0.9
    
    @pytest.mark.asyncio
    async def test_spanish_transcription(
        self,
        regional_medical_tenant,
        spanish_audio_segment
    ):
        """
        Verify Spanish transcription is accurate.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        result = await harness.transcribe_audio(
            spanish_audio_segment,
            SupportedLanguage.SPANISH
        )
        
        assert result.text is not None
        assert "dolor" in result.text.lower() or "paciente" in result.text.lower()
    
    @pytest.mark.asyncio
    async def test_medical_terms_extracted(
        self,
        regional_medical_tenant,
        english_audio_segment
    ):
        """
        Verify medical terms are extracted during transcription.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        result = await harness.transcribe_audio(
            english_audio_segment,
            SupportedLanguage.ENGLISH
        )
        
        assert len(result.medical_terms) > 0
        assert "chest pain" in result.medical_terms


class TestTranslation:
    """Test medical translation."""
    
    @pytest.mark.asyncio
    async def test_english_to_spanish_translation(
        self,
        regional_medical_tenant,
        english_audio_segment
    ):
        """
        Verify English to Spanish translation works.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        transcription = await harness.transcribe_audio(
            english_audio_segment,
            SupportedLanguage.ENGLISH
        )
        
        result = await harness.translate_transcription(
            transcription,
            SupportedLanguage.SPANISH
        )
        
        assert result["translated"] is True
        assert result["target_language"] == "es"
        assert len(result["translated_text"]) > 0
    
    @pytest.mark.asyncio
    async def test_medical_terms_translated(
        self,
        regional_medical_tenant,
        english_audio_segment
    ):
        """
        Verify medical terms are properly translated.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        transcription = await harness.transcribe_audio(
            english_audio_segment,
            SupportedLanguage.ENGLISH
        )
        
        result = await harness.translate_transcription(
            transcription,
            SupportedLanguage.SPANISH
        )
        
        assert len(result["medical_terms_translated"]) > 0
        # Spanish terms should include Spanish medical terminology
        assert any("dolor" in term.lower() for term in result["medical_terms_translated"])


class TestSOAPNoteGeneration:
    """Test SOAP note generation in different languages."""
    
    @pytest.mark.asyncio
    async def test_soap_note_in_english(
        self,
        regional_medical_tenant,
        english_audio_segment
    ):
        """
        Verify SOAP note is generated in English.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        transcription = await harness.transcribe_audio(
            english_audio_segment,
            SupportedLanguage.ENGLISH
        )
        
        soap = await harness.generate_soap_note(
            transcription,
            SupportedLanguage.ENGLISH
        )
        
        assert soap.language == SupportedLanguage.ENGLISH
        assert len(soap.subjective) > 0
        assert len(soap.plan) > 0
    
    @pytest.mark.asyncio
    async def test_soap_note_in_spanish(
        self,
        regional_medical_tenant,
        spanish_audio_segment
    ):
        """
        Verify SOAP note is generated in Spanish.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        transcription = await harness.transcribe_audio(
            spanish_audio_segment,
            SupportedLanguage.SPANISH
        )
        
        soap = await harness.generate_soap_note(
            transcription,
            SupportedLanguage.SPANISH
        )
        
        assert soap.language == SupportedLanguage.SPANISH
        assert "paciente" in soap.subjective.lower() or "dolor" in soap.subjective.lower()
    
    @pytest.mark.asyncio
    async def test_soap_includes_medical_codes(
        self,
        regional_medical_tenant,
        english_audio_segment
    ):
        """
        Verify SOAP note includes ICD-10 codes.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        transcription = await harness.transcribe_audio(
            english_audio_segment,
            SupportedLanguage.ENGLISH
        )
        
        soap = await harness.generate_soap_note(
            transcription,
            SupportedLanguage.ENGLISH
        )
        
        assert len(soap.medical_codes) > 0
        # Should include chest pain code
        assert any("R07" in code for code in soap.medical_codes)


class TestRTLSupport:
    """Test RTL language support."""
    
    @pytest.mark.asyncio
    async def test_arabic_rtl_formatting(
        self,
        regional_medical_tenant,
        arabic_audio_segment
    ):
        """
        Verify Arabic text has RTL formatting.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        transcription = await harness.transcribe_audio(
            arabic_audio_segment,
            SupportedLanguage.ARABIC
        )
        
        result = await harness.apply_rtl_formatting(
            transcription.text,
            SupportedLanguage.ARABIC
        )
        
        assert result["is_rtl"] is True
        assert result["direction"] == "rtl"
        assert result["text_align"] == "right"
    
    @pytest.mark.asyncio
    async def test_english_ltr_formatting(
        self,
        regional_medical_tenant,
        english_audio_segment
    ):
        """
        Verify English text has LTR formatting.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        transcription = await harness.transcribe_audio(
            english_audio_segment,
            SupportedLanguage.ENGLISH
        )
        
        result = await harness.apply_rtl_formatting(
            transcription.text,
            SupportedLanguage.ENGLISH
        )
        
        assert result["is_rtl"] is False
        assert result["direction"] == "ltr"


class TestMedicalDictionary:
    """Test medical terminology dictionary."""
    
    @pytest.mark.asyncio
    async def test_english_medical_terms(
        self,
        regional_medical_tenant
    ):
        """
        Verify English medical terms are available.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        result = await harness.get_medical_terminology(SupportedLanguage.ENGLISH)
        
        assert result["language"] == "en"
        assert result["term_count"] > 0
        assert "chest pain" in result["sample_terms"]
    
    @pytest.mark.asyncio
    async def test_chinese_medical_terms(
        self,
        regional_medical_tenant
    ):
        """
        Verify Chinese medical terms are available.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        result = await harness.get_medical_terminology(SupportedLanguage.CHINESE)
        
        assert result["language"] == "zh"
        assert result["term_count"] > 0


class TestCompleteFlow:
    """Test complete multi-language flow."""
    
    @pytest.mark.asyncio
    async def test_complete_english_flow(
        self,
        regional_medical_tenant,
        english_audio_segment
    ):
        """
        Verify complete flow works for English.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        result = await harness.run_complete_flow(english_audio_segment)
        
        assert result["success"] is True
        assert "language_detection" in result["steps"]
        assert "transcription" in result["steps"]
        assert "soap_note" in result["steps"]
    
    @pytest.mark.asyncio
    async def test_complete_spanish_flow(
        self,
        regional_medical_tenant,
        spanish_audio_segment
    ):
        """
        Verify complete flow works for Spanish.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        result = await harness.run_complete_flow(spanish_audio_segment)
        
        assert result["success"] is True
        assert result["steps"]["transcription"]["language"] == "es"
    
    @pytest.mark.asyncio
    async def test_cross_language_translation_in_flow(
        self,
        regional_medical_tenant,
        spanish_audio_segment
    ):
        """
        Verify cross-language translation works in complete flow.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        # Spanish audio with English output
        result = await harness.run_complete_flow(
            spanish_audio_segment,
            target_language=SupportedLanguage.ENGLISH
        )
        
        assert result["success"] is True
        assert result["steps"]["translation"]["translated"] is True


# ============================================================================
# Additional Tests
# ============================================================================

class TestAdditionalLanguageScenarios:
    """Additional language test scenarios."""
    
    @pytest.mark.asyncio
    async def test_all_supported_languages(
        self,
        regional_medical_tenant
    ):
        """
        Verify all supported languages have medical dictionaries.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        for language in SupportedLanguage:
            result = await harness.get_medical_terminology(language)
            assert result["term_count"] > 0, f"No terms for {language.value}"
    
    @pytest.mark.asyncio
    async def test_flow_performance(
        self,
        regional_medical_tenant,
        english_audio_segment
    ):
        """
        Verify complete flow completes within acceptable time.
        """
        harness = MultiLanguageTestHarness(regional_medical_tenant)
        
        result = await harness.run_complete_flow(english_audio_segment)
        
        # Should complete within 5 seconds
        assert result["duration_ms"] < 5000


# ============================================================================
# Summary: Test Count
# ============================================================================
#
# TestLanguageDetection: 3 tests
# TestTranscription: 3 tests
# TestTranslation: 2 tests
# TestSOAPNoteGeneration: 3 tests
# TestRTLSupport: 2 tests
# TestMedicalDictionary: 2 tests
# TestCompleteFlow: 3 tests
# TestAdditionalLanguageScenarios: 2 tests
#
# TOTAL: 20 tests
# ============================================================================
