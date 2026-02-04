"""
Phoenix Guardian - Encounter Metrics
Complete metrics for a single physician-patient encounter.

This is our PRIMARY validation instrument for Phase 3 pilot deployments.
Every metric captured here gets compared to Phase 2 benchmarks.

Phase 2 Promises (from UIP17 submission):
- Time saved: 12.3 minutes per patient encounter
- Physician satisfaction: 4.3/5.0
- Attack detection rate: 97.4%
- P95 API latency: <200ms
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import hashlib
import json
import uuid


# ==============================================================================
# Enumerations
# ==============================================================================

class EncounterPhase(Enum):
    """Phases of a physician encounter with Phoenix Guardian."""
    STARTED = "started"                      # Encounter opened
    RECORDING = "recording"                  # Audio/input being captured
    AI_PROCESSING = "ai_processing"          # Scribe generating SOAP
    DRAFT_READY = "draft_ready"              # SOAP note ready for review
    PHYSICIAN_REVIEW = "physician_review"    # Physician editing
    APPROVED = "approved"                    # Physician approved note
    EHR_WRITING = "ehr_writing"              # Writing to EHR
    COMPLETED = "completed"                  # Successfully saved to EHR
    FAILED = "failed"                        # Error occurred
    ABANDONED = "abandoned"                  # Physician abandoned encounter


class AgentType(Enum):
    """Types of Phoenix Guardian agents."""
    SCRIBE = "scribe"                        # SOAP note generation
    NAVIGATOR = "navigator"                  # ICD-10/CPT coding
    PRIOR_AUTH = "prior_auth"                # Prior authorization
    SAFETY = "safety"                        # Drug interaction checks
    SENTINELQ = "sentinelq"                  # Security monitoring
    DECEPTION = "deception"                  # Honeytoken deployment


class SOAPSection(Enum):
    """SOAP note sections."""
    SUBJECTIVE = "subjective"
    OBJECTIVE = "objective"
    ASSESSMENT = "assessment"
    PLAN = "plan"


class SecurityEventType(Enum):
    """Types of security events."""
    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK_ATTEMPT = "jailbreak_attempt"
    DATA_EXFILTRATION = "data_exfiltration"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    HONEYTOKEN_ACCESS = "honeytoken_access"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    SUSPICIOUS_QUERY = "suspicious_query"


# ==============================================================================
# Supporting Data Classes
# ==============================================================================

@dataclass
class TimingBreakdown:
    """
    Detailed timing breakdown for an encounter.
    
    Used to calculate time saved vs traditional documentation.
    Traditional baseline: 25 minutes per encounter.
    """
    encounter_opened: Optional[datetime] = None
    recording_started: Optional[datetime] = None
    recording_ended: Optional[datetime] = None
    ai_processing_started: Optional[datetime] = None
    ai_draft_completed: Optional[datetime] = None
    physician_review_started: Optional[datetime] = None
    physician_review_ended: Optional[datetime] = None
    ehr_write_started: Optional[datetime] = None
    ehr_write_completed: Optional[datetime] = None
    encounter_completed: Optional[datetime] = None
    
    # Traditional documentation baseline (minutes)
    TRADITIONAL_TIME_MINUTES: float = 25.0
    
    @property
    def total_time_seconds(self) -> float:
        """Total encounter time in seconds."""
        if self.encounter_completed and self.encounter_opened:
            delta = self.encounter_completed - self.encounter_opened
            return delta.total_seconds()
        return 0.0
    
    @property
    def total_time_minutes(self) -> float:
        """Total encounter time in minutes."""
        return self.total_time_seconds / 60.0
    
    @property
    def ai_processing_time_seconds(self) -> float:
        """Time spent generating AI draft."""
        if self.ai_draft_completed and self.ai_processing_started:
            delta = self.ai_draft_completed - self.ai_processing_started
            return delta.total_seconds()
        return 0.0
    
    @property
    def physician_review_time_seconds(self) -> float:
        """Time physician spent reviewing/editing."""
        if self.physician_review_ended and self.physician_review_started:
            delta = self.physician_review_ended - self.physician_review_started
            return delta.total_seconds()
        return 0.0
    
    @property
    def ehr_write_time_seconds(self) -> float:
        """Time to write to EHR."""
        if self.ehr_write_completed and self.ehr_write_started:
            delta = self.ehr_write_completed - self.ehr_write_started
            return delta.total_seconds()
        return 0.0
    
    @property
    def time_saved_minutes(self) -> float:
        """
        Time saved compared to traditional documentation.
        
        Positive value = time saved
        Negative value = took longer than traditional
        """
        return self.TRADITIONAL_TIME_MINUTES - self.total_time_minutes
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "encounter_opened": self.encounter_opened.isoformat() if self.encounter_opened else None,
            "recording_started": self.recording_started.isoformat() if self.recording_started else None,
            "recording_ended": self.recording_ended.isoformat() if self.recording_ended else None,
            "ai_processing_started": self.ai_processing_started.isoformat() if self.ai_processing_started else None,
            "ai_draft_completed": self.ai_draft_completed.isoformat() if self.ai_draft_completed else None,
            "physician_review_started": self.physician_review_started.isoformat() if self.physician_review_started else None,
            "physician_review_ended": self.physician_review_ended.isoformat() if self.physician_review_ended else None,
            "ehr_write_started": self.ehr_write_started.isoformat() if self.ehr_write_started else None,
            "ehr_write_completed": self.ehr_write_completed.isoformat() if self.ehr_write_completed else None,
            "encounter_completed": self.encounter_completed.isoformat() if self.encounter_completed else None,
            "total_time_seconds": self.total_time_seconds,
            "total_time_minutes": self.total_time_minutes,
            "ai_processing_time_seconds": self.ai_processing_time_seconds,
            "physician_review_time_seconds": self.physician_review_time_seconds,
            "ehr_write_time_seconds": self.ehr_write_time_seconds,
            "time_saved_minutes": self.time_saved_minutes,
        }


@dataclass
class AgentInvocation:
    """
    Record of a single agent invocation during an encounter.
    
    Tracks which agents were used and their performance.
    """
    agent_type: AgentType
    invoked_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = True
    latency_ms: float = 0.0
    
    # Agent-specific outputs
    output_accepted: bool = False              # Did physician accept output?
    output_modified: bool = False              # Was output modified?
    modification_percentage: float = 0.0       # How much was modified
    
    # For Scribe agent
    sections_generated: List[str] = field(default_factory=list)
    note_length_chars: int = 0
    
    # For Navigator agent
    icd_codes_suggested: int = 0
    cpt_codes_suggested: int = 0
    codes_accepted: int = 0
    codes_rejected: int = 0
    
    # For Safety agent
    drug_interactions_found: int = 0
    alerts_shown: int = 0
    alerts_acknowledged: int = 0
    
    # For SentinelQ agent
    threats_detected: int = 0
    confidence_score: float = 0.0
    
    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def __post_init__(self):
        """Calculate latency if times are available."""
        if self.completed_at and self.invoked_at:
            delta = self.completed_at - self.invoked_at
            self.latency_ms = delta.total_seconds() * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_type": self.agent_type.value,
            "invoked_at": self.invoked_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "latency_ms": self.latency_ms,
            "output_accepted": self.output_accepted,
            "output_modified": self.output_modified,
            "modification_percentage": self.modification_percentage,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
        }


@dataclass
class SecurityEvent:
    """
    Security event detected during an encounter.
    
    Captured by SentinelQ and Deception agents.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: SecurityEventType = SecurityEventType.ANOMALOUS_BEHAVIOR
    detected_at: datetime = field(default_factory=datetime.now)
    
    severity: str = "medium"                   # critical, high, medium, low
    confidence: float = 0.0                    # 0.0 to 1.0
    
    # Detection details
    detection_method: str = ""                 # ml_model, rule, honeytoken
    detection_model_version: str = ""
    raw_input: Optional[str] = None            # The input that triggered
    
    # Response actions
    blocked: bool = False
    alert_sent: bool = False
    honeytoken_deployed: bool = False
    attacker_fingerprint: Optional[str] = None
    
    # False positive tracking (CRITICAL for ML retraining)
    marked_false_positive: bool = False
    false_positive_reason: Optional[str] = None
    false_positive_by: Optional[str] = None    # physician_id who marked it
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "detected_at": self.detected_at.isoformat(),
            "severity": self.severity,
            "confidence": self.confidence,
            "detection_method": self.detection_method,
            "blocked": self.blocked,
            "alert_sent": self.alert_sent,
            "marked_false_positive": self.marked_false_positive,
            "false_positive_reason": self.false_positive_reason,
        }


