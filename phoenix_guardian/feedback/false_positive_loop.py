"""
Phoenix Guardian - False Positive Loop
Critical ML retraining pipeline for security false positives.

When SentinelQ blocks a legitimate request, physicians report it.
This module queues those reports for ML model retraining.

This is the #1 most important feedback loop for security in production.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
import uuid

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class FalsePositiveStatus(Enum):
    """Status of a false positive report in the pipeline."""
    PENDING = "pending"                      # Awaiting review
    UNDER_REVIEW = "under_review"           # Security team reviewing
    CONFIRMED = "confirmed"                 # Confirmed as false positive
    REJECTED = "rejected"                   # Was actually a true positive
    QUEUED_FOR_TRAINING = "queued"          # In ML training queue
    TRAINING = "training"                   # Currently being used in training
    DEPLOYED = "deployed"                   # Fix deployed to production
    CLOSED = "closed"                       # Resolution complete


class AttackTypeBlocked(Enum):
    """Types of attacks that SentinelQ may have blocked."""
    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK_ATTEMPT = "jailbreak_attempt"
    DATA_EXFILTRATION = "data_exfiltration"
    HALLUCINATION = "hallucination"
    OFF_TOPIC = "off_topic"
    UNSAFE_CONTENT = "unsafe_content"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"


class ReviewDecision(Enum):
    """Decision made during review."""
    APPROVE_RETRAIN = "approve_retrain"     # Add to training set
    REJECT_TRUE_POSITIVE = "reject_true_positive"  # Was correctly blocked
    NEEDS_CONTEXT = "needs_context"         # Need more info
    ESCALATE = "escalate"                   # Escalate to senior team


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class FalsePositiveReport:
    """
    A report of a security false positive.
    
    Contains all context needed to retrain the ML model.
    """
    # Identity
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    physician_id: str = ""
    encounter_id: str = ""
    
    # Classification
    status: FalsePositiveStatus = FalsePositiveStatus.PENDING
    attack_type_blocked: AttackTypeBlocked = AttackTypeBlocked.UNKNOWN
    confidence_when_blocked: float = 0.0     # Model's confidence when it blocked
    
    # Timing
    blocked_at: datetime = field(default_factory=datetime.now)
    reported_at: datetime = field(default_factory=datetime.now)
    reviewed_at: Optional[datetime] = None
    deployed_at: Optional[datetime] = None
    
    # Content (PHI-safe samples)
    input_text: str = ""                     # What was blocked (sanitized)
    expected_output: str = ""                # What physician expected
    block_reason: str = ""                   # Why model blocked it
    model_version: str = ""                  # Model version that blocked
    
    # Physician context
    specialty: str = ""
    clinical_context: str = ""               # What they were doing
    urgency: str = "normal"                  # low, normal, high, urgent
    
    # Review
    reviewer_id: str = ""
    review_decision: Optional[ReviewDecision] = None
    review_notes: str = ""
    
    # Training
    training_batch_id: str = ""              # Batch used for retraining
    new_model_version: str = ""              # Model after retrain
    improvement_verified: bool = False
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    similar_report_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "report_id": self.report_id,
            "tenant_id": self.tenant_id,
            "physician_id": self.physician_id,
            "encounter_id": self.encounter_id,
            "status": self.status.value,
            "attack_type_blocked": self.attack_type_blocked.value,
            "confidence_when_blocked": self.confidence_when_blocked,
            "blocked_at": self.blocked_at.isoformat(),
            "reported_at": self.reported_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "input_text": self.input_text,
            "expected_output": self.expected_output,
            "block_reason": self.block_reason,
            "model_version": self.model_version,
            "specialty": self.specialty,
            "clinical_context": self.clinical_context,
            "urgency": self.urgency,
            "reviewer_id": self.reviewer_id,
            "review_decision": self.review_decision.value if self.review_decision else None,
            "review_notes": self.review_notes,
            "training_batch_id": self.training_batch_id,
            "new_model_version": self.new_model_version,
            "improvement_verified": self.improvement_verified,
            "tags": self.tags,
            "similar_report_ids": self.similar_report_ids,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FalsePositiveReport":
        """Create from dictionary."""
        return cls(
            report_id=data.get("report_id", str(uuid.uuid4())),
            tenant_id=data.get("tenant_id", ""),
            physician_id=data.get("physician_id", ""),
            encounter_id=data.get("encounter_id", ""),
            status=FalsePositiveStatus(data.get("status", "pending")),
            attack_type_blocked=AttackTypeBlocked(data.get("attack_type_blocked", "unknown")),
            confidence_when_blocked=data.get("confidence_when_blocked", 0.0),
            blocked_at=datetime.fromisoformat(data["blocked_at"]) if "blocked_at" in data else datetime.now(),
            reported_at=datetime.fromisoformat(data["reported_at"]) if "reported_at" in data else datetime.now(),
            reviewed_at=datetime.fromisoformat(data["reviewed_at"]) if data.get("reviewed_at") else None,
            deployed_at=datetime.fromisoformat(data["deployed_at"]) if data.get("deployed_at") else None,
            input_text=data.get("input_text", ""),
            expected_output=data.get("expected_output", ""),
            block_reason=data.get("block_reason", ""),
            model_version=data.get("model_version", ""),
            specialty=data.get("specialty", ""),
            clinical_context=data.get("clinical_context", ""),
            urgency=data.get("urgency", "normal"),
            reviewer_id=data.get("reviewer_id", ""),
            review_decision=ReviewDecision(data["review_decision"]) if data.get("review_decision") else None,
            review_notes=data.get("review_notes", ""),
            training_batch_id=data.get("training_batch_id", ""),
            new_model_version=data.get("new_model_version", ""),
            improvement_verified=data.get("improvement_verified", False),
            tags=data.get("tags", []),
            similar_report_ids=data.get("similar_report_ids", []),
        )
    
    def to_training_sample(self) -> Dict[str, Any]:
        """
        Convert to training sample format.
        
        This is the format consumed by the ML training pipeline.
        """
        return {
            "input": self.input_text,
            "expected_output": self.expected_output,
            "label": "safe",                 # Marked as safe since it was FP
            "attack_type": self.attack_type_blocked.value,
            "original_confidence": self.confidence_when_blocked,
            "specialty": self.specialty,
            "context": self.clinical_context,
            "report_id": self.report_id,
        }
    
    def is_pending(self) -> bool:
        """Check if report is awaiting review."""
        return self.status in [FalsePositiveStatus.PENDING, FalsePositiveStatus.UNDER_REVIEW]
    
    def is_confirmed(self) -> bool:
        """Check if report is confirmed as false positive."""
        return self.status in [
            FalsePositiveStatus.CONFIRMED,
            FalsePositiveStatus.QUEUED_FOR_TRAINING,
            FalsePositiveStatus.TRAINING,
            FalsePositiveStatus.DEPLOYED,
        ]


@dataclass
class TrainingBatch:
    """
    A batch of false positive samples for ML retraining.
    """
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    
    report_ids: List[str] = field(default_factory=list)
    sample_count: int = 0
    
    # Training metadata
    model_version_before: str = ""
    model_version_after: str = ""
    training_started_at: Optional[datetime] = None
    training_completed_at: Optional[datetime] = None
    
    # Metrics
    accuracy_before: float = 0.0
    accuracy_after: float = 0.0
    false_positive_rate_before: float = 0.0
    false_positive_rate_after: float = 0.0
    
    # Status
    is_deployed: bool = False
    deployed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "batch_id": self.batch_id,
            "created_at": self.created_at.isoformat(),
            "report_ids": self.report_ids,
            "sample_count": self.sample_count,
            "model_version_before": self.model_version_before,
            "model_version_after": self.model_version_after,
            "training_started_at": self.training_started_at.isoformat() if self.training_started_at else None,
            "training_completed_at": self.training_completed_at.isoformat() if self.training_completed_at else None,
            "accuracy_before": self.accuracy_before,
            "accuracy_after": self.accuracy_after,
            "false_positive_rate_before": self.false_positive_rate_before,
            "false_positive_rate_after": self.false_positive_rate_after,
            "is_deployed": self.is_deployed,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
        }


# ==============================================================================
# False Positive Queue
# ==============================================================================

class FalsePositiveQueue:
    """
    Queue for managing false positive reports awaiting review.
    
    Implements priority-based queuing with SLA tracking.
    """
    
    def __init__(self):
        self._pending: List[FalsePositiveReport] = []
        self._under_review: Dict[str, FalsePositiveReport] = {}
        
        # SLA thresholds (hours)
        self._sla_thresholds = {
            "urgent": 4,
            "high": 24,
            "normal": 72,
            "low": 168,  # 1 week
        }
    
    def add(self, report: FalsePositiveReport) -> None:
        """Add report to queue."""
        self._pending.append(report)
        self._sort_by_priority()
    
    def _sort_by_priority(self) -> None:
        """Sort pending by urgency and age."""
        urgency_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        self._pending.sort(
            key=lambda r: (urgency_order.get(r.urgency, 2), r.reported_at)
        )
    
    def get_next(self) -> Optional[FalsePositiveReport]:
        """Get next report for review."""
        if not self._pending:
            return None
        
        report = self._pending.pop(0)
        report.status = FalsePositiveStatus.UNDER_REVIEW
        self._under_review[report.report_id] = report
        
        return report
    
    def return_to_queue(self, report_id: str) -> bool:
        """Return a report to the queue (review incomplete)."""
        if report_id in self._under_review:
            report = self._under_review.pop(report_id)
            report.status = FalsePositiveStatus.PENDING
            self._pending.append(report)
            self._sort_by_priority()
            return True
        return False
    
    def get_pending_count(self) -> int:
        """Get count of pending reports."""
        return len(self._pending)
    
    def get_under_review_count(self) -> int:
        """Get count of reports under review."""
        return len(self._under_review)
    
    def get_breaching_sla(self) -> List[FalsePositiveReport]:
        """Get reports that are breaching or about to breach SLA."""
        now = datetime.now()
        breaching = []
        
        for report in self._pending:
            threshold_hours = self._sla_thresholds.get(report.urgency, 72)
            age_hours = (now - report.reported_at).total_seconds() / 3600
            
            if age_hours >= threshold_hours * 0.8:  # 80% of SLA
                breaching.append(report)
        
        return breaching


# ==============================================================================
# False Positive Loop
# ==============================================================================

class FalsePositiveLoop:
    """
    End-to-end false positive pipeline for ML retraining.
    
    Example:
        loop = FalsePositiveLoop(
            training_trigger=lambda batch: ml_pipeline.train(batch),
            min_batch_size=10,
        )
        
        # Physician reports false positive
        report = loop.report_false_positive(
            tenant_id="pilot_hospital_001",
            physician_id="dr_smith_001",
            encounter_id="enc-123",
            input_text="Patient has history of...",
            block_reason="Possible data exfiltration",
            clinical_context="Documenting history in SOAP note"
        )
        
        # Security team reviews
        loop.review(
            report_id=report.report_id,
            reviewer_id="security_analyst_001",
            decision=ReviewDecision.APPROVE_RETRAIN,
            notes="Valid clinical content, blocked incorrectly"
        )
        
        # When batch is ready, trigger training
        batch = loop.create_training_batch()
    """
    
    def __init__(
        self,
        training_trigger: Optional[Callable[[TrainingBatch], None]] = None,
        min_batch_size: int = 10,
        max_batch_age_hours: int = 168,      # 1 week
        auto_batch: bool = True,
    ):
        self._queue = FalsePositiveQueue()
        self._all_reports: Dict[str, FalsePositiveReport] = {}
        self._confirmed_queue: List[FalsePositiveReport] = []
        self._training_batches: List[TrainingBatch] = []
        
        self._training_trigger = training_trigger
        self._min_batch_size = min_batch_size
        self._max_batch_age_hours = max_batch_age_hours
        self._auto_batch = auto_batch
        
        # Stats
        self._total_reports = 0
        self._confirmed_count = 0
        self._rejected_count = 0
        self._batches_created = 0
    
    # =========================================================================
    # Reporting
    # =========================================================================
    
    def report_false_positive(
        self,
        tenant_id: str,
        physician_id: str,
        encounter_id: str,
        input_text: str,
        block_reason: str,
        attack_type: AttackTypeBlocked = AttackTypeBlocked.UNKNOWN,
        confidence: float = 0.0,
        clinical_context: str = "",
        specialty: str = "",
        urgency: str = "normal",
        model_version: str = "",
        expected_output: str = "",
    ) -> FalsePositiveReport:
        """
        Report a false positive from a physician.
        
        This is the entry point when a physician clicks "This shouldn't be blocked".
        """
        report = FalsePositiveReport(
            tenant_id=tenant_id,
            physician_id=physician_id,
            encounter_id=encounter_id,
            attack_type_blocked=attack_type,
            confidence_when_blocked=confidence,
            input_text=input_text,
            expected_output=expected_output,
            block_reason=block_reason,
            model_version=model_version,
            specialty=specialty,
            clinical_context=clinical_context,
            urgency=urgency,
        )
        
        self._all_reports[report.report_id] = report
        self._queue.add(report)
        self._total_reports += 1
        
        logger.info(
            f"False positive reported: {report.report_id} "
            f"({report.attack_type_blocked.value}) from {physician_id}"
        )
        
        return report
    
    # =========================================================================
    # Review Process
    # =========================================================================
    
    def get_next_for_review(self) -> Optional[FalsePositiveReport]:
        """Get next report for security team review."""
        return self._queue.get_next()
    
    def review(
        self,
        report_id: str,
        reviewer_id: str,
        decision: ReviewDecision,
        notes: str = "",
    ) -> Optional[FalsePositiveReport]:
        """
        Record review decision.
        
        If approved, adds to training queue.
        """
        if report_id not in self._all_reports:
            return None
        
        report = self._all_reports[report_id]
        report.reviewed_at = datetime.now()
        report.reviewer_id = reviewer_id
        report.review_decision = decision
        report.review_notes = notes
        
        if decision == ReviewDecision.APPROVE_RETRAIN:
            report.status = FalsePositiveStatus.CONFIRMED
            self._confirmed_queue.append(report)
            self._confirmed_count += 1
            
            logger.info(f"FP report {report_id} confirmed for retraining")
            
            # Check if we should trigger batch
            if self._auto_batch:
                self._check_batch_trigger()
            
        elif decision == ReviewDecision.REJECT_TRUE_POSITIVE:
            report.status = FalsePositiveStatus.REJECTED
            self._rejected_count += 1
            
            logger.info(f"FP report {report_id} rejected (was true positive)")
            
        elif decision == ReviewDecision.NEEDS_CONTEXT:
            # Keep in review queue
            report.status = FalsePositiveStatus.UNDER_REVIEW
            report.tags.append("needs_context")
            
        elif decision == ReviewDecision.ESCALATE:
            report.status = FalsePositiveStatus.UNDER_REVIEW
            report.urgency = "urgent"
            report.tags.append("escalated")
        
        return report
    
    def _check_batch_trigger(self) -> Optional[TrainingBatch]:
        """Check if we should create a training batch."""
        if len(self._confirmed_queue) >= self._min_batch_size:
            return self.create_training_batch()
        
        # Check age of oldest confirmed
        if self._confirmed_queue:
            oldest = min(r.reviewed_at for r in self._confirmed_queue if r.reviewed_at)
            age_hours = (datetime.now() - oldest).total_seconds() / 3600
            
            if age_hours >= self._max_batch_age_hours and len(self._confirmed_queue) >= 3:
                return self.create_training_batch()
        
        return None
    
    # =========================================================================
    # Training Batches
    # =========================================================================
    
    def create_training_batch(self, model_version: str = "") -> TrainingBatch:
        """
        Create a training batch from confirmed false positives.
        """
        batch = TrainingBatch(
            report_ids=[r.report_id for r in self._confirmed_queue],
            sample_count=len(self._confirmed_queue),
            model_version_before=model_version,
        )
        
        # Update report statuses
        for report in self._confirmed_queue:
            report.status = FalsePositiveStatus.QUEUED_FOR_TRAINING
            report.training_batch_id = batch.batch_id
        
        self._training_batches.append(batch)
        self._confirmed_queue = []
        self._batches_created += 1
        
        logger.info(
            f"Created training batch {batch.batch_id} with {batch.sample_count} samples"
        )
        
        # Trigger training if callback provided
        if self._training_trigger:
            try:
                self._training_trigger(batch)
            except Exception as e:
                logger.error(f"Training trigger failed: {e}")
        
        return batch
    
    def get_training_samples(self, batch_id: str) -> List[Dict[str, Any]]:
        """
        Get training samples for a batch.
        
        Returns samples in ML training format.
        """
        batch = self._get_batch(batch_id)
        if not batch:
            return []
        
        samples = []
        for report_id in batch.report_ids:
            if report_id in self._all_reports:
                report = self._all_reports[report_id]
                samples.append(report.to_training_sample())
        
        return samples
    
    def mark_training_started(
        self,
        batch_id: str,
        model_version: str = "",
    ) -> Optional[TrainingBatch]:
        """Mark batch as started training."""
        batch = self._get_batch(batch_id)
        if not batch:
            return None
        
        batch.training_started_at = datetime.now()
        if model_version:
            batch.model_version_before = model_version
        
        # Update report statuses
        for report_id in batch.report_ids:
            if report_id in self._all_reports:
                self._all_reports[report_id].status = FalsePositiveStatus.TRAINING
        
        return batch
    
    def mark_training_completed(
        self,
        batch_id: str,
        new_model_version: str,
        accuracy_before: float,
        accuracy_after: float,
        fp_rate_before: float,
        fp_rate_after: float,
    ) -> Optional[TrainingBatch]:
        """Mark batch as completed training."""
        batch = self._get_batch(batch_id)
        if not batch:
            return None
        
        batch.training_completed_at = datetime.now()
        batch.model_version_after = new_model_version
        batch.accuracy_before = accuracy_before
        batch.accuracy_after = accuracy_after
        batch.false_positive_rate_before = fp_rate_before
        batch.false_positive_rate_after = fp_rate_after
        
        logger.info(
            f"Training completed for batch {batch_id}: "
            f"FP rate {fp_rate_before:.2%} -> {fp_rate_after:.2%}"
        )
        
        return batch
    
    def mark_deployed(self, batch_id: str) -> Optional[TrainingBatch]:
        """Mark batch model as deployed."""
        batch = self._get_batch(batch_id)
        if not batch:
            return None
        
        batch.is_deployed = True
        batch.deployed_at = datetime.now()
        
        # Update report statuses
        for report_id in batch.report_ids:
            if report_id in self._all_reports:
                report = self._all_reports[report_id]
                report.status = FalsePositiveStatus.DEPLOYED
                report.deployed_at = datetime.now()
                report.new_model_version = batch.model_version_after
        
        logger.info(f"Model from batch {batch_id} deployed")
        
        return batch
    
    def _get_batch(self, batch_id: str) -> Optional[TrainingBatch]:
        """Get batch by ID."""
        for batch in self._training_batches:
            if batch.batch_id == batch_id:
                return batch
        return None
    
    # =========================================================================
    # Queries
    # =========================================================================
    
    def get_report(self, report_id: str) -> Optional[FalsePositiveReport]:
        """Get report by ID."""
        return self._all_reports.get(report_id)
    
    def get_pending_reports(self) -> List[FalsePositiveReport]:
        """Get all reports pending review."""
        return [
            r for r in self._all_reports.values()
            if r.is_pending()
        ]
    
    def get_confirmed_reports(self) -> List[FalsePositiveReport]:
        """Get all confirmed false positives."""
        return [
            r for r in self._all_reports.values()
            if r.is_confirmed()
        ]
    
    def get_sla_breaches(self) -> List[FalsePositiveReport]:
        """Get reports breaching SLA."""
        return self._queue.get_breaching_sla()
    
    def get_similar_reports(
        self,
        input_text: str,
        attack_type: AttackTypeBlocked,
        limit: int = 5,
    ) -> List[FalsePositiveReport]:
        """
        Find similar historical reports.
        
        Used to detect patterns and link related issues.
        """
        similar = []
        
        for report in self._all_reports.values():
            if report.attack_type_blocked != attack_type:
                continue
            
            # Simple similarity: shared words
            input_words = set(input_text.lower().split())
            report_words = set(report.input_text.lower().split())
            
            if len(input_words & report_words) >= 3:
                similar.append(report)
        
        return similar[:limit]
    
    # =========================================================================
    # Stats & Reporting
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "total_reports": self._total_reports,
            "pending_review": self._queue.get_pending_count(),
            "under_review": self._queue.get_under_review_count(),
            "confirmed": self._confirmed_count,
            "rejected": self._rejected_count,
            "confirmation_rate": (
                self._confirmed_count / (self._confirmed_count + self._rejected_count)
                if (self._confirmed_count + self._rejected_count) > 0 else 0.0
            ),
            "awaiting_training": len(self._confirmed_queue),
            "batches_created": self._batches_created,
            "sla_breaches": len(self._queue.get_breaching_sla()),
        }
    
    def get_attack_type_breakdown(self) -> Dict[str, int]:
        """Get breakdown by attack type."""
        breakdown: Dict[str, int] = {}
        
        for report in self._all_reports.values():
            key = report.attack_type_blocked.value
            breakdown[key] = breakdown.get(key, 0) + 1
        
        return breakdown
    
    def get_specialty_breakdown(self) -> Dict[str, int]:
        """Get breakdown by physician specialty."""
        breakdown: Dict[str, int] = {}
        
        for report in self._all_reports.values():
            if report.specialty:
                breakdown[report.specialty] = breakdown.get(report.specialty, 0) + 1
        
        return breakdown
    
    def generate_weekly_report(self) -> Dict[str, Any]:
        """Generate weekly false positive report."""
        week_ago = datetime.now() - timedelta(days=7)
        
        weekly_reports = [
            r for r in self._all_reports.values()
            if r.reported_at >= week_ago
        ]
        
        weekly_confirmed = [
            r for r in weekly_reports
            if r.is_confirmed()
        ]
        
        weekly_rejected = [
            r for r in weekly_reports
            if r.status == FalsePositiveStatus.REJECTED
        ]
        
        return {
            "period": {
                "start": week_ago.isoformat(),
                "end": datetime.now().isoformat(),
            },
            "volume": {
                "total_reports": len(weekly_reports),
                "confirmed": len(weekly_confirmed),
                "rejected": len(weekly_rejected),
                "pending": len([r for r in weekly_reports if r.is_pending()]),
            },
            "confirmation_rate": (
                len(weekly_confirmed) / len(weekly_reports)
                if weekly_reports else 0.0
            ),
            "attack_types": self.get_attack_type_breakdown(),
            "specialties": self.get_specialty_breakdown(),
            "avg_review_time_hours": self._calculate_avg_review_time(weekly_reports),
            "sla_breaches": len([
                r for r in weekly_reports
                if r in self._queue.get_breaching_sla()
            ]),
            "training_batches": len([
                b for b in self._training_batches
                if b.created_at >= week_ago
            ]),
        }
    
    def _calculate_avg_review_time(
        self,
        reports: List[FalsePositiveReport],
    ) -> float:
        """Calculate average review time in hours."""
        reviewed = [
            r for r in reports
            if r.reviewed_at and r.reported_at
        ]
        
        if not reviewed:
            return 0.0
        
        times = [
            (r.reviewed_at - r.reported_at).total_seconds() / 3600
            for r in reviewed
        ]
        
        return sum(times) / len(times)
