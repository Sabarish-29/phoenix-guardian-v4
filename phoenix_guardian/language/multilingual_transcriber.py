"""
Multilingual Speech-to-Text Transcriber.

Converts audio to text in English, Spanish, or Mandarin.

SPEECH RECOGNITION ENGINES:
- English: Whisper (OpenAI) - Medical fine-tuned
- Spanish: Whisper multilingual
- Mandarin: Whisper multilingual

MEDICAL VOCABULARY:
- Custom medical term dictionary per language
- Proper noun handling (medication names, diseases)
- Acronym expansion (COPD, CHF, MI)

QUALITY ASSURANCE:
- Confidence scoring per word
- Alternative hypotheses for ambiguous sections
- Speaker diarization (patient vs physician)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import logging
import numpy as np

from phoenix_guardian.language.language_detector import Language

logger = logging.getLogger(__name__)


class SpeakerRole(Enum):
    """Speaker roles in clinical conversation."""
    PHYSICIAN = "physician"
    PATIENT = "patient"
    FAMILY = "family"
    INTERPRETER = "interpreter"
    UNKNOWN = "unknown"


@dataclass
class TranscriptionSegment:
    """
    Single segment of transcribed text.
    
    Attributes:
        start_time: Seconds from start of audio
        end_time: Seconds from start of audio
        text: Transcribed text content
        confidence: ASR confidence (0.0 - 1.0)
        speaker: Identified speaker role
        language: Language of this segment
        alternatives: Alternative transcriptions for low-confidence segments
    """
    start_time: float              # Seconds from start
    end_time: float                # Seconds from start
    text: str                      # Transcribed text
    confidence: float              # 0.0 - 1.0
    speaker: SpeakerRole = SpeakerRole.UNKNOWN
    language: Language = Language.ENGLISH
    
    # Alternative hypotheses (for low-confidence segments)
    alternatives: List[str] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        """Duration of segment in seconds."""
        return self.end_time - self.start_time


@dataclass
class TranscriptionResult:
    """
    Complete transcription result.
    
    Attributes:
        full_text: Complete transcript as single string
        segments: List of timestamped segments
        language: Primary language of transcription
        overall_confidence: Average confidence across segments
        duration_seconds: Total audio duration
        flagged_medical_terms: Medical terms detected
        physician_segments: Segments attributed to physician
        patient_segments: Segments attributed to patient
    """
    full_text: str                 # Complete transcript
    segments: List[TranscriptionSegment]
    language: Language
    overall_confidence: float
    duration_seconds: float
    
    # Medical entities flagged during transcription
    flagged_medical_terms: List[str] = field(default_factory=list)
    
    # Speaker attribution
    physician_segments: List[TranscriptionSegment] = field(default_factory=list)
    patient_segments: List[TranscriptionSegment] = field(default_factory=list)
    
    def get_speaker_text(self, role: SpeakerRole) -> str:
        """Get all text from a specific speaker."""
        if role == SpeakerRole.PHYSICIAN:
            return " ".join(s.text for s in self.physician_segments)
        elif role == SpeakerRole.PATIENT:
            return " ".join(s.text for s in self.patient_segments)
        else:
            return " ".join(s.text for s in self.segments if s.speaker == role)


class MultilingualTranscriber:
    """
    Transcribes medical audio in multiple languages.
    
    Integrates with:
    - OpenAI Whisper (multilingual ASR)
    - Medical term dictionaries
    - Speaker diarization
    
    Example:
        transcriber = MultilingualTranscriber()
        result = await transcriber.transcribe(
            audio_data, 
            sample_rate=16000,
            language=Language.SPANISH_MX
        )
        print(f"Transcript: {result.full_text}")
        print(f"Confidence: {result.overall_confidence:.0%}")
    """
    
    # Medical term corrections per language
    MEDICAL_CORRECTIONS = {
        Language.SPANISH_MX: {
            # Common mishearings → correct term
            "diabete": "diabetes",
            "hipersensión": "hipertensión",
            "infardo": "infarto",
            "azma": "asma",
            "artritis": "artritis",
            "colestrol": "colesterol",
            "precion": "presión",
            "medecina": "medicina",
        },
        Language.SPANISH_US: {
            "diabete": "diabetes",
            "hipersensión": "hipertensión",
            "infardo": "infarto",
        },
        Language.MANDARIN: {
            "糖尿病": "糖尿病",  # Diabetes
            "高血压": "高血压",  # Hypertension
            "哮喘": "哮喘",      # Asthma
        },
        Language.ENGLISH: {
            "diabetis": "diabetes",
            "diabeties": "diabetes",
            "hypertention": "hypertension",
            "arthritus": "arthritis",
            "metforman": "metformin",
            "lisinipril": "lisinopril",
        }
    }
    
    # Whisper language code mapping
    WHISPER_LANG_MAP = {
        Language.ENGLISH: "en",
        Language.SPANISH_MX: "es",
        Language.SPANISH_US: "es",
        Language.MANDARIN: "zh"
    }
    
    def __init__(self, min_confidence: float = 0.6):
        """
        Initialize transcriber.
        
        Args:
            min_confidence: Minimum confidence for accepting transcription
        """
        self.min_confidence = min_confidence
        self.medical_dicts = self._load_medical_dictionaries()
    
    async def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        language: Language,
        enable_speaker_diarization: bool = True
    ) -> TranscriptionResult:
        """
        Transcribe audio to text.
        
        Args:
            audio_data: Audio samples as numpy array
            sample_rate: Sample rate in Hz
            language: Detected language for transcription
            enable_speaker_diarization: Whether to identify speakers
        
        Returns:
            TranscriptionResult with segments and confidence
        """
        duration = len(audio_data) / sample_rate
        
        logger.info(
            f"Transcribing {duration:.1f}s audio in {language.value}"
        )
        
        # Step 1: Speech-to-text
        segments = await self._transcribe_segments(
            audio_data,
            sample_rate,
            language
        )
        
        # Step 2: Apply medical term corrections
        segments = self._apply_medical_corrections(segments, language)
        
        # Step 3: Speaker diarization (if enabled)
        if enable_speaker_diarization:
            segments = await self._diarize_speakers(segments, audio_data, sample_rate)
        
        # Step 4: Calculate overall confidence
        overall_conf = float(np.mean([s.confidence for s in segments])) if segments else 0.0
        
        # Step 5: Extract full text
        full_text = " ".join(s.text for s in segments)
        
        # Step 6: Separate by speaker
        physician_segs = [s for s in segments if s.speaker == SpeakerRole.PHYSICIAN]
        patient_segs = [s for s in segments if s.speaker == SpeakerRole.PATIENT]
        
        # Step 7: Flag medical terms
        flagged_terms = self._flag_medical_terms(full_text, language)
        
        return TranscriptionResult(
            full_text=full_text,
            segments=segments,
            language=language,
            overall_confidence=round(overall_conf, 3),
            duration_seconds=duration,
            flagged_medical_terms=flagged_terms,
            physician_segments=physician_segs,
            patient_segments=patient_segs
        )
    
    async def transcribe_streaming(
        self,
        audio_stream,
        sample_rate: int,
        language: Language,
        on_segment: Optional[callable] = None
    ):
        """
        Transcribe audio in real-time streaming mode.
        
        Args:
            audio_stream: Async generator yielding audio chunks
            sample_rate: Sample rate in Hz
            language: Language for transcription
            on_segment: Callback for each transcribed segment
        
        Yields:
            TranscriptionSegment as they become available
        """
        buffer = np.array([], dtype=np.float32)
        segment_id = 0
        current_time = 0.0
        
        async for chunk in audio_stream:
            buffer = np.concatenate([buffer, chunk])
            
            # Process when we have enough audio (e.g., 2 seconds)
            if len(buffer) >= sample_rate * 2:
                segments = await self._transcribe_segments(
                    buffer, sample_rate, language
                )
                
                for seg in segments:
                    # Adjust timestamps
                    seg.start_time += current_time
                    seg.end_time += current_time
                    
                    if on_segment:
                        on_segment(seg)
                    
                    yield seg
                
                current_time += len(buffer) / sample_rate
                buffer = np.array([], dtype=np.float32)
    
    async def _transcribe_segments(
        self,
        audio: np.ndarray,
        sr: int,
        language: Language
    ) -> List[TranscriptionSegment]:
        """
        Transcribe audio into timestamped segments.
        
        Uses Whisper API (or similar) to get word-level timestamps.
        """
        whisper_lang = self.WHISPER_LANG_MAP.get(language, "en")
        
        # In production: Call OpenAI Whisper API or run local Whisper
        # response = await whisper_api.transcribe(
        #     audio=audio,
        #     language=whisper_lang,
        #     task="transcribe",
        #     word_timestamps=True
        # )
        
        # Simulated transcription based on language
        duration = len(audio) / sr
        
        if language in (Language.SPANISH_MX, Language.SPANISH_US):
            mock_segments = self._generate_spanish_mock_segments(duration)
        elif language == Language.MANDARIN:
            mock_segments = self._generate_mandarin_mock_segments(duration)
        else:
            mock_segments = self._generate_english_mock_segments(duration)
        
        return mock_segments
    
    def _generate_spanish_mock_segments(self, duration: float) -> List[TranscriptionSegment]:
        """Generate mock Spanish transcription segments."""
        segments = [
            TranscriptionSegment(
                start_time=0.0,
                end_time=min(3.5, duration * 0.3),
                text="Tengo dolor en el pecho",
                confidence=0.92,
                language=Language.SPANISH_MX
            ),
            TranscriptionSegment(
                start_time=min(3.5, duration * 0.3),
                end_time=min(6.0, duration * 0.5),
                text="desde hace dos días",
                confidence=0.88,
                language=Language.SPANISH_MX
            ),
            TranscriptionSegment(
                start_time=min(6.0, duration * 0.5),
                end_time=min(10.0, duration * 0.8),
                text="especialmente cuando camino",
                confidence=0.85,
                language=Language.SPANISH_MX
            ),
        ]
        return [s for s in segments if s.end_time <= duration]
    
    def _generate_mandarin_mock_segments(self, duration: float) -> List[TranscriptionSegment]:
        """Generate mock Mandarin transcription segments."""
        segments = [
            TranscriptionSegment(
                start_time=0.0,
                end_time=min(3.0, duration * 0.3),
                text="我胸口疼",
                confidence=0.90,
                language=Language.MANDARIN
            ),
            TranscriptionSegment(
                start_time=min(3.0, duration * 0.3),
                end_time=min(5.5, duration * 0.5),
                text="已经两天了",
                confidence=0.87,
                language=Language.MANDARIN
            ),
        ]
        return [s for s in segments if s.end_time <= duration]
    
    def _generate_english_mock_segments(self, duration: float) -> List[TranscriptionSegment]:
        """Generate mock English transcription segments."""
        segments = [
            TranscriptionSegment(
                start_time=0.0,
                end_time=min(3.0, duration * 0.25),
                text="I have chest pain",
                confidence=0.94,
                language=Language.ENGLISH
            ),
            TranscriptionSegment(
                start_time=min(3.0, duration * 0.25),
                end_time=min(5.5, duration * 0.45),
                text="for the past two days",
                confidence=0.91,
                language=Language.ENGLISH
            ),
            TranscriptionSegment(
                start_time=min(5.5, duration * 0.45),
                end_time=min(9.0, duration * 0.75),
                text="especially when I walk or climb stairs",
                confidence=0.89,
                language=Language.ENGLISH
            ),
        ]
        return [s for s in segments if s.end_time <= duration]
    
    def _apply_medical_corrections(
        self,
        segments: List[TranscriptionSegment],
        language: Language
    ) -> List[TranscriptionSegment]:
        """
        Apply medical term corrections.
        
        Fixes common ASR errors in medical terminology.
        """
        corrections = self.MEDICAL_CORRECTIONS.get(language, {})
        
        for segment in segments:
            original_text = segment.text
            for wrong, correct in corrections.items():
                if wrong.lower() in segment.text.lower():
                    # Case-insensitive replacement
                    import re
                    pattern = re.compile(re.escape(wrong), re.IGNORECASE)
                    segment.text = pattern.sub(correct, segment.text)
            
            if segment.text != original_text:
                logger.debug(f"Corrected: '{original_text}' → '{segment.text}'")
        
        return segments
    
    async def _diarize_speakers(
        self,
        segments: List[TranscriptionSegment],
        audio: np.ndarray,
        sr: int
    ) -> List[TranscriptionSegment]:
        """
        Identify speakers (physician vs patient).
        
        Uses voice characteristics + conversation patterns.
        """
        # In production: Use pyannote.audio or similar diarization
        
        # Simplified heuristic based on conversation patterns:
        # - Questions (ending with ?) → likely physician
        # - Short responses → likely patient
        # - Medical terminology → could be either
        # - Alternating pattern is typical
        
        current_speaker = SpeakerRole.UNKNOWN
        
        for i, segment in enumerate(segments):
            text = segment.text.strip()
            
            # Check for question patterns
            is_question = (
                text.endswith("?") or
                text.lower().startswith(("what", "how", "when", "where", "do you", "are you", "have you")) or
                text.lower().startswith(("qué", "cómo", "cuándo", "dónde", "tiene", "siente")) or  # Spanish
                "吗" in text  # Mandarin question particle
            )
            
            # Check for medical instruction patterns
            is_instruction = any(word in text.lower() for word in [
                "take", "prescribe", "recommend", "need to", "should",
                "tome", "receta", "debe",  # Spanish
                "服用", "建议"  # Mandarin
            ])
            
            if is_question or is_instruction:
                segment.speaker = SpeakerRole.PHYSICIAN
                current_speaker = SpeakerRole.PHYSICIAN
            elif current_speaker == SpeakerRole.PHYSICIAN:
                # After physician → patient response
                segment.speaker = SpeakerRole.PATIENT
                current_speaker = SpeakerRole.PATIENT
            elif current_speaker == SpeakerRole.PATIENT:
                # After patient → physician follow-up
                segment.speaker = SpeakerRole.PHYSICIAN
                current_speaker = SpeakerRole.PHYSICIAN
            else:
                # First segment - assume patient describing symptoms
                if i == 0:
                    segment.speaker = SpeakerRole.PATIENT
                    current_speaker = SpeakerRole.PATIENT
                else:
                    segment.speaker = SpeakerRole.UNKNOWN
        
        return segments
    
    def _flag_medical_terms(self, text: str, language: Language) -> List[str]:
        """
        Flag medical terms found in transcript.
        
        Useful for quality review and medical coding.
        """
        flagged = []
        
        medical_dict = self.medical_dicts.get(language, [])
        text_lower = text.lower()
        
        for term in medical_dict:
            if term.lower() in text_lower:
                flagged.append(term)
        
        return flagged
    
    def _load_medical_dictionaries(self) -> Dict[Language, List[str]]:
        """
        Load medical term dictionaries per language.
        
        In production: Load from config/languages/medical_dictionaries/
        """
        return {
            Language.SPANISH_MX: [
                "diabetes", "hipertensión", "dolor", "fiebre",
                "náusea", "mareo", "tos", "asma", "artritis",
                "infarto", "colesterol", "insulina", "presión arterial",
                "dolor de pecho", "dolor de cabeza", "dolor de estómago"
            ],
            Language.SPANISH_US: [
                "diabetes", "hipertensión", "dolor", "fiebre",
                "náusea", "mareo", "tos", "asma", "artritis"
            ],
            Language.MANDARIN: [
                "糖尿病", "高血压", "疼痛", "发烧",
                "恶心", "头晕", "咳嗽", "哮喘",
                "心脏病", "胆固醇", "胰岛素", "血压",
                "胸痛", "头痛", "胃痛"
            ],
            Language.ENGLISH: [
                "diabetes", "hypertension", "pain", "fever",
                "nausea", "dizziness", "cough", "asthma", "arthritis",
                "heart attack", "cholesterol", "insulin", "blood pressure",
                "chest pain", "headache", "stomach pain"
            ]
        }
    
    def get_supported_languages(self) -> List[Language]:
        """Get list of supported transcription languages."""
        return list(self.WHISPER_LANG_MAP.keys())
