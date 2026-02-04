"""
Phoenix Guardian - EHR Connector Abstraction Layer
Abstract base class and implementations for Epic, Cerner, and Allscripts.
Version: 1.0.0

This module provides:
- Abstract base class for EHR connectors
- Epic FHIR R4 connector (OAuth 2.0 with client credentials)
- Cerner FHIR R4 connector (OAuth 2.0)
- Allscripts FHIR R4 connector (API key authentication)

Each connector handles:
- OAuth 2.0 / API key authentication
- FHIR patient read/write operations
- Rate limiting and throttling
- Error handling and retries
- Connection pooling
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import hashlib
import hmac
import json
import logging
import time
import base64
from urllib.parse import urljoin, urlencode

# Note: In production, these would be actual imports
# import httpx
# import aiohttp

logger = logging.getLogger(__name__)


# ==============================================================================
# Exceptions
# ==============================================================================

class EHRError(Exception):
    """Base exception for EHR operations."""
    pass


class EHRAuthenticationError(EHRError):
    """Authentication with EHR failed."""
    pass


class EHRConnectionError(EHRError):
    """Failed to connect to EHR system."""
    pass


class EHRRateLimitError(EHRError):
    """Rate limit exceeded."""
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s")


class EHRResourceNotFoundError(EHRError):
    """Requested resource not found."""
    pass


class EHRValidationError(EHRError):
    """FHIR resource validation failed."""
    pass


class EHRPermissionError(EHRError):
    """Insufficient permissions for operation."""
    pass


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class FHIRResource:
    """Generic FHIR resource wrapper."""
    resource_type: str
    id: str
    data: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def version_id(self) -> Optional[str]:
        return self.meta.get("versionId")
    
    @property
    def last_updated(self) -> Optional[str]:
        return self.meta.get("lastUpdated")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "resourceType": self.resource_type,
            "id": self.id,
            "meta": self.meta,
            **self.data
        }


@dataclass
class Patient:
    """Patient demographics."""
    id: str
    mrn: str
    given_name: str
    family_name: str
    birth_date: str
    gender: str
    address: Optional[Dict[str, Any]] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    raw_resource: Optional[Dict[str, Any]] = None
    
    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}"
    
    @property
    def age(self) -> int:
        birth = datetime.fromisoformat(self.birth_date)
        today = datetime.now()
        return today.year - birth.year - (
            (today.month, today.day) < (birth.month, birth.day)
        )


@dataclass
class Encounter:
    """Clinical encounter."""
    id: str
    patient_id: str
    status: str
    encounter_class: str
    start_time: str
    end_time: Optional[str] = None
    practitioner_id: Optional[str] = None
    location: Optional[str] = None
    reason: Optional[str] = None
    raw_resource: Optional[Dict[str, Any]] = None


@dataclass
class DocumentReference:
    """Clinical document reference (SOAP notes, reports)."""
    id: str
    patient_id: str
    encounter_id: Optional[str]
    doc_type: str
    status: str
    content: str
    created: str
    author_id: Optional[str] = None
    raw_resource: Optional[Dict[str, Any]] = None


@dataclass
class TokenInfo:
    """OAuth token information."""
    access_token: str
    token_type: str
    expires_at: datetime
    refresh_token: Optional[str] = None
    scope: str = ""
    
    @property
    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at
    
    @property
    def expires_in_seconds(self) -> int:
        delta = self.expires_at - datetime.now()
        return max(0, int(delta.total_seconds()))


# ==============================================================================
# Rate Limiter
# ==============================================================================

class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, requests_per_minute: int):
        self.rate = requests_per_minute
        self.tokens = requests_per_minute
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire a rate limit token."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * (self.rate / 60))
            self.last_update = now
            
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (60 / self.rate)
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1
    
    def acquire_sync(self) -> None:
        """Synchronous version of acquire."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.rate, self.tokens + elapsed * (self.rate / 60))
        self.last_update = now
        
        if self.tokens < 1:
            wait_time = (1 - self.tokens) * (60 / self.rate)
            time.sleep(wait_time)
            self.tokens = 0
        else:
            self.tokens -= 1


# ==============================================================================
# Abstract Base Class
# ==============================================================================

