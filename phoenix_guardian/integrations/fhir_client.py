"""
FHIR R4 Client for Phoenix Guardian EHR Integration.

This module provides a unified interface for interacting with FHIR R4 servers
(Epic, Cerner, and other FHIR-compliant EHR systems). It handles:
- FHIR resource CRUD operations
- OAuth 2.0 authentication
- Resource serialization/deserialization
- Error handling and retries

Supported FHIR Resources:
- Patient (Read)
- Observation (Read + Write)
- Condition (Read + Write)
- MedicationRequest (Read + Write)
- DocumentReference (Write)
- DiagnosticReport (Read)
"""

import logging
import base64
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════


class FHIRResourceType(Enum):
    """FHIR resource types."""
    PATIENT = "Patient"
    OBSERVATION = "Observation"
    CONDITION = "Condition"
    MEDICATION_REQUEST = "MedicationRequest"
    DOCUMENT_REFERENCE = "DocumentReference"
    DIAGNOSTIC_REPORT = "DiagnosticReport"
    ENCOUNTER = "Encounter"
    PRACTITIONER = "Practitioner"
    ALLERGY_INTOLERANCE = "AllergyIntolerance"
    PROCEDURE = "Procedure"
    IMMUNIZATION = "Immunization"


class ObservationStatus(Enum):
    """FHIR Observation status."""
    REGISTERED = "registered"
    PRELIMINARY = "preliminary"
    FINAL = "final"
    AMENDED = "amended"
    CORRECTED = "corrected"
    CANCELLED = "cancelled"
    ENTERED_IN_ERROR = "entered-in-error"
    UNKNOWN = "unknown"


class ConditionClinicalStatus(Enum):
    """FHIR Condition clinical status."""
    ACTIVE = "active"
    RECURRENCE = "recurrence"
    RELAPSE = "relapse"
    INACTIVE = "inactive"
    REMISSION = "remission"
    RESOLVED = "resolved"


class ConditionVerificationStatus(Enum):
    """FHIR Condition verification status."""
    UNCONFIRMED = "unconfirmed"
    PROVISIONAL = "provisional"
    DIFFERENTIAL = "differential"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    ENTERED_IN_ERROR = "entered-in-error"


class MedicationRequestStatus(Enum):
    """FHIR MedicationRequest status."""
    ACTIVE = "active"
    ON_HOLD = "on-hold"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    ENTERED_IN_ERROR = "entered-in-error"
    STOPPED = "stopped"
    DRAFT = "draft"
    UNKNOWN = "unknown"


class DocumentReferenceStatus(Enum):
    """FHIR DocumentReference status."""
    CURRENT = "current"
    SUPERSEDED = "superseded"
    ENTERED_IN_ERROR = "entered-in-error"


class ObservationCategory(Enum):
    """FHIR Observation categories."""
    VITAL_SIGNS = "vital-signs"
    LABORATORY = "laboratory"
    IMAGING = "imaging"
    PROCEDURE = "procedure"
    SURVEY = "survey"
    EXAM = "exam"
    THERAPY = "therapy"
    ACTIVITY = "activity"
    SOCIAL_HISTORY = "social-history"


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class FHIRConfig:
    """Configuration for FHIR server connection."""
    base_url: str  # e.g., "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/"
    client_id: str
    client_secret: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_url: Optional[str] = None  # OAuth token endpoint
    authorize_url: Optional[str] = None  # OAuth authorize endpoint
    timeout: int = 30  # Seconds
    max_retries: int = 3
    retry_backoff_factor: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding secrets)."""
        return {
            "base_url": self.base_url,
            "client_id": self.client_id,
            "timeout": self.timeout,
            "max_retries": self.max_retries
        }


@dataclass
class FHIRPatient:
    """Simplified FHIR Patient resource."""
    id: str
    name: str  # "John Doe"
    birth_date: date
    sex: str  # "male", "female", "other", "unknown"
    mrn: Optional[str] = None  # Medical Record Number
    ssn: Optional[str] = None  # Social Security Number (last 4 only)
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    language: Optional[str] = None
    marital_status: Optional[str] = None
    race: Optional[str] = None
    ethnicity: Optional[str] = None
    deceased: bool = False
    active: bool = True
    raw_resource: Optional[Dict[str, Any]] = field(default=None, repr=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "sex": self.sex,
            "mrn": self.mrn,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code,
            "phone": self.phone,
            "email": self.email,
            "language": self.language,
            "marital_status": self.marital_status,
            "deceased": self.deceased,
            "active": self.active
        }
    
    @property
    def age(self) -> int:
        """Calculate patient age."""
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )


@dataclass
class FHIRObservation:
    """Simplified FHIR Observation resource."""
    id: Optional[str] = None
    patient_id: str = ""
    encounter_id: Optional[str] = None
    code: str = ""  # LOINC code
    code_system: str = "http://loinc.org"
    display: str = ""  # "Blood Pressure", "Glucose", etc.
    category: Optional[ObservationCategory] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    value_string: Optional[str] = None  # For non-numeric values
    value_code: Optional[str] = None  # For coded values
    # For blood pressure and other component observations
    component_systolic: Optional[float] = None
    component_diastolic: Optional[float] = None
    status: ObservationStatus = ObservationStatus.FINAL
    effective_date: Optional[datetime] = None
    issued_date: Optional[datetime] = None
    performer_id: Optional[str] = None
    performer_name: Optional[str] = None
    interpretation: Optional[str] = None  # "normal", "high", "low", etc.
    reference_range_low: Optional[float] = None
    reference_range_high: Optional[float] = None
    note: Optional[str] = None
    raw_resource: Optional[Dict[str, Any]] = field(default=None, repr=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "encounter_id": self.encounter_id,
            "code": self.code,
            "code_system": self.code_system,
            "display": self.display,
            "category": self.category.value if self.category else None,
            "value": self.value,
            "unit": self.unit,
            "value_string": self.value_string,
            "value_code": self.value_code,
            "component_systolic": self.component_systolic,
            "component_diastolic": self.component_diastolic,
            "status": self.status.value,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "issued_date": self.issued_date.isoformat() if self.issued_date else None,
            "performer_name": self.performer_name,
            "interpretation": self.interpretation,
            "reference_range_low": self.reference_range_low,
            "reference_range_high": self.reference_range_high,
            "note": self.note
        }


@dataclass
class FHIRCondition:
    """Simplified FHIR Condition resource."""
    id: Optional[str] = None
    patient_id: str = ""
    encounter_id: Optional[str] = None
    code: str = ""  # ICD-10 code
    code_system: str = "http://hl7.org/fhir/sid/icd-10-cm"
    display: str = ""  # "Type 2 Diabetes Mellitus"
    category: Optional[str] = None  # "encounter-diagnosis", "problem-list-item"
    clinical_status: ConditionClinicalStatus = ConditionClinicalStatus.ACTIVE
    verification_status: ConditionVerificationStatus = ConditionVerificationStatus.CONFIRMED
    severity: Optional[str] = None  # "mild", "moderate", "severe"
    onset_date: Optional[date] = None
    abatement_date: Optional[date] = None
    recorded_date: Optional[date] = None
    recorder_id: Optional[str] = None
    recorder_name: Optional[str] = None
    note: Optional[str] = None
    raw_resource: Optional[Dict[str, Any]] = field(default=None, repr=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "encounter_id": self.encounter_id,
            "code": self.code,
            "code_system": self.code_system,
            "display": self.display,
            "category": self.category,
            "clinical_status": self.clinical_status.value,
            "verification_status": self.verification_status.value,
            "severity": self.severity,
            "onset_date": self.onset_date.isoformat() if self.onset_date else None,
            "abatement_date": self.abatement_date.isoformat() if self.abatement_date else None,
            "recorded_date": self.recorded_date.isoformat() if self.recorded_date else None,
            "recorder_name": self.recorder_name,
            "note": self.note
        }


@dataclass
class FHIRMedicationRequest:
    """Simplified FHIR MedicationRequest resource."""
    id: Optional[str] = None
    patient_id: str = ""
    encounter_id: Optional[str] = None
    medication_code: str = ""  # RxNorm code
    medication_code_system: str = "http://www.nlm.nih.gov/research/umls/rxnorm"
    medication_display: str = ""  # "Metformin 1000mg"
    dosage_text: str = ""  # "Take 1 tablet by mouth twice daily"
    dosage_route: Optional[str] = None  # "oral", "intravenous", etc.
    dosage_frequency: Optional[str] = None  # "BID", "TID", "QD"
    dosage_quantity: Optional[float] = None
    dosage_unit: Optional[str] = None
    status: MedicationRequestStatus = MedicationRequestStatus.ACTIVE
    intent: str = "order"  # "proposal", "plan", "order", "original-order"
    priority: Optional[str] = None  # "routine", "urgent", "asap", "stat"
    authored_date: Optional[datetime] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    requester_id: Optional[str] = None
    requester_name: Optional[str] = None
    reason_code: Optional[str] = None
    reason_display: Optional[str] = None
    note: Optional[str] = None
    dispense_quantity: Optional[int] = None
    refills_allowed: Optional[int] = None
    raw_resource: Optional[Dict[str, Any]] = field(default=None, repr=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "encounter_id": self.encounter_id,
            "medication_code": self.medication_code,
            "medication_display": self.medication_display,
            "dosage_text": self.dosage_text,
            "dosage_route": self.dosage_route,
            "dosage_frequency": self.dosage_frequency,
            "dosage_quantity": self.dosage_quantity,
            "dosage_unit": self.dosage_unit,
            "status": self.status.value,
            "intent": self.intent,
            "priority": self.priority,
            "authored_date": self.authored_date.isoformat() if self.authored_date else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "requester_name": self.requester_name,
            "reason_display": self.reason_display,
            "note": self.note,
            "dispense_quantity": self.dispense_quantity,
            "refills_allowed": self.refills_allowed
        }


@dataclass
class FHIRDocumentReference:
    """Simplified FHIR DocumentReference resource."""
    id: Optional[str] = None
    patient_id: str = ""
    encounter_id: Optional[str] = None
    document_type_code: str = ""  # LOINC code for document type
    document_type_display: str = ""  # "Progress Note", "Discharge Summary"
    content: str = ""  # Base64-encoded or plain text
    content_type: str = "text/plain"  # MIME type: "text/plain", "application/pdf"
    status: DocumentReferenceStatus = DocumentReferenceStatus.CURRENT
    doc_status: Optional[str] = None  # "preliminary", "final", "amended"
    created_date: Optional[datetime] = None
    indexed_date: Optional[datetime] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    custodian: Optional[str] = None  # Organization responsible
    description: Optional[str] = None
    security_label: Optional[str] = None
    raw_resource: Optional[Dict[str, Any]] = field(default=None, repr=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "encounter_id": self.encounter_id,
            "document_type_code": self.document_type_code,
            "document_type_display": self.document_type_display,
            "content_type": self.content_type,
            "status": self.status.value,
            "doc_status": self.doc_status,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "author_name": self.author_name,
            "description": self.description
        }


@dataclass
class FHIRDiagnosticReport:
    """Simplified FHIR DiagnosticReport resource."""
    id: Optional[str] = None
    patient_id: str = ""
    encounter_id: Optional[str] = None
    code: str = ""  # LOINC code
    code_system: str = "http://loinc.org"
    display: str = ""  # "Complete Blood Count"
    category: Optional[str] = None  # "LAB", "RAD", "PATH"
    status: str = "final"  # "registered", "preliminary", "final", "amended"
    conclusion: Optional[str] = None
    effective_date: Optional[datetime] = None
    issued_date: Optional[datetime] = None
    performer_id: Optional[str] = None
    performer_name: Optional[str] = None
    result_ids: List[str] = field(default_factory=list)  # Reference to Observation IDs
    presented_form_content: Optional[str] = None  # PDF/text attachment
    presented_form_content_type: Optional[str] = None
    raw_resource: Optional[Dict[str, Any]] = field(default=None, repr=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "encounter_id": self.encounter_id,
            "code": self.code,
            "display": self.display,
            "category": self.category,
            "status": self.status,
            "conclusion": self.conclusion,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "issued_date": self.issued_date.isoformat() if self.issued_date else None,
            "performer_name": self.performer_name,
            "result_ids": self.result_ids
        }


@dataclass
class FHIRBundle:
    """FHIR Bundle resource for batch operations."""
    id: Optional[str] = None
    type: str = "searchset"  # "searchset", "batch", "transaction", etc.
    total: Optional[int] = None
    entries: List[Dict[str, Any]] = field(default_factory=list)
    next_link: Optional[str] = None  # Pagination
    self_link: Optional[str] = None
    raw_resource: Optional[Dict[str, Any]] = field(default=None, repr=False)


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════


class FHIRError(Exception):
    """Base exception for FHIR client errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None,
                 operation_outcome: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.operation_outcome = operation_outcome


