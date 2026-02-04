"""
Phoenix Guardian - athenahealth Connector Tests.

Comprehensive tests for the athenahealth EHR connector with mocked HTTP.

Test Coverage:
- Authentication (OAuth 2.0)
- Patient retrieval (FHIR and proprietary)
- Encounter retrieval
- Patient history
- Appointments (proprietary API)
- SOAP note writing
- Practice ID requirement
- Error handling
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from phoenix_guardian.integrations.athenahealth_connector import (
    AthenaConnector,
    AthenaConfig,
    AthenaAppointment,
    create_athena_connector,
    ATHENA_SANDBOX_BASE_URL,
    ATHENA_PRODUCTION_BASE_URL,
)
from phoenix_guardian.integrations.universal_adapter import (
    PatientData,
    EncounterData,
    SOAPNote,
    EHRAuthenticationError,
    EHRConnectionError,
    EHRNotFoundError,
    EHRValidationError,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def athena_config() -> AthenaConfig:
    """Create athenahealth config for testing."""
    return AthenaConfig(
        base_url="https://api.preview.platform.athenahealth.com/fhir/r4",
        client_id="test-client",
        client_secret="test-secret",
        practice_id="195900",
        use_sandbox=True,
        department_id="1",
    )


@pytest.fixture
def mock_token_response() -> dict:
    """Mock OAuth token response."""
    return {
        "access_token": "athena-token-12345",
        "token_type": "Bearer",
        "expires_in": 3600,
    }


@pytest.fixture
def mock_patient_resource() -> dict:
    """Mock FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": "A12345",
        "name": [{"family": "Williams", "given": ["Robert"]}],
        "birthDate": "1965-03-10",
        "gender": "male",
        "identifier": [
            {"system": "http://athenahealth.com/mrn", "value": "ATH001"}
        ],
    }


@pytest.fixture
def mock_encounter_resource() -> dict:
    """Mock FHIR Encounter resource."""
    return {
        "resourceType": "Encounter",
        "id": "AE55555",
        "status": "finished",
        "class": {"code": "AMB", "display": "ambulatory"},
        "subject": {"reference": "Patient/A12345"},
        "period": {
            "start": "2026-02-01T10:00:00Z",
            "end": "2026-02-01T10:30:00Z",
        },
    }


@pytest.fixture
def mock_appointments_response() -> dict:
    """Mock appointments response from proprietary API."""
    return {
        "appointments": [
            {
                "appointmentid": 12345,
                "patientid": 67890,
                "departmentid": 1,
                "providerid": 111,
                "appointmenttype": "Office Visit",
                "date": "02/01/2026",
                "starttime": "10:00",
                "appointmentstatus": "4",
                "duration": 30,
            },
            {
                "appointmentid": 12346,
                "patientid": 67891,
                "departmentid": 1,
                "providerid": 111,
                "appointmenttype": "Follow-up",
                "date": "02/01/2026",
                "starttime": "10:30",
                "appointmentstatus": "4",
                "duration": 15,
            },
        ]
    }


@pytest.fixture
def sample_soap_note() -> SOAPNote:
    """Create sample SOAP note."""
    return SOAPNote(
        encounter_id="AE55555",
        subjective="Patient presents for diabetes management.",
        objective="HbA1c 7.2%, BP 128/82.",
        assessment="Type 2 diabetes, well controlled.",
        plan="Continue current medications. Recheck in 3 months.",
        icd_codes=["E11.9"],
        cpt_codes=["99214"],
        author_id="DR001",
    )


# =============================================================================
# Configuration Tests
# =============================================================================


class TestAthenaConfig:
    """Tests for AthenaConfig."""
    
    def test_sandbox_config(self) -> None:
        """Test sandbox configuration."""
        config = AthenaConfig(
            base_url="",
            client_id="client",
            client_secret="secret",
            practice_id="195900",
            use_sandbox=True,
        )
        
        assert ATHENA_SANDBOX_BASE_URL in config.base_url
    
    def test_production_config(self) -> None:
        """Test production configuration."""
        config = AthenaConfig(
            base_url="",
            client_id="client",
            client_secret="secret",
            practice_id="195900",
            use_sandbox=False,
        )
        
        assert ATHENA_PRODUCTION_BASE_URL in config.base_url
    
    def test_practice_id_required(self) -> None:
        """Test that practice_id is required."""
        config = AthenaConfig(
            base_url="https://test.athena.com/fhir/r4",
            client_id="client",
            client_secret="secret",
            practice_id="",
        )
        
        with pytest.raises(EHRValidationError):
            config.validate()
    
    def test_department_id_optional(self) -> None:
        """Test department_id is optional."""
        config = AthenaConfig(
            base_url="https://test.athena.com/fhir/r4",
            client_id="client",
            client_secret="secret",
            practice_id="195900",
        )
        
        assert config.department_id is None


