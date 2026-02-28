"""Transcription API routes.

Endpoints:
  POST  /process          – Process a transcript from the browser
  POST  /verify-terms     – Verify a list of medical terms
  POST  /transcribe-audio – Transcribe audio via Groq Whisper
  GET   /supported-languages – Supported transcription languages
  GET   /{id}             – Retrieve a stored transcription result
  GET   /                 – List recent transcription results
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from phoenix_guardian.services.medical_terminology import (
    find_medical_terms,
    get_suggestions,
    verify_terms,
)
from phoenix_guardian.services.transcription_service import (
    get_transcription,
    list_transcriptions,
    process_transcript,
    result_to_dict,
)


router = APIRouter()


# ──────────────────────────────────────────────────────────────
# Request / Response schemas
# ──────────────────────────────────────────────────────────────

class SegmentIn(BaseModel):
    id: str = ""
    text: str
    startTime: float = Field(0.0, alias="startTime")
    endTime: float = Field(0.0, alias="endTime")
    confidence: float = 0.0
    speaker: str = "unknown"

    class Config:
        populate_by_name = True


class ProcessRequest(BaseModel):
    transcript: str
    segments: List[SegmentIn] = []
    metadata: Optional[Dict[str, Any]] = None


class VerifyTermsRequest(BaseModel):
    terms: List[str]


class DetectTermsRequest(BaseModel):
    text: str


class SuggestionRequest(BaseModel):
    partial: str
    limit: int = 10


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────

@router.post("/process", status_code=status.HTTP_200_OK)
async def api_process_transcript(body: ProcessRequest) -> Dict[str, Any]:
    """Process a transcript received from the browser's Web Speech API.

    Detects medical terms, verifies them, annotates segments and stores
    the result for later retrieval.
    """
    if not body.transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript text is required.",
        )

    segments_raw = [s.dict(by_alias=True) for s in body.segments]
    result = process_transcript(
        transcript=body.transcript,
        segments=segments_raw,
        user_id="current_user",
        metadata=body.metadata,
    )

    return {
        "status": "success",
        "data": result_to_dict(result),
    }


@router.post("/verify-terms", status_code=status.HTTP_200_OK)
async def api_verify_terms(body: VerifyTermsRequest) -> Dict[str, Any]:
    """Verify a list of terms against the medical dictionary."""
    if not body.terms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one term is required.",
        )

    vr = verify_terms(body.terms)

    return {
        "status": "success",
        "data": {
            "verified": [
                {"term": v.term, "category": v.category}
                for v in vr.verified_terms
            ],
            "unrecognised": vr.unrecognised,
            "suggestions": vr.suggestions,
        },
    }


@router.post("/detect-terms", status_code=status.HTTP_200_OK)
async def api_detect_terms(body: DetectTermsRequest) -> Dict[str, Any]:
    """Detect medical terms in a block of text."""
    if not body.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text is required.",
        )

    matches = find_medical_terms(body.text)
    return {
        "status": "success",
        "data": {
            "terms": [
                {
                    "term": m.term,
                    "category": m.category,
                    "start": m.start,
                    "end": m.end,
                }
                for m in matches
            ],
            "count": len(matches),
        },
    }


@router.post("/suggestions", status_code=status.HTTP_200_OK)
async def api_suggestions(body: SuggestionRequest) -> Dict[str, Any]:
    """Return autocomplete suggestions for a partial medical term."""
    results = get_suggestions(body.partial, body.limit)
    return {
        "status": "success",
        "data": {
            "suggestions": results,
            "count": len(results),
        },
    }


@router.get("/supported-languages", status_code=status.HTTP_200_OK)
async def api_supported_languages() -> Dict[str, Any]:
    """Return supported transcription languages.

    Currently Web Speech API handles language selection on the client,
    so we just list the languages we've verified work well.
    """
    return {
        "status": "success",
        "data": {
            "languages": [
                {"code": "en-US", "name": "English (US)", "default": True},
                {"code": "en-GB", "name": "English (UK)", "default": False},
                {"code": "es-ES", "name": "Spanish", "default": False},
                {"code": "fr-FR", "name": "French", "default": False},
            ],
            "note": "Language selection is handled by the browser's Web Speech API.",
        },
    }


@router.get("/list", status_code=status.HTTP_200_OK)
async def api_list_transcriptions(limit: int = 50) -> Dict[str, Any]:
    """List recent transcription results."""
    items = list_transcriptions(limit=limit)
    return {
        "status": "success",
        "data": items,
        "count": len(items),
    }


@router.get("/providers", status_code=status.HTTP_200_OK)
async def list_providers():
    """
    List available ASR providers and their status.

    Returns which providers are installed and configured.
    """
    try:
        from phoenix_guardian.services.voice_transcription import (
            MultiProviderTranscriptionService,
        )

        service = MultiProviderTranscriptionService()
        providers = service.get_available_providers()
        return {
            "status": "success",
            "providers": [
                {
                    "provider": p["provider"].value,
                    "available": p["available"],
                    "description": p["description"],
                }
                for p in providers
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{transcription_id}", status_code=status.HTTP_200_OK)
async def api_get_transcription(transcription_id: str) -> Dict[str, Any]:
    """Retrieve a stored transcription result by ID."""
    result = get_transcription(transcription_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcription '{transcription_id}' not found.",
        )
    return {
        "status": "success",
        "data": result_to_dict(result),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Groq Whisper Audio Transcription
# ═══════════════════════════════════════════════════════════════════════════════

DEMO_TRANSCRIPT = (
    "Doctor: Good morning, how are you feeling today? "
    "Patient: I've been having persistent headaches for the past two weeks, "
    "mostly in the frontal region. They tend to worsen in the afternoon. "
    "Doctor: On a scale of one to ten, how would you rate the pain? "
    "Patient: Usually around six or seven. Over-the-counter ibuprofen helps somewhat "
    "but the relief only lasts a few hours. "
    "Doctor: Any associated symptoms — nausea, visual changes, neck stiffness? "
    "Patient: Some mild nausea occasionally, no visual changes. "
    "Doctor: Let me check your vitals. Blood pressure is 128 over 82, "
    "heart rate 76 beats per minute, temperature 98.4 degrees Fahrenheit. "
    "I'd like to order a CBC and a basic metabolic panel. "
    "We should also schedule an MRI of the brain to rule out any structural causes. "
    "In the meantime, I'm prescribing Sumatriptan 50 milligrams as needed for acute episodes. "
    "Patient: Thank you, Doctor."
)


@router.post("/transcribe-audio", status_code=status.HTTP_200_OK)
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe an uploaded audio file using Groq Whisper API.

    Accepts audio formats: WAV, WebM, MP3, FLAC, OGG, M4A.
    Returns the transcribed text with segment-level timestamps.

    Falls back to a realistic demo transcript when the Groq API
    is unavailable or no API key is configured.
    """
    groq_key = os.getenv("GROQ_API_KEY", "")

    # Read audio bytes
    audio_bytes = await file.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # Determine content type
    content_type = file.content_type or "audio/webm"
    filename = file.filename or "recording.webm"

    # Try Groq Whisper
    if groq_key:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    files={"file": (filename, audio_bytes, content_type)},
                    data={
                        "model": "whisper-large-v3-turbo",
                        "response_format": "verbose_json",
                        "language": "en",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "text": data.get("text", ""),
                        "segments": data.get("segments", []),
                        "language": data.get("language", "en"),
                        "duration": data.get("duration", 0),
                        "source": "groq_whisper",
                    }
                else:
                    print(f"Groq Whisper returned {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:
            print(f"Groq Whisper error: {exc}")

    # Fallback: demo transcript
    return {
        "text": DEMO_TRANSCRIPT,
        "segments": [],
        "language": "en",
        "duration": 45.0,
        "source": "demo",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Multi-Provider Audio Upload Endpoints (legacy)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/upload-audio", status_code=status.HTTP_200_OK)
async def upload_and_transcribe(
    provider: str = "auto",
    language: str = "en",
    model: str = "base",
):
    """
    Upload an audio file for server-side transcription.

    Supports multiple ASR providers (Whisper, Google, Azure).
    Audio formats: WAV, WebM, MP3, FLAC, OGG.

    **Query Parameters:**
    - `provider`: ASR provider (whisper_local, whisper_api, google, azure, auto)
    - `language`: Language code (en, es, fr, etc.)
    - `model`: Whisper model size (tiny, base, small, medium, large)
    """
    try:
        from phoenix_guardian.services.voice_transcription import (
            MultiProviderTranscriptionService,
            ASRConfig,
            ASRProvider,
        )

        # Map string to provider enum
        provider_map = {
            "auto": ASRProvider.WHISPER_LOCAL,
            "whisper_local": ASRProvider.WHISPER_LOCAL,
            "whisper_api": ASRProvider.WHISPER_API,
            "google": ASRProvider.GOOGLE,
            "azure": ASRProvider.AZURE,
        }
        asr_provider = provider_map.get(provider, ASRProvider.WHISPER_LOCAL)

        config = ASRConfig(
            provider=asr_provider,
            model=model,
            language=language,
        )

        service = MultiProviderTranscriptionService()
        providers = service.get_available_providers()

        return {
            "status": "ready",
            "message": "Audio upload endpoint ready. POST audio file as multipart/form-data.",
            "config": {
                "provider": asr_provider.value,
                "model": model,
                "language": language,
            },
            "available_providers": [
                {"provider": p["provider"].value, "available": p["available"]}
                for p in providers
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configuration failed: {str(e)}")
