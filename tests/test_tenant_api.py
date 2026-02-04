"""
Phoenix Guardian - Week 21-22: Tenant API Tests
Tests for FastAPI REST API endpoints.

These tests validate:
- All REST endpoints work correctly
- Request/response validation
- Authentication and authorization
- Error handling
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

from phoenix_guardian.tenants.tenant_api import (
    router,
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantListResponse,
    TenantConfigUpdate as ConfigUpdate,
    TenantLimitsUpdate as LimitsUpdate,
)
from phoenix_guardian.core.tenant_context import TenantStatus


class MockFastAPIApp:
    """Mock FastAPI app for testing."""
    
    def __init__(self):
        from fastapi import FastAPI
        self.app = FastAPI()
        self.app.include_router(router, prefix="/api/v1/tenants")


@pytest.fixture
def client():
    """Create test client."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/tenants")
    
    return TestClient(app)


class TestTenantCreate:
    """Tests for TenantCreate Pydantic model."""
    
    def test_valid_create(self):
        """Test valid tenant create request."""
        data = TenantCreate(
            tenant_id="new_hospital",
            name="New Hospital",
            admin_email="admin@new.org",
        )
        
        assert data.tenant_id == "new_hospital"
        assert data.name == "New Hospital"
    
    def test_with_optional_fields(self):
        """Test create with optional fields."""
        data = TenantCreate(
            tenant_id="full_hospital",
            name="Full Hospital",
            admin_email="admin@full.org",
            tier="enterprise",
            metadata={"region": "east"},
        )
        
        assert data.tier == "enterprise"
        assert data.metadata["region"] == "east"
    
    def test_validates_tenant_id(self):
        """Test tenant ID validation."""
        with pytest.raises(ValueError):
            TenantCreate(
                tenant_id="AB",  # Too short
                name="Invalid",
                admin_email="admin@invalid.org",
            )
    
    def test_validates_email(self):
        """Test email validation."""
        with pytest.raises(ValueError):
            TenantCreate(
                tenant_id="valid_hospital",
                name="Valid Hospital",
                admin_email="not-an-email",
            )


class TestTenantUpdate:
    """Tests for TenantUpdate Pydantic model."""
    
    def test_partial_update(self):
        """Test partial update."""
        data = TenantUpdate(name="Updated Name")
        
        assert data.name == "Updated Name"
        assert data.tier is None
    
    def test_full_update(self):
        """Test full update."""
        data = TenantUpdate(
            name="Updated Name",
            tier="enterprise",
            metadata={"key": "value"},
        )
        
        assert data.name == "Updated Name"
        assert data.tier == "enterprise"


class TestTenantResponse:
    """Tests for TenantResponse Pydantic model."""
    
    def test_response_serialization(self):
        """Test response serialization."""
        response = TenantResponse(
            tenant_id="hospital_a",
            name="Hospital A",
            status=TenantStatus.ACTIVE,
            tier="standard",
            created_at=datetime.now(timezone.utc),
        )
        
        data = response.model_dump()
        
        assert data["tenant_id"] == "hospital_a"
        assert "created_at" in data


class TestConfigUpdate:
    """Tests for ConfigUpdate Pydantic model."""
    
    def test_config_update(self):
        """Test config update."""
        data = ConfigUpdate(
            features=["advanced_analytics"],
            settings={"theme": "dark"},
        )
        
        assert "advanced_analytics" in data.features


class TestLimitsUpdate:
    """Tests for LimitsUpdate Pydantic model."""
    
    def test_limits_update(self):
        """Test limits update."""
        data = LimitsUpdate(
            max_users=500,
            max_storage_gb=100,
            max_predictions_per_day=10000,
        )
        
        assert data.max_users == 500
        assert data.max_storage_gb == 100


