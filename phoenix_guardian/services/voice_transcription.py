"""
Multi-Provider Voice Transcription Service.

Supports multiple ASR (Automatic Speech Recognition) backends:
- OpenAI Whisper (local or API)
- Google Cloud Speech-to-Text
- Azure Cognitive Services Speech
- Web Speech API (browser-side, existing)

The service provides:
1. Provider-agnostic audio transcription
2. Medical terminology verification post-transcription
3. Quality scoring per segment
4. Speaker diarization hints
5. HIPAA-compliant audit logging

Architecture:
    Audio → [Provider Selection] → [ASR] → [Medical Term Enrichment] → Result
                                                    ↓
                                         [Quality Scoring & Verification]

Sprint 4, Days 7-8: Voice Pipeline & Medical Term Verification
"""

import asyncio
import io
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════


class ASRProvider(str, Enum):
    """Supported ASR providers."""
    WHISPER_LOCAL = "whisper_local"
    WHISPER_API = "whisper_api"
    GOOGLE = "google"
    AZURE = "azure"
    WEB_SPEECH = "web_speech"  # Browser-side (existing)


@dataclass
class ASRConfig:
    """Configuration for an ASR provider."""
    provider: ASRProvider
    model: str = "base"
    language: str = "en"
    sample_rate: int = 16000
    # Provider-specific
    api_key: Optional[str] = None
    region: Optional[str] = None
    endpoint: Optional[str] = None
    # Quality
    enable_punctuation: bool = True
    enable_speaker_diarization: bool = False
    max_speakers: int = 2
    # Medical
    medical_vocabulary_boost: bool = True
    custom_vocabulary: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TranscriptWord:
    """A single word with timing and confidence."""
    word: str
    start_time: float  # seconds
    end_time: float    # seconds
    confidence: float  # 0-1
    speaker: Optional[str] = None
    is_medical_term: bool = False


@dataclass
class TranscriptSegment:
    """A segment of transcription (usually a sentence or phrase)."""
    text: str
    start_time: float
    end_time: float
    confidence: float
    speaker: Optional[str] = None
    language: str = "en"
    words: List[TranscriptWord] = field(default_factory=list)
    medical_terms: List[str] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    """Complete transcription result from any provider."""
    id: str
    transcript: str
    segments: List[TranscriptSegment]
    provider: str
    model: str
    language: str
    duration_seconds: float
    processing_time_ms: float
    quality_score: float  # 0-100
    medical_terms_found: List[Dict[str, Any]]
    medical_terms_verified: List[Dict[str, Any]]
    word_count: int
    confidence_avg: float
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# MEDICAL VOCABULARY
# ═══════════════════════════════════════════════════════════════════════════════

# High-priority medical terms for ASR vocabulary boosting
MEDICAL_VOCABULARY = [
    # Vital signs
    "systolic", "diastolic", "tachycardia", "bradycardia", "hypertension",
    "hypotension", "tachypnea", "bradypnea", "hypothermia", "hyperthermia",
    # Common conditions
    "diabetes", "mellitus", "hypertension", "hyperlipidemia", "COPD",
    "pneumonia", "myocardial", "infarction", "cerebrovascular", "accident",
    "pulmonary", "embolism", "deep vein thrombosis", "atrial fibrillation",
    # Medications
    "metformin", "lisinopril", "atorvastatin", "amlodipine", "metoprolol",
    "omeprazole", "levothyroxine", "amoxicillin", "prednisone", "warfarin",
    "heparin", "insulin", "albuterol", "acetaminophen", "ibuprofen",
    # Procedures
    "echocardiogram", "electrocardiogram", "colonoscopy", "endoscopy",
    "bronchoscopy", "angiography", "arthroplasty", "cholecystectomy",
    "appendectomy", "laparoscopy", "thoracentesis", "paracentesis",
    # Lab terms
    "hemoglobin", "hematocrit", "creatinine", "troponin", "d-dimer",
    "procalcitonin", "BNP", "HbA1c", "TSH", "INR", "PTT", "CBC",
    "BMP", "CMP", "urinalysis", "lipase", "amylase", "bilirubin",
    # Anatomical
    "bilateral", "anterior", "posterior", "lateral", "medial",
    "proximal", "distal", "superficial", "subcutaneous", "intramuscular",
]


