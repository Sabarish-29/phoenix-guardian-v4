"""
Phoenix Guardian - Allscripts EHR Connector.

Provides FHIR R4 integration with Allscripts EHR systems using OAuth 2.0
authentication. Supports patient demographics, encounters, and clinical
documentation via DocumentReference resources.

Allscripts Integration Details:
- FHIR R4 compliant API
- OAuth 2.0 authentication flow
- Rate limit: 20 requests/minute
- SOAP notes → DocumentReference resources

Compliance:
- HIPAA Technical Safeguards (§164.312)
- HL7 FHIR R4 specification
- Allscripts API security requirements

Dependencies:
- httpx>=0.27.0
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import httpx

from .universal_adapter import (
    EHRConnectorBase,
    ConnectorConfig,
    PatientData,
    EncounterData,
    SOAPNote,
    EHRAuthenticationError,
    EHRConnectionError,
    EHRNotFoundError,
    EHRValidationError,
    EHRRateLimitError,
    parse_fhir_patient,
    parse_fhir_encounter,
    create_fhir_document_reference,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════


logger = logging.getLogger(__name__)

# Allscripts rate limits
ALLSCRIPTS_RATE_LIMIT = 20  # requests per minute
ALLSCRIPTS_RATE_WINDOW = 60  # seconds

# Allscripts FHIR endpoints
ALLSCRIPTS_SANDBOX_BASE_URL = "https://tw171.allscriptscloud.com/fhir/r4"
ALLSCRIPTS_SANDBOX_TOKEN_URL = "https://tw171.allscriptscloud.com/authorization/connect/token"

# Allscripts-specific FHIR scopes
ALLSCRIPTS_SCOPES = [
    "system/Patient.read",
    "system/Encounter.read",
    "system/DocumentReference.read",
    "system/DocumentReference.write",
    "system/Observation.read",
    "system/Condition.read",
]


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class AllscriptsConfig(ConnectorConfig):
    """
    Allscripts-specific configuration.
    
    Attributes:
        base_url: Allscripts FHIR API base URL
        client_id: OAuth client ID
        client_secret: OAuth client secret
        token_url: OAuth token endpoint
        scopes: OAuth scopes to request
        rate_limit: Maximum requests per minute (default: 20)
        app_name: Allscripts application name for logging
    """
    scopes: List[str] = field(default_factory=lambda: ALLSCRIPTS_SCOPES.copy())
    rate_limit: int = ALLSCRIPTS_RATE_LIMIT
    app_name: str = "PhoenixGuardian"
    
    def __post_init__(self):
        """Set defaults if not provided."""
        if not self.base_url:
            self.base_url = ALLSCRIPTS_SANDBOX_BASE_URL
        if not self.token_url:
            self.token_url = ALLSCRIPTS_SANDBOX_TOKEN_URL


# ═══════════════════════════════════════════════════════════════════════════════
# RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════════


class RateLimiter:
    """
    Token bucket rate limiter for API calls.
    
    Tracks request timestamps and enforces rate limits.
    """
    
    def __init__(self, max_requests: int, window_seconds: int):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._request_times: List[float] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """
        Acquire permission to make a request.
        
        Blocks if rate limit is exceeded until capacity is available.
        
        Raises:
            EHRRateLimitError: If rate limit cannot be acquired
        """
        async with self._lock:
            now = time.time()
            
            # Remove timestamps outside the window
            self._request_times = [
                t for t in self._request_times
                if now - t < self.window_seconds
            ]
            
            if len(self._request_times) >= self.max_requests:
                # Calculate wait time
                oldest = self._request_times[0]
                wait_time = self.window_seconds - (now - oldest)
                if wait_time > 0:
                    logger.warning(
                        f"⏳ Rate limit reached, waiting {wait_time:.1f}s"
                    )
                    await asyncio.sleep(wait_time)
            
            self._request_times.append(time.time())
    
    @property
    def remaining(self) -> int:
        """Get remaining requests in current window."""
        now = time.time()
        active = sum(
            1 for t in self._request_times
            if now - t < self.window_seconds
        )
        return max(0, self.max_requests - active)


# ═══════════════════════════════════════════════════════════════════════════════
# ALLSCRIPTS CONNECTOR
# ═══════════════════════════════════════════════════════════════════════════════


class AllscriptsConnector(EHRConnectorBase):
    """
    Allscripts FHIR R4 connector with OAuth 2.0 authentication.
    
    Implements the EHRConnectorBase interface for Allscripts EHR systems.
    Includes built-in rate limiting to respect Allscripts API limits.
    
    Example:
        >>> config = AllscriptsConfig(
        ...     base_url="https://tw171.allscriptscloud.com/fhir/r4",
        ...     client_id="your-client-id",
        ...     client_secret="your-client-secret",
        ... )
        >>> async with AllscriptsConnector(config) as connector:
        ...     patient = await connector.get_patient("12345")
        ...     print(patient.name)
    """
    
    def __init__(self, config: AllscriptsConfig):
        """
        Initialize Allscripts connector.
        
        Args:
            config: Allscripts-specific configuration
        """
        super().__init__(config)
        self.allscripts_config = config
        self._rate_limiter = RateLimiter(
            max_requests=config.rate_limit,
            window_seconds=ALLSCRIPTS_RATE_WINDOW,
        )
    
    @property
    def connector_name(self) -> str:
        """Return connector name."""
        return "allscripts"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # AUTHENTICATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _authenticate(self) -> str:
        """
        Authenticate with Allscripts OAuth 2.0.
        
        Returns:
            Access token
            
        Raises:
            EHRAuthenticationError: If authentication fails
        """
        # Check if we have a valid cached token
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token
        
        self.logger.info("🔐 Authenticating with Allscripts OAuth 2.0")
        
        client = await self._get_client()
        
        try:
            response = await client.post(
                self.allscripts_config.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "scope": " ".join(self.allscripts_config.scopes),
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            
            token_data = response.json()
            self._access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            self.logger.info(f"✅ Allscripts authentication successful (expires in {expires_in}s)")
            return self._access_token
            
        except httpx.HTTPStatusError as e:
            raise EHRAuthenticationError(
                f"Allscripts authentication failed: {e.response.status_code}",
                connector_name=self.connector_name,
                details={"response": e.response.text},
            )
        except Exception as e:
            raise EHRAuthenticationError(
                f"Allscripts authentication error: {str(e)}",
                connector_name=self.connector_name,
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HTTP REQUEST HELPERS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to Allscripts API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (relative to base URL)
            **kwargs: Additional httpx request arguments
            
        Returns:
            Response JSON as dictionary
            
        Raises:
            EHRConnectionError: If request fails
            EHRNotFoundError: If resource not found
            EHRRateLimitError: If rate limit exceeded
        """
        await self._rate_limiter.acquire()
        await self._authenticate()
        
        client = await self._get_client()
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = await self._get_headers()
        
        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs,
            )
            
            if response.status_code == 404:
                raise EHRNotFoundError(
                    f"Resource not found: {endpoint}",
                    connector_name=self.connector_name,
                )
            
            if response.status_code == 429:
                raise EHRRateLimitError(
                    "Allscripts rate limit exceeded",
                    connector_name=self.connector_name,
                )
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise EHRNotFoundError(
                    f"Resource not found: {endpoint}",
                    connector_name=self.connector_name,
                )
            raise EHRConnectionError(
                f"Allscripts request failed: {e.response.status_code}",
                connector_name=self.connector_name,
                details={"response": e.response.text},
            )
        except httpx.RequestError as e:
            raise EHRConnectionError(
                f"Allscripts connection error: {str(e)}",
                connector_name=self.connector_name,
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PATIENT OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_patient(self, patient_id: str) -> PatientData:
        """
        Retrieve patient demographics by ID.
        
        Args:
            patient_id: Allscripts patient identifier
            
        Returns:
            PatientData object
            
        Raises:
            EHRNotFoundError: If patient not found
        """
        self.logger.debug(f"📋 Getting patient: {patient_id}")
        
        fhir_resource = await self._request("GET", f"Patient/{patient_id}")
        return parse_fhir_patient(fhir_resource)
    
    async def search_patients(
        self,
        name: Optional[str] = None,
        birthdate: Optional[str] = None,
        identifier: Optional[str] = None,
    ) -> List[PatientData]:
        """
        Search for patients by criteria.
        
        Args:
            name: Patient name to search
            birthdate: Birth date (YYYY-MM-DD)
            identifier: Patient identifier/MRN
            
        Returns:
            List of matching PatientData objects
        """
        params = {}
        if name:
            params["name"] = name
        if birthdate:
            params["birthdate"] = birthdate
        if identifier:
            params["identifier"] = identifier
        
        if not params:
            raise EHRValidationError(
                "At least one search parameter required",
                connector_name=self.connector_name,
            )
        
        bundle = await self._request("GET", "Patient", params=params)
        
        patients = []
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Patient":
                patients.append(parse_fhir_patient(resource))
        
        return patients
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ENCOUNTER OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_encounter(self, encounter_id: str) -> EncounterData:
        """
        Retrieve encounter details by ID.
        
        Args:
            encounter_id: Allscripts encounter identifier
            
        Returns:
            EncounterData object
            
        Raises:
            EHRNotFoundError: If encounter not found
        """
        self.logger.debug(f"📋 Getting encounter: {encounter_id}")
        
        fhir_resource = await self._request("GET", f"Encounter/{encounter_id}")
        return parse_fhir_encounter(fhir_resource)
    
    async def get_patient_history(
        self,
        patient_id: str,
        days: int = 90,
    ) -> List[EncounterData]:
        """
        Retrieve patient encounter history.
        
        Args:
            patient_id: Patient identifier
            days: Number of days to look back
            
        Returns:
            List of EncounterData objects
        """
        self.logger.debug(f"📋 Getting history for patient: {patient_id} ({days} days)")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        params = {
            "patient": patient_id,
            "date": f"ge{start_date.strftime('%Y-%m-%d')}",
            "_sort": "-date",
            "_count": 100,
        }
        
        bundle = await self._request("GET", "Encounter", params=params)
        
        encounters = []
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Encounter":
                encounters.append(parse_fhir_encounter(resource))
        
        return encounters
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CLINICAL DOCUMENTATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def write_soap_note(self, note: SOAPNote) -> bool:
        """
        Write a SOAP note as DocumentReference.
        
        Allscripts stores clinical notes as DocumentReference resources.
        
        Args:
            note: SOAPNote object
            
        Returns:
            True if successful
            
        Raises:
            EHRValidationError: If note validation fails
        """
        self.logger.info(f"📝 Writing SOAP note for encounter: {note.encounter_id}")
        
        # Validate required fields
        if not note.encounter_id:
            raise EHRValidationError(
                "Encounter ID required for SOAP note",
                connector_name=self.connector_name,
            )
        
        if not note.subjective and not note.objective:
            raise EHRValidationError(
                "SOAP note must have at least subjective or objective content",
                connector_name=self.connector_name,
            )
        
        # Get patient ID from encounter
        encounter = await self.get_encounter(note.encounter_id)
        patient_id = encounter.patient_id
        
        # Create DocumentReference resource
        doc_ref = create_fhir_document_reference(
            note=note,
            patient_id=patient_id,
            author_id=note.author_id,
        )
        
        # Add Allscripts-specific metadata
        doc_ref["category"] = [
            {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "11488-4",
                        "display": "Consult note",
                    }
                ]
            }
        ]
        
        # POST to create new document
        try:
            result = await self._request(
                "POST",
                "DocumentReference",
                json=doc_ref,
            )
            
            doc_id = result.get("id", "")
            self.logger.info(f"✅ SOAP note created: DocumentReference/{doc_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to write SOAP note: {e}")
            raise


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════


def create_allscripts_connector(
    base_url: str,
    client_id: str,
    client_secret: str,
    token_url: Optional[str] = None,
) -> AllscriptsConnector:
    """
    Factory function to create an Allscripts connector.
    
    Args:
        base_url: Allscripts FHIR API base URL
        client_id: OAuth client ID
        client_secret: OAuth client secret
        token_url: OAuth token endpoint (optional)
        
    Returns:
        Configured AllscriptsConnector instance
    """
    config = AllscriptsConfig(
        base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        token_url=token_url,
    )
    return AllscriptsConnector(config)
