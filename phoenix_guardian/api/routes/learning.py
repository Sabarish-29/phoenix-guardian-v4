"""
API Routes for Bidirectional Learning Pipeline.

Provides endpoints for:
- Recording physician feedback
- Running learning pipeline cycles
- Querying pipeline status and metrics
- Viewing learning history
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from phoenix_guardian.api.auth import get_current_user

router = APIRouter(prefix="/learning", tags=["bidirectional-learning"])


# ═══════════════════════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════════════════════


class FeedbackRequest(BaseModel):
    """Request model for physician feedback."""
    agent: str = Field(..., description="Agent that produced the output (e.g., 'scribe', 'fraud')")
    action: str = Field(..., description="Feedback action: accept, reject, modify")
    original_output: str = Field(..., description="Original agent output")
    corrected_output: Optional[str] = Field(None, description="Corrected output (for modify action)")
    encounter_id: Optional[str] = Field(None, description="Associated encounter ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class FeedbackBatchRequest(BaseModel):
    """Request model for batch feedback."""
    feedback: List[FeedbackRequest] = Field(..., description="List of feedback events")


class RunCycleRequest(BaseModel):
    """Request model for triggering a learning cycle."""
    domain: str = Field(
        default="fraud_detection",
        description="Model domain: fraud_detection, threat_detection, readmission, code_suggestion, soap_quality"
    )
    force: bool = Field(
        default=False,
        description="Force training even with insufficient feedback"
    )


class PipelineStatusResponse(BaseModel):
    """Response model for pipeline status."""
    stage: str
    domain: str
    feedback_buffer_size: int
    min_feedback_for_training: int
    ready_for_training: bool
    total_cycles_completed: int


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/feedback")
async def record_feedback(
    request: FeedbackRequest,
    current_user=Depends(get_current_user),
):
    """
    Record physician feedback on agent output.

    This feedback fuels the bidirectional learning pipeline:
    - **accept**: Agent output was correct (positive training signal)
    - **reject**: Agent output was wrong (negative training signal)
    - **modify**: Agent output was partially correct (highest-value signal)

    Corrections (modify action) carry the highest training weight.
    """
    from phoenix_guardian.learning.bidirectional_pipeline import (
        get_pipeline,
        ModelDomain,
        FeedbackEvent,
    )

    # Determine domain from agent type
    agent_domain_map = {
        "fraud": ModelDomain.FRAUD_DETECTION,
        "sentinel": ModelDomain.THREAT_DETECTION,
        "readmission": ModelDomain.READMISSION,
        "coding": ModelDomain.CODE_SUGGESTION,
        "scribe": ModelDomain.SOAP_QUALITY,
    }
    domain = agent_domain_map.get(request.agent, ModelDomain.FRAUD_DETECTION)
    pipeline = get_pipeline(domain)

    event = FeedbackEvent(
        id="",
        agent=request.agent,
        action=request.action,
        original_output=request.original_output,
        corrected_output=request.corrected_output,
        physician_id=str(getattr(current_user, "id", "unknown")),
        encounter_id=request.encounter_id,
        metadata=request.metadata,
    )

    pipeline.record_feedback(event)

    return {
        "status": "recorded",
        "feedback_id": event.id,
        "buffer_size": len(pipeline._feedback_buffer),
        "ready_for_training": len(pipeline._feedback_buffer) >= pipeline.min_feedback,
    }


@router.post("/feedback/batch")
async def record_feedback_batch(
    request: FeedbackBatchRequest,
    current_user=Depends(get_current_user),
):
    """Record multiple feedback events at once."""
    from phoenix_guardian.learning.bidirectional_pipeline import (
        get_pipeline,
        ModelDomain,
        FeedbackEvent,
    )

    recorded = 0
    for fb in request.feedback:
        agent_domain_map = {
            "fraud": ModelDomain.FRAUD_DETECTION,
            "sentinel": ModelDomain.THREAT_DETECTION,
            "readmission": ModelDomain.READMISSION,
            "coding": ModelDomain.CODE_SUGGESTION,
            "scribe": ModelDomain.SOAP_QUALITY,
        }
        domain = agent_domain_map.get(fb.agent, ModelDomain.FRAUD_DETECTION)
        pipeline = get_pipeline(domain)

        event = FeedbackEvent(
            id="",
            agent=fb.agent,
            action=fb.action,
            original_output=fb.original_output,
            corrected_output=fb.corrected_output,
            physician_id=str(getattr(current_user, "id", "unknown")),
            encounter_id=fb.encounter_id,
            metadata=fb.metadata,
        )
        pipeline.record_feedback(event)
        recorded += 1

    return {"status": "recorded", "count": recorded}


@router.post("/run-cycle")
async def run_learning_cycle(
    request: RunCycleRequest,
    current_user=Depends(get_current_user),
):
    """
    Trigger a complete bidirectional learning pipeline cycle.

    Steps executed:
    1. Validate sufficient feedback exists
    2. Prepare training data from physician corrections
    3. Fine-tune model on feedback data
    4. A/B test baseline vs fine-tuned model
    5. Deploy improved model (if statistically significant)

    **Returns:**
    - Complete metrics including F1 improvement and deployment decision
    """
    from phoenix_guardian.learning.bidirectional_pipeline import (
        get_pipeline,
        ModelDomain,
    )

    try:
        domain = ModelDomain(request.domain)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain: {request.domain}. "
            f"Valid: fraud_detection, threat_detection, readmission, code_suggestion, soap_quality"
        )

    pipeline = get_pipeline(domain)

    if request.force:
        pipeline.min_feedback = 1  # Allow forcing with any amount of data

    try:
        metrics = await pipeline.run_cycle()
        return {
            "status": "completed",
            "pipeline_id": metrics.pipeline_id,
            "domain": metrics.domain,
            "baseline_f1": metrics.baseline_f1,
            "bidirectional_f1": metrics.bidirectional_f1,
            "f1_improvement": metrics.f1_improvement,
            "deployment_decision": metrics.deployment_decision,
            "acceptance_rate": metrics.acceptance_rate,
            "training_examples": metrics.training_examples,
            "training_time_ms": metrics.training_time_ms,
            "ab_test_significant": metrics.ab_test_significant,
            "ab_test_p_value": metrics.ab_test_p_value,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline cycle failed: {str(e)}")


@router.get("/status/{domain}")
async def get_pipeline_status(
    domain: str,
    current_user=Depends(get_current_user),
):
    """
    Get the current status of a learning pipeline.

    **Path Parameters:**
    - `domain`: Model domain (fraud_detection, threat_detection, etc.)
    """
    from phoenix_guardian.learning.bidirectional_pipeline import (
        get_pipeline,
        ModelDomain,
    )

    try:
        model_domain = ModelDomain(domain)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

    pipeline = get_pipeline(model_domain)
    return pipeline.get_status()


@router.get("/feedback-stats/{domain}")
async def get_feedback_stats(
    domain: str,
    current_user=Depends(get_current_user),
):
    """
    Get feedback statistics for a learning pipeline.

    Returns acceptance rates, counts by action type, and
    training readiness.
    """
    from phoenix_guardian.learning.bidirectional_pipeline import (
        get_pipeline,
        ModelDomain,
    )

    try:
        model_domain = ModelDomain(domain)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

    pipeline = get_pipeline(model_domain)
    return pipeline.get_feedback_stats()


@router.get("/history/{domain}")
async def get_learning_history(
    domain: str,
    current_user=Depends(get_current_user),
):
    """
    Get history of all learning pipeline runs for a domain.

    Shows F1 improvement trends, deployment decisions, and
    acceptance rates over time.
    """
    from phoenix_guardian.learning.bidirectional_pipeline import (
        get_pipeline,
        ModelDomain,
    )

    try:
        model_domain = ModelDomain(domain)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

    pipeline = get_pipeline(model_domain)
    return {
        "domain": domain,
        "history": pipeline.get_history(),
        "total_cycles": len(pipeline.get_history()),
    }


@router.get("/status")
async def get_all_pipeline_status(
    current_user=Depends(get_current_user),
):
    """Get status of all learning pipelines across all domains."""
    from phoenix_guardian.learning.bidirectional_pipeline import get_all_pipelines

    pipelines = get_all_pipelines()
    return {
        "pipelines": {
            name: pipeline.get_status()
            for name, pipeline in pipelines.items()
        },
        "total_pipelines": len(pipelines),
    }