@dataclass
class SOAPNoteQuality:
    """
    Quality metrics for the generated SOAP note.
    
    Tracks per-section quality and physician feedback.
    """
    # Per-section ratings (1-5)
    subjective_rating: Optional[int] = None
    objective_rating: Optional[int] = None
    assessment_rating: Optional[int] = None
    plan_rating: Optional[int] = None
    
    # Edit tracking per section
    subjective_edited: bool = False
    objective_edited: bool = False
    assessment_edited: bool = False
    plan_edited: bool = False
    
    # Character counts (original vs final)
    original_length_chars: int = 0
    final_length_chars: int = 0
    
    # Medical accuracy flags
    hallucination_detected: bool = False
    hallucination_corrected: bool = False
    missing_info_added: bool = False
    incorrect_info_removed: bool = False
    
    @property
    def average_section_rating(self) -> Optional[float]:
        """Average rating across sections."""
        ratings = [r for r in [
            self.subjective_rating,
            self.objective_rating,
            self.assessment_rating,
            self.plan_rating
        ] if r is not None]
        
        return sum(ratings) / len(ratings) if ratings else None
    
    @property
    def edit_percentage(self) -> float:
        """Percentage of note that was edited."""
        if self.original_length_chars == 0:
            return 0.0
        
        diff = abs(self.final_length_chars - self.original_length_chars)
        return min(100.0, (diff / self.original_length_chars) * 100)
    
    @property
    def sections_edited(self) -> List[str]:
        """List of sections that were edited."""
        edited = []
        if self.subjective_edited:
            edited.append("subjective")
        if self.objective_edited:
            edited.append("objective")
        if self.assessment_edited:
            edited.append("assessment")
        if self.plan_edited:
            edited.append("plan")
        return edited
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "subjective_rating": self.subjective_rating,
            "objective_rating": self.objective_rating,
            "assessment_rating": self.assessment_rating,
            "plan_rating": self.plan_rating,
            "average_section_rating": self.average_section_rating,
            "sections_edited": self.sections_edited,
            "edit_percentage": self.edit_percentage,
            "hallucination_detected": self.hallucination_detected,
        }


