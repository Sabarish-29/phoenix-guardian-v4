"""
Phoenix Guardian - Meditech EHR Connector.

Provides FHIR R4 integration with Meditech EHR systems. Supports patient
demographics, encounters, and clinical documentation with batch processing
optimization.

Meditech Integration Details:
- FHIR R4 compliant API
- OAuth 2.0 authentication
- Batch request support (batch_size=20)
- SOAP notes → DocumentReference resources

Compliance:
- HIPAA Technical Safeguards (§164.312)
- HL7 FHIR R4 specification
- Meditech Expanse interoperability standards

Dependencies:
- httpx>=0.27.0
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

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
    parse_fhir_patient,
    parse_fhir_encounter,
    create_fhir_document_reference,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════


logger = logging.getLogger(__name__)

# Meditech batch processing preferences
MEDITECH_BATCH_SIZE = 20
MEDITECH_MAX_CONCURRENT = 5

# Meditech FHIR endpoints (example sandbox)
MEDITECH_SANDBOX_BASE_URL = "https://fhir.meditech.com/api/fhir/r4"
MEDITECH_SANDBOX_TOKEN_URL = "https://fhir.meditech.com/auth/oauth2/token"

# Meditech-specific FHIR scopes
MEDITECH_SCOPES = [
    "system/Patient.read",
    "system/Encounter.read",
    "system/Encounter.write",
    "system/DocumentReference.read",
    "system/DocumentReference.write",
    "system/Observation.read",
    "system/Condition.read",
    "system/DiagnosticReport.read",
]


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class MeditechConfig(ConnectorConfig):
    """
    Meditech-specific configuration.
    
    Attributes:
        base_url: Meditech FHIR API base URL
        client_id: OAuth client ID
        client_secret: OAuth client secret
        token_url: OAuth token endpoint
        scopes: OAuth scopes to request
        batch_size: Preferred batch size for requests (default: 20)
        max_concurrent: Maximum concurrent requests
        facility_id: Meditech facility identifier (optional)
    """
    scopes: List[str] = field(default_factory=lambda: MEDITECH_SCOPES.copy())
    batch_size: int = MEDITECH_BATCH_SIZE
    max_concurrent: int = MEDITECH_MAX_CONCURRENT
    facility_id: Optional[str] = None
    
    def __post_init__(self):
        """Set defaults if not provided."""
        if not self.base_url:
            self.base_url = MEDITECH_SANDBOX_BASE_URL
        if not self.token_url:
            self.token_url = MEDITECH_SANDBOX_TOKEN_URL


@dataclass
class BatchResult:
    """Result of a batch operation."""
    successful: List[Any]
    failed: List[Tuple[str, str]]  # (id, error_message)
    
    @property
    def success_count(self) -> int:
        return len(self.successful)
    
    @property
    def failure_count(self) -> int:
        return len(self.failed)
    
    @property
    def total_count(self) -> int:
        return self.success_count + self.failure_count


# ═══════════════════════════════════════════════════════════════════════════════
# MEDITECH CONNECTOR
# ═══════════════════════════════════════════════════════════════════════════════


class MeditechConnector(EHRConnectorBase):
    """
    Meditech FHIR R4 connector with batch processing support.
    
    Implements the EHRConnectorBase interface for Meditech EHR systems.
    Optimized for batch operations with configurable batch size.
    
    Example:
        >>> config = MeditechConfig(
        ...     base_url="https://fhir.meditech.com/api/fhir/r4",
        ...     client_id="your-client-id",
        ...     client_secret="your-client-secret",
        ... )
        >>> async with MeditechConnector(config) as connector:
        ...     patients = await connector.get_patients_batch(["P001", "P002"])
    """
    
    def __init__(self, config: MeditechConfig):
        """
        Initialize Meditech connector.
        
        Args:
            config: Meditech-specific configuration
        """
        super().__init__(config)
        self.meditech_config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
    
    @property
    def connector_name(self) -> str:
        """Return connector name."""
        return "meditech"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # AUTHENTICATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _authenticate(self) -> str:
        """
        Authenticate with Meditech OAuth 2.0.
        
        Returns:
            Access token
            
        Raises:
            EHRAuthenticationError: If authentication fails
        """
        # Check if we have a valid cached token
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token
        
        self.logger.info("🔐 Authenticating with Meditech OAuth 2.0")
        
        client = await self._get_client()
        
        try:
            response = await client.post(
                self.meditech_config.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "scope": " ".join(self.meditech_config.scopes),
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
            
            self.logger.info(f"✅ Meditech authentication successful (expires in {expires_in}s)")
            return self._access_token
            
        except httpx.HTTPStatusError as e:
            raise EHRAuthenticationError(
                f"Meditech authentication failed: {e.response.status_code}",
                connector_name=self.connector_name,
                details={"response": e.response.text},
            )
        except Exception as e:
            raise EHRAuthenticationError(
                f"Meditech authentication error: {str(e)}",
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
        Make an authenticated request to Meditech API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (relative to base URL)
            **kwargs: Additional httpx request arguments
            
        Returns:
            Response JSON as dictionary
            
        Raises:
            EHRConnectionError: If request fails
            EHRNotFoundError: If resource not found
        """
        async with self._semaphore:
            await self._authenticate()
            
            client = await self._get_client()
            url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            headers = await self._get_headers()
            
            # Add Meditech-specific headers
            if self.meditech_config.facility_id:
                headers["X-Meditech-Facility"] = self.meditech_config.facility_id
            
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
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise EHRNotFoundError(
                        f"Resource not found: {endpoint}",
                        connector_name=self.connector_name,
                    )
                raise EHRConnectionError(
                    f"Meditech request failed: {e.response.status_code}",
                    connector_name=self.connector_name,
                    details={"response": e.response.text},
                )
            except httpx.RequestError as e:
                raise EHRConnectionError(
                    f"Meditech connection error: {str(e)}",
                    connector_name=self.connector_name,
                )
    
    async def _batch_request(
        self,
        resource_type: str,
        ids: List[str],
    ) -> BatchResult:
        """
        Execute batch request for multiple resources.
        
        Meditech supports FHIR batch bundles for efficient multi-resource retrieval.
        
        Args:
            resource_type: FHIR resource type (e.g., "Patient")
            ids: List of resource IDs to retrieve
            
        Returns:
            BatchResult with successful and failed items
        """
        successful = []
        failed = []
        
        # Process in batches
        for i in range(0, len(ids), self.meditech_config.batch_size):
            batch_ids = ids[i:i + self.meditech_config.batch_size]
            
            # Create FHIR batch bundle
            bundle = {
                "resourceType": "Bundle",
                "type": "batch",
                "entry": [
                    {
                        "request": {
                            "method": "GET",
                            "url": f"{resource_type}/{id_}",
                        }
                    }
                    for id_ in batch_ids
                ],
            }
            
            try:
                response = await self._request("POST", "", json=bundle)
                
                # Process batch response
                for j, entry in enumerate(response.get("entry", [])):
                    response_obj = entry.get("response", {})
                    status = response_obj.get("status", "")
                    
                    if status.startswith("2"):
                        resource = entry.get("resource")
                        if resource:
                            successful.append(resource)
                    else:
                        failed.append((batch_ids[j], f"Status: {status}"))
                        
            except Exception as e:
                # Mark all IDs in batch as failed
                for id_ in batch_ids:
                    failed.append((id_, str(e)))
        
        return BatchResult(successful=successful, failed=failed)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PATIENT OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_patient(self, patient_id: str) -> PatientData:
        """
        Retrieve patient demographics by ID.
        
        Args:
            patient_id: Meditech patient identifier
            
        Returns:
            PatientData object
            
        Raises:
            EHRNotFoundError: If patient not found
        """
        self.logger.debug(f"📋 Getting patient: {patient_id}")
        
        fhir_resource = await self._request("GET", f"Patient/{patient_id}")
        return parse_fhir_patient(fhir_resource)
    
    async def get_patients_batch(self, patient_ids: List[str]) -> BatchResult:
        """
        Retrieve multiple patients in a batch.
        
        Args:
            patient_ids: List of patient identifiers
            
        Returns:
            BatchResult with PatientData objects
        """
        self.logger.debug(f"📋 Getting {len(patient_ids)} patients in batch")
        
        result = await self._batch_request("Patient", patient_ids)
        
        # Convert FHIR resources to PatientData
        patients = [parse_fhir_patient(r) for r in result.successful]
        return BatchResult(successful=patients, failed=result.failed)
    
    async def search_patients(
        self,
        name: Optional[str] = None,
        birthdate: Optional[str] = None,
        identifier: Optional[str] = None,
        limit: int = 100,
    ) -> List[PatientData]:
        """
        Search for patients by criteria.
        
        Args:
            name: Patient name to search
            birthdate: Birth date (YYYY-MM-DD)
            identifier: Patient identifier/MRN
            limit: Maximum results to return
            
        Returns:
            List of matching PatientData objects
        """
        params = {"_count": limit}
        if name:
            params["name"] = name
        if birthdate:
            params["birthdate"] = birthdate
        if identifier:
            params["identifier"] = identifier
        
        if len(params) == 1:  # Only _count
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
            encounter_id: Meditech encounter identifier
            
        Returns:
            EncounterData object
            
        Raises:
            EHRNotFoundError: If encounter not found
        """
        self.logger.debug(f"📋 Getting encounter: {encounter_id}")
        
        fhir_resource = await self._request("GET", f"Encounter/{encounter_id}")
        return parse_fhir_encounter(fhir_resource)
    
    async def get_encounters_batch(
        self,
        encounter_ids: List[str],
    ) -> BatchResult:
        """
        Retrieve multiple encounters in a batch.
        
        Args:
            encounter_ids: List of encounter identifiers
            
        Returns:
            BatchResult with EncounterData objects
        """
        self.logger.debug(f"📋 Getting {len(encounter_ids)} encounters in batch")
        
        result = await self._batch_request("Encounter", encounter_ids)
        
        # Convert FHIR resources to EncounterData
        encounters = [parse_fhir_encounter(r) for r in result.successful]
        return BatchResult(successful=encounters, failed=result.failed)
    
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
        
        # Add Meditech-specific metadata
        doc_ref["category"] = [
            {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "11506-3",
                        "display": "Progress note",
                    }
                ]
            }
        ]
        
        # Add facility context if available
        if self.meditech_config.facility_id:
            doc_ref["context"]["facilityType"] = {
                "coding": [
                    {
                        "system": "urn:meditech:facility",
                        "code": self.meditech_config.facility_id,
                    }
                ]
            }
        
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
    
    async def write_soap_notes_batch(
        self,
        notes: List[SOAPNote],
    ) -> BatchResult:
        """
        Write multiple SOAP notes in a batch.
        
        Args:
            notes: List of SOAPNote objects
            
        Returns:
            BatchResult with creation status
        """
        self.logger.info(f"📝 Writing {len(notes)} SOAP notes in batch")
        
        successful = []
        failed = []
        
        # Process notes concurrently with semaphore
        async def write_single(note: SOAPNote) -> Tuple[bool, Optional[str]]:
            try:
                await self.write_soap_note(note)
                return True, None
            except Exception as e:
                return False, str(e)
        
        tasks = [write_single(note) for note in notes]
        results = await asyncio.gather(*tasks)
        
        for note, (success, error) in zip(notes, results):
            if success:
                successful.append(note.encounter_id)
            else:
                failed.append((note.encounter_id, error or "Unknown error"))
        
        return BatchResult(successful=successful, failed=failed)


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════


def create_meditech_connector(
    base_url: str,
    client_id: str,
    client_secret: str,
    token_url: Optional[str] = None,
    facility_id: Optional[str] = None,
    batch_size: int = MEDITECH_BATCH_SIZE,
) -> MeditechConnector:
    """
    Factory function to create a Meditech connector.
    
    Args:
        base_url: Meditech FHIR API base URL
        client_id: OAuth client ID
        client_secret: OAuth client secret
        token_url: OAuth token endpoint (optional)
        facility_id: Meditech facility ID (optional)
        batch_size: Batch size for multi-resource requests
        
    Returns:
        Configured MeditechConnector instance
    """
    config = MeditechConfig(
        base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        token_url=token_url,
        facility_id=facility_id,
        batch_size=batch_size,
    )
    return MeditechConnector(config)
