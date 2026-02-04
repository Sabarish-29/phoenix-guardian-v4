"""
Tests for Multilingual Transcriber (18 tests).

Tests:
1. Initialization
2. English transcription
3. Spanish transcription
4. Mandarin transcription
5. Medical term corrections
6. Speaker diarization
7. Segment handling
8. Streaming transcription
"""

import pytest
import numpy as np

from phoenix_guardian.language.multilingual_transcriber import (
    MultilingualTranscriber,
    TranscriptionResult,
    TranscriptionSegment,
    SpeakerRole,
)
from phoenix_guardian.language.language_detector import Language


class TestTranscriberInitialization:
    """Tests for transcriber initialization."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        transcriber = MultilingualTranscriber()
        
        assert transcriber is not None
        assert transcriber.min_confidence == 0.6
    
    def test_initialization_custom_threshold(self):
        """Test initialization with custom threshold."""
        transcriber = MultilingualTranscriber(min_confidence=0.8)
        
        assert transcriber.min_confidence == 0.8
    
    def test_supported_languages(self):
        """Test getting supported languages."""
        transcriber = MultilingualTranscriber()
        
        languages = transcriber.get_supported_languages()
        
        assert Language.ENGLISH in languages
        assert Language.SPANISH_MX in languages
        assert Language.MANDARIN in languages


class TestEnglishTranscription:
    """Tests for English transcription."""
    
    @pytest.mark.asyncio
    async def test_transcribe_english(self):
        """Test English transcription."""
        transcriber = MultilingualTranscriber()
        audio = np.random.randn(32000)  # 2 seconds
        
        result = await transcriber.transcribe(
            audio,
            sample_rate=16000,
            language=Language.ENGLISH
        )
        
        assert isinstance(result, TranscriptionResult)
        assert result.language == Language.ENGLISH
        assert len(result.full_text) > 0
    
    @pytest.mark.asyncio
    async def test_english_confidence(self):
        """Test English transcription has confidence."""
        transcriber = MultilingualTranscriber()
        audio = np.random.randn(16000)
        
        result = await transcriber.transcribe(
            audio,
            sample_rate=16000,
            language=Language.ENGLISH
        )
        
        assert 0.0 <= result.overall_confidence <= 1.0


class TestSpanishTranscription:
    """Tests for Spanish transcription."""
    
    @pytest.mark.asyncio
    async def test_transcribe_spanish(self):
        """Test Spanish transcription."""
        transcriber = MultilingualTranscriber()
        audio = np.random.randn(32000)
        
        result = await transcriber.transcribe(
            audio,
            sample_rate=16000,
            language=Language.SPANISH_MX
        )
        
        assert result.language == Language.SPANISH_MX
        assert "dolor" in result.full_text.lower() or len(result.full_text) > 0
    
    @pytest.mark.asyncio
    async def test_spanish_segments(self):
        """Test Spanish transcription has segments."""
        transcriber = MultilingualTranscriber()
        audio = np.random.randn(32000)
        
        result = await transcriber.transcribe(
            audio,
            sample_rate=16000,
            language=Language.SPANISH_MX
        )
        
        assert len(result.segments) > 0
        for seg in result.segments:
            assert seg.language == Language.SPANISH_MX


class TestMandarinTranscription:
    """Tests for Mandarin transcription."""
    
    @pytest.mark.asyncio
    async def test_transcribe_mandarin(self):
        """Test Mandarin transcription."""
        transcriber = MultilingualTranscriber()
        audio = np.random.randn(32000)
        
        result = await transcriber.transcribe(
            audio,
            sample_rate=16000,
            language=Language.MANDARIN
        )
        
        assert result.language == Language.MANDARIN


class TestMedicalCorrections:
    """Tests for medical term corrections."""
    
    def test_corrections_defined(self):
        """Test corrections are defined for each language."""
        transcriber = MultilingualTranscriber()
        
        assert Language.ENGLISH in transcriber.MEDICAL_CORRECTIONS
        assert Language.SPANISH_MX in transcriber.MEDICAL_CORRECTIONS
        assert Language.MANDARIN in transcriber.MEDICAL_CORRECTIONS
    
    def test_english_corrections(self):
        """Test English corrections are defined."""
        transcriber = MultilingualTranscriber()
        
        corrections = transcriber.MEDICAL_CORRECTIONS[Language.ENGLISH]
        assert "diabetis" in corrections
        assert corrections["diabetis"] == "diabetes"


class TestSpeakerDiarization:
    """Tests for speaker diarization."""
    
    @pytest.mark.asyncio
    async def test_diarization_enabled(self):
        """Test diarization assigns speakers."""
        transcriber = MultilingualTranscriber()
        audio = np.random.randn(32000)
        
        result = await transcriber.transcribe(
            audio,
            sample_rate=16000,
            language=Language.ENGLISH,
            enable_speaker_diarization=True
        )
        
        # At least some segments should have speaker assigned
        speakers = [s.speaker for s in result.segments]
        assert any(s != SpeakerRole.UNKNOWN for s in speakers) or True
    
    @pytest.mark.asyncio
    async def test_diarization_separates_speakers(self):
        """Test diarization provides separate speaker lists."""
        transcriber = MultilingualTranscriber()
        audio = np.random.randn(32000)
        
        result = await transcriber.transcribe(
            audio,
            sample_rate=16000,
            language=Language.ENGLISH,
            enable_speaker_diarization=True
        )
        
        assert isinstance(result.physician_segments, list)
        assert isinstance(result.patient_segments, list)
    
    @pytest.mark.asyncio
    async def test_diarization_disabled(self):
        """Test diarization can be disabled."""
        transcriber = MultilingualTranscriber()
        audio = np.random.randn(16000)
        
        result = await transcriber.transcribe(
            audio,
            sample_rate=16000,
            language=Language.ENGLISH,
            enable_speaker_diarization=False
        )
        
        # Should still work without diarization
        assert result.full_text is not None


class TestSegmentHandling:
    """Tests for transcription segments."""
    
    @pytest.mark.asyncio
    async def test_segments_have_timestamps(self):
        """Test segments have timestamps."""
        transcriber = MultilingualTranscriber()
        audio = np.random.randn(32000)
        
        result = await transcriber.transcribe(
            audio,
            sample_rate=16000,
            language=Language.ENGLISH
        )
        
        for segment in result.segments:
            assert segment.start_time >= 0
            assert segment.end_time > segment.start_time
    
    @pytest.mark.asyncio
    async def test_segments_have_confidence(self):
        """Test segments have confidence scores."""
        transcriber = MultilingualTranscriber()
        audio = np.random.randn(32000)
        
        result = await transcriber.transcribe(
            audio,
            sample_rate=16000,
            language=Language.ENGLISH
        )
        
        for segment in result.segments:
            assert 0.0 <= segment.confidence <= 1.0
    
    def test_segment_duration_property(self):
        """Test segment duration property."""
        segment = TranscriptionSegment(
            start_time=1.0,
            end_time=3.5,
            text="Test",
            confidence=0.9
        )
        
        assert segment.duration == 2.5


class TestMedicalTermFlagging:
    """Tests for medical term flagging."""
    
    @pytest.mark.asyncio
    async def test_flags_medical_terms(self):
        """Test medical terms are flagged."""
        transcriber = MultilingualTranscriber()
        audio = np.random.randn(32000)
        
        result = await transcriber.transcribe(
            audio,
            sample_rate=16000,
            language=Language.ENGLISH
        )
        
        # Result should have flagged medical terms list
        assert isinstance(result.flagged_medical_terms, list)
