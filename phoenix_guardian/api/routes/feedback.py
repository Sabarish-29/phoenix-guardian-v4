"""
FastAPI Routes for Feedback Collection.

Provides REST API endpoints for:
- Submitting physician feedback on agent suggestions
- Retrieving feedback statistics
- Managing training data
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, validator

from phoenix_guardian.learning.feedback_collector import (
    FeedbackCollector,
    Feedback,
    FeedbackStats,
    FeedbackType,
    FeedbackError,
    FeedbackValidationError,
    FeedbackConnectionError,
    VALID_FEEDBACK_TYPES,
)


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/feedback", tags=["feedback"])


# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class FeedbackRequest(BaseModel):
    """Request model for submitting feedback."""
    agent_name: str = Field(..., min_length=1, max_length=50, description="Name of the agent")
    user_id: int = Field(..., gt=0, description="User ID")
    session_id: str = Field(..., description="Session UUID")
    suggestion: str = Field(..., min_length=1, description="Original agent suggestion")
    user_feedback: str = Field(..., description="Feedback type: accept, reject, or modify")
    modified_output: Optional[str] = Field(None, description="User's correction for 'modify' type")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Agent confidence score")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    model_version: Optional[str] = Field(None, description="Model version")
    tags: Optional[List[str]] = Field(None, description="Optional tags")
    
    @validator("user_feedback")
    def validate_feedback_type(cls, v):
        if v not in VALID_FEEDBACK_TYPES:
            raise ValueError(f"Invalid feedback type. Must be one of: {VALID_FEEDBACK_TYPES}")
        return v
    
    @validator("session_id")
    def validate_session_id(cls, v):
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError("Invalid session_id format. Must be a valid UUID.")
    
    @validator("modified_output", always=True)
    def validate_modified_output(cls, v, values):
        if values.get("user_feedback") == "modify" and not v:
            raise ValueError("modified_output is required when user_feedback is 'modify'")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_name": "safety_agent",
                "user_id": 123,
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "suggestion": "Check for aspirin-warfarin interaction",
                "user_feedback": "accept",
                "confidence_score": 0.95,
                "context": {"patient_id": "12345", "medication": "aspirin"},
                "model_version": "safety_agent_v1.2.0"
            }
        }
    )


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""
    feedback_id: int
    status: str = "success"
    message: str = "Feedback recorded successfully"


class FeedbackBatchRequest(BaseModel):
    """Request model for batch feedback submission."""
    feedback_items: List[FeedbackRequest] = Field(..., min_items=1, max_items=100)


class FeedbackBatchResponse(BaseModel):
    """Response model for batch feedback submission."""
    feedback_ids: List[int]
    count: int
    status: str = "success"


class FeedbackStatsResponse(BaseModel):
    """Response model for feedback statistics."""
    total_feedback: int
    accepted: int
    rejected: int
    modified: int
    avg_confidence: Optional[float]
    acceptance_rate: float
    agents: Optional[Dict[str, Dict[str, int]]]
    time_period: Optional[Dict[str, Optional[str]]]
    used_for_training: int
    pending_training: int


class AgentPerformanceResponse(BaseModel):
    """Response model for agent performance metrics."""
    agent_name: str
    period_days: int
    total_feedback: int
    acceptance_rate: float
    avg_confidence: Optional[float]
    avg_quality: Optional[float]
    daily_trend: List[Dict[str, Any]]


class TrainingDataRequest(BaseModel):
    """Request model for training data retrieval."""
    agent_name: Optional[str] = None
    min_confidence: float = Field(0.0, ge=0, le=1)
    feedback_types: Optional[List[str]] = None
    limit: int = Field(1000, gt=0, le=10000)
    offset: int = Field(0, ge=0)


class TrainingDataResponse(BaseModel):
    """Response model for training data."""
    batch_id: str
    count: int
    feedback_ids: List[int]
    training_pairs: List[Dict[str, str]]


class MarkTrainedRequest(BaseModel):
    """Request model for marking feedback as used for training."""
    feedback_ids: List[int] = Field(..., min_items=1)


# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY
# ═══════════════════════════════════════════════════════════════════════════════

# Database configuration - should be loaded from environment/config
_db_config: Optional[Dict[str, Any]] = None


def get_db_config() -> Dict[str, Any]:
    """Get database configuration."""
    global _db_config
    if _db_config is None:
        # Default config - override in production
        _db_config = {
            "host": "localhost",
            "port": 5432,
            "database": "phoenix_guardian",
            "user": "postgres",
            "password": "password",
        }
    return _db_config


def set_db_config(config: Dict[str, Any]) -> None:
    """Set database configuration."""
    global _db_config
    _db_config = config


def get_feedback_collector() -> FeedbackCollector:
    """Dependency to get FeedbackCollector instance."""
    return FeedbackCollector(get_db_config())


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback",
    description="Submit physician feedback on an agent suggestion."
)
async def submit_feedback(
    request: FeedbackRequest,
    collector: FeedbackCollector = Depends(get_feedback_collector),
) -> FeedbackResponse:
    """
    Submit user feedback on an agent suggestion.
    
    The feedback will be stored for future model training and improvement.
    """
    try:
        collector.connect()
        
        feedback = Feedback(
            agent_name=request.agent_name,
            user_id=request.user_id,
            session_id=uuid.UUID(request.session_id),
            suggestion=request.suggestion,
            user_feedback=request.user_feedback,
            modified_output=request.modified_output,
            confidence_score=request.confidence_score,
            context=request.context,
            model_version=request.model_version,
            tags=request.tags,
        )
        
        feedback_id = collector.collect_feedback(feedback)
        
        return FeedbackResponse(
            feedback_id=feedback_id,
            status="success",
            message=f"Feedback recorded for {request.agent_name}"
        )
        
    except FeedbackValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except FeedbackConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection error: {e.message}"
        )
    except FeedbackError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        collector.close()


@router.post(
    "/batch",
    response_model=FeedbackBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit batch feedback",
    description="Submit multiple feedback records at once."
)
async def submit_feedback_batch(
    request: FeedbackBatchRequest,
    collector: FeedbackCollector = Depends(get_feedback_collector),
) -> FeedbackBatchResponse:
    """Submit multiple feedback records in a single request."""
    try:
        collector.connect()
        
        feedback_list = [
            Feedback(
                agent_name=item.agent_name,
                user_id=item.user_id,
                session_id=uuid.UUID(item.session_id),
                suggestion=item.suggestion,
                user_feedback=item.user_feedback,
                modified_output=item.modified_output,
                confidence_score=item.confidence_score,
                context=item.context,
                model_version=item.model_version,
                tags=item.tags,
            )
            for item in request.feedback_items
        ]
        
        feedback_ids = collector.collect_feedback_batch(feedback_list)
        
        return FeedbackBatchResponse(
            feedback_ids=feedback_ids,
            count=len(feedback_ids),
            status="success"
        )
        
    except FeedbackError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        collector.close()


@router.get(
    "/stats",
    response_model=FeedbackStatsResponse,
    summary="Get feedback statistics",
    description="Retrieve aggregated feedback statistics."
)
async def get_feedback_stats(
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    start_date: Optional[datetime] = Query(None, description="Start of time period"),
    end_date: Optional[datetime] = Query(None, description="End of time period"),
    collector: FeedbackCollector = Depends(get_feedback_collector),
) -> FeedbackStatsResponse:
    """Get aggregated feedback statistics."""
    try:
        collector.connect()
        
        stats = collector.get_feedback_stats(
            agent_name=agent_name,
            start_date=start_date,
            end_date=end_date,
        )
        
        return FeedbackStatsResponse(**stats.to_dict())
        
    except FeedbackError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        collector.close()


@router.get(
    "/agent/{agent_name}/performance",
    response_model=AgentPerformanceResponse,
    summary="Get agent performance",
    description="Retrieve performance metrics for a specific agent."
)
async def get_agent_performance(
    agent_name: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    collector: FeedbackCollector = Depends(get_feedback_collector),
) -> AgentPerformanceResponse:
    """Get performance metrics for a specific agent."""
    try:
        collector.connect()
        
        performance = collector.get_agent_performance(agent_name, days=days)
        
        return AgentPerformanceResponse(**performance)
        
    except FeedbackError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        collector.close()


@router.get(
    "/{feedback_id}",
    summary="Get feedback by ID",
    description="Retrieve a specific feedback record."
)
async def get_feedback(
    feedback_id: int,
    collector: FeedbackCollector = Depends(get_feedback_collector),
) -> Dict[str, Any]:
    """Get a specific feedback record by ID."""
    try:
        collector.connect()
        
        feedback = collector.get_feedback(feedback_id)
        
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feedback {feedback_id} not found"
            )
        
        return feedback.to_dict()
        
    except FeedbackError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        collector.close()


@router.get(
    "/session/{session_id}",
    summary="Get session feedback",
    description="Retrieve all feedback for a session."
)
async def get_session_feedback(
    session_id: str,
    collector: FeedbackCollector = Depends(get_feedback_collector),
) -> List[Dict[str, Any]]:
    """Get all feedback for a specific session."""
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id format"
        )
    
    try:
        collector.connect()
        
        feedback_list = collector.get_feedback_by_session(session_uuid)
        
        return [fb.to_dict() for fb in feedback_list]
        
    except FeedbackError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        collector.close()


@router.post(
    "/training-data",
    response_model=TrainingDataResponse,
    summary="Get training data",
    description="Retrieve feedback data for model training."
)
async def get_training_data(
    request: TrainingDataRequest,
    collector: FeedbackCollector = Depends(get_feedback_collector),
) -> TrainingDataResponse:
    """Retrieve feedback data for model training."""
    try:
        collector.connect()
        
        batch = collector.get_training_data(
            agent_name=request.agent_name,
            min_confidence=request.min_confidence,
            feedback_types=request.feedback_types,
            limit=request.limit,
            offset=request.offset,
        )
        
        training_pairs = [
            {"input": pair[0], "target": pair[1]}
            for pair in batch.get_training_pairs()
        ]
        
        return TrainingDataResponse(
            batch_id=str(batch.batch_id),
            count=batch.size,
            feedback_ids=batch.feedback_ids,
            training_pairs=training_pairs,
        )
        
    except FeedbackError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        collector.close()


@router.post(
    "/mark-trained",
    summary="Mark feedback as trained",
    description="Mark feedback records as used for model training."
)
async def mark_feedback_trained(
    request: MarkTrainedRequest,
    collector: FeedbackCollector = Depends(get_feedback_collector),
) -> Dict[str, Any]:
    """Mark feedback records as used for training."""
    try:
        collector.connect()
        
        updated = collector.mark_as_used_for_training(request.feedback_ids)
        
        return {
            "updated": updated,
            "status": "success",
            "message": f"Marked {updated} records as used for training"
        }
        
    except FeedbackError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        collector.close()


@router.delete(
    "/{feedback_id}",
    summary="Delete feedback",
    description="Delete a specific feedback record."
)
async def delete_feedback(
    feedback_id: int,
    collector: FeedbackCollector = Depends(get_feedback_collector),
) -> Dict[str, Any]:
    """Delete a feedback record."""
    try:
        collector.connect()
        
        deleted = collector.delete_feedback(feedback_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feedback {feedback_id} not found"
            )
        
        return {
            "deleted": True,
            "feedback_id": feedback_id,
            "status": "success"
        }
        
    except FeedbackError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        collector.close()


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "router",
    "FeedbackRequest",
    "FeedbackResponse",
    "FeedbackBatchRequest",
    "FeedbackBatchResponse",
    "FeedbackStatsResponse",
    "TrainingDataRequest",
    "TrainingDataResponse",
    "get_feedback_collector",
    "set_db_config",
]
