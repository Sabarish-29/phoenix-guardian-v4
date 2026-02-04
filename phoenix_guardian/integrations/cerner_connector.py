"""
Cerner-specific FHIR Connector with OAuth 2.0 Authentication.

This module provides a Cerner-specific implementation for connecting to
Cerner Millennium FHIR R4 servers with OAuth 2.0 client credentials authentication.

Features:
- OAuth 2.0 client credentials flow
- Cerner sandbox support (no auth required)
- Tenant-based URL configuration
- Cerner-specific identifier systems (MRN, FIN)
- Cerner Millennium code system support
- Token caching with automatic refresh

Example:
    # Sandbox mode (no authentication)
    from phoenix_guardian.integrations import create_cerner_sandbox_connector
    
    with create_cerner_sandbox_connector() as cerner:
        patient = cerner.fhir_client.get_patient("12724066")
        print(f"Patient: {patient.name}")
    
    # Production mode (with OAuth 2.0)
    from phoenix_guardian.integrations import create_cerner_production_connector
    
    with create_cerner_production_connector(
        tenant_id="your-tenant-id",
        client_id="your-client-id",
        client_secret="your-client-secret"
    ) as cerner:
        results = cerner.search_patients_by_mrn("12345678")
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import requests
import logging

from .fhir_client import FHIRClient, FHIRConfig

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Cerner Sandbox Configuration
CERNER_SANDBOX_TENANT_ID = "ec2458f2-1e24-41c8-b71b-0e701af7583d"
CERNER_SANDBOX_BASE_URL = f"https://fhir-open.cerner.com/r4/{CERNER_SANDBOX_TENANT_ID}/"

# Cerner Production URL Templates
CERNER_PRODUCTION_BASE_URL_TEMPLATE = "https://fhir-myrecord.cerner.com/r4/{tenant_id}/"
CERNER_TOKEN_URL_TEMPLATE = "https://authorization.cerner.com/tenants/{tenant_id}/protocols/oauth2/profiles/smart-v1/token"

# Cerner Sandbox Test Patients
CERNER_SANDBOX_TEST_PATIENTS = {
    "smart_nancy": {
        "id": "12724066",
        "name": "Smart, Nancy",
        "gender": "female",
        "birthDate": "1980-08-11"
    },
    "smart_joe": {
        "id": "12742400",
        "name": "Smart, Joe",
        "gender": "male",
        "birthDate": "1976-04-29"
    },
    "smart_timmy": {
        "id": "12742633",
        "name": "Smart, Timmy",
        "gender": "male",
        "birthDate": "2012-05-03"
    }
}

# Cerner Identifier Systems
CERNER_IDENTIFIER_SYSTEMS = {
    "mrn": "urn:oid:2.16.840.1.113883.6.1000",  # Medical Record Number
    "fin": "urn:oid:2.16.840.1.113883.3.787.0.0",  # Financial Identifier Number
    "ssn": "http://hl7.org/fhir/sid/us-ssn",  # Social Security Number
    "npi": "http://hl7.org/fhir/sid/us-npi"  # National Provider Identifier
}

# Default Cerner OAuth Scopes
CERNER_DEFAULT_SCOPES = [
    "system/Patient.read",
    "system/Observation.read",
    "system/Condition.read",
    "system/MedicationRequest.read",
    "system/DocumentReference.read",
    "system/DiagnosticReport.read",
    "system/Encounter.read",
    "system/Practitioner.read"
]

# Cerner Write Scopes (requires additional permissions)
CERNER_WRITE_SCOPES = [
    "system/Patient.write",
    "system/Observation.write",
    "system/Condition.write",
    "system/MedicationRequest.write",
    "system/DocumentReference.write"
]


class CernerEnvironment(Enum):
    """Cerner environment types."""
    SANDBOX = "sandbox"
    PRODUCTION = "production"


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class CernerError(Exception):
    """Base exception for Cerner-specific errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


class CernerAuthenticationError(CernerError):
    """Raised when Cerner authentication fails."""
    pass


