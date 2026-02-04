"""
Federated Learning API endpoints
Privacy-preserving threat intelligence sharing
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/federated", tags=["federated"])


class ThreatSignature(BaseModel):
    """Federated threat signature"""
    id: UUID
    signature_hash: str = Field(alias="signatureHash")
    attack_type: str = Field(alias="attackType")
    confidence: float = Field(ge=0, le=1)
    contributor_count: int = Field(alias="contributorCount")
    first_seen: datetime = Field(alias="firstSeen")
    last_updated: datetime = Field(alias="lastUpdated")
    mitre_mapping: List[str] = Field(default_factory=list, alias="mitreMapping")
    privacy_preserved: bool = Field(True, alias="privacyPreserved")
    
    model_config = ConfigDict(populate_by_name=True)


class PrivacyMetrics(BaseModel):
    """Differential privacy budget metrics"""
    epsilon: float
    delta: float
    budget_used: float = Field(alias="budgetUsed")
    budget_total: float = Field(alias="budgetTotal")
    queries_this_period: int = Field(alias="queriesThisPeriod")
    noise_multiplier: float = Field(alias="noiseMultiplier")
    next_reset: datetime = Field(alias="nextReset")
    
    model_config = ConfigDict(populate_by_name=True)


class HospitalContribution(BaseModel):
    """Hospital contribution to federated network"""
    hospital_id: str = Field(alias="hospitalId")
    hospital_name: str = Field(alias="hospitalName")
    region: str
    contribution_count: int = Field(alias="contributionCount")
    last_contribution: datetime = Field(alias="lastContribution")
    quality_score: float = Field(ge=0, le=1, alias="qualityScore")
    privacy_compliant: bool = Field(alias="privacyCompliant")
    
    model_config = ConfigDict(populate_by_name=True)


class ModelStatus(BaseModel):
    """Federated model status"""
    model_version: str = Field(alias="modelVersion")
    last_update: datetime = Field(alias="lastUpdate")
    accuracy: float
    total_contributors: int = Field(alias="totalContributors")
    total_signatures: int = Field(alias="totalSignatures")
    is_training: bool = Field(alias="isTraining")


class ContributionSubmit(BaseModel):
    """Contribution submission"""
    signatures: List[dict]
    privacy_level: str = Field("high", alias="privacyLevel")
    
    model_config = ConfigDict(populate_by_name=True)


# In-memory stores with demo data
_signatures_store: List[dict] = []
_contributions_store: List[dict] = []
_privacy_metrics = {
    "epsilon": 1.0,
    "delta": 1e-5,
    "budget_used": 0.35,
    "budget_total": 1.0,
    "queries_this_period": 127,
    "noise_multiplier": 1.1,
    "next_reset": datetime.utcnow() + timedelta(days=7),
}
_model_status = {
    "model_version": "2.4.1",
    "last_update": datetime.utcnow() - timedelta(hours=6),
    "accuracy": 0.947,
    "total_contributors": 45,
    "total_signatures": 1247,
    "is_training": False,
}


# Initialize demo data
def _init_demo_data():
    if not _signatures_store:
        attack_types = ["ransomware_encryption", "lateral_movement", "data_exfiltration", 
                       "credential_theft", "c2_communication", "privilege_escalation"]
        mitre_tactics = ["T1486", "T1021", "T1567", "T1003", "T1071", "T1068"]
        
        for i in range(20):
            _signatures_store.append({
                "id": uuid4(),
                "signature_hash": f"sig_{uuid4().hex[:32]}",
                "attack_type": attack_types[i % len(attack_types)],
                "confidence": 0.75 + (i % 25) * 0.01,
                "contributor_count": 5 + i * 2,
                "first_seen": datetime.utcnow() - timedelta(days=30 - i),
                "last_updated": datetime.utcnow() - timedelta(hours=i * 2),
                "mitre_mapping": [mitre_tactics[i % len(mitre_tactics)]],
                "privacy_preserved": True,
            })
    
    if not _contributions_store:
        regions = ["Northeast", "Southeast", "Midwest", "West", "Southwest"]
        hospitals = [
            "Metro General Hospital", "Central Medical Center", "Pacific Health System",
            "Regional Medical", "University Hospital", "Community Care Center",
            "Mercy Health", "Providence Medical", "Baptist Health", "Sacred Heart"
        ]
        
        for i, hospital in enumerate(hospitals):
            _contributions_store.append({
                "hospital_id": f"hosp-{i+1}",
                "hospital_name": hospital,
                "region": regions[i % len(regions)],
                "contribution_count": 50 + i * 20,
                "last_contribution": datetime.utcnow() - timedelta(hours=i * 3),
                "quality_score": 0.8 + (i % 20) * 0.01,
                "privacy_compliant": i != 7,  # One non-compliant for demo
            })


_init_demo_data()


@router.get("/model/status", response_model=ModelStatus)
async def get_model_status():
    """Get federated model status"""
    return _model_status


@router.get("/signatures", response_model=List[ThreatSignature])
async def get_signatures(
    attack_type: Optional[str] = Query(None, alias="attackType"),
    min_confidence: Optional[float] = Query(None, ge=0, le=1, alias="minConfidence"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get federated threat signatures"""
    signatures = _signatures_store.copy()
    
    if attack_type:
        signatures = [s for s in signatures if s["attack_type"] == attack_type]
    if min_confidence:
        signatures = [s for s in signatures if s["confidence"] >= min_confidence]
    
    signatures.sort(key=lambda x: x["last_updated"], reverse=True)
    return signatures[:limit]


@router.get("/privacy/metrics", response_model=PrivacyMetrics)
async def get_privacy_metrics():
    """Get privacy budget metrics"""
    return _privacy_metrics


@router.get("/contributions", response_model=List[HospitalContribution])
async def get_contributions(
    region: Optional[str] = Query(None),
):
    """Get hospital contributions"""
    contributions = _contributions_store.copy()
    
    if region:
        contributions = [c for c in contributions if c["region"] == region]
    
    contributions.sort(key=lambda x: x["contribution_count"], reverse=True)
    return contributions


@router.post("/contributions")
async def submit_contribution(contribution: ContributionSubmit):
    """Submit a new contribution to the federated network"""
    # In production, would validate and process signatures
    # Apply differential privacy noise before aggregation
    
    return {
        "success": True,
        "signatures_accepted": len(contribution.signatures),
        "privacy_budget_used": 0.01,
    }


@router.get("/stats/summary")
async def get_federated_stats():
    """Get federated network statistics"""
    return {
        "model": _model_status,
        "privacy": _privacy_metrics,
        "network": {
            "total_hospitals": len(_contributions_store),
            "total_signatures": len(_signatures_store),
            "total_contributions": sum(c["contribution_count"] for c in _contributions_store),
            "regions": list(set(c["region"] for c in _contributions_store)),
            "compliant_hospitals": len([c for c in _contributions_store if c["privacy_compliant"]]),
        }
    }


@router.post("/model/trigger-training")
async def trigger_training():
    """Trigger federated model training round"""
    global _model_status
    _model_status["is_training"] = True
    
    return {
        "success": True,
        "message": "Training round initiated",
        "estimated_duration_minutes": 15,
    }


@router.get("/signatures/{signature_id}", response_model=ThreatSignature)
async def get_signature(signature_id: UUID):
    """Get a specific threat signature"""
    for sig in _signatures_store:
        if sig["id"] == signature_id:
            return sig
    raise HTTPException(status_code=404, detail="Signature not found")
