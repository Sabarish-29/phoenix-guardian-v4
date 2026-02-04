"""
Epic FHIR Connector for Phoenix Guardian EHR Integration.

This module provides Epic-specific FHIR connectivity with OAuth 2.0 JWT
authentication following Epic's Backend Services specification.

Features:
- Epic OAuth 2.0 JWT (RS384) authentication
- Epic sandbox testing support
- Epic-specific patient matching
- Epic OperationOutcome handling
- Connection pooling and retry logic

Epic Documentation:
- https://fhir.epic.com/Documentation
- https://open.epic.com/

Dependencies:
- PyJWT>=2.8.0
- cryptography>=41.0.0
"""

import logging
import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

import jwt
import requests
from requests.exceptions import RequestException, Timeout

from .fhir_client import (
    FHIRClient,
    FHIRConfig,
    FHIRPatient,
    FHIRObservation,
    FHIRCondition,
    FHIRMedicationRequest,
    FHIRError,
    FHIRAuthenticationError,
    FHIRNotFoundError,
    FHIRConnectionError,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════


class EpicEnvironment(Enum):
    """Epic environment types."""
    SANDBOX = "sandbox"
    PRODUCTION = "production"


# Epic Sandbox Test Patient IDs
EPIC_SANDBOX_TEST_PATIENTS = {
    "derrick_lin": "Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB",
    "mychart_amy": "erXuFYUfucBZaryVksYEcMg3",
    "mychart_billy": "eq081-VQEgP8drUUqCWzHfw3",
}

# Epic FHIR Endpoint URLs
EPIC_SANDBOX_BASE_URL = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/"
EPIC_SANDBOX_TOKEN_URL = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"

# Epic Identifier Systems (OIDs)
EPIC_IDENTIFIER_SYSTEMS = {
    "epic_internal": "urn:oid:1.2.840.114350",
    "epic_mrn": "urn:oid:1.2.840.114350.1.13",
    "epic_fhir_id": "urn:oid:1.2.840.114350.1.13.0.1.7.5.737384.0",
    "ssn": "http://hl7.org/fhir/sid/us-ssn",
    "npi": "http://hl7.org/fhir/sid/us-npi",
}

# Epic-specific FHIR scopes
EPIC_SCOPES = {
    "patient_read": "system/Patient.read",
    "patient_write": "system/Patient.write",
    "observation_read": "system/Observation.read",
    "observation_write": "system/Observation.write",
    "condition_read": "system/Condition.read",
    "condition_write": "system/Condition.write",
    "medication_read": "system/MedicationRequest.read",
    "medication_write": "system/MedicationRequest.write",
    "document_read": "system/DocumentReference.read",
    "document_write": "system/DocumentReference.write",
    "encounter_read": "system/Encounter.read",
    "practitioner_read": "system/Practitioner.read",
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class EpicConfig:
    """
    Epic-specific configuration.
    
    For sandbox testing, set use_sandbox=True and no authentication is required.
    For production, provide client_id and either private_key or private_key_path.
    
    Attributes:
        client_id: Epic App Orchard client ID
        private_key_path: Path to RSA private key file (PEM format)
        private_key: RSA private key content (PEM format)
        base_url: Epic FHIR base URL
        token_url: Epic OAuth token endpoint
        use_sandbox: Whether to use Epic public sandbox
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        scopes: OAuth scopes to request
        organization_id: Epic organization ID (optional)
    """
    client_id: str
    private_key_path: Optional[str] = None
    private_key: Optional[str] = None
    base_url: str = EPIC_SANDBOX_BASE_URL
    token_url: str = EPIC_SANDBOX_TOKEN_URL
    use_sandbox: bool = False
    timeout: int = 30
    max_retries: int = 3
    scopes: List[str] = field(default_factory=list)
    organization_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.use_sandbox:
            if not self.private_key and not self.private_key_path:
                # Will be validated at connection time
                pass
        
        # Set default scopes if not provided
        if not self.scopes:
            self.scopes = [
                EPIC_SCOPES["patient_read"],
                EPIC_SCOPES["observation_read"],
                EPIC_SCOPES["observation_write"],
                EPIC_SCOPES["condition_read"],
                EPIC_SCOPES["medication_read"],
                EPIC_SCOPES["document_read"],
                EPIC_SCOPES["document_write"],
            ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding secrets)."""
        return {
            "client_id": self.client_id,
            "base_url": self.base_url,
            "token_url": self.token_url,
            "use_sandbox": self.use_sandbox,
            "timeout": self.timeout,
            "organization_id": self.organization_id,
        }


@dataclass
class EpicTokenResponse:
    """Epic OAuth token response."""
    access_token: str
    token_type: str
    expires_in: int
    scope: str
    expires_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Calculate expiration time."""
        if self.expires_at == datetime.now():
            self.expires_at = datetime.now() + timedelta(seconds=self.expires_in)
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 5 min buffer)."""
        return datetime.now() >= self.expires_at - timedelta(minutes=5)


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════


class EpicError(Exception):
    """Base exception for Epic connector errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class EpicAuthenticationError(EpicError):
    """Epic authentication failed."""
    pass


class EpicConnectionError(EpicError):
    """Epic connection error."""
    pass


class EpicConfigurationError(EpicError):
    """Epic configuration error."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# EPIC CONNECTOR
# ═══════════════════════════════════════════════════════════════════════════════


class EpicConnector:
    """
    Epic-specific FHIR connector with OAuth 2.0 JWT authentication.
    
    Supports both production Epic instances and Epic public sandbox.
    
    Example (Sandbox):
        >>> config = EpicConfig(client_id="test", use_sandbox=True)
        >>> with EpicConnector(config) as epic:
        ...     patient = epic.fhir_client.get_patient(epic.get_sandbox_test_patients()[0])
        ...     print(patient.name)
    
    Example (Production):
        >>> config = EpicConfig(
        ...     client_id="your-client-id",
        ...     private_key_path="/path/to/key.pem",
        ...     base_url="https://hospital.epic.com/api/FHIR/R4/",
        ...     token_url="https://hospital.epic.com/oauth2/token"
        ... )
        >>> with EpicConnector(config) as epic:
        ...     patient = epic.fhir_client.get_patient("12345")
    """
    
    def __init__(self, config: EpicConfig):
        """
        Initialize Epic connector.
        
        Args:
            config: Epic-specific configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        self.fhir_client: Optional[FHIRClient] = None
        self._token_response: Optional[EpicTokenResponse] = None
        self._private_key_cache: Optional[str] = None
        self._connected: bool = False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONNECTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def connect(self) -> "FHIRClient":
        """
        Connect to Epic FHIR server with authentication.
        
        For sandbox mode, creates unauthenticated connection.
        For production, performs JWT authentication first.
        
        Returns:
            Authenticated FHIRClient instance
            
        Raises:
            EpicConfigurationError: If configuration is invalid
            EpicAuthenticationError: If authentication fails
            EpicConnectionError: If connection fails
        """
        if self._connected and self.fhir_client:
            # Check if token needs refresh
            if not self.config.use_sandbox and self._token_response:
                if self._token_response.is_expired:
                    self._refresh_token()
            return self.fhir_client
        
        # Sandbox mode - no authentication required
        if self.config.use_sandbox:
            self.logger.info("🧪 Connecting to Epic sandbox (no auth)")
            fhir_config = FHIRConfig(
                base_url=self.config.base_url,
                client_id=self.config.client_id,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            )
            self.fhir_client = FHIRClient(fhir_config)
            self._connected = True
            self.logger.info("✅ Connected to Epic sandbox")
            return self.fhir_client
        
        # Production mode - JWT authentication required
        self.logger.info("🔐 Authenticating with Epic (JWT)")
        access_token = self._authenticate_jwt()
        
        fhir_config = FHIRConfig(
            base_url=self.config.base_url,
            client_id=self.config.client_id,
            access_token=access_token,
            token_url=self.config.token_url,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )
        
        self.fhir_client = FHIRClient(fhir_config)
        self._connected = True
        self.logger.info("✅ Connected to Epic production")
        return self.fhir_client
    
    def disconnect(self) -> None:
        """Disconnect from Epic FHIR server."""
        if self.fhir_client:
            self.fhir_client.close()
            self.fhir_client = None
        self._connected = False
        self._token_response = None
        self.logger.info("🔌 Disconnected from Epic")
    
    def is_connected(self) -> bool:
        """Check if connected to Epic."""
        return self._connected and self.fhir_client is not None
    
    def _refresh_token(self) -> None:
        """Refresh the access token if expired."""
        if self.config.use_sandbox:
            return
        
        self.logger.info("🔄 Refreshing Epic access token")
        access_token = self._authenticate_jwt()
        
        if self.fhir_client:
            self.fhir_client._update_access_token(
                access_token,
                self._token_response.expires_in if self._token_response else 3600
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # JWT AUTHENTICATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _authenticate_jwt(self) -> str:
        """
        Authenticate with Epic using JWT assertion (Backend Services).
        
        Returns:
            Access token
            
        Raises:
            EpicConfigurationError: If private key is missing
            EpicAuthenticationError: If authentication fails
        """
        # Check if we have a valid cached token
        if self._token_response and not self._token_response.is_expired:
            return self._token_response.access_token
        
        # Load private key
        private_key = self._load_private_key()
        
        # Generate JWT assertion
        jwt_assertion = self._generate_jwt_assertion(private_key)
        
        # Exchange JWT for access token
        try:
            response = requests.post(
                self.config.token_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                    'client_assertion': jwt_assertion,
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json',
                },
                timeout=self.config.timeout
            )
            
            if response.status_code != 200:
                error_detail = self._parse_error_response(response)
                raise EpicAuthenticationError(
                    f"Epic authentication failed: {response.status_code}",
                    details=error_detail
                )
            
            token_data = response.json()
            
            self._token_response = EpicTokenResponse(
                access_token=token_data['access_token'],
                token_type=token_data.get('token_type', 'Bearer'),
                expires_in=token_data.get('expires_in', 3600),
                scope=token_data.get('scope', ''),
            )
            
            self.logger.info(f"✅ Epic JWT authentication successful (expires in {self._token_response.expires_in}s)")
            return self._token_response.access_token
            
        except Timeout:
            raise EpicConnectionError(f"Epic authentication timeout after {self.config.timeout}s")
        except RequestException as e:
            raise EpicConnectionError(f"Epic authentication connection error: {e}")
        except EpicError:
            raise
        except Exception as e:
            raise EpicAuthenticationError(f"Epic authentication failed: {e}")
    
    def _load_private_key(self) -> str:
        """
        Load RSA private key from config or file.
        
        Returns:
            Private key in PEM format
            
        Raises:
            EpicConfigurationError: If private key is not available
        """
        # Return cached key
        if self._private_key_cache:
            return self._private_key_cache
        
        # Load from config
        if self.config.private_key:
            self._private_key_cache = self.config.private_key
            return self._private_key_cache
        
        # Load from file
        if self.config.private_key_path:
            path = Path(self.config.private_key_path)
            if not path.exists():
                raise EpicConfigurationError(
                    f"Private key file not found: {self.config.private_key_path}"
                )
            
            try:
                self._private_key_cache = path.read_text()
                return self._private_key_cache
            except IOError as e:
                raise EpicConfigurationError(f"Failed to read private key: {e}")
        
        raise EpicConfigurationError(
            "Either private_key or private_key_path must be provided for production mode"
        )
    
    def _generate_jwt_assertion(self, private_key: str) -> str:
        """
        Generate JWT assertion for Epic authentication.
        
        Epic requires RS384 (RSA with SHA-384) algorithm.
        
        Args:
            private_key: RSA private key in PEM format
            
        Returns:
            Signed JWT token
            
        Raises:
            EpicConfigurationError: If JWT generation fails
        """
        now = int(time.time())
        jti = str(uuid.uuid4())
        
        # JWT Payload per Epic spec
        payload = {
            'iss': self.config.client_id,  # Issuer: Your client ID
            'sub': self.config.client_id,  # Subject: Same as issuer
            'aud': self.config.token_url,  # Audience: Token endpoint
            'jti': jti,                     # JWT ID: Unique identifier
            'exp': now + 300,               # Expiration: 5 minutes from now
            'iat': now,                     # Issued at: Current time
        }
        
        # Add optional claims
        if self.config.organization_id:
            payload['organization'] = self.config.organization_id
        
        try:
            # Sign with RS384 (SHA-384 with RSA) as required by Epic
            token = jwt.encode(
                payload,
                private_key,
                algorithm='RS384',
                headers={
                    'typ': 'JWT',
                    'alg': 'RS384',
                }
            )
            
            self.logger.debug(f"Generated JWT assertion with jti={jti}")
            return token
            
        except jwt.exceptions.InvalidKeyError as e:
            raise EpicConfigurationError(f"Invalid RSA private key: {e}")
        except Exception as e:
            raise EpicConfigurationError(f"Failed to generate JWT: {e}")
    
    def _parse_error_response(self, response: requests.Response) -> Dict[str, Any]:
        """Parse Epic error response."""
        try:
            data = response.json()
            return {
                'status_code': response.status_code,
                'error': data.get('error', 'unknown'),
                'error_description': data.get('error_description', response.text),
            }
        except ValueError:
            return {
                'status_code': response.status_code,
                'error': 'parse_error',
                'error_description': response.text,
            }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EPIC SANDBOX HELPERS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_sandbox_test_patients(self) -> List[str]:
        """
        Get list of Epic sandbox test patient IDs.
        
        These are publicly available test patients in Epic's sandbox environment.
        
        Returns:
            List of patient IDs for testing
        """
        return list(EPIC_SANDBOX_TEST_PATIENTS.values())
    
    def get_sandbox_test_patient_by_name(self, name: str) -> Optional[str]:
        """
        Get sandbox test patient ID by name.
        
        Args:
            name: Patient name key (derrick_lin, mychart_amy, mychart_billy)
            
        Returns:
            Patient ID or None if not found
        """
        return EPIC_SANDBOX_TEST_PATIENTS.get(name.lower().replace(" ", "_"))
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EPIC-SPECIFIC OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def search_patients_by_identifier(
        self,
        identifier: str,
        identifier_system: str = "urn:oid:1.2.840.114350"
    ) -> List[FHIRPatient]:
        """
        Search for patients by identifier (MRN, SSN, etc.).
        
        Args:
            identifier: Patient identifier value
            identifier_system: Identifier system OID (default: Epic internal)
            
        Returns:
            List of matching FHIRPatient objects
            
        Raises:
            EpicError: If not connected
        """
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        
        return self.fhir_client.search_patients(
            identifier=f"{identifier_system}|{identifier}"
        )
    
    def search_patients_by_mrn(self, mrn: str) -> List[FHIRPatient]:
        """
        Search for patients by Medical Record Number (MRN).
        
        Args:
            mrn: Medical Record Number
            
        Returns:
            List of matching FHIRPatient objects
        """
        return self.search_patients_by_identifier(
            mrn,
            EPIC_IDENTIFIER_SYSTEMS["epic_mrn"]
        )
    
    def search_patients_by_name_dob(
        self,
        family_name: str,
        given_name: Optional[str] = None,
        birth_date: Optional[str] = None
    ) -> List[FHIRPatient]:
        """
        Search for patients by name and date of birth.
        
        Args:
            family_name: Patient's last name
            given_name: Patient's first name (optional)
            birth_date: Date of birth in YYYY-MM-DD format (optional)
            
        Returns:
            List of matching FHIRPatient objects
        """
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected

        search_params = {'family': family_name}
        
        if given_name:
            search_params['given'] = given_name
        if birth_date:
            search_params['birthdate'] = birth_date
        
        return self.fhir_client.search_patients(**search_params)
    
    def validate_patient_id(self, patient_id: str) -> bool:
        """
        Validate if patient ID exists in Epic.
        
        Args:
            patient_id: Epic FHIR patient ID
            
        Returns:
            True if patient exists, False otherwise
        """
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        
        try:
            patient = self.fhir_client.get_patient(patient_id)
            return patient is not None
        except FHIRNotFoundError:
            return False
        except Exception:
            return False
    
    def get_epic_capability_statement(self) -> Dict[str, Any]:
        """
        Get Epic FHIR server CapabilityStatement.
        
        Returns:
            CapabilityStatement resource with Epic version and capabilities
        """
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        return self.fhir_client.get_server_capabilities()
    
    def get_epic_version(self) -> Tuple[str, str]:
        """
        Get Epic FHIR server version information.
        
        Returns:
            Tuple of (FHIR version, software name)
        """
        capability = self.get_epic_capability_statement()
        
        fhir_version = capability.get('fhirVersion', 'unknown')
        software = capability.get('software', {})
        software_name = software.get('name', 'Epic')
        software_version = software.get('version', '')
        
        return fhir_version, f"{software_name} {software_version}".strip()
    
    def get_supported_resources(self) -> List[str]:
        """
        Get list of supported FHIR resources from Epic.
        
        Returns:
            List of supported resource types
        """
        capability = self.get_epic_capability_statement()
        
        resources = []
        for rest in capability.get('rest', []):
            for resource in rest.get('resource', []):
                resource_type = resource.get('type')
                if resource_type:
                    resources.append(resource_type)
        
        return sorted(resources)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONVENIENCE METHODS (DELEGATES TO FHIR CLIENT)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_patient(self, patient_id: str) -> Optional[FHIRPatient]:
        """Get patient by ID."""
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        return self.fhir_client.get_patient(patient_id)

    def get_patient_observations(
        self,
        patient_id: str,
        code: Optional[str] = None,
        limit: int = 100
    ) -> List[FHIRObservation]:
        """Get observations for patient."""
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        return self.fhir_client.get_observations(patient_id, code=code, limit=limit)

    def get_patient_conditions(
        self,
        patient_id: str,
        active_only: bool = True
    ) -> List[FHIRCondition]:
        """Get conditions for patient."""
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        if active_only:
            return self.fhir_client.get_active_conditions(patient_id)
        return self.fhir_client.get_conditions(patient_id)

    def get_patient_medications(
        self,
        patient_id: str,
        active_only: bool = True
    ) -> List[FHIRMedicationRequest]:
        """Get medications for patient."""
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        if active_only:
            return self.fhir_client.get_active_medications(patient_id)
        return self.fhir_client.get_medications(patient_id)

    def get_patient_summary(self, patient_id: str) -> Dict[str, Any]:
        """Get comprehensive patient summary."""
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        return self.fhir_client.get_patient_summary(patient_id)

    def create_observation(self, observation: FHIRObservation) -> str:
        """Create new observation."""
        self._ensure_connected()
        assert self.fhir_client is not None  # Guaranteed by _ensure_connected
        return self.fhir_client.create_observation(observation)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _ensure_connected(self) -> None:
        """Ensure we're connected to Epic."""
        if not self._connected or not self.fhir_client:
            raise EpicError("Not connected. Call connect() first.")
        
        # Check token expiration for production mode
        if not self.config.use_sandbox and self._token_response:
            if self._token_response.is_expired:
                self._refresh_token()
    
    def test_connection(self) -> bool:
        """
        Test connection to Epic FHIR server.
        
        Returns:
            True if connection is successful
        """
        try:
            self.connect()
            assert self.fhir_client is not None  # Guaranteed by connect()
            return self.fhir_client.test_connection()
        except Exception as e:
            self.logger.error(f"Epic connection test failed: {e}")
            return False
    
    def get_token_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current token information (for debugging).
        
        Returns:
            Token info dict or None if not authenticated
        """
        if not self._token_response:
            return None
        
        return {
            'token_type': self._token_response.token_type,
            'expires_in': self._token_response.expires_in,
            'expires_at': self._token_response.expires_at.isoformat(),
            'is_expired': self._token_response.is_expired,
            'scope': self._token_response.scope,
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONTEXT MANAGER
    # ═══════════════════════════════════════════════════════════════════════════
    
    def __enter__(self) -> "EpicConnector":
        """Context manager entry - connects to Epic."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - disconnects from Epic."""
        self.disconnect()
    
    def __repr__(self) -> str:
        """String representation."""
        mode = "sandbox" if self.config.use_sandbox else "production"
        status = "connected" if self._connected else "disconnected"
        return f"EpicConnector(mode={mode}, status={status}, base_url={self.config.base_url})"


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def create_epic_sandbox_connector(client_id: str = "phoenix-guardian-test") -> EpicConnector:
    """
    Create Epic connector configured for sandbox testing.
    
    Args:
        client_id: Client ID (any value works for sandbox)
        
    Returns:
        Configured EpicConnector for sandbox
    """
    config = EpicConfig(
        client_id=client_id,
        use_sandbox=True,
        base_url=EPIC_SANDBOX_BASE_URL,
        token_url=EPIC_SANDBOX_TOKEN_URL,
    )
    return EpicConnector(config)


def create_epic_production_connector(
    client_id: str,
    private_key_path: str,
    base_url: str,
    token_url: str,
    **kwargs
) -> EpicConnector:
    """
    Create Epic connector configured for production.
    
    Args:
        client_id: Epic App Orchard client ID
        private_key_path: Path to RSA private key
        base_url: Hospital's Epic FHIR base URL
        token_url: Hospital's Epic OAuth token URL
        **kwargs: Additional configuration options
        
    Returns:
        Configured EpicConnector for production
    """
    config = EpicConfig(
        client_id=client_id,
        private_key_path=private_key_path,
        base_url=base_url,
        token_url=token_url,
        use_sandbox=False,
        **kwargs
    )
    return EpicConnector(config)