class CernerConnectionError(CernerError):
    """Raised when connection to Cerner fails."""
    pass


class CernerConfigurationError(CernerError):
    """Raised when Cerner configuration is invalid."""
    pass


class CernerResourceNotFoundError(CernerError):
    """Raised when a requested resource is not found."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CernerConfig:
    """
    Cerner-specific configuration.
    
    Attributes:
        tenant_id: Cerner tenant ID (required for production)
        client_id: OAuth client ID (required for production)
        client_secret: OAuth client secret (required for production)
        base_url_template: URL template for FHIR base URL
        token_url_template: URL template for OAuth token endpoint
        use_sandbox: Whether to use Cerner sandbox (no auth required)
        sandbox_url: Cerner sandbox FHIR base URL
        scopes: OAuth scopes to request
        timeout: Request timeout in seconds
        verify_ssl: Whether to verify SSL certificates
    """
    tenant_id: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    base_url_template: str = CERNER_PRODUCTION_BASE_URL_TEMPLATE
    token_url_template: str = CERNER_TOKEN_URL_TEMPLATE
    use_sandbox: bool = False
    sandbox_url: str = CERNER_SANDBOX_BASE_URL
    scopes: List[str] = field(default_factory=lambda: CERNER_DEFAULT_SCOPES.copy())
    timeout: int = 30
    verify_ssl: bool = True
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.use_sandbox and (not self.client_id or not self.client_secret):
            logger.warning("Production mode requires client_id and client_secret")
    
    @property
    def base_url(self) -> str:
        """Get the FHIR base URL based on configuration."""
        if self.use_sandbox:
            return self.sandbox_url
        return self.base_url_template.format(tenant_id=self.tenant_id)
    
    @property
    def token_url(self) -> str:
        """Get the OAuth token URL based on configuration."""
        return self.token_url_template.format(tenant_id=self.tenant_id)
    
    @property
    def environment(self) -> CernerEnvironment:
        """Get the current environment type."""
        return CernerEnvironment.SANDBOX if self.use_sandbox else CernerEnvironment.PRODUCTION
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert config to dictionary, excluding sensitive fields.
        
        Returns:
            Dictionary representation without secrets
        """
        return {
            "tenant_id": self.tenant_id,
            "client_id": self.client_id,
            "base_url": self.base_url,
            "token_url": self.token_url,
            "use_sandbox": self.use_sandbox,
            "scopes": self.scopes,
            "timeout": self.timeout,
            "environment": self.environment.value
        }