# =============================================================================
# AthenaAppointment Tests
# =============================================================================


class TestAthenaAppointment:
    """Tests for AthenaAppointment dataclass."""
    
    def test_create_appointment(self) -> None:
        """Test creating appointment."""
        appt = AthenaAppointment(
            appointment_id="12345",
            patient_id="67890",
            department_id="1",
            provider_id="111",
            appointment_type="Office Visit",
            appointment_date="02/01/2026",
            appointment_time="10:00",
            status="4",
            duration_minutes=30,
            reason="Annual checkup",
        )
        
        assert appt.appointment_id == "12345"
        assert appt.duration_minutes == 30
    
    def test_appointment_to_dict(self) -> None:
        """Test appointment serialization."""
        appt = AthenaAppointment(
            appointment_id="12345",
            patient_id="67890",
            department_id="1",
            provider_id="111",
            appointment_type="Office Visit",
            appointment_date="02/01/2026",
            appointment_time="10:00",
            status="4",
        )
        
        d = appt.to_dict()
        assert d["appointment_id"] == "12345"
        assert "reason" in d


# =============================================================================
# Connector Initialization Tests
# =============================================================================


class TestAthenaConnectorInit:
    """Tests for connector initialization."""
    
    def test_connector_name(self, athena_config: AthenaConfig) -> None:
        """Test connector name."""
        connector = AthenaConnector(athena_config)
        assert connector.connector_name == "athenahealth"
    
    def test_practice_id_property(self, athena_config: AthenaConfig) -> None:
        """Test practice_id property."""
        connector = AthenaConnector(athena_config)
        assert connector.practice_id == "195900"
    
    def test_missing_practice_id(self) -> None:
        """Test initialization without practice_id."""
        config = AthenaConfig(
            base_url="https://test.athena.com/fhir/r4",
            client_id="client",
            client_secret="secret",
            practice_id="",
        )
        
        with pytest.raises(EHRValidationError):
            AthenaConnector(config)


# =============================================================================
# Authentication Tests
# =============================================================================


class TestAthenaAuthentication:
    """Tests for athenahealth authentication."""
    
    @pytest.mark.asyncio
    async def test_authentication_success(
        self,
        athena_config: AthenaConfig,
        mock_token_response: dict,
    ) -> None:
        """Test successful authentication."""
        connector = AthenaConnector(athena_config)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_token_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            token = await connector._authenticate()
            
            assert token == "athena-token-12345"
    
    @pytest.mark.asyncio
    async def test_authentication_uses_basic_auth(
        self,
        athena_config: AthenaConfig,
        mock_token_response: dict,
    ) -> None:
        """Test that authentication uses Basic auth header."""
        connector = AthenaConnector(athena_config)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_token_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            await connector._authenticate()
            
            # Verify Basic auth was used
            call_args = mock_client.post.call_args
            headers = call_args.kwargs.get("headers", {})
            assert "Authorization" in headers
            assert headers["Authorization"].startswith("Basic ")
    
    @pytest.mark.asyncio
    async def test_authentication_failure(
        self,
        athena_config: AthenaConfig,
    ) -> None:
        """Test authentication failure."""
        connector = AthenaConnector(athena_config)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Invalid credentials"
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "401",
                    request=MagicMock(),
                    response=mock_response,
                )
            )
            mock_get_client.return_value = mock_client
            
            with pytest.raises(EHRAuthenticationError):
                await connector._authenticate()


# =============================================================================
# Patient Operations Tests
# =============================================================================


