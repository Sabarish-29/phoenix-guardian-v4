"""
Feedback Collection System for Phoenix Guardian Bidirectional Learning.

This module provides a comprehensive system for collecting, storing, and
retrieving physician feedback on agent suggestions. Feedback is stored in
PostgreSQL and used for continuous model improvement.

Features:
- Structured feedback storage with full context preservation
- Support for accept/reject/modify feedback types
- Training data retrieval with filtering
- Comprehensive statistics and analytics
- Connection pooling for production use
- Async support for high-throughput scenarios

Database Schema:
    CREATE TABLE agent_feedback (
        id SERIAL PRIMARY KEY,
        agent_name VARCHAR(50) NOT NULL,
        user_id INTEGER NOT NULL,
        session_id UUID NOT NULL,
        suggestion TEXT NOT NULL,
        user_feedback VARCHAR(20) NOT NULL,
        modified_output TEXT,
        confidence_score FLOAT,
        context JSONB,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_used_for_training BOOLEAN DEFAULT FALSE,
        model_version VARCHAR(50),
        feedback_quality_score FLOAT,
        tags VARCHAR(255)[]
    );

Usage:
    from phoenix_guardian.learning import FeedbackCollector, Feedback
    
    config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'phoenix_guardian',
        'user': 'postgres',
        'password': 'password'
    }
    
    with FeedbackCollector(config) as collector:
        feedback = Feedback(
            agent_name="safety_agent",
            user_id=123,
            session_id=uuid.uuid4(),
            suggestion="Drug interaction detected",
            user_feedback="accept",
            confidence_score=0.95
        )
        feedback_id = collector.collect_feedback(feedback)
"""

import json
import logging
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, execute_values
    from psycopg2.pool import ThreadedConnectionPool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
    RealDictCursor = None
    execute_values = None
    ThreadedConnectionPool = None


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

FEEDBACK_SCHEMA_VERSION = "1.0.0"

VALID_FEEDBACK_TYPES = frozenset({"accept", "reject", "modify"})

