"""
Phoenix Guardian - Meditech Connector Tests.

Comprehensive tests for the Meditech EHR connector with mocked HTTP.

Test Coverage:
- Authentication (OAuth 2.0)
- Patient retrieval (single and batch)
- Encounter retrieval (single and batch)
- Patient history
- SOAP note writing (single and batch)
- Batch processing
- Error handling
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from phoenix_guardian.integrations.meditech_connector import (
    MeditechConnector,
    MeditechConfig,
    BatchResult,
    create_meditech_connector,
    MEDITECH_BATCH_SIZE,
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
def meditech_config() -> MeditechConfig:
    """Create Meditech config for testing."""
    return MeditechConfig(
        base_url="https://fhir.meditech.test/api/fhir/r4",
        client_id="test-client",
        client_secret="test-secret",
        token_url="https://fhir.meditech.test/auth/oauth2/token",
        facility_id="FAC001",
    )


@pytest.fixture
def mock_token_response() -> dict:
    """Mock OAuth token response."""
    return {
        "access_token": "meditech-token-12345",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "system/Patient.read",
    }


@pytest.fixture
def mock_patient_resource() -> dict:
    """Mock FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": "P12345",
        "name": [{"family": "Johnson", "given": ["Mary"]}],
        "birthDate": "1975-08-20",
        "gender": "female",
        "identifier": [
            {"system": "http://meditech.com/mrn", "value": "MRN002"}
        ],
    }


@pytest.fixture
def mock_encounter_resource() -> dict:
    """Mock FHIR Encounter resource."""
    return {
        "resourceType": "Encounter",
        "id": "E11111",
        "status": "in-progress",
        "class": {"code": "IMP", "display": "inpatient"},
        "subject": {"reference": "Patient/P12345"},
        "period": {
            "start": "2026-01-20T08:00:00Z",
        },
    }


@pytest.fixture
def sample_soap_note() -> SOAPNote:
    """Create sample SOAP note."""
    return SOAPNote(
        encounter_id="E11111",
        subjective="Patient complains of chest pain.",
        objective="BP 140/90, HR 88.",
        assessment="Hypertension.",
        plan="Start antihypertensive medication.",
        icd_codes=["I10"],
        cpt_codes=["99223"],
    )


# =============================================================================
# Configuration Tests
# =============================================================================


class TestMeditechConfig:
    """Tests for MeditechConfig."""
    
    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = MeditechConfig(
            base_url="https://test.meditech.com/fhir/r4",
            client_id="client",
            client_secret="secret",
        )
        
        assert config.batch_size == MEDITECH_BATCH_SIZE
        assert len(config.scopes) > 0
    
    def test_custom_batch_size(self) -> None:
        """Test custom batch size."""
        config = MeditechConfig(
            base_url="https://test.meditech.com/fhir/r4",
            client_id="client",
            client_secret="secret",
            batch_size=10,
        )
        
        assert config.batch_size == 10
    
    def test_facility_id(self) -> None:
        """Test facility ID configuration."""
        config = MeditechConfig(
            base_url="https://test.meditech.com/fhir/r4",
            client_id="client",
            client_secret="secret",
            facility_id="FAC123",
        )
        
        assert config.facility_id == "FAC123"


# =============================================================================
# BatchResult Tests
# =============================================================================


class TestBatchResult:
    """Tests for BatchResult dataclass."""
    
    def test_success_count(self) -> None:
        """Test success count calculation."""
        result = BatchResult(
            successful=["A", "B", "C"],
            failed=[("D", "error")],
        )
        
        assert result.success_count == 3
        assert result.failure_count == 1
        assert result.total_count == 4
    
    def test_empty_result(self) -> None:
        """Test empty result."""
        result = BatchResult(successful=[], failed=[])
        
        assert result.success_count == 0
        assert result.failure_count == 0
        assert result.total_count == 0


# =============================================================================
# Authentication Tests
# =============================================================================


class TestMeditechAuthentication:
    """Tests for Meditech authentication."""
    
    @pytest.mark.asyncio
    async def test_authentication_success(
        self,
        meditech_config: MeditechConfig,
        mock_token_response: dict,
    ) -> None:
        """Test successful authentication."""
        connector = MeditechConnector(meditech_config)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_token_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            token = await connector._authenticate()
            
            assert token == "meditech-token-12345"
    
    @pytest.mark.asyncio
    async def test_authentication_failure(
        self,
        meditech_config: MeditechConfig,
    ) -> None:
        """Test authentication failure."""
        connector = MeditechConnector(meditech_config)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.text = "Forbidden"
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "403",
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


