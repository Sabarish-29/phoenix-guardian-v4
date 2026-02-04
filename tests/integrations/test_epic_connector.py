"""
Tests for Epic FHIR Connector - Phoenix Guardian EHR Integration.

This test module provides comprehensive coverage for the Epic connector including:
- Epic configuration tests
- JWT authentication tests
- Epic sandbox connection tests
- Epic-specific operations tests
- Error handling tests
- Integration tests with Epic sandbox

Test Count: 35+ test cases
Target Coverage: 90%+
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, mock_open
import json
import base64
import time

from phoenix_guardian.integrations.epic_connector import (
    EpicConnector,
    EpicConfig,
    EpicTokenResponse,
    EpicEnvironment,
    EpicError,
    EpicAuthenticationError,
    EpicConnectionError,
    EpicConfigurationError,
    EPIC_SANDBOX_TEST_PATIENTS,
    EPIC_SANDBOX_BASE_URL,
    EPIC_SANDBOX_TOKEN_URL,
    EPIC_IDENTIFIER_SYSTEMS,
    EPIC_SCOPES,
    create_epic_sandbox_connector,
    create_epic_production_connector,
)
from phoenix_guardian.integrations.fhir_client import (
    FHIRClient,
    FHIRConfig,
    FHIRPatient,
    FHIRObservation,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


# Sample RSA Private Key for testing (2048-bit)
TEST_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAyqMQ3KPH3M9f3WQ3QJNxT7V0yM0LpEAL6O5c1N2+YLVFXl5R
0AzJoqFmjjNtW8qPO7v1wpOFzOnFHMWnhVcMgZ7XJ5J0FXCKvH1zPZLl2ZHr8VPF
q0YNxTqzPVbK0q5J9WLV7ZMvTHR7UJfQ0W1VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3P
zJfQn0VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5zJQQ7f8U9
PZ0P3PzJfQn0VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5zJQ
Q7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PwIDAQABAoIBAFVgAs
+cYXqTjP4cPTFZzGJvJzA4LPl+d0VxkFpL0+L0K6LPF3M9f3WQ3QJNxT7V0yM0Lp
EAL6O5c1N2+YLVFXl5R0AzJoqFmjjNtW8qPO7v1wpOFzOnFHMWnhVcMgZ7XJ5J0F
XCKvH1zPZLl2ZHr8VPFq0YNxTqzPVbK0q5J9WLV7ZMvTHR7UJfQ0W1VxMHzpJ3V8
J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMH
zpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5zJQQ7f8U9PZ0ECgYEA
7JM3R7f3WQ3QJNxT7V0yM0LpEAL6O5c1N2+YLVFXl5R0AzJoqFmjjNtW8qPO7v1w
pOFzOnFHMWnhVcMgZ7XJ5J0FXCKvH1zPZLl2ZHr8VPFq0YNxTqzPVbK0q5J9WLV7
ZMvTHR7UJfQ0W1VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5z
JQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8ECgYEA2qMQ3KPH3M9f3WQ3QJNxT7V0yM0L
pEAL6O5c1N2+YLVFXl5R0AzJoqFmjjNtW8qPO7v1wpOFzOnFHMWnhVcMgZ7XJ5J0
FXCKvH1zPZLl2ZHr8VPFq0YNxTqzPVbK0q5J9WLV7ZMvTHR7UJfQ0W1VxMHzpJ3V
8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5zJQQ7f8U9PZ0ECgYBr3WQ3QJ
NxT7V0yM0LpEAL6O5c1N2+YLVFXl5R0AzJoqFmjjNtW8qPO7v1wpOFzOnFHMWnhV
cMgZ7XJ5J0FXCKvH1zPZLl2ZHr8VPFq0YNxTqzPVbK0q5J9WLV7ZMvTHR7UJfQ0W
1VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3
PzJfQn0VxMHzpJ3V8ECgYAL6O5c1N2+YLVFXl5R0AzJoqFmjjNtW8qPO7v1wpOFz
OnFHMWnhVcMgZ7XJ5J0FXCKvH1zPZLl2ZHr8VPFq0YNxTqzPVbK0q5J9WLV7ZMvT
HR7UJfQ0W1VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5zJQQ7
f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PwKBgDqzPVbK0q5J9WLV
7ZMvTHR7UJfQ0W1VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5
-----END RSA PRIVATE KEY-----"""