class FHIRAuthenticationError(FHIRError):
    """Authentication failed."""
    pass


class FHIRNotFoundError(FHIRError):
    """Resource not found (404)."""
    pass


class FHIRValidationError(FHIRError):
    """Resource validation failed (400)."""
    pass


class FHIRPermissionError(FHIRError):
    """Permission denied (403)."""
    pass


class FHIRServerError(FHIRError):
    """Server error (5xx)."""
    pass


class FHIRConnectionError(FHIRError):
    """Connection error."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# COMMON LOINC CODES
# ═══════════════════════════════════════════════════════════════════════════════


class LOINCCodes:
    """Common LOINC codes for observations."""
    # Vital Signs
    BLOOD_PRESSURE_SYSTOLIC = "8480-6"
    BLOOD_PRESSURE_DIASTOLIC = "8462-4"
    BLOOD_PRESSURE_PANEL = "85354-9"
    HEART_RATE = "8867-4"
    RESPIRATORY_RATE = "9279-1"
    BODY_TEMPERATURE = "8310-5"
    OXYGEN_SATURATION = "2708-6"
    BODY_WEIGHT = "29463-7"
    BODY_HEIGHT = "8302-2"
    BMI = "39156-5"
    
    # Laboratory - Chemistry
    GLUCOSE = "2345-7"
    GLUCOSE_FASTING = "1558-6"
    HBA1C = "4548-4"
    CREATININE = "2160-0"
    BUN = "3094-0"
    EGFR = "33914-3"
    SODIUM = "2951-2"
    POTASSIUM = "2823-3"
    CHLORIDE = "2075-0"
    CO2 = "2028-9"
    CALCIUM = "17861-6"
    MAGNESIUM = "19123-9"
    PHOSPHORUS = "2777-1"
    
    # Laboratory - Liver
    ALT = "1742-6"
    AST = "1920-8"
    ALKALINE_PHOSPHATASE = "6768-6"
    BILIRUBIN_TOTAL = "1975-2"
    BILIRUBIN_DIRECT = "1968-7"
    ALBUMIN = "1751-7"
    TOTAL_PROTEIN = "2885-2"
    
    # Laboratory - Lipids
    TOTAL_CHOLESTEROL = "2093-3"
    LDL = "2089-1"
    HDL = "2085-9"
    TRIGLYCERIDES = "2571-8"
    
    # Laboratory - CBC
    WBC = "6690-2"
    RBC = "789-8"
    HEMOGLOBIN = "718-7"
    HEMATOCRIT = "4544-3"
    PLATELETS = "777-3"
    MCV = "787-2"
    MCH = "785-6"
    MCHC = "786-4"
    
    # Laboratory - Coagulation
    PT = "5902-2"
    INR = "6301-6"
    PTT = "3173-2"
    
    # Laboratory - Cardiac
    TROPONIN_I = "10839-9"
    TROPONIN_T = "6598-7"
    BNP = "30934-4"
    NT_PROBNP = "33762-6"
    
    # Laboratory - Thyroid
    TSH = "3016-3"
    FREE_T4 = "3024-7"
    FREE_T3 = "3051-0"
    
    # Laboratory - Other
    LACTATE = "2524-7"
    PROCALCITONIN = "75241-0"
    D_DIMER = "48065-7"
    CRP = "1988-5"
    ESR = "4537-7"
    FERRITIN = "2276-4"
    
    # Document Types
    PROGRESS_NOTE = "11506-3"
    DISCHARGE_SUMMARY = "18842-5"
    HISTORY_AND_PHYSICAL = "34117-2"
    CONSULTATION_NOTE = "11488-4"
    OPERATIVE_NOTE = "11504-8"


# ═══════════════════════════════════════════════════════════════════════════════
# FHIR CLIENT
# ═══════════════════════════════════════════════════════════════════════════════


class FHIRClient:
    """
    FHIR R4 client for reading/writing health records.
    
    Supports Epic, Cerner, and other FHIR-compliant EHR systems.
    
    Example:
        >>> config = FHIRConfig(
        ...     base_url="https://fhir.epic.com/api/FHIR/R4/",
        ...     client_id="my-client-id",
        ...     access_token="my-access-token"
        ... )
        >>> client = FHIRClient(config)
        >>> patient = client.get_patient("12345")
        >>> print(patient.name)
    """
    
    def __init__(self, config: FHIRConfig):
        """
        Initialize FHIR client.
        
        Args:
            config: FHIR server configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Ensure base URL ends with /
        if not self.config.base_url.endswith('/'):
            self.config.base_url += '/'
        
        # Create session with retry logic
        self.session = self._create_session()
        
        # Token expiry tracking
        self._token_expires_at: Optional[datetime] = None
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic and default headers."""
        session = requests.Session()
        
        # Configure retries
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json',
            'User-Agent': 'PhoenixGuardian-FHIR-Client/1.0'
        })
        
        # Add auth token if provided
        if self.config.access_token:
            session.headers.update({
                'Authorization': f'Bearer {self.config.access_token}'
            })
        
        return session
    
    def _update_access_token(self, token: str, expires_in: Optional[int] = None) -> None:
        """Update the access token in the session."""
        self.config.access_token = token
        self.session.headers.update({
            'Authorization': f'Bearer {token}'
        })
        
        if expires_in:
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # AUTHENTICATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def authenticate(self) -> bool:
        """
        Authenticate with FHIR server using OAuth 2.0 client credentials.
        
        Returns:
            True if authentication successful
            
        Raises:
            FHIRAuthenticationError: If authentication fails
        """
        if not self.config.token_url:
            self.logger.warning("No token URL configured, skipping authentication")
            return False
        
        try:
            auth_data = {
                'grant_type': 'client_credentials',
                'client_id': self.config.client_id,
            }
            
            if self.config.client_secret:
                auth_data['client_secret'] = self.config.client_secret
            
            response = requests.post(
                self.config.token_url,
                data=auth_data,
                timeout=self.config.timeout,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code != 200:
                error_detail = response.text
                raise FHIRAuthenticationError(
                    f"Authentication failed: {error_detail}",
                    status_code=response.status_code
                )
            
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            if not access_token:
                raise FHIRAuthenticationError("No access token in response")
            
            # Update session with new token
            self._update_access_token(
                access_token,
                token_data.get('expires_in')
            )
            
            # Store refresh token if provided
            if 'refresh_token' in token_data:
                self.config.refresh_token = token_data['refresh_token']
            
            self.logger.info("✅ FHIR authentication successful")
            return True
            
        except requests.exceptions.RequestException as e:
            raise FHIRConnectionError(f"Connection error during authentication: {e}")
        except FHIRError:
            raise
        except Exception as e:
            raise FHIRAuthenticationError(f"Authentication failed: {e}")
    
    def refresh_authentication(self) -> bool:
        """
        Refresh access token using refresh token.
        
        Returns:
            True if refresh successful
        """
        if not self.config.refresh_token or not self.config.token_url:
            return False
        
        try:
            response = requests.post(
                self.config.token_url,
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': self.config.refresh_token,
                    'client_id': self.config.client_id
                },
                timeout=self.config.timeout
            )
            
            if response.status_code != 200:
                return False
            
            token_data = response.json()
            self._update_access_token(
                token_data['access_token'],
                token_data.get('expires_in')
            )
            
            if 'refresh_token' in token_data:
                self.config.refresh_token = token_data['refresh_token']
            
            self.logger.info("✅ Token refresh successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Token refresh failed: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HTTP OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make HTTP request with error handling.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Request URL
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object
            
        Raises:
            FHIRError: On request failure
        """
        kwargs.setdefault('timeout', self.config.timeout)
        
        try:
            response = self.session.request(method, url, **kwargs)
            self._handle_response_error(response)
            return response
            
        except requests.exceptions.Timeout:
            raise FHIRConnectionError(f"Request timeout after {self.config.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise FHIRConnectionError(f"Connection error: {e}")
        except FHIRError:
            raise
        except Exception as e:
            raise FHIRError(f"Request failed: {e}")
    
    def _handle_response_error(self, response: requests.Response) -> None:
        """
        Handle HTTP response errors.
        
        Args:
            response: HTTP response
            
        Raises:
            FHIRError: On error response
        """
        if response.ok:
            return
        
        # Try to parse OperationOutcome
        operation_outcome = None
        error_message = response.text
        
        try:
            data = response.json()
            if data.get('resourceType') == 'OperationOutcome':
                operation_outcome = data
                issues = data.get('issue', [])
                if issues:
                    error_message = issues[0].get('diagnostics', 
                                   issues[0].get('details', {}).get('text', error_message))
        except (ValueError, KeyError):
            pass
        
        status_code = response.status_code
        
        if status_code == 401:
            raise FHIRAuthenticationError(
                f"Authentication required: {error_message}",
                status_code=status_code,
                operation_outcome=operation_outcome
            )
        elif status_code == 403:
            raise FHIRPermissionError(
                f"Permission denied: {error_message}",
                status_code=status_code,
                operation_outcome=operation_outcome
            )
        elif status_code == 404:
            raise FHIRNotFoundError(
                f"Resource not found: {error_message}",
                status_code=status_code,
                operation_outcome=operation_outcome
            )
        elif status_code == 400 or status_code == 422:
            raise FHIRValidationError(
                f"Validation error: {error_message}",
                status_code=status_code,
                operation_outcome=operation_outcome
            )
        elif status_code >= 500:
            raise FHIRServerError(
                f"Server error: {error_message}",
                status_code=status_code,
                operation_outcome=operation_outcome
            )
        else:
            raise FHIRError(
                f"HTTP {status_code}: {error_message}",
                status_code=status_code,
                operation_outcome=operation_outcome
            )
    
    def _build_url(self, resource_type: str, resource_id: Optional[str] = None) -> str:
        """Build full URL for resource."""
        if resource_id:
            return urljoin(self.config.base_url, f"{resource_type}/{resource_id}")
        return urljoin(self.config.base_url, resource_type)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PATIENT OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_patient(self, patient_id: str) -> Optional[FHIRPatient]:
        """
        Retrieve patient by ID.
        
        Args:
            patient_id: FHIR Patient ID
            
        Returns:
            FHIRPatient object or None if not found
        """
        try:
            url = self._build_url("Patient", patient_id)
            response = self._make_request("GET", url)
            resource = response.json()
            return self._parse_patient(resource)
            
        except FHIRNotFoundError:
            self.logger.warning(f"Patient {patient_id} not found")
            return None
    
    def search_patients(self, **search_params) -> List[FHIRPatient]:
        """
        Search for patients.
        
        Args:
            **search_params: FHIR search parameters
                - name: Patient name
                - identifier: MRN or other identifier
                - birthdate: Birth date (YYYY-MM-DD)
                - gender: male, female, other, unknown
                - _count: Max results
                
        Returns:
            List of FHIRPatient objects
        """
        url = self._build_url("Patient")
        search_params.setdefault('_count', 100)
        
        response = self._make_request("GET", url, params=search_params)
        bundle = response.json()
        
        patients = []
        for entry in bundle.get('entry', []):
            resource = entry.get('resource', {})
            if resource.get('resourceType') == 'Patient':
                patients.append(self._parse_patient(resource))
        
        return patients
    
    def _parse_patient(self, resource: Dict[str, Any]) -> FHIRPatient:
        """Parse FHIR Patient resource into FHIRPatient dataclass."""
        # Extract name (prefer official name)
        name = "Unknown"
        if resource.get('name'):
            name_obj = None
            for n in resource['name']:
                if n.get('use') == 'official':
                    name_obj = n
                    break
            if not name_obj:
                name_obj = resource['name'][0]
            
            given = ' '.join(name_obj.get('given', []))
            family = name_obj.get('family', '')
            name = f"{given} {family}".strip()
        
        # Extract birth date
        birth_date_str = resource.get('birthDate', '1900-01-01')
        try:
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
        except ValueError:
            birth_date = date(1900, 1, 1)
        
        # Extract sex/gender
        sex = resource.get('gender', 'unknown')
        
        # Extract identifiers
        mrn = None
        ssn = None
        for identifier in resource.get('identifier', []):
            id_type = identifier.get('type', {})
            coding = id_type.get('coding', [{}])[0]
            code = coding.get('code', '')
            type_text = id_type.get('text', '').upper()
            
            if code == 'MR' or type_text == 'MRN' or 'MEDICAL RECORD' in type_text:
                mrn = identifier.get('value')
            elif code == 'SS' or type_text == 'SSN':
                ssn = identifier.get('value')
        
        # Extract address
        address = None
        city = None
        state = None
        postal_code = None
        if resource.get('address'):
            addr = resource['address'][0]
            lines = addr.get('line', [])
            address = ', '.join(lines) if lines else None
            city = addr.get('city')
            state = addr.get('state')
            postal_code = addr.get('postalCode')
        
        # Extract contact info
        phone = None
        email = None
        for telecom in resource.get('telecom', []):
            if telecom.get('system') == 'phone' and not phone:
                phone = telecom.get('value')
            elif telecom.get('system') == 'email' and not email:
                email = telecom.get('value')
        
        # Extract language
        language = None
        if resource.get('communication'):
            lang = resource['communication'][0].get('language', {})
            coding = lang.get('coding', [{}])[0]
            language = coding.get('display') or coding.get('code')
        
        # Extract marital status
        marital_status = None
        if resource.get('maritalStatus'):
            coding = resource['maritalStatus'].get('coding', [{}])[0]
            marital_status = coding.get('display') or coding.get('code')
        
        # Extract deceased status
        deceased = resource.get('deceasedBoolean', False)
        if not deceased and resource.get('deceasedDateTime'):
            deceased = True
        
        return FHIRPatient(
            id=resource['id'],
            name=name,
            birth_date=birth_date,
            sex=sex,
            mrn=mrn,
            ssn=ssn,
            address=address,
            city=city,
            state=state,
            postal_code=postal_code,
            phone=phone,
            email=email,
            language=language,
            marital_status=marital_status,
            deceased=deceased,
            active=resource.get('active', True),
            raw_resource=resource
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # OBSERVATION OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_observation(self, observation_id: str) -> Optional[FHIRObservation]:
        """
        Retrieve observation by ID.
        
        Args:
            observation_id: FHIR Observation ID
            
        Returns:
            FHIRObservation object or None if not found
        """
        try:
            url = self._build_url("Observation", observation_id)
            response = self._make_request("GET", url)
            resource = response.json()
            return self._parse_observation(resource)
            
        except FHIRNotFoundError:
            self.logger.warning(f"Observation {observation_id} not found")
            return None
    
    def get_observations(self, patient_id: str, 
                        code: Optional[str] = None,
                        category: Optional[Union[str, ObservationCategory]] = None,
                        date_from: Optional[date] = None,
                        date_to: Optional[date] = None,
                        limit: int = 100) -> List[FHIRObservation]:
        """
        Retrieve observations for patient.
        
        Args:
            patient_id: FHIR Patient ID
            code: LOINC code filter (e.g., "4548-4" for HbA1c)
            category: Category filter (e.g., "vital-signs", "laboratory")
            date_from: Start date filter
            date_to: End date filter
            limit: Maximum number of results
            
        Returns:
            List of FHIRObservation objects
        """
        url = self._build_url("Observation")
        params = {
            'patient': patient_id,
            '_count': limit,
            '_sort': '-date'  # Most recent first
        }
        
        if code:
            params['code'] = code
        if category:
            if isinstance(category, ObservationCategory):
                params['category'] = category.value
            else:
                params['category'] = category
        if date_from:
            params['date'] = f'ge{date_from.isoformat()}'
        if date_to:
            if 'date' in params:
                # FHIR allows multiple date params
                params['date'] = [params['date'], f'le{date_to.isoformat()}']
            else:
                params['date'] = f'le{date_to.isoformat()}'
        
        response = self._make_request("GET", url, params=params)
        bundle = response.json()
        
        observations = []
        for entry in bundle.get('entry', []):
            resource = entry.get('resource', {})
            if resource.get('resourceType') == 'Observation':
                observations.append(self._parse_observation(resource))
        
        return observations
    
    def get_vital_signs(self, patient_id: str, limit: int = 50) -> List[FHIRObservation]:
        """Get vital signs for patient."""
        return self.get_observations(
            patient_id, 
            category=ObservationCategory.VITAL_SIGNS,
            limit=limit
        )
    
    def get_lab_results(self, patient_id: str, limit: int = 100) -> List[FHIRObservation]:
        """Get laboratory results for patient."""
        return self.get_observations(
            patient_id,
            category=ObservationCategory.LABORATORY,
            limit=limit
        )
    
    def _parse_observation(self, resource: Dict[str, Any]) -> FHIRObservation:
        """Parse FHIR Observation resource into FHIRObservation dataclass."""
        # Extract code
        code = ""
        code_system = "http://loinc.org"
        display = ""
        if resource.get('code'):
            coding = resource['code'].get('coding', [{}])[0]
            code = coding.get('code', '')
            code_system = coding.get('system', code_system)
            display = coding.get('display', resource['code'].get('text', ''))
        
        # Extract category
        category = None
        if resource.get('category'):
            cat_coding = resource['category'][0].get('coding', [{}])[0]
            cat_code = cat_coding.get('code', '')
            try:
                category = ObservationCategory(cat_code)
            except ValueError:
                pass
        
        # Extract value
        value = None
        unit = None
        value_string = None
        value_code = None
        component_systolic = None
        component_diastolic = None
        
        if 'valueQuantity' in resource:
            value = resource['valueQuantity'].get('value')
            unit = resource['valueQuantity'].get('unit')
        elif 'valueString' in resource:
            value_string = resource['valueString']
        elif 'valueCodeableConcept' in resource:
            coding = resource['valueCodeableConcept'].get('coding', [{}])[0]
            value_code = coding.get('code')
            value_string = coding.get('display', resource['valueCodeableConcept'].get('text'))
        elif 'valueBoolean' in resource:
            value_string = str(resource['valueBoolean'])
        elif 'valueInteger' in resource:
            value = float(resource['valueInteger'])
        
        # Handle component observations (e.g., blood pressure)
        for component in resource.get('component', []):
            comp_code = component.get('code', {}).get('coding', [{}])[0].get('code', '')
            if comp_code == LOINCCodes.BLOOD_PRESSURE_SYSTOLIC:
                component_systolic = component.get('valueQuantity', {}).get('value')
            elif comp_code == LOINCCodes.BLOOD_PRESSURE_DIASTOLIC:
                component_diastolic = component.get('valueQuantity', {}).get('value')
        
        # Extract dates
        effective_date = None
        if 'effectiveDateTime' in resource:
            try:
                effective_date = datetime.fromisoformat(
                    resource['effectiveDateTime'].replace('Z', '+00:00')
                )
            except ValueError:
                pass
        
        issued_date = None
        if 'issued' in resource:
            try:
                issued_date = datetime.fromisoformat(
                    resource['issued'].replace('Z', '+00:00')
                )
            except ValueError:
                pass
        
        # Extract status
        status_str = resource.get('status', 'final')
        try:
            status = ObservationStatus(status_str)
        except ValueError:
            status = ObservationStatus.FINAL
        
        # Extract patient reference
        patient_ref = resource.get('subject', {}).get('reference', '')
        patient_id = patient_ref.split('/')[-1] if patient_ref else ''
        
        # Extract encounter reference
        encounter_ref = resource.get('encounter', {}).get('reference', '')
        encounter_id = encounter_ref.split('/')[-1] if encounter_ref else None
        
        # Extract performer
        performer_id = None
        performer_name = None
        if resource.get('performer'):
            perf = resource['performer'][0]
            performer_ref = perf.get('reference', '')
            performer_id = performer_ref.split('/')[-1] if performer_ref else None
            performer_name = perf.get('display')
        
        # Extract interpretation
        interpretation = None
        if resource.get('interpretation'):
            interp = resource['interpretation'][0]
            coding = interp.get('coding', [{}])[0]
            interpretation = coding.get('display') or coding.get('code')
        
        # Extract reference range
        reference_range_low = None
        reference_range_high = None
        if resource.get('referenceRange'):
            ref_range = resource['referenceRange'][0]
            if 'low' in ref_range:
                reference_range_low = ref_range['low'].get('value')
            if 'high' in ref_range:
                reference_range_high = ref_range['high'].get('value')
        
        # Extract note
        note = None
        if resource.get('note'):
            note = resource['note'][0].get('text')
        
        return FHIRObservation(
            id=resource.get('id'),
            patient_id=patient_id,
            encounter_id=encounter_id,
            code=code,
            code_system=code_system,
            display=display,
            category=category,
            value=value,
            unit=unit,
            value_string=value_string,
            value_code=value_code,
            component_systolic=component_systolic,
            component_diastolic=component_diastolic,
            status=status,
            effective_date=effective_date,
            issued_date=issued_date,
            performer_id=performer_id,
            performer_name=performer_name,
            interpretation=interpretation,
            reference_range_low=reference_range_low,
            reference_range_high=reference_range_high,
            note=note,
            raw_resource=resource
        )
    
    def create_observation(self, observation: FHIRObservation) -> str:
        """
        Create new observation.
        
        Args:
            observation: FHIRObservation object
            
        Returns:
            Created observation ID
            
        Raises:
            FHIRValidationError: If observation data is invalid
        """
        resource = self._build_observation_resource(observation)
        
        url = self._build_url("Observation")
        response = self._make_request("POST", url, json=resource)
        
        created = response.json()
        observation_id = created.get('id')
        
        self.logger.info(f"✅ Created observation {observation_id}")
        return observation_id
    
    def update_observation(self, observation: FHIRObservation) -> bool:
        """
        Update existing observation.
        
        Args:
            observation: FHIRObservation object with id set
            
        Returns:
            True if update successful
        """
        if not observation.id:
            raise FHIRValidationError("Observation ID required for update")
        
        resource = self._build_observation_resource(observation)
        resource['id'] = observation.id
        
        url = self._build_url("Observation", observation.id)
        self._make_request("PUT", url, json=resource)
        
        self.logger.info(f"✅ Updated observation {observation.id}")
        return True
    
    def _build_observation_resource(self, obs: FHIRObservation) -> Dict[str, Any]:
        """Build FHIR Observation resource from FHIRObservation dataclass."""
        resource: Dict[str, Any] = {
            'resourceType': 'Observation',
            'status': obs.status.value,
            'subject': {
                'reference': f'Patient/{obs.patient_id}'
            },
            'code': {
                'coding': [{
                    'system': obs.code_system,
                    'code': obs.code,
                    'display': obs.display
                }],
                'text': obs.display
            }
        }
        
        # Add category
        if obs.category:
            resource['category'] = [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/observation-category',
                    'code': obs.category.value,
                    'display': obs.category.value.replace('-', ' ').title()
                }]
            }]
        
        # Add encounter reference
        if obs.encounter_id:
            resource['encounter'] = {
                'reference': f'Encounter/{obs.encounter_id}'
            }
        
        # Add value
        if obs.component_systolic is not None and obs.component_diastolic is not None:
            # Blood pressure with components
            resource['component'] = [
                {
                    'code': {
                        'coding': [{
                            'system': 'http://loinc.org',
                            'code': LOINCCodes.BLOOD_PRESSURE_SYSTOLIC,
                            'display': 'Systolic blood pressure'
                        }]
                    },
                    'valueQuantity': {
                        'value': obs.component_systolic,
                        'unit': 'mmHg',
                        'system': 'http://unitsofmeasure.org',
                        'code': 'mm[Hg]'
                    }
                },
                {
                    'code': {
                        'coding': [{
                            'system': 'http://loinc.org',
                            'code': LOINCCodes.BLOOD_PRESSURE_DIASTOLIC,
                            'display': 'Diastolic blood pressure'
                        }]
                    },
                    'valueQuantity': {
                        'value': obs.component_diastolic,
                        'unit': 'mmHg',
                        'system': 'http://unitsofmeasure.org',
                        'code': 'mm[Hg]'
                    }
                }
            ]
        elif obs.value is not None:
            resource['valueQuantity'] = {
                'value': obs.value,
                'unit': obs.unit or '',
                'system': 'http://unitsofmeasure.org',
                'code': obs.unit or ''
            }
        elif obs.value_string:
            resource['valueString'] = obs.value_string
        elif obs.value_code:
            resource['valueCodeableConcept'] = {
                'coding': [{
                    'code': obs.value_code
                }],
                'text': obs.value_string or obs.value_code
            }
        
        # Add dates
        if obs.effective_date:
            resource['effectiveDateTime'] = obs.effective_date.isoformat()
        else:
            resource['effectiveDateTime'] = datetime.now().isoformat()
        
        if obs.issued_date:
            resource['issued'] = obs.issued_date.isoformat()
        
        # Add performer
        if obs.performer_id:
            resource['performer'] = [{
                'reference': f'Practitioner/{obs.performer_id}'
            }]
            if obs.performer_name:
                resource['performer'][0]['display'] = obs.performer_name
        
        # Add interpretation
        if obs.interpretation:
            resource['interpretation'] = [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation',
                    'code': obs.interpretation
                }]
            }]
        
        # Add reference range
        if obs.reference_range_low is not None or obs.reference_range_high is not None:
            ref_range: Dict[str, Any] = {}
            if obs.reference_range_low is not None:
                ref_range['low'] = {'value': obs.reference_range_low, 'unit': obs.unit or ''}
            if obs.reference_range_high is not None:
                ref_range['high'] = {'value': obs.reference_range_high, 'unit': obs.unit or ''}
            resource['referenceRange'] = [ref_range]
        
        # Add note
        if obs.note:
            resource['note'] = [{'text': obs.note}]
        
        return resource
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONDITION OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_condition(self, condition_id: str) -> Optional[FHIRCondition]:
        """Retrieve condition by ID."""
        try:
            url = self._build_url("Condition", condition_id)
            response = self._make_request("GET", url)
            resource = response.json()
            return self._parse_condition(resource)
        except FHIRNotFoundError:
            return None
    
    def get_conditions(self, patient_id: str,
                      clinical_status: Optional[Union[str, ConditionClinicalStatus]] = None,
                      category: Optional[str] = None,
                      limit: int = 100) -> List[FHIRCondition]:
        """
        Retrieve conditions (diagnoses) for patient.
        
        Args:
            patient_id: FHIR Patient ID
            clinical_status: Filter by status (e.g., "active", "resolved")
            category: Filter by category (e.g., "problem-list-item", "encounter-diagnosis")
            limit: Maximum number of results
            
        Returns:
            List of FHIRCondition objects
        """
        url = self._build_url("Condition")
        params = {
            'patient': patient_id,
            '_count': limit
        }
        
        if clinical_status:
            if isinstance(clinical_status, ConditionClinicalStatus):
                params['clinical-status'] = clinical_status.value
            else:
                params['clinical-status'] = clinical_status
        
        if category:
            params['category'] = category
        
        response = self._make_request("GET", url, params=params)
        bundle = response.json()
        
        conditions = []
        for entry in bundle.get('entry', []):
            resource = entry.get('resource', {})
            if resource.get('resourceType') == 'Condition':
                conditions.append(self._parse_condition(resource))
        
        return conditions
    
    def get_active_conditions(self, patient_id: str) -> List[FHIRCondition]:
        """Get active conditions (problem list) for patient."""
        return self.get_conditions(
            patient_id,
            clinical_status=ConditionClinicalStatus.ACTIVE
        )
    
    def _parse_condition(self, resource: Dict[str, Any]) -> FHIRCondition:
        """Parse FHIR Condition resource into FHIRCondition dataclass."""
        # Extract code
        code = ""
        code_system = "http://hl7.org/fhir/sid/icd-10-cm"
        display = ""
        if resource.get('code'):
            coding = resource['code'].get('coding', [{}])[0]
            code = coding.get('code', '')
            code_system = coding.get('system', code_system)
            display = coding.get('display', resource['code'].get('text', ''))
        
        # Extract category
        category = None
        if resource.get('category'):
            cat_coding = resource['category'][0].get('coding', [{}])[0]
            category = cat_coding.get('code')
        
        # Extract clinical status
        clinical_status = ConditionClinicalStatus.ACTIVE
        if resource.get('clinicalStatus'):
            status_coding = resource['clinicalStatus'].get('coding', [{}])[0]
            status_str = status_coding.get('code', 'active')
            try:
                clinical_status = ConditionClinicalStatus(status_str)
            except ValueError:
                pass
        
        # Extract verification status
        verification_status = ConditionVerificationStatus.CONFIRMED
        if resource.get('verificationStatus'):
            ver_coding = resource['verificationStatus'].get('coding', [{}])[0]
            ver_str = ver_coding.get('code', 'confirmed')
            try:
                verification_status = ConditionVerificationStatus(ver_str)
            except ValueError:
                pass
        
        # Extract severity
        severity = None
        if resource.get('severity'):
            sev_coding = resource['severity'].get('coding', [{}])[0]
            severity = sev_coding.get('display') or sev_coding.get('code')
        
        # Extract dates
        onset_date = None
        if 'onsetDateTime' in resource:
            try:
                onset_date = datetime.fromisoformat(
                    resource['onsetDateTime'].replace('Z', '+00:00')
                ).date()
            except ValueError:
                pass
        
        abatement_date = None
        if 'abatementDateTime' in resource:
            try:
                abatement_date = datetime.fromisoformat(
                    resource['abatementDateTime'].replace('Z', '+00:00')
                ).date()
            except ValueError:
                pass
        
        recorded_date = None
        if 'recordedDate' in resource:
            try:
                recorded_date = datetime.fromisoformat(
                    resource['recordedDate'].replace('Z', '+00:00')
                ).date()
            except ValueError:
                pass
        
        # Extract patient reference
        patient_ref = resource.get('subject', {}).get('reference', '')
        patient_id = patient_ref.split('/')[-1] if patient_ref else ''
        
        # Extract encounter reference
        encounter_ref = resource.get('encounter', {}).get('reference', '')
        encounter_id = encounter_ref.split('/')[-1] if encounter_ref else None
        
        # Extract recorder
        recorder_id = None
        recorder_name = None
        if resource.get('recorder'):
            recorder_ref = resource['recorder'].get('reference', '')
            recorder_id = recorder_ref.split('/')[-1] if recorder_ref else None
            recorder_name = resource['recorder'].get('display')
        
        # Extract note
        note = None
        if resource.get('note'):
            note = resource['note'][0].get('text')
        
        return FHIRCondition(
            id=resource.get('id'),
            patient_id=patient_id,
            encounter_id=encounter_id,
            code=code,
            code_system=code_system,
            display=display,
            category=category,
            clinical_status=clinical_status,
            verification_status=verification_status,
            severity=severity,
            onset_date=onset_date,
            abatement_date=abatement_date,
            recorded_date=recorded_date,
            recorder_id=recorder_id,
            recorder_name=recorder_name,
            note=note,
            raw_resource=resource
        )
    
    def create_condition(self, condition: FHIRCondition) -> str:
        """
        Create new condition.
        
        Args:
            condition: FHIRCondition object
            
        Returns:
            Created condition ID
        """
        resource = self._build_condition_resource(condition)
        
        url = self._build_url("Condition")
        response = self._make_request("POST", url, json=resource)
        
        created = response.json()
        condition_id = created.get('id')
        
        self.logger.info(f"✅ Created condition {condition_id}")
        return condition_id
    
    def _build_condition_resource(self, cond: FHIRCondition) -> Dict[str, Any]:
        """Build FHIR Condition resource from FHIRCondition dataclass."""
        resource: Dict[str, Any] = {
            'resourceType': 'Condition',
            'subject': {
                'reference': f'Patient/{cond.patient_id}'
            },
            'code': {
                'coding': [{
                    'system': cond.code_system,
                    'code': cond.code,
                    'display': cond.display
                }],
                'text': cond.display
            },
            'clinicalStatus': {
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/condition-clinical',
                    'code': cond.clinical_status.value
                }]
            },
            'verificationStatus': {
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/condition-ver-status',
                    'code': cond.verification_status.value
                }]
            }
        }
        
        if cond.category:
            resource['category'] = [{
                'coding': [{
                    'system': 'http://terminology.hl7.org/CodeSystem/condition-category',
                    'code': cond.category
                }]
            }]
        
        if cond.encounter_id:
            resource['encounter'] = {'reference': f'Encounter/{cond.encounter_id}'}
        
        if cond.severity:
            resource['severity'] = {
                'coding': [{
                    'system': 'http://snomed.info/sct',
                    'display': cond.severity
                }]
            }
        
        if cond.onset_date:
            resource['onsetDateTime'] = cond.onset_date.isoformat()
        
        if cond.abatement_date:
            resource['abatementDateTime'] = cond.abatement_date.isoformat()
        
        if cond.recorded_date:
            resource['recordedDate'] = cond.recorded_date.isoformat()
        else:
            resource['recordedDate'] = date.today().isoformat()
        
        if cond.recorder_id:
            resource['recorder'] = {'reference': f'Practitioner/{cond.recorder_id}'}
        
        if cond.note:
            resource['note'] = [{'text': cond.note}]
        
        return resource
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MEDICATION REQUEST OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_medication(self, medication_id: str) -> Optional[FHIRMedicationRequest]:
        """Retrieve medication request by ID."""
        try:
            url = self._build_url("MedicationRequest", medication_id)
            response = self._make_request("GET", url)
            resource = response.json()
            return self._parse_medication_request(resource)
        except FHIRNotFoundError:
            return None
    
    def get_medications(self, patient_id: str,
                       status: Optional[Union[str, MedicationRequestStatus]] = None,
                       limit: int = 100) -> List[FHIRMedicationRequest]:
        """
        Retrieve medication requests for patient.
        
        Args:
            patient_id: FHIR Patient ID
            status: Filter by status (e.g., "active", "stopped")
            limit: Maximum number of results
            
        Returns:
            List of FHIRMedicationRequest objects
        """
        url = self._build_url("MedicationRequest")
        params = {
            'patient': patient_id,
            '_count': limit
        }
        
        if status:
            if isinstance(status, MedicationRequestStatus):
                params['status'] = status.value
            else:
                params['status'] = status
        
        response = self._make_request("GET", url, params=params)
        bundle = response.json()
        
        medications = []
        for entry in bundle.get('entry', []):
            resource = entry.get('resource', {})
            if resource.get('resourceType') == 'MedicationRequest':
                medications.append(self._parse_medication_request(resource))
        
        return medications
    
    def get_active_medications(self, patient_id: str) -> List[FHIRMedicationRequest]:
        """Get active medications for patient."""
        return self.get_medications(
            patient_id,
            status=MedicationRequestStatus.ACTIVE
        )
    
    def _parse_medication_request(self, resource: Dict[str, Any]) -> FHIRMedicationRequest:
        """Parse FHIR MedicationRequest resource."""
        # Extract medication
        med_code = ""
        med_code_system = "http://www.nlm.nih.gov/research/umls/rxnorm"
        med_display = ""
        
        if 'medicationCodeableConcept' in resource:
            coding = resource['medicationCodeableConcept'].get('coding', [{}])[0]
            med_code = coding.get('code', '')
            med_code_system = coding.get('system', med_code_system)
            med_display = coding.get('display', 
                         resource['medicationCodeableConcept'].get('text', ''))
        elif 'medicationReference' in resource:
            med_display = resource['medicationReference'].get('display', '')
        
        # Extract dosage
        dosage_text = ""
        dosage_route = None
        dosage_frequency = None
        dosage_quantity = None
        dosage_unit = None
        
        if resource.get('dosageInstruction'):
            dosage = resource['dosageInstruction'][0]
            dosage_text = dosage.get('text', '')
            
            if dosage.get('route'):
                route_coding = dosage['route'].get('coding', [{}])[0]
                dosage_route = route_coding.get('display') or route_coding.get('code')
            
            if dosage.get('timing', {}).get('code'):
                timing_coding = dosage['timing']['code'].get('coding', [{}])[0]
                dosage_frequency = timing_coding.get('code')
            
            if dosage.get('doseAndRate'):
                dose = dosage['doseAndRate'][0].get('doseQuantity', {})
                dosage_quantity = dose.get('value')
                dosage_unit = dose.get('unit')
        
        # Extract status
        status_str = resource.get('status', 'active')
        try:
            status = MedicationRequestStatus(status_str)
        except ValueError:
            status = MedicationRequestStatus.ACTIVE
        
        # Extract patient reference
        patient_ref = resource.get('subject', {}).get('reference', '')
        patient_id = patient_ref.split('/')[-1] if patient_ref else ''
        
        # Extract encounter reference
        encounter_ref = resource.get('encounter', {}).get('reference', '')
        encounter_id = encounter_ref.split('/')[-1] if encounter_ref else None
        
        # Extract dates
        authored_date = None
        if 'authoredOn' in resource:
            try:
                authored_date = datetime.fromisoformat(
                    resource['authoredOn'].replace('Z', '+00:00')
                )
            except ValueError:
                pass
        
        # Extract requester
        requester_id = None
        requester_name = None
        if resource.get('requester'):
            req_ref = resource['requester'].get('reference', '')
            requester_id = req_ref.split('/')[-1] if req_ref else None
            requester_name = resource['requester'].get('display')
        
        # Extract reason
        reason_code = None
        reason_display = None
        if resource.get('reasonCode'):
            reason_coding = resource['reasonCode'][0].get('coding', [{}])[0]
            reason_code = reason_coding.get('code')
            reason_display = reason_coding.get('display')
        
        # Extract dispense info
        dispense_quantity = None
        refills_allowed = None
        if resource.get('dispenseRequest'):
            disp = resource['dispenseRequest']
            if disp.get('quantity'):
                dispense_quantity = int(disp['quantity'].get('value', 0))
            refills_allowed = disp.get('numberOfRepeatsAllowed')
        
        # Extract note
        note = None
        if resource.get('note'):
            note = resource['note'][0].get('text')
        
        return FHIRMedicationRequest(
            id=resource.get('id'),
            patient_id=patient_id,
            encounter_id=encounter_id,
            medication_code=med_code,
            medication_code_system=med_code_system,
            medication_display=med_display,
            dosage_text=dosage_text,
            dosage_route=dosage_route,
            dosage_frequency=dosage_frequency,
            dosage_quantity=dosage_quantity,
            dosage_unit=dosage_unit,
            status=status,
            intent=resource.get('intent', 'order'),
            priority=resource.get('priority'),
            authored_date=authored_date,
            requester_id=requester_id,
            requester_name=requester_name,
            reason_code=reason_code,
            reason_display=reason_display,
            note=note,
            dispense_quantity=dispense_quantity,
            refills_allowed=refills_allowed,
            raw_resource=resource
        )
    
    def create_medication_request(self, medication: FHIRMedicationRequest) -> str:
        """
        Create new medication request.
        
        Args:
            medication: FHIRMedicationRequest object
            
        Returns:
            Created medication request ID
        """
        resource = self._build_medication_request_resource(medication)
        
        url = self._build_url("MedicationRequest")
        response = self._make_request("POST", url, json=resource)
        
        created = response.json()
        med_id = created.get('id')
        
        self.logger.info(f"✅ Created medication request {med_id}")
        return med_id
    
    def _build_medication_request_resource(self, med: FHIRMedicationRequest) -> Dict[str, Any]:
        """Build FHIR MedicationRequest resource."""
        resource: Dict[str, Any] = {
            'resourceType': 'MedicationRequest',
            'status': med.status.value,
            'intent': med.intent,
            'subject': {
                'reference': f'Patient/{med.patient_id}'
            },
            'medicationCodeableConcept': {
                'coding': [{
                    'system': med.medication_code_system,
                    'code': med.medication_code,
                    'display': med.medication_display
                }],
                'text': med.medication_display
            }
        }
        
        if med.encounter_id:
            resource['encounter'] = {'reference': f'Encounter/{med.encounter_id}'}
        
        if med.priority:
            resource['priority'] = med.priority
        
        if med.dosage_text or med.dosage_quantity:
            dosage: Dict[str, Any] = {}
            if med.dosage_text:
                dosage['text'] = med.dosage_text
            if med.dosage_route:
                dosage['route'] = {
                    'coding': [{'display': med.dosage_route}]
                }
            if med.dosage_quantity:
                dosage['doseAndRate'] = [{
                    'doseQuantity': {
                        'value': med.dosage_quantity,
                        'unit': med.dosage_unit or ''
                    }
                }]
            resource['dosageInstruction'] = [dosage]
        
        if med.authored_date:
            resource['authoredOn'] = med.authored_date.isoformat()
        else:
            resource['authoredOn'] = datetime.now().isoformat()
        
        if med.requester_id:
            resource['requester'] = {'reference': f'Practitioner/{med.requester_id}'}
        
        if med.reason_code:
            resource['reasonCode'] = [{
                'coding': [{
                    'code': med.reason_code,
                    'display': med.reason_display
                }]
            }]
        
        if med.dispense_quantity or med.refills_allowed:
            disp: Dict[str, Any] = {}
            if med.dispense_quantity:
                disp['quantity'] = {'value': med.dispense_quantity}
            if med.refills_allowed is not None:
                disp['numberOfRepeatsAllowed'] = med.refills_allowed
            resource['dispenseRequest'] = disp
        
        if med.note:
            resource['note'] = [{'text': med.note}]
        
        return resource
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DOCUMENT REFERENCE OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_document_reference(self, document_id: str) -> Optional[FHIRDocumentReference]:
        """Retrieve document reference by ID."""
        try:
            url = self._build_url("DocumentReference", document_id)
            response = self._make_request("GET", url)
            resource = response.json()
            return self._parse_document_reference(resource)
        except FHIRNotFoundError:
            return None
    
    def get_document_references(self, patient_id: str,
                               type_code: Optional[str] = None,
                               limit: int = 50) -> List[FHIRDocumentReference]:
        """
        Retrieve document references for patient.
        
        Args:
            patient_id: FHIR Patient ID
            type_code: LOINC code for document type
            limit: Maximum number of results
            
        Returns:
            List of FHIRDocumentReference objects
        """
        url = self._build_url("DocumentReference")
        params = {
            'patient': patient_id,
            '_count': limit,
            '_sort': '-date'
        }
        
        if type_code:
            params['type'] = type_code
        
        response = self._make_request("GET", url, params=params)
        bundle = response.json()
        
        documents = []
        for entry in bundle.get('entry', []):
            resource = entry.get('resource', {})
            if resource.get('resourceType') == 'DocumentReference':
                documents.append(self._parse_document_reference(resource))
        
        return documents
    
    def _parse_document_reference(self, resource: Dict[str, Any]) -> FHIRDocumentReference:
        """Parse FHIR DocumentReference resource."""
        # Extract type
        type_code = ""
        type_display = ""
        if resource.get('type'):
            coding = resource['type'].get('coding', [{}])[0]
            type_code = coding.get('code', '')
            type_display = coding.get('display', resource['type'].get('text', ''))
        
        # Extract content
        content = ""
        content_type = "text/plain"
        if resource.get('content'):
            attachment = resource['content'][0].get('attachment', {})
            content_type = attachment.get('contentType', 'text/plain')
            if 'data' in attachment:
                content = attachment['data']  # Base64 encoded
            elif 'url' in attachment:
                content = attachment['url']
        
        # Extract status
        status_str = resource.get('status', 'current')
        try:
            status = DocumentReferenceStatus(status_str)
        except ValueError:
            status = DocumentReferenceStatus.CURRENT
        
        # Extract patient reference
        patient_ref = resource.get('subject', {}).get('reference', '')
        patient_id = patient_ref.split('/')[-1] if patient_ref else ''
        
        # Extract dates
        created_date = None
        if resource.get('date'):
            try:
                created_date = datetime.fromisoformat(
                    resource['date'].replace('Z', '+00:00')
                )
            except ValueError:
                pass
        
        # Extract author
        author_id = None
        author_name = None
        if resource.get('author'):
            author = resource['author'][0]
            author_ref = author.get('reference', '')
            author_id = author_ref.split('/')[-1] if author_ref else None
            author_name = author.get('display')
        
        return FHIRDocumentReference(
            id=resource.get('id'),
            patient_id=patient_id,
            document_type_code=type_code,
            document_type_display=type_display,
            content=content,
            content_type=content_type,
            status=status,
            doc_status=resource.get('docStatus'),
            created_date=created_date,
            author_id=author_id,
            author_name=author_name,
            description=resource.get('description'),
            raw_resource=resource
        )
    
    def create_document_reference(self, document: FHIRDocumentReference) -> str:
        """
        Create new document reference.
        
        Args:
            document: FHIRDocumentReference object
            
        Returns:
            Created document reference ID
        """
        resource = self._build_document_reference_resource(document)
        
        url = self._build_url("DocumentReference")
        response = self._make_request("POST", url, json=resource)
        
        created = response.json()
        doc_id = created.get('id')
        
        self.logger.info(f"✅ Created document reference {doc_id}")
        return doc_id
    
    def _build_document_reference_resource(self, doc: FHIRDocumentReference) -> Dict[str, Any]:
        """Build FHIR DocumentReference resource."""
        # Encode content if not already base64
        content_data = doc.content
        if doc.content_type != 'text/plain' and not self._is_base64(doc.content):
            content_data = base64.b64encode(doc.content.encode()).decode()
        
        resource: Dict[str, Any] = {
            'resourceType': 'DocumentReference',
            'status': doc.status.value,
            'subject': {
                'reference': f'Patient/{doc.patient_id}'
            },
            'type': {
                'coding': [{
                    'system': 'http://loinc.org',
                    'code': doc.document_type_code,
                    'display': doc.document_type_display
                }],
                'text': doc.document_type_display
            },
            'content': [{
                'attachment': {
                    'contentType': doc.content_type,
                    'data': content_data
                }
            }]
        }
        
        if doc.encounter_id:
            resource['context'] = {
                'encounter': [{'reference': f'Encounter/{doc.encounter_id}'}]
            }
        
        if doc.doc_status:
            resource['docStatus'] = doc.doc_status
        
        if doc.created_date:
            resource['date'] = doc.created_date.isoformat()
        else:
            resource['date'] = datetime.now().isoformat()
        
        if doc.author_id:
            resource['author'] = [{
                'reference': f'Practitioner/{doc.author_id}'
            }]
            if doc.author_name:
                resource['author'][0]['display'] = doc.author_name
        
        if doc.description:
            resource['description'] = doc.description
        
        if doc.custodian:
            resource['custodian'] = {'display': doc.custodian}
        
        return resource
    
    def _is_base64(self, s: str) -> bool:
        """Check if string is base64 encoded."""
        try:
            if len(s) % 4 != 0:
                return False
            base64.b64decode(s)
            return True
        except Exception:
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DIAGNOSTIC REPORT OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_diagnostic_report(self, report_id: str) -> Optional[FHIRDiagnosticReport]:
        """Retrieve diagnostic report by ID."""
        try:
            url = self._build_url("DiagnosticReport", report_id)
            response = self._make_request("GET", url)
            resource = response.json()
            return self._parse_diagnostic_report(resource)
        except FHIRNotFoundError:
            return None
    
    def get_diagnostic_reports(self, patient_id: str,
                              category: Optional[str] = None,
                              code: Optional[str] = None,
                              limit: int = 50) -> List[FHIRDiagnosticReport]:
        """
        Retrieve diagnostic reports for patient.
        
        Args:
            patient_id: FHIR Patient ID
            category: Filter by category (e.g., "LAB", "RAD")
            code: Filter by LOINC code
            limit: Maximum number of results
            
        Returns:
            List of FHIRDiagnosticReport objects
        """
        url = self._build_url("DiagnosticReport")
        params = {
            'patient': patient_id,
            '_count': limit,
            '_sort': '-date'
        }
        
        if category:
            params['category'] = category
        if code:
            params['code'] = code
        
        response = self._make_request("GET", url, params=params)
        bundle = response.json()
        
        reports = []
        for entry in bundle.get('entry', []):
            resource = entry.get('resource', {})
            if resource.get('resourceType') == 'DiagnosticReport':
                reports.append(self._parse_diagnostic_report(resource))
        
        return reports
    
    def _parse_diagnostic_report(self, resource: Dict[str, Any]) -> FHIRDiagnosticReport:
        """Parse FHIR DiagnosticReport resource."""
        # Extract code
        code = ""
        code_system = "http://loinc.org"
        display = ""
        if resource.get('code'):
            coding = resource['code'].get('coding', [{}])[0]
            code = coding.get('code', '')
            code_system = coding.get('system', code_system)
            display = coding.get('display', resource['code'].get('text', ''))
        
        # Extract category
        category = None
        if resource.get('category'):
            cat_coding = resource['category'][0].get('coding', [{}])[0]
            category = cat_coding.get('code')
        
        # Extract patient reference
        patient_ref = resource.get('subject', {}).get('reference', '')
        patient_id = patient_ref.split('/')[-1] if patient_ref else ''
        
        # Extract encounter reference
        encounter_ref = resource.get('encounter', {}).get('reference', '')
        encounter_id = encounter_ref.split('/')[-1] if encounter_ref else None
        
        # Extract dates
        effective_date = None
        if 'effectiveDateTime' in resource:
            try:
                effective_date = datetime.fromisoformat(
                    resource['effectiveDateTime'].replace('Z', '+00:00')
                )
            except ValueError:
                pass
        
        issued_date = None
        if 'issued' in resource:
            try:
                issued_date = datetime.fromisoformat(
                    resource['issued'].replace('Z', '+00:00')
                )
            except ValueError:
                pass
        
        # Extract performer
        performer_id = None
        performer_name = None
        if resource.get('performer'):
            perf = resource['performer'][0]
            perf_ref = perf.get('reference', '')
            performer_id = perf_ref.split('/')[-1] if perf_ref else None
            performer_name = perf.get('display')
        
        # Extract result references
        result_ids = []
        for result in resource.get('result', []):
            ref = result.get('reference', '')
            if ref:
                result_ids.append(ref.split('/')[-1])
        
        # Extract presented form (attachment)
        presented_form_content = None
        presented_form_content_type = None
        if resource.get('presentedForm'):
            attachment = resource['presentedForm'][0]
            presented_form_content_type = attachment.get('contentType')
            presented_form_content = attachment.get('data')
        
        return FHIRDiagnosticReport(
            id=resource.get('id'),
            patient_id=patient_id,
            encounter_id=encounter_id,
            code=code,
            code_system=code_system,
            display=display,
            category=category,
            status=resource.get('status', 'final'),
            conclusion=resource.get('conclusion'),
            effective_date=effective_date,
            issued_date=issued_date,
            performer_id=performer_id,
            performer_name=performer_name,
            result_ids=result_ids,
            presented_form_content=presented_form_content,
            presented_form_content_type=presented_form_content_type,
            raw_resource=resource
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BATCH OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_patient_summary(self, patient_id: str) -> Dict[str, Any]:
        """
        Get comprehensive patient summary including conditions, medications, and recent observations.
        
        Args:
            patient_id: FHIR Patient ID
            
        Returns:
            Dictionary with patient data, conditions, medications, and observations
        """
        patient = self.get_patient(patient_id)
        if not patient:
            raise FHIRNotFoundError(f"Patient {patient_id} not found")
        
        conditions = self.get_active_conditions(patient_id)
        medications = self.get_active_medications(patient_id)
        vital_signs = self.get_vital_signs(patient_id, limit=10)
        lab_results = self.get_lab_results(patient_id, limit=20)
        
        return {
            'patient': patient.to_dict(),
            'conditions': [c.to_dict() for c in conditions],
            'medications': [m.to_dict() for m in medications],
            'vital_signs': [v.to_dict() for v in vital_signs],
            'lab_results': [l.to_dict() for l in lab_results]
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_connection(self) -> bool:
        """
        Test connection to FHIR server.
        
        Returns:
            True if connection successful
        """
        try:
            url = urljoin(self.config.base_url, "metadata")
            response = self._make_request("GET", url)
            capability = response.json()
            
            if capability.get('resourceType') == 'CapabilityStatement':
                self.logger.info("✅ FHIR server connection successful")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"❌ FHIR server connection failed: {e}")
            return False
    
    def get_server_capabilities(self) -> Dict[str, Any]:
        """
        Get FHIR server capability statement.
        
        Returns:
            CapabilityStatement resource
        """
        url = urljoin(self.config.base_url, "metadata")
        response = self._make_request("GET", url)
        return response.json()
    
    def close(self) -> None:
        """Close the session."""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