@dataclass
class CernerTokenResponse:
    """
    Cerner OAuth token response.
    
    Attributes:
        access_token: The access token for API requests
        token_type: Token type (usually "Bearer")
        expires_in: Token lifetime in seconds
        scope: Granted scopes
        issued_at: When the token was issued
    """
    access_token: str
    token_type: str
    expires_in: int
    scope: str
    issued_at: datetime = field(default_factory=datetime.now)
    
    @property
    def expires_at(self) -> datetime:
        """Calculate token expiration time."""
        return self.issued_at + timedelta(seconds=self.expires_in)
    
    def is_expired(self, buffer_seconds: int = 30) -> bool:
        """
        Check if token is expired or about to expire.
        
        Args:
            buffer_seconds: Buffer time before actual expiration
            
        Returns:
            True if token is expired or will expire within buffer
        """
        return datetime.now() >= self.expires_at - timedelta(seconds=buffer_seconds)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert token response to dictionary."""
        return {
            "access_token": self.access_token[:20] + "...",  # Truncate for security
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "scope": self.scope,
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired()
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CERNER CONNECTOR CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class CernerConnector:
    """
    Cerner-specific FHIR connector with OAuth 2.0 authentication.
    
    Supports both production Cerner instances (with OAuth 2.0 client credentials)
    and Cerner sandbox (no authentication required).
    
    Features:
    - OAuth 2.0 client credentials flow
    - Automatic token caching and refresh
    - Cerner sandbox support
    - Tenant-based URL configuration
    - Cerner-specific identifier systems (MRN, FIN)
    - Cerner Millennium code system support
    
    Example:
        # Using context manager
        with CernerConnector(config) as connector:
            patient = connector.fhir_client.get_patient("12724066")
        
        # Manual connection
        connector = CernerConnector(config)
        connector.connect()
        try:
            patient = connector.fhir_client.get_patient("12724066")
        finally:
            connector.disconnect()
    """
    
    def __init__(self, config: CernerConfig):
        """
        Initialize Cerner connector.
        
        Args:
            config: Cerner-specific configuration
            
        Raises:
            CernerConfigurationError: If configuration is invalid
        """
        self.config = config
        self.fhir_client: Optional[FHIRClient] = None
        self._token_response: Optional[CernerTokenResponse] = None
        self._session: Optional[requests.Session] = None
        self._connected: bool = False
        
        logger.info(f"Initialized CernerConnector for tenant: {config.tenant_id}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONNECTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def connect(self) -> 'CernerConnector':
        """
        Connect to Cerner FHIR server with authentication.
        
        Returns:
            Self for method chaining
            
        Raises:
            CernerAuthenticationError: If authentication fails
            CernerConnectionError: If connection fails
        """
        if self._connected:
            logger.debug("Already connected, reusing existing connection")
            return self
        
        try:
            # Create session for requests
            self._session = requests.Session()
            self._session.verify = self.config.verify_ssl
            
            # Determine base URL and authentication
            if self.config.use_sandbox:
                base_url = self.config.sandbox_url
                # Sandbox doesn't require authentication
                fhir_config = FHIRConfig(
                    base_url=base_url,
                    client_id=self.config.client_id or "cerner-sandbox-client",
                    timeout=self.config.timeout
                )
                logger.info("Connected to Cerner sandbox (no authentication)")
            else:
                # Production: authenticate with client credentials
                if not self.config.client_id or not self.config.client_secret:
                    raise CernerConfigurationError(
                        "client_id and client_secret required for production Cerner",
                        {"tenant_id": self.config.tenant_id}
                    )
                
                base_url = self.config.base_url
                access_token = self._authenticate_client_credentials()
                
                fhir_config = FHIRConfig(
                    base_url=base_url,
                    client_id=self.config.client_id,
                    access_token=access_token,
                    token_url=self.config.token_url,
                    timeout=self.config.timeout
                )
                logger.info(f"Connected to Cerner production: {self.config.tenant_id}")
            
            self.fhir_client = FHIRClient(fhir_config)
            self._connected = True
            
            return self
            
        except CernerError:
            raise
        except requests.exceptions.ConnectionError as e:
            raise CernerConnectionError(
                f"Failed to connect to Cerner: {str(e)}",
                {"base_url": self.config.base_url}
            )
        except Exception as e:
            raise CernerError(f"Unexpected error connecting to Cerner: {str(e)}")
    
    def disconnect(self) -> None:
        """Disconnect from Cerner and clean up resources."""
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
        
        logger.info("Disconnected from Cerner")
    
    def is_connected(self) -> bool:
        """Check if connector is currently connected."""
        return self._connected and self.fhir_client is not None
    
    def _ensure_connected(self) -> None:
        """Ensure connector is connected before operations."""
        if not self.is_connected():
            raise CernerConnectionError(
                "Not connected. Call connect() first.",
                {"tenant_id": self.config.tenant_id}
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # OAUTH 2.0 AUTHENTICATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _authenticate_client_credentials(self) -> str:
        """
        Authenticate with Cerner using OAuth 2.0 client credentials.
        
        Returns:
            Access token
            
        Raises:
            CernerAuthenticationError: If authentication fails
        """
        # Check if existing token is still valid
        if self._token_response and not self._token_response.is_expired():
            logger.debug("Using cached token")
            return self._token_response.access_token
        
        logger.info("Authenticating with Cerner OAuth 2.0...")
        
        try:
            response = requests.post(
                self.config.token_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.config.client_id,
                    'client_secret': self.config.client_secret,
                    'scope': ' '.join(self.config.scopes)
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json'
                },
                timeout=self.config.timeout,
                verify=self.config.verify_ssl
            )
            
            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get('error_description', error_detail)
                except Exception:
                    pass
                
                raise CernerAuthenticationError(
                    f"Cerner authentication failed: {response.status_code}",
                    {
                        "status_code": response.status_code,
                        "error": error_detail,
                        "token_url": self.config.token_url
                    }
                )
            
            token_data = response.json()
            
            self._token_response = CernerTokenResponse(
                access_token=token_data['access_token'],
                token_type=token_data.get('token_type', 'Bearer'),
                expires_in=token_data.get('expires_in', 570),  # Cerner default: 570 seconds
                scope=token_data.get('scope', ' '.join(self.config.scopes))
            )
            
            logger.info(f"Authentication successful, token expires in {self._token_response.expires_in}s")
            
            return self._token_response.access_token
            
        except requests.exceptions.Timeout:
            raise CernerAuthenticationError(
                "Authentication request timed out",
                {"token_url": self.config.token_url, "timeout": self.config.timeout}
            )
        except requests.exceptions.ConnectionError as e:
            raise CernerConnectionError(
                f"Failed to connect to Cerner authentication server: {str(e)}",
                {"token_url": self.config.token_url}
            )
        except CernerError:
            raise
        except Exception as e:
            raise CernerAuthenticationError(f"Unexpected authentication error: {str(e)}")
    
    def refresh_token(self) -> str:
        """
        Force refresh the access token.
        
        Returns:
            New access token
            
        Raises:
            CernerAuthenticationError: If token refresh fails
        """
        if self.config.use_sandbox:
            logger.debug("Sandbox mode, no token to refresh")
            return ""
        
        # Clear existing token to force refresh
        self._token_response = None
        return self._authenticate_client_credentials()
    
    def get_token_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the current access token.
        
        Returns:
            Token information or None if not authenticated
        """
        if self._token_response:
            return self._token_response.to_dict()
        return None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CERNER-SPECIFIC HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_sandbox_test_patients(self) -> List[Dict[str, Any]]:
        """
        Get list of Cerner sandbox test patients.
        
        Returns:
            List of test patient information dictionaries
        """
        return list(CERNER_SANDBOX_TEST_PATIENTS.values())
    
    def get_sandbox_test_patient_ids(self) -> List[str]:
        """
        Get list of Cerner sandbox test patient IDs.
        
        Returns:
            List of patient IDs for testing
        """
        return [p["id"] for p in CERNER_SANDBOX_TEST_PATIENTS.values()]
    
    def get_sandbox_test_patient_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a sandbox test patient by name key.
        
        Args:
            name: Patient key (e.g., "smart_nancy", "smart_joe", "smart_timmy")
            
        Returns:
            Patient info dict or None if not found
        """
        return CERNER_SANDBOX_TEST_PATIENTS.get(name)
    
    def search_patients_by_mrn(self, mrn: str) -> List[Dict[str, Any]]:
        """
        Search for patients by MRN (Medical Record Number).
        
        Args:
            mrn: Medical Record Number
            
        Returns:
            List of matching patient resources
            
        Raises:
            CernerConnectionError: If not connected
        """
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        
        identifier_system = CERNER_IDENTIFIER_SYSTEMS["mrn"]
        
        url = f"{self.fhir_client.config.base_url}Patient"
        params = {
            'identifier': f"{identifier_system}|{mrn}"
        }
        
        try:
            response = self.fhir_client.session.get(
                url,
                params=params,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            bundle = response.json()
            return [entry['resource'] for entry in bundle.get('entry', [])]
            
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Error searching by MRN: {e}")
            return []
    
    def search_patients_by_fin(self, fin: str) -> List[Dict[str, Any]]:
        """
        Search for patients by FIN (Financial Identifier Number).
        
        Args:
            fin: Financial Identifier Number
            
        Returns:
            List of matching patient resources
            
        Raises:
            CernerConnectionError: If not connected
        """
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        
        identifier_system = CERNER_IDENTIFIER_SYSTEMS["fin"]
        
        url = f"{self.fhir_client.config.base_url}Patient"
        params = {
            'identifier': f"{identifier_system}|{fin}"
        }
        
        try:
            response = self.fhir_client.session.get(
                url,
                params=params,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            bundle = response.json()
            return [entry['resource'] for entry in bundle.get('entry', [])]
            
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Error searching by FIN: {e}")
            return []
    
    def search_patients_by_name_and_dob(
        self,
        family_name: str,
        given_name: Optional[str] = None,
        birth_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for patients by name and optionally date of birth.
        
        Args:
            family_name: Patient's family/last name
            given_name: Patient's given/first name (optional)
            birth_date: Patient's date of birth in YYYY-MM-DD format (optional)
            
        Returns:
            List of matching patient resources
        """
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        
        url = f"{self.fhir_client.config.base_url}Patient"
        params = {'family': family_name}
        
        if given_name:
            params['given'] = given_name
        if birth_date:
            params['birthdate'] = birth_date
        
        try:
            response = self.fhir_client.session.get(
                url,
                params=params,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            bundle = response.json()
            return [entry['resource'] for entry in bundle.get('entry', [])]
            
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Error searching by name/DOB: {e}")
            return []
    
    def validate_patient_id(self, patient_id: str) -> bool:
        """
        Validate if patient ID exists in Cerner.
        
        Args:
            patient_id: Cerner patient ID
            
        Returns:
            True if patient exists
        """
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        
        try:
            patient = self.fhir_client.get_patient(patient_id)
            return patient is not None
        except Exception:
            return False
    
    def get_cerner_capability_statement(self) -> Dict[str, Any]:
        """
        Get Cerner FHIR server capability statement.
        
        Returns:
            CapabilityStatement resource
            
        Raises:
            CernerConnectionError: If not connected or request fails
        """
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        
        url = f"{self.fhir_client.config.base_url}metadata"
        
        try:
            response = self.fhir_client.session.get(url, timeout=self.config.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise CernerConnectionError(f"Failed to get capability statement: {str(e)}")
    
    def get_cerner_version(self) -> Optional[str]:
        """
        Get Cerner FHIR server version.
        
        Returns:
            Server version string or None
        """
        try:
            capability = self.get_cerner_capability_statement()
            software = capability.get('software', {})
            return software.get('version')
        except Exception:
            return None
    
    def get_supported_resources(self) -> List[str]:
        """
        Get list of supported FHIR resources.
        
        Returns:
            List of supported resource types
        """
        try:
            capability = self.get_cerner_capability_statement()
            rest = capability.get('rest', [])
            if rest:
                resources = rest[0].get('resource', [])
                return [r.get('type') for r in resources if r.get('type')]
            return []
        except Exception:
            return []
    
    def get_cerner_code_system_url(self, code_set_id: str) -> str:
        """
        Generate Cerner Millennium code system URL.
        
        Args:
            code_set_id: Cerner code set ID
            
        Returns:
            Cerner code system URL
        """
        return f"https://fhir.cerner.com/{self.config.tenant_id}/codeSet/{code_set_id}"
    
    def get_patient(self, patient_id: str) -> Optional[Any]:
        """
        Get patient by ID.
        
        Args:
            patient_id: Cerner patient ID
            
        Returns:
            Patient data or None
        """
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        return self.fhir_client.get_patient(patient_id)
    
    def get_patient_observations(
        self,
        patient_id: str,
        category: Optional[str] = None,
        limit: int = 100
    ) -> List[Any]:
        """
        Get observations for a patient.
        
        Args:
            patient_id: Cerner patient ID
            category: Observation category filter (e.g., "vital-signs", "laboratory")
            limit: Maximum number of results
            
        Returns:
            List of observations
        """
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        
        if category == "vital-signs":
            return self.fhir_client.get_vital_signs(patient_id, limit=limit)
        elif category == "laboratory":
            return self.fhir_client.get_lab_results(patient_id, limit=limit)
        else:
            return self.fhir_client.get_observations(patient_id, limit=limit)
    
    def get_patient_conditions(self, patient_id: str, limit: int = 100) -> List[Any]:
        """
        Get conditions for a patient.
        
        Args:
            patient_id: Cerner patient ID
            limit: Maximum number of results
            
        Returns:
            List of conditions
        """
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        return self.fhir_client.get_conditions(patient_id, limit=limit)
    
    def get_patient_medications(self, patient_id: str, limit: int = 100) -> List[Any]:
        """
        Get medication requests for a patient.
        
        Args:
            patient_id: Cerner patient ID
            limit: Maximum number of results
            
        Returns:
            List of medication requests
        """
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        return self.fhir_client.get_medications(patient_id, limit=limit)
    
    def test_connection(self) -> bool:
        """
        Test connection to Cerner FHIR server.
        
        Returns:
            True if connection is successful
        """
        try:
            if not self.is_connected():
                self.connect()
            capability = self.get_cerner_capability_statement()
            return capability.get('resourceType') == 'CapabilityStatement'
        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONTEXT MANAGER SUPPORT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def __enter__(self) -> 'CernerConnector':
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()
    
    def __repr__(self) -> str:
        """String representation."""
        status = "connected" if self._connected else "disconnected"
        env = self.config.environment.value
        return f"CernerConnector(tenant={self.config.tenant_id}, env={env}, status={status})"


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def create_cerner_sandbox_connector(
    client_id: Optional[str] = None,
    timeout: int = 30
) -> CernerConnector:
    """
    Create Cerner connector for sandbox testing.
    
    The Cerner sandbox is a public FHIR endpoint that doesn't require
    authentication, making it ideal for development and testing.
    
    Args:
        client_id: Optional client ID for logging purposes
        timeout: Request timeout in seconds
        
    Returns:
        CernerConnector configured for sandbox
        
    Example:
        with create_cerner_sandbox_connector() as cerner:
            patient = cerner.fhir_client.get_patient("12724066")
    """
    config = CernerConfig(
        tenant_id=CERNER_SANDBOX_TENANT_ID,
        client_id=client_id,
        use_sandbox=True,
        timeout=timeout
    )
    return CernerConnector(config)


def create_cerner_production_connector(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    scopes: Optional[List[str]] = None,
    timeout: int = 30,
    verify_ssl: bool = True
) -> CernerConnector:
    """
    Create Cerner connector for production use.
    
    Args:
        tenant_id: Cerner tenant ID
        client_id: OAuth client ID
        client_secret: OAuth client secret
        scopes: OAuth scopes (defaults to standard read scopes)
        timeout: Request timeout in seconds
        verify_ssl: Whether to verify SSL certificates
        
    Returns:
        CernerConnector configured for production
        
    Example:
        with create_cerner_production_connector(
            tenant_id="your-tenant-id",
            client_id="your-client-id",
            client_secret="your-client-secret"
        ) as cerner:
            results = cerner.search_patients_by_mrn("12345678")
    """
    config = CernerConfig(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        use_sandbox=False,
        scopes=scopes or CERNER_DEFAULT_SCOPES.copy(),
        timeout=timeout,
        verify_ssl=verify_ssl
    )
    return CernerConnector(config)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Main classes
    "CernerConnector",
    "CernerConfig",
    "CernerTokenResponse",
    "CernerEnvironment",
    
    # Factory functions
    "create_cerner_sandbox_connector",
    "create_cerner_production_connector",
    
    # Exceptions
    "CernerError",
    "CernerAuthenticationError",
    "CernerConnectionError",
    "CernerConfigurationError",
    "CernerResourceNotFoundError",
    
    # Constants
    "CERNER_SANDBOX_TENANT_ID",
    "CERNER_SANDBOX_BASE_URL",
    "CERNER_SANDBOX_TEST_PATIENTS",
    "CERNER_IDENTIFIER_SYSTEMS",
    "CERNER_DEFAULT_SCOPES",
    "CERNER_WRITE_SCOPES",
]