# Valid RSA key for JWT signing tests
VALID_RSA_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA2mKqH5xzNrQE0cuD0lG8ILdv6vG7X7MwLkYb8X5MQPW+gNnW
xO5pNHB0xW9bJ3XK7qGvP3HfrCVcF2N7KpLK5cM5JjLjjRZGXKF3PQ4P8YmzJX+l
cz7GiMN0O1V5Pq0R5Q8fMZMfVm/PQ0F7P3QrHxKlP8RL5PQ6V9kzJP3F0xzMl5Q4
L3MjR5pQ6P8F0xzMl5Q4L3MjR5pQ6P8F0xzMl5Q4L3MjR5pQ6P8F0xzMl5Q4L3Mj
R5pQ6P8F0xzMl5Q4L3MjR5pQ6P8F0xzMl5Q4L3MjR5pQ6P8F0xzMl5Q4L3MjR5pQ
6P8F0xzMl5Q4L3MjR5pQ6P8F0xzMl5Q4L3MjRwIDAQABAoIBAFVgAs+cYXqTjP4c
PTFZzGJvJzA4LPl+d0VxkFpL0+L0K6LPF3M9f3WQ3QJNxT7V0yM0LpEAL6O5c1N2
+YLVFXl5R0AzJoqFmjjNtW8qPO7v1wpOFzOnFHMWnhVcMgZ7XJ5J0FXCKvH1zPZL
l2ZHr8VPFq0YNxTqzPVbK0q5J9WLV7ZMvTHR7UJfQ0W1VxMHzpJ3V8J+N5zJQQ7f
8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5
zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3
V8J+N5zJQQ7f8U9PZ0ECgYEA7JM3R7f3WQ3QJNxT7V0yM0LpEAL6O5c1N2+YLVFX
l5R0AzJoqFmjjNtW8qPO7v1wpOFzOnFHMWnhVcMgZ7XJ5J0FXCKvH1zPZLl2ZHr8
VPFq0YNxTqzPVbK0q5J9WLV7ZMvTHR7UJfQ0W1VxMHzpJ3V8J+N5zJQQ7f8U9PZ0
P3PzJfQn0VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8ECgYEA2qMQ
3KPH3M9f3WQ3QJNxT7V0yM0LpEAL6O5c1N2+YLVFXl5R0AzJoqFmjjNtW8qPO7v1
wpOFzOnFHMWnhVcMgZ7XJ5J0FXCKvH1zPZLl2ZHr8VPFq0YNxTqzPVbK0q5J9WLV
7ZMvTHR7UJfQ0W1VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5
zJQQ7f8U9PZ0ECgYBr3WQ3QJNxT7V0yM0LpEAL6O5c1N2+YLVFXl5R0AzJoqFmjj
NtW8qPO7v1wpOFzOnFHMWnhVcMgZ7XJ5J0FXCKvH1zPZLl2ZHr8VPFq0YNxTqzPV
bK0q5J9WLV7ZMvTHR7UJfQ0W1VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMH
zpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8ECgYAL6O5c1N2+YLVFXl5R0A
zJoqFmjjNtW8qPO7v1wpOFzOnFHMWnhVcMgZ7XJ5J0FXCKvH1zPZLl2ZHr8VPFq0
YNxTqzPVbK0q5J9WLV7ZMvTHR7UJfQ0W1VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJ
fQn0VxMHzpJ3V8J+N5zJQQ7f8U9PZ0P3PzJfQn0VxMHzpJ3V8J+N5zJQQ7f8U9PZ
0P3PwKBgDqzPVbK0q5J9WLV7ZMvTHR7UJfQ0W1VxMHzpJ3V8J+N5zJQQ7f8U9PZ0
P3PzJfQn0VxMHzpJ3V8J+N5
-----END RSA PRIVATE KEY-----"""


@pytest.fixture
def sandbox_config():
    """Create sandbox Epic configuration."""
    return EpicConfig(
        client_id="test-client-id",
        use_sandbox=True,
    )


@pytest.fixture
def production_config():
    """Create production Epic configuration."""
    return EpicConfig(
        client_id="prod-client-id",
        private_key=TEST_PRIVATE_KEY,
        base_url="https://hospital.epic.com/api/FHIR/R4/",
        token_url="https://hospital.epic.com/oauth2/token",
        use_sandbox=False,
    )


@pytest.fixture
def epic_sandbox_connector(sandbox_config):
    """Create Epic sandbox connector with mocked FHIR client."""
    connector = EpicConnector(sandbox_config)
    return connector


@pytest.fixture
def epic_production_connector(production_config):
    """Create Epic production connector with mocked FHIR client."""
    connector = EpicConnector(production_config)
    return connector


@pytest.fixture
def sample_patient_resource():
    """Sample FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": "Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB",
        "name": [{"use": "official", "family": "Lin", "given": ["Derrick"]}],
        "gender": "male",
        "birthDate": "1973-06-03"
    }


