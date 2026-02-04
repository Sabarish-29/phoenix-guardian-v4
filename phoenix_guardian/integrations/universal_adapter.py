"""
Phoenix Guardian - Universal EHR Adapter.

Provides a unified interface for all EHR system integrations, abstracting
away vendor-specific implementations behind a common API.

Supported EHR Systems:
- Epic (FHIR R4 + OAuth 2.0 JWT)
- Cerner (FHIR R4 + OAuth 2.0)
- Allscripts (FHIR R4 + OAuth 2.0)
- Meditech (FHIR R4)
- athenahealth (FHIR R4 + proprietary API)

Compliance:
- HIPAA Technical Safeguards (§164.312)
- HL7 FHIR R4 specification
- SMART on FHIR security framework

Dependencies:
- httpx>=0.27.0
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Type

import httpx


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════


logger = logging.getLogger(__name__)


class EHRType(Enum):
    """Supported EHR system types."""
    EPIC = "epic"
    CERNER = "cerner"
    ALLSCRIPTS = "allscripts"
    MEDITECH = "meditech"
    ATHENAHEALTH = "athenahealth"


# Default timeouts (seconds)
DEFAULT_READ_TIMEOUT = 10.0
DEFAULT_WRITE_TIMEOUT = 15.0
DEFAULT_CONNECT_TIMEOUT = 5.0


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class PatientData:
    """
    Unified patient data structure across all EHR systems.
    
    Attributes:
        patient_id: Unique patient identifier in the EHR system
        name: Patient full name (may be None if restricted)
        dob: Date of birth in ISO format (YYYY-MM-DD)
        mrn: Medical Record Number
        gender: Patient gender code
        address: Patient address (optional)
        phone: Contact phone number (optional)
        email: Contact email (optional)
        identifiers: Additional identifiers from the EHR
    """
    patient_id: str
    name: Optional[str] = None
    dob: Optional[str] = None
    mrn: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    identifiers: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "patient_id": self.patient_id,
            "name": self.name,
            "dob": self.dob,
            "mrn": self.mrn,
            "gender": self.gender,
            "address": self.address,
            "phone": self.phone,
            "email": self.email,
            "identifiers": self.identifiers,
        }


@dataclass
class EncounterData:
    """
    Unified encounter data structure across all EHR systems.
    
    Attributes:
        encounter_id: Unique encounter identifier
        patient_id: Associated patient identifier
        status: Encounter status (planned, arrived, in-progress, finished, etc.)
        encounter_type: Type of encounter (ambulatory, emergency, inpatient, etc.)
        start_time: Encounter start datetime (ISO format)
        end_time: Encounter end datetime (ISO format, optional)
        reason: Reason for visit (optional)
        provider_id: Attending provider ID (optional)
        location: Encounter location (optional)
        diagnosis_codes: ICD-10 diagnosis codes (optional)
    """
    encounter_id: str
    patient_id: str
    status: str
    encounter_type: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    reason: Optional[str] = None
    provider_id: Optional[str] = None
    location: Optional[str] = None
    diagnosis_codes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "encounter_id": self.encounter_id,
            "patient_id": self.patient_id,
            "status": self.status,
            "encounter_type": self.encounter_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "reason": self.reason,
            "provider_id": self.provider_id,
            "location": self.location,
            "diagnosis_codes": self.diagnosis_codes,
        }


@dataclass
class SOAPNote:
    """
    SOAP note structure for clinical documentation.
    
    Attributes:
        encounter_id: Associated encounter identifier
        subjective: Patient's description of symptoms and concerns
        objective: Provider's observations and findings
        assessment: Clinical assessment and diagnosis
        plan: Treatment plan and next steps
        icd_codes: ICD-10 diagnosis codes
        cpt_codes: CPT procedure codes
        author_id: Note author/provider ID (optional)
        authored_date: Note creation datetime (optional)
    """
    encounter_id: str
    subjective: str
    objective: str
    assessment: str
    plan: str
    icd_codes: List[str] = field(default_factory=list)
    cpt_codes: List[str] = field(default_factory=list)
    author_id: Optional[str] = None
    authored_date: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "encounter_id": self.encounter_id,
            "subjective": self.subjective,
            "objective": self.objective,
            "assessment": self.assessment,
            "plan": self.plan,
            "icd_codes": self.icd_codes,
            "cpt_codes": self.cpt_codes,
            "author_id": self.author_id,
            "authored_date": self.authored_date,
        }
    
    def to_text(self) -> str:
        """Convert to plain text SOAP format."""
        lines = [
            "SUBJECTIVE:",
            self.subjective,
            "",
            "OBJECTIVE:",
            self.objective,
            "",
            "ASSESSMENT:",
            self.assessment,
            "",
            "PLAN:",
            self.plan,
        ]
        
        if self.icd_codes:
            lines.extend(["", f"ICD-10: {', '.join(self.icd_codes)}"])
        if self.cpt_codes:
            lines.extend(["", f"CPT: {', '.join(self.cpt_codes)}"])
        
        return "\n".join(lines)


@dataclass
class ConnectorConfig:
    """
    Base configuration for EHR connectors.
    
    Attributes:
        base_url: EHR FHIR API base URL
        client_id: OAuth client ID
        client_secret: OAuth client secret (optional for JWT auth)
        token_url: OAuth token endpoint
        read_timeout: HTTP read timeout in seconds
        write_timeout: HTTP write timeout in seconds
        connect_timeout: HTTP connect timeout in seconds
        max_retries: Maximum retry attempts for failed requests
        verify_ssl: Whether to verify SSL certificates
    """
    base_url: str
    client_id: str
    client_secret: Optional[str] = None
    token_url: Optional[str] = None
    read_timeout: float = DEFAULT_READ_TIMEOUT
    write_timeout: float = DEFAULT_WRITE_TIMEOUT
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT
    max_retries: int = 3
    verify_ssl: bool = True


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════


class EHRConnectorError(Exception):
    """Base exception for EHR connector errors."""
    
    def __init__(
        self,
        message: str,
        connector_name: str = "unknown",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.connector_name = connector_name
        self.details = details or {}


class EHRAuthenticationError(EHRConnectorError):
    """Authentication failed with EHR system."""
    pass


class EHRConnectionError(EHRConnectorError):
    """Failed to connect to EHR system."""
    pass


class EHRNotFoundError(EHRConnectorError):
    """Requested resource not found in EHR system."""
    pass


class EHRValidationError(EHRConnectorError):
    """Data validation failed."""
    pass


class EHRRateLimitError(EHRConnectorError):
    """Rate limit exceeded."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# ABSTRACT BASE CONNECTOR