# ==============================================================================
# Main Encounter Metrics Class
# ==============================================================================

@dataclass
class EncounterMetrics:
    """
    Complete metrics for a single physician-patient encounter.
    
    This is our PRIMARY validation instrument for Phase 3 pilot deployments.
    Every number here gets compared to Phase 2 benchmarks.
    
    Example:
        metrics = EncounterMetrics(
            encounter_id="enc-001",
            tenant_id="pilot_hospital_001",
            physician_id="phy-hash-123",
            specialty="Cardiology"
        )
        metrics.start_encounter()
        # ... encounter progresses ...
        metrics.complete_encounter()
        
        report = metrics.generate_report()
    """
    
    # === IDENTITY ===
    encounter_id: str
    tenant_id: str
    physician_id: str                          # Anonymized hash
    specialty: str = "General"
    patient_id_hash: str = ""                  # Anonymized patient ID
    
    # === STATE ===
    phase: EncounterPhase = EncounterPhase.STARTED
    created_at: datetime = field(default_factory=datetime.now)
    
    # === TIMING ===
    timing: TimingBreakdown = field(default_factory=TimingBreakdown)
    
    # === AGENT USAGE ===
    agent_invocations: List[AgentInvocation] = field(default_factory=list)
    
    # === QUALITY METRICS ===
    note_quality: SOAPNoteQuality = field(default_factory=SOAPNoteQuality)
    physician_rating: Optional[int] = None     # 1-5 overall rating
    physician_comment: Optional[str] = None
    
    # === SECURITY EVENTS ===
    security_events: List[SecurityEvent] = field(default_factory=list)
    
    # === TECHNICAL PERFORMANCE ===
    api_latency_p50_ms: float = 0.0
    api_latency_p95_ms: float = 0.0
    api_latency_p99_ms: float = 0.0
    ml_inference_time_ms: float = 0.0
    ehr_write_latency_ms: float = 0.0
    
    # === ERROR TRACKING ===
    errors: List[Dict[str, str]] = field(default_factory=list)
    total_retry_attempts: int = 0
    
    # === METADATA ===
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # =========================================================================
    # Lifecycle Methods
    # =========================================================================
    
    def start_encounter(self) -> None:
        """Mark encounter as started."""
        self.phase = EncounterPhase.STARTED
        self.timing.encounter_opened = datetime.now()
    
    def start_recording(self) -> None:
        """Mark recording phase as started."""
        self.phase = EncounterPhase.RECORDING
        self.timing.recording_started = datetime.now()
    
    def end_recording(self) -> None:
        """Mark recording phase as ended."""
        self.timing.recording_ended = datetime.now()
        self.phase = EncounterPhase.AI_PROCESSING
        self.timing.ai_processing_started = datetime.now()
    
    def draft_ready(self) -> None:
        """Mark AI draft as ready for review."""
        self.phase = EncounterPhase.DRAFT_READY
        self.timing.ai_draft_completed = datetime.now()
    
    def start_review(self) -> None:
        """Mark physician review as started."""
        self.phase = EncounterPhase.PHYSICIAN_REVIEW
        self.timing.physician_review_started = datetime.now()
    
    def approve_note(self) -> None:
        """Mark note as approved by physician."""
        self.phase = EncounterPhase.APPROVED
        self.timing.physician_review_ended = datetime.now()
    
    def start_ehr_write(self) -> None:
        """Mark EHR write as started."""
        self.phase = EncounterPhase.EHR_WRITING
        self.timing.ehr_write_started = datetime.now()
    
    def complete_encounter(self) -> None:
        """Mark encounter as successfully completed."""
        self.phase = EncounterPhase.COMPLETED
        self.timing.ehr_write_completed = datetime.now()
        self.timing.encounter_completed = datetime.now()
    
    def fail_encounter(self, error: str) -> None:
        """Mark encounter as failed."""
        self.phase = EncounterPhase.FAILED
        self.errors.append({
            "timestamp": datetime.now().isoformat(),
            "error": error,
            "phase": self.phase.value
        })
    
    def abandon_encounter(self) -> None:
        """Mark encounter as abandoned by physician."""
        self.phase = EncounterPhase.ABANDONED
        self.timing.encounter_completed = datetime.now()
    
    # =========================================================================
    # Agent Tracking
    # =========================================================================
    
    def record_agent_invocation(self, invocation: AgentInvocation) -> None:
        """Record an agent invocation."""
        self.agent_invocations.append(invocation)
        self.total_retry_attempts += invocation.retry_count
    
    def get_agents_used(self) -> List[str]:
        """Get list of agent types used in this encounter."""
        return list(set(inv.agent_type.value for inv in self.agent_invocations))
    
    def get_agent_latencies(self) -> Dict[str, float]:
        """Get average latency per agent type."""
        latencies: Dict[str, List[float]] = {}
        
        for inv in self.agent_invocations:
            agent = inv.agent_type.value
            if agent not in latencies:
                latencies[agent] = []
            latencies[agent].append(inv.latency_ms)
        
        return {
            agent: sum(vals) / len(vals)
            for agent, vals in latencies.items()
        }
    
    # =========================================================================
    # Security Tracking
    # =========================================================================
    
    def record_security_event(self, event: SecurityEvent) -> None:
        """Record a security event."""
        self.security_events.append(event)
    
    @property
    def attack_detected(self) -> bool:
        """Whether any attack was detected."""
        return len(self.security_events) > 0
    
    @property
    def attacks_blocked(self) -> int:
        """Number of attacks that were blocked."""
        return sum(1 for e in self.security_events if e.blocked)
    
    @property
    def false_positives_marked(self) -> int:
        """Number of security events marked as false positives."""
        return sum(1 for e in self.security_events if e.marked_false_positive)
    
    # =========================================================================
    # Quality Metrics
    # =========================================================================
    
    def set_physician_rating(self, rating: int, comment: Optional[str] = None) -> None:
        """Set physician's overall rating for the encounter."""
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        self.physician_rating = rating
        self.physician_comment = comment
    
    @property
    def ai_acceptance_rate(self) -> float:
        """
        Rate at which AI-generated content was accepted without major edits.
        
        Major edit = >20% modification.
        """
        scribe_invocations = [
            inv for inv in self.agent_invocations
            if inv.agent_type == AgentType.SCRIBE
        ]
        
        if not scribe_invocations:
            return 0.0
        
        accepted = sum(
            1 for inv in scribe_invocations
            if inv.output_accepted and inv.modification_percentage < 20
        )
        
        return accepted / len(scribe_invocations)
    
    # =========================================================================
    # Benchmark Comparison
    # =========================================================================
    
    @property
    def time_saved_minutes(self) -> float:
        """Time saved compared to traditional documentation."""
        return self.timing.time_saved_minutes
    
    @property
    def meets_latency_sla(self) -> bool:
        """Whether P95 latency is under 200ms SLA."""
        return self.api_latency_p95_ms < 200.0
    
    def compare_to_benchmarks(self) -> Dict[str, Dict[str, Any]]:
        """
        Compare this encounter's metrics to Phase 2 benchmarks.
        
        Phase 2 Promises:
        - Time saved: 12.3 minutes
        - Physician satisfaction: 4.3/5.0
        - P95 latency: <200ms
        """
        benchmarks = {
            "time_saved": {
                "promise": 12.3,
                "actual": self.time_saved_minutes,
                "delta": self.time_saved_minutes - 12.3,
                "meeting": self.time_saved_minutes >= 10.0,  # 10% margin
            },
            "latency_p95": {
                "promise": 200.0,
                "actual": self.api_latency_p95_ms,
                "delta": 200.0 - self.api_latency_p95_ms,
                "meeting": self.meets_latency_sla,
            },
        }
        
        if self.physician_rating is not None:
            benchmarks["satisfaction"] = {
                "promise": 4.3,
                "actual": float(self.physician_rating),
                "delta": float(self.physician_rating) - 4.3,
                "meeting": self.physician_rating >= 4,
            }
        
        return benchmarks
    
    # =========================================================================
    # Serialization
    # =========================================================================
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize encounter metrics to dictionary."""
        return {
            "encounter_id": self.encounter_id,
            "tenant_id": self.tenant_id,
            "physician_id": self.physician_id,
            "specialty": self.specialty,
            "patient_id_hash": self.patient_id_hash,
            "phase": self.phase.value,
            "created_at": self.created_at.isoformat(),
            "timing": self.timing.to_dict(),
            "agent_invocations": [inv.to_dict() for inv in self.agent_invocations],
            "agents_used": self.get_agents_used(),
            "note_quality": self.note_quality.to_dict(),
            "physician_rating": self.physician_rating,
            "physician_comment": self.physician_comment,
            "security_events": [evt.to_dict() for evt in self.security_events],
            "attack_detected": self.attack_detected,
            "attacks_blocked": self.attacks_blocked,
            "api_latency_p50_ms": self.api_latency_p50_ms,
            "api_latency_p95_ms": self.api_latency_p95_ms,
            "api_latency_p99_ms": self.api_latency_p99_ms,
            "ml_inference_time_ms": self.ml_inference_time_ms,
            "ehr_write_latency_ms": self.ehr_write_latency_ms,
            "errors": self.errors,
            "total_retry_attempts": self.total_retry_attempts,
            "time_saved_minutes": self.time_saved_minutes,
            "ai_acceptance_rate": self.ai_acceptance_rate,
            "benchmarks": self.compare_to_benchmarks(),
            "metadata": self.metadata,
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EncounterMetrics":
        """Create EncounterMetrics from dictionary."""
        metrics = cls(
            encounter_id=data["encounter_id"],
            tenant_id=data["tenant_id"],
            physician_id=data["physician_id"],
            specialty=data.get("specialty", "General"),
            patient_id_hash=data.get("patient_id_hash", ""),
        )
        
        # Restore phase
        metrics.phase = EncounterPhase(data.get("phase", "started"))
        
        # Restore timing
        timing_data = data.get("timing", {})
        if timing_data:
            for field_name in [
                "encounter_opened", "recording_started", "recording_ended",
                "ai_processing_started", "ai_draft_completed",
                "physician_review_started", "physician_review_ended",
                "ehr_write_started", "ehr_write_completed", "encounter_completed"
            ]:
                if timing_data.get(field_name):
                    setattr(
                        metrics.timing,
                        field_name,
                        datetime.fromisoformat(timing_data[field_name])
                    )
        
        # Restore ratings
        metrics.physician_rating = data.get("physician_rating")
        metrics.physician_comment = data.get("physician_comment")
        
        # Restore performance metrics
        metrics.api_latency_p50_ms = data.get("api_latency_p50_ms", 0.0)
        metrics.api_latency_p95_ms = data.get("api_latency_p95_ms", 0.0)
        metrics.api_latency_p99_ms = data.get("api_latency_p99_ms", 0.0)
        
        return metrics
    
    def generate_fingerprint(self) -> str:
        """
        Generate a unique fingerprint for this encounter.
        
        Used for deduplication and tracking.
        """
        data = f"{self.encounter_id}:{self.tenant_id}:{self.physician_id}:{self.created_at.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def generate_report(self) -> str:
        """Generate a human-readable report for this encounter."""
        lines = [
            f"╔════════════════════════════════════════════════════════════════╗",
            f"║         ENCOUNTER METRICS REPORT - {self.encounter_id[:20]}       ║",
            f"╠════════════════════════════════════════════════════════════════╣",
            f"║ Tenant: {self.tenant_id:<20} Specialty: {self.specialty:<15} ║",
            f"║ Phase: {self.phase.value:<21} Status: {'✓ Complete' if self.phase == EncounterPhase.COMPLETED else '⏳ In Progress':<15} ║",
            f"╠════════════════════════════════════════════════════════════════╣",
            f"║ TIMING                                                          ║",
            f"║   Total Time: {self.timing.total_time_minutes:>6.1f} min   Time Saved: {self.time_saved_minutes:>6.1f} min       ║",
            f"║   AI Processing: {self.timing.ai_processing_time_seconds:>5.1f}s   Review: {self.timing.physician_review_time_seconds:>5.1f}s             ║",
            f"╠════════════════════════════════════════════════════════════════╣",
            f"║ QUALITY                                                          ║",
            f"║   Physician Rating: {self.physician_rating or 'N/A':>3}/5   AI Acceptance: {self.ai_acceptance_rate*100:>5.1f}%       ║",
            f"║   Sections Edited: {', '.join(self.note_quality.sections_edited) or 'None':<35} ║",
            f"╠════════════════════════════════════════════════════════════════╣",
            f"║ SECURITY                                                         ║",
            f"║   Events: {len(self.security_events):>3}   Blocked: {self.attacks_blocked:>3}   False Positives: {self.false_positives_marked:>3}      ║",
            f"╠════════════════════════════════════════════════════════════════╣",
            f"║ AGENTS USED: {', '.join(self.get_agents_used()) or 'None':<40}    ║",
            f"╚════════════════════════════════════════════════════════════════╝",
        ]
        
        return "\n".join(lines)