@pytest.fixture
def sample_observation_resource():
    """Sample FHIR Observation resource."""
    return {
        "resourceType": "Observation",
        "id": "obs-123",
        "status": "final",
        "code": {
            "coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "HbA1c"}]
        },
        "subject": {"reference": "Patient/Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB"},
        "valueQuantity": {"value": 6.5, "unit": "%"}
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TEST EPIC CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestEpicConfig:
    """Tests for EpicConfig dataclass."""
    
    def test_epic_config_creation(self, sandbox_config):
        """Test EpicConfig creation."""
        assert sandbox_config.client_id == "test-client-id"
        assert sandbox_config.use_sandbox is True
        assert sandbox_config.base_url == EPIC_SANDBOX_BASE_URL
        assert sandbox_config.token_url == EPIC_SANDBOX_TOKEN_URL
    
    def test_epic_config_with_private_key(self, production_config):
        """Test EpicConfig with private key."""
        assert production_config.client_id == "prod-client-id"
        assert production_config.private_key == TEST_PRIVATE_KEY
        assert production_config.use_sandbox is False
    
    def test_epic_config_sandbox_mode(self, sandbox_config):
        """Test sandbox mode defaults."""
        assert sandbox_config.timeout == 30
        assert sandbox_config.max_retries == 3
    
    def test_epic_config_default_scopes(self, sandbox_config):
        """Test default scopes are set."""
        assert len(sandbox_config.scopes) > 0
        assert EPIC_SCOPES["patient_read"] in sandbox_config.scopes
    
    def test_epic_config_to_dict_excludes_secrets(self, production_config):
        """Test that to_dict excludes sensitive data."""
        config_dict = production_config.to_dict()
        
        assert "client_id" in config_dict
        assert "base_url" in config_dict
        assert "private_key" not in config_dict
        assert "private_key_path" not in config_dict
    
    def test_epic_config_custom_scopes(self):
        """Test custom scopes configuration."""
        config = EpicConfig(
            client_id="test",
            use_sandbox=True,
            scopes=["system/Patient.read"]
        )
        
        assert config.scopes == ["system/Patient.read"]


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CONNECTION
# ═══════════════════════════════════════════════════════════════════════════════


class TestConnection:
    """Tests for Epic connection management."""
    
    def test_connect_sandbox_no_auth(self, sandbox_config):
        """Test sandbox connection doesn't require authentication."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session'):
            connector = EpicConnector(sandbox_config)
            fhir_client = connector.connect()
            
            assert fhir_client is not None
            assert connector.is_connected()
    
    def test_connect_production_with_jwt(self, production_config):
        """Test production connection with JWT authentication."""
        with patch('phoenix_guardian.integrations.epic_connector.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "test-access-token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "system/Patient.read"
            }
            mock_post.return_value = mock_response
            
            with patch('phoenix_guardian.integrations.fhir_client.requests.Session'):
                with patch('phoenix_guardian.integrations.epic_connector.jwt.encode') as mock_jwt:
                    mock_jwt.return_value = "mock-jwt-token"
                    
                    connector = EpicConnector(production_config)
                    fhir_client = connector.connect()
                    
                    assert fhir_client is not None
                    assert connector.is_connected()
                    mock_jwt.assert_called_once()
    
    def test_connect_missing_private_key_error(self):
        """Test error when private key is missing in production mode."""
        config = EpicConfig(
            client_id="test",
            use_sandbox=False  # Production mode but no private key
        )
        
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session'):
            connector = EpicConnector(config)
            
            with pytest.raises(EpicConfigurationError) as exc_info:
                connector.connect()
            
            assert "private_key" in str(exc_info.value)
    
    def test_context_manager(self, sandbox_config):
        """Test context manager connects and disconnects."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session'):
            with EpicConnector(sandbox_config) as connector:
                assert connector.is_connected()
            
            assert not connector.is_connected()
    
    def test_connection_reuse(self, sandbox_config):
        """Test that repeated connect() reuses connection."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session'):
            connector = EpicConnector(sandbox_config)
            client1 = connector.connect()
            client2 = connector.connect()
            
            assert client1 is client2
    
    def test_disconnect(self, sandbox_config):
        """Test disconnect properly cleans up."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session'):
            connector = EpicConnector(sandbox_config)
            connector.connect()
            
            assert connector.is_connected()
            
            connector.disconnect()
            
            assert not connector.is_connected()
            assert connector.fhir_client is None
    
    def test_repr(self, sandbox_config):
        """Test string representation."""
        connector = EpicConnector(sandbox_config)
        repr_str = repr(connector)
        
        assert "sandbox" in repr_str
        assert "disconnected" in repr_str


# ═══════════════════════════════════════════════════════════════════════════════
# TEST JWT AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestJWTAuthentication:
    """Tests for JWT authentication."""
    
    def test_generate_jwt_assertion(self, production_config):
        """Test JWT assertion generation."""
        connector = EpicConnector(production_config)
        
        with patch('phoenix_guardian.integrations.epic_connector.jwt.encode') as mock_jwt:
            mock_jwt.return_value = "mock-jwt-token"
            
            jwt_token = connector._generate_jwt_assertion(TEST_PRIVATE_KEY)
            
            assert jwt_token == "mock-jwt-token"
            mock_jwt.assert_called_once()
    
    def test_jwt_payload_structure(self, production_config):
        """Test JWT payload contains required fields."""
        connector = EpicConnector(production_config)
        
        with patch('phoenix_guardian.integrations.epic_connector.jwt.encode') as mock_jwt:
            mock_jwt.return_value = "mock-token"
            
            connector._generate_jwt_assertion(TEST_PRIVATE_KEY)
            
            # Get the payload passed to jwt.encode
            call_args = mock_jwt.call_args
            payload = call_args[0][0]
            
            assert 'iss' in payload
            assert 'sub' in payload
            assert 'aud' in payload
            assert 'jti' in payload
            assert 'exp' in payload
            assert 'iat' in payload
            
            assert payload['iss'] == production_config.client_id
            assert payload['sub'] == production_config.client_id
            assert payload['aud'] == production_config.token_url
    
    def test_jwt_signature_algorithm_rs384(self, production_config):
        """Test JWT uses RS384 algorithm."""
        connector = EpicConnector(production_config)
        
        with patch('phoenix_guardian.integrations.epic_connector.jwt.encode') as mock_jwt:
            mock_jwt.return_value = "mock-token"
            
            connector._generate_jwt_assertion(TEST_PRIVATE_KEY)
            
            call_args = mock_jwt.call_args
            algorithm = call_args[1]['algorithm']
            
            assert algorithm == 'RS384'
    
    def test_jwt_token_refresh(self, production_config):
        """Test token refresh when expired."""
        connector = EpicConnector(production_config)
        
        # Set an expired token
        connector._token_response = EpicTokenResponse(
            access_token="old-token",
            token_type="Bearer",
            expires_in=3600,
            scope="",
        )
        connector._token_response.expires_at = datetime.now() - timedelta(hours=1)
        
        with patch('phoenix_guardian.integrations.epic_connector.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "new-access-token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": ""
            }
            mock_post.return_value = mock_response
            
            with patch('phoenix_guardian.integrations.epic_connector.jwt.encode') as mock_jwt:
                mock_jwt.return_value = "mock-jwt"
                
                token = connector._authenticate_jwt()
                
                assert token == "new-access-token"
    
    def test_jwt_token_expiration_check(self):
        """Test token expiration check."""
        # Fresh token
        fresh_token = EpicTokenResponse(
            access_token="token",
            token_type="Bearer",
            expires_in=3600,
            scope=""
        )
        assert not fresh_token.is_expired
        
        # Expired token
        expired_token = EpicTokenResponse(
            access_token="token",
            token_type="Bearer",
            expires_in=3600,
            scope=""
        )
        expired_token.expires_at = datetime.now() - timedelta(minutes=10)
        assert expired_token.is_expired
    
    def test_authenticate_jwt_failure(self, production_config):
        """Test JWT authentication failure handling."""
        connector = EpicConnector(production_config)
        
        with patch('phoenix_guardian.integrations.epic_connector.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Invalid JWT"
            mock_response.json.return_value = {
                "error": "invalid_client",
                "error_description": "Invalid JWT signature"
            }
            mock_post.return_value = mock_response
            
            with patch('phoenix_guardian.integrations.epic_connector.jwt.encode') as mock_jwt:
                mock_jwt.return_value = "mock-jwt"
                
                with pytest.raises(EpicAuthenticationError) as exc_info:
                    connector._authenticate_jwt()
                
                assert "401" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST PRIVATE KEY LOADING
# ═══════════════════════════════════════════════════════════════════════════════


class TestPrivateKeyLoading:
    """Tests for private key loading."""
    
    def test_load_private_key_from_config(self, production_config):
        """Test loading private key from config."""
        connector = EpicConnector(production_config)
        
        key = connector._load_private_key()
        
        assert key == TEST_PRIVATE_KEY
    
    def test_load_private_key_from_file(self):
        """Test loading private key from file."""
        config = EpicConfig(
            client_id="test",
            private_key_path="/path/to/key.pem",
            use_sandbox=False
        )
        
        connector = EpicConnector(config)
        
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = True
            
            with patch('pathlib.Path.read_text') as mock_read:
                mock_read.return_value = TEST_PRIVATE_KEY
                
                key = connector._load_private_key()
                
                assert key == TEST_PRIVATE_KEY
    
    def test_private_key_file_not_found(self):
        """Test error when private key file doesn't exist."""
        config = EpicConfig(
            client_id="test",
            private_key_path="/nonexistent/key.pem",
            use_sandbox=False
        )
        
        connector = EpicConnector(config)
        
        with pytest.raises(EpicConfigurationError) as exc_info:
            connector._load_private_key()
        
        assert "not found" in str(exc_info.value)
    
    def test_private_key_caching(self, production_config):
        """Test that private key is cached after loading."""
        connector = EpicConnector(production_config)
        
        key1 = connector._load_private_key()
        key2 = connector._load_private_key()
        
        assert key1 == key2
        assert connector._private_key_cache is not None


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FHIR CLIENT INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestFHIRClientIntegration:
    """Tests for FHIR client integration."""
    
    def test_get_patient(self, sandbox_config, sample_patient_resource):
        """Test getting patient through Epic connector."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = sample_patient_resource
            mock_session.request.return_value = mock_response
            
            connector = EpicConnector(sandbox_config)
            connector.connect()
            
            patient = connector.get_patient("Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB")
            
            assert patient is not None
            assert patient.name == "Derrick Lin"
    
    def test_get_patient_observations(self, sandbox_config, sample_observation_resource):
        """Test getting patient observations."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "resourceType": "Bundle",
                "entry": [{"resource": sample_observation_resource}]
            }
            mock_session.request.return_value = mock_response
            
            connector = EpicConnector(sandbox_config)
            connector.connect()
            
            observations = connector.get_patient_observations(
                "Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB"
            )
            
            assert len(observations) == 1
    
    def test_validate_patient_id_exists(self, sandbox_config, sample_patient_resource):
        """Test validating existing patient ID."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = sample_patient_resource
            mock_session.request.return_value = mock_response
            
            connector = EpicConnector(sandbox_config)
            connector.connect()
            
            exists = connector.validate_patient_id("Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB")
            
            assert exists is True
    
    def test_validate_patient_id_not_exists(self, sandbox_config):
        """Test validating non-existent patient ID."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            mock_response = Mock()
            mock_response.ok = False
            mock_response.status_code = 404
            mock_response.text = "Not found"
            mock_response.json.return_value = {}
            mock_session.request.return_value = mock_response
            
            connector = EpicConnector(sandbox_config)
            connector.connect()
            
            exists = connector.validate_patient_id("nonexistent-patient-id")
            
            assert exists is False
    
    def test_ensure_connected_raises_error(self, sandbox_config):
        """Test that operations fail when not connected."""
        connector = EpicConnector(sandbox_config)
        
        with pytest.raises(EpicError) as exc_info:
            connector.get_patient("test-id")
        
        assert "Not connected" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST EPIC-SPECIFIC FEATURES
# ═══════════════════════════════════════════════════════════════════════════════


class TestEpicSpecificFeatures:
    """Tests for Epic-specific features."""
    
    def test_get_sandbox_test_patients(self, sandbox_config):
        """Test getting sandbox test patient IDs."""
        connector = EpicConnector(sandbox_config)
        
        patients = connector.get_sandbox_test_patients()
        
        assert len(patients) == 3
        assert "Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB" in patients
        assert "erXuFYUfucBZaryVksYEcMg3" in patients
        assert "eq081-VQEgP8drUUqCWzHfw3" in patients
    
    def test_get_sandbox_test_patient_by_name(self, sandbox_config):
        """Test getting sandbox test patient by name."""
        connector = EpicConnector(sandbox_config)
        
        derrick = connector.get_sandbox_test_patient_by_name("derrick_lin")
        amy = connector.get_sandbox_test_patient_by_name("Mychart Amy")
        
        assert derrick == "Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB"
        assert amy == "erXuFYUfucBZaryVksYEcMg3"
    
    def test_search_patients_by_identifier(self, sandbox_config, sample_patient_resource):
        """Test searching patients by identifier."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "resourceType": "Bundle",
                "entry": [{"resource": sample_patient_resource}]
            }
            mock_session.request.return_value = mock_response
            
            connector = EpicConnector(sandbox_config)
            connector.connect()
            
            patients = connector.search_patients_by_identifier("12345")
            
            assert len(patients) == 1
    
    def test_search_patients_by_mrn(self, sandbox_config, sample_patient_resource):
        """Test searching patients by MRN."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "resourceType": "Bundle",
                "entry": [{"resource": sample_patient_resource}]
            }
            mock_session.request.return_value = mock_response
            
            connector = EpicConnector(sandbox_config)
            connector.connect()
            
            patients = connector.search_patients_by_mrn("MRN12345")
            
            assert len(patients) == 1
    
    def test_get_epic_capability_statement(self, sandbox_config):
        """Test getting Epic capability statement."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "resourceType": "CapabilityStatement",
                "fhirVersion": "4.0.1",
                "software": {
                    "name": "Epic",
                    "version": "2024"
                }
            }
            mock_session.request.return_value = mock_response
            
            connector = EpicConnector(sandbox_config)
            connector.connect()
            
            capability = connector.get_epic_capability_statement()
            
            assert capability["resourceType"] == "CapabilityStatement"
    
    def test_get_epic_version(self, sandbox_config):
        """Test getting Epic version info."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "resourceType": "CapabilityStatement",
                "fhirVersion": "4.0.1",
                "software": {
                    "name": "Epic",
                    "version": "2024"
                }
            }
            mock_session.request.return_value = mock_response
            
            connector = EpicConnector(sandbox_config)
            connector.connect()
            
            fhir_version, software = connector.get_epic_version()
            
            assert fhir_version == "4.0.1"
            assert "Epic" in software
    
    def test_get_supported_resources(self, sandbox_config):
        """Test getting supported resources."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "resourceType": "CapabilityStatement",
                "rest": [
                    {
                        "resource": [
                            {"type": "Patient"},
                            {"type": "Observation"},
                            {"type": "Condition"}
                        ]
                    }
                ]
            }
            mock_session.request.return_value = mock_response
            
            connector = EpicConnector(sandbox_config)
            connector.connect()
            
            resources = connector.get_supported_resources()
            
            assert "Patient" in resources
            assert "Observation" in resources
            assert "Condition" in resources
    
    def test_epic_identifier_systems(self):
        """Test Epic identifier systems are defined."""
        assert "epic_internal" in EPIC_IDENTIFIER_SYSTEMS
        assert "epic_mrn" in EPIC_IDENTIFIER_SYSTEMS
        assert "ssn" in EPIC_IDENTIFIER_SYSTEMS


# ═══════════════════════════════════════════════════════════════════════════════
# TEST ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_invalid_jwt_signature_error(self, production_config):
        """Test invalid JWT signature handling."""
        connector = EpicConnector(production_config)
        
        with patch('phoenix_guardian.integrations.epic_connector.jwt.encode') as mock_jwt:
            mock_jwt.side_effect = Exception("Invalid key format")
            
            with pytest.raises(EpicConfigurationError) as exc_info:
                connector._generate_jwt_assertion(TEST_PRIVATE_KEY)
            
            assert "Failed to generate JWT" in str(exc_info.value)
    
    def test_network_timeout(self, production_config):
        """Test network timeout handling."""
        connector = EpicConnector(production_config)
        
        with patch('phoenix_guardian.integrations.epic_connector.requests.post') as mock_post:
            from requests.exceptions import Timeout
            mock_post.side_effect = Timeout("Connection timed out")
            
            with patch('phoenix_guardian.integrations.epic_connector.jwt.encode') as mock_jwt:
                mock_jwt.return_value = "mock-jwt"
                
                with pytest.raises(EpicConnectionError) as exc_info:
                    connector._authenticate_jwt()
                
                assert "timeout" in str(exc_info.value).lower()
    
    def test_connection_error(self, production_config):
        """Test connection error handling."""
        connector = EpicConnector(production_config)
        
        with patch('phoenix_guardian.integrations.epic_connector.requests.post') as mock_post:
            from requests.exceptions import ConnectionError
            mock_post.side_effect = ConnectionError("Connection refused")
            
            with patch('phoenix_guardian.integrations.epic_connector.jwt.encode') as mock_jwt:
                mock_jwt.return_value = "mock-jwt"
                
                with pytest.raises(EpicConnectionError) as exc_info:
                    connector._authenticate_jwt()
                
                assert "connection error" in str(exc_info.value).lower()
    
    def test_epic_error_with_details(self):
        """Test EpicError includes details."""
        error = EpicError(
            "Test error",
            details={"status_code": 400, "reason": "Bad request"}
        )
        
        assert error.details["status_code"] == 400
        assert error.details["reason"] == "Bad request"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FACTORY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFactoryFunctions:
    """Tests for factory functions."""
    
    def test_create_epic_sandbox_connector(self):
        """Test sandbox connector factory."""
        connector = create_epic_sandbox_connector()
        
        assert connector.config.use_sandbox is True
        assert connector.config.base_url == EPIC_SANDBOX_BASE_URL
    
    def test_create_epic_sandbox_connector_custom_client_id(self):
        """Test sandbox connector with custom client ID."""
        connector = create_epic_sandbox_connector(client_id="custom-client")
        
        assert connector.config.client_id == "custom-client"
    
    def test_create_epic_production_connector(self):
        """Test production connector factory."""
        connector = create_epic_production_connector(
            client_id="prod-client",
            private_key_path="/path/to/key.pem",
            base_url="https://hospital.epic.com/api/FHIR/R4/",
            token_url="https://hospital.epic.com/oauth2/token"
        )
        
        assert connector.config.use_sandbox is False
        assert connector.config.client_id == "prod-client"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST TOKEN RESPONSE
# ═══════════════════════════════════════════════════════════════════════════════


class TestEpicTokenResponse:
    """Tests for EpicTokenResponse dataclass."""
    
    def test_token_response_creation(self):
        """Test token response creation."""
        token = EpicTokenResponse(
            access_token="test-token",
            token_type="Bearer",
            expires_in=3600,
            scope="system/Patient.read"
        )
        
        assert token.access_token == "test-token"
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600
    
    def test_token_response_expiration_calculation(self):
        """Test expiration time calculation."""
        token = EpicTokenResponse(
            access_token="test-token",
            token_type="Bearer",
            expires_in=3600,
            scope=""
        )
        
        # Should be approximately 1 hour from now
        expected = datetime.now() + timedelta(hours=1)
        diff = abs((token.expires_at - expected).total_seconds())
        
        assert diff < 5  # Within 5 seconds
    
    def test_token_is_expired_with_buffer(self):
        """Test token expiration with 5-minute buffer."""
        token = EpicTokenResponse(
            access_token="test-token",
            token_type="Bearer",
            expires_in=3600,
            scope=""
        )
        
        # Set expiration to 4 minutes from now (within buffer)
        token.expires_at = datetime.now() + timedelta(minutes=4)
        
        assert token.is_expired is True
        
        # Set expiration to 10 minutes from now (outside buffer)
        token.expires_at = datetime.now() + timedelta(minutes=10)
        
        assert token.is_expired is False


# ═══════════════════════════════════════════════════════════════════════════════
# TEST TOKEN INFO
# ═══════════════════════════════════════════════════════════════════════════════


class TestTokenInfo:
    """Tests for token info retrieval."""
    
    def test_get_token_info_no_token(self, sandbox_config):
        """Test get_token_info when no token."""
        connector = EpicConnector(sandbox_config)
        
        info = connector.get_token_info()
        
        assert info is None
    
    def test_get_token_info_with_token(self, production_config):
        """Test get_token_info with token."""
        connector = EpicConnector(production_config)
        connector._token_response = EpicTokenResponse(
            access_token="test-token",
            token_type="Bearer",
            expires_in=3600,
            scope="system/Patient.read"
        )
        
        info = connector.get_token_info()
        
        assert info is not None
        assert info["token_type"] == "Bearer"
        assert info["expires_in"] == 3600
        assert "expires_at" in info


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CONVENIENCE METHODS
# ═══════════════════════════════════════════════════════════════════════════════


class TestConvenienceMethods:
    """Tests for convenience methods."""
    
    def test_get_patient_conditions(self, sandbox_config):
        """Test getting patient conditions."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "resourceType": "Bundle",
                "entry": []
            }
            mock_session.request.return_value = mock_response
            
            connector = EpicConnector(sandbox_config)
            connector.connect()
            
            conditions = connector.get_patient_conditions("test-patient")
            
            assert isinstance(conditions, list)
    
    def test_get_patient_medications(self, sandbox_config):
        """Test getting patient medications."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "resourceType": "Bundle",
                "entry": []
            }
            mock_session.request.return_value = mock_response
            
            connector = EpicConnector(sandbox_config)
            connector.connect()
            
            medications = connector.get_patient_medications("test-patient")
            
            assert isinstance(medications, list)
    
    def test_test_connection(self, sandbox_config):
        """Test connection test method."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "resourceType": "CapabilityStatement"
            }
            mock_session.request.return_value = mock_response
            
            connector = EpicConnector(sandbox_config)
            
            result = connector.test_connection()
            
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