class EHRConnector(ABC):
    """
    Abstract base class for EHR system connectors.
    
    All EHR platform implementations must inherit from this class
    and implement the abstract methods.
    
    Example:
        connector = EpicConnector(config)
        await connector.authenticate()
        patient = await connector.get_patient("12345")
    """
    
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        timeout_seconds: int = 30,
        retry_attempts: int = 3,
        rate_limit_per_minute: int = 100,
    ):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout_seconds
        self.retry_attempts = retry_attempts
        self.rate_limiter = RateLimiter(rate_limit_per_minute)
        
        self._token: Optional[TokenInfo] = None
        self._session = None
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the EHR platform name."""
        pass
    
    @property
    @abstractmethod
    def token_endpoint(self) -> str:
        """Return the OAuth token endpoint."""
        pass
    
    @abstractmethod
    async def authenticate(self) -> TokenInfo:
        """
        Authenticate with the EHR system.
        
        Returns:
            TokenInfo with access token and expiration
        
        Raises:
            EHRAuthenticationError: If authentication fails
        """
        pass
    
    @abstractmethod
    async def get_patient(self, patient_id: str) -> Patient:
        """
        Fetch patient demographics.
        
        Args:
            patient_id: FHIR Patient resource ID
        
        Returns:
            Patient object with demographics
        
        Raises:
            EHRResourceNotFoundError: If patient not found
        """
        pass
    
    @abstractmethod
    async def search_patients(
        self,
        criteria: Dict[str, str],
        max_results: int = 10
    ) -> List[Patient]:
        """
        Search for patients.
        
        Args:
            criteria: Search parameters (name, birthdate, mrn, etc.)
            max_results: Maximum number of results
        
        Returns:
            List of matching Patient objects
        """
        pass
    
    @abstractmethod
    async def get_encounter(self, encounter_id: str) -> Encounter:
        """
        Fetch encounter details.
        
        Args:
            encounter_id: FHIR Encounter resource ID
        
        Returns:
            Encounter object
        
        Raises:
            EHRResourceNotFoundError: If encounter not found
        """
        pass
    
    @abstractmethod
    async def create_document(
        self,
        patient_id: str,
        encounter_id: str,
        doc_type: str,
        content: str,
        author_id: Optional[str] = None
    ) -> DocumentReference:
        """
        Create a clinical document (SOAP note).
        
        Args:
            patient_id: Patient FHIR ID
            encounter_id: Encounter FHIR ID
            doc_type: Document type code
            content: Document text content
            author_id: Optional practitioner ID
        
        Returns:
            Created DocumentReference
        
        Raises:
            EHRValidationError: If document validation fails
        """
        pass
    
    async def ensure_authenticated(self) -> str:
        """
        Ensure we have a valid access token.
        
        Returns:
            Valid access token
        """
        if self._token is None or self._token.is_expired:
            self._token = await self.authenticate()
        return self._token.access_token
    
    async def _make_request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Make an authenticated HTTP request to the EHR.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path (appended to base_url)
            data: Request body for POST/PUT
            params: Query parameters
        
        Returns:
            Response JSON
        
        Raises:
            EHRError: On request failure
        """
        await self.rate_limiter.acquire()
        
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        token = await self.ensure_authenticated()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
        }
        
        # Add platform-specific headers
        headers.update(self._get_custom_headers())
        
        for attempt in range(self.retry_attempts):
            try:
                # Simulated HTTP request (would use httpx in production)
                response = await self._execute_request(
                    method, url, headers, data, params
                )
                return response
            except EHRRateLimitError:
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
            except EHRConnectionError:
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(1)
                else:
                    raise
        
        raise EHRError("Max retries exceeded")
    
    async def _execute_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        data: Optional[Dict],
        params: Optional[Dict],
    ) -> Dict[str, Any]:
        """
        Execute the actual HTTP request.
        
        This is a placeholder that would use httpx/aiohttp in production.
        """
        # In production, this would be:
        # async with httpx.AsyncClient(timeout=self.timeout) as client:
        #     response = await client.request(
        #         method, url, headers=headers, json=data, params=params
        #     )
        #     response.raise_for_status()
        #     return response.json()
        
        logger.debug(f"{method} {url}")
        
        # Simulate successful response for testing
        if "/Patient/" in url:
            return self._mock_patient_response(url.split("/")[-1])
        elif "/Encounter/" in url:
            return self._mock_encounter_response(url.split("/")[-1])
        elif "/DocumentReference" in url and method == "POST":
            return self._mock_document_create_response()
        
        return {"resourceType": "Bundle", "entry": []}
    
    def _get_custom_headers(self) -> Dict[str, str]:
        """Get platform-specific custom headers."""
        return {}
    
    def _mock_patient_response(self, patient_id: str) -> Dict[str, Any]:
        """Generate mock patient response for testing."""
        return {
            "resourceType": "Patient",
            "id": patient_id,
            "meta": {"versionId": "1", "lastUpdated": datetime.now().isoformat()},
            "identifier": [{"system": "urn:oid:1.2.3.4", "value": f"MRN-{patient_id}"}],
            "name": [{"given": ["John"], "family": "Doe"}],
            "birthDate": "1980-01-15",
            "gender": "male",
        }
    
    def _mock_encounter_response(self, encounter_id: str) -> Dict[str, Any]:
        """Generate mock encounter response for testing."""
        return {
            "resourceType": "Encounter",
            "id": encounter_id,
            "status": "in-progress",
            "class": {"code": "AMB", "display": "ambulatory"},
            "subject": {"reference": "Patient/12345"},
            "period": {"start": datetime.now().isoformat()},
        }
    
    def _mock_document_create_response(self) -> Dict[str, Any]:
        """Generate mock document creation response for testing."""
        import secrets
        doc_id = secrets.token_hex(4)  # Secure alternative to MD5
        return {
            "resourceType": "DocumentReference",
            "id": doc_id,
            "status": "current",
            "date": datetime.now().isoformat(),
        }
    
    async def close(self) -> None:
        """Close the connector and release resources."""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# ==============================================================================
