"""
Tests for BaseOAuthConnector and related base classes.

Tests the shared OAuth connector functionality including:
- Token management
- Connection lifecycle
- Error handling decorators
- Retry logic
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from phoenix_guardian.integrations.base_connector import (
    BaseOAuthConnector,
    BaseConnectorConfig,
    TokenResponse,
    ConnectorError,
    AuthenticationError,
    ConnectionError,
    ConfigurationError,
    ResourceNotFoundError,
    handle_fhir_errors,
    retry_on_failure,
    require_connection,
    parse_oauth_error_response,
)
from phoenix_guardian.integrations.fhir_client import FHIRError


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def base_config():
    """Create a basic connector config."""
    return BaseConnectorConfig(
        client_id="test-client",
        client_secret="test-secret",
        base_url="https://api.test.com/fhir/r4/",
        token_url="https://api.test.com/oauth/token",
        use_sandbox=True,
        timeout=30,
        max_retries=3,
    )


@pytest.fixture
def token_response():
    """Create a valid token response."""
    return TokenResponse(
        access_token="test-access-token-12345",
        token_type="Bearer",
        expires_in=3600,
        scope="patient/*.read",
        issued_at=datetime.utcnow(),
    )


@pytest.fixture
def expired_token():
    """Create an expired token response."""
    return TokenResponse(
        access_token="expired-token",
        token_type="Bearer",
        expires_in=3600,
        scope="patient/*.read",
        issued_at=datetime.utcnow() - timedelta(hours=2),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CONCRETE TEST CONNECTOR
# ═══════════════════════════════════════════════════════════════════════════════


class TestConnector(BaseOAuthConnector):
    """Concrete implementation for testing."""
    
    @property
    def vendor_name(self) -> str:
        return "Test"
    
    def _authenticate(self) -> str:
        return "test-token"
    
    def _get_sandbox_base_url(self) -> str:
        return "https://sandbox.test.com/fhir/r4/"


# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN RESPONSE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTokenResponse:
    """Tests for TokenResponse dataclass."""
    
    def test_token_creation(self, token_response):
        """Test token response creation."""
        assert token_response.access_token == "test-access-token-12345"
        assert token_response.token_type == "Bearer"
        assert token_response.expires_in == 3600
        assert token_response.scope == "patient/*.read"
    
    def test_expires_at_calculation(self, token_response):
        """Test expiration time calculation."""
        expected_expiry = token_response.issued_at + timedelta(seconds=3600)
        assert token_response.expires_at == expected_expiry
    
    def test_is_expired_fresh_token(self, token_response):
        """Test fresh token is not expired."""
        assert not token_response.is_expired()
    
    def test_is_expired_with_buffer(self):
        """Test token expiring within buffer is considered expired."""
        token = TokenResponse(
            access_token="soon-expiring",
            expires_in=30,  # Expires in 30 seconds
            issued_at=datetime.utcnow(),
        )
        # With 60 second buffer, should be considered expired
        assert token.is_expired(buffer_seconds=60)
    
    def test_is_expired_old_token(self, expired_token):
        """Test old token is expired."""
        assert expired_token.is_expired()
    
    def test_to_dict_excludes_token(self, token_response):
        """Test to_dict doesn't expose actual token."""
        data = token_response.to_dict()
        assert "access_token" not in data
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] == 3600


# ═══════════════════════════════════════════════════════════════════════════════
# BASE CONFIG TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestBaseConnectorConfig:
    """Tests for BaseConnectorConfig."""
    
    def test_config_defaults(self):
        """Test default config values."""
        config = BaseConnectorConfig()
        assert config.use_sandbox is True
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.verify_ssl is True
    
    def test_config_to_dict_excludes_secret(self, base_config):
        """Test config to_dict excludes sensitive data."""
        data = base_config.to_dict()
        assert "client_secret" not in data
        assert data["client_id"] == "test-client"
        assert data["base_url"] == "https://api.test.com/fhir/r4/"


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestConnectorExceptions:
    """Tests for connector exceptions."""
    
    def test_connector_error_basic(self):
        """Test basic ConnectorError."""
        error = ConnectorError("Test error")
        assert str(error) == "Test error"
        assert error.details == {}
    
    def test_connector_error_with_details(self):
        """Test ConnectorError with details."""
        error = ConnectorError("Test error", {"code": 500, "reason": "Server error"})
        assert "Test error" in str(error)
        assert "code" in str(error)
    
    def test_authentication_error(self):
        """Test AuthenticationError inheritance."""
        error = AuthenticationError("Auth failed")
        assert isinstance(error, ConnectorError)
    
    def test_connection_error(self):
        """Test ConnectionError inheritance."""
        error = ConnectionError("Connection lost")
        assert isinstance(error, ConnectorError)
    
    def test_configuration_error(self):
        """Test ConfigurationError inheritance."""
        error = ConfigurationError("Invalid config")
        assert isinstance(error, ConnectorError)
    
    def test_resource_not_found_error(self):
        """Test ResourceNotFoundError inheritance."""
        error = ResourceNotFoundError("Patient not found", {"id": "12345"})
        assert isinstance(error, ConnectorError)
        assert error.details["id"] == "12345"


