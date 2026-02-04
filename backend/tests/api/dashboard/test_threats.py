"""
Tests for Threat Feed API endpoints
"""

import pytest
from datetime import datetime
from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.api.dashboard.threats import router, _threats_store


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


@pytest.fixture(autouse=True)
def clear_store():
    """Clear store before each test"""
    _threats_store.clear()
    yield
    _threats_store.clear()


class TestGetThreats:
    """Tests for GET /threats endpoint"""
    
    def test_get_threats_empty(self, client):
        """Test getting threats when none exist"""
        response = client.get("/threats")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_threats_with_data(self, client):
        """Test getting threats list"""
        # Create test threat
        client.post("/threats", json={
            "title": "Test Threat",
            "severity": "high",
            "threatType": "malware"
        })
        
        response = client.get("/threats")
        assert response.status_code == 200
        assert len(response.json()) == 1
    
    def test_get_threats_filter_severity(self, client):
        """Test filtering threats by severity"""
        client.post("/threats", json={"title": "Critical", "severity": "critical", "threatType": "ransomware"})
        client.post("/threats", json={"title": "Low", "severity": "low", "threatType": "phishing"})
        
        response = client.get("/threats?severity=critical")
        assert response.status_code == 200
        threats = response.json()
        assert len(threats) == 1
        assert threats[0]["severity"] == "critical"
    
    def test_get_threats_filter_status(self, client):
        """Test filtering threats by status"""
        client.post("/threats", json={"title": "Test", "severity": "high", "threatType": "malware"})
        
        response = client.get("/threats?status=active")
        assert response.status_code == 200
        assert all(t["status"] == "active" for t in response.json())
    
    def test_get_threats_pagination(self, client):
        """Test pagination"""
        for i in range(5):
            client.post("/threats", json={"title": f"Threat {i}", "severity": "high", "threatType": "malware"})
        
        response = client.get("/threats?limit=2&offset=0")
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestGetThreat:
    """Tests for GET /threats/{id} endpoint"""
    
    def test_get_threat_success(self, client):
        """Test getting a specific threat"""
        create_response = client.post("/threats", json={
            "title": "Test Threat",
            "severity": "critical",
            "threatType": "ransomware"
        })
        threat_id = create_response.json()["id"]
        
        response = client.get(f"/threats/{threat_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Test Threat"
    
    def test_get_threat_not_found(self, client):
        """Test getting non-existent threat"""
        fake_id = uuid4()
        response = client.get(f"/threats/{fake_id}")
        assert response.status_code == 404


class TestCreateThreat:
    """Tests for POST /threats endpoint"""
    
    def test_create_threat_success(self, client):
        """Test creating a new threat"""
        response = client.post("/threats", json={
            "title": "New Threat",
            "description": "Test description",
            "severity": "high",
            "threatType": "malware",
            "sourceIp": "192.168.1.1",
            "targetSystem": "EHR"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Threat"
        assert data["status"] == "active"
        assert data["acknowledged"] == False
    
    def test_create_threat_minimal(self, client):
        """Test creating threat with minimal data"""
        response = client.post("/threats", json={
            "title": "Minimal Threat",
            "severity": "low",
            "threatType": "reconnaissance"
        })
        
        assert response.status_code == 201
    
    def test_create_threat_invalid_severity(self, client):
        """Test creating threat with invalid severity"""
        response = client.post("/threats", json={
            "title": "Test",
            "severity": "invalid",
            "threatType": "malware"
        })
        
        assert response.status_code == 422


class TestAcknowledgeThreat:
    """Tests for POST /threats/{id}/acknowledge endpoint"""
    
    def test_acknowledge_threat_success(self, client):
        """Test acknowledging a threat"""
        create_response = client.post("/threats", json={
            "title": "Test",
            "severity": "high",
            "threatType": "malware"
        })
        threat_id = create_response.json()["id"]
        
        response = client.post(f"/threats/{threat_id}/acknowledge")
        assert response.status_code == 200
        assert response.json()["success"] == True
        
        # Verify threat is acknowledged
        get_response = client.get(f"/threats/{threat_id}")
        assert get_response.json()["acknowledged"] == True
    
    def test_acknowledge_threat_not_found(self, client):
        """Test acknowledging non-existent threat"""
        fake_id = uuid4()
        response = client.post(f"/threats/{fake_id}/acknowledge")
        assert response.status_code == 404


class TestUpdateThreatStatus:
    """Tests for PUT /threats/{id}/status endpoint"""
    
    def test_update_status_success(self, client):
        """Test updating threat status"""
        create_response = client.post("/threats", json={
            "title": "Test",
            "severity": "high",
            "threatType": "malware"
        })
        threat_id = create_response.json()["id"]
        
        response = client.put(f"/threats/{threat_id}/status", json={"status": "mitigated"})
        assert response.status_code == 200
        assert response.json()["status"] == "mitigated"
    
    def test_update_status_invalid(self, client):
        """Test updating with invalid status"""
        create_response = client.post("/threats", json={
            "title": "Test",
            "severity": "high",
            "threatType": "malware"
        })
        threat_id = create_response.json()["id"]
        
        response = client.put(f"/threats/{threat_id}/status", json={"status": "invalid"})
        assert response.status_code == 422


class TestDeleteThreat:
    """Tests for DELETE /threats/{id} endpoint"""
    
    def test_delete_threat_success(self, client):
        """Test deleting a threat"""
        create_response = client.post("/threats", json={
            "title": "Test",
            "severity": "high",
            "threatType": "malware"
        })
        threat_id = create_response.json()["id"]
        
        response = client.delete(f"/threats/{threat_id}")
        assert response.status_code == 204
        
        # Verify deleted
        get_response = client.get(f"/threats/{threat_id}")
        assert get_response.status_code == 404
    
    def test_delete_threat_not_found(self, client):
        """Test deleting non-existent threat"""
        fake_id = uuid4()
        response = client.delete(f"/threats/{fake_id}")
        assert response.status_code == 404


class TestThreatStats:
    """Tests for GET /threats/stats/summary endpoint"""
    
    def test_get_stats_empty(self, client):
        """Test stats with no threats"""
        response = client.get("/threats/stats/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
    
    def test_get_stats_with_data(self, client):
        """Test stats with threats"""
        client.post("/threats", json={"title": "T1", "severity": "critical", "threatType": "ransomware"})
        client.post("/threats", json={"title": "T2", "severity": "high", "threatType": "malware"})
        
        response = client.get("/threats/stats/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["by_severity"]["critical"] == 1
        assert data["by_severity"]["high"] == 1
