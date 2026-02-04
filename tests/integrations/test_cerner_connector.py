"""
Tests for Cerner FHIR Connector.

This module contains comprehensive tests for the CernerConnector class,
covering configuration, OAuth 2.0 authentication, FHIR operations,
Cerner-specific features, and error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import requests

from phoenix_guardian.integrations.cerner_connector import (
    CernerConnector,
    CernerConfig,
    CernerTokenResponse,
    CernerEnvironment,
    CernerError,
    CernerAuthenticationError,
    CernerConnectionError,
    CernerConfigurationError,
    create_cerner_sandbox_connector,
    create_cerner_production_connector,
    CERNER_SANDBOX_TENANT_ID,
    CERNER_SANDBOX_BASE_URL,
    CERNER_SANDBOX_TEST_PATIENTS,
    CERNER_IDENTIFIER_SYSTEMS,
    CERNER_DEFAULT_SCOPES,
)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sandbox_config():
    """Create sandbox configuration for testing."""
    return CernerConfig(
        tenant_id=CERNER_SANDBOX_TENANT_ID,
        use_sandbox=True
    )


@pytest.fixture
def production_config():
    """Create production configuration for testing."""
    return CernerConfig(
        tenant_id="test-tenant-id",
        client_id="test-client-id",
        client_secret="test-client-secret",
        use_sandbox=False
    )


@pytest.fixture
def sandbox_connector(sandbox_config):
    """Create sandbox connector for testing."""
    return CernerConnector(sandbox_config)


@pytest.fixture
def production_connector(production_config):
    """Create production connector for testing."""
    return CernerConnector(production_config)


@pytest.fixture
def mock_token_response():
    """Create mock token response."""
    return {
        "access_token": "mock-access-token-12345",
        "token_type": "Bearer",
        "expires_in": 570,
        "scope": "system/Patient.read system/Observation.read"
    }


@pytest.fixture
def mock_patient_bundle():
    """Create mock patient search bundle."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "12724066",
                    "name": [{"family": "Smart", "given": ["Nancy"]}],
                    "gender": "female",
                    "birthDate": "1980-08-11"
                }
            }
        ]
    }