# ═══════════════════════════════════════════════════════════════════════════════


class EHRConnectorBase(ABC):
    """
    Abstract base class for all EHR connectors.
    
    All EHR-specific connectors must implement this interface to ensure
    consistent behavior across different EHR systems.
    
    Example:
        >>> class MyEHRConnector(EHRConnectorBase):
        ...     async def get_patient(self, patient_id: str) -> PatientData:
        ...         # Implementation
        ...         pass
    """
    
    def __init__(self, config: ConnectorConfig):
        """
        Initialize connector with configuration.
        
        Args:
            config: Connector configuration
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.connector_name}")
        self._client: Optional[httpx.AsyncClient] = None
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
    
    @property
    @abstractmethod
    def connector_name(self) -> str:
        """
        Return the connector name for logging and identification.
        
        Returns:
            Connector name (e.g., "epic", "cerner", "allscripts")
        """
        pass
    
    @abstractmethod
    async def get_patient(self, patient_id: str) -> PatientData:
        """
        Retrieve patient demographics by ID.
        
        Args:
            patient_id: Patient identifier in the EHR system
            
        Returns:
            PatientData object with patient information
            
        Raises:
            EHRNotFoundError: If patient not found
            EHRAuthenticationError: If authentication fails
            EHRConnectionError: If connection fails
        """
        pass
    
    @abstractmethod
    async def get_encounter(self, encounter_id: str) -> EncounterData:
        """
        Retrieve encounter details by ID.
        
        Args:
            encounter_id: Encounter identifier in the EHR system
            
        Returns:
            EncounterData object with encounter information
            
        Raises:
            EHRNotFoundError: If encounter not found
            EHRAuthenticationError: If authentication fails
            EHRConnectionError: If connection fails
        """
        pass
    
    @abstractmethod
    async def write_soap_note(self, note: SOAPNote) -> bool:
        """
        Write a SOAP note to the EHR system.
        
        Args:
            note: SOAPNote object containing clinical documentation
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            EHRValidationError: If note validation fails
            EHRAuthenticationError: If authentication fails
            EHRConnectionError: If connection fails
        """
        pass
    
    @abstractmethod
    async def get_patient_history(
        self,
        patient_id: str,
        days: int = 90,
    ) -> List[EncounterData]:
        """
        Retrieve patient encounter history.
        
        Args:
            patient_id: Patient identifier
            days: Number of days to look back (default 90)
            
        Returns:
            List of EncounterData objects
            
        Raises:
            EHRNotFoundError: If patient not found
            EHRAuthenticationError: If authentication fails
            EHRConnectionError: If connection fails
        """
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HTTP CLIENT MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            timeout = httpx.Timeout(
                connect=self.config.connect_timeout,
                read=self.config.read_timeout,
                write=self.config.write_timeout,
                pool=5.0,
            )
            self._client = httpx.AsyncClient(
                timeout=timeout,
                verify=self.config.verify_ssl,
                follow_redirects=True,
            )
        return self._client
    
    async def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication."""
        headers = {
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
        }
        
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        
        return headers
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> "EHRConnectorBase":
        """Async context manager entry."""
        await self._get_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


