"""
Base OAuth Connector for Phoenix Guardian EHR Integration.

This module provides abstract base classes for EHR connectors with shared
OAuth 2.0 authentication patterns, connection management, and error handling.

Features:
- Common OAuth 2.0 token management
- Connection lifecycle (connect/disconnect/context manager)
- Token refresh and caching
- Consistent error handling
- Retry logic with exponential backoff

Usage:
    from phoenix_guardian.integrations.base_connector import (
        BaseOAuthConnector,
        BaseConnectorConfig,
        TokenResponse,
    )
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import RequestException, Timeout

from .fhir_client import FHIRClient, FHIRConfig, FHIRError


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# TYPE VARIABLES
# ═══════════════════════════════════════════════════════════════════════════════

ConfigT = TypeVar('ConfigT', bound='BaseConnectorConfig')
TokenT = TypeVar('TokenT', bound='TokenResponse')


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════


class ConnectorError(Exception):
    """Base exception for connector errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class AuthenticationError(ConnectorError):
    """Raised when authentication fails."""
    pass


class ConnectionError(ConnectorError):
    """Raised when connection fails."""
    pass


class ConfigurationError(ConnectorError):
    """Raised when configuration is invalid."""
    pass


class ResourceNotFoundError(ConnectorError):
    """Raised when a requested resource is not found."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# DECORATORS
# ═══════════════════════════════════════════════════════════════════════════════


def handle_fhir_errors(
    connector_error_class: type = ConnectorError,
    auth_error_class: type = AuthenticationError,
    connection_error_class: type = ConnectionError,
) -> Callable:
    """
    Decorator for consistent FHIR error handling.
    
    Catches common exceptions and converts them to connector-specific errors.
    
    Args:
        connector_error_class: Base error class for the connector
        auth_error_class: Authentication error class
        connection_error_class: Connection error class
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except FHIRError as e:
                raise connector_error_class(str(e), {"original_error": type(e).__name__})
            except Timeout as e:
                raise connection_error_class(f"Request timed out: {e}")
            except RequestsConnectionError as e:
                raise connection_error_class(f"Connection failed: {e}")
            except RequestException as e:
                raise connection_error_class(f"Request failed: {e}")
            except connector_error_class:
                raise
            except Exception as e:
                raise connector_error_class(f"Unexpected error: {e}")
        return wrapper
    return decorator


def retry_on_failure(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Timeout, RequestsConnectionError),
) -> Callable:
    """
    Decorator for retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        retryable_exceptions: Tuple of exceptions to retry on
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed, "
                            f"retrying in {delay:.1f}s: {e}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed: {e}")
            
            raise last_exception  # type: ignore
        return wrapper
    return decorator


def require_connection(func: Callable) -> Callable:
    """
    Decorator that ensures connector is connected before calling method.
    
    Args:
        func: Method to wrap
        
    Returns:
        Wrapped method that checks connection first
    """
    @wraps(func)
    def wrapper(self: 'BaseOAuthConnector', *args: Any, **kwargs: Any) -> Any:
        self._ensure_connected()
        return func(self, *args, **kwargs)
    return wrapper


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class BaseConnectorConfig:
    """
    Base configuration for EHR connectors.
    
    Attributes:
        client_id: OAuth client ID
        client_secret: OAuth client secret (optional)
        base_url: FHIR server base URL
        token_url: OAuth token endpoint URL
        use_sandbox: Whether to use sandbox environment
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        verify_ssl: Whether to verify SSL certificates
        scopes: OAuth scopes to request
    """
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    base_url: str = ""
    token_url: str = ""
    use_sandbox: bool = True
    timeout: int = 30
    max_retries: int = 3
    verify_ssl: bool = True
    scopes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (excluding secrets)."""
        return {
            "client_id": self.client_id,
            "base_url": self.base_url,
            "token_url": self.token_url,
            "use_sandbox": self.use_sandbox,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "verify_ssl": self.verify_ssl,
            "scopes": self.scopes,
        }


