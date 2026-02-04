"""
Evidence Package API endpoints
Forensic evidence collection and chain of custody
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID, uuid4
import hashlib

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/evidence", tags=["evidence"])


class EvidenceItem(BaseModel):
    """Single evidence item"""
    id: UUID
    type: str = Field(..., description="Evidence type: network_logs, system_logs, etc.")
    name: str
    size: int
    collected_at: datetime = Field(alias="collectedAt")
    hash: str = Field(..., description="SHA-256 hash for integrity")
    
    model_config = ConfigDict(populate_by_name=True)


class EvidencePackageBase(BaseModel):
    """Base evidence package model"""
    incident_id: UUID = Field(alias="incidentId")
    incident_title: str = Field(alias="incidentTitle")
    
    model_config = ConfigDict(populate_by_name=True)


class EvidencePackageCreate(EvidencePackageBase):
    """Evidence package creation"""
    items: List[dict] = Field(default_factory=list)


class EvidencePackageResponse(EvidencePackageBase):
    """Evidence package response"""
    id: UUID
    status: str = Field(..., pattern="^(generating|ready|expired|error)$")
    items: List[EvidenceItem]
    total_size: int = Field(alias="totalSize")
    created_at: datetime = Field(alias="createdAt")
    created_by: str = Field(alias="createdBy")
    expires_at: datetime = Field(alias="expiresAt")
    integrity_verified: bool = Field(alias="integrityVerified")
    integrity_verified_at: Optional[datetime] = Field(None, alias="integrityVerifiedAt")
    
    model_config = ConfigDict(populate_by_name=True)


# In-memory store
_packages_store: dict[UUID, dict] = {}


@router.get("/packages", response_model=List[EvidencePackageResponse])
async def get_packages(
    status: Optional[str] = Query(None),
    incident_id: Optional[UUID] = Query(None, alias="incidentId"),
):
    """Get list of evidence packages"""
    packages = list(_packages_store.values())
    
    if status:
        packages = [p for p in packages if p["status"] == status]
    if incident_id:
        packages = [p for p in packages if p["incident_id"] == incident_id]
    
    packages.sort(key=lambda x: x["created_at"], reverse=True)
    return packages


@router.get("/packages/{package_id}", response_model=EvidencePackageResponse)
async def get_package(package_id: UUID):
    """Get a specific evidence package"""
    if package_id not in _packages_store:
        raise HTTPException(status_code=404, detail="Evidence package not found")
    return _packages_store[package_id]


@router.post("/packages", response_model=EvidencePackageResponse, status_code=201)
async def create_package(package: EvidencePackageCreate, created_by: str = "analyst@hospital.org"):
    """Create a new evidence package"""
    now = datetime.utcnow()
    package_id = uuid4()
    
    # Process items
    items = []
    total_size = 0
    for item_data in package.items:
        item_id = uuid4()
        item = {
            "id": item_id,
            "type": item_data.get("type", "unknown"),
            "name": item_data.get("name", f"evidence_{item_id}"),
            "size": item_data.get("size", 0),
            "collected_at": datetime.fromisoformat(item_data["collected_at"]) if "collected_at" in item_data else now,
            "hash": hashlib.sha256(str(item_id).encode()).hexdigest(),
        }
        items.append(item)
        total_size += item["size"]
    
    package_data = {
        "id": package_id,
        "incident_id": package.incident_id,
        "incident_title": package.incident_title,
        "status": "generating",
        "items": items,
        "total_size": total_size,
        "created_at": now,
        "created_by": created_by,
        "expires_at": now + timedelta(days=30),
        "integrity_verified": False,
        "integrity_verified_at": None,
    }
    
    _packages_store[package_id] = package_data
    
    # Simulate async generation complete
    package_data["status"] = "ready"
    
    return package_data


@router.post("/packages/{package_id}/verify")
async def verify_integrity(package_id: UUID):
    """Verify evidence package integrity"""
    if package_id not in _packages_store:
        raise HTTPException(status_code=404, detail="Evidence package not found")
    
    package = _packages_store[package_id]
    now = datetime.utcnow()
    
    # In production, would verify all item hashes
    verified = True
    for item in package["items"]:
        expected_hash = hashlib.sha256(str(item["id"]).encode()).hexdigest()
        if item["hash"] != expected_hash:
            verified = False
            break
    
    package.update({
        "integrity_verified": verified,
        "integrity_verified_at": now,
    })
    
    return {
        "verified": verified,
        "verified_at": now,
        "items_checked": len(package["items"]),
    }


@router.get("/packages/{package_id}/download")
async def download_package(package_id: UUID):
    """Download evidence package as ZIP"""
    if package_id not in _packages_store:
        raise HTTPException(status_code=404, detail="Evidence package not found")
    
    package = _packages_store[package_id]
    if package["status"] != "ready":
        raise HTTPException(status_code=400, detail="Package not ready for download")
    
    # In production, would generate and stream actual ZIP file
    # For demo, return a placeholder
    async def fake_file_generator():
        yield b"PK"  # ZIP magic bytes
        yield b"\x03\x04"
        yield b"\x00" * 100
    
    return StreamingResponse(
        fake_file_generator(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=evidence_{package_id}.zip"
        }
    )


@router.delete("/packages/{package_id}", status_code=204)
async def delete_package(package_id: UUID):
    """Delete an evidence package"""
    if package_id not in _packages_store:
        raise HTTPException(status_code=404, detail="Evidence package not found")
    
    del _packages_store[package_id]
    return None


@router.get("/stats/summary")
async def get_evidence_stats():
    """Get evidence statistics"""
    packages = list(_packages_store.values())
    
    total_items = sum(len(p["items"]) for p in packages)
    total_size = sum(p["total_size"] for p in packages)
    
    return {
        "total_packages": len(packages),
        "total_items": total_items,
        "total_size_bytes": total_size,
        "by_status": {
            "generating": len([p for p in packages if p["status"] == "generating"]),
            "ready": len([p for p in packages if p["status"] == "ready"]),
            "expired": len([p for p in packages if p["status"] == "expired"]),
        },
        "verified": len([p for p in packages if p["integrity_verified"]]),
    }