# ═══════════════════════════════════════════════════════════════════════════════
# PROVIDER IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class WhisperLocalProvider:
    """Local OpenAI Whisper model for transcription.
    
    Runs Whisper locally for maximum privacy (no data leaves the server).
    Requires: pip install openai-whisper
    
    Models:
    - tiny:   ~39M params, ~1GB VRAM,  fastest
    - base:   ~74M params, ~1GB VRAM,  good balance
    - small:  ~244M params, ~2GB VRAM, better quality
    - medium: ~769M params, ~5GB VRAM, high quality
    - large:  ~1.5B params, ~10GB VRAM, best quality
    """
    
    def __init__(self, config: ASRConfig):
        self.config = config
        self._model = None
    
    def _load_model(self):
        """Lazy-load the Whisper model."""
        if self._model is None:
            try:
                import whisper
                self._model = whisper.load_model(self.config.model)
                logger.info(f"Whisper model '{self.config.model}' loaded")
            except ImportError:
                raise RuntimeError(
                    "openai-whisper not installed. "
                    "Install with: pip install openai-whisper"
                )
    
    async def transcribe(self, audio_data: bytes) -> TranscriptionResult:
        """Transcribe audio using local Whisper model."""
        start = time.time()
        self._load_model()
        
        import tempfile
        result_id = str(uuid.uuid4())
        
        # Write audio to temp file (Whisper needs file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        try:
            import whisper
            
            # Run transcription
            result = whisper.transcribe(
                self._model,
                temp_path,
                language=self.config.language if self.config.language != "auto" else None,
                word_timestamps=True,
            )
            
            # Build segments
            segments = []
            all_words = []
            for seg in result.get("segments", []):
                words = []
                for w in seg.get("words", []):
                    word = TranscriptWord(
                        word=w["word"].strip(),
                        start_time=w["start"],
                        end_time=w["end"],
                        confidence=w.get("probability", 0.9),
                    )
                    words.append(word)
                    all_words.append(word)
                
                segments.append(TranscriptSegment(
                    text=seg["text"].strip(),
                    start_time=seg["start"],
                    end_time=seg["end"],
                    confidence=seg.get("avg_logprob", -0.3) + 1.0,  # Normalize
                    words=words,
                    language=result.get("language", self.config.language),
                ))
            
            elapsed = (time.time() - start) * 1000
            transcript = result.get("text", "").strip()
            
            return self._build_result(
                result_id=result_id,
                transcript=transcript,
                segments=segments,
                words=all_words,
                elapsed_ms=elapsed,
                provider="whisper_local",
                model=self.config.model,
                language=result.get("language", self.config.language),
            )
        finally:
            os.unlink(temp_path)


