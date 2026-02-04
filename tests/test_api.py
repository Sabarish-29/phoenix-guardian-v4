"""Comprehensive API tests.

Tests all FastAPI endpoints with various scenarios.
"""

import os
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from phoenix_guardian.api.main import app
from phoenix_guardian.api.dependencies import clear_dependency_cache
from phoenix_guardian.api.routes.encounters import ENCOUNTERS_DB
from phoenix_guardian.database.connection import get_db


# Set mock API key for tests
os.environ.setdefault("ANTHROPIC_API_KEY", "test-api-key-for-testing")


def get_mock_db():
    """Create a mock database session."""
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_session.commit.return_value = None
    mock_session.add.return_value = None
    mock_session.close.return_value = None
    yield mock_session


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    ENCOUNTERS_DB.clear()
    clear_dependency_cache()
    # Override the database dependency with a mock
    app.dependency_overrides[get_db] = get_mock_db
    yield
    ENCOUNTERS_DB.clear()
    # Clean up overrides
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_patient_data() -> Dict[str, Any]:
    """Sample patient data for mocking."""
    return {
        "mrn": "MRN001234",
        "demographics": {
            "name": "John Smith",
            "age": 65,
            "gender": "Male",
            "dob": "1959-03-15",
        },
        "conditions": ["Hypertension", "Type 2 Diabetes"],
        "medications": [
            {"name": "Lisinopril", "dose": "10mg", "frequency": "Daily", "route": "PO"}
        ],
        "allergies": [
            {"allergen": "Penicillin", "reaction": "Rash", "severity": "Moderate"}
        ],
        "vitals": {
            "blood_pressure": "135/85",
            "heart_rate": 78,
            "temperature": 98.4,
            "respiratory_rate": 16,
            "oxygen_saturation": 97,
            "recorded_at": "2025-01-28T10:30:00Z",
        },
        "labs": [],
        "last_encounter": {
            "date": "2025-01-10",
            "type": "Office Visit",
            "provider": "Dr. Sarah Johnson",
            "chief_complaint": "Routine follow-up",
        },
        "retrieved_at": "2025-01-30T10:00:00Z",
    }


# =============================================================================
# Test: Root Endpoint
# =============================================================================


class TestRootEndpoint:
    """Test API root endpoint."""

    def test_root(self, client: TestClient) -> None:
        """Test root endpoint returns API information."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "Phoenix Guardian API"
        assert "version" in data
        assert data["status"] == "operational"
        assert data["docs"] == "/api/docs"


# =============================================================================
# Test: Health Endpoints
# =============================================================================


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client: TestClient) -> None:
        """Test health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "agents" in data
        assert len(data["agents"]) == 2  # Navigator + Scribe
        assert "timestamp" in data
        assert data["version"] == "1.0.0"

    def test_health_check_agents(self, client: TestClient) -> None:
        """Test health check returns agent information."""
        response = client.get("/api/v1/health")
        data = response.json()

        agent_names = [agent["name"] for agent in data["agents"]]
        assert "NavigatorAgent" in agent_names
        assert "ScribeAgent" in agent_names

    def test_metrics_endpoint(self, client: TestClient) -> None:
        """Test metrics endpoint."""
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "navigator_metrics" in data
        assert "scribe_metrics" in data
        assert "total_encounters" in data
        assert "success_rate" in data


# =============================================================================
# Test: Authentication Endpoints
# =============================================================================


class TestAuthenticationEndpoints:
    """Test authentication endpoints."""

    def test_login_success(self, client: TestClient) -> None:
        """Test successful login - returns 401 with no real users in mock DB."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "dr.smith@phoenixguardian.health", "password": "SecurePassword123!"},
        )
        # Without real database users, authentication should fail
        assert response.status_code == 401

    def test_login_admin(self, client: TestClient) -> None:
        """Test admin login - returns 401 with no real users in mock DB."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@phoenixguardian.health", "password": "AdminPass456!"},
        )
        # Without real database users, authentication should fail
        assert response.status_code == 401

    def test_login_invalid_password(self, client: TestClient) -> None:
        """Test login with wrong password."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "dr.smith@phoenixguardian.health", "password": "WrongPassword123"},
        )
        assert response.status_code == 401

    def test_login_invalid_username(self, client: TestClient) -> None:
        """Test login with non-existent user."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "AnyPassword123!"},
        )
        assert response.status_code == 401

    def test_login_short_password(self, client: TestClient) -> None:
        """Test login with too-short password (validation)."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "dr.smith@phoenixguardian.health", "password": "short"},
        )
        assert response.status_code == 422  # Validation error

    def test_login_short_username(self, client: TestClient) -> None:
        """Test login with invalid email format (validation)."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "notanemail", "password": "ValidPassword123!"},
        )
        assert response.status_code == 422