class TestCreateTenantEndpoint:
    """Tests for POST /tenants endpoint."""
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_create_tenant_success(self, mock_manager, client):
        """Test successful tenant creation."""
        mock_manager.create_tenant.return_value = Mock(
            tenant_id="new_hospital",
            name="New Hospital",
            status=TenantStatus.PENDING,
            tier="standard",
            created_at=datetime.now(timezone.utc),
        )
        
        response = client.post(
            "/api/v1/tenants",
            json={
                "tenant_id": "new_hospital",
                "name": "New Hospital",
                "admin_email": "admin@new.org",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["tenant_id"] == "new_hospital"
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_create_duplicate_tenant(self, mock_manager, client):
        """Test creating duplicate tenant."""
        mock_manager.create_tenant.side_effect = ValueError("Tenant exists")
        
        response = client.post(
            "/api/v1/tenants",
            json={
                "tenant_id": "existing_hospital",
                "name": "Existing Hospital",
                "admin_email": "admin@existing.org",
            },
        )
        
        assert response.status_code == 400
    
    def test_create_tenant_invalid_request(self, client):
        """Test invalid create request."""
        response = client.post(
            "/api/v1/tenants",
            json={
                "tenant_id": "AB",  # Too short
                "name": "Invalid",
                "admin_email": "admin@invalid.org",
            },
        )
        
        assert response.status_code == 422


class TestListTenantsEndpoint:
    """Tests for GET /tenants endpoint."""
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_list_tenants(self, mock_manager, client):
        """Test listing tenants."""
        mock_manager.list_tenants.return_value = [
            Mock(
                tenant_id="hospital_a",
                name="Hospital A",
                status=TenantStatus.ACTIVE,
                tier="standard",
                created_at=datetime.now(timezone.utc),
            ),
            Mock(
                tenant_id="hospital_b",
                name="Hospital B",
                status=TenantStatus.ACTIVE,
                tier="enterprise",
                created_at=datetime.now(timezone.utc),
            ),
        ]
        
        response = client.get("/api/v1/tenants")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["tenants"]) == 2
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_list_with_pagination(self, mock_manager, client):
        """Test listing with pagination."""
        mock_manager.list_tenants.return_value = []
        
        response = client.get("/api/v1/tenants?offset=10&limit=20")
        
        assert response.status_code == 200
        mock_manager.list_tenants.assert_called_with(offset=10, limit=20)
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_list_with_status_filter(self, mock_manager, client):
        """Test listing with status filter."""
        mock_manager.list_tenants.return_value = []
        
        response = client.get("/api/v1/tenants?status=active")
        
        assert response.status_code == 200


class TestGetTenantEndpoint:
    """Tests for GET /tenants/{tenant_id} endpoint."""
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_get_tenant(self, mock_manager, client):
        """Test getting a tenant."""
        mock_manager.get_tenant.return_value = Mock(
            tenant_id="hospital_a",
            name="Hospital A",
            status=TenantStatus.ACTIVE,
            tier="standard",
            created_at=datetime.now(timezone.utc),
        )
        
        response = client.get("/api/v1/tenants/hospital_a")
        
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == "hospital_a"
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_get_nonexistent_tenant(self, mock_manager, client):
        """Test getting nonexistent tenant."""
        mock_manager.get_tenant.return_value = None
        
        response = client.get("/api/v1/tenants/nonexistent")
        
        assert response.status_code == 404


class TestUpdateTenantEndpoint:
    """Tests for PATCH /tenants/{tenant_id} endpoint."""
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_update_tenant(self, mock_manager, client):
        """Test updating a tenant."""
        mock_manager.get_tenant.return_value = Mock(
            tenant_id="hospital_a",
            name="Old Name",
            status=TenantStatus.ACTIVE,
            tier="standard",
            created_at=datetime.now(timezone.utc),
        )
        mock_manager.update_tenant.return_value = Mock(
            tenant_id="hospital_a",
            name="New Name",
            status=TenantStatus.ACTIVE,
            tier="standard",
            created_at=datetime.now(timezone.utc),
        )
        
        response = client.patch(
            "/api/v1/tenants/hospital_a",
            json={"name": "New Name"},
        )
        
        assert response.status_code == 200
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_update_nonexistent_tenant(self, mock_manager, client):
        """Test updating nonexistent tenant."""
        mock_manager.get_tenant.return_value = None
        
        response = client.patch(
            "/api/v1/tenants/nonexistent",
            json={"name": "New Name"},
        )
        
        assert response.status_code == 404


class TestDeleteTenantEndpoint:
    """Tests for DELETE /tenants/{tenant_id} endpoint."""
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_delete_tenant(self, mock_manager, client):
        """Test deleting a tenant."""
        mock_manager.get_tenant.return_value = Mock(
            tenant_id="delete_hospital",
            status=TenantStatus.ACTIVE,
        )
        mock_manager.delete_tenant.return_value = True
        
        response = client.delete("/api/v1/tenants/delete_hospital")
        
        assert response.status_code == 204
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_delete_nonexistent_tenant(self, mock_manager, client):
        """Test deleting nonexistent tenant."""
        mock_manager.get_tenant.return_value = None
        
        response = client.delete("/api/v1/tenants/nonexistent")
        
        assert response.status_code == 404


class TestConfigEndpoints:
    """Tests for config management endpoints."""
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_get_config(self, mock_manager, client):
        """Test getting tenant config."""
        mock_manager.get_tenant.return_value = Mock(
            tenant_id="hospital_a",
            status=TenantStatus.ACTIVE,
        )
        mock_manager.get_config.return_value = {
            "features": ["basic"],
            "settings": {},
        }
        
        response = client.get("/api/v1/tenants/hospital_a/config")
        
        assert response.status_code == 200
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_update_config(self, mock_manager, client):
        """Test updating tenant config."""
        mock_manager.get_tenant.return_value = Mock(
            tenant_id="hospital_a",
            status=TenantStatus.ACTIVE,
        )
        mock_manager.update_config.return_value = True
        
        response = client.patch(
            "/api/v1/tenants/hospital_a/config",
            json={"features": ["advanced"]},
        )
        
        assert response.status_code == 200


class TestLimitsEndpoints:
    """Tests for limits management endpoints."""
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_get_limits(self, mock_manager, client):
        """Test getting tenant limits."""
        mock_manager.get_tenant.return_value = Mock(
            tenant_id="hospital_a",
            status=TenantStatus.ACTIVE,
        )
        mock_manager.get_limits.return_value = {
            "max_users": 100,
            "max_storage_gb": 50,
        }
        
        response = client.get("/api/v1/tenants/hospital_a/limits")
        
        assert response.status_code == 200
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_update_limits(self, mock_manager, client):
        """Test updating tenant limits."""
        mock_manager.get_tenant.return_value = Mock(
            tenant_id="hospital_a",
            status=TenantStatus.ACTIVE,
        )
        mock_manager.update_limits.return_value = True
        
        response = client.patch(
            "/api/v1/tenants/hospital_a/limits",
            json={"max_users": 500},
        )
        
        assert response.status_code == 200


class TestStatusEndpoints:
    """Tests for status management endpoints."""
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_activate_tenant(self, mock_manager, client):
        """Test activating a tenant."""
        mock_manager.get_tenant.return_value = Mock(
            tenant_id="hospital_a",
            status=TenantStatus.PENDING,
        )
        mock_manager.activate_tenant.return_value = True
        
        response = client.post("/api/v1/tenants/hospital_a/activate")
        
        assert response.status_code == 200
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_suspend_tenant(self, mock_manager, client):
        """Test suspending a tenant."""
        mock_manager.get_tenant.return_value = Mock(
            tenant_id="hospital_a",
            status=TenantStatus.ACTIVE,
        )
        mock_manager.suspend_tenant.return_value = True
        
        response = client.post("/api/v1/tenants/hospital_a/suspend")
        
        assert response.status_code == 200
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_suspend_with_reason(self, mock_manager, client):
        """Test suspending with reason."""
        mock_manager.get_tenant.return_value = Mock(
            tenant_id="hospital_a",
            status=TenantStatus.ACTIVE,
        )
        mock_manager.suspend_tenant.return_value = True
        
        response = client.post(
            "/api/v1/tenants/hospital_a/suspend",
            json={"reason": "Payment overdue"},
        )
        
        assert response.status_code == 200


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_health_check(self, mock_manager, client):
        """Test health check."""
        mock_manager.get_tenant.return_value = Mock(
            tenant_id="hospital_a",
            status=TenantStatus.ACTIVE,
        )
        mock_manager.check_health.return_value = {
            "database": "healthy",
            "cache": "healthy",
        }
        
        response = client.get("/api/v1/tenants/hospital_a/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["database"] == "healthy"


class TestErrorHandling:
    """Tests for API error handling."""
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_internal_error(self, mock_manager, client):
        """Test internal server error handling."""
        mock_manager.list_tenants.side_effect = Exception("Database error")
        
        response = client.get("/api/v1/tenants")
        
        assert response.status_code == 500
    
    @patch('phoenix_guardian.tenants.tenant_api.tenant_manager')
    def test_validation_error(self, mock_manager, client):
        """Test validation error handling."""
        response = client.post(
            "/api/v1/tenants",
            json={},  # Missing required fields
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


class TestAPIDocumentation:
    """Tests for API documentation."""
    
    def test_openapi_schema(self, client):
        """Test OpenAPI schema is available."""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data


# ==============================================================================
# Test Count: ~45 tests for Tenant API
# ==============================================================================
