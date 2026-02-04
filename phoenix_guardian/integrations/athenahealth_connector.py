"""
Phoenix Guardian - athenahealth EHR Connector.

Provides integration with athenahealth EHR systems using both FHIR R4 and
athenahealth's proprietary API. Requires practice_id for all operations.

athenahealth Integration Details:
- FHIR R4 compliant API + proprietary endpoints
- OAuth 2.0 authentication
- Practice ID required for all operations
- SOAP notes → Clinical document API

Compliance:
- HIPAA Technical Safeguards (§164.312)
- HL7 FHIR R4 specification
- athenahealth API security requirements

Dependencies:
- httpx>=0.27.0
"""

import logging
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
    parse_fhir_patient,
    parse_fhir_encounter,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════


logger = logging.getLogger(__name__)

# athenahealth API environments
ATHENA_SANDBOX_BASE_URL = "https://api.preview.platform.athenahealth.com/fhir/r4"
ATHENA_PRODUCTION_BASE_URL = "https://api.platform.athenahealth.com/fhir/r4"
ATHENA_PROPRIETARY_SANDBOX = "https://api.preview.platform.athenahealth.com/v1"
ATHENA_PROPRIETARY_PRODUCTION = "https://api.platform.athenahealth.com/v1"
ATHENA_TOKEN_URL = "https://api.platform.athenahealth.com/oauth2/v1/token"

# athenahealth-specific FHIR scopes
ATHENA_SCOPES = [
    "system/Patient.read",
    "system/Encounter.read",
    "system/DocumentReference.read",
    "system/DocumentReference.write",
    "system/Observation.read",
    "system/Condition.read",
    "athena/service/Athenanet.MDP.*",
]