@pytest.fixture
def mock_capability_statement():
    """Create mock capability statement."""
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "software": {
            "name": "Cerner Millennium",
            "version": "2024.01"
        },
        "fhirVersion": "4.0.1",
        "rest": [
            {
                "mode": "server",
                "resource": [
                    {"type": "Patient"},
                    {"type": "Observation"},
                    {"type": "Condition"},
                    {"type": "MedicationRequest"}
                ]
            }
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCernerConfig:
    """Tests for CernerConfig dataclass."""
    
    def test_cerner_config_creation(self):
        """Test basic configuration creation."""
        config = CernerConfig(
            tenant_id="test-tenant-123",
            client_id="test-client",
            client_secret="test-secret"
        )
        
        assert config.tenant_id == "test-tenant-123"
        assert config.client_id == "test-client"
        assert config.client_secret == "test-secret"
        assert config.use_sandbox is False
    
    def test_cerner_config_sandbox_mode(self, sandbox_config):
        """Test sandbox mode configuration."""
        assert sandbox_config.use_sandbox is True
        assert sandbox_config.tenant_id == CERNER_SANDBOX_TENANT_ID
        assert sandbox_config.base_url == CERNER_SANDBOX_BASE_URL
        assert sandbox_config.environment == CernerEnvironment.SANDBOX
    
    def test_cerner_config_production_mode(self, production_config):
        """Test production mode configuration."""
        assert production_config.use_sandbox is False
        assert production_config.environment == CernerEnvironment.PRODUCTION
        assert "test-tenant-id" in production_config.base_url
        assert "test-tenant-id" in production_config.token_url
    
    def test_cerner_config_tenant_id_formatting(self):
        """Test tenant ID is properly formatted in URLs."""
        tenant_id = "my-custom-tenant-uuid"
        config = CernerConfig(
            tenant_id=tenant_id,
            client_id="test",
            client_secret="test",
            use_sandbox=False
        )
        
        assert tenant_id in config.base_url
        assert tenant_id in config.token_url
    
    def test_cerner_config_to_dict_excludes_secrets(self, production_config):
        """Test that to_dict excludes sensitive information."""
        result = production_config.to_dict()
        
        assert "client_secret" not in result
        assert "tenant_id" in result
        assert "client_id" in result
        assert "base_url" in result
    
    def test_cerner_config_default_scopes(self):
        """Test default scopes are set correctly."""
        config = CernerConfig(tenant_id="test")
        
        assert len(config.scopes) > 0
        assert "system/Patient.read" in config.scopes
        assert "system/Observation.read" in config.scopes
    
    def test_cerner_config_custom_scopes(self):
        """Test custom scopes configuration."""
        custom_scopes = ["system/Patient.read", "system/Condition.read"]
        config = CernerConfig(
            tenant_id="test",
            scopes=custom_scopes
        )
        
        assert config.scopes == custom_scopes


# ═══════════════════════════════════════════════════════════════════════════════
# CONNECTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestConnection:
    """Tests for connection management."""
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_connect_sandbox_no_auth(self, mock_fhir_client, sandbox_connector):
        """Test sandbox connection without authentication."""
        connector = sandbox_connector.connect()
        
        assert connector.is_connected()
        assert connector.fhir_client is not None
        mock_fhir_client.assert_called_once()
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    @patch('phoenix_guardian.integrations.cerner_connector.requests.post')
    def test_connect_production_with_credentials(
        self, mock_post, mock_fhir_client, production_connector, mock_token_response
    ):
        """Test production connection with OAuth credentials."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_token_response
        mock_post.return_value = mock_response
        
        connector = production_connector.connect()
        
        assert connector.is_connected()
        mock_post.assert_called_once()
        mock_fhir_client.assert_called_once()
    
    def test_connect_missing_credentials_error(self):
        """Test error when connecting without credentials in production."""
        config = CernerConfig(
            tenant_id="test-tenant",
            use_sandbox=False
        )
        connector = CernerConnector(config)
        
        with pytest.raises(CernerConfigurationError):
            connector.connect()
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_context_manager(self, mock_fhir_client, sandbox_config):
        """Test context manager usage."""
        with CernerConnector(sandbox_config) as connector:
            assert connector.is_connected()
        
        assert not connector.is_connected()
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_connection_reuse(self, mock_fhir_client, sandbox_connector):
        """Test that connection is reused when already connected."""
        sandbox_connector.connect()
        first_client = sandbox_connector.fhir_client
        
        sandbox_connector.connect()
        second_client = sandbox_connector.fhir_client
        
        assert first_client is second_client
        assert mock_fhir_client.call_count == 1
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_disconnect(self, mock_fhir_client, sandbox_connector):
        """Test disconnect functionality."""
        mock_client = Mock()
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        assert sandbox_connector.is_connected()
        
        sandbox_connector.disconnect()
        assert not sandbox_connector.is_connected()
        mock_client.close.assert_called_once()
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_repr(self, mock_fhir_client, sandbox_connector):
        """Test string representation."""
        repr_str = repr(sandbox_connector)
        
        assert "CernerConnector" in repr_str
        assert "sandbox" in repr_str
        assert "disconnected" in repr_str
        
        sandbox_connector.connect()
        repr_str = repr(sandbox_connector)
        assert "connected" in repr_str


# ═══════════════════════════════════════════════════════════════════════════════
# OAUTH AUTHENTICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestOAuthAuthentication:
    """Tests for OAuth 2.0 client credentials authentication."""
    
    @patch('phoenix_guardian.integrations.cerner_connector.requests.post')
    def test_authenticate_client_credentials(
        self, mock_post, production_connector, mock_token_response
    ):
        """Test successful OAuth authentication."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_token_response
        mock_post.return_value = mock_response
        
        token = production_connector._authenticate_client_credentials()
        
        assert token == mock_token_response["access_token"]
        mock_post.assert_called_once()
        
        # Verify request parameters
        call_args = mock_post.call_args
        assert "grant_type" in call_args.kwargs.get("data", {})
        assert call_args.kwargs["data"]["grant_type"] == "client_credentials"
    
    @patch('phoenix_guardian.integrations.cerner_connector.requests.post')
    def test_token_caching(
        self, mock_post, production_connector, mock_token_response
    ):
        """Test token caching behavior."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_token_response
        mock_post.return_value = mock_response
        
        # First call - should authenticate
        token1 = production_connector._authenticate_client_credentials()
        
        # Second call - should use cached token
        token2 = production_connector._authenticate_client_credentials()
        
        assert token1 == token2
        assert mock_post.call_count == 1  # Only one actual request
    
    @patch('phoenix_guardian.integrations.cerner_connector.requests.post')
    def test_token_refresh_on_expiration(
        self, mock_post, production_connector, mock_token_response
    ):
        """Test token refresh when expired."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_token_response
        mock_post.return_value = mock_response
        
        # First call
        production_connector._authenticate_client_credentials()
        
        # Simulate expired token by setting it to None to force refresh
        production_connector._token_response = None
        
        # Second call should refresh
        production_connector._authenticate_client_credentials()
        
        assert mock_post.call_count == 2  # Two requests
    
    @patch('phoenix_guardian.integrations.cerner_connector.requests.post')
    def test_authenticate_invalid_credentials(self, mock_post, production_connector):
        """Test authentication failure with invalid credentials."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Invalid client credentials"
        mock_response.json.return_value = {"error": "invalid_client"}
        mock_post.return_value = mock_response
        
        with pytest.raises(CernerAuthenticationError):
            production_connector._authenticate_client_credentials()
    
    @patch('phoenix_guardian.integrations.cerner_connector.requests.post')
    def test_authenticate_network_error(self, mock_post, production_connector):
        """Test authentication failure due to network error."""
        mock_post.side_effect = requests.exceptions.Timeout()
        
        with pytest.raises(CernerAuthenticationError):
            production_connector._authenticate_client_credentials()
    
    @patch('phoenix_guardian.integrations.cerner_connector.requests.post')
    def test_get_token_info(
        self, mock_post, production_connector, mock_token_response
    ):
        """Test getting token information."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_token_response
        mock_post.return_value = mock_response
        
        # Before authentication
        assert production_connector.get_token_info() is None
        
        # After authentication
        production_connector._authenticate_client_credentials()
        token_info = production_connector.get_token_info()
        
        assert token_info is not None
        assert "access_token" in token_info
        assert "expires_at" in token_info


# ═══════════════════════════════════════════════════════════════════════════════
# FHIR CLIENT INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFHIRClientIntegration:
    """Tests for FHIR client integration."""
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_get_patient(self, mock_fhir_client, sandbox_connector):
        """Test getting a patient."""
        mock_client = Mock()
        mock_client.get_patient.return_value = {"id": "12724066", "name": "Nancy Smart"}
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        patient = sandbox_connector.get_patient("12724066")
        
        assert patient is not None
        mock_client.get_patient.assert_called_once_with("12724066")
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_get_patient_observations(self, mock_fhir_client, sandbox_connector):
        """Test getting patient observations."""
        mock_client = Mock()
        mock_client.get_observations.return_value = [{"id": "obs-1"}]
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        observations = sandbox_connector.get_patient_observations("12724066")
        
        assert len(observations) > 0
        mock_client.get_observations.assert_called_once()
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_get_patient_vital_signs(self, mock_fhir_client, sandbox_connector):
        """Test getting patient vital signs."""
        mock_client = Mock()
        mock_client.get_vital_signs.return_value = [{"id": "vs-1"}]
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        vitals = sandbox_connector.get_patient_observations("12724066", category="vital-signs")
        
        assert len(vitals) > 0
        mock_client.get_vital_signs.assert_called_once()
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_get_patient_lab_results(self, mock_fhir_client, sandbox_connector):
        """Test getting patient lab results."""
        mock_client = Mock()
        mock_client.get_lab_results.return_value = [{"id": "lab-1"}]
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        labs = sandbox_connector.get_patient_observations("12724066", category="laboratory")
        
        assert len(labs) > 0
        mock_client.get_lab_results.assert_called_once()
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_get_patient_conditions(self, mock_fhir_client, sandbox_connector):
        """Test getting patient conditions."""
        mock_client = Mock()
        mock_client.get_conditions.return_value = [{"id": "cond-1"}]
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        conditions = sandbox_connector.get_patient_conditions("12724066")
        
        assert len(conditions) > 0
        mock_client.get_conditions.assert_called_once()
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_get_patient_medications(self, mock_fhir_client, sandbox_connector):
        """Test getting patient medications."""
        mock_client = Mock()
        mock_client.get_medications.return_value = [{"id": "med-1"}]
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        medications = sandbox_connector.get_patient_medications("12724066")
        
        assert len(medications) > 0
        mock_client.get_medications.assert_called_once()
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_validate_patient_id_exists(self, mock_fhir_client, sandbox_connector):
        """Test validating existing patient ID."""
        mock_client = Mock()
        mock_client.get_patient.return_value = {"id": "12724066"}
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        exists = sandbox_connector.validate_patient_id("12724066")
        
        assert exists is True
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_validate_patient_id_not_exists(self, mock_fhir_client, sandbox_connector):
        """Test validating non-existing patient ID."""
        mock_client = Mock()
        mock_client.get_patient.return_value = None
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        exists = sandbox_connector.validate_patient_id("invalid-id")
        
        assert exists is False
    
    def test_ensure_connected_raises_error(self, sandbox_connector):
        """Test that operations fail when not connected."""
        with pytest.raises(CernerConnectionError):
            sandbox_connector.get_patient("12724066")


# ═══════════════════════════════════════════════════════════════════════════════
# PATIENT SEARCH TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPatientSearch:
    """Tests for patient search functionality."""
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_search_patients_by_mrn(
        self, mock_fhir_client, sandbox_connector, mock_patient_bundle
    ):
        """Test searching patients by MRN."""
        mock_client = Mock()
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_patient_bundle
        mock_session.get.return_value = mock_response
        mock_client.session = mock_session
        mock_client.config = Mock(base_url=CERNER_SANDBOX_BASE_URL)
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        results = sandbox_connector.search_patients_by_mrn("12345678")
        
        assert len(results) > 0
        assert results[0]["id"] == "12724066"
        
        # Verify identifier system was used
        call_args = mock_session.get.call_args
        assert CERNER_IDENTIFIER_SYSTEMS["mrn"] in str(call_args)
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_search_patients_by_fin(
        self, mock_fhir_client, sandbox_connector, mock_patient_bundle
    ):
        """Test searching patients by FIN."""
        mock_client = Mock()
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_patient_bundle
        mock_session.get.return_value = mock_response
        mock_client.session = mock_session
        mock_client.config = Mock(base_url=CERNER_SANDBOX_BASE_URL)
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        results = sandbox_connector.search_patients_by_fin("FIN123456")
        
        assert len(results) > 0
        
        # Verify FIN identifier system was used
        call_args = mock_session.get.call_args
        assert CERNER_IDENTIFIER_SYSTEMS["fin"] in str(call_args)
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_search_patients_by_name_and_dob(
        self, mock_fhir_client, sandbox_connector, mock_patient_bundle
    ):
        """Test searching patients by name and DOB."""
        mock_client = Mock()
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_patient_bundle
        mock_session.get.return_value = mock_response
        mock_client.session = mock_session
        mock_client.config = Mock(base_url=CERNER_SANDBOX_BASE_URL)
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        results = sandbox_connector.search_patients_by_name_and_dob(
            family_name="Smart",
            given_name="Nancy",
            birth_date="1980-08-11"
        )
        
        assert len(results) > 0
        
        # Verify search parameters
        call_args = mock_session.get.call_args
        params = call_args.kwargs.get("params", {})
        assert params.get("family") == "Smart"


# ═══════════════════════════════════════════════════════════════════════════════
# CERNER-SPECIFIC FEATURES TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCernerSpecificFeatures:
    """Tests for Cerner-specific features."""
    
    def test_get_sandbox_test_patients(self, sandbox_connector):
        """Test getting sandbox test patient list."""
        patients = sandbox_connector.get_sandbox_test_patients()
        
        assert len(patients) == 3
        assert any(p["name"] == "Smart, Nancy" for p in patients)
        assert any(p["name"] == "Smart, Joe" for p in patients)
        assert any(p["name"] == "Smart, Timmy" for p in patients)
    
    def test_get_sandbox_test_patient_ids(self, sandbox_connector):
        """Test getting sandbox test patient IDs."""
        ids = sandbox_connector.get_sandbox_test_patient_ids()
        
        assert "12724066" in ids
        assert "12742400" in ids
        assert "12742633" in ids
    
    def test_get_sandbox_test_patient_by_name(self, sandbox_connector):
        """Test getting specific test patient by name key."""
        nancy = sandbox_connector.get_sandbox_test_patient_by_name("smart_nancy")
        
        assert nancy is not None
        assert nancy["id"] == "12724066"
        assert nancy["name"] == "Smart, Nancy"
        
        # Test non-existent name
        unknown = sandbox_connector.get_sandbox_test_patient_by_name("unknown")
        assert unknown is None
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_get_cerner_capability_statement(
        self, mock_fhir_client, sandbox_connector, mock_capability_statement
    ):
        """Test getting Cerner capability statement."""
        mock_client = Mock()
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_capability_statement
        mock_session.get.return_value = mock_response
        mock_client.session = mock_session
        mock_client.config = Mock(base_url=CERNER_SANDBOX_BASE_URL)
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        capability = sandbox_connector.get_cerner_capability_statement()
        
        assert capability["resourceType"] == "CapabilityStatement"
        assert capability["software"]["name"] == "Cerner Millennium"
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_get_cerner_version(
        self, mock_fhir_client, sandbox_connector, mock_capability_statement
    ):
        """Test getting Cerner server version."""
        mock_client = Mock()
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_capability_statement
        mock_session.get.return_value = mock_response
        mock_client.session = mock_session
        mock_client.config = Mock(base_url=CERNER_SANDBOX_BASE_URL)
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        version = sandbox_connector.get_cerner_version()
        
        assert version == "2024.01"
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_get_supported_resources(
        self, mock_fhir_client, sandbox_connector, mock_capability_statement
    ):
        """Test getting supported FHIR resources."""
        mock_client = Mock()
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_capability_statement
        mock_session.get.return_value = mock_response
        mock_client.session = mock_session
        mock_client.config = Mock(base_url=CERNER_SANDBOX_BASE_URL)
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        resources = sandbox_connector.get_supported_resources()
        
        assert "Patient" in resources
        assert "Observation" in resources
        assert "Condition" in resources
    
    def test_get_cerner_code_system_url(self, sandbox_connector):
        """Test Cerner code system URL generation."""
        url = sandbox_connector.get_cerner_code_system_url("72")
        
        assert "codeSet/72" in url
        assert sandbox_connector.config.tenant_id in url
    
    def test_cerner_identifier_systems(self):
        """Test Cerner identifier systems are defined."""
        assert "mrn" in CERNER_IDENTIFIER_SYSTEMS
        assert "fin" in CERNER_IDENTIFIER_SYSTEMS
        assert CERNER_IDENTIFIER_SYSTEMS["mrn"] == "urn:oid:2.16.840.1.113883.6.1000"
        assert CERNER_IDENTIFIER_SYSTEMS["fin"] == "urn:oid:2.16.840.1.113883.3.787.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Tests for error handling."""
    
    def test_connect_without_credentials_production(self):
        """Test error when connecting to production without credentials."""
        config = CernerConfig(
            tenant_id="test-tenant",
            use_sandbox=False
        )
        connector = CernerConnector(config)
        
        with pytest.raises(CernerConfigurationError) as exc_info:
            connector.connect()
        
        assert "client_id" in str(exc_info.value).lower()
    
    @patch('phoenix_guardian.integrations.cerner_connector.requests.post')
    def test_invalid_tenant_id_error(self, mock_post, production_config):
        """Test error with invalid tenant ID."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Tenant not found"
        mock_response.json.return_value = {"error": "not_found"}
        mock_post.return_value = mock_response
        
        connector = CernerConnector(production_config)
        
        with pytest.raises(CernerAuthenticationError):
            connector.connect()
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    @patch('phoenix_guardian.integrations.cerner_connector.requests.post')
    def test_network_timeout(self, mock_post, mock_fhir_client, production_config):
        """Test handling of network timeout."""
        mock_post.side_effect = requests.exceptions.Timeout()
        
        connector = CernerConnector(production_config)
        
        with pytest.raises(CernerAuthenticationError) as exc_info:
            connector.connect()
        
        assert "timeout" in str(exc_info.value).lower()
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_connection_error_handling(self, mock_fhir_client):
        """Test handling of connection errors."""
        mock_fhir_client.side_effect = requests.exceptions.ConnectionError()
        
        config = CernerConfig(
            tenant_id=CERNER_SANDBOX_TENANT_ID,
            use_sandbox=True
        )
        connector = CernerConnector(config)
        
        with pytest.raises(CernerConnectionError):
            connector.connect()
    
    def test_cerner_error_with_details(self):
        """Test CernerError includes details."""
        error = CernerError(
            "Test error",
            {"key": "value", "code": 123}
        )
        
        assert "Test error" in str(error)
        assert error.details["key"] == "value"
        assert error.details["code"] == 123


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTIONS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFactoryFunctions:
    """Tests for factory functions."""
    
    def test_create_sandbox_connector(self):
        """Test creating sandbox connector via factory."""
        connector = create_cerner_sandbox_connector()
        
        assert connector.config.use_sandbox is True
        assert connector.config.tenant_id == CERNER_SANDBOX_TENANT_ID
    
    def test_create_sandbox_connector_with_options(self):
        """Test creating sandbox connector with custom options."""
        connector = create_cerner_sandbox_connector(
            client_id="custom-client",
            timeout=60
        )
        
        assert connector.config.client_id == "custom-client"
        assert connector.config.timeout == 60
    
    def test_create_production_connector(self):
        """Test creating production connector via factory."""
        connector = create_cerner_production_connector(
            tenant_id="prod-tenant-id",
            client_id="prod-client",
            client_secret="prod-secret"
        )
        
        assert connector.config.use_sandbox is False
        assert connector.config.tenant_id == "prod-tenant-id"
        assert connector.config.client_id == "prod-client"
        assert connector.config.client_secret == "prod-secret"
    
    def test_create_production_connector_with_scopes(self):
        """Test creating production connector with custom scopes."""
        custom_scopes = ["system/Patient.read"]
        connector = create_cerner_production_connector(
            tenant_id="prod-tenant",
            client_id="client",
            client_secret="secret",
            scopes=custom_scopes
        )
        
        assert connector.config.scopes == custom_scopes


# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN RESPONSE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCernerTokenResponse:
    """Tests for CernerTokenResponse dataclass."""
    
    def test_token_response_creation(self):
        """Test token response creation."""
        token = CernerTokenResponse(
            access_token="test-token",
            token_type="Bearer",
            expires_in=570,
            scope="system/Patient.read"
        )
        
        assert token.access_token == "test-token"
        assert token.token_type == "Bearer"
        assert token.expires_in == 570
    
    def test_token_response_expiration_calculation(self):
        """Test token expiration time calculation."""
        token = CernerTokenResponse(
            access_token="test-token",
            token_type="Bearer",
            expires_in=3600,
            scope="system/Patient.read"
        )
        
        expected_expiry = token.issued_at + timedelta(seconds=3600)
        assert abs((token.expires_at - expected_expiry).total_seconds()) < 1
    
    def test_token_is_expired_with_buffer(self):
        """Test token expiration check with buffer."""
        # Create token that expires in 20 seconds
        token = CernerTokenResponse(
            access_token="test-token",
            token_type="Bearer",
            expires_in=20,
            scope="system/Patient.read"
        )
        
        # Should be expired with 30 second buffer
        assert token.is_expired(buffer_seconds=30) is True
        
        # Should not be expired with 10 second buffer
        assert token.is_expired(buffer_seconds=10) is False
    
    def test_token_to_dict_truncates_token(self):
        """Test that to_dict truncates the access token for security."""
        token = CernerTokenResponse(
            access_token="very-long-access-token-value-12345",
            token_type="Bearer",
            expires_in=570,
            scope="system/Patient.read"
        )
        
        result = token.to_dict()
        
        assert "..." in result["access_token"]
        assert len(result["access_token"]) < len(token.access_token)


# ═══════════════════════════════════════════════════════════════════════════════
# CONNECTION TEST TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestConnectionTest:
    """Tests for connection testing functionality."""
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_test_connection_success(
        self, mock_fhir_client, sandbox_connector, mock_capability_statement
    ):
        """Test successful connection test."""
        mock_client = Mock()
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_capability_statement
        mock_session.get.return_value = mock_response
        mock_client.session = mock_session
        mock_client.config = Mock(base_url=CERNER_SANDBOX_BASE_URL)
        mock_fhir_client.return_value = mock_client
        
        result = sandbox_connector.test_connection()
        
        assert result is True
    
    @patch('phoenix_guardian.integrations.cerner_connector.FHIRClient')
    def test_test_connection_failure(self, mock_fhir_client, sandbox_connector):
        """Test failed connection test."""
        mock_client = Mock()
        mock_session = Mock()
        mock_session.get.side_effect = Exception("Connection failed")
        mock_client.session = mock_session
        mock_client.config = Mock(base_url=CERNER_SANDBOX_BASE_URL)
        mock_fhir_client.return_value = mock_client
        
        sandbox_connector.connect()
        result = sandbox_connector.test_connection()
        
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCernerEnvironment:
    """Tests for CernerEnvironment enum."""
    
    def test_environment_values(self):
        """Test environment enum values."""
        assert CernerEnvironment.SANDBOX.value == "sandbox"
        assert CernerEnvironment.PRODUCTION.value == "production"
    
    def test_config_environment_property(self, sandbox_config, production_config):
        """Test config environment property."""
        assert sandbox_config.environment == CernerEnvironment.SANDBOX
        assert production_config.environment == CernerEnvironment.PRODUCTION
