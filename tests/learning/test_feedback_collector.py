"""
Tests for FeedbackCollector.

Comprehensive tests covering:
- Feedback validation
- Database operations (mocked)
- Statistics calculations
- Training data retrieval
- Error handling
"""

import json
import sys
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from typing import Dict, Any, List

import pytest

# Mock psycopg2 before importing the module
mock_psycopg2 = MagicMock()
mock_psycopg2.Error = Exception
mock_psycopg2.extras = MagicMock()
mock_psycopg2.extras.RealDictCursor = MagicMock()
mock_psycopg2.pool = MagicMock()
mock_psycopg2.pool.ThreadedConnectionPool = MagicMock()

sys.modules['psycopg2'] = mock_psycopg2
sys.modules['psycopg2.extras'] = mock_psycopg2.extras
sys.modules['psycopg2.pool'] = mock_psycopg2.pool

from phoenix_guardian.learning.feedback_collector import (
    FeedbackCollector,
    Feedback,
    FeedbackType,
    FeedbackStats,
    TrainingBatch,
    FeedbackError,
    FeedbackDatabaseError,
    FeedbackValidationError,
    FeedbackConnectionError,
    VALID_FEEDBACK_TYPES,
    FEEDBACK_SCHEMA_VERSION,
    CREATE_FEEDBACK_TABLE_SQL,
)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def db_config():
    """Database configuration for tests."""
    return {
        "host": "localhost",
        "port": 5432,
        "database": "phoenix_test",
        "user": "test_user",
        "password": "test_password",
    }


@pytest.fixture
def sample_session_id():
    """Sample session UUID."""
    return uuid.uuid4()


@pytest.fixture
def sample_feedback(sample_session_id):
    """Sample feedback object."""
    return Feedback(
        agent_name="safety_agent",
        user_id=123,
        session_id=sample_session_id,
        suggestion="Check for aspirin-warfarin interaction",
        user_feedback="accept",
        confidence_score=0.95,
        context={"patient_id": "12345", "medication": "aspirin"},
        model_version="safety_agent_v1.2.0",
    )


@pytest.fixture
def sample_modify_feedback(sample_session_id):
    """Sample modify feedback object."""
    return Feedback(
        agent_name="scribe_agent",
        user_id=456,
        session_id=sample_session_id,
        suggestion="Patient reports headache for 3 days",
        user_feedback="modify",
        modified_output="Patient reports severe headache for 3 days, unresponsive to OTC medication",
        confidence_score=0.75,
        context={"encounter_id": "enc-123"},
        model_version="scribe_agent_v2.0.0",
    )