# ═══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL ADAPTER
# ═══════════════════════════════════════════════════════════════════════════════


class UniversalEHRAdapter:
    """
    Universal adapter providing unified access to all EHR systems.
    
    This adapter manages multiple EHR connectors and routes requests
    to the appropriate connector based on the EHR type.
    
    Example:
        >>> adapter = UniversalEHRAdapter()
        >>> adapter.register_connector("epic", EpicConnector(config))
        >>> patient = await adapter.get_patient("epic", "12345")
    """
    
    def __init__(self):
        """Initialize universal adapter with empty connector registry."""
        self._connectors: Dict[str, EHRConnectorBase] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_connector(
        self,
        ehr_type: str,
        connector: EHRConnectorBase,
    ) -> None:
        """
        Register an EHR connector.
        
        Args:
            ehr_type: EHR type identifier (e.g., "epic", "cerner")
            connector: EHR connector instance
        """
        ehr_type = ehr_type.lower()
        self._connectors[ehr_type] = connector
        self.logger.info(f"✅ Registered connector: {connector.connector_name}")
    
    def get_connector(self, ehr_type: str) -> EHRConnectorBase:
        """
        Get a registered connector by EHR type.
        
        Args:
            ehr_type: EHR type identifier
            
        Returns:
            EHRConnectorBase instance
            
        Raises:
            KeyError: If connector not registered
        """
        ehr_type = ehr_type.lower()
        if ehr_type not in self._connectors:
            raise KeyError(
                f"No connector registered for EHR type: {ehr_type}. "
                f"Available: {list(self._connectors.keys())}"
            )
        return self._connectors[ehr_type]
    
    def list_connectors(self) -> List[str]:
        """
        List all registered connector types.
        
        Returns:
            List of EHR type identifiers
        """
        return list(self._connectors.keys())
    
    async def get_patient(self, ehr_type: str, patient_id: str) -> PatientData:
        """
        Get patient from specified EHR system.
        
        Args:
            ehr_type: EHR type identifier
            patient_id: Patient identifier
            
        Returns:
            PatientData object
        """
        connector = self.get_connector(ehr_type)
        return await connector.get_patient(patient_id)
    
    async def get_encounter(self, ehr_type: str, encounter_id: str) -> EncounterData:
        """
        Get encounter from specified EHR system.
        
        Args:
            ehr_type: EHR type identifier
            encounter_id: Encounter identifier
            
        Returns:
            EncounterData object
        """
        connector = self.get_connector(ehr_type)
        return await connector.get_encounter(encounter_id)
    
    async def write_soap_note(self, ehr_type: str, note: SOAPNote) -> bool:
        """
        Write SOAP note to specified EHR system.
        
        Args:
            ehr_type: EHR type identifier
            note: SOAPNote object
            
        Returns:
            True if successful
        """
        connector = self.get_connector(ehr_type)
        return await connector.write_soap_note(note)
    
    async def get_patient_history(
        self,
        ehr_type: str,
        patient_id: str,
        days: int = 90,
    ) -> List[EncounterData]:
        """
        Get patient history from specified EHR system.
        
        Args:
            ehr_type: EHR type identifier
            patient_id: Patient identifier
            days: Days to look back
            
        Returns:
            List of EncounterData objects
        """
        connector = self.get_connector(ehr_type)
        return await connector.get_patient_history(patient_id, days)
    
    async def close_all(self) -> None:
        """Close all connector connections."""
        for ehr_type, connector in self._connectors.items():
            try:
                await connector.close()
                self.logger.info(f"🔌 Closed connector: {ehr_type}")
            except Exception as e:
                self.logger.warning(f"Error closing {ehr_type}: {e}")
    
    async def __aenter__(self) -> "UniversalEHRAdapter":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close_all()


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def parse_fhir_patient(fhir_resource: Dict[str, Any]) -> PatientData:
    """
    Parse a FHIR Patient resource into PatientData.
    
    Args:
        fhir_resource: FHIR Patient resource as dictionary
        
    Returns:
        PatientData object
    """
    patient_id = fhir_resource.get("id", "")
    
    # Parse name
    name = None
    names = fhir_resource.get("name", [])
    if names:
        name_obj = names[0]
        given = " ".join(name_obj.get("given", []))
        family = name_obj.get("family", "")
        name = f"{given} {family}".strip() or None
    
    # Parse DOB
    dob = fhir_resource.get("birthDate")
    
    # Parse gender
    gender = fhir_resource.get("gender")
    
    # Parse identifiers (including MRN)
    identifiers = {}
    mrn = None
    for identifier in fhir_resource.get("identifier", []):
        system = identifier.get("system", "")
        value = identifier.get("value", "")
        if value:
            identifiers[system] = value
            # Look for MRN
            if "mrn" in system.lower() or identifier.get("type", {}).get("text", "").lower() == "mrn":
                mrn = value
    
    # Parse address
    address = None
    addresses = fhir_resource.get("address", [])
    if addresses:
        addr = addresses[0]
        lines = addr.get("line", [])
        city = addr.get("city", "")
        state = addr.get("state", "")
        postal = addr.get("postalCode", "")
        address = ", ".join(filter(None, [*lines, city, state, postal]))
    
    # Parse telecom (phone/email)
    phone = None
    email = None
    for telecom in fhir_resource.get("telecom", []):
        system = telecom.get("system")
        value = telecom.get("value")
        if system == "phone" and not phone:
            phone = value
        elif system == "email" and not email:
            email = value
    
    return PatientData(
        patient_id=patient_id,
        name=name,
        dob=dob,
        mrn=mrn,
        gender=gender,
        address=address,
        phone=phone,
        email=email,
        identifiers=identifiers,
    )


