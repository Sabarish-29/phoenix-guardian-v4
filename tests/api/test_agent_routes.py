"""API Route Tests for AI Agents.

Tests all agent endpoints with authentication.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

# Set mock API key before imports
os.environ.setdefault("ANTHROPIC_API_KEY", "test-api-key")

from fastapi.testclient import TestClient
from phoenix_guardian.api.main import app
from phoenix_guardian.database.connection import get_db
from phoenix_guardian.api.auth.utils import get_current_user


# Create a mock user for authentication
class MockUser:
    """Mock user for testing."""
    id = 1
    email = "test@phoenix.local"
    first_name = "Test"
    last_name = "User"
    role = "physician"
    is_active = True
    is_deleted = False


def get_mock_db():
    """Create a mock database session."""
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_session.commit.return_value = None
    mock_session.add.return_value = None
    mock_session.close.return_value = None
    yield mock_session


def get_mock_user():
    """Return a mock authenticated user."""
    return MockUser()


@pytest.fixture(autouse=True)
def setup_overrides():
    """Set up dependency overrides for each test."""
    app.dependency_overrides[get_db] = get_mock_db
    app.dependency_overrides[get_current_user] = get_mock_user
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_anthropic():
    """Mock the Anthropic client for all tests."""
    with patch('phoenix_guardian.agents.base.Anthropic') as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Mock response")]
        mock_instance.messages.create.return_value = mock_response
        
        yield mock_instance


class TestScribeEndpoint:
    """Tests for SOAP generation endpoint."""
    
    def test_scribe_endpoint_success(self, client, mock_anthropic):
        """Test SOAP generation endpoint."""
        mock_anthropic.messages.create.return_value.content = [
            MagicMock(text="""**Subjective:**
Patient presents with cough.

**Objective:**
Temp: 98.6F, clear lungs.

**Assessment:**
Upper respiratory infection (J06.9)

**Plan:**
Rest and fluids.""")
        ]
        
        response = client.post(
            "/api/v1/agents/scribe/generate-soap",
            json={
                "chief_complaint": "Cough",
                "vitals": {"temp": "98.6F"},
                "symptoms": ["cough"],
                "exam_findings": "Clear lungs"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "soap_note" in data
        assert "icd_codes" in data
    
    def test_scribe_endpoint_unauthorized(self, client):
        """Test endpoint requires authentication."""
        # Remove auth override for this test
        app.dependency_overrides.pop(get_current_user, None)
        
        response = client.post(
            "/api/v1/agents/scribe/generate-soap",
            json={"chief_complaint": "Test"}
        )
        assert response.status_code == 401
        
        # Restore for other tests
        app.dependency_overrides[get_current_user] = get_mock_user


class TestSafetyEndpoint:
    """Tests for drug interaction endpoint."""
    
    def test_safety_endpoint_success(self, client, mock_anthropic):
        """Test drug interaction endpoint."""
        mock_anthropic.messages.create.return_value.content = [
            MagicMock(text="No significant interactions noted.")
        ]
        
        response = client.post(
            "/api/v1/agents/safety/check-interactions",
            json={"medications": ["lisinopril", "potassium"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "interactions" in data
        assert "severity" in data
    
    def test_safety_detects_known_interaction(self, client, mock_anthropic):
        """Test known interaction is detected."""
        mock_anthropic.messages.create.return_value.content = [
            MagicMock(text="Warning: Monitor potassium levels.")
        ]
        
        response = client.post(
            "/api/v1/agents/safety/check-interactions",
            json={"medications": ["lisinopril", "potassium"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["severity"] == "HIGH"


class TestNavigatorEndpoint:
    """Tests for workflow suggestion endpoint."""
    
    def test_navigator_endpoint_success(self, client, mock_anthropic):
        """Test workflow suggestion endpoint."""
        mock_anthropic.messages.create.return_value.content = [
            MagicMock(text="""Here are the next steps:
1. Complete vital signs
2. Review lab results
3. Document assessment""")
        ]
        
        response = client.post(
            "/api/v1/agents/navigator/suggest-workflow",
            json={
                "current_status": "Patient admitted",
                "encounter_type": "Inpatient"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "next_steps" in data
        assert "priority" in data


class TestCodingEndpoint:
    """Tests for code suggestion endpoint."""
    
    def test_coding_endpoint_success(self, client, mock_anthropic):
        """Test code suggestion endpoint."""
        mock_anthropic.messages.create.return_value.content = [
            MagicMock(text="""ICD-10 codes:
J18.9 - Pneumonia, unspecified

CPT codes:
99213 - Office visit""")
        ]
        
        response = client.post(
            "/api/v1/agents/coding/suggest-codes",
            json={
                "clinical_note": "Patient has pneumonia",
                "procedures": []
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "icd10_codes" in data
        assert "cpt_codes" in data


class TestSentinelEndpoint:
    """Tests for security analysis endpoint."""
    
    def test_sentinel_endpoint_xss_detection(self, client, mock_anthropic):
        """Test XSS detection."""
        response = client.post(
            "/api/v1/agents/sentinel/analyze-input",
            json={"user_input": "<script>alert(1)</script>"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "threat_detected" in data
        assert data["threat_detected"] is True
    
    def test_sentinel_endpoint_safe_input(self, client, mock_anthropic):
        """Test safe input passes."""
        mock_anthropic.messages.create.return_value.content = [
            MagicMock(text="NO - This is normal medical text.")
        ]
        
        response = client.post(
            "/api/v1/agents/sentinel/analyze-input",
            json={"user_input": "Patient feels better today"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["threat_detected"] is False