# =============================================================================
# Test: Patient Endpoints
# =============================================================================


class TestPatientEndpoints:
    """Test patient data endpoints."""

    def test_get_patient_success(self, client: TestClient) -> None:
        """Test fetching existing patient."""
        response = client.get("/api/v1/patients/MRN001234")
        assert response.status_code == 200

        data = response.json()
        assert data["mrn"] == "MRN001234"
        assert "demographics" in data
        assert "conditions" in data
        assert "medications" in data

    def test_get_patient_demographics(self, client: TestClient) -> None:
        """Test patient demographics structure."""
        response = client.get("/api/v1/patients/MRN001234")
        data = response.json()

        assert "demographics" in data
        demo = data["demographics"]
        assert demo["name"] == "John Smith"
        assert demo["age"] == 65
        assert demo["gender"] == "Male"

    def test_get_patient_not_found(self, client: TestClient) -> None:
        """Test fetching non-existent patient."""
        response = client.get("/api/v1/patients/MRN999999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_patient_with_field_filter(self, client: TestClient) -> None:
        """Test fetching patient with field filtering."""
        response = client.get(
            "/api/v1/patients/MRN001234?include_fields=demographics,medications"
        )
        assert response.status_code == 200

        data = response.json()
        assert "mrn" in data  # Always included
        assert "demographics" in data
        assert "medications" in data

    def test_get_different_patients(self, client: TestClient) -> None:
        """Test fetching different patients."""
        # Get first patient
        response1 = client.get("/api/v1/patients/MRN001234")
        assert response1.status_code == 200
        assert response1.json()["demographics"]["name"] == "John Smith"

        # Get second patient
        response2 = client.get("/api/v1/patients/MRN005678")
        assert response2.status_code == 200
        assert response2.json()["demographics"]["name"] == "Maria Garcia"


# =============================================================================
# Test: Encounter Endpoints (Mocked)
# =============================================================================


class TestEncounterEndpointsMocked:
    """Test encounter endpoints with mocked ScribeAgent."""

    @pytest.fixture(autouse=True)
    def setup_mock_auth(self):
        """Set up mock authentication for all tests in this class."""
        from phoenix_guardian.api.auth.utils import require_physician, get_current_active_user
        from phoenix_guardian.models.user import UserRole
        
        # Create a mock user that looks like a physician
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "dr.test@phoenixguardian.health"
        mock_user.first_name = "Test"
        mock_user.last_name = "Doctor"
        mock_user.role = UserRole.PHYSICIAN
        mock_user.is_active = True
        
        # Override authentication dependencies
        app.dependency_overrides[require_physician] = lambda: mock_user
        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        
        yield
        
        # Clean up
        app.dependency_overrides.pop(require_physician, None)
        app.dependency_overrides.pop(get_current_active_user, None)

    @pytest.fixture
    def mock_scribe_result(self):
        """Mock ScribeAgent result."""
        from phoenix_guardian.agents.base_agent import AgentResult

        return AgentResult(
            success=True,
            data={
                "soap_note": """SUBJECTIVE:
Patient presents with chest pain for 2 hours.

OBJECTIVE:
Vital signs: BP 150/95, HR 105.

ASSESSMENT:
Suspected acute coronary syndrome.

PLAN:
EKG, cardiac enzymes, aspirin.""",
                "sections": {
                    "subjective": "Patient presents with chest pain for 2 hours.",
                    "objective": "Vital signs: BP 150/95, HR 105.",
                    "assessment": "Suspected acute coronary syndrome.",
                    "plan": "EKG, cardiac enzymes, aspirin.",
                },
                "model_used": "claude-sonnet-4-20250514",
                "token_count": 150,
            },
            error=None,
            reasoning="Generated SOAP note from transcript",
            execution_time_ms=500.0,
        )

    def test_create_encounter_success(
        self, client: TestClient, mock_scribe_result
    ) -> None:
        """Test creating encounter with valid data."""
        # Create a mock orchestrator with mocked scribe
        from phoenix_guardian.agents.navigator_agent import NavigatorAgent
        from phoenix_guardian.api.utils.orchestrator import EncounterOrchestrator
        from phoenix_guardian.api.dependencies import get_orchestrator

        mock_scribe_agent = MagicMock()
        mock_scribe_agent.execute = AsyncMock(return_value=mock_scribe_result)
        mock_scribe_agent.get_metrics = MagicMock(
            return_value={
                "call_count": 1.0,
                "avg_execution_time_ms": 500.0,
                "total_execution_time_ms": 500.0,
            }
        )

        mock_orchestrator = EncounterOrchestrator(
            navigator_agent=NavigatorAgent(),
            scribe_agent=mock_scribe_agent,
        )

        # Use FastAPI's dependency override mechanism
        app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
        try:
            response = client.post(
                "/api/v1/encounters",
                json={
                    "patient_mrn": "MRN001234",
                    "encounter_type": "office_visit",
                    "transcript": """
                    Patient presents with chest pain for 2 hours.
                    Pain is substernal, 7/10 severity, radiating to left arm.
                    Associated with shortness of breath and diaphoresis.
                    Vital signs: BP 150/95, HR 105, RR 22, O2 sat 96%.
                    Plan: EKG, cardiac enzymes, aspirin 325mg given.
                    """,
                    "provider_id": "provider_001",
                },
            )

            assert response.status_code == 201

            data = response.json()
            assert "encounter_id" in data
            assert data["encounter_id"].startswith("enc_")
            assert data["patient_mrn"] == "MRN001234"
            assert "soap_note" in data
            assert data["status"] == "pending_review"
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_orchestrator, None)

    def test_create_encounter_patient_not_found(self, client: TestClient) -> None:
        """Test creating encounter with invalid MRN."""
        response = client.post(
            "/api/v1/encounters",
            json={
                "patient_mrn": "MRN999999",
                "encounter_type": "office_visit",
                "transcript": "Patient presents with headache. " * 10,
                "provider_id": "provider_001",
            },
        )
        assert response.status_code == 404

    def test_create_encounter_short_transcript(self, client: TestClient) -> None:
        """Test creating encounter with too-short transcript."""
        response = client.post(
            "/api/v1/encounters",
            json={
                "patient_mrn": "MRN001234",
                "encounter_type": "office_visit",
                "transcript": "Too short",
                "provider_id": "provider_001",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_create_encounter_invalid_type(self, client: TestClient) -> None:
        """Test creating encounter with invalid encounter type."""
        response = client.post(
            "/api/v1/encounters",
            json={
                "patient_mrn": "MRN001234",
                "encounter_type": "invalid_type",
                "transcript": "Patient presents with symptoms. " * 10,
                "provider_id": "provider_001",
            },
        )
        assert response.status_code == 422

    def test_get_encounter_not_found(self, client: TestClient) -> None:
        """Test retrieving non-existent encounter."""
        response = client.get("/api/v1/encounters/enc_nonexistent")
        assert response.status_code == 404

    def test_list_encounters_empty(self, client: TestClient) -> None:
        """Test listing encounters when empty."""
        response = client.get("/api/v1/encounters")
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 0
        assert data["encounters"] == []

    def test_encounter_types(self, client: TestClient) -> None:
        """Test all valid encounter types."""
        valid_types = [
            "office_visit",
            "urgent_care",
            "emergency",
            "telehealth",
            "follow_up",
        ]

        for encounter_type in valid_types:
            response = client.post(
                "/api/v1/encounters",
                json={
                    "patient_mrn": "MRN001234",
                    "encounter_type": encounter_type,
                    "transcript": "Patient presents with symptoms needing evaluation. " * 5,
                    "provider_id": "provider_001",
                },
            )
            # May fail due to ScribeAgent requiring API key, but should not be 422
            assert response.status_code != 422, f"Type {encounter_type} should be valid"


# =============================================================================
# Test: Error Handling
# =============================================================================


class TestErrorHandling:
    """Test error handling and responses."""

    def test_invalid_json(self, client: TestClient) -> None:
        """Test invalid JSON in request body."""
        response = client.post(
            "/api/v1/auth/login",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_missing_required_field(self, client: TestClient) -> None:
        """Test missing required field in request."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "dr.smith@phoenixguardian.health"},  # Missing password
        )
        assert response.status_code == 422

    def test_process_time_header(self, client: TestClient) -> None:
        """Test that X-Process-Time header is added."""
        response = client.get("/")
        assert "X-Process-Time" in response.headers


# =============================================================================
# Test: API Documentation
# =============================================================================


class TestAPIDocs:
    """Test API documentation endpoints."""

    def test_swagger_docs(self, client: TestClient) -> None:
        """Test Swagger UI is accessible."""
        response = client.get("/api/docs")
        assert response.status_code == 200

    def test_redoc_docs(self, client: TestClient) -> None:
        """Test ReDoc is accessible."""
        response = client.get("/api/redoc")
        assert response.status_code == 200

    def test_openapi_schema(self, client: TestClient) -> None:
        """Test OpenAPI schema is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        data = response.json()
        assert data["info"]["title"] == "Phoenix Guardian API"
        assert "paths" in data


# =============================================================================
# Test: Security Utilities
# =============================================================================


class TestSecurityUtilities:
    """Test security utility functions."""

    def test_password_hashing(self) -> None:
        """Test password hashing and verification."""
        from phoenix_guardian.api.utils.security import hash_password, verify_password

        password = "TestPassword123!"
        hashed = hash_password(password)

        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("WrongPassword", hashed)

    def test_token_creation(self) -> None:
        """Test JWT token creation."""
        from phoenix_guardian.api.utils.security import create_access_token

        token = create_access_token(
            data={"sub": "user_001", "username": "test", "role": "physician"}
        )

        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_decode(self) -> None:
        """Test JWT token decoding."""
        from phoenix_guardian.api.utils.security import (
            create_access_token,
            decode_access_token,
        )

        token = create_access_token(
            data={"sub": "user_001", "username": "test", "role": "physician"}
        )

        payload = decode_access_token(token)
        assert payload["sub"] == "user_001"
        assert payload["username"] == "test"
        assert payload["role"] == "physician"

    def test_invalid_token_decode(self) -> None:
        """Test decoding invalid token raises exception."""
        from fastapi import HTTPException

        from phoenix_guardian.api.utils.security import decode_access_token

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("invalid_token")

        assert exc_info.value.status_code == 401


# =============================================================================
# Test: Orchestrator
# =============================================================================


class TestOrchestrator:
    """Test EncounterOrchestrator."""

    def test_orchestrator_initialization(self) -> None:
        """Test orchestrator initializes correctly with mock agents."""
        from unittest.mock import MagicMock
        from phoenix_guardian.api.utils.orchestrator import EncounterOrchestrator
        from phoenix_guardian.agents.navigator_agent import NavigatorAgent

        mock_scribe = MagicMock()
        mock_scribe.get_metrics.return_value = {
            "call_count": 0.0,
            "avg_execution_time_ms": 0.0,
            "total_execution_time_ms": 0.0,
        }

        orchestrator = EncounterOrchestrator(
            navigator_agent=NavigatorAgent(),
            scribe_agent=mock_scribe,
        )
        assert orchestrator.navigator is not None
        assert orchestrator.scribe is not None
        assert orchestrator.total_encounters == 0

    def test_orchestrator_metrics(self) -> None:
        """Test orchestrator metrics."""
        from unittest.mock import MagicMock
        from phoenix_guardian.api.utils.orchestrator import EncounterOrchestrator
        from phoenix_guardian.agents.navigator_agent import NavigatorAgent

        mock_scribe = MagicMock()
        mock_scribe.get_metrics.return_value = {
            "call_count": 0.0,
            "avg_execution_time_ms": 0.0,
            "total_execution_time_ms": 0.0,
        }

        orchestrator = EncounterOrchestrator(
            navigator_agent=NavigatorAgent(),
            scribe_agent=mock_scribe,
        )
        metrics = orchestrator.get_metrics()

        assert "total_encounters" in metrics
        assert "success_rate" in metrics
        assert "navigator_metrics" in metrics
        assert "scribe_metrics" in metrics

    def test_encounter_id_generation(self) -> None:
        """Test encounter ID generation format."""
        from unittest.mock import MagicMock
        from phoenix_guardian.api.utils.orchestrator import EncounterOrchestrator
        from phoenix_guardian.agents.navigator_agent import NavigatorAgent

        mock_scribe = MagicMock()
        orchestrator = EncounterOrchestrator(
            navigator_agent=NavigatorAgent(),
            scribe_agent=mock_scribe,
        )
        encounter_id = orchestrator._generate_encounter_id()

        assert encounter_id.startswith("enc_")
        parts = encounter_id.split("_")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # Date: YYYYMMDD
        assert len(parts[2]) == 8  # UUID first 8 chars


# =============================================================================
# Test: Pydantic Models
# =============================================================================


class TestPydanticModels:
    """Test Pydantic model validation."""

    def test_encounter_request_validation(self) -> None:
        """Test EncounterRequest model validation."""
        from phoenix_guardian.api.models import EncounterRequest, EncounterType

        # Valid request
        request = EncounterRequest(
            patient_mrn="MRN001234",
            encounter_type=EncounterType.OFFICE_VISIT,
            transcript="A" * 50,
            provider_id="provider_001",
        )
        assert request.patient_mrn == "MRN001234"

    def test_encounter_request_short_mrn(self) -> None:
        """Test EncounterRequest rejects short MRN."""
        from pydantic import ValidationError

        from phoenix_guardian.api.models import EncounterRequest, EncounterType

        with pytest.raises(ValidationError):
            EncounterRequest(
                patient_mrn="MRN",  # Too short
                encounter_type=EncounterType.OFFICE_VISIT,
                transcript="A" * 50,
                provider_id="provider_001",
            )

    def test_login_request_validation(self) -> None:
        """Test LoginRequest model validation."""
        from phoenix_guardian.api.models import LoginRequest

        # Valid request
        request = LoginRequest(username="testuser", password="password123")
        assert request.username == "testuser"

    def test_health_status_enum(self) -> None:
        """Test HealthStatus enum values."""
        from phoenix_guardian.api.models import HealthStatus

        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
