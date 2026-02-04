"""
Phoenix Guardian - Universal Adapter Tests.

Comprehensive tests for the Universal EHR Adapter and base classes.

Test Coverage:
- Data classes (PatientData, EncounterData, SOAPNote)
- EHRConnectorBase abstract interface
- UniversalEHRAdapter registration and routing
- FHIR parsing utilities
- Error handling
"""

import pytest
from datetime import datetime
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from phoenix_guardian.integrations.universal_adapter import (
    EHRType,
    PatientData,
    EncounterData,
    SOAPNote,
    ConnectorConfig,
    EHRConnectorBase,
    UniversalEHRAdapter,
    EHRConnectorError,
    EHRAuthenticationError,
    EHRConnectionError,
    EHRNotFoundError,
    EHRValidationError,
    parse_fhir_patient,
    parse_fhir_encounter,
    create_fhir_document_reference,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_config() -> ConnectorConfig:
    """Create sample connector config."""
    return ConnectorConfig(
        base_url="https://fhir.example.com/r4",
        client_id="test-client",
        client_secret="test-secret",
        token_url="https://auth.example.com/token",
    )


@pytest.fixture
def sample_patient_data() -> PatientData:
    """Create sample patient data."""
    return PatientData(
        patient_id="P12345",
        name="John Smith",
        dob="1980-05-15",
        mrn="MRN001",
        gender="male",
        address="123 Main St, City, ST 12345",
        phone="555-123-4567",
        email="john.smith@email.com",
    )


@pytest.fixture
def sample_encounter_data() -> EncounterData:
    """Create sample encounter data."""
    return EncounterData(
        encounter_id="E98765",
        patient_id="P12345",
        status="finished",
        encounter_type="ambulatory",
        start_time="2026-01-15T09:00:00Z",
        end_time="2026-01-15T09:30:00Z",
        reason="Annual checkup",
        diagnosis_codes=["Z00.00"],
    )


@pytest.fixture
def sample_soap_note() -> SOAPNote:
    """Create sample SOAP note."""
    return SOAPNote(
        encounter_id="E98765",
        subjective="Patient reports mild headache for 2 days.",
        objective="Vital signs stable. No focal deficits.",
        assessment="Tension headache.",
        plan="OTC analgesics as needed. Follow up if persists.",
        icd_codes=["G44.209"],
        cpt_codes=["99213"],
        author_id="DR001",
    )


@pytest.fixture
def fhir_patient_resource() -> dict:
    """Create sample FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": "P12345",
        "name": [
            {
                "use": "official",
                "family": "Smith",
                "given": ["John", "Michael"],
            }
        ],
        "birthDate": "1980-05-15",
        "gender": "male",
        "identifier": [
            {
                "system": "http://hospital.org/mrn",
                "value": "MRN001",
                "type": {"text": "MRN"},
            }
        ],
        "address": [
            {
                "use": "home",
                "line": ["123 Main St"],
                "city": "City",
                "state": "ST",
                "postalCode": "12345",
            }
        ],
        "telecom": [
            {"system": "phone", "value": "555-123-4567"},
            {"system": "email", "value": "john@email.com"},
        ],
    }


@pytest.fixture
def fhir_encounter_resource() -> dict:
    """Create sample FHIR Encounter resource."""
    return {
        "resourceType": "Encounter",
        "id": "E98765",
        "status": "finished",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory",
        },
        "type": [
            {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "308335008",
                        "display": "Patient encounter procedure",
                    }
                ]
            }
        ],
        "subject": {"reference": "Patient/P12345"},
        "period": {
            "start": "2026-01-15T09:00:00Z",
            "end": "2026-01-15T09:30:00Z",
        },
        "reasonCode": [
            {
                "coding": [{"display": "Annual checkup"}]
            }
        ],
    }


# =============================================================================
# Mock Connector for Testing
# =============================================================================


class MockConnector(EHRConnectorBase):
    """Mock connector for testing."""
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self._mock_patients = {}
        self._mock_encounters = {}
    
    @property
    def connector_name(self) -> str:
        return "mock"
    
    async def get_patient(self, patient_id: str) -> PatientData:
        if patient_id in self._mock_patients:
            return self._mock_patients[patient_id]
        raise EHRNotFoundError(f"Patient not found: {patient_id}", "mock")
    
    async def get_encounter(self, encounter_id: str) -> EncounterData:
        if encounter_id in self._mock_encounters:
            return self._mock_encounters[encounter_id]
        raise EHRNotFoundError(f"Encounter not found: {encounter_id}", "mock")
    
    async def write_soap_note(self, note: SOAPNote) -> bool:
        return True
    
    async def get_patient_history(
        self,
        patient_id: str,
        days: int = 90,
    ) -> List[EncounterData]:
        return [e for e in self._mock_encounters.values() if e.patient_id == patient_id]
    
    def add_patient(self, patient: PatientData) -> None:
        self._mock_patients[patient.patient_id] = patient
    
    def add_encounter(self, encounter: EncounterData) -> None:
        self._mock_encounters[encounter.encounter_id] = encounter


# =============================================================================
# Data Class Tests
# =============================================================================


class TestPatientData:
    """Tests for PatientData dataclass."""
    
    def test_create_patient_data(self, sample_patient_data: PatientData) -> None:
        """Test creating PatientData."""
        assert sample_patient_data.patient_id == "P12345"
        assert sample_patient_data.name == "John Smith"
        assert sample_patient_data.dob == "1980-05-15"
        assert sample_patient_data.mrn == "MRN001"
    
    def test_patient_data_to_dict(self, sample_patient_data: PatientData) -> None:
        """Test PatientData serialization."""
        d = sample_patient_data.to_dict()
        
        assert d["patient_id"] == "P12345"
        assert d["name"] == "John Smith"
        assert "email" in d
    
    def test_patient_data_optional_fields(self) -> None:
        """Test PatientData with optional fields."""
        patient = PatientData(patient_id="P001")
        
        assert patient.patient_id == "P001"
        assert patient.name is None
        assert patient.dob is None


class TestEncounterData:
    """Tests for EncounterData dataclass."""
    
    def test_create_encounter_data(self, sample_encounter_data: EncounterData) -> None:
        """Test creating EncounterData."""
        assert sample_encounter_data.encounter_id == "E98765"
        assert sample_encounter_data.patient_id == "P12345"
        assert sample_encounter_data.status == "finished"
    
    def test_encounter_data_to_dict(self, sample_encounter_data: EncounterData) -> None:
        """Test EncounterData serialization."""
        d = sample_encounter_data.to_dict()
        
        assert d["encounter_id"] == "E98765"
        assert d["status"] == "finished"
        assert "diagnosis_codes" in d


class TestSOAPNote:
    """Tests for SOAPNote dataclass."""
    
    def test_create_soap_note(self, sample_soap_note: SOAPNote) -> None:
        """Test creating SOAPNote."""
        assert sample_soap_note.encounter_id == "E98765"
        assert "headache" in sample_soap_note.subjective
        assert sample_soap_note.icd_codes == ["G44.209"]
    
    def test_soap_note_to_dict(self, sample_soap_note: SOAPNote) -> None:
        """Test SOAPNote serialization."""
        d = sample_soap_note.to_dict()
        
        assert d["encounter_id"] == "E98765"
        assert d["subjective"] is not None
        assert "icd_codes" in d
    
    def test_soap_note_to_text(self, sample_soap_note: SOAPNote) -> None:
        """Test SOAPNote text format."""
        text = sample_soap_note.to_text()
        
        assert "SUBJECTIVE:" in text
        assert "OBJECTIVE:" in text
        assert "ASSESSMENT:" in text
        assert "PLAN:" in text
        assert "ICD-10:" in text
        assert "CPT:" in text


# =============================================================================
# FHIR Parsing Tests
# =============================================================================


class TestFHIRParsing:
    """Tests for FHIR parsing utilities."""
    
    def test_parse_fhir_patient(self, fhir_patient_resource: dict) -> None:
        """Test parsing FHIR Patient resource."""
        patient = parse_fhir_patient(fhir_patient_resource)
        
        assert patient.patient_id == "P12345"
        assert patient.name == "John Michael Smith"
        assert patient.dob == "1980-05-15"
        assert patient.gender == "male"
        assert patient.mrn == "MRN001"
        assert patient.phone == "555-123-4567"
        assert patient.email == "john@email.com"
    
    def test_parse_fhir_patient_minimal(self) -> None:
        """Test parsing minimal FHIR Patient resource."""
        minimal = {
            "resourceType": "Patient",
            "id": "P001",
        }
        patient = parse_fhir_patient(minimal)
        
        assert patient.patient_id == "P001"
        assert patient.name is None
    
    def test_parse_fhir_encounter(self, fhir_encounter_resource: dict) -> None:
        """Test parsing FHIR Encounter resource."""
        encounter = parse_fhir_encounter(fhir_encounter_resource)
        
        assert encounter.encounter_id == "E98765"
        assert encounter.patient_id == "P12345"
        assert encounter.status == "finished"
        assert encounter.start_time == "2026-01-15T09:00:00Z"
    
    def test_parse_fhir_encounter_minimal(self) -> None:
        """Test parsing minimal FHIR Encounter resource."""
        minimal = {
            "resourceType": "Encounter",
            "id": "E001",
            "status": "in-progress",
        }
        encounter = parse_fhir_encounter(minimal)
        
        assert encounter.encounter_id == "E001"
        assert encounter.status == "in-progress"


class TestDocumentReferenceCreation:
    """Tests for FHIR DocumentReference creation."""
    
    def test_create_document_reference(self, sample_soap_note: SOAPNote) -> None:
        """Test creating FHIR DocumentReference from SOAP note."""
        doc_ref = create_fhir_document_reference(
            note=sample_soap_note,
            patient_id="P12345",
            author_id="DR001",
        )
        
        assert doc_ref["resourceType"] == "DocumentReference"
        assert doc_ref["status"] == "current"
        assert doc_ref["subject"]["reference"] == "Patient/P12345"
        assert doc_ref["author"][0]["reference"] == "Practitioner/DR001"
        assert len(doc_ref["content"]) == 1
    
    def test_document_reference_without_author(self, sample_soap_note: SOAPNote) -> None:
        """Test DocumentReference creation without author."""
        doc_ref = create_fhir_document_reference(
            note=sample_soap_note,
            patient_id="P12345",
        )
        
        assert "author" not in doc_ref


# =============================================================================
# Universal Adapter Tests
# =============================================================================


class TestUniversalEHRAdapter:
    """Tests for UniversalEHRAdapter."""
    
    def test_register_connector(self, sample_config: ConnectorConfig) -> None:
        """Test registering a connector."""
        adapter = UniversalEHRAdapter()
        connector = MockConnector(sample_config)
        
        adapter.register_connector("mock", connector)
        
        assert "mock" in adapter.list_connectors()
    
    def test_get_connector(self, sample_config: ConnectorConfig) -> None:
        """Test getting a registered connector."""
        adapter = UniversalEHRAdapter()
        connector = MockConnector(sample_config)
        adapter.register_connector("mock", connector)
        
        retrieved = adapter.get_connector("mock")
        
        assert retrieved is connector
    
    def test_get_connector_not_found(self) -> None:
        """Test getting unregistered connector raises error."""
        adapter = UniversalEHRAdapter()
        
        with pytest.raises(KeyError, match="No connector registered"):
            adapter.get_connector("nonexistent")
    
    def test_case_insensitive_lookup(self, sample_config: ConnectorConfig) -> None:
        """Test connector lookup is case-insensitive."""
        adapter = UniversalEHRAdapter()
        connector = MockConnector(sample_config)
        adapter.register_connector("MOCK", connector)
        
        retrieved = adapter.get_connector("mock")
        assert retrieved is connector
    
    @pytest.mark.asyncio
    async def test_get_patient(
        self,
        sample_config: ConnectorConfig,
        sample_patient_data: PatientData,
    ) -> None:
        """Test getting patient through adapter."""
        adapter = UniversalEHRAdapter()
        connector = MockConnector(sample_config)
        connector.add_patient(sample_patient_data)
        adapter.register_connector("mock", connector)
        
        patient = await adapter.get_patient("mock", "P12345")
        
        assert patient.patient_id == "P12345"
        assert patient.name == "John Smith"
    
    @pytest.mark.asyncio
    async def test_get_encounter(
        self,
        sample_config: ConnectorConfig,
        sample_encounter_data: EncounterData,
    ) -> None:
        """Test getting encounter through adapter."""
        adapter = UniversalEHRAdapter()
        connector = MockConnector(sample_config)
        connector.add_encounter(sample_encounter_data)
        adapter.register_connector("mock", connector)
        
        encounter = await adapter.get_encounter("mock", "E98765")
        
        assert encounter.encounter_id == "E98765"
    
    @pytest.mark.asyncio
    async def test_write_soap_note(
        self,
        sample_config: ConnectorConfig,
        sample_soap_note: SOAPNote,
    ) -> None:
        """Test writing SOAP note through adapter."""
        adapter = UniversalEHRAdapter()
        connector = MockConnector(sample_config)
        adapter.register_connector("mock", connector)
        
        result = await adapter.write_soap_note("mock", sample_soap_note)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_patient_history(
        self,
        sample_config: ConnectorConfig,
        sample_encounter_data: EncounterData,
    ) -> None:
        """Test getting patient history through adapter."""
        adapter = UniversalEHRAdapter()
        connector = MockConnector(sample_config)
        connector.add_encounter(sample_encounter_data)
        adapter.register_connector("mock", connector)
        
        history = await adapter.get_patient_history("mock", "P12345", days=30)
        
        assert len(history) == 1
        assert history[0].encounter_id == "E98765"
    
    @pytest.mark.asyncio
    async def test_close_all(self, sample_config: ConnectorConfig) -> None:
        """Test closing all connectors."""
        adapter = UniversalEHRAdapter()
        connector = MockConnector(sample_config)
        connector.close = AsyncMock()
        adapter.register_connector("mock", connector)
        
        await adapter.close_all()
        
        connector.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_manager(self, sample_config: ConnectorConfig) -> None:
        """Test adapter as async context manager."""
        connector = MockConnector(sample_config)
        connector.close = AsyncMock()
        
        async with UniversalEHRAdapter() as adapter:
            adapter.register_connector("mock", connector)
        
        connector.close.assert_called_once()


# =============================================================================
# Exception Tests
# =============================================================================


class TestExceptions:
    """Tests for EHR connector exceptions."""
    
    def test_base_error(self) -> None:
        """Test base EHRConnectorError."""
        error = EHRConnectorError(
            "Test error",
            connector_name="test",
            details={"code": 500},
        )
        
        assert str(error) == "Test error"
        assert error.connector_name == "test"
        assert error.details["code"] == 500
    
    def test_authentication_error(self) -> None:
        """Test EHRAuthenticationError."""
        error = EHRAuthenticationError(
            "Auth failed",
            connector_name="test",
        )
        
        assert isinstance(error, EHRConnectorError)
    
    def test_not_found_error(self) -> None:
        """Test EHRNotFoundError."""
        error = EHRNotFoundError(
            "Resource not found",
            connector_name="test",
        )
        
        assert isinstance(error, EHRConnectorError)


# =============================================================================
# EHR Type Enum Tests
# =============================================================================


class TestEHRType:
    """Tests for EHRType enum."""
    
    def test_ehr_types(self) -> None:
        """Test all EHR types are defined."""
        assert EHRType.EPIC.value == "epic"
        assert EHRType.CERNER.value == "cerner"
        assert EHRType.ALLSCRIPTS.value == "allscripts"
        assert EHRType.MEDITECH.value == "meditech"
        assert EHRType.ATHENAHEALTH.value == "athenahealth"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
