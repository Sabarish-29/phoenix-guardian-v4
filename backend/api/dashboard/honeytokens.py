"""
Honeytoken API endpoints
Deception technology for healthcare threat detection
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/honeytokens", tags=["honeytokens"])


class HoneytokenBase(BaseModel):
    """Base honeytoken model"""
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., pattern="^(patient_record|medication|admin_credential|api_key|database)$")
    description: Optional[str] = None
    location: Optional[str] = None
    alert_level: str = Field("high", pattern="^(low|medium|high|critical)$", alias="alertLevel")
    
    model_config = ConfigDict(populate_by_name=True)


class HoneytokenCreate(HoneytokenBase):
    """Honeytoken creation model"""
    pass


class HoneytokenResponse(HoneytokenBase):
    """Honeytoken response model"""
    id: UUID
    status: str = Field(..., pattern="^(active|inactive|expired)$")
    trigger_count: int = Field(0, alias="triggerCount")
    last_triggered: Optional[datetime] = Field(None, alias="lastTriggered")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    model_config = ConfigDict(populate_by_name=True)


class TriggerResponse(BaseModel):
    """Honeytoken trigger event"""
    id: UUID
    honeytoken_id: UUID = Field(alias="honeytokenId")
    honeytoken_name: str = Field(alias="honeytokenName")
    timestamp: datetime
    source_ip: str = Field(alias="sourceIp")
    source_user: Optional[str] = Field(None, alias="sourceUser")
    access_type: str = Field(alias="accessType")
    target_system: str = Field(alias="targetSystem")
    
    model_config = ConfigDict(populate_by_name=True)


# In-memory stores
_honeytokens_store: dict[UUID, dict] = {}
_triggers_store: dict[UUID, List[dict]] = {}


@router.get("", response_model=List[HoneytokenResponse])
async def get_honeytokens(
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
):
    """Get list of honeytokens"""
    honeytokens = list(_honeytokens_store.values())
    
    if status:
        honeytokens = [h for h in honeytokens if h["status"] == status]
    if type:
        honeytokens = [h for h in honeytokens if h["type"] == type]
    
    return honeytokens


@router.get("/{honeytoken_id}", response_model=HoneytokenResponse)
async def get_honeytoken(honeytoken_id: UUID):
    """Get a specific honeytoken"""
    if honeytoken_id not in _honeytokens_store:
        raise HTTPException(status_code=404, detail="Honeytoken not found")
    return _honeytokens_store[honeytoken_id]


@router.post("", response_model=HoneytokenResponse, status_code=201)
async def create_honeytoken(honeytoken: HoneytokenCreate):
    """Create a new honeytoken"""
    now = datetime.utcnow()
    honeytoken_id = uuid4()
    
    honeytoken_data = {
        "id": honeytoken_id,
        **honeytoken.model_dump(by_alias=True),
        "status": "active",
        "trigger_count": 0,
        "last_triggered": None,
        "created_at": now,
        "updated_at": now,
    }
    
    _honeytokens_store[honeytoken_id] = honeytoken_data
    _triggers_store[honeytoken_id] = []
    
    return honeytoken_data


@router.put("/{honeytoken_id}", response_model=HoneytokenResponse)
async def update_honeytoken(honeytoken_id: UUID, updates: dict):
    """Update a honeytoken"""
    if honeytoken_id not in _honeytokens_store:
        raise HTTPException(status_code=404, detail="Honeytoken not found")
    
    _honeytokens_store[honeytoken_id].update({
        **updates,
        "updated_at": datetime.utcnow(),
    })
    
    return _honeytokens_store[honeytoken_id]


@router.delete("/{honeytoken_id}", status_code=204)
async def delete_honeytoken(honeytoken_id: UUID):
    """Delete a honeytoken"""
    if honeytoken_id not in _honeytokens_store:
        raise HTTPException(status_code=404, detail="Honeytoken not found")
    
    del _honeytokens_store[honeytoken_id]
    if honeytoken_id in _triggers_store:
        del _triggers_store[honeytoken_id]
    return None


@router.get("/{honeytoken_id}/triggers", response_model=List[TriggerResponse])
async def get_triggers(
    honeytoken_id: UUID,
    limit: int = Query(50, ge=1, le=200),
):
    """Get trigger events for a honeytoken"""
    if honeytoken_id not in _honeytokens_store:
        raise HTTPException(status_code=404, detail="Honeytoken not found")
    
    triggers = _triggers_store.get(honeytoken_id, [])
    triggers.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return triggers[:limit]


@router.get("/triggers/recent", response_model=List[TriggerResponse])
async def get_recent_triggers(limit: int = Query(20, ge=1, le=100)):
    """Get all recent trigger events across honeytokens"""
    all_triggers = []
    for triggers in _triggers_store.values():
        all_triggers.extend(triggers)
    
    all_triggers.sort(key=lambda x: x["timestamp"], reverse=True)
    return all_triggers[:limit]


@router.post("/{honeytoken_id}/trigger", response_model=TriggerResponse)
async def record_trigger(
    honeytoken_id: UUID,
    source_ip: str,
    access_type: str,
    target_system: str,
    source_user: Optional[str] = None,
):
    """Record a honeytoken trigger event (called by detection system)"""
    if honeytoken_id not in _honeytokens_store:
        raise HTTPException(status_code=404, detail="Honeytoken not found")
    
    now = datetime.utcnow()
    honeytoken = _honeytokens_store[honeytoken_id]
    
    trigger = {
        "id": uuid4(),
        "honeytoken_id": honeytoken_id,
        "honeytoken_name": honeytoken["name"],
        "timestamp": now,
        "source_ip": source_ip,
        "source_user": source_user,
        "access_type": access_type,
        "target_system": target_system,
    }
    
    # Update honeytoken stats
    honeytoken["trigger_count"] += 1
    honeytoken["last_triggered"] = now
    honeytoken["updated_at"] = now
    
    # Store trigger
    if honeytoken_id not in _triggers_store:
        _triggers_store[honeytoken_id] = []
    _triggers_store[honeytoken_id].append(trigger)
    
    return trigger


@router.get("/stats/summary")
async def get_honeytoken_stats():
    """Get honeytoken statistics"""
    honeytokens = list(_honeytokens_store.values())
    all_triggers = []
    for triggers in _triggers_store.values():
        all_triggers.extend(triggers)
    
    return {
        "total_honeytokens": len(honeytokens),
        "active": len([h for h in honeytokens if h["status"] == "active"]),
        "total_triggers": len(all_triggers),
        "by_type": {
            "patient_record": len([h for h in honeytokens if h["type"] == "patient_record"]),
            "medication": len([h for h in honeytokens if h["type"] == "medication"]),
            "admin_credential": len([h for h in honeytokens if h["type"] == "admin_credential"]),
            "api_key": len([h for h in honeytokens if h["type"] == "api_key"]),
            "database": len([h for h in honeytokens if h["type"] == "database"]),
        },
    }