# ═══════════════════════════════════════════════════════════════════════════════
# DECORATOR TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestHandleFhirErrorsDecorator:
    """Tests for handle_fhir_errors decorator."""
    
    def test_successful_call_passes_through(self):
        """Test successful function call returns normally."""
        @handle_fhir_errors()
        def success_func():
            return "success"
        
        assert success_func() == "success"
    
    def test_fhir_error_converted(self):
        """Test FHIRError is converted to ConnectorError."""
        @handle_fhir_errors()
        def raise_fhir_error():
            raise FHIRError("FHIR error")
        
        with pytest.raises(ConnectorError) as exc:
            raise_fhir_error()
        assert "FHIR error" in str(exc.value)
    
    def test_timeout_converted(self):
        """Test Timeout is converted to ConnectionError."""
        from requests.exceptions import Timeout
        
        @handle_fhir_errors()
        def raise_timeout():
            raise Timeout("Request timed out")
        
        with pytest.raises(ConnectionError) as exc:
            raise_timeout()
        assert "timed out" in str(exc.value)
    
    def test_custom_error_classes(self):
        """Test decorator uses custom error classes."""
        class CustomConnectorError(ConnectorError):
            pass
        
        class CustomAuthError(AuthenticationError):
            pass
        
        @handle_fhir_errors(connector_error_class=CustomConnectorError)
        def raise_fhir_error():
            raise FHIRError("test")
        
        with pytest.raises(CustomConnectorError):
            raise_fhir_error()


class TestRetryOnFailureDecorator:
    """Tests for retry_on_failure decorator."""
    
    def test_successful_call_no_retry(self):
        """Test successful call doesn't retry."""
        call_count = 0
        
        @retry_on_failure(max_retries=3, base_delay=0.01)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = success_func()
        assert result == "success"
        assert call_count == 1
    
    def test_retry_on_timeout(self):
        """Test function retries on Timeout."""
        from requests.exceptions import Timeout
        
        call_count = 0
        
        @retry_on_failure(max_retries=2, base_delay=0.01)
        def fail_twice_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Timeout("timeout")
            return "success"
        
        result = fail_twice_then_succeed()
        assert result == "success"
        assert call_count == 3
    
    def test_max_retries_exceeded(self):
        """Test exception raised after max retries."""
        from requests.exceptions import Timeout
        
        @retry_on_failure(max_retries=2, base_delay=0.01)
        def always_fail():
            raise Timeout("always timeout")
        
        with pytest.raises(Timeout):
            always_fail()
    
    def test_non_retryable_error_not_retried(self):
        """Test non-retryable errors are not retried."""
        call_count = 0
        
        @retry_on_failure(max_retries=3, base_delay=0.01)
        def raise_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")
        
        with pytest.raises(ValueError):
            raise_value_error()
        assert call_count == 1


class TestRequireConnectionDecorator:
    """Tests for require_connection decorator."""
    
    def test_connected_passes_through(self, base_config):
        """Test call succeeds when connected."""
        connector = TestConnector(base_config)
        connector._connected = True
        connector.fhir_client = Mock()
        
        @require_connection
        def test_method(self):
            return "success"
        
        result = test_method(connector)
        assert result == "success"
    
    def test_not_connected_raises(self, base_config):
        """Test call fails when not connected."""
        connector = TestConnector(base_config)
        connector._connected = False
        
        @require_connection
        def test_method(self):
            return "success"
        
        with pytest.raises(ConnectionError):
            test_method(connector)


