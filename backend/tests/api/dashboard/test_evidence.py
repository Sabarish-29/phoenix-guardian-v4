"""
Tests for Evidence API endpoints
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.api.dashboard.evidence import router, _packages_store


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
    _packages_store.clear()
    yield
    _packages_store.clear()


class TestGetPackages:
    """Tests for GET /evidence/packages endpoint"""
    
    def test_get_packages_empty(self, client):
        """Test getting packages when none exist"""
        response = client.get("/evidence/packages")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_packages_with_data(self, client):
        """Test getting packages list"""
        incident_id = uuid4()
        client.post("/evidence/packages", json={
            "incidentId": str(incident_id),
            "incidentTitle": "Test Incident",
            "items": []
        })
        
        response = client.get("/evidence/packages")
        assert response.status_code == 200
        assert len(response.json()) == 1
    
    def test_get_packages_filter_status(self, client):
        """Test filtering by status"""
        incident_id = uuid4()
        client.post("/evidence/packages", json={
            "incidentId": str(incident_id),
            "incidentTitle": "Test",
            "items": []
        })
        
        response = client.get("/evidence/packages?status=ready")
        assert response.status_code == 200


class TestGetPackage:
    """Tests for GET /evidence/packages/{id} endpoint"""
    
    def test_get_package_success(self, client):
        """Test getting a specific package"""
        incident_id = uuid4()
        create_response = client.post("/evidence/packages", json={
            "incidentId": str(incident_id),
            "incidentTitle": "Test Incident",
            "items": []
        })
        package_id = create_response.json()["id"]
        
        response = client.get(f"/evidence/packages/{package_id}")
        assert response.status_code == 200
        assert response.json()["incidentTitle"] == "Test Incident"
    
    def test_get_package_not_found(self, client):
        """Test getting non-existent package"""
        fake_id = uuid4()
        response = client.get(f"/evidence/packages/{fake_id}")
        assert response.status_code == 404


class TestCreatePackage:
    """Tests for POST /evidence/packages endpoint"""
    
    def test_create_package_success(self, client):
        """Test creating a new package"""
        incident_id = uuid4()
        response = client.post("/evidence/packages", json={
            "incidentId": str(incident_id),
            "incidentTitle": "Ransomware Investigation",
            "items": [
                {"type": "network_logs", "name": "network.pcap", "size": 1024000},
                {"type": "system_logs", "name": "system.log", "size": 512000}
            ]
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["incidentTitle"] == "Ransomware Investigation"
        assert len(data["items"]) == 2
        assert data["totalSize"] == 1536000
    
    def test_create_package_minimal(self, client):
        """Test creating with minimal data"""
        incident_id = uuid4()
        response = client.post("/evidence/packages", json={
            "incidentId": str(incident_id),
            "incidentTitle": "Minimal",
            "items": []
        })
        
        assert response.status_code == 201


class TestVerifyIntegrity:
    """Tests for POST /evidence/packages/{id}/verify endpoint"""
    
    def test_verify_integrity_success(self, client):
        """Test verifying package integrity"""
        incident_id = uuid4()
        create_response = client.post("/evidence/packages", json={
            "incidentId": str(incident_id),
            "incidentTitle": "Test",
            "items": [{"type": "logs", "name": "test.log", "size": 1000}]
        })
        package_id = create_response.json()["id"]
        
        response = client.post(f"/evidence/packages/{package_id}/verify")
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] == True
        assert data["items_checked"] == 1
    
    def test_verify_integrity_not_found(self, client):
        """Test verifying non-existent package"""
        fake_id = uuid4()
        response = client.post(f"/evidence/packages/{fake_id}/verify")
        assert response.status_code == 404


class TestDownloadPackage:
    """Tests for GET /evidence/packages/{id}/download endpoint"""
    
    def test_download_package_success(self, client):
        """Test downloading a package"""
        incident_id = uuid4()
        create_response = client.post("/evidence/packages", json={
            "incidentId": str(incident_id),
            "incidentTitle": "Test",
            "items": []
        })
        package_id = create_response.json()["id"]
        
        response = client.get(f"/evidence/packages/{package_id}/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
    
    def test_download_package_not_found(self, client):
        """Test downloading non-existent package"""
        fake_id = uuid4()
        response = client.get(f"/evidence/packages/{fake_id}/download")
        assert response.status_code == 404


class TestDeletePackage:
    """Tests for DELETE /evidence/packages/{id} endpoint"""
    
    def test_delete_package_success(self, client):
        """Test deleting a package"""
        incident_id = uuid4()
        create_response = client.post("/evidence/packages", json={
            "incidentId": str(incident_id),
            "incidentTitle": "Test",
            "items": []
        })
        package_id = create_response.json()["id"]
        
        response = client.delete(f"/evidence/packages/{package_id}")
        assert response.status_code == 204
        
        # Verify deleted
        get_response = client.get(f"/evidence/packages/{package_id}")
        assert get_response.status_code == 404


class TestEvidenceStats:
    """Tests for GET /evidence/stats/summary endpoint"""
    
    def test_get_stats(self, client):
        """Test getting evidence stats"""
        incident_id = uuid4()
        client.post("/evidence/packages", json={
            "incidentId": str(incident_id),
            "incidentTitle": "Test",
            "items": [{"type": "logs", "name": "test.log", "size": 1000}]
        })
        
        response = client.get("/evidence/stats/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_packages"] == 1
        assert data["total_items"] == 1
        assert data["total_size_bytes"] == 1000
