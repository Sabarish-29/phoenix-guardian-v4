"""
Tests for Federated Learning API endpoints
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.api.dashboard.federated import router


@pytest.fixture
def app():
    """Create test FastAPI app"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestModelStatus:
    """Tests for GET /federated/model/status endpoint"""
    
    def test_get_model_status(self, client):
        """Test getting model status"""
        response = client.get("/federated/model/status")
        assert response.status_code == 200
        data = response.json()
        assert "modelVersion" in data
        assert "accuracy" in data
        assert "totalContributors" in data
        assert "isTraining" in data


class TestSignatures:
    """Tests for signature endpoints"""
    
    def test_get_signatures(self, client):
        """Test getting threat signatures"""
        response = client.get("/federated/signatures")
        assert response.status_code == 200
        signatures = response.json()
        assert isinstance(signatures, list)
        assert len(signatures) > 0
    
    def test_get_signatures_filter_attack_type(self, client):
        """Test filtering signatures by attack type"""
        response = client.get("/federated/signatures?attackType=ransomware_encryption")
        assert response.status_code == 200
        signatures = response.json()
        assert all(s["attackType"] == "ransomware_encryption" for s in signatures)
    
    def test_get_signatures_filter_confidence(self, client):
        """Test filtering signatures by minimum confidence"""
        response = client.get("/federated/signatures?minConfidence=0.9")
        assert response.status_code == 200
        signatures = response.json()
        assert all(s["confidence"] >= 0.9 for s in signatures)
    
    def test_get_signatures_limit(self, client):
        """Test limiting signature results"""
        response = client.get("/federated/signatures?limit=5")
        assert response.status_code == 200
        assert len(response.json()) <= 5


class TestPrivacyMetrics:
    """Tests for GET /federated/privacy/metrics endpoint"""
    
    def test_get_privacy_metrics(self, client):
        """Test getting privacy metrics"""
        response = client.get("/federated/privacy/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "epsilon" in data
        assert "delta" in data
        assert "budgetUsed" in data
        assert "budgetTotal" in data
        assert "noiseMultiplier" in data
    
    def test_privacy_budget_range(self, client):
        """Test that budget values are within expected range"""
        response = client.get("/federated/privacy/metrics")
        data = response.json()
        assert 0 <= data["budgetUsed"] <= data["budgetTotal"]


class TestContributions:
    """Tests for contribution endpoints"""
    
    def test_get_contributions(self, client):
        """Test getting hospital contributions"""
        response = client.get("/federated/contributions")
        assert response.status_code == 200
        contributions = response.json()
        assert isinstance(contributions, list)
        assert len(contributions) > 0
    
    def test_get_contributions_filter_region(self, client):
        """Test filtering contributions by region"""
        response = client.get("/federated/contributions?region=Northeast")
        assert response.status_code == 200
        contributions = response.json()
        assert all(c["region"] == "Northeast" for c in contributions)
    
    def test_contribution_has_required_fields(self, client):
        """Test that contributions have required fields"""
        response = client.get("/federated/contributions")
        contributions = response.json()
        
        for contrib in contributions:
            assert "hospitalId" in contrib
            assert "hospitalName" in contrib
            assert "region" in contrib
            assert "contributionCount" in contrib
            assert "qualityScore" in contrib
            assert "privacyCompliant" in contrib


class TestSubmitContribution:
    """Tests for POST /federated/contributions endpoint"""
    
    def test_submit_contribution_success(self, client):
        """Test submitting a contribution"""
        response = client.post("/federated/contributions", json={
            "signatures": [{"hash": "abc123", "type": "ransomware"}],
            "privacyLevel": "high"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["signatures_accepted"] == 1
    
    def test_submit_contribution_empty(self, client):
        """Test submitting empty contribution"""
        response = client.post("/federated/contributions", json={
            "signatures": [],
            "privacyLevel": "medium"
        })
        
        assert response.status_code == 200
        assert response.json()["signatures_accepted"] == 0


class TestFederatedStats:
    """Tests for GET /federated/stats/summary endpoint"""
    
    def test_get_federated_stats(self, client):
        """Test getting federated stats"""
        response = client.get("/federated/stats/summary")
        assert response.status_code == 200
        data = response.json()
        
        assert "model" in data
        assert "privacy" in data
        assert "network" in data
        
        assert "total_hospitals" in data["network"]
        assert "total_signatures" in data["network"]
        assert "compliant_hospitals" in data["network"]


class TestTriggerTraining:
    """Tests for POST /federated/model/trigger-training endpoint"""
    
    def test_trigger_training(self, client):
        """Test triggering training round"""
        response = client.post("/federated/model/trigger-training")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "estimated_duration_minutes" in data


class TestGetSignature:
    """Tests for GET /federated/signatures/{id} endpoint"""
    
    def test_get_signature_success(self, client):
        """Test getting a specific signature"""
        # First get list of signatures
        list_response = client.get("/federated/signatures?limit=1")
        signatures = list_response.json()
        
        if signatures:
            sig_id = signatures[0]["id"]
            response = client.get(f"/federated/signatures/{sig_id}")
            assert response.status_code == 200
            assert response.json()["id"] == sig_id
    
    def test_get_signature_not_found(self, client):
        """Test getting non-existent signature"""
        fake_id = uuid4()
        response = client.get(f"/federated/signatures/{fake_id}")
        assert response.status_code == 404
