"""Transcription Service.

Handles audio quality validation, transcript processing, medical-term
enrichment, and audit logging. Currently operates purely with text
received from the browser's Web Speech API. When an external ASR engine
(Whisper, Google, Azure) becomes available the ``transcribe_audio``
method can be extended with the relevant SDK calls.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from phoenix_guardian.services.medical_terminology import (
    VerificationResult,
    find_medical_terms,
    verify_terms,
)


# ──────────────────────────────────────────────────────────────
# Data models
# ──────────────────────────────────────────────────────────────

@dataclass
class TranscriptSegment:
    """One segment of a transcript with speaker & confidence."""
    id: str
    text: str
    start_time: float
    end_time: float
    confidence: float
    speaker: str = "unknown"
    medical_terms: List[str] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    """Full result returned to the caller."""
    id: str
    transcript: str
    segments: List[TranscriptSegment]
    medical_terms: List[Dict[str, Any]]
    verification: Optional[Dict[str, Any]]
    quality_score: float
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEntry:
    """Immutable audit record for HIPAA compliance."""
    entry_id: str
    timestamp: str
    action: str
    user_id: str
    details: Dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────
# In-memory store (swap for PostgreSQL table later)
# ──────────────────────────────────────────────────────────────

TRANSCRIPTION_DB: Dict[str, TranscriptionResult] = {}
AUDIT_LOG: List[AuditEntry] = []


def _audit(action: str, user_id: str, **details: Any) -> None:
    """Append an entry to the audit log."""
    AUDIT_LOG.append(
        AuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            user_id=user_id,
            details=details,
        )
    )


# ──────────────────────────────────────────────────────────────
# Service functions
# ──────────────────────────────────────────────────────────────

def process_transcript(
    transcript: str,
    segments: List[Dict[str, Any]],
    user_id: str = "system",
    metadata: Optional[Dict[str, Any]] = None,
) -> TranscriptionResult:
    """Process a transcript received from the frontend.

    1. Detects medical terms in the full text.
    2. Verifies the detected terms against the dictionary.
    3. Annotates each segment with its medical terms.
    4. Creates an audit entry.
    5. Stores the result.
    """
    result_id = str(uuid.uuid4())

    # 1. Detect medical terms
    matches = find_medical_terms(transcript)
    medical_terms = [
        {"term": m.term, "category": m.category, "start": m.start, "end": m.end}
        for m in matches
    ]

    # 2. Verify terms
    unique_terms = list({m.term for m in matches})
    verification: VerificationResult = verify_terms(unique_terms)
    verification_dict = {
        "verified": [
            {"term": v.term, "category": v.category}
            for v in verification.verified_terms
        ],
        "unrecognised": verification.unrecognised,
        "suggestions": verification.suggestions,
    }

    # 3. Build segment objects with per-segment medical terms
    processed_segments: List[TranscriptSegment] = []
    for raw in segments:
        seg_text = raw.get("text", "")
        seg_matches = find_medical_terms(seg_text)
        processed_segments.append(
            TranscriptSegment(
                id=raw.get("id", str(uuid.uuid4())),
                text=seg_text,
                start_time=raw.get("startTime", raw.get("start_time", 0.0)),
                end_time=raw.get("endTime", raw.get("end_time", 0.0)),
                confidence=raw.get("confidence", 0.0),
                speaker=raw.get("speaker", "unknown"),
                medical_terms=[m.term for m in seg_matches],
            )
        )

    # 4. Calculate overall quality score (average confidence)
    if processed_segments:
        quality_score = sum(s.confidence for s in processed_segments) / len(
            processed_segments
        )
    else:
        quality_score = 0.0

    # 5. Build result
    result = TranscriptionResult(
        id=result_id,
        transcript=transcript,
        segments=processed_segments,
        medical_terms=medical_terms,
        verification=verification_dict,
        quality_score=round(quality_score, 4),
        created_at=datetime.now(timezone.utc).isoformat(),
        metadata=metadata or {},
    )

    # 6. Store and audit
    TRANSCRIPTION_DB[result_id] = result
    _audit(
        action="transcript_processed",
        user_id=user_id,
        transcript_id=result_id,
        word_count=len(transcript.split()),
        segment_count=len(processed_segments),
        medical_term_count=len(medical_terms),
    )

    return result


def get_transcription(result_id: str) -> Optional[TranscriptionResult]:
    """Retrieve a stored transcription result by ID."""
    return TRANSCRIPTION_DB.get(result_id)


def list_transcriptions(limit: int = 50) -> List[Dict[str, Any]]:
    """Return recent transcription summaries."""
    items = sorted(
        TRANSCRIPTION_DB.values(), key=lambda r: r.created_at, reverse=True
    )[:limit]
    return [
        {
            "id": r.id,
            "preview": r.transcript[:120],
            "quality_score": r.quality_score,
            "segment_count": len(r.segments),
            "medical_term_count": len(r.medical_terms),
            "created_at": r.created_at,
        }
        for r in items
    ]


def result_to_dict(result: TranscriptionResult) -> Dict[str, Any]:
    """Serialise a ``TranscriptionResult`` to a plain dict."""
    d = asdict(result)
    return d