# Epic Connector
# ==============================================================================

class EpicConnector(EHRConnector):
    """
    Epic FHIR R4 Connector.
    
    Implements Epic-specific authentication and FHIR operations.
    Uses OAuth 2.0 with client credentials flow (backend services).
    
    Epic-specific features:
    - SMART Backend Services authentication (JWT assertion)
    - Custom Epic-specific extensions
    - MyChart integration support
    """
    
    @property
    def platform_name(self) -> str:
        return "epic"
    
    @property
    def token_endpoint(self) -> str:
        return f"{self.base_url}/oauth2/token"
    
    async def authenticate(self) -> TokenInfo:
        """
        Authenticate using Epic Backend Services OAuth 2.0.
        
        Epic uses JWT assertion for backend authentication.
        """
        logger.info(f"Authenticating with Epic at {self.base_url}")
        
        # Create JWT assertion (would use proper JWT library in production)
        now = datetime.now()
        assertion = self._create_jwt_assertion()
        
        # Token request
        token_data = {
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
            "scope": "system/Patient.read system/Encounter.read system/DocumentReference.write",
        }
        
        # Simulated token response (would make actual HTTP request in production)
        # response = await self._request_token(token_data)
        import secrets
        token = TokenInfo(
            access_token=f"epic_token_{secrets.token_urlsafe(12)}",
            token_type="Bearer",
            expires_at=now + timedelta(hours=1),
            scope=token_data["scope"],
        )
        
        logger.info("Epic authentication successful")
        return token
    
    def _create_jwt_assertion(self) -> str:
        """Create JWT assertion for Epic authentication."""
        import uuid
        # In production, this would create a proper RS384-signed JWT
        # with claims: iss, sub, aud, jti, exp
        header = {"alg": "RS384", "typ": "JWT"}
        payload = {
            "iss": self.client_id,
            "sub": self.client_id,
            "aud": self.token_endpoint,
            "jti": str(uuid.uuid4()),  # Use UUID instead of MD5
            "exp": int((datetime.now() + timedelta(minutes=5)).timestamp()),
        }
        
        # Simulated JWT (would use proper signing in production)
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode()
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        signature = "simulated_signature"
        
        return f"{header_b64}.{payload_b64}.{signature}"
    
    async def get_patient(self, patient_id: str) -> Patient:
        """Fetch patient from Epic."""
        response = await self._make_request("GET", f"/Patient/{patient_id}")
        return self._parse_patient(response)
    
    async def search_patients(
        self,
        criteria: Dict[str, str],
        max_results: int = 10
    ) -> List[Patient]:
        """Search patients in Epic."""
        params = {**criteria, "_count": str(max_results)}
        response = await self._make_request("GET", "/Patient", params=params)
        
        patients = []
        for entry in response.get("entry", []):
            if entry.get("resource", {}).get("resourceType") == "Patient":
                patients.append(self._parse_patient(entry["resource"]))
        
        return patients
    
    async def get_encounter(self, encounter_id: str) -> Encounter:
        """Fetch encounter from Epic."""
        response = await self._make_request("GET", f"/Encounter/{encounter_id}")
        return self._parse_encounter(response)
    
    async def create_document(
        self,
        patient_id: str,
        encounter_id: str,
        doc_type: str,
        content: str,
        author_id: Optional[str] = None
    ) -> DocumentReference:
        """Create clinical document in Epic."""
        document = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {
                "coding": [{"system": "http://loinc.org", "code": doc_type}]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "context": {"encounter": [{"reference": f"Encounter/{encounter_id}"}]},
            "content": [{
                "attachment": {
                    "contentType": "text/plain",
                    "data": base64.b64encode(content.encode()).decode(),
                }
            }],
            "date": datetime.now().isoformat(),
        }
        
        if author_id:
            document["author"] = [{"reference": f"Practitioner/{author_id}"}]
        
        response = await self._make_request("POST", "/DocumentReference", data=document)
        return self._parse_document(response, patient_id, encounter_id, content)
    
    def _get_custom_headers(self) -> Dict[str, str]:
        """Epic-specific headers."""
        return {
            "Epic-Client-ID": self.client_id,
        }
    
    def _parse_patient(self, resource: Dict[str, Any]) -> Patient:
        """Parse FHIR Patient resource to Patient object."""
        names = resource.get("name", [{}])
        name = names[0] if names else {}
        
        identifiers = resource.get("identifier", [])
        mrn = ""
        for ident in identifiers:
            if "MRN" in ident.get("type", {}).get("coding", [{}])[0].get("code", ""):
                mrn = ident.get("value", "")
                break
            elif not mrn:
                mrn = ident.get("value", "")
        
        return Patient(
            id=resource.get("id", ""),
            mrn=mrn,
            given_name=" ".join(name.get("given", ["Unknown"])),
            family_name=name.get("family", "Unknown"),
            birth_date=resource.get("birthDate", "1900-01-01"),
            gender=resource.get("gender", "unknown"),
            raw_resource=resource,
        )
    
    def _parse_encounter(self, resource: Dict[str, Any]) -> Encounter:
        """Parse FHIR Encounter resource to Encounter object."""
        period = resource.get("period", {})
        subject = resource.get("subject", {}).get("reference", "")
        patient_id = subject.split("/")[-1] if subject else ""
        
        return Encounter(
            id=resource.get("id", ""),
            patient_id=patient_id,
            status=resource.get("status", "unknown"),
            encounter_class=resource.get("class", {}).get("code", "unknown"),
            start_time=period.get("start", ""),
            end_time=period.get("end"),
            raw_resource=resource,
        )
    
    def _parse_document(
        self,
        resource: Dict[str, Any],
        patient_id: str,
        encounter_id: str,
        content: str
    ) -> DocumentReference:
        """Parse FHIR DocumentReference resource."""
        return DocumentReference(
            id=resource.get("id", ""),
            patient_id=patient_id,
            encounter_id=encounter_id,
            doc_type=resource.get("type", {}).get("coding", [{}])[0].get("code", ""),
            status=resource.get("status", ""),
            content=content,
            created=resource.get("date", datetime.now().isoformat()),
            raw_resource=resource,
        )