# ═══════════════════════════════════════════════════════════════════════════════
# BASE CONNECTOR TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestBaseOAuthConnector:
    """Tests for BaseOAuthConnector."""
    
    def test_initialization(self, base_config):
        """Test connector initialization."""
        connector = TestConnector(base_config)
        assert connector.config == base_config
        assert connector.fhir_client is None
        assert connector._connected is False
        assert connector.vendor_name == "Test"
    
    def test_is_connected_false_initially(self, base_config):
        """Test is_connected returns false initially."""
        connector = TestConnector(base_config)
        assert not connector.is_connected()
    
    @patch('phoenix_guardian.integrations.base_connector.FHIRClient')
    def test_connect_sandbox_mode(self, mock_fhir, base_config):
        """Test connection in sandbox mode."""
        base_config.use_sandbox = True
        connector = TestConnector(base_config)
        
        connector.connect()
        
        assert connector._connected
        assert mock_fhir.called
    
    @patch('phoenix_guardian.integrations.base_connector.FHIRClient')
    def test_connect_production_mode(self, mock_fhir, base_config):
        """Test connection in production mode."""
        base_config.use_sandbox = False
        connector = TestConnector(base_config)
        
        connector.connect()
        
        assert connector._connected
        # Should have called _authenticate for production
        assert mock_fhir.called
    
    def test_disconnect(self, base_config):
        """Test disconnect cleans up resources."""
        connector = TestConnector(base_config)
        connector._connected = True
        connector.fhir_client = Mock()
        connector._session = Mock()
        
        connector.disconnect()
        
        assert not connector._connected
        assert connector.fhir_client is None
        assert connector._session is None
    
    def test_ensure_connected_raises_when_not_connected(self, base_config):
        """Test _ensure_connected raises when not connected."""
        connector = TestConnector(base_config)
        
        with pytest.raises(ConnectionError):
            connector._ensure_connected()
    
    @patch('phoenix_guardian.integrations.base_connector.FHIRClient')
    def test_context_manager(self, mock_fhir, base_config):
        """Test context manager connect/disconnect."""
        with TestConnector(base_config) as connector:
            assert connector._connected
        
        assert not connector._connected
    
    def test_repr(self, base_config):
        """Test string representation."""
        connector = TestConnector(base_config)
        repr_str = repr(connector)
        
        assert "TestConnector" in repr_str
        assert "Test" in repr_str
        assert "sandbox=True" in repr_str
    
    def test_get_token_info_none_when_no_token(self, base_config):
        """Test get_token_info returns None when not authenticated."""
        connector = TestConnector(base_config)
        assert connector.get_token_info() is None
    
    def test_get_token_info_returns_data(self, base_config, token_response):
        """Test get_token_info returns token data."""
        connector = TestConnector(base_config)
        connector._token_response = token_response
        
        info = connector.get_token_info()
        assert info["token_type"] == "Bearer"
        assert info["expires_in"] == 3600


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseOAuthErrorResponse:
    """Tests for parse_oauth_error_response utility."""
    
    def test_parse_json_error_description(self):
        """Test parsing JSON response with error_description."""
        response = Mock()
        response.json.return_value = {"error_description": "Invalid credentials"}
        
        result = parse_oauth_error_response(response)
        assert result == "Invalid credentials"
    
    def test_parse_json_error_field(self):
        """Test parsing JSON response with error field."""
        response = Mock()
        response.json.return_value = {"error": "unauthorized_client"}
        
        result = parse_oauth_error_response(response)
        assert result == "unauthorized_client"
    
    def test_parse_plain_text_response(self):
        """Test parsing plain text error response."""
        response = Mock()
        response.json.side_effect = Exception("Not JSON")
        response.text = "Server error occurred"
        
        result = parse_oauth_error_response(response)
        assert result == "Server error occurred"
    
    def test_parse_empty_response(self):
        """Test parsing empty error response."""
        response = Mock()
        response.json.side_effect = Exception("Not JSON")
        response.text = ""
        response.status_code = 500
        
        result = parse_oauth_error_response(response)
        assert "500" in result


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestBaseConnectorIntegration:
    """Integration tests for base connector."""
    
    @patch('phoenix_guardian.integrations.base_connector.FHIRClient')
    def test_full_connection_lifecycle(self, mock_fhir, base_config):
        """Test complete connection lifecycle."""
        # Mock FHIR client
        mock_client = Mock()
        mock_client.test_connection.return_value = {"status": "ok"}
        mock_fhir.return_value = mock_client
        
        connector = TestConnector(base_config)
        
        # Connect
        connector.connect()
        assert connector.is_connected()
        
        # Test connection
        result = connector.test_connection()
        assert result["connected"]
        assert result["vendor"] == "Test"
        
        # Disconnect
        connector.disconnect()
        assert not connector.is_connected()
    
    @patch('phoenix_guardian.integrations.base_connector.FHIRClient')
    def test_multiple_connect_calls(self, mock_fhir, base_config):
        """Test multiple connect calls reuse connection."""
        connector = TestConnector(base_config)
        
        connector.connect()
        first_client = connector.fhir_client
        
        connector.connect()
        second_client = connector.fhir_client
        
        # Should reuse same client
        assert first_client is second_client
