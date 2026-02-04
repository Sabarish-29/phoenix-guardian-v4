"""
Tests for Incident API endpoints
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.api.dashboard.incidents import router, _incidents_store


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
    _incidents_store.clear()
    yield
    _incidents_store.clear()


class TestGetIncidents:
    """Tests for GET /incidents endpoint"""
    
    def test_get_incidents_empty(self, client):
        """Test getting incidents when none exist"""
        response = client.get("/incidents")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_incidents_with_data(self, client):
        """Test getting incidents list"""
        client.post("/incidents", json={
            "title": "Test Incident",
            "priority": "P1",
            "severity": "critical",
            "category": "ransomware"
        })
        
        response = client.get("/incidents")
        assert response.status_code == 200
        assert len(response.json()) == 1
    
    def test_get_incidents_filter_status(self, client):
        """Test filtering by status"""
        client.post("/incidents", json={
            "title": "Test",
            "priority": "P2",
            "severity": "high",
            "category": "malware"
        })
        
        response = client.get("/incidents?status=open")
        assert response.status_code == 200
        assert all(i["status"] == "open" for i in response.json())
    
    def test_get_incidents_filter_priority(self, client):
        """Test filtering by priority"""
        client.post("/incidents", json={"title": "P1", "priority": "P1", "severity": "critical", "category": "ransomware"})
        client.post("/incidents", json={"title": "P3", "priority": "P3", "severity": "medium", "category": "phishing"})
        
        response = client.get("/incidents?priority=P1")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["priority"] == "P1"
    
    def test_get_incidents_sorted_by_priority(self, client):
        """Test that incidents are sorted by priority"""
        client.post("/incidents", json={"title": "P3", "priority": "P3", "severity": "medium", "category": "phishing"})
        client.post("/incidents", json={"title": "P1", "priority": "P1", "severity": "critical", "category": "ransomware"})
        
        response = client.get("/incidents")
        incidents = response.json()
        assert incidents[0]["priority"] == "P1"
        assert incidents[1]["priority"] == "P3"


class TestGetIncident:
    """Tests for GET /incidents/{id} endpoint"""
    
    def test_get_incident_success(self, client):
        """Test getting a specific incident"""
        create_response = client.post("/incidents", json={
            "title": "Test Incident",
            "priority": "P2",
            "severity": "high",
            "category": "unauthorized_access"
        })
        incident_id = create_response.json()["id"]
        
        response = client.get(f"/incidents/{incident_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Test Incident"
    
    def test_get_incident_not_found(self, client):
        """Test getting non-existent incident"""
        fake_id = uuid4()
        response = client.get(f"/incidents/{fake_id}")
        assert response.status_code == 404


class TestCreateIncident:
    """Tests for POST /incidents endpoint"""
    
    def test_create_incident_success(self, client):
        """Test creating a new incident"""
        response = client.post("/incidents", json={
            "title": "Ransomware Attack",
            "description": "BlackCat ransomware detected",
            "priority": "P1",
            "severity": "critical",
            "category": "ransomware",
            "affectedAssets": ["EHR-Primary", "Lab-System"],
            "affectedDepartments": ["Radiology"]
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Ransomware Attack"
        assert data["status"] == "open"
        assert data["slaBreach"] == False
        assert len(data["affectedAssets"]) == 2
    
    def test_create_incident_minimal(self, client):
        """Test creating with minimal data"""
        response = client.post("/incidents", json={
            "title": "Minimal Incident",
            "priority": "P4",
            "severity": "low",
            "category": "policy_violation"
        })
        
        assert response.status_code == 201
    
    def test_create_incident_invalid_priority(self, client):
        """Test creating with invalid priority"""
        response = client.post("/incidents", json={
            "title": "Invalid",
            "priority": "P5",
            "severity": "high",
            "category": "malware"
        })
        
        assert response.status_code == 422


class TestUpdateIncidentStatus:
    """Tests for PUT /incidents/{id}/status endpoint"""
    
    def test_update_status_success(self, client):
        """Test updating incident status"""
        create_response = client.post("/incidents", json={
            "title": "Test",
            "priority": "P2",
            "severity": "high",
            "category": "malware"
        })
        incident_id = create_response.json()["id"]
        
        response = client.put(f"/incidents/{incident_id}/status", json={"status": "investigating"})
        assert response.status_code == 200
        assert response.json()["status"] == "investigating"
    
    def test_update_status_to_resolved(self, client):
        """Test updating status to resolved sets resolved_at"""
        create_response = client.post("/incidents", json={
            "title": "Test",
            "priority": "P3",
            "severity": "medium",
            "category": "phishing"
        })
        incident_id = create_response.json()["id"]
        
        response = client.put(f"/incidents/{incident_id}/status", json={"status": "resolved"})
        assert response.status_code == 200
        assert response.json()["resolvedAt"] is not None
    
    def test_update_status_invalid(self, client):
        """Test updating with invalid status"""
        create_response = client.post("/incidents", json={
            "title": "Test",
            "priority": "P2",
            "severity": "high",
            "category": "malware"
        })
        incident_id = create_response.json()["id"]
        
        response = client.put(f"/incidents/{incident_id}/status", json={"status": "invalid"})
        assert response.status_code == 422


class TestAssignIncident:
    """Tests for PUT /incidents/{id}/assign endpoint"""
    
    def test_assign_incident_success(self, client):
        """Test assigning an incident"""
        create_response = client.post("/incidents", json={
            "title": "Test",
            "priority": "P1",
            "severity": "critical",
            "category": "ransomware"
        })
        incident_id = create_response.json()["id"]
        
        response = client.put(f"/incidents/{incident_id}/assign", json={"userId": "user-1"})
        assert response.status_code == 200
        assert response.json()["assignee"]["id"] == "user-1"
        assert response.json()["assignee"]["name"] == "John Analyst"
    
    def test_assign_incident_user_not_found(self, client):
        """Test assigning to non-existent user"""
        create_response = client.post("/incidents", json={
            "title": "Test",
            "priority": "P2",
            "severity": "high",
            "category": "malware"
        })
        incident_id = create_response.json()["id"]
        
        response = client.put(f"/incidents/{incident_id}/assign", json={"userId": "nonexistent"})
        assert response.status_code == 404


class TestDeleteIncident:
    """Tests for DELETE /incidents/{id} endpoint"""
    
    def test_delete_incident_success(self, client):
        """Test deleting an incident"""
        create_response = client.post("/incidents", json={
            "title": "Test",
            "priority": "P3",
            "severity": "medium",
            "category": "phishing"
        })
        incident_id = create_response.json()["id"]
        
        response = client.delete(f"/incidents/{incident_id}")
        assert response.status_code == 204
        
        # Verify deleted
        get_response = client.get(f"/incidents/{incident_id}")
        assert get_response.status_code == 404


class TestContainmentActions:
    """Tests for POST /incidents/{id}/containment endpoint"""
    
    def test_add_containment_action(self, client):
        """Test adding a containment action"""
        create_response = client.post("/incidents", json={
            "title": "Test",
            "priority": "P1",
            "severity": "critical",
            "category": "ransomware"
        })
        incident_id = create_response.json()["id"]
        
        response = client.post(
            f"/incidents/{incident_id}/containment",
            params={"action": "Network isolation initiated"}
        )
        assert response.status_code == 200
        assert "Network isolation initiated" in response.json()["actions"]


class TestIncidentStats:
    """Tests for GET /incidents/stats/summary endpoint"""
    
    def test_get_stats(self, client):
        """Test getting incident stats"""
        client.post("/incidents", json={"title": "P1", "priority": "P1", "severity": "critical", "category": "ransomware"})
        client.post("/incidents", json={"title": "P2", "priority": "P2", "severity": "high", "category": "malware"})
        
        response = client.get("/incidents/stats/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["by_priority"]["P1"] == 1
        assert data["by_priority"]["P2"] == 1
        assert data["unassigned"] == 2