class TestAthenaPatientOperations:
    """Tests for patient operations."""
    
    @pytest.mark.asyncio
    async def test_get_patient_fhir(
        self,
        athena_config: AthenaConfig,
        mock_patient_resource: dict,
    ) -> None:
        """Test getting patient via FHIR."""
        connector = AthenaConnector(athena_config)
        
        with patch.object(connector, "_fhir_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_patient_resource
            
            patient = await connector.get_patient("A12345")
            
            assert patient.patient_id == "A12345"
            assert patient.name == "Robert Williams"
    
    @pytest.mark.asyncio
    async def test_get_patient_proprietary(
        self,
        athena_config: AthenaConfig,
    ) -> None:
        """Test getting patient via proprietary API."""
        connector = AthenaConnector(athena_config)
        
        mock_proprietary = {
            "patientid": 12345,
            "firstname": "Robert",
            "lastname": "Williams",
            "dob": "03/10/1965",
            "sex": "M",
            "email": "robert@email.com",
        }
        
        with patch.object(connector, "_proprietary_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_proprietary
            
            result = await connector.get_patient_proprietary("12345")
            
            assert result["patientid"] == 12345
            assert result["firstname"] == "Robert"
    
    @pytest.mark.asyncio
    async def test_search_patients(
        self,
        athena_config: AthenaConfig,
    ) -> None:
        """Test patient search."""
        connector = AthenaConnector(athena_config)
        
        mock_bundle = {
            "resourceType": "Bundle",
            "type": "searchset",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "A001",
                        "name": [{"family": "Smith", "given": ["John"]}],
                    }
                }
            ],
        }
        
        with patch.object(connector, "_fhir_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_bundle
            
            patients = await connector.search_patients(name="Smith")
            
            assert len(patients) == 1
    
    @pytest.mark.asyncio
    async def test_search_with_department_filter(
        self,
        athena_config: AthenaConfig,
    ) -> None:
        """Test patient search with department filter."""
        connector = AthenaConnector(athena_config)
        
        mock_bundle = {"resourceType": "Bundle", "type": "searchset", "entry": []}
        
        with patch.object(connector, "_fhir_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_bundle
            
            await connector.search_patients(name="Smith", department_id="1")
            
            # Verify department filter was included
            call_args = mock_request.call_args
            params = call_args.kwargs.get("params", {})
            assert "_tag" in params


# =============================================================================
# Encounter Operations Tests
# =============================================================================


class TestAthenaEncounterOperations:
    """Tests for encounter operations."""
    
    @pytest.mark.asyncio
    async def test_get_encounter(
        self,
        athena_config: AthenaConfig,
        mock_encounter_resource: dict,
    ) -> None:
        """Test getting encounter."""
        connector = AthenaConnector(athena_config)
        
        with patch.object(connector, "_fhir_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_encounter_resource
            
            encounter = await connector.get_encounter("AE55555")
            
            assert encounter.encounter_id == "AE55555"
            assert encounter.status == "finished"
    
    @pytest.mark.asyncio
    async def test_get_patient_history(
        self,
        athena_config: AthenaConfig,
    ) -> None:
        """Test getting patient history."""
        connector = AthenaConnector(athena_config)
        
        mock_bundle = {
            "resourceType": "Bundle",
            "type": "searchset",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Encounter",
                        "id": "E001",
                        "status": "finished",
                        "subject": {"reference": "Patient/A12345"},
                    }
                },
            ],
        }
        
        with patch.object(connector, "_fhir_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_bundle
            
            history = await connector.get_patient_history("A12345", days=30)
            
            assert len(history) == 1


# =============================================================================
# Appointment Operations Tests
# =============================================================================


class TestAthenaAppointments:
    """Tests for appointment operations (proprietary API)."""
    
    @pytest.mark.asyncio
    async def test_get_appointments(
        self,
        athena_config: AthenaConfig,
        mock_appointments_response: dict,
    ) -> None:
        """Test getting appointments."""
        connector = AthenaConnector(athena_config)
        
        with patch.object(connector, "_proprietary_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_appointments_response
            
            appointments = await connector.get_appointments(
                department_id="1",
                start_date="02/01/2026",
            )
            
            assert len(appointments) == 2
            assert appointments[0].appointment_type == "Office Visit"
            assert appointments[1].appointment_type == "Follow-up"
    
    @pytest.mark.asyncio
    async def test_get_appointments_with_filters(
        self,
        athena_config: AthenaConfig,
    ) -> None:
        """Test getting appointments with filters."""
        connector = AthenaConnector(athena_config)
        
        mock_response = {"appointments": []}
        
        with patch.object(connector, "_proprietary_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            await connector.get_appointments(
                department_id="1",
                start_date="02/01/2026",
                end_date="02/28/2026",
                provider_id="111",
            )
            
            # Verify params were passed
            call_args = mock_request.call_args
            params = call_args.kwargs.get("params", {})
            assert params["departmentid"] == "1"
            assert params["enddate"] == "02/28/2026"
            assert params["providerid"] == "111"


# =============================================================================
# SOAP Note Tests
# =============================================================================


class TestAthenaSOAPNotes:
    """Tests for SOAP note operations."""
    
    @pytest.mark.asyncio
    async def test_write_soap_note(
        self,
        athena_config: AthenaConfig,
        sample_soap_note: SOAPNote,
        mock_encounter_resource: dict,
    ) -> None:
        """Test writing SOAP note."""
        connector = AthenaConnector(athena_config)
        
        with patch.object(connector, "_fhir_request", new_callable=AsyncMock) as mock_fhir:
            with patch.object(connector, "_proprietary_request", new_callable=AsyncMock) as mock_prop:
                mock_fhir.return_value = mock_encounter_resource
                mock_prop.return_value = {"documentid": "DOC001"}
                
                result = await connector.write_soap_note(sample_soap_note)
                
                assert result is True
    
    @pytest.mark.asyncio
    async def test_write_soap_note_validation(
        self,
        athena_config: AthenaConfig,
    ) -> None:
        """Test SOAP note validation."""
        connector = AthenaConnector(athena_config)
        
        # No encounter ID
        note = SOAPNote(
            encounter_id="",
            subjective="Test",
            objective="Test",
            assessment="Test",
            plan="Test",
        )
        
        with pytest.raises(EHRValidationError):
            await connector.write_soap_note(note)
    
    @pytest.mark.asyncio
    async def test_get_clinical_documents(
        self,
        athena_config: AthenaConfig,
    ) -> None:
        """Test getting clinical documents."""
        connector = AthenaConnector(athena_config)
        
        mock_response = {
            "documents": [
                {"documentid": 1, "documentclass": "ENCOUNTERDOCUMENT"},
                {"documentid": 2, "documentclass": "PROGRESSNOTE"},
            ]
        }
        
        with patch.object(connector, "_proprietary_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            docs = await connector.get_clinical_documents(
                patient_id="12345",
                department_id="1",
            )
            
            assert len(docs) == 2


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestAthenaErrorHandling:
    """Tests for error handling."""
    
    @pytest.mark.asyncio
    async def test_fhir_not_found(
        self,
        athena_config: AthenaConfig,
    ) -> None:
        """Test FHIR 404 error handling."""
        connector = AthenaConnector(athena_config)
        connector._access_token = "test-token"
        connector._token_expires_at = datetime.now() + timedelta(hours=1)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            with pytest.raises(EHRNotFoundError):
                await connector._fhir_request("GET", "Patient/NONEXISTENT")
    
    @pytest.mark.asyncio
    async def test_proprietary_connection_error(
        self,
        athena_config: AthenaConfig,
    ) -> None:
        """Test proprietary API connection error."""
        connector = AthenaConnector(athena_config)
        connector._access_token = "test-token"
        connector._token_expires_at = datetime.now() + timedelta(hours=1)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(
                side_effect=httpx.RequestError("Connection refused")
            )
            mock_get_client.return_value = mock_client
            
            with pytest.raises(EHRConnectionError):
                await connector._proprietary_request("GET", "patients/12345")


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestAthenaFactory:
    """Tests for factory function."""
    
    def test_create_athena_connector_sandbox(self) -> None:
        """Test creating sandbox connector."""
        connector = create_athena_connector(
            practice_id="195900",
            client_id="client",
            client_secret="secret",
            use_sandbox=True,
        )
        
        assert isinstance(connector, AthenaConnector)
        assert connector.practice_id == "195900"
        assert "preview" in connector.config.base_url
    
    def test_create_athena_connector_production(self) -> None:
        """Test creating production connector."""
        connector = create_athena_connector(
            practice_id="195900",
            client_id="client",
            client_secret="secret",
            use_sandbox=False,
        )
        
        assert "preview" not in connector.config.base_url


# =============================================================================
# URL Construction Tests
# =============================================================================


class TestAthenaURLConstruction:
    """Tests for URL construction with practice_id."""
    
    @pytest.mark.asyncio
    async def test_fhir_url_includes_practice_id(
        self,
        athena_config: AthenaConfig,
    ) -> None:
        """Test FHIR URLs include practice_id."""
        connector = AthenaConnector(athena_config)
        connector._access_token = "test-token"
        connector._token_expires_at = datetime.now() + timedelta(hours=1)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"resourceType": "Patient", "id": "P001"}
            mock_response.raise_for_status = MagicMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            await connector._fhir_request("GET", "Patient/P001")
            
            # Verify practice_id in URL
            call_args = mock_client.request.call_args
            url = call_args.kwargs.get("url", "")
            assert "195900" in url


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestAthenaContextManager:
    """Tests for async context manager."""
    
    @pytest.mark.asyncio
    async def test_context_manager(
        self,
        athena_config: AthenaConfig,
    ) -> None:
        """Test connector as async context manager."""
        async with AthenaConnector(athena_config) as connector:
            assert connector.connector_name == "athenahealth"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