@dataclass
class TokenResponse:
    """
    OAuth token response.
    
    Attributes:
        access_token: The access token
        token_type: Token type (usually "Bearer")
        expires_in: Seconds until token expires
        scope: Granted scopes
        refresh_token: Optional refresh token
        issued_at: Timestamp when token was issued
    """
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    scope: str = ""
    refresh_token: Optional[str] = None
    issued_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def expires_at(self) -> datetime:
        """Calculate expiration time."""
        return self.issued_at + timedelta(seconds=self.expires_in)
    
    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """
        Check if token is expired or will expire soon.
        
        Args:
            buffer_seconds: Consider expired if within this many seconds
            
        Returns:
            True if token is expired or will expire within buffer
        """
        return datetime.utcnow() >= self.expires_at - timedelta(seconds=buffer_seconds)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (for debugging, excludes actual token)."""
        return {
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "scope": self.scope,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# BASE CONNECTOR
# ═══════════════════════════════════════════════════════════════════════════════


class BaseOAuthConnector(ABC, Generic[ConfigT, TokenT]):
    """
    Abstract base class for OAuth-based EHR connectors.
    
    Provides common functionality for:
    - Connection management (connect/disconnect)
    - Token management (authenticate/refresh)
    - Error handling
    - Context manager support
    
    Subclasses must implement:
    - _authenticate(): Perform vendor-specific authentication
    - _get_sandbox_base_url(): Return sandbox FHIR server URL
    - vendor_name: Property returning vendor name for logging
    """
    
    def __init__(self, config: ConfigT):
        """
        Initialize connector.
        
        Args:
            config: Vendor-specific configuration
        """
        self.config = config
        self.fhir_client: Optional[FHIRClient] = None
        self._token_response: Optional[TokenT] = None
        self._session: Optional[requests.Session] = None
        self._connected: bool = False
        
        logger.info(f"Initialized {self.vendor_name} connector")
    
    @property
    @abstractmethod
    def vendor_name(self) -> str:
        """Return vendor name for logging."""
        pass
    
    @abstractmethod
    def _authenticate(self) -> str:
        """
        Perform vendor-specific authentication.
        
        Returns:
            Access token
            
        Raises:
            AuthenticationError: If authentication fails
        """
        pass
    
    @abstractmethod
    def _get_sandbox_base_url(self) -> str:
        """Return sandbox FHIR server base URL."""
        pass
    
    def _get_base_url(self) -> str:
        """Get appropriate base URL based on environment."""
        if self.config.use_sandbox:
            return self._get_sandbox_base_url()
        return self.config.base_url
    
    def connect(self) -> 'BaseOAuthConnector':
        """
        Connect to FHIR server with authentication.
        
        Returns:
            Self for method chaining
            
        Raises:
            AuthenticationError: If authentication fails
            ConnectionError: If connection fails
        """
        if self._connected:
            # Check if token needs refresh
            if self._token_response and self._token_response.is_expired():
                self._refresh_token()
            return self
        
        try:
            # Create session
            self._session = requests.Session()
            self._session.verify = self.config.verify_ssl
            
            base_url = self._get_base_url()
            
            if self.config.use_sandbox:
                # Sandbox mode - typically no authentication
                logger.info(f"🧪 Connecting to {self.vendor_name} sandbox")
                fhir_config = FHIRConfig(
                    base_url=base_url,
                    client_id=self.config.client_id or f"{self.vendor_name.lower()}-sandbox",
                    timeout=self.config.timeout,
                    max_retries=self.config.max_retries,
                )
            else:
                # Production mode - authenticate first
                logger.info(f"🔐 Authenticating with {self.vendor_name}")
                access_token = self._authenticate()
                
                fhir_config = FHIRConfig(
                    base_url=base_url,
                    client_id=self.config.client_id or "",
                    access_token=access_token,
                    token_url=self.config.token_url,
                    timeout=self.config.timeout,
                    max_retries=self.config.max_retries,
                )
            
            self.fhir_client = FHIRClient(fhir_config)
            self._connected = True
            logger.info(f"✅ Connected to {self.vendor_name}")
            
            return self
            
        except ConnectorError:
            raise
        except RequestsConnectionError as e:
            raise ConnectionError(f"Failed to connect to {self.vendor_name}: {e}")
        except Exception as e:
            raise ConnectorError(f"Unexpected error connecting to {self.vendor_name}: {e}")
    
    def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        if self.fhir_client:
            try:
                self.fhir_client.close()
            except Exception as e:
                logger.warning(f"Error closing FHIR client: {e}")
        
        if self._session:
            try:
                self._session.close()
            except Exception as e:
                logger.warning(f"Error closing session: {e}")
        
        self.fhir_client = None
        self._session = None
        self._token_response = None
        self._connected = False
        
        logger.info(f"🔌 Disconnected from {self.vendor_name}")
    
    def is_connected(self) -> bool:
        """Check if connector is currently connected."""
        return self._connected and self.fhir_client is not None
    
    def _ensure_connected(self) -> None:
        """
        Ensure connector is connected before operations.
        
        Raises:
            ConnectionError: If not connected
        """
        if not self.is_connected():
            raise ConnectionError(
                f"Not connected to {self.vendor_name}. Call connect() first."
            )
    
    def _refresh_token(self) -> None:
        """Refresh access token if expired."""
        if self.config.use_sandbox:
            return
        
        logger.info(f"🔄 Refreshing {self.vendor_name} access token")
        access_token = self._authenticate()
        
        if self.fhir_client and self._token_response:
            self.fhir_client._update_access_token(
                access_token,
                self._token_response.expires_in
            )
    
    def get_token_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current token information (for debugging).
        
        Returns:
            Token information dictionary or None if not authenticated
        """
        if self._token_response:
            return self._token_response.to_dict()
        return None
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection by fetching server capabilities.
        
        Returns:
            Dictionary with connection status and server info
            
        Raises:
            ConnectionError: If not connected
        """
        self._ensure_connected()
        
        if not self.fhir_client:
            raise ConnectionError("FHIR client not initialized")
        
        try:
            result = self.fhir_client.test_connection()
            return {
                "connected": True,
                "vendor": self.vendor_name,
                "environment": "sandbox" if self.config.use_sandbox else "production",
                "base_url": self._get_base_url(),
                **result,
            }
        except Exception as e:
            return {
                "connected": False,
                "vendor": self.vendor_name,
                "error": str(e),
            }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONTEXT MANAGER
    # ═══════════════════════════════════════════════════════════════════════════
    
    def __enter__(self) -> 'BaseOAuthConnector':
        """Enter context manager."""
        self.connect()
        return self
    
    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit context manager."""
        self.disconnect()
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"{self.__class__.__name__}("
            f"vendor={self.vendor_name!r}, "
            f"connected={self._connected}, "
            f"sandbox={self.config.use_sandbox})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════


def parse_oauth_error_response(response: requests.Response) -> str:
    """
    Parse error details from OAuth error response.
    
    Args:
        response: HTTP response object
        
    Returns:
        Error description string
    """
    try:
        error_json = response.json()
        if 'error_description' in error_json:
            return error_json['error_description']
        if 'error' in error_json:
            return error_json['error']
        return str(error_json)
    except Exception:
        return response.text[:500] if response.text else f"HTTP {response.status_code}"


__all__ = [
    # Base Classes
    "BaseOAuthConnector",
    "BaseConnectorConfig",
    "TokenResponse",
    
    # Exceptions
    "ConnectorError",
    "AuthenticationError",
    "ConnectionError",
    "ConfigurationError",
    "ResourceNotFoundError",
    
    # Decorators
    "handle_fhir_errors",
    "retry_on_failure",
    "require_connection",
    
    # Utilities
    "parse_oauth_error_response",
]