# athenahealth document types for SOAP notes
ATHENA_DOCUMENT_TYPES = {
    "soap": "ENCOUNTERDOCUMENT",
    "progress_note": "PROGRESSNOTE",
    "consultation": "CONSULTATION",
    "history_physical": "HISTORYPHYSICAL",
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class AthenaConfig(ConnectorConfig):
    """
    athenahealth-specific configuration.
    
    Attributes:
        base_url: athenahealth FHIR API base URL
        proprietary_url: athenahealth proprietary API base URL
        client_id: OAuth client ID
        client_secret: OAuth client secret
        token_url: OAuth token endpoint
        practice_id: Required athenahealth practice ID
        scopes: OAuth scopes to request
        use_sandbox: Whether to use sandbox environment
        department_id: Default department ID (optional)
    """
    practice_id: str = ""
    proprietary_url: Optional[str] = None
    scopes: List[str] = field(default_factory=lambda: ATHENA_SCOPES.copy())
    use_sandbox: bool = True
    department_id: Optional[str] = None
    
    def __post_init__(self):
        """Set defaults based on environment."""
        if self.use_sandbox:
            if not self.base_url:
                self.base_url = ATHENA_SANDBOX_BASE_URL
            if not self.proprietary_url:
                self.proprietary_url = ATHENA_PROPRIETARY_SANDBOX
        else:
            if not self.base_url:
                self.base_url = ATHENA_PRODUCTION_BASE_URL
            if not self.proprietary_url:
                self.proprietary_url = ATHENA_PROPRIETARY_PRODUCTION
        
        if not self.token_url:
            self.token_url = ATHENA_TOKEN_URL
    
    def validate(self) -> None:
        """Validate configuration."""
        if not self.practice_id:
            raise EHRValidationError(
                "practice_id is required for athenahealth connector",
                connector_name="athenahealth",
            )


@dataclass
class AthenaAppointment:
    """athenahealth appointment data."""
    appointment_id: str
    patient_id: str
    department_id: str
    provider_id: str
    appointment_type: str
    appointment_date: str
    appointment_time: str
    status: str
    duration_minutes: int = 0
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "appointment_id": self.appointment_id,
            "patient_id": self.patient_id,
            "department_id": self.department_id,
            "provider_id": self.provider_id,
            "appointment_type": self.appointment_type,
            "appointment_date": self.appointment_date,
            "appointment_time": self.appointment_time,
            "status": self.status,
            "duration_minutes": self.duration_minutes,
            "reason": self.reason,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ATHENAHEALTH CONNECTOR
# ═══════════════════════════════════════════════════════════════════════════════


class AthenaConnector(EHRConnectorBase):
    """
    athenahealth connector with FHIR R4 and proprietary API support.
    
    Implements the EHRConnectorBase interface for athenahealth EHR.
    Combines FHIR R4 for standard operations and proprietary API for
    athenahealth-specific features.
    
    Note: practice_id is required for all operations.
    
    Example:
        >>> config = AthenaConfig(
        ...     base_url="https://api.preview.platform.athenahealth.com/fhir/r4",
        ...     client_id="your-client-id",
        ...     client_secret="your-client-secret",
        ...     practice_id="195900",
        ... )
        >>> async with AthenaConnector(config) as connector:
        ...     patient = await connector.get_patient("12345")
        ...     print(patient.name)
    """
    
    def __init__(self, config: AthenaConfig):
        """
        Initialize athenahealth connector.
        
        Args:
            config: athenahealth-specific configuration
            
        Raises:
            EHRValidationError: If practice_id not provided
        """
        super().__init__(config)
        self.athena_config = config
        config.validate()
    
    @property
    def connector_name(self) -> str:
        """Return connector name."""
        return "athenahealth"
    
    @property
    def practice_id(self) -> str:
        """Get practice ID."""
        return self.athena_config.practice_id
    
    # ═══════════════════════════════════════════════════════════════════════════
    # AUTHENTICATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _authenticate(self) -> str:
        """
        Authenticate with athenahealth OAuth 2.0.
        
        Returns:
            Access token
            
        Raises:
            EHRAuthenticationError: If authentication fails
        """
        # Check if we have a valid cached token
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token
        
        self.logger.info("🔐 Authenticating with athenahealth OAuth 2.0")
        
        client = await self._get_client()
        
        try:
            # athenahealth uses basic auth for token request
            import base64
            credentials = base64.b64encode(
                f"{self.config.client_id}:{self.config.client_secret}".encode()
            ).decode()
            
            response = await client.post(
                self.athena_config.token_url,
                data={
                    "grant_type": "client_credentials",
                    "scope": " ".join(self.athena_config.scopes),
                },
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            
            token_data = response.json()
            self._access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            self.logger.info(f"✅ athenahealth authentication successful (expires in {expires_in}s)")
            return self._access_token
            
        except httpx.HTTPStatusError as e:
            raise EHRAuthenticationError(
                f"athenahealth authentication failed: {e.response.status_code}",
                connector_name=self.connector_name,
                details={"response": e.response.text},
            )
        except Exception as e:
            raise EHRAuthenticationError(
                f"athenahealth authentication error: {str(e)}",
                connector_name=self.connector_name,
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HTTP REQUEST HELPERS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _fhir_request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make an authenticated FHIR request.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (relative to FHIR base URL)
            **kwargs: Additional httpx request arguments
            
        Returns:
            Response JSON as dictionary
        """
        await self._authenticate()
        
        client = await self._get_client()
        
        # athenahealth FHIR URLs include practice_id
        base = self.config.base_url.rstrip('/')
        url = f"{base}/{self.practice_id}/{endpoint.lstrip('/')}"
        
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
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise EHRNotFoundError(
                    f"Resource not found: {endpoint}",
                    connector_name=self.connector_name,
                )
            raise EHRConnectionError(
                f"athenahealth FHIR request failed: {e.response.status_code}",
                connector_name=self.connector_name,
                details={"response": e.response.text},
            )
        except httpx.RequestError as e:
            raise EHRConnectionError(
                f"athenahealth connection error: {str(e)}",
                connector_name=self.connector_name,
            )
    
    async def _proprietary_request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make an authenticated proprietary API request.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (relative to proprietary base URL)
            **kwargs: Additional httpx request arguments
            
        Returns:
            Response JSON as dictionary
        """
        await self._authenticate()
        
        client = await self._get_client()
        
        # Proprietary API includes practice_id in path
        base = self.athena_config.proprietary_url.rstrip('/')
        url = f"{base}/{self.practice_id}/{endpoint.lstrip('/')}"
        
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        
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
            
            # Proprietary API may return empty response
            if response.status_code == 204:
                return {}
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise EHRNotFoundError(
                    f"Resource not found: {endpoint}",
                    connector_name=self.connector_name,
                )
            raise EHRConnectionError(
                f"athenahealth API request failed: {e.response.status_code}",
                connector_name=self.connector_name,
                details={"response": e.response.text},
            )
        except httpx.RequestError as e:
            raise EHRConnectionError(
                f"athenahealth connection error: {str(e)}",
                connector_name=self.connector_name,
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PATIENT OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_patient(self, patient_id: str) -> PatientData:
        """
        Retrieve patient demographics by ID.
        
        Args:
            patient_id: athenahealth patient identifier
            
        Returns:
            PatientData object
            
        Raises:
            EHRNotFoundError: If patient not found
        """
        self.logger.debug(f"📋 Getting patient: {patient_id}")
        
        fhir_resource = await self._fhir_request("GET", f"Patient/{patient_id}")
        return parse_fhir_patient(fhir_resource)
    
    async def get_patient_proprietary(self, patient_id: str) -> Dict[str, Any]:
        """
        Retrieve patient using proprietary API (more fields).
        
        Args:
            patient_id: athenahealth patient identifier
            
        Returns:
            Raw patient data from proprietary API
        """
        self.logger.debug(f"📋 Getting patient (proprietary): {patient_id}")
        
        return await self._proprietary_request(
            "GET",
            f"patients/{patient_id}",
        )
    
    async def search_patients(
        self,
        name: Optional[str] = None,
        birthdate: Optional[str] = None,
        identifier: Optional[str] = None,
        department_id: Optional[str] = None,
    ) -> List[PatientData]:
        """
        Search for patients by criteria.
        
        Args:
            name: Patient name to search
            birthdate: Birth date (YYYY-MM-DD)
            identifier: Patient identifier
            department_id: Department ID filter
            
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
        
        # athenahealth-specific: department filter
        if department_id:
            params["_tag"] = f"https://athenahealth.com/fhir/tag/departmentid|{department_id}"
        
        if not params:
            raise EHRValidationError(
                "At least one search parameter required",
                connector_name=self.connector_name,
            )
        
        bundle = await self._fhir_request("GET", "Patient", params=params)
        
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
            encounter_id: athenahealth encounter identifier
            
        Returns:
            EncounterData object
            
        Raises:
            EHRNotFoundError: If encounter not found
        """
        self.logger.debug(f"📋 Getting encounter: {encounter_id}")
        
        fhir_resource = await self._fhir_request("GET", f"Encounter/{encounter_id}")
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
        
        bundle = await self._fhir_request("GET", "Encounter", params=params)
        
        encounters = []
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Encounter":
                encounters.append(parse_fhir_encounter(resource))
        
        return encounters
    
    # ═══════════════════════════════════════════════════════════════════════════
    # APPOINTMENT OPERATIONS (Proprietary API)
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_appointments(
        self,
        department_id: str,
        start_date: str,
        end_date: Optional[str] = None,
        provider_id: Optional[str] = None,
    ) -> List[AthenaAppointment]:
        """
        Get appointments using proprietary API.
        
        Args:
            department_id: Department ID (required)
            start_date: Start date (MM/DD/YYYY)
            end_date: End date (MM/DD/YYYY, optional)
            provider_id: Filter by provider ID (optional)
            
        Returns:
            List of AthenaAppointment objects
        """
        self.logger.debug(f"📋 Getting appointments for dept: {department_id}")
        
        params = {
            "departmentid": department_id,
            "startdate": start_date,
        }
        if end_date:
            params["enddate"] = end_date
        if provider_id:
            params["providerid"] = provider_id
        
        result = await self._proprietary_request(
            "GET",
            "appointments/booked",
            params=params,
        )
        
        appointments = []
        for appt in result.get("appointments", []):
            appointments.append(
                AthenaAppointment(
                    appointment_id=str(appt.get("appointmentid", "")),
                    patient_id=str(appt.get("patientid", "")),
                    department_id=str(appt.get("departmentid", "")),
                    provider_id=str(appt.get("providerid", "")),
                    appointment_type=appt.get("appointmenttype", ""),
                    appointment_date=appt.get("date", ""),
                    appointment_time=appt.get("starttime", ""),
                    status=appt.get("appointmentstatus", ""),
                    duration_minutes=appt.get("duration", 0),
                    reason=appt.get("reasonid"),
                )
            )
        
        return appointments
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CLINICAL DOCUMENTATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def write_soap_note(self, note: SOAPNote) -> bool:
        """
        Write a SOAP note using proprietary clinical document API.
        
        athenahealth uses a proprietary API for clinical documentation
        that differs from standard FHIR DocumentReference.
        
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
        
        # Get department_id from encounter or config
        department_id = self.athena_config.department_id
        if not department_id:
            # Try to get from encounter
            encounter = await self.get_encounter(note.encounter_id)
            # Parse department from location if available
            department_id = "1"  # Default fallback
        
        # Build clinical document for proprietary API
        document_data = {
            "encounterid": note.encounter_id,
            "departmentid": department_id,
            "documentclass": "ENCOUNTERDOCUMENT",
            "documentsubclass": "PROGRESSNOTE",
            "content": note.to_text(),
            "status": "FINAL",
        }
        
        # Add diagnosis codes if present
        if note.icd_codes:
            document_data["diagnosiscodes"] = ",".join(note.icd_codes)
        
        # Add procedure codes if present
        if note.cpt_codes:
            document_data["procedurecodes"] = ",".join(note.cpt_codes)
        
        # Add author if present
        if note.author_id:
            document_data["providerid"] = note.author_id
        
        try:
            result = await self._proprietary_request(
                "POST",
                f"chart/encounter/{note.encounter_id}/documents",
                json=document_data,
            )
            
            doc_id = result.get("documentid", "")
            self.logger.info(f"✅ SOAP note created: documentid={doc_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to write SOAP note: {e}")
            raise
    
    async def get_clinical_documents(
        self,
        patient_id: str,
        department_id: str,
        document_class: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get clinical documents for a patient.
        
        Args:
            patient_id: Patient identifier
            department_id: Department identifier
            document_class: Filter by document class (optional)
            
        Returns:
            List of document dictionaries
        """
        params = {
            "departmentid": department_id,
        }
        if document_class:
            params["documentclass"] = document_class
        
        result = await self._proprietary_request(
            "GET",
            f"patients/{patient_id}/documents",
            params=params,
        )
        
        return result.get("documents", [])


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════


def create_athena_connector(
    practice_id: str,
    client_id: str,
    client_secret: str,
    use_sandbox: bool = True,
    department_id: Optional[str] = None,
) -> AthenaConnector:
    """
    Factory function to create an athenahealth connector.
    
    Args:
        practice_id: athenahealth practice ID (required)
        client_id: OAuth client ID
        client_secret: OAuth client secret
        use_sandbox: Whether to use sandbox environment
        department_id: Default department ID (optional)
        
    Returns:
        Configured AthenaConnector instance
    """
    config = AthenaConfig(
        base_url="",  # Will be set based on use_sandbox
        client_id=client_id,
        client_secret=client_secret,
        practice_id=practice_id,
        use_sandbox=use_sandbox,
        department_id=department_id,
    )
    return AthenaConnector(config)