# ==============================================================================
# Cerner Connector
# ==============================================================================

class CernerConnector(EHRConnector):
    """
    Cerner FHIR R4 Connector.
    
    Implements Cerner-specific authentication and FHIR operations.
    Uses OAuth 2.0 with client credentials flow.
    
    Cerner-specific features:
    - Standard OAuth 2.0 client credentials
    - Cerner-specific resource extensions
    - Millennium EHR integration
    """
    
    @property
    def platform_name(self) -> str:
        return "cerner"
    
    @property
    def token_endpoint(self) -> str:
        # Cerner uses a separate authorization server
        return f"{self.base_url.replace('/R4', '')}/oauth2/token"
    
    async def authenticate(self) -> TokenInfo:
        """
        Authenticate using Cerner OAuth 2.0 client credentials.
        """
        logger.info(f"Authenticating with Cerner at {self.base_url}")
        
        now = datetime.now()
        
        # Standard OAuth 2.0 client credentials
        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "system/Patient.read system/Encounter.read system/DocumentReference.write",
        }
        
        # Simulated token response
        import secrets
        token = TokenInfo(
            access_token=f"cerner_token_{secrets.token_urlsafe(12)}",
            token_type="Bearer",
            expires_at=now + timedelta(hours=1),
            scope=token_data["scope"],
        )
        
        logger.info("Cerner authentication successful")
        return token
    
    async def get_patient(self, patient_id: str) -> Patient:
        """Fetch patient from Cerner."""
        response = await self._make_request("GET", f"/Patient/{patient_id}")
        return self._parse_patient(response)
    
    async def search_patients(
        self,
        criteria: Dict[str, str],
        max_results: int = 10
    ) -> List[Patient]:
        """Search patients in Cerner."""
        params = {**criteria, "_count": str(max_results)}
        response = await self._make_request("GET", "/Patient", params=params)
        
        patients = []
        for entry in response.get("entry", []):
            if entry.get("resource", {}).get("resourceType") == "Patient":
                patients.append(self._parse_patient(entry["resource"]))
        
        return patients
    
    async def get_encounter(self, encounter_id: str) -> Encounter:
        """Fetch encounter from Cerner."""
        response = await self._make_request("GET", f"/Encounter/{encounter_id}")
        return self._parse_encounter(response)
    
    async def create_document(
        self,
        patient_id: str,
        encounter_id: str,
        doc_type: str,
        content: str,
        author_id: Optional[str] = None
    ) -> DocumentReference:
        """Create clinical document in Cerner."""
        document = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {
                "coding": [{"system": "http://loinc.org", "code": doc_type}]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "context": {"encounter": [{"reference": f"Encounter/{encounter_id}"}]},
            "content": [{
                "attachment": {
                    "contentType": "text/plain",
                    "data": base64.b64encode(content.encode()).decode(),
                }
            }],
            "date": datetime.now().isoformat(),
        }
        
        if author_id:
            document["author"] = [{"reference": f"Practitioner/{author_id}"}]
        
        response = await self._make_request("POST", "/DocumentReference", data=document)
        return self._parse_document(response, patient_id, encounter_id, content)
    
    def _get_custom_headers(self) -> Dict[str, str]:
        """Cerner-specific headers."""
        return {
            "X-Cerner-Client-Id": self.client_id,
        }
    
    def _parse_patient(self, resource: Dict[str, Any]) -> Patient:
        """Parse FHIR Patient resource to Patient object."""
        names = resource.get("name", [{}])
        name = names[0] if names else {}
        
        identifiers = resource.get("identifier", [])
        mrn = identifiers[0].get("value", "") if identifiers else ""
        
        return Patient(
            id=resource.get("id", ""),
            mrn=mrn,
            given_name=" ".join(name.get("given", ["Unknown"])),
            family_name=name.get("family", "Unknown"),
            birth_date=resource.get("birthDate", "1900-01-01"),
            gender=resource.get("gender", "unknown"),
            raw_resource=resource,
        )
    
    def _parse_encounter(self, resource: Dict[str, Any]) -> Encounter:
        """Parse FHIR Encounter resource to Encounter object."""
        period = resource.get("period", {})
        subject = resource.get("subject", {}).get("reference", "")
        patient_id = subject.split("/")[-1] if subject else ""
        
        return Encounter(
            id=resource.get("id", ""),
            patient_id=patient_id,
            status=resource.get("status", "unknown"),
            encounter_class=resource.get("class", {}).get("code", "unknown"),
            start_time=period.get("start", ""),
            end_time=period.get("end"),
            raw_resource=resource,
        )
    
    def _parse_document(
        self,
        resource: Dict[str, Any],
        patient_id: str,
        encounter_id: str,
        content: str
    ) -> DocumentReference:
        """Parse FHIR DocumentReference resource."""
        return DocumentReference(
            id=resource.get("id", ""),
            patient_id=patient_id,
            encounter_id=encounter_id,
            doc_type=resource.get("type", {}).get("coding", [{}])[0].get("code", ""),
            status=resource.get("status", ""),
            content=content,
            created=resource.get("date", datetime.now().isoformat()),
            raw_resource=resource,
        )


