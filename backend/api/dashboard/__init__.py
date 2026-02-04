"""
Phoenix Guardian Security Dashboard API
Week 27-28: Real-time security command center endpoints
"""

from fastapi import APIRouter

from .threats import router as threats_router
from .honeytokens import router as honeytokens_router
from .evidence import router as evidence_router
from .incidents import router as incidents_router
from .federated import router as federated_router
from .websocket import router as websocket_router

router = APIRouter(prefix="/api/v1", tags=["dashboard"])

# Include all dashboard sub-routers
router.include_router(threats_router)
router.include_router(honeytokens_router)
router.include_router(evidence_router)
router.include_router(incidents_router)
router.include_router(federated_router)
router.include_router(websocket_router)

__all__ = ["router"]
