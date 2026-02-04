"""
Tests for Phoenix Guardian Feedback Module
Week 19-20: Physician Feedback System Tests

Tests feedback collection, false positive handling, and feature suggestions.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import json

from phoenix_guardian.feedback.physician_feedback import (
    FeedbackType,
    FeedbackCategory,
    FeedbackPriority,
    FeedbackStatus,
    PhysicianFeedback,
    FeedbackCollector,
    FeedbackAggregation,
)
from phoenix_guardian.feedback.false_positive_loop import (
    FalsePositiveReport,
    FalsePositiveStatus,
    FalsePositiveQueue,
    FalsePositiveLoop,
    AttackTypeBlocked,
    ReviewDecision,
)
from phoenix_guardian.feedback.suggestion_processor import (
    FeatureSuggestion,
    SuggestionStatus,
    SuggestionProcessor,
    SuggestionPriority,
    SuggestionCategory,
)


# ==============================================================================
# Physician Feedback Tests
# ==============================================================================

class TestFeedbackType:
    """Tests for FeedbackType enum."""
    
    def test_feedback_types_defined(self):
        """Test all feedback types are defined."""
        assert FeedbackType.RATING
        assert FeedbackType.SUGGESTION
        assert FeedbackType.BUG_REPORT
        assert FeedbackType.FALSE_POSITIVE
        assert FeedbackType.PRAISE
        assert FeedbackType.QUALITY_ISSUE


class TestFeedbackCategory:
    """Tests for FeedbackCategory enum."""
    
    def test_feedback_categories_defined(self):
        """Test all categories are defined."""
        assert FeedbackCategory.AI_SCRIBE
        assert FeedbackCategory.PERFORMANCE
        assert FeedbackCategory.SECURITY
        assert FeedbackCategory.UI_UX
        assert FeedbackCategory.CLINICAL_NAVIGATION


class TestPhysicianFeedback:
    """Tests for PhysicianFeedback dataclass."""
    
    def test_create_rating_feedback(self):
        """Test creating rating feedback."""
        feedback = PhysicianFeedback(
            tenant_id="medsys",
            physician_id="dr-smith",
            feedback_type=FeedbackType.RATING,
            rating=5,
            summary="Great experience!",
        )
        
        assert feedback.feedback_id is not None
        assert feedback.rating == 5
        assert feedback.feedback_type == FeedbackType.RATING
        assert feedback.tenant_id == "medsys"
    
    def test_create_bug_report_feedback(self):
        """Test creating bug report feedback."""
        feedback = PhysicianFeedback(
            physician_id="dr-jones",
            tenant_id="medsys",
            feedback_type=FeedbackType.BUG_REPORT,
            category=FeedbackCategory.AI_SCRIBE,
            summary="AI suggested incorrect medication dosage",
            details="Expected 10mg but got 100mg suggestion",
            encounter_id="enc-123",
        )
        
        assert feedback.feedback_type == FeedbackType.BUG_REPORT
        assert feedback.category == FeedbackCategory.AI_SCRIBE
        assert "medication" in feedback.summary
    
    def test_create_false_positive_feedback(self):
        """Test creating false positive feedback."""
        feedback = PhysicianFeedback(
            tenant_id="medsys",
            physician_id="dr-jones",
            feedback_type=FeedbackType.FALSE_POSITIVE,
            category=FeedbackCategory.SECURITY,
            summary="Legitimate query blocked as prompt injection",
            details="Patient query about medication interactions was blocked",
            encounter_id="enc-456",
        )
        
        assert feedback.feedback_type == FeedbackType.FALSE_POSITIVE
        assert feedback.category == FeedbackCategory.SECURITY
    
    def test_feedback_with_metadata(self):
        """Test feedback with full metadata."""
        feedback = PhysicianFeedback(
            tenant_id="regional",
            physician_id="dr-wilson",
            feedback_type=FeedbackType.SUGGESTION,
            category=FeedbackCategory.UI_UX,
            priority=FeedbackPriority.MEDIUM,
            summary="Need keyboard shortcuts",
            details="Would save time during consultations",
            tags=["ux", "productivity", "keyboard"],
            physician_specialty="Cardiology",
        )
        
        assert len(feedback.tags) == 3
        assert feedback.physician_specialty == "Cardiology"
    
    def test_feedback_rating_range(self):
        """Test feedback with valid rating."""
        feedback = PhysicianFeedback(
            tenant_id="medsys",
            physician_id="dr-smith",
            feedback_type=FeedbackType.RATING,
            rating=4,
        )
        
        assert 1 <= feedback.rating <= 5
    
    def test_feedback_to_dict(self):
        """Test serializing feedback to dict."""
        feedback = PhysicianFeedback(
            tenant_id="medsys",
            physician_id="dr-smith",
            summary="Test feedback",
            rating=5,
        )
        
        data = feedback.to_dict()
        
        assert data["tenant_id"] == "medsys"
        assert data["physician_id"] == "dr-smith"
        assert data["rating"] == 5
        assert "created_at" in data
    
    def test_feedback_is_positive(self):
        """Test is_positive method."""
        positive = PhysicianFeedback(
            feedback_type=FeedbackType.RATING,
            rating=5,
        )
        
        negative = PhysicianFeedback(
            feedback_type=FeedbackType.RATING,
            rating=2,
        )
        
        assert positive.is_positive() is True
        assert negative.is_positive() is False
    
    def test_feedback_is_negative(self):
        """Test is_negative method."""
        bug_report = PhysicianFeedback(
            feedback_type=FeedbackType.BUG_REPORT,
            summary="Something broke",
        )
        
        praise = PhysicianFeedback(
            feedback_type=FeedbackType.PRAISE,
            summary="Great work!",
        )
        
        assert bug_report.is_negative() is True
        assert praise.is_negative() is False


class TestFeedbackCollector:
    """Tests for FeedbackCollector."""
    
    def test_collector_creation(self):
        """Test creating feedback collector."""
        collector = FeedbackCollector()
        
        assert collector._total_collected == 0
    
    def test_collector_record_rating(self):
        """Test recording a rating."""
        collector = FeedbackCollector()
        
        feedback = collector.record_rating(
            tenant_id="medsys",
            physician_id="dr-smith",
            rating=5,
            summary="Excellent!",
        )
        
        assert feedback.rating == 5
        assert feedback.feedback_type == FeedbackType.RATING
    
    def test_collector_record_issue(self):
        """Test recording an issue."""
        collector = FeedbackCollector()
        
        feedback = collector.record_issue(
            tenant_id="medsys",
            physician_id="dr-jones",
            category=FeedbackCategory.AI_SCRIBE,
            summary="Incorrect assessment",
            details="Missing differential diagnosis",
        )
        
        assert feedback.category == FeedbackCategory.AI_SCRIBE
        assert feedback.summary == "Incorrect assessment"
    
    def test_collector_get_physician_feedback(self):
        """Test getting feedback by physician."""
        collector = FeedbackCollector()
        
        # Record feedback
        collector.record_rating(tenant_id="medsys", physician_id="dr-smith", rating=5)
        collector.record_rating(tenant_id="medsys", physician_id="dr-smith", rating=4)
        collector.record_rating(tenant_id="regional", physician_id="dr-jones", rating=3)
        
        smith_feedback = collector.get_physician_feedback("dr-smith")
        
        assert len(smith_feedback) == 2
    
    def test_collector_get_actionable(self):
        """Test getting actionable feedback."""
        collector = FeedbackCollector()
        
        collector.record_rating(tenant_id="medsys", physician_id="dr-1", rating=5)
        collector.record_issue(
            tenant_id="medsys",
            physician_id="dr-2",
            category=FeedbackCategory.AI_SCRIBE,
            summary="Bug",
        )
        
        actionable = collector.get_actionable()
        
        assert len(actionable) >= 1


class TestFeedbackAggregation:
    """Tests for FeedbackAggregation."""
    
    def test_aggregation_creation(self):
        """Test creating aggregation."""
        agg = FeedbackAggregation(
            tenant_id="medsys",
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now(),
            total_feedback=100,
            average_rating=4.3,
        )
        
        assert agg.tenant_id == "medsys"
        assert agg.total_feedback == 100
        assert agg.average_rating == 4.3
    
    def test_aggregation_to_dict(self):
        """Test aggregation serialization."""
        agg = FeedbackAggregation(
            tenant_id="medsys",
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now(),
            total_feedback=50,
            positive_count=40,
            negative_count=10,
        )
        
        data = agg.to_dict()
        
        assert data["tenant_id"] == "medsys"
        assert data["volume"]["total"] == 50
        assert data["sentiment"]["positive"] == 40


# ==============================================================================
# False Positive Loop Tests
# ==============================================================================

class TestFalsePositiveStatus:
    """Tests for FalsePositiveStatus enum."""
    
    def test_status_values(self):
        """Test all status values exist."""
        assert FalsePositiveStatus.PENDING
        assert FalsePositiveStatus.UNDER_REVIEW
        assert FalsePositiveStatus.CONFIRMED
        assert FalsePositiveStatus.REJECTED
        assert FalsePositiveStatus.QUEUED_FOR_TRAINING


class TestFalsePositiveReport:
    """Tests for FalsePositiveReport dataclass."""
    
    def test_create_report(self):
        """Test creating a false positive report."""
        report = FalsePositiveReport(
            tenant_id="medsys",
            physician_id="dr-smith",
            encounter_id="enc-123",
            attack_type_blocked=AttackTypeBlocked.PROMPT_INJECTION,
            input_text="What medications interact with warfarin?",
            block_reason="Detected potential prompt injection pattern",
        )
        
        assert report.report_id is not None
        assert report.status == FalsePositiveStatus.PENDING
        assert report.attack_type_blocked == AttackTypeBlocked.PROMPT_INJECTION
    
    def test_report_with_context(self):
        """Test report with clinical context."""
        report = FalsePositiveReport(
            tenant_id="medsys",
            physician_id="dr-jones",
            specialty="Cardiology",
            clinical_context="Reviewing medication interactions for patient",
            urgency="high",
        )
        
        assert report.specialty == "Cardiology"
        assert report.urgency == "high"
    
    def test_report_to_dict(self):
        """Test report serialization."""
        report = FalsePositiveReport(
            tenant_id="medsys",
            physician_id="dr-smith",
            input_text="test input",
        )
        
        data = report.to_dict()
        
        assert data["tenant_id"] == "medsys"
        assert data["status"] == "pending"


class TestFalsePositiveQueue:
    """Tests for FalsePositiveQueue."""
    
    def test_queue_creation(self):
        """Test creating queue."""
        queue = FalsePositiveQueue()
        
        assert queue.get_pending_count() == 0
    
    def test_queue_add_report(self):
        """Test adding report to queue."""
        queue = FalsePositiveQueue()
        
        report = FalsePositiveReport(
            tenant_id="medsys",
            physician_id="dr-smith",
        )
        
        queue.add(report)
        
        assert queue.get_pending_count() == 1
    
    def test_queue_get_next(self):
        """Test getting next report for review."""
        queue = FalsePositiveQueue()
        
        for i in range(3):
            queue.add(FalsePositiveReport(
                tenant_id="medsys",
                physician_id=f"dr-{i}",
            ))
        
        report = queue.get_next()
        
        assert report is not None
        assert report.status == FalsePositiveStatus.UNDER_REVIEW
        assert queue.get_pending_count() == 2
    
    def test_queue_priority_sorting(self):
        """Test queue sorts by urgency."""
        queue = FalsePositiveQueue()
        
        # Add normal priority
        queue.add(FalsePositiveReport(
            tenant_id="medsys",
            physician_id="dr-normal",
            urgency="normal",
        ))
        
        # Add urgent priority
        queue.add(FalsePositiveReport(
            tenant_id="medsys",
            physician_id="dr-urgent",
            urgency="urgent",
        ))
        
        # Should get urgent first
        report = queue.get_next()
        assert report.urgency == "urgent"


class TestFalsePositiveLoop:
    """Tests for FalsePositiveLoop."""
    
    def test_loop_creation(self):
        """Test creating the loop."""
        loop = FalsePositiveLoop()
        
        assert loop._queue is not None
    
    def test_loop_report_false_positive(self):
        """Test reporting a false positive through the loop."""
        loop = FalsePositiveLoop()
        
        report = loop.report_false_positive(
            tenant_id="medsys",
            physician_id="dr-smith",
            encounter_id="enc-123",
            input_text="Legitimate medical query",
            block_reason="Pattern match false trigger",
            attack_type=AttackTypeBlocked.PROMPT_INJECTION,
        )
        
        assert report.report_id is not None
        assert loop._queue.get_pending_count() == 1
    
    def test_loop_review_approve(self):
        """Test approving a report through review."""
        loop = FalsePositiveLoop()
        
        # Submit report
        report = loop.report_false_positive(
            tenant_id="medsys",
            physician_id="dr-smith",
            encounter_id="enc-123",
            input_text="Query",
            block_reason="Reason",
        )
        
        # Get for review
        for_review = loop.get_next_for_review()
        assert for_review is not None
        
        # Approve
        reviewed = loop.review(
            report_id=report.report_id,
            reviewer_id="analyst-001",
            decision=ReviewDecision.APPROVE_RETRAIN,
            notes="Valid clinical content",
        )
        
        assert reviewed.status == FalsePositiveStatus.CONFIRMED
    
    def test_loop_create_training_batch(self):
        """Test creating a training batch."""
        loop = FalsePositiveLoop(min_batch_size=2, auto_batch=False)
        
        # Submit and approve multiple reports
        for i in range(3):
            report = loop.report_false_positive(
                tenant_id="medsys",
                physician_id=f"dr-{i}",
                encounter_id=f"enc-{i}",
                input_text=f"Query {i}",
                block_reason="False trigger",
            )
            
            loop.get_next_for_review()
            loop.review(
                report_id=report.report_id,
                reviewer_id="analyst-001",
                decision=ReviewDecision.APPROVE_RETRAIN,
            )
        
        # Create batch
        batch = loop.create_training_batch()
        
        assert batch.sample_count == 3
        assert len(batch.report_ids) == 3


# ==============================================================================
# Suggestion Processor Tests
# ==============================================================================

class TestSuggestionPriority:
    """Tests for SuggestionPriority enum."""
    
    def test_priority_values(self):
        """Test all priority values exist."""
        assert SuggestionPriority.CRITICAL
        assert SuggestionPriority.HIGH
        assert SuggestionPriority.MEDIUM
        assert SuggestionPriority.LOW
        assert SuggestionPriority.WISHLIST


class TestSuggestionStatus:
    """Tests for SuggestionStatus enum."""
    
    def test_status_values(self):
        """Test all status values exist."""
        assert SuggestionStatus.NEW
        assert SuggestionStatus.TRIAGED
        assert SuggestionStatus.ACCEPTED
        assert SuggestionStatus.IN_DEVELOPMENT
        assert SuggestionStatus.RELEASED


class TestFeatureSuggestion:
    """Tests for FeatureSuggestion dataclass."""
    
    def test_create_suggestion(self):
        """Test creating a suggestion."""
        suggestion = FeatureSuggestion(
            tenant_id="medsys",
            title="Add keyboard shortcuts",
            description="Would speed up workflow significantly",
        )
        
        assert suggestion.suggestion_id is not None
        assert suggestion.status == SuggestionStatus.NEW
        assert suggestion.vote_count == 1
    
    def test_suggestion_with_priority(self):
        """Test suggestion with priority."""
        suggestion = FeatureSuggestion(
            title="Critical fix needed",
            priority=SuggestionPriority.HIGH,
            category=SuggestionCategory.WORKFLOW,
        )
        
        assert suggestion.priority == SuggestionPriority.HIGH
        assert suggestion.category == SuggestionCategory.WORKFLOW
    
    def test_suggestion_to_dict(self):
        """Test suggestion serialization."""
        suggestion = FeatureSuggestion(
            tenant_id="medsys",
            title="New feature",
            vote_count=5,
        )
        
        data = suggestion.to_dict()
        
        assert data["title"] == "New feature"
        assert data["vote_count"] == 5


class TestSuggestionProcessor:
    """Tests for SuggestionProcessor."""
    
    def test_processor_creation(self):
        """Test creating processor."""
        processor = SuggestionProcessor()
        
        assert processor._suggestions == {}
    
    def test_processor_process_suggestion(self):
        """Test processing a suggestion."""
        processor = SuggestionProcessor()
        
        suggestion = processor.process_suggestion(
            tenant_id="medsys",
            physician_id="dr-smith",
            feedback_id="fb-001",
            title="Better search",
            description="Need faster patient lookup",
            category=SuggestionCategory.WORKFLOW,
        )
        
        assert suggestion.suggestion_id is not None
        assert suggestion.title == "Better search"
    
    def test_processor_merge_similar(self):
        """Test that suggestions are stored correctly."""
        processor = SuggestionProcessor()
        
        # First suggestion
        s1 = processor.process_suggestion(
            tenant_id="medsys",
            physician_id="dr-smith",
            feedback_id="fb-001",
            title="Faster search functionality needed",
            description="Need faster patient lookup",
            category=SuggestionCategory.WORKFLOW,
        )
        
        # Different suggestion
        s2 = processor.process_suggestion(
            tenant_id="medsys",
            physician_id="dr-jones",
            feedback_id="fb-002",
            title="Add voice recording feature",
            description="Allow dictating SOAP notes",
            category=SuggestionCategory.WORKFLOW,
        )
        
        # Should have two separate suggestions
        assert s1.suggestion_id != s2.suggestion_id
        assert len(processor._suggestions) == 2
    
    def test_processor_get_by_status(self):
        """Test getting suggestions by status."""
        processor = SuggestionProcessor()
        
        # Submit some suggestions
        processor.process_suggestion(
            tenant_id="medsys",
            physician_id="dr-1",
            feedback_id="fb-1",
            title="Feature 1",
        )
        processor.process_suggestion(
            tenant_id="medsys",
            physician_id="dr-2",
            feedback_id="fb-2",
            title="Feature 2",
        )
        
        new_suggestions = processor.get_by_status(SuggestionStatus.NEW)
        
        assert len(new_suggestions) == 2
    
    def test_processor_triage(self):
        """Test triaging a suggestion."""
        processor = SuggestionProcessor()
        
        suggestion = processor.process_suggestion(
            tenant_id="medsys",
            physician_id="dr-smith",
            feedback_id="fb-001",
            title="Needs triage",
        )
        
        processor.triage(
            suggestion_id=suggestion.suggestion_id,
            triaged_by="pm-alice",
            estimated_effort="M",
            estimated_impact="High",
            notes="Important for pilot success",
        )
        
        updated = processor.get_suggestion(suggestion.suggestion_id)
        assert updated.status == SuggestionStatus.TRIAGED
    
    def test_processor_get_prioritized_backlog(self):
        """Test getting prioritized suggestions."""
        processor = SuggestionProcessor()
        
        # Submit suggestions
        s1 = processor.process_suggestion(
            tenant_id="medsys",
            physician_id="dr-1",
            feedback_id="fb-1",
            title="Feature 1",
        )
        s2 = processor.process_suggestion(
            tenant_id="medsys",
            physician_id="dr-2",
            feedback_id="fb-2",
            title="Feature 2",
        )
        
        # Add votes to s1
        s1.vote_count = 5
        
        backlog = processor.get_prioritized_backlog()
        
        assert len(backlog) >= 1


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestFeedbackIntegration:
    """Integration tests for feedback system."""
    
    def test_feedback_to_false_positive_flow(self):
        """Test flow from feedback to false positive report."""
        collector = FeedbackCollector()
        loop = FalsePositiveLoop()
        
        # Physician reports false positive via feedback
        feedback = collector.record_false_positive(
            tenant_id="medsys",
            physician_id="dr-smith",
            encounter_id="enc-123",
            summary="Legitimate query was blocked",
            details="Clinical query about medication interactions",
        )
        
        # Create false positive report from feedback
        report = loop.report_false_positive(
            tenant_id=feedback.tenant_id,
            physician_id=feedback.physician_id,
            encounter_id=feedback.encounter_id,
            input_text=feedback.details,
            block_reason="Pattern match",
        )
        
        assert report.status == FalsePositiveStatus.PENDING
    
    def test_suggestion_aggregation_flow(self):
        """Test suggestion processing from multiple physicians."""
        processor = SuggestionProcessor()
        
        # Multiple physicians suggest different features
        s1 = processor.process_suggestion(
            tenant_id="medsys",
            physician_id="dr-1",
            feedback_id="fb-1",
            title="Faster search function",
            category=SuggestionCategory.WORKFLOW,
        )
        
        # Different suggestion
        s2 = processor.process_suggestion(
            tenant_id="medsys",
            physician_id="dr-2",
            feedback_id="fb-2",
            title="Add voice recognition",
            category=SuggestionCategory.AI_QUALITY,
        )
        
        s3 = processor.process_suggestion(
            tenant_id="medsys",
            physician_id="dr-3",
            feedback_id="fb-3",
            title="Improve SOAP formatting",
            category=SuggestionCategory.WORKFLOW,
        )
        
        # Check all were stored as separate suggestions
        assert len(processor._suggestions) == 3
        assert s1.suggestion_id != s2.suggestion_id
        assert s2.suggestion_id != s3.suggestion_id
    
    def test_full_feedback_cycle(self):
        """Test complete feedback cycle from collection to action."""
        collector = FeedbackCollector()
        
        # Record various feedback
        collector.record_rating(tenant_id="medsys", physician_id="dr-1", rating=5)
        collector.record_rating(tenant_id="medsys", physician_id="dr-2", rating=4)
        collector.record_issue(
            tenant_id="medsys",
            physician_id="dr-3",
            category=FeedbackCategory.AI_SCRIBE,
            summary="Minor issue",
        )
        
        # Aggregate
        agg = collector.aggregate(
            tenant_id="medsys",
            period_start=datetime.now() - timedelta(hours=1),
            period_end=datetime.now(),
        )
        
        assert agg.total_feedback == 3
        assert agg.average_rating > 0