# ==============================================================================
# Allscripts Connector
# ==============================================================================

class AllscriptsConnector(EHRConnector):
    """
    Allscripts FHIR R4 Connector.
    
    Implements Allscripts-specific authentication and FHIR operations.
    Uses API key authentication with custom headers.
    
    Allscripts-specific features:
    - API key + secret authentication
    - Custom header requirements
    - Unity/Veradigm platform support
    """
    
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        api_key: str,
        **kwargs
    ):
        super().__init__(base_url, client_id, client_secret, **kwargs)
        self.api_key = api_key
    
    @property
    def platform_name(self) -> str:
        return "allscripts"
    
    @property
    def token_endpoint(self) -> str:
        return f"{self.base_url}/Unity/Token"
    
    async def authenticate(self) -> TokenInfo:
        """
        Authenticate using Allscripts Unity API.
        
        Allscripts uses a combination of API key and OAuth.
        """
        logger.info(f"Authenticating with Allscripts at {self.base_url}")
        
        now = datetime.now()
        
        # Allscripts-specific authentication
        # Creates a hash-based signature
        timestamp = now.isoformat()
        signature = self._create_signature(timestamp)
        
        # Simulated token response
        import secrets
        token = TokenInfo(
            access_token=f"allscripts_token_{secrets.token_urlsafe(12)}",
            token_type="Bearer",
            expires_at=now + timedelta(hours=8),  # Allscripts tokens last longer
            scope="fhir_complete",
        )
        
        logger.info("Allscripts authentication successful")
        return token
    
    def _create_signature(self, timestamp: str) -> str:
        """Create HMAC signature for Allscripts authentication."""
        message = f"{self.client_id}:{timestamp}:{self.api_key}"
        signature = hmac.new(
            self.client_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def get_patient(self, patient_id: str) -> Patient:
        """Fetch patient from Allscripts."""
        response = await self._make_request("GET", f"/Patient/{patient_id}")
        return self._parse_patient(response)
    
    async def search_patients(
        self,
        criteria: Dict[str, str],
        max_results: int = 10
    ) -> List[Patient]:
        """Search patients in Allscripts."""
        params = {**criteria, "_count": str(max_results)}
        response = await self._make_request("GET", "/Patient", params=params)
        
        patients = []
        for entry in response.get("entry", []):
            if entry.get("resource", {}).get("resourceType") == "Patient":
                patients.append(self._parse_patient(entry["resource"]))
        
        return patients
    
    async def get_encounter(self, encounter_id: str) -> Encounter:
        """Fetch encounter from Allscripts."""
        response = await self._make_request("GET", f"/Encounter/{encounter_id}")
        return self._parse_encounter(response)
    
    async def create_document(
        self,
        patient_id: str,
        encounter_id: str,
        doc_type: str,
        content: str,
        author_id: Optional[str] = None
    ) -> DocumentReference:
        """Create clinical document in Allscripts."""
        # Allscripts has some custom extensions
        document = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {
                "coding": [{"system": "http://loinc.org", "code": doc_type}]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "context": {"encounter": [{"reference": f"Encounter/{encounter_id}"}]},
            "content": [{
                "attachment": {
                    "contentType": "text/plain",
                    "data": base64.b64encode(content.encode()).decode(),
                }
            }],
            "date": datetime.now().isoformat(),
            # Allscripts extension
            "extension": [{
                "url": "http://allscripts.com/fhir/extension/document-source",
                "valueString": "phoenix_guardian"
            }]
        }
        
        if author_id:
            document["author"] = [{"reference": f"Practitioner/{author_id}"}]
        
        response = await self._make_request("POST", "/DocumentReference", data=document)
        return self._parse_document(response, patient_id, encounter_id, content)
    
    def _get_custom_headers(self) -> Dict[str, str]:
        """Allscripts-specific headers."""
        timestamp = datetime.now().isoformat()
        return {
            "X-Allscripts-API-Key": self.api_key,
            "X-Allscripts-Timestamp": timestamp,
            "X-Allscripts-Signature": self._create_signature(timestamp),
        }
    
    def _parse_patient(self, resource: Dict[str, Any]) -> Patient:
        """Parse FHIR Patient resource to Patient object."""
        names = resource.get("name", [{}])
        name = names[0] if names else {}
        
        identifiers = resource.get("identifier", [])
        mrn = identifiers[0].get("value", "") if identifiers else ""
        
        return Patient(
            id=resource.get("id", ""),
            mrn=mrn,
            given_name=" ".join(name.get("given", ["Unknown"])),
            family_name=name.get("family", "Unknown"),
            birth_date=resource.get("birthDate", "1900-01-01"),
            gender=resource.get("gender", "unknown"),
            raw_resource=resource,
        )
    
    def _parse_encounter(self, resource: Dict[str, Any]) -> Encounter:
        """Parse FHIR Encounter resource to Encounter object."""
        period = resource.get("period", {})
        subject = resource.get("subject", {}).get("reference", "")
        patient_id = subject.split("/")[-1] if subject else ""
        
        return Encounter(
            id=resource.get("id", ""),
            patient_id=patient_id,
            status=resource.get("status", "unknown"),
            encounter_class=resource.get("class", {}).get("code", "unknown"),
            start_time=period.get("start", ""),
            end_time=period.get("end"),
            raw_resource=resource,
        )
    
    def _parse_document(
        self,
        resource: Dict[str, Any],
        patient_id: str,
        encounter_id: str,
        content: str
    ) -> DocumentReference:
        """Parse FHIR DocumentReference resource."""
        return DocumentReference(
            id=resource.get("id", ""),
            patient_id=patient_id,
            encounter_id=encounter_id,
            doc_type=resource.get("type", {}).get("coding", [{}])[0].get("code", ""),
            status=resource.get("status", ""),
            content=content,
            created=resource.get("date", datetime.now().isoformat()),
            raw_resource=resource,
        )


# ==============================================================================
# Factory Function
# ==============================================================================

def create_ehr_connector(
    platform: str,
    base_url: str,
    client_id: str,
    client_secret: str,
    **kwargs
) -> EHRConnector:
    """
    Factory function to create the appropriate EHR connector.
    
    Args:
        platform: EHR platform name ("epic", "cerner", "allscripts")
        base_url: Base URL of the FHIR API
        client_id: OAuth client ID
        client_secret: OAuth client secret
        **kwargs: Additional platform-specific parameters
    
    Returns:
        Appropriate EHRConnector subclass instance
    
    Raises:
        ValueError: If platform is not supported
    """
    platform_lower = platform.lower()
    
    if platform_lower == "epic":
        return EpicConnector(base_url, client_id, client_secret, **kwargs)
    elif platform_lower == "cerner":
        return CernerConnector(base_url, client_id, client_secret, **kwargs)
    elif platform_lower == "allscripts":
        api_key = kwargs.pop("api_key", "")
        return AllscriptsConnector(base_url, client_id, client_secret, api_key, **kwargs)
    else:
        raise ValueError(f"Unsupported EHR platform: {platform}. Supported: epic, cerner, allscripts")


def get_connector_for_tenant(tenant_config) -> EHRConnector:
    """
    Create an EHR connector for a tenant configuration.
    
    Args:
        tenant_config: TenantConfig object
    
    Returns:
        Configured EHRConnector for the tenant's EHR platform
    
    Note:
        Client secret must be provided separately (from K8s secrets).
    """
    return create_ehr_connector(
        platform=tenant_config.ehr.platform.value,
        base_url=tenant_config.ehr.base_url,
        client_id=tenant_config.ehr.client_id,
        client_secret="",  # Must be injected from secrets
        timeout_seconds=tenant_config.ehr.timeout_seconds,
        retry_attempts=tenant_config.ehr.retry_attempts,
        rate_limit_per_minute=tenant_config.ehr.rate_limit_per_minute,
    )