@pytest.fixture
def mock_psycopg2_fixture():
    """Mock psycopg2 module."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    
    # Setup cursor context manager
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
    
    mock_psycopg2.connect.return_value = mock_conn
    
    return mock_psycopg2, mock_conn, mock_cursor


@pytest.fixture
def mock_collector(db_config, mock_psycopg2_fixture):
    """Create a mocked FeedbackCollector."""
    mock_pg, mock_conn, mock_cursor = mock_psycopg2_fixture
    
    collector = FeedbackCollector(db_config)
    collector._conn = mock_conn
    collector._connected = True
    
    return collector, mock_conn, mock_cursor


# ═══════════════════════════════════════════════════════════════════════════════
# FEEDBACK VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFeedbackValidation:
    """Tests for Feedback validation."""
    
    def test_valid_accept_feedback(self, sample_session_id):
        """Test creating valid accept feedback."""
        feedback = Feedback(
            agent_name="safety_agent",
            user_id=123,
            session_id=sample_session_id,
            suggestion="Test suggestion",
            user_feedback="accept",
        )
        
        assert feedback.agent_name == "safety_agent"
        assert feedback.user_feedback == "accept"
        assert feedback.timestamp is not None
    
    def test_valid_reject_feedback(self, sample_session_id):
        """Test creating valid reject feedback."""
        feedback = Feedback(
            agent_name="quality_agent",
            user_id=456,
            session_id=sample_session_id,
            suggestion="Test suggestion",
            user_feedback="reject",
        )
        
        assert feedback.user_feedback == "reject"
    
    def test_valid_modify_feedback(self, sample_session_id):
        """Test creating valid modify feedback with modified_output."""
        feedback = Feedback(
            agent_name="scribe_agent",
            user_id=789,
            session_id=sample_session_id,
            suggestion="Original text",
            user_feedback="modify",
            modified_output="Corrected text",
        )
        
        assert feedback.user_feedback == "modify"
        assert feedback.modified_output == "Corrected text"
    
    def test_invalid_feedback_type(self, sample_session_id):
        """Test that invalid feedback type raises error."""
        with pytest.raises(FeedbackValidationError) as exc:
            Feedback(
                agent_name="test_agent",
                user_id=123,
                session_id=sample_session_id,
                suggestion="Test",
                user_feedback="invalid_type",
            )
        
        assert "Invalid feedback type" in str(exc.value)
    
    def test_modify_without_modified_output(self, sample_session_id):
        """Test that modify feedback requires modified_output."""
        with pytest.raises(FeedbackValidationError) as exc:
            Feedback(
                agent_name="test_agent",
                user_id=123,
                session_id=sample_session_id,
                suggestion="Test",
                user_feedback="modify",
            )
        
        assert "modified_output is required" in str(exc.value)
    
    def test_invalid_confidence_score_too_high(self, sample_session_id):
        """Test that confidence score > 1 raises error."""
        with pytest.raises(FeedbackValidationError) as exc:
            Feedback(
                agent_name="test_agent",
                user_id=123,
                session_id=sample_session_id,
                suggestion="Test",
                user_feedback="accept",
                confidence_score=1.5,
            )
        
        assert "Confidence score must be between 0 and 1" in str(exc.value)
    
    def test_invalid_confidence_score_negative(self, sample_session_id):
        """Test that negative confidence score raises error."""
        with pytest.raises(FeedbackValidationError) as exc:
            Feedback(
                agent_name="test_agent",
                user_id=123,
                session_id=sample_session_id,
                suggestion="Test",
                user_feedback="accept",
                confidence_score=-0.5,
            )
        
        assert "Confidence score must be between 0 and 1" in str(exc.value)
    
    def test_string_session_id_conversion(self):
        """Test that string session_id is converted to UUID."""
        session_str = "550e8400-e29b-41d4-a716-446655440000"
        feedback = Feedback(
            agent_name="test_agent",
            user_id=123,
            session_id=session_str,
            suggestion="Test",
            user_feedback="accept",
        )
        
        assert isinstance(feedback.session_id, uuid.UUID)
        assert str(feedback.session_id) == session_str
    
    def test_feedback_to_dict(self, sample_feedback):
        """Test converting feedback to dictionary."""
        data = sample_feedback.to_dict()
        
        assert data["agent_name"] == "safety_agent"
        assert data["user_id"] == 123
        assert data["user_feedback"] == "accept"
        assert data["confidence_score"] == 0.95
        assert isinstance(data["session_id"], str)
    
    def test_feedback_from_dict(self):
        """Test creating feedback from dictionary."""
        data = {
            "agent_name": "test_agent",
            "user_id": 100,
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "suggestion": "Test suggestion",
            "user_feedback": "accept",
            "confidence_score": 0.8,
            "timestamp": "2026-01-31T10:00:00",
        }
        
        feedback = Feedback.from_dict(data)
        
        assert feedback.agent_name == "test_agent"
        assert feedback.user_id == 100
        assert feedback.confidence_score == 0.8
        assert feedback.timestamp == datetime(2026, 1, 31, 10, 0, 0)


# ═══════════════════════════════════════════════════════════════════════════════
# FEEDBACK TYPE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFeedbackType:
    """Tests for FeedbackType enum."""
    
    def test_valid_types(self):
        """Test all valid feedback types."""
        assert FeedbackType.ACCEPT.value == "accept"
        assert FeedbackType.REJECT.value == "reject"
        assert FeedbackType.MODIFY.value == "modify"
    
    def test_is_valid_positive(self):
        """Test is_valid returns True for valid types."""
        assert FeedbackType.is_valid("accept") is True
        assert FeedbackType.is_valid("reject") is True
        assert FeedbackType.is_valid("modify") is True
    
    def test_is_valid_negative(self):
        """Test is_valid returns False for invalid types."""
        assert FeedbackType.is_valid("invalid") is False
        assert FeedbackType.is_valid("ACCEPT") is False  # Case sensitive
        assert FeedbackType.is_valid("") is False


# ═══════════════════════════════════════════════════════════════════════════════
# FEEDBACK STATS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFeedbackStats:
    """Tests for FeedbackStats."""
    
    def test_stats_creation(self):
        """Test creating feedback stats."""
        stats = FeedbackStats(
            total_feedback=100,
            accepted=70,
            rejected=20,
            modified=10,
            avg_confidence=0.85,
        )
        
        assert stats.total_feedback == 100
        assert stats.accepted == 70
        assert stats.acceptance_rate == 70.0
    
    def test_acceptance_rate_calculation(self):
        """Test acceptance rate is calculated correctly."""
        stats = FeedbackStats(
            total_feedback=200,
            accepted=150,
            rejected=30,
            modified=20,
            avg_confidence=0.9,
        )
        
        assert stats.acceptance_rate == 75.0
    
    def test_zero_feedback_handling(self):
        """Test handling of zero total feedback."""
        stats = FeedbackStats(
            total_feedback=0,
            accepted=0,
            rejected=0,
            modified=0,
            avg_confidence=None,
        )
        
        assert stats.acceptance_rate == 0.0
    
    def test_stats_to_dict(self):
        """Test converting stats to dictionary."""
        stats = FeedbackStats(
            total_feedback=100,
            accepted=80,
            rejected=15,
            modified=5,
            avg_confidence=0.88,
            used_for_training=50,
        )
        
        data = stats.to_dict()
        
        assert data["total_feedback"] == 100
        assert data["acceptance_rate"] == 80.0
        assert data["pending_training"] == 50


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING BATCH TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTrainingBatch:
    """Tests for TrainingBatch."""
    
    def test_batch_creation(self, sample_feedback, sample_modify_feedback):
        """Test creating a training batch."""
        batch = TrainingBatch(
            feedback_ids=[1, 2],
            feedback_items=[sample_feedback, sample_modify_feedback],
        )
        
        assert batch.size == 2
        assert len(batch.feedback_ids) == 2
    
    def test_get_training_pairs_accept(self, sample_session_id):
        """Test training pairs for accept feedback."""
        feedback = Feedback(
            agent_name="test_agent",
            user_id=1,
            session_id=sample_session_id,
            suggestion="Good suggestion",
            user_feedback="accept",
        )
        
        batch = TrainingBatch(
            feedback_ids=[1],
            feedback_items=[feedback],
        )
        
        pairs = batch.get_training_pairs()
        
        assert len(pairs) == 1
        assert pairs[0] == ("Good suggestion", "Good suggestion")
    
    def test_get_training_pairs_modify(self, sample_session_id):
        """Test training pairs for modify feedback."""
        feedback = Feedback(
            agent_name="test_agent",
            user_id=1,
            session_id=sample_session_id,
            suggestion="Original text",
            user_feedback="modify",
            modified_output="Corrected text",
        )
        
        batch = TrainingBatch(
            feedback_ids=[1],
            feedback_items=[feedback],
        )
        
        pairs = batch.get_training_pairs()
        
        assert len(pairs) == 1
        assert pairs[0] == ("Original text", "Corrected text")
    
    def test_get_training_pairs_reject_excluded(self, sample_session_id):
        """Test that reject feedback is excluded from training pairs."""
        feedback = Feedback(
            agent_name="test_agent",
            user_id=1,
            session_id=sample_session_id,
            suggestion="Bad suggestion",
            user_feedback="reject",
        )
        
        batch = TrainingBatch(
            feedback_ids=[1],
            feedback_items=[feedback],
        )
        
        pairs = batch.get_training_pairs()
        
        assert len(pairs) == 0
    
    def test_mixed_training_pairs(self, sample_session_id):
        """Test training pairs with mixed feedback types."""
        accept_fb = Feedback(
            agent_name="test", user_id=1, session_id=sample_session_id,
            suggestion="Accept this", user_feedback="accept"
        )
        reject_fb = Feedback(
            agent_name="test", user_id=1, session_id=sample_session_id,
            suggestion="Reject this", user_feedback="reject"
        )
        modify_fb = Feedback(
            agent_name="test", user_id=1, session_id=sample_session_id,
            suggestion="Modify this", user_feedback="modify",
            modified_output="Modified version"
        )
        
        batch = TrainingBatch(
            feedback_ids=[1, 2, 3],
            feedback_items=[accept_fb, reject_fb, modify_fb],
        )
        
        pairs = batch.get_training_pairs()
        
        assert len(pairs) == 2  # Accept and modify only
        assert ("Accept this", "Accept this") in pairs
        assert ("Modify this", "Modified version") in pairs


# ═══════════════════════════════════════════════════════════════════════════════
# FEEDBACK COLLECTOR TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFeedbackCollector:
    """Tests for FeedbackCollector."""
    
    def test_initialization(self, db_config):
        """Test collector initialization."""
        collector = FeedbackCollector(db_config)
        
        assert collector.db_config == db_config
        assert collector._connected is False
        assert collector.use_pool is False
    
    def test_initialization_with_pool(self, db_config):
        """Test collector initialization with connection pool."""
        collector = FeedbackCollector(
            db_config,
            use_pool=True,
            pool_min_conn=2,
            pool_max_conn=20,
        )
        
        assert collector.use_pool is True
        assert collector.pool_min_conn == 2
        assert collector.pool_max_conn == 20
    
    def test_connect_success(self, db_config, mock_psycopg2_fixture):
        """Test successful database connection."""
        mock_pg, mock_conn, _ = mock_psycopg2_fixture
        
        collector = FeedbackCollector(db_config)
        collector.connect()
        
        assert collector._connected is True
        mock_pg.connect.assert_called_once_with(**db_config)
    
    def test_close(self, mock_collector):
        """Test closing connection."""
        collector, mock_conn, _ = mock_collector
        
        collector.close()
        
        assert collector._connected is False
        mock_conn.close.assert_called_once()
    
    def test_is_connected(self, mock_collector):
        """Test is_connected method."""
        collector, _, _ = mock_collector
        
        assert collector.is_connected() is True
        
        collector._connected = False
        assert collector.is_connected() is False
    
    def test_ensure_connected_raises_when_not_connected(self, db_config):
        """Test _ensure_connected raises when not connected."""
        collector = FeedbackCollector(db_config)
        
        with pytest.raises(FeedbackConnectionError) as exc:
            collector._ensure_connected()
        
        assert "Not connected" in str(exc.value)
    
    def test_context_manager(self, db_config, mock_psycopg2_fixture):
        """Test context manager usage."""
        mock_pg, mock_conn, _ = mock_psycopg2_fixture
        
        with FeedbackCollector(db_config) as collector:
            assert collector._connected is True
        
        mock_conn.close.assert_called()
    
    def test_repr(self, db_config):
        """Test string representation."""
        collector = FeedbackCollector(db_config)
        repr_str = repr(collector)
        
        assert "FeedbackCollector" in repr_str
        assert "connected=False" in repr_str


# ═══════════════════════════════════════════════════════════════════════════════
# FEEDBACK COLLECTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFeedbackCollection:
    """Tests for feedback collection operations."""
    
    def test_collect_feedback(self, mock_collector, sample_feedback):
        """Test collecting single feedback."""
        collector, mock_conn, mock_cursor = mock_collector
        mock_cursor.fetchone.return_value = [42]  # Returned ID
        
        feedback_id = collector.collect_feedback(sample_feedback)
        
        assert feedback_id == 42
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
    
    def test_collect_feedback_batch(self, mock_collector, sample_feedback, sample_modify_feedback):
        """Test collecting batch feedback."""
        collector, mock_conn, mock_cursor = mock_collector
        
        # Mock execute_values to return IDs
        with patch("phoenix_guardian.learning.feedback_collector.execute_values") as mock_exec:
            mock_exec.return_value = [[1], [2]]
            
            feedback_ids = collector.collect_feedback_batch(
                [sample_feedback, sample_modify_feedback]
            )
            
            assert len(feedback_ids) == 2
            mock_exec.assert_called_once()
    
    def test_collect_feedback_empty_batch(self, mock_collector):
        """Test collecting empty batch returns empty list."""
        collector, _, _ = mock_collector
        
        feedback_ids = collector.collect_feedback_batch([])
        
        assert feedback_ids == []


# ═══════════════════════════════════════════════════════════════════════════════
# FEEDBACK RETRIEVAL TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFeedbackRetrieval:
    """Tests for feedback retrieval operations."""
    
    def test_get_feedback(self, mock_collector, sample_session_id):
        """Test retrieving single feedback."""
        collector, _, mock_cursor = mock_collector
        
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "agent_name": "test_agent",
            "user_id": 123,
            "session_id": str(sample_session_id),
            "suggestion": "Test",
            "user_feedback": "accept",
            "modified_output": None,
            "confidence_score": 0.9,
            "context": None,
            "timestamp": datetime.utcnow(),
            "model_version": "v1.0",
            "feedback_quality_score": None,
            "tags": None,
        }
        
        feedback = collector.get_feedback(1)
        
        assert feedback is not None
        assert feedback.agent_name == "test_agent"
        assert feedback.user_id == 123
    
    def test_get_feedback_not_found(self, mock_collector):
        """Test retrieving non-existent feedback."""
        collector, _, mock_cursor = mock_collector
        mock_cursor.fetchone.return_value = None
        
        feedback = collector.get_feedback(999)
        
        assert feedback is None
    
    def test_get_training_data(self, mock_collector, sample_session_id):
        """Test retrieving training data."""
        collector, _, mock_cursor = mock_collector
        
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "agent_name": "safety_agent",
                "user_id": 123,
                "session_id": str(sample_session_id),
                "suggestion": "Test 1",
                "user_feedback": "accept",
                "modified_output": None,
                "confidence_score": 0.9,
                "context": None,
                "timestamp": datetime.utcnow(),
                "model_version": None,
                "feedback_quality_score": None,
                "tags": None,
            },
            {
                "id": 2,
                "agent_name": "safety_agent",
                "user_id": 456,
                "session_id": str(sample_session_id),
                "suggestion": "Test 2",
                "user_feedback": "modify",
                "modified_output": "Modified",
                "confidence_score": 0.8,
                "context": None,
                "timestamp": datetime.utcnow(),
                "model_version": None,
                "feedback_quality_score": None,
                "tags": None,
            },
        ]
        
        batch = collector.get_training_data(agent_name="safety_agent")
        
        assert batch.size == 2
        assert len(batch.get_training_pairs()) == 2
    
    def test_get_feedback_by_session(self, mock_collector, sample_session_id):
        """Test retrieving feedback by session."""
        collector, _, mock_cursor = mock_collector
        
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "agent_name": "test_agent",
                "user_id": 123,
                "session_id": str(sample_session_id),
                "suggestion": "Test",
                "user_feedback": "accept",
                "modified_output": None,
                "confidence_score": 0.9,
                "context": None,
                "timestamp": datetime.utcnow(),
                "model_version": None,
                "feedback_quality_score": None,
                "tags": None,
            },
        ]
        
        feedback_list = collector.get_feedback_by_session(sample_session_id)
        
        assert len(feedback_list) == 1
    
    def test_get_feedback_by_user(self, mock_collector, sample_session_id):
        """Test retrieving feedback by user."""
        collector, _, mock_cursor = mock_collector
        
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "agent_name": "test_agent",
                "user_id": 123,
                "session_id": str(sample_session_id),
                "suggestion": "Test",
                "user_feedback": "accept",
                "modified_output": None,
                "confidence_score": 0.9,
                "context": None,
                "timestamp": datetime.utcnow(),
                "model_version": None,
                "feedback_quality_score": None,
                "tags": None,
            },
        ]
        
        feedback_list = collector.get_feedback_by_user(123)
        
        assert len(feedback_list) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING MANAGEMENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTrainingManagement:
    """Tests for training management operations."""
    
    def test_mark_as_used_for_training(self, mock_collector):
        """Test marking feedback as used for training."""
        collector, mock_conn, mock_cursor = mock_collector
        mock_cursor.rowcount = 5
        
        updated = collector.mark_as_used_for_training([1, 2, 3, 4, 5])
        
        assert updated == 5
        mock_conn.commit.assert_called()
    
    def test_mark_as_used_empty_list(self, mock_collector):
        """Test marking empty list returns 0."""
        collector, _, _ = mock_collector
        
        updated = collector.mark_as_used_for_training([])
        
        assert updated == 0
    
    def test_reset_training_status_specific(self, mock_collector):
        """Test resetting specific feedback training status."""
        collector, mock_conn, mock_cursor = mock_collector
        mock_cursor.rowcount = 3
        
        updated = collector.reset_training_status([1, 2, 3])
        
        assert updated == 3
        mock_conn.commit.assert_called()
    
    def test_reset_training_status_all(self, mock_collector):
        """Test resetting all feedback training status."""
        collector, mock_conn, mock_cursor = mock_collector
        mock_cursor.rowcount = 100
        
        updated = collector.reset_training_status()
        
        assert updated == 100


# ═══════════════════════════════════════════════════════════════════════════════
# STATISTICS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatistics:
    """Tests for statistics operations."""
    
    def test_get_feedback_stats(self, mock_collector):
        """Test getting feedback statistics."""
        collector, _, mock_cursor = mock_collector
        
        mock_cursor.fetchone.return_value = {
            "total_feedback": 100,
            "accepted": 70,
            "rejected": 20,
            "modified": 10,
            "avg_confidence": 0.85,
            "used_for_training": 50,
        }
        
        # Mock per-agent stats
        collector._get_per_agent_stats = Mock(return_value={
            "safety_agent": {"total": 50, "accepted": 40, "rejected": 5, "modified": 5},
            "scribe_agent": {"total": 50, "accepted": 30, "rejected": 15, "modified": 5},
        })
        
        stats = collector.get_feedback_stats()
        
        assert stats.total_feedback == 100
        assert stats.accepted == 70
        assert stats.acceptance_rate == 70.0
        assert stats.avg_confidence == 0.85
    
    def test_get_feedback_stats_with_filters(self, mock_collector):
        """Test getting stats with time filters."""
        collector, _, mock_cursor = mock_collector
        
        mock_cursor.fetchone.return_value = {
            "total_feedback": 50,
            "accepted": 30,
            "rejected": 15,
            "modified": 5,
            "avg_confidence": 0.88,
            "used_for_training": 20,
        }
        
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31)
        
        stats = collector.get_feedback_stats(
            agent_name="safety_agent",
            start_date=start,
            end_date=end,
        )
        
        assert stats.time_period is not None
        assert stats.time_period["start"] == start.isoformat()
    
    def test_get_agent_performance(self, mock_collector):
        """Test getting agent performance metrics."""
        collector, _, mock_cursor = mock_collector
        
        # First query: overall stats
        # Second query: daily trend
        mock_cursor.fetchone.return_value = {
            "total": 100,
            "accepted": 80,
            "avg_confidence": 0.9,
            "avg_quality": 0.85,
        }
        mock_cursor.fetchall.return_value = [
            {"date": datetime(2026, 1, 30).date(), "total": 10, "accepted": 8},
            {"date": datetime(2026, 1, 31).date(), "total": 15, "accepted": 12},
        ]
        
        performance = collector.get_agent_performance("safety_agent", days=30)
        
        assert performance["agent_name"] == "safety_agent"
        assert performance["acceptance_rate"] == 80.0
        assert len(performance["daily_trend"]) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestUtilities:
    """Tests for utility operations."""
    
    def test_delete_feedback(self, mock_collector):
        """Test deleting feedback."""
        collector, mock_conn, mock_cursor = mock_collector
        mock_cursor.rowcount = 1
        
        deleted = collector.delete_feedback(42)
        
        assert deleted is True
        mock_conn.commit.assert_called()
    
    def test_delete_feedback_not_found(self, mock_collector):
        """Test deleting non-existent feedback."""
        collector, mock_conn, mock_cursor = mock_collector
        mock_cursor.rowcount = 0
        
        deleted = collector.delete_feedback(999)
        
        assert deleted is False
    
    def test_cleanup_old_feedback(self, mock_collector):
        """Test cleaning up old feedback."""
        collector, mock_conn, mock_cursor = mock_collector
        mock_cursor.rowcount = 50
        
        deleted = collector.cleanup_old_feedback(days_to_keep=365)
        
        assert deleted == 50
        mock_conn.commit.assert_called()


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestExceptions:
    """Tests for exception handling."""
    
    def test_feedback_error(self):
        """Test FeedbackError."""
        error = FeedbackError("Test error")
        assert str(error) == "Test error"
        assert error.details == {}
    
    def test_feedback_error_with_details(self):
        """Test FeedbackError with details."""
        error = FeedbackError("Test error", {"key": "value"})
        assert "Test error" in str(error)
        assert "key" in str(error)
    
    def test_feedback_database_error(self):
        """Test FeedbackDatabaseError."""
        error = FeedbackDatabaseError("DB error")
        assert isinstance(error, FeedbackError)
    
    def test_feedback_validation_error(self):
        """Test FeedbackValidationError."""
        error = FeedbackValidationError("Validation failed")
        assert isinstance(error, FeedbackError)
    
    def test_feedback_connection_error(self):
        """Test FeedbackConnectionError."""
        error = FeedbackConnectionError("Connection failed")
        assert isinstance(error, FeedbackError)


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestConstants:
    """Tests for module constants."""
    
    def test_valid_feedback_types(self):
        """Test VALID_FEEDBACK_TYPES constant."""
        assert "accept" in VALID_FEEDBACK_TYPES
        assert "reject" in VALID_FEEDBACK_TYPES
        assert "modify" in VALID_FEEDBACK_TYPES
        assert len(VALID_FEEDBACK_TYPES) == 3
    
    def test_schema_version(self):
        """Test FEEDBACK_SCHEMA_VERSION constant."""
        assert FEEDBACK_SCHEMA_VERSION == "1.0.0"
    
    def test_create_table_sql(self):
        """Test CREATE_FEEDBACK_TABLE_SQL contains required elements."""
        assert "CREATE TABLE" in CREATE_FEEDBACK_TABLE_SQL
        assert "agent_feedback" in CREATE_FEEDBACK_TABLE_SQL
        assert "agent_name" in CREATE_FEEDBACK_TABLE_SQL
        assert "user_feedback" in CREATE_FEEDBACK_TABLE_SQL
        assert "CREATE INDEX" in CREATE_FEEDBACK_TABLE_SQL
