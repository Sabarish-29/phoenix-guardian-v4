"""
Threat Feed API endpoints
Real-time threat monitoring and management
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/threats", tags=["threats"])


class ThreatIndicator(BaseModel):
    """Threat indicator of compromise"""
    type: str = Field(..., description="IOC type: hash, domain, ip, etc.")
    value: str = Field(..., description="IOC value")
    confidence: float = Field(ge=0, le=1, description="Confidence score")


class ThreatBase(BaseModel):
    """Base threat model"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    severity: str = Field(..., pattern="^(critical|high|medium|low)$")
    threat_type: str = Field(..., alias="threatType")
    source_ip: Optional[str] = Field(None, alias="sourceIp")
    target_system: Optional[str] = Field(None, alias="targetSystem")
    indicators: List[str] = Field(default_factory=list)
    mitre_tactics: List[str] = Field(default_factory=list, alias="mitreTactics")
    
    model_config = ConfigDict(populate_by_name=True)


class ThreatCreate(ThreatBase):
    """Threat creation model"""
    pass


class ThreatResponse(ThreatBase):
    """Threat response model"""
    id: UUID
    status: str = Field(..., pattern="^(active|investigating|mitigated|resolved|false_positive)$")
    confidence: float = Field(ge=0, le=1)
    acknowledged: bool = False
    acknowledged_by: Optional[str] = Field(None, alias="acknowledgedBy")
    acknowledged_at: Optional[datetime] = Field(None, alias="acknowledgedAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    model_config = ConfigDict(populate_by_name=True)


class ThreatStatusUpdate(BaseModel):
    """Threat status update"""
    status: str = Field(..., pattern="^(active|investigating|mitigated|resolved|false_positive)$")


# In-memory store for demo
_threats_store: dict[UUID, dict] = {}


@router.get("", response_model=List[ThreatResponse])
async def get_threats(
    severity: Optional[List[str]] = Query(None),
    status: Optional[List[str]] = Query(None),
    threat_type: Optional[List[str]] = Query(None, alias="threatType"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Get list of threats with optional filtering
    
    - **severity**: Filter by severity levels
    - **status**: Filter by threat status
    - **threat_type**: Filter by threat types
    - **search**: Full-text search in title and description
    """
    threats = list(_threats_store.values())
    
    # Apply filters
    if severity:
        threats = [t for t in threats if t["severity"] in severity]
    if status:
        threats = [t for t in threats if t["status"] in status]
    if threat_type:
        threats = [t for t in threats if t["threat_type"] in threat_type]
    if search:
        search_lower = search.lower()
        threats = [
            t for t in threats 
            if search_lower in t["title"].lower() 
            or (t.get("description") and search_lower in t["description"].lower())
        ]
    
    # Sort by created_at descending
    threats.sort(key=lambda x: x["created_at"], reverse=True)
    
    # Pagination
    return threats[offset:offset + limit]


@router.get("/{threat_id}", response_model=ThreatResponse)
async def get_threat(threat_id: UUID):
    """Get a specific threat by ID"""
    if threat_id not in _threats_store:
        raise HTTPException(status_code=404, detail="Threat not found")
    return _threats_store[threat_id]


@router.post("", response_model=ThreatResponse, status_code=201)
async def create_threat(threat: ThreatCreate):
    """Create a new threat alert"""
    now = datetime.utcnow()
    threat_id = uuid4()
    
    threat_data = {
        "id": threat_id,
        **threat.model_dump(by_alias=True),
        "status": "active",
        "confidence": 0.85,
        "acknowledged": False,
        "acknowledged_by": None,
        "acknowledged_at": None,
        "created_at": now,
        "updated_at": now,
    }
    
    _threats_store[threat_id] = threat_data
    return threat_data


@router.post("/{threat_id}/acknowledge")
async def acknowledge_threat(threat_id: UUID, user_id: str = "system"):
    """Acknowledge a threat alert"""
    if threat_id not in _threats_store:
        raise HTTPException(status_code=404, detail="Threat not found")
    
    now = datetime.utcnow()
    _threats_store[threat_id].update({
        "acknowledged": True,
        "acknowledged_by": user_id,
        "acknowledged_at": now,
        "updated_at": now,
    })
    
    return {"success": True, "acknowledged_at": now}


@router.put("/{threat_id}/status", response_model=ThreatResponse)
async def update_threat_status(threat_id: UUID, status_update: ThreatStatusUpdate):
    """Update threat status"""
    if threat_id not in _threats_store:
        raise HTTPException(status_code=404, detail="Threat not found")
    
    _threats_store[threat_id].update({
        "status": status_update.status,
        "updated_at": datetime.utcnow(),
    })
    
    return _threats_store[threat_id]


@router.delete("/{threat_id}", status_code=204)
async def delete_threat(threat_id: UUID):
    """Delete a threat (soft delete in production)"""
    if threat_id not in _threats_store:
        raise HTTPException(status_code=404, detail="Threat not found")
    
    del _threats_store[threat_id]
    return None


@router.get("/stats/summary")
async def get_threat_stats():
    """Get threat statistics summary"""
    threats = list(_threats_store.values())
    
    return {
        "total": len(threats),
        "by_severity": {
            "critical": len([t for t in threats if t["severity"] == "critical"]),
            "high": len([t for t in threats if t["severity"] == "high"]),
            "medium": len([t for t in threats if t["severity"] == "medium"]),
            "low": len([t for t in threats if t["severity"] == "low"]),
        },
        "by_status": {
            "active": len([t for t in threats if t["status"] == "active"]),
            "investigating": len([t for t in threats if t["status"] == "investigating"]),
            "mitigated": len([t for t in threats if t["status"] == "mitigated"]),
            "resolved": len([t for t in threats if t["status"] == "resolved"]),
        },
        "unacknowledged": len([t for t in threats if not t["acknowledged"]]),
    }