class WhisperAPIProvider:
    """OpenAI Whisper API provider.
    
    Uses OpenAI's hosted Whisper API for transcription.
    Requires: OPENAI_API_KEY environment variable.
    """
    
    def __init__(self, config: ASRConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("OPENAI_API_KEY")
    
    async def transcribe(self, audio_data: bytes) -> TranscriptionResult:
        """Transcribe audio using OpenAI Whisper API."""
        start = time.time()
        result_id = str(uuid.uuid4())
        
        try:
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": ("audio.wav", audio_data, "audio/wav")},
                    data={
                        "model": "whisper-1",
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": "word",
                        "language": self.config.language if self.config.language != "auto" else "",
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
                result = response.json()
            
            # Build segments from API response
            segments = []
            all_words = []
            for seg in result.get("segments", []):
                words = []
                for w in seg.get("words", []):
                    word = TranscriptWord(
                        word=w["word"].strip(),
                        start_time=w.get("start", 0),
                        end_time=w.get("end", 0),
                        confidence=0.95,  # API doesn't return per-word confidence
                    )
                    words.append(word)
                    all_words.append(word)
                
                segments.append(TranscriptSegment(
                    text=seg.get("text", "").strip(),
                    start_time=seg.get("start", 0),
                    end_time=seg.get("end", 0),
                    confidence=0.95,
                    words=words,
                    language=result.get("language", self.config.language),
                ))
            
            elapsed = (time.time() - start) * 1000
            
            return self._build_result(
                result_id=result_id,
                transcript=result.get("text", ""),
                segments=segments,
                words=all_words,
                elapsed_ms=elapsed,
                provider="whisper_api",
                model="whisper-1",
                language=result.get("language", self.config.language),
            )
        except ImportError:
            raise RuntimeError("httpx not installed. Install with: pip install httpx")
        except Exception as e:
            raise RuntimeError(f"Whisper API transcription failed: {e}")


class GoogleSpeechProvider:
    """Google Cloud Speech-to-Text provider.
    
    Requires: google-cloud-speech package and credentials.
    Best for: Real-time streaming, medical vocabulary support.
    """
    
    def __init__(self, config: ASRConfig):
        self.config = config
    
    async def transcribe(self, audio_data: bytes) -> TranscriptionResult:
        """Transcribe audio using Google Cloud Speech-to-Text."""
        start = time.time()
        result_id = str(uuid.uuid4())
        
        try:
            from google.cloud import speech_v1
            
            client = speech_v1.SpeechAsyncClient()
            
            # Configure recognition
            recognition_config = speech_v1.RecognitionConfig(
                encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.config.sample_rate,
                language_code=self.config.language,
                enable_automatic_punctuation=self.config.enable_punctuation,
                enable_word_time_offsets=True,
                enable_word_confidence=True,
                model="medical_dictation" if self.config.medical_vocabulary_boost else "default",
                use_enhanced=True,
            )
            
            # Add medical vocabulary boost
            if self.config.medical_vocabulary_boost:
                speech_context = speech_v1.SpeechContext(
                    phrases=MEDICAL_VOCABULARY[:500],  # Max 500 phrases
                    boost=15.0,  # Strong boost for medical terms
                )
                recognition_config.speech_contexts = [speech_context]
            
            audio = speech_v1.RecognitionAudio(content=audio_data)
            
            response = await client.recognize(
                config=recognition_config,
                audio=audio,
            )
            
            segments = []
            all_words = []
            full_text = ""
            
            for result in response.results:
                alt = result.alternatives[0]
                full_text += alt.transcript + " "
                
                words = []
                for w in alt.words:
                    word = TranscriptWord(
                        word=w.word,
                        start_time=w.start_time.total_seconds(),
                        end_time=w.end_time.total_seconds(),
                        confidence=w.confidence,
                        speaker=f"speaker_{w.speaker_tag}" if w.speaker_tag else None,
                    )
                    words.append(word)
                    all_words.append(word)
                
                start_t = words[0].start_time if words else 0
                end_t = words[-1].end_time if words else 0
                
                segments.append(TranscriptSegment(
                    text=alt.transcript,
                    start_time=start_t,
                    end_time=end_t,
                    confidence=alt.confidence,
                    words=words,
                    language=self.config.language,
                ))
            
            elapsed = (time.time() - start) * 1000
            
            return self._build_result(
                result_id=result_id,
                transcript=full_text.strip(),
                segments=segments,
                words=all_words,
                elapsed_ms=elapsed,
                provider="google",
                model="medical_dictation",
                language=self.config.language,
            )
        except ImportError:
            raise RuntimeError(
                "google-cloud-speech not installed. "
                "Install with: pip install google-cloud-speech"
            )


class AzureSpeechProvider:
    """Azure Cognitive Services Speech provider.
    
    Requires: azure-cognitiveservices-speech package.
    Best for: HIPAA compliance, medical terminology, custom models.
    """
    
    def __init__(self, config: ASRConfig):
        self.config = config
        self.api_key = config.api_key or os.getenv("AZURE_SPEECH_KEY")
        self.region = config.region or os.getenv("AZURE_SPEECH_REGION", "eastus")
    
    async def transcribe(self, audio_data: bytes) -> TranscriptionResult:
        """Transcribe audio using Azure Speech Services."""
        start = time.time()
        result_id = str(uuid.uuid4())
        
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            speech_config = speechsdk.SpeechConfig(
                subscription=self.api_key,
                region=self.region,
            )
            speech_config.speech_recognition_language = self.config.language
            speech_config.request_word_level_timestamps()
            
            # Enable detailed output
            speech_config.output_format = speechsdk.OutputFormat.Detailed
            
            # Medical phrase list
            if self.config.medical_vocabulary_boost:
                phrase_list = speechsdk.PhraseListGrammar.from_recognizer(None)
                for term in MEDICAL_VOCABULARY[:1000]:
                    phrase_list.addPhrase(term)
            
            # Use push stream for in-memory audio
            stream = speechsdk.audio.PushAudioInputStream()
            stream.write(audio_data)
            stream.close()
            
            audio_config = speechsdk.audio.AudioConfig(stream=stream)
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config,
            )
            
            # Collect results
            all_results = []
            done = asyncio.Event()
            
            def on_recognized(evt):
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    all_results.append(evt.result)
            
            def on_session_stopped(evt):
                done.set()
            
            recognizer.recognized.connect(on_recognized)
            recognizer.session_stopped.connect(on_session_stopped)
            
            recognizer.start_continuous_recognition()
            await done.wait()
            recognizer.stop_continuous_recognition()
            
            # Build segments
            segments = []
            all_words = []
            full_text = ""
            
            for result in all_results:
                full_text += result.text + " "
                segments.append(TranscriptSegment(
                    text=result.text,
                    start_time=result.offset / 10_000_000,  # ticks to seconds
                    end_time=(result.offset + result.duration) / 10_000_000,
                    confidence=0.9,
                    language=self.config.language,
                ))
            
            elapsed = (time.time() - start) * 1000
            
            return self._build_result(
                result_id=result_id,
                transcript=full_text.strip(),
                segments=segments,
                words=all_words,
                elapsed_ms=elapsed,
                provider="azure",
                model="speech-to-text",
                language=self.config.language,
            )
        except ImportError:
            raise RuntimeError(
                "azure-cognitiveservices-speech not installed. "
                "Install with: pip install azure-cognitiveservices-speech"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SERVICE
# ═══════════════════════════════════════════════════════════════════════════════


class MultiProviderTranscriptionService:
    """
    Multi-provider voice transcription service with medical enrichment.
    
    Selects the best available ASR provider and enriches results with
    medical terminology detection, verification, and quality scoring.
    
    Provider Selection Priority:
    1. Explicit provider from config
    2. Local Whisper (if installed) — maximum privacy
    3. Whisper API (if OPENAI_API_KEY set)
    4. Google Speech (if google-cloud-speech installed)
    5. Azure Speech (if azure-cognitiveservices-speech installed)
    
    Usage:
        service = MultiProviderTranscriptionService()
        result = await service.transcribe(audio_bytes, config)
    """
    
    def __init__(self):
        self._providers: Dict[ASRProvider, Any] = {}
        self._audit_log: List[Dict[str, Any]] = []
    
    def _get_provider(self, config: ASRConfig):
        """Get or create the appropriate provider."""
        provider = config.provider
        
        if provider == ASRProvider.WHISPER_LOCAL:
            return WhisperLocalProvider(config)
        elif provider == ASRProvider.WHISPER_API:
            return WhisperAPIProvider(config)
        elif provider == ASRProvider.GOOGLE:
            return GoogleSpeechProvider(config)
        elif provider == ASRProvider.AZURE:
            return AzureSpeechProvider(config)
        else:
            # Auto-select best available
            return self._auto_select_provider(config)
    
    def _auto_select_provider(self, config: ASRConfig):
        """Auto-select the best available provider."""
        # Try local Whisper first (best privacy)
        try:
            import whisper
            logger.info("Auto-selected: Whisper Local")
            return WhisperLocalProvider(config)
        except ImportError:
            pass
        
        # Try Whisper API
        if os.getenv("OPENAI_API_KEY"):
            logger.info("Auto-selected: Whisper API")
            return WhisperAPIProvider(config)
        
        # Try Google
        try:
            from google.cloud import speech_v1
            logger.info("Auto-selected: Google Speech")
            return GoogleSpeechProvider(config)
        except ImportError:
            pass
        
        # Try Azure
        if os.getenv("AZURE_SPEECH_KEY"):
            logger.info("Auto-selected: Azure Speech")
            return AzureSpeechProvider(config)
        
        raise RuntimeError(
            "No ASR provider available. Install one of: "
            "openai-whisper, google-cloud-speech, azure-cognitiveservices-speech, "
            "or set OPENAI_API_KEY for Whisper API"
        )
    
    async def transcribe(
        self,
        audio_data: bytes,
        config: Optional[ASRConfig] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio using the configured provider.
        
        Args:
            audio_data: Raw audio bytes (WAV, WebM, MP3, FLAC supported)
            config: ASR configuration. If None, auto-selects provider.
        
        Returns:
            TranscriptionResult with transcript, segments, medical terms,
            and quality metrics.
        """
        if config is None:
            config = ASRConfig(provider=ASRProvider.WHISPER_LOCAL)
        
        provider = self._get_provider(config)
        
        # Transcribe
        result = await provider.transcribe(audio_data)
        
        # Enrich with medical terminology
        result = self._enrich_medical_terms(result)
        
        # Compute quality score
        result.quality_score = self._compute_quality_score(result)
        
        # Audit log
        self._audit(result, config)
        
        return result
    
    def _enrich_medical_terms(self, result: TranscriptionResult) -> TranscriptionResult:
        """Enrich transcription with medical terminology detection."""
        try:
            from phoenix_guardian.services.medical_terminology import (
                find_medical_terms,
                verify_terms,
            )
            
            # Find medical terms in the full transcript
            found_terms = find_medical_terms(result.transcript)
            result.medical_terms_found = [
                {
                    "term": t.term,
                    "category": t.category,
                    "start": t.start,
                    "end": t.end,
                    "confidence": t.confidence,
                }
                for t in found_terms
            ]
            
            # Verify found terms
            term_strings = [t.term for t in found_terms]
            if term_strings:
                verified = verify_terms(term_strings)
                result.medical_terms_verified = [
                    {
                        "term": v.term,
                        "verified": v.verified,
                        "category": v.category,
                        "confidence": v.confidence,
                    }
                    for v in verified
                ]
            
            # Mark medical terms in segments
            for segment in result.segments:
                segment_terms = find_medical_terms(segment.text)
                segment.medical_terms = [t.term for t in segment_terms]
                
                # Mark words
                for word in segment.words:
                    word_lower = word.word.lower().strip(".,;:!?")
                    word.is_medical_term = any(
                        word_lower in t.term.lower() for t in segment_terms
                    )
        except ImportError:
            logger.warning("Medical terminology service not available")
        except Exception as e:
            logger.error(f"Medical term enrichment failed: {e}")
        
        return result
    
    def _compute_quality_score(self, result: TranscriptionResult) -> float:
        """Compute overall transcription quality score (0-100)."""
        if not result.segments:
            return 0.0
        
        scores = []
        
        # 1. Average confidence (40% weight)
        avg_conf = sum(s.confidence for s in result.segments) / len(result.segments)
        conf_score = min(avg_conf * 100, 100)
        scores.append(conf_score * 0.4)
        
        # 2. Medical term coverage (30% weight)
        word_count = len(result.transcript.split())
        if word_count > 0:
            term_density = len(result.medical_terms_found) / max(word_count / 10, 1)
            term_score = min(term_density * 50, 100)
        else:
            term_score = 0
        scores.append(term_score * 0.3)
        
        # 3. Completeness (30% weight)
        # Check for reasonable length and structure
        has_words = word_count >= 10
        has_segments = len(result.segments) >= 1
        has_timing = any(s.end_time > 0 for s in result.segments)
        completeness = sum([has_words, has_segments, has_timing]) / 3 * 100
        scores.append(completeness * 0.3)
        
        return round(sum(scores), 1)
    
    def _audit(self, result: TranscriptionResult, config: ASRConfig) -> None:
        """Log transcription for HIPAA audit trail."""
        self._audit_log.append({
            "id": result.id,
            "provider": result.provider,
            "language": result.language,
            "duration_seconds": result.duration_seconds,
            "processing_time_ms": result.processing_time_ms,
            "quality_score": result.quality_score,
            "word_count": result.word_count,
            "medical_terms_count": len(result.medical_terms_found),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    
    def get_available_providers(self) -> List[Dict[str, Any]]:
        """List available ASR providers and their status."""
        providers = []
        
        # Whisper Local
        try:
            import whisper
            providers.append({
                "provider": ASRProvider.WHISPER_LOCAL,
                "available": True,
                "description": "OpenAI Whisper (local, maximum privacy)",
            })
        except ImportError:
            providers.append({
                "provider": ASRProvider.WHISPER_LOCAL,
                "available": False,
                "description": "Install: pip install openai-whisper",
            })
        
        # Whisper API
        providers.append({
            "provider": ASRProvider.WHISPER_API,
            "available": bool(os.getenv("OPENAI_API_KEY")),
            "description": "OpenAI Whisper API (cloud)",
        })
        
        # Google
        try:
            from google.cloud import speech_v1
            providers.append({
                "provider": ASRProvider.GOOGLE,
                "available": True,
                "description": "Google Cloud Speech-to-Text",
            })
        except ImportError:
            providers.append({
                "provider": ASRProvider.GOOGLE,
                "available": False,
                "description": "Install: pip install google-cloud-speech",
            })
        
        # Azure
        providers.append({
            "provider": ASRProvider.AZURE,
            "available": bool(os.getenv("AZURE_SPEECH_KEY")),
            "description": "Azure Cognitive Services Speech",
        })
        
        # Web Speech (always available via browser)
        providers.append({
            "provider": ASRProvider.WEB_SPEECH,
            "available": True,
            "description": "Browser Web Speech API (client-side only)",
        })
        
        return providers
    
    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Get audit log for HIPAA compliance."""
        return list(self._audit_log)


# Helper methods shared across providers
def _build_result(
    result_id: str,
    transcript: str,
    segments: List[TranscriptSegment],
    words: List[TranscriptWord],
    elapsed_ms: float,
    provider: str,
    model: str,
    language: str,
) -> TranscriptionResult:
    """Build a standardized TranscriptionResult."""
    duration = max(
        (s.end_time for s in segments),
        default=0.0,
    )
    avg_confidence = (
        sum(s.confidence for s in segments) / len(segments)
        if segments else 0.0
    )
    
    return TranscriptionResult(
        id=result_id,
        transcript=transcript,
        segments=segments,
        provider=provider,
        model=model,
        language=language,
        duration_seconds=duration,
        processing_time_ms=round(elapsed_ms, 2),
        quality_score=0.0,  # Computed after enrichment
        medical_terms_found=[],
        medical_terms_verified=[],
        word_count=len(transcript.split()),
        confidence_avg=round(avg_confidence, 3),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# Patch _build_result onto providers
for _cls in (WhisperLocalProvider, WhisperAPIProvider, GoogleSpeechProvider, AzureSpeechProvider):
    _cls._build_result = staticmethod(_build_result)
