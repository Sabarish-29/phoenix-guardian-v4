"""
Incident Management API endpoints
Security incident response workflow
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/incidents", tags=["incidents"])


class Assignee(BaseModel):
    """Incident assignee"""
    id: str
    name: str
    email: str


class IncidentBase(BaseModel):
    """Base incident model"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: str = Field(..., pattern="^(P1|P2|P3|P4)$")
    severity: str = Field(..., pattern="^(critical|high|medium|low)$")
    category: str
    affected_assets: List[str] = Field(default_factory=list, alias="affectedAssets")
    affected_departments: List[str] = Field(default_factory=list, alias="affectedDepartments")
    threat_ids: List[UUID] = Field(default_factory=list, alias="threatIds")
    
    model_config = ConfigDict(populate_by_name=True)


class IncidentCreate(IncidentBase):
    """Incident creation model"""
    pass


class IncidentResponse(IncidentBase):
    """Incident response model"""
    id: UUID
    status: str = Field(..., pattern="^(open|investigating|contained|eradicating|recovering|resolved|closed)$")
    assignee: Optional[Assignee] = None
    sla_breach: bool = Field(False, alias="slaBreach")
    containment_actions: List[str] = Field(default_factory=list, alias="containmentActions")
    remediation_actions: List[str] = Field(default_factory=list, alias="remediationActions")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    resolved_at: Optional[datetime] = Field(None, alias="resolvedAt")
    
    model_config = ConfigDict(populate_by_name=True)


class IncidentStatusUpdate(BaseModel):
    """Incident status update"""
    status: str = Field(..., pattern="^(open|investigating|contained|eradicating|recovering|resolved|closed)$")


class IncidentAssignment(BaseModel):
    """Incident assignment"""
    user_id: str = Field(alias="userId")
    
    model_config = ConfigDict(populate_by_name=True)


# In-memory store
_incidents_store: dict[UUID, dict] = {}

# Mock users for assignment
_mock_users = {
    "user-1": {"id": "user-1", "name": "John Analyst", "email": "john@hospital.org"},
    "user-2": {"id": "user-2", "name": "Jane Security", "email": "jane@hospital.org"},
    "user-3": {"id": "user-3", "name": "Bob Admin", "email": "bob@hospital.org"},
}


@router.get("", response_model=List[IncidentResponse])
async def get_incidents(
    status: Optional[List[str]] = Query(None),
    priority: Optional[List[str]] = Query(None),
    assignee_id: Optional[str] = Query(None, alias="assigneeId"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get list of incidents with optional filtering"""
    incidents = list(_incidents_store.values())
    
    if status:
        incidents = [i for i in incidents if i["status"] in status]
    if priority:
        incidents = [i for i in incidents if i["priority"] in priority]
    if assignee_id:
        incidents = [i for i in incidents if i.get("assignee") and i["assignee"]["id"] == assignee_id]
    
    # Sort by priority then created_at
    priority_order = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
    incidents.sort(key=lambda x: (priority_order.get(x["priority"], 4), -x["created_at"].timestamp()))
    
    return incidents[offset:offset + limit]


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: UUID):
    """Get a specific incident"""
    if incident_id not in _incidents_store:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _incidents_store[incident_id]


@router.post("", response_model=IncidentResponse, status_code=201)
async def create_incident(incident: IncidentCreate):
    """Create a new incident"""
    now = datetime.utcnow()
    incident_id = uuid4()
    
    incident_data = {
        "id": incident_id,
        **incident.model_dump(by_alias=True),
        "status": "open",
        "assignee": None,
        "sla_breach": False,
        "containment_actions": [],
        "remediation_actions": [],
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
    }
    
    _incidents_store[incident_id] = incident_data
    return incident_data


@router.put("/{incident_id}/status", response_model=IncidentResponse)
async def update_incident_status(incident_id: UUID, status_update: IncidentStatusUpdate):
    """Update incident status"""
    if incident_id not in _incidents_store:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    now = datetime.utcnow()
    incident = _incidents_store[incident_id]
    incident["status"] = status_update.status
    incident["updated_at"] = now
    
    if status_update.status in ("resolved", "closed"):
        incident["resolved_at"] = now
    
    return incident


@router.put("/{incident_id}/assign", response_model=IncidentResponse)
async def assign_incident(incident_id: UUID, assignment: IncidentAssignment):
    """Assign incident to a user"""
    if incident_id not in _incidents_store:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    user_id = assignment.user_id
    if user_id not in _mock_users:
        raise HTTPException(status_code=404, detail="User not found")
    
    incident = _incidents_store[incident_id]
    incident["assignee"] = _mock_users[user_id]
    incident["updated_at"] = datetime.utcnow()
    
    return incident


@router.put("/{incident_id}", response_model=IncidentResponse)
async def update_incident(incident_id: UUID, updates: dict):
    """Update incident fields"""
    if incident_id not in _incidents_store:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    allowed_fields = {"title", "description", "priority", "severity", "category", 
                      "affected_assets", "affected_departments", "containment_actions", 
                      "remediation_actions", "sla_breach"}
    
    incident = _incidents_store[incident_id]
    for key, value in updates.items():
        if key in allowed_fields:
            incident[key] = value
    
    incident["updated_at"] = datetime.utcnow()
    return incident


@router.delete("/{incident_id}", status_code=204)
async def delete_incident(incident_id: UUID):
    """Delete an incident"""
    if incident_id not in _incidents_store:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    del _incidents_store[incident_id]
    return None


@router.post("/{incident_id}/containment")
async def add_containment_action(incident_id: UUID, action: str):
    """Add a containment action to incident"""
    if incident_id not in _incidents_store:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    incident = _incidents_store[incident_id]
    incident["containment_actions"].append(action)
    incident["updated_at"] = datetime.utcnow()
    
    return {"success": True, "actions": incident["containment_actions"]}


@router.get("/stats/summary")
async def get_incident_stats():
    """Get incident statistics"""
    incidents = list(_incidents_store.values())
    
    return {
        "total": len(incidents),
        "by_priority": {
            "P1": len([i for i in incidents if i["priority"] == "P1"]),
            "P2": len([i for i in incidents if i["priority"] == "P2"]),
            "P3": len([i for i in incidents if i["priority"] == "P3"]),
            "P4": len([i for i in incidents if i["priority"] == "P4"]),
        },
        "by_status": {
            "open": len([i for i in incidents if i["status"] == "open"]),
            "investigating": len([i for i in incidents if i["status"] == "investigating"]),
            "contained": len([i for i in incidents if i["status"] == "contained"]),
            "resolved": len([i for i in incidents if i["status"] == "resolved"]),
        },
        "unassigned": len([i for i in incidents if not i["assignee"]]),
        "sla_breached": len([i for i in incidents if i["sla_breach"]]),
    }