class TestMeditechPatientOperations:
    """Tests for patient operations."""
    
    @pytest.mark.asyncio
    async def test_get_patient(
        self,
        meditech_config: MeditechConfig,
        mock_patient_resource: dict,
    ) -> None:
        """Test getting patient by ID."""
        connector = MeditechConnector(meditech_config)
        
        with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_patient_resource
            
            patient = await connector.get_patient("P12345")
            
            assert patient.patient_id == "P12345"
            assert patient.name == "Mary Johnson"
    
    @pytest.mark.asyncio
    async def test_get_patients_batch(
        self,
        meditech_config: MeditechConfig,
    ) -> None:
        """Test batch patient retrieval."""
        connector = MeditechConnector(meditech_config)
        
        mock_bundle_response = {
            "resourceType": "Bundle",
            "type": "batch-response",
            "entry": [
                {
                    "response": {"status": "200 OK"},
                    "resource": {
                        "resourceType": "Patient",
                        "id": "P001",
                        "name": [{"family": "Smith", "given": ["John"]}],
                    },
                },
                {
                    "response": {"status": "200 OK"},
                    "resource": {
                        "resourceType": "Patient",
                        "id": "P002",
                        "name": [{"family": "Jones", "given": ["Jane"]}],
                    },
                },
            ],
        }
        
        with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_bundle_response
            
            result = await connector.get_patients_batch(["P001", "P002"])
            
            assert result.success_count == 2
            assert result.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_search_patients(
        self,
        meditech_config: MeditechConfig,
    ) -> None:
        """Test patient search."""
        connector = MeditechConnector(meditech_config)
        
        mock_bundle = {
            "resourceType": "Bundle",
            "type": "searchset",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "P001",
                        "name": [{"family": "Smith", "given": ["John"]}],
                    }
                }
            ],
        }
        
        with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_bundle
            
            patients = await connector.search_patients(name="Smith")
            
            assert len(patients) == 1
    
    @pytest.mark.asyncio
    async def test_search_patients_no_params(
        self,
        meditech_config: MeditechConfig,
    ) -> None:
        """Test search without parameters raises error."""
        connector = MeditechConnector(meditech_config)
        
        with pytest.raises(EHRValidationError):
            await connector.search_patients()


# =============================================================================
# Encounter Operations Tests
# =============================================================================


class TestMeditechEncounterOperations:
    """Tests for encounter operations."""
    
    @pytest.mark.asyncio
    async def test_get_encounter(
        self,
        meditech_config: MeditechConfig,
        mock_encounter_resource: dict,
    ) -> None:
        """Test getting encounter by ID."""
        connector = MeditechConnector(meditech_config)
        
        with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_encounter_resource
            
            encounter = await connector.get_encounter("E11111")
            
            assert encounter.encounter_id == "E11111"
            assert encounter.status == "in-progress"
    
    @pytest.mark.asyncio
    async def test_get_encounters_batch(
        self,
        meditech_config: MeditechConfig,
    ) -> None:
        """Test batch encounter retrieval."""
        connector = MeditechConnector(meditech_config)
        
        mock_bundle_response = {
            "resourceType": "Bundle",
            "type": "batch-response",
            "entry": [
                {
                    "response": {"status": "200 OK"},
                    "resource": {
                        "resourceType": "Encounter",
                        "id": "E001",
                        "status": "finished",
                        "subject": {"reference": "Patient/P001"},
                    },
                },
                {
                    "response": {"status": "404 Not Found"},
                },
            ],
        }
        
        with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_bundle_response
            
            result = await connector.get_encounters_batch(["E001", "E002"])
            
            assert result.success_count == 1
            assert result.failure_count == 1
    
    @pytest.mark.asyncio
    async def test_get_patient_history(
        self,
        meditech_config: MeditechConfig,
    ) -> None:
        """Test getting patient history."""
        connector = MeditechConnector(meditech_config)
        
        mock_bundle = {
            "resourceType": "Bundle",
            "type": "searchset",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Encounter",
                        "id": "E001",
                        "status": "finished",
                        "subject": {"reference": "Patient/P12345"},
                    }
                },
                {
                    "resource": {
                        "resourceType": "Encounter",
                        "id": "E002",
                        "status": "finished",
                        "subject": {"reference": "Patient/P12345"},
                    }
                },
            ],
        }
        
        with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_bundle
            
            history = await connector.get_patient_history("P12345", days=60)
            
            assert len(history) == 2


# =============================================================================
# SOAP Note Tests
# =============================================================================