def parse_fhir_encounter(fhir_resource: Dict[str, Any]) -> EncounterData:
    """
    Parse a FHIR Encounter resource into EncounterData.
    
    Args:
        fhir_resource: FHIR Encounter resource as dictionary
        
    Returns:
        EncounterData object
    """
    encounter_id = fhir_resource.get("id", "")
    
    # Parse patient reference
    patient_id = ""
    subject = fhir_resource.get("subject", {})
    if subject:
        ref = subject.get("reference", "")
        if ref.startswith("Patient/"):
            patient_id = ref.replace("Patient/", "")
    
    # Parse status
    status = fhir_resource.get("status", "unknown")
    
    # Parse encounter type
    encounter_type = "unknown"
    type_list = fhir_resource.get("type", [])
    if type_list:
        codings = type_list[0].get("coding", [])
        if codings:
            encounter_type = codings[0].get("display", codings[0].get("code", "unknown"))
    
    # Parse class as fallback for type
    if encounter_type == "unknown":
        class_obj = fhir_resource.get("class", {})
        if class_obj:
            encounter_type = class_obj.get("display", class_obj.get("code", "unknown"))
    
    # Parse period
    period = fhir_resource.get("period", {})
    start_time = period.get("start")
    end_time = period.get("end")
    
    # Parse reason
    reason = None
    reasons = fhir_resource.get("reasonCode", [])
    if reasons:
        codings = reasons[0].get("coding", [])
        if codings:
            reason = codings[0].get("display")
    
    # Parse location
    location = None
    locations = fhir_resource.get("location", [])
    if locations:
        loc_ref = locations[0].get("location", {})
        location = loc_ref.get("display")
    
    # Parse diagnosis codes
    diagnosis_codes = []
    for diag in fhir_resource.get("diagnosis", []):
        condition = diag.get("condition", {})
        # If condition is a reference, we'd need to resolve it
        # For now, check for inline coding
        if "coding" in condition:
            for coding in condition.get("coding", []):
                code = coding.get("code")
                if code:
                    diagnosis_codes.append(code)
    
    return EncounterData(
        encounter_id=encounter_id,
        patient_id=patient_id,
        status=status,
        encounter_type=encounter_type,
        start_time=start_time,
        end_time=end_time,
        reason=reason,
        location=location,
        diagnosis_codes=diagnosis_codes,
    )


def create_fhir_document_reference(
    note: SOAPNote,
    patient_id: str,
    author_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a FHIR DocumentReference resource from a SOAP note.
    
    Args:
        note: SOAPNote object
        patient_id: Patient identifier
        author_id: Author/provider identifier (optional)
        
    Returns:
        FHIR DocumentReference resource as dictionary
    """
    import base64
    
    # Encode note content as base64
    content_text = note.to_text()
    content_b64 = base64.b64encode(content_text.encode()).decode()
    
    resource = {
        "resourceType": "DocumentReference",
        "status": "current",
        "type": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "11506-3",
                    "display": "Progress note",
                }
            ]
        },
        "subject": {
            "reference": f"Patient/{patient_id}",
        },
        "context": {
            "encounter": [
                {
                    "reference": f"Encounter/{note.encounter_id}",
                }
            ],
        },
        "content": [
            {
                "attachment": {
                    "contentType": "text/plain",
                    "data": content_b64,
                }
            }
        ],
        "date": note.authored_date or datetime.now().isoformat(),
    }
    
    if author_id:
        resource["author"] = [{"reference": f"Practitioner/{author_id}"}]
    
    return resource