# SQL for creating the feedback table
CREATE_FEEDBACK_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_feedback (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(50) NOT NULL,
    user_id INTEGER NOT NULL,
    session_id UUID NOT NULL,
    suggestion TEXT NOT NULL,
    user_feedback VARCHAR(20) NOT NULL CHECK (user_feedback IN ('accept', 'reject', 'modify')),
    modified_output TEXT,
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    context JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_used_for_training BOOLEAN DEFAULT FALSE,
    model_version VARCHAR(50),
    feedback_quality_score FLOAT CHECK (feedback_quality_score >= 0 AND feedback_quality_score <= 1),
    tags VARCHAR(255)[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_feedback_timestamp ON agent_feedback(timestamp);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_agent ON agent_feedback(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_user_feedback ON agent_feedback(user_feedback);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_user_id ON agent_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_session_id ON agent_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_training ON agent_feedback(is_used_for_training);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_context ON agent_feedback USING GIN (context);
"""


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════


class FeedbackError(Exception):
    """Base exception for feedback-related errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class FeedbackDatabaseError(FeedbackError):
    """Raised when database operations fail."""
    pass


class FeedbackValidationError(FeedbackError):
    """Raised when feedback validation fails."""
    pass


class FeedbackConnectionError(FeedbackError):
    """Raised when database connection fails."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════


class FeedbackType(str, Enum):
    """Types of user feedback on agent suggestions."""
    ACCEPT = "accept"
    REJECT = "reject"
    MODIFY = "modify"
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if value is a valid feedback type."""
        return value in {item.value for item in cls}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class Feedback:
    """
    User feedback on an agent suggestion.
    
    Attributes:
        agent_name: Name of the agent that made the suggestion
        user_id: ID of the user providing feedback
        session_id: Session identifier for grouping related feedback
        suggestion: The original agent suggestion
        user_feedback: Type of feedback ('accept', 'reject', 'modify')
        modified_output: User's corrected version (for 'modify' feedback)
        confidence_score: Agent's confidence in the suggestion (0-1)
        context: Additional context for the suggestion (JSON serializable)
        timestamp: When the feedback was provided
        model_version: Version of the model that generated the suggestion
        feedback_quality_score: Quality score of the feedback itself (0-1)
        tags: Optional tags for categorizing feedback
        id: Database ID (set after storage)
    """
    agent_name: str
    user_id: int
    session_id: Union[uuid.UUID, str]
    suggestion: str
    user_feedback: str
    modified_output: Optional[str] = None
    confidence_score: Optional[float] = None
    context: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    model_version: Optional[str] = None
    feedback_quality_score: Optional[float] = None
    tags: Optional[List[str]] = None
    id: Optional[int] = None
    
    def __post_init__(self):
        """Validate feedback after initialization."""
        # Convert string UUID to UUID object if needed
        if isinstance(self.session_id, str):
            self.session_id = uuid.UUID(self.session_id)
        
        # Validate feedback type
        if not FeedbackType.is_valid(self.user_feedback):
            raise FeedbackValidationError(
                f"Invalid feedback type: {self.user_feedback}",
                {"valid_types": list(VALID_FEEDBACK_TYPES)}
            )
        
        # Validate confidence score range
        if self.confidence_score is not None:
            if not 0 <= self.confidence_score <= 1:
                raise FeedbackValidationError(
                    f"Confidence score must be between 0 and 1: {self.confidence_score}"
                )
        
        # Validate feedback quality score range
        if self.feedback_quality_score is not None:
            if not 0 <= self.feedback_quality_score <= 1:
                raise FeedbackValidationError(
                    f"Feedback quality score must be between 0 and 1: {self.feedback_quality_score}"
                )
        
        # Require modified_output for 'modify' feedback type
        if self.user_feedback == FeedbackType.MODIFY.value and not self.modified_output:
            raise FeedbackValidationError(
                "modified_output is required when user_feedback is 'modify'"
            )
        
        # Set timestamp if not provided
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert feedback to dictionary."""
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "user_id": self.user_id,
            "session_id": str(self.session_id),
            "suggestion": self.suggestion,
            "user_feedback": self.user_feedback,
            "modified_output": self.modified_output,
            "confidence_score": self.confidence_score,
            "context": self.context,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "model_version": self.model_version,
            "feedback_quality_score": self.feedback_quality_score,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Feedback":
        """Create Feedback from dictionary."""
        # Handle timestamp conversion
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        
        return cls(
            id=data.get("id"),
            agent_name=data["agent_name"],
            user_id=data["user_id"],
            session_id=data["session_id"],
            suggestion=data["suggestion"],
            user_feedback=data["user_feedback"],
            modified_output=data.get("modified_output"),
            confidence_score=data.get("confidence_score"),
            context=data.get("context"),
            timestamp=timestamp,
            model_version=data.get("model_version"),
            feedback_quality_score=data.get("feedback_quality_score"),
            tags=data.get("tags"),
        )


@dataclass
class FeedbackStats:
    """
    Statistics about collected feedback.
    
    Attributes:
        total_feedback: Total number of feedback records
        accepted: Number of accepted suggestions
        rejected: Number of rejected suggestions
        modified: Number of modified suggestions
        avg_confidence: Average confidence score
        acceptance_rate: Percentage of accepted feedback
        agents: Per-agent statistics
        time_period: Time period for the statistics
    """
    total_feedback: int
    accepted: int
    rejected: int
    modified: int
    avg_confidence: Optional[float]
    acceptance_rate: float = 0.0
    agents: Optional[Dict[str, Dict[str, int]]] = None
    time_period: Optional[Dict[str, str]] = None
    used_for_training: int = 0
    pending_training: int = 0
    
    def __post_init__(self):
        """Calculate derived statistics."""
        if self.total_feedback > 0:
            self.acceptance_rate = (self.accepted / self.total_feedback) * 100
            self.pending_training = self.total_feedback - self.used_for_training
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_feedback": self.total_feedback,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "modified": self.modified,
            "avg_confidence": self.avg_confidence,
            "acceptance_rate": round(self.acceptance_rate, 2),
            "agents": self.agents,
            "time_period": self.time_period,
            "used_for_training": self.used_for_training,
            "pending_training": self.pending_training,
        }


@dataclass
class TrainingBatch:
    """
    A batch of feedback for model training.
    
    Attributes:
        feedback_ids: IDs of feedback in this batch
        feedback_items: List of Feedback objects
        batch_id: Unique identifier for this batch
        created_at: When the batch was created
        agent_name: Agent this batch is for (if filtered)
    """
    feedback_ids: List[int]
    feedback_items: List[Feedback]
    batch_id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
    agent_name: Optional[str] = None
    
    @property
    def size(self) -> int:
        """Get batch size."""
        return len(self.feedback_items)
    
    def get_training_pairs(self) -> List[Tuple[str, str]]:
        """
        Get input-output pairs for training.
        
        Returns:
            List of (input, target) tuples where:
            - For 'accept': (suggestion, suggestion)
            - For 'modify': (suggestion, modified_output)
            - 'reject' items are filtered out
        """
        pairs = []
        for fb in self.feedback_items:
            if fb.user_feedback == FeedbackType.ACCEPT.value:
                pairs.append((fb.suggestion, fb.suggestion))
            elif fb.user_feedback == FeedbackType.MODIFY.value and fb.modified_output:
                pairs.append((fb.suggestion, fb.modified_output))
        return pairs


# ═══════════════════════════════════════════════════════════════════════════════
# FEEDBACK COLLECTOR
# ═══════════════════════════════════════════════════════════════════════════════


class FeedbackCollector:
    """
    Collect and store physician feedback for model improvement.
    
    Provides a complete feedback collection system with:
    - Structured feedback storage in PostgreSQL
    - Connection pooling for production use
    - Batch operations for efficient training data retrieval
    - Comprehensive statistics and analytics
    
    Example:
        >>> config = {'host': 'localhost', 'database': 'phoenix'}
        >>> with FeedbackCollector(config) as collector:
        ...     feedback = Feedback(
        ...         agent_name="safety_agent",
        ...         user_id=123,
        ...         session_id=uuid.uuid4(),
        ...         suggestion="Check interaction",
        ...         user_feedback="accept"
        ...     )
        ...     feedback_id = collector.collect_feedback(feedback)
    """
    
    def __init__(
        self,
        db_config: Dict[str, Any],
        use_pool: bool = False,
        pool_min_conn: int = 1,
        pool_max_conn: int = 10,
    ):
        """
        Initialize feedback collector.
        
        Args:
            db_config: PostgreSQL connection configuration
            use_pool: Whether to use connection pooling
            pool_min_conn: Minimum pool connections
            pool_max_conn: Maximum pool connections
            
        Raises:
            FeedbackError: If psycopg2 is not installed
        """
        if not PSYCOPG2_AVAILABLE:
            raise FeedbackError(
                "psycopg2 is required for FeedbackCollector. "
                "Install with: pip install psycopg2-binary"
            )
        
        self.db_config = db_config
        self.use_pool = use_pool
        self.pool_min_conn = pool_min_conn
        self.pool_max_conn = pool_max_conn
        
        self._conn: Optional[Any] = None
        self._pool: Optional[Any] = None
        self._connected: bool = False
        
        logger.info(f"Initialized FeedbackCollector (pool={use_pool})")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONNECTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def connect(self) -> "FeedbackCollector":
        """
        Establish database connection.
        
        Returns:
            Self for method chaining
            
        Raises:
            FeedbackConnectionError: If connection fails
        """
        if self._connected:
            return self
        
        try:
            if self.use_pool:
                self._pool = ThreadedConnectionPool(
                    self.pool_min_conn,
                    self.pool_max_conn,
                    **self.db_config
                )
                logger.info("Created connection pool")
            else:
                self._conn = psycopg2.connect(**self.db_config)
                logger.info("Connected to PostgreSQL")
            
            self._connected = True
            return self
            
        except psycopg2.Error as e:
            raise FeedbackConnectionError(
                f"Failed to connect to database: {e}",
                {"config": {k: v for k, v in self.db_config.items() if k != "password"}}
            )
    
    def close(self) -> None:
        """Close database connection(s)."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Closed PostgreSQL connection")
        
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("Closed connection pool")
        
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if connected to database."""
        return self._connected
    
    @contextmanager
    def get_connection(self):
        """
        Get a database connection (from pool or direct).
        
        Yields:
            Database connection
        """
        if not self._connected:
            raise FeedbackConnectionError("Not connected. Call connect() first.")
        
        if self.use_pool:
            conn = self._pool.getconn()
            try:
                yield conn
            finally:
                self._pool.putconn(conn)
        else:
            yield self._conn
    
    def _ensure_connected(self) -> None:
        """Ensure collector is connected."""
        if not self._connected:
            raise FeedbackConnectionError("Not connected. Call connect() first.")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SCHEMA MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def create_tables(self) -> None:
        """
        Create feedback tables if they don't exist.
        
        Raises:
            FeedbackDatabaseError: If table creation fails
        """
        self._ensure_connected()
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(CREATE_FEEDBACK_TABLE_SQL)
                    conn.commit()
                    logger.info("Created feedback tables")
        except psycopg2.Error as e:
            raise FeedbackDatabaseError(f"Failed to create tables: {e}")
    
    def drop_tables(self) -> None:
        """Drop feedback tables (use with caution!)."""
        self._ensure_connected()
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS agent_feedback CASCADE")
                conn.commit()
                logger.warning("Dropped feedback tables")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FEEDBACK COLLECTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def collect_feedback(self, feedback: Feedback) -> int:
        """
        Store feedback in database.
        
        Args:
            feedback: Feedback object to store
            
        Returns:
            Database ID of the stored feedback
            
        Raises:
            FeedbackDatabaseError: If storage fails
            FeedbackValidationError: If feedback is invalid
        """
        self._ensure_connected()
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO agent_feedback 
                        (agent_name, user_id, session_id, suggestion, 
                         user_feedback, modified_output, confidence_score, 
                         context, model_version, feedback_quality_score, tags)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        feedback.agent_name,
                        feedback.user_id,
                        str(feedback.session_id),
                        feedback.suggestion,
                        feedback.user_feedback,
                        feedback.modified_output,
                        feedback.confidence_score,
                        json.dumps(feedback.context) if feedback.context else None,
                        feedback.model_version,
                        feedback.feedback_quality_score,
                        feedback.tags,
                    ))
                    
                    feedback_id = cur.fetchone()[0]
                    conn.commit()
                    
                    logger.info(f"Stored feedback {feedback_id} for {feedback.agent_name}")
                    return feedback_id
                    
        except psycopg2.Error as e:
            raise FeedbackDatabaseError(f"Failed to store feedback: {e}")
    
    def collect_feedback_batch(self, feedback_list: List[Feedback]) -> List[int]:
        """
        Store multiple feedback records efficiently.
        
        Args:
            feedback_list: List of Feedback objects
            
        Returns:
            List of database IDs
        """
        self._ensure_connected()
        
        if not feedback_list:
            return []
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Prepare data for batch insert
                    values = [
                        (
                            fb.agent_name,
                            fb.user_id,
                            str(fb.session_id),
                            fb.suggestion,
                            fb.user_feedback,
                            fb.modified_output,
                            fb.confidence_score,
                            json.dumps(fb.context) if fb.context else None,
                            fb.model_version,
                            fb.feedback_quality_score,
                            fb.tags,
                        )
                        for fb in feedback_list
                    ]
                    
                    # Use execute_values for efficient batch insert
                    result = execute_values(
                        cur,
                        """
                        INSERT INTO agent_feedback 
                        (agent_name, user_id, session_id, suggestion, 
                         user_feedback, modified_output, confidence_score, 
                         context, model_version, feedback_quality_score, tags)
                        VALUES %s
                        RETURNING id
                        """,
                        values,
                        fetch=True
                    )
                    
                    feedback_ids = [row[0] for row in result]
                    conn.commit()
                    
                    logger.info(f"Stored {len(feedback_ids)} feedback records in batch")
                    return feedback_ids
                    
        except psycopg2.Error as e:
            raise FeedbackDatabaseError(f"Failed to store feedback batch: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FEEDBACK RETRIEVAL
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_feedback(self, feedback_id: int) -> Optional[Feedback]:
        """
        Get a single feedback record by ID.
        
        Args:
            feedback_id: Database ID of the feedback
            
        Returns:
            Feedback object or None if not found
        """
        self._ensure_connected()
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM agent_feedback WHERE id = %s",
                    (feedback_id,)
                )
                row = cur.fetchone()
                
                if row:
                    return self._row_to_feedback(row)
                return None
    
    def get_training_data(
        self,
        agent_name: Optional[str] = None,
        min_confidence: float = 0.0,
        feedback_types: Optional[List[str]] = None,
        exclude_used: bool = True,
        limit: int = 1000,
        offset: int = 0,
    ) -> TrainingBatch:
        """
        Retrieve feedback for model training.
        
        Args:
            agent_name: Filter by agent (None = all agents)
            min_confidence: Minimum confidence score
            feedback_types: List of feedback types to include
            exclude_used: Exclude already-used-for-training records
            limit: Maximum records to return
            offset: Offset for pagination
            
        Returns:
            TrainingBatch containing feedback records
        """
        self._ensure_connected()
        
        query = "SELECT * FROM agent_feedback WHERE 1=1"
        params: List[Any] = []
        
        if exclude_used:
            query += " AND is_used_for_training = FALSE"
        
        if min_confidence > 0:
            query += " AND confidence_score >= %s"
            params.append(min_confidence)
        
        if agent_name:
            query += " AND agent_name = %s"
            params.append(agent_name)
        
        if feedback_types:
            query += " AND user_feedback = ANY(%s)"
            params.append(feedback_types)
        
        query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        
        feedback_items = [self._row_to_feedback(row) for row in rows]
        feedback_ids = [fb.id for fb in feedback_items if fb.id]
        
        return TrainingBatch(
            feedback_ids=feedback_ids,
            feedback_items=feedback_items,
            agent_name=agent_name,
        )
    
    def get_feedback_by_session(self, session_id: uuid.UUID) -> List[Feedback]:
        """
        Get all feedback for a session.
        
        Args:
            session_id: Session UUID
            
        Returns:
            List of Feedback objects
        """
        self._ensure_connected()
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM agent_feedback WHERE session_id = %s ORDER BY timestamp",
                    (str(session_id),)
                )
                rows = cur.fetchall()
        
        return [self._row_to_feedback(row) for row in rows]
    
    def get_feedback_by_user(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Feedback]:
        """
        Get feedback from a specific user.
        
        Args:
            user_id: User ID
            limit: Maximum records
            offset: Offset for pagination
            
        Returns:
            List of Feedback objects
        """
        self._ensure_connected()
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM agent_feedback 
                    WHERE user_id = %s 
                    ORDER BY timestamp DESC
                    LIMIT %s OFFSET %s
                    """,
                    (user_id, limit, offset)
                )
                rows = cur.fetchall()
        
        return [self._row_to_feedback(row) for row in rows]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRAINING MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def mark_as_used_for_training(self, feedback_ids: List[int]) -> int:
        """
        Mark feedback records as used for training.
        
        Args:
            feedback_ids: List of feedback IDs
            
        Returns:
            Number of records updated
        """
        self._ensure_connected()
        
        if not feedback_ids:
            return 0
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE agent_feedback
                    SET is_used_for_training = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ANY(%s)
                    """,
                    (feedback_ids,)
                )
                updated = cur.rowcount
                conn.commit()
        
        logger.info(f"Marked {updated} feedback records as used for training")
        return updated
    
    def reset_training_status(self, feedback_ids: Optional[List[int]] = None) -> int:
        """
        Reset training status for feedback records.
        
        Args:
            feedback_ids: Specific IDs to reset, or None for all
            
        Returns:
            Number of records reset
        """
        self._ensure_connected()
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                if feedback_ids:
                    cur.execute(
                        """
                        UPDATE agent_feedback
                        SET is_used_for_training = FALSE,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ANY(%s)
                        """,
                        (feedback_ids,)
                    )
                else:
                    cur.execute(
                        """
                        UPDATE agent_feedback
                        SET is_used_for_training = FALSE,
                            updated_at = CURRENT_TIMESTAMP
                        """
                    )
                
                updated = cur.rowcount
                conn.commit()
        
        logger.info(f"Reset training status for {updated} records")
        return updated
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_feedback_stats(
        self,
        agent_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> FeedbackStats:
        """
        Get feedback statistics.
        
        Args:
            agent_name: Filter by agent (None = all)
            start_date: Start of time period
            end_date: End of time period
            
        Returns:
            FeedbackStats object
        """
        self._ensure_connected()
        
        query = """
            SELECT 
                COUNT(*) as total_feedback,
                COUNT(CASE WHEN user_feedback = 'accept' THEN 1 END) as accepted,
                COUNT(CASE WHEN user_feedback = 'reject' THEN 1 END) as rejected,
                COUNT(CASE WHEN user_feedback = 'modify' THEN 1 END) as modified,
                AVG(confidence_score) as avg_confidence,
                COUNT(CASE WHEN is_used_for_training THEN 1 END) as used_for_training
            FROM agent_feedback
            WHERE 1=1
        """
        params: List[Any] = []
        
        if agent_name:
            query += " AND agent_name = %s"
            params.append(agent_name)
        
        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                row = cur.fetchone()
        
        # Get per-agent stats if not filtering by agent
        agents = None
        if not agent_name:
            agents = self._get_per_agent_stats(start_date, end_date)
        
        time_period = None
        if start_date or end_date:
            time_period = {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            }
        
        return FeedbackStats(
            total_feedback=row["total_feedback"] or 0,
            accepted=row["accepted"] or 0,
            rejected=row["rejected"] or 0,
            modified=row["modified"] or 0,
            avg_confidence=float(row["avg_confidence"]) if row["avg_confidence"] else None,
            agents=agents,
            time_period=time_period,
            used_for_training=row["used_for_training"] or 0,
        )
    
    def _get_per_agent_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Dict[str, int]]:
        """Get statistics per agent."""
        query = """
            SELECT 
                agent_name,
                COUNT(*) as total,
                COUNT(CASE WHEN user_feedback = 'accept' THEN 1 END) as accepted,
                COUNT(CASE WHEN user_feedback = 'reject' THEN 1 END) as rejected,
                COUNT(CASE WHEN user_feedback = 'modify' THEN 1 END) as modified
            FROM agent_feedback
            WHERE 1=1
        """
        params: List[Any] = []
        
        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        
        query += " GROUP BY agent_name"
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        
        return {
            row["agent_name"]: {
                "total": row["total"],
                "accepted": row["accepted"],
                "rejected": row["rejected"],
                "modified": row["modified"],
            }
            for row in rows
        }
    
    def get_agent_performance(self, agent_name: str, days: int = 30) -> Dict[str, Any]:
        """
        Get performance metrics for a specific agent.
        
        Args:
            agent_name: Name of the agent
            days: Number of days to analyze
            
        Returns:
            Performance metrics dictionary
        """
        self._ensure_connected()
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Overall stats
                cur.execute(
                    """
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN user_feedback = 'accept' THEN 1 END) as accepted,
                        AVG(confidence_score) as avg_confidence,
                        AVG(feedback_quality_score) as avg_quality
                    FROM agent_feedback
                    WHERE agent_name = %s AND timestamp >= %s
                    """,
                    (agent_name, start_date)
                )
                stats = cur.fetchone()
                
                # Daily trend
                cur.execute(
                    """
                    SELECT 
                        DATE(timestamp) as date,
                        COUNT(*) as total,
                        COUNT(CASE WHEN user_feedback = 'accept' THEN 1 END) as accepted
                    FROM agent_feedback
                    WHERE agent_name = %s AND timestamp >= %s
                    GROUP BY DATE(timestamp)
                    ORDER BY date
                    """,
                    (agent_name, start_date)
                )
                daily = cur.fetchall()
        
        acceptance_rate = 0.0
        if stats["total"] and stats["total"] > 0:
            acceptance_rate = (stats["accepted"] / stats["total"]) * 100
        
        return {
            "agent_name": agent_name,
            "period_days": days,
            "total_feedback": stats["total"] or 0,
            "acceptance_rate": round(acceptance_rate, 2),
            "avg_confidence": float(stats["avg_confidence"]) if stats["avg_confidence"] else None,
            "avg_quality": float(stats["avg_quality"]) if stats["avg_quality"] else None,
            "daily_trend": [
                {
                    "date": str(row["date"]),
                    "total": row["total"],
                    "accepted": row["accepted"],
                }
                for row in daily
            ],
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _row_to_feedback(self, row: Dict[str, Any]) -> Feedback:
        """Convert database row to Feedback object."""
        return Feedback(
            id=row["id"],
            agent_name=row["agent_name"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            suggestion=row["suggestion"],
            user_feedback=row["user_feedback"],
            modified_output=row.get("modified_output"),
            confidence_score=float(row["confidence_score"]) if row.get("confidence_score") else None,
            context=row.get("context"),
            timestamp=row.get("timestamp"),
            model_version=row.get("model_version"),
            feedback_quality_score=float(row["feedback_quality_score"]) if row.get("feedback_quality_score") else None,
            tags=row.get("tags"),
        )
    
    def delete_feedback(self, feedback_id: int) -> bool:
        """
        Delete a feedback record.
        
        Args:
            feedback_id: ID of feedback to delete
            
        Returns:
            True if deleted, False if not found
        """
        self._ensure_connected()
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM agent_feedback WHERE id = %s",
                    (feedback_id,)
                )
                deleted = cur.rowcount > 0
                conn.commit()
        
        if deleted:
            logger.info(f"Deleted feedback {feedback_id}")
        
        return deleted
    
    def cleanup_old_feedback(self, days_to_keep: int = 365) -> int:
        """
        Delete feedback older than specified days.
        
        Args:
            days_to_keep: Number of days to retain
            
        Returns:
            Number of records deleted
        """
        self._ensure_connected()
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM agent_feedback 
                    WHERE timestamp < %s AND is_used_for_training = TRUE
                    """,
                    (cutoff_date,)
                )
                deleted = cur.rowcount
                conn.commit()
        
        logger.info(f"Cleaned up {deleted} old feedback records")
        return deleted
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONTEXT MANAGER
    # ═══════════════════════════════════════════════════════════════════════════
    
    def __enter__(self) -> "FeedbackCollector":
        """Enter context manager."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        self.close()
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"FeedbackCollector("
            f"connected={self._connected}, "
            f"pool={self.use_pool})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Core Classes
    "FeedbackCollector",
    "Feedback",
    "FeedbackType",
    "FeedbackStats",
    "TrainingBatch",
    
    # Exceptions
    "FeedbackError",
    "FeedbackDatabaseError",
    "FeedbackValidationError",
    "FeedbackConnectionError",
    
    # Constants
    "VALID_FEEDBACK_TYPES",
    "FEEDBACK_SCHEMA_VERSION",
    "CREATE_FEEDBACK_TABLE_SQL",
]
