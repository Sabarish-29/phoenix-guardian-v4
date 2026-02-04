"""
Tests for Honeytoken API endpoints
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.api.dashboard.honeytokens import router, _honeytokens_store, _triggers_store


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
    """Clear stores before each test"""
    _honeytokens_store.clear()
    _triggers_store.clear()
    yield
    _honeytokens_store.clear()
    _triggers_store.clear()


class TestGetHoneytokens:
    """Tests for GET /honeytokens endpoint"""
    
    def test_get_honeytokens_empty(self, client):
        """Test getting honeytokens when none exist"""
        response = client.get("/honeytokens")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_honeytokens_with_data(self, client):
        """Test getting honeytokens list"""
        client.post("/honeytokens", json={
            "name": "Test Token",
            "type": "patient_record",
            "alertLevel": "high"
        })
        
        response = client.get("/honeytokens")
        assert response.status_code == 200
        assert len(response.json()) == 1
    
    def test_get_honeytokens_filter_status(self, client):
        """Test filtering by status"""
        client.post("/honeytokens", json={"name": "Active", "type": "patient_record", "alertLevel": "high"})
        
        response = client.get("/honeytokens?status=active")
        assert response.status_code == 200
        assert all(h["status"] == "active" for h in response.json())
    
    def test_get_honeytokens_filter_type(self, client):
        """Test filtering by type"""
        client.post("/honeytokens", json={"name": "Patient", "type": "patient_record", "alertLevel": "high"})
        client.post("/honeytokens", json={"name": "API", "type": "api_key", "alertLevel": "medium"})
        
        response = client.get("/honeytokens?type=patient_record")
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestGetHoneytoken:
    """Tests for GET /honeytokens/{id} endpoint"""
    
    def test_get_honeytoken_success(self, client):
        """Test getting a specific honeytoken"""
        create_response = client.post("/honeytokens", json={
            "name": "Test Token",
            "type": "admin_credential",
            "alertLevel": "critical"
        })
        honeytoken_id = create_response.json()["id"]
        
        response = client.get(f"/honeytokens/{honeytoken_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Test Token"
    
    def test_get_honeytoken_not_found(self, client):
        """Test getting non-existent honeytoken"""
        fake_id = uuid4()
        response = client.get(f"/honeytokens/{fake_id}")
        assert response.status_code == 404


class TestCreateHoneytoken:
    """Tests for POST /honeytokens endpoint"""
    
    def test_create_honeytoken_success(self, client):
        """Test creating a new honeytoken"""
        response = client.post("/honeytokens", json={
            "name": "VIP Patient Record",
            "type": "patient_record",
            "description": "Decoy patient record",
            "location": "/data/patients/vip",
            "alertLevel": "critical"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "VIP Patient Record"
        assert data["status"] == "active"
        assert data["triggerCount"] == 0
    
    def test_create_honeytoken_minimal(self, client):
        """Test creating with minimal data"""
        response = client.post("/honeytokens", json={
            "name": "Minimal",
            "type": "database",
            "alertLevel": "low"
        })
        
        assert response.status_code == 201
    
    def test_create_honeytoken_invalid_type(self, client):
        """Test creating with invalid type"""
        response = client.post("/honeytokens", json={
            "name": "Invalid",
            "type": "invalid_type",
            "alertLevel": "high"
        })
        
        assert response.status_code == 422


class TestUpdateHoneytoken:
    """Tests for PUT /honeytokens/{id} endpoint"""
    
    def test_update_honeytoken_success(self, client):
        """Test updating a honeytoken"""
        create_response = client.post("/honeytokens", json={
            "name": "Test",
            "type": "api_key",
            "alertLevel": "high"
        })
        honeytoken_id = create_response.json()["id"]
        
        response = client.put(f"/honeytokens/{honeytoken_id}", json={"status": "inactive"})
        assert response.status_code == 200
        assert response.json()["status"] == "inactive"
    
    def test_update_honeytoken_not_found(self, client):
        """Test updating non-existent honeytoken"""
        fake_id = uuid4()
        response = client.put(f"/honeytokens/{fake_id}", json={"status": "inactive"})
        assert response.status_code == 404


class TestDeleteHoneytoken:
    """Tests for DELETE /honeytokens/{id} endpoint"""
    
    def test_delete_honeytoken_success(self, client):
        """Test deleting a honeytoken"""
        create_response = client.post("/honeytokens", json={
            "name": "Test",
            "type": "medication",
            "alertLevel": "medium"
        })
        honeytoken_id = create_response.json()["id"]
        
        response = client.delete(f"/honeytokens/{honeytoken_id}")
        assert response.status_code == 204
        
        # Verify deleted
        get_response = client.get(f"/honeytokens/{honeytoken_id}")
        assert get_response.status_code == 404


class TestTriggers:
    """Tests for trigger endpoints"""
    
    def test_get_triggers_empty(self, client):
        """Test getting triggers when none exist"""
        create_response = client.post("/honeytokens", json={
            "name": "Test",
            "type": "patient_record",
            "alertLevel": "high"
        })
        honeytoken_id = create_response.json()["id"]
        
        response = client.get(f"/honeytokens/{honeytoken_id}/triggers")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_record_trigger(self, client):
        """Test recording a trigger event"""
        create_response = client.post("/honeytokens", json={
            "name": "Test Token",
            "type": "admin_credential",
            "alertLevel": "critical"
        })
        honeytoken_id = create_response.json()["id"]
        
        response = client.post(
            f"/honeytokens/{honeytoken_id}/trigger",
            params={
                "source_ip": "192.168.1.100",
                "access_type": "read",
                "target_system": "AD-Server",
                "source_user": "suspicious_user"
            }
        )
        
        assert response.status_code == 200
        trigger = response.json()
        assert trigger["sourceIp"] == "192.168.1.100"
        assert trigger["accessType"] == "read"
        
        # Verify trigger count increased
        get_response = client.get(f"/honeytokens/{honeytoken_id}")
        assert get_response.json()["triggerCount"] == 1
    
    def test_get_recent_triggers(self, client):
        """Test getting recent triggers across all honeytokens"""
        # Create and trigger multiple honeytokens
        for i in range(3):
            create_response = client.post("/honeytokens", json={
                "name": f"Token {i}",
                "type": "patient_record",
                "alertLevel": "high"
            })
            honeytoken_id = create_response.json()["id"]
            client.post(
                f"/honeytokens/{honeytoken_id}/trigger",
                params={"source_ip": f"192.168.1.{i}", "access_type": "read", "target_system": "EHR"}
            )
        
        response = client.get("/honeytokens/triggers/recent")
        assert response.status_code == 200
        assert len(response.json()) == 3


class TestHoneytokenStats:
    """Tests for GET /honeytokens/stats/summary endpoint"""
    
    def test_get_stats(self, client):
        """Test getting honeytoken stats"""
        client.post("/honeytokens", json={"name": "T1", "type": "patient_record", "alertLevel": "high"})
        client.post("/honeytokens", json={"name": "T2", "type": "api_key", "alertLevel": "medium"})
        
        response = client.get("/honeytokens/stats/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_honeytokens"] == 2
        assert data["active"] == 2
        assert data["by_type"]["patient_record"] == 1
        assert data["by_type"]["api_key"] == 1