class TestMeditechSOAPNotes:
    """Tests for SOAP note operations."""
    
    @pytest.mark.asyncio
    async def test_write_soap_note(
        self,
        meditech_config: MeditechConfig,
        sample_soap_note: SOAPNote,
        mock_encounter_resource: dict,
    ) -> None:
        """Test writing SOAP note."""
        connector = MeditechConnector(meditech_config)
        
        with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [
                mock_encounter_resource,
                {"id": "DOC001"},
            ]
            
            result = await connector.write_soap_note(sample_soap_note)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_write_soap_notes_batch(
        self,
        meditech_config: MeditechConfig,
        mock_encounter_resource: dict,
    ) -> None:
        """Test batch SOAP note writing."""
        connector = MeditechConnector(meditech_config)
        
        notes = [
            SOAPNote(
                encounter_id="E001",
                subjective="S1",
                objective="O1",
                assessment="A1",
                plan="P1",
            ),
            SOAPNote(
                encounter_id="E002",
                subjective="S2",
                objective="O2",
                assessment="A2",
                plan="P2",
            ),
        ]
        
        with patch.object(connector, "write_soap_note", new_callable=AsyncMock) as mock_write:
            mock_write.return_value = True
            
            result = await connector.write_soap_notes_batch(notes)
            
            assert result.success_count == 2
            assert result.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_write_soap_note_validation_error(
        self,
        meditech_config: MeditechConfig,
    ) -> None:
        """Test SOAP note validation."""
        connector = MeditechConnector(meditech_config)
        
        note = SOAPNote(
            encounter_id="",
            subjective="Test",
            objective="Test",
            assessment="Test",
            plan="Test",
        )
        
        with pytest.raises(EHRValidationError):
            await connector.write_soap_note(note)


# =============================================================================
# Batch Processing Tests
# =============================================================================


class TestMeditechBatchProcessing:
    """Tests for batch processing."""
    
    @pytest.mark.asyncio
    async def test_batch_request_chunking(
        self,
        meditech_config: MeditechConfig,
    ) -> None:
        """Test that batch requests are chunked correctly."""
        # Use small batch size for testing
        config = MeditechConfig(
            base_url=meditech_config.base_url,
            client_id=meditech_config.client_id,
            client_secret=meditech_config.client_secret,
            batch_size=2,
        )
        connector = MeditechConnector(config)
        
        mock_bundle_response = {
            "resourceType": "Bundle",
            "type": "batch-response",
            "entry": [
                {
                    "response": {"status": "200 OK"},
                    "resource": {"resourceType": "Patient", "id": "P1"},
                },
                {
                    "response": {"status": "200 OK"},
                    "resource": {"resourceType": "Patient", "id": "P2"},
                },
            ],
        }
        
        with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_bundle_response
            
            # Request 4 patients with batch_size=2
            result = await connector._batch_request("Patient", ["P1", "P2", "P3", "P4"])
            
            # Should have made 2 requests (4 / 2 = 2 batches)
            assert mock_request.call_count == 2


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestMeditechErrorHandling:
    """Tests for error handling."""
    
    @pytest.mark.asyncio
    async def test_not_found_error(
        self,
        meditech_config: MeditechConfig,
    ) -> None:
        """Test 404 error handling."""
        connector = MeditechConnector(meditech_config)
        connector._access_token = "test-token"
        connector._token_expires_at = datetime.now() + timedelta(hours=1)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            with pytest.raises(EHRNotFoundError):
                await connector._request("GET", "Patient/NONEXISTENT")
    
    @pytest.mark.asyncio
    async def test_connection_error(
        self,
        meditech_config: MeditechConfig,
    ) -> None:
        """Test connection error handling."""
        connector = MeditechConnector(meditech_config)
        connector._access_token = "test-token"
        connector._token_expires_at = datetime.now() + timedelta(hours=1)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(
                side_effect=httpx.RequestError("Connection refused")
            )
            mock_get_client.return_value = mock_client
            
            with pytest.raises(EHRConnectionError):
                await connector._request("GET", "Patient/P001")


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestMeditechFactory:
    """Tests for factory function."""
    
    def test_create_meditech_connector(self) -> None:
        """Test creating connector via factory."""
        connector = create_meditech_connector(
            base_url="https://test.meditech.com/fhir/r4",
            client_id="client",
            client_secret="secret",
            token_url="https://test.meditech.com/auth/token",
            facility_id="FAC001",
            batch_size=15,
        )
        
        assert isinstance(connector, MeditechConnector)
        assert connector.connector_name == "meditech"
        assert connector.meditech_config.facility_id == "FAC001"
        assert connector.meditech_config.batch_size == 15


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestMeditechContextManager:
    """Tests for async context manager."""
    
    @pytest.mark.asyncio
    async def test_context_manager(
        self,
        meditech_config: MeditechConfig,
    ) -> None:
        """Test connector as async context manager."""
        async with MeditechConnector(meditech_config) as connector:
            assert connector.connector_name == "meditech"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
