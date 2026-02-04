"""
Phoenix Guardian - Allscripts Connector Tests.

Comprehensive tests for the Allscripts EHR connector with mocked HTTP.

Test Coverage:
- Authentication (OAuth 2.0)
- Patient retrieval
- Encounter retrieval
- Patient history
- SOAP note writing
- Rate limiting
- Error handling
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from phoenix_guardian.integrations.allscripts_connector import (
    AllscriptsConnector,
    AllscriptsConfig,
    RateLimiter,
    create_allscripts_connector,
    ALLSCRIPTS_RATE_LIMIT,
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
def allscripts_config() -> AllscriptsConfig:
    """Create Allscripts config for testing."""
    return AllscriptsConfig(
        base_url="https://test.allscriptscloud.com/fhir/r4",
        client_id="test-client",
        client_secret="test-secret",
        token_url="https://test.allscriptscloud.com/auth/token",
    )


@pytest.fixture
def mock_token_response() -> dict:
    """Mock OAuth token response."""
    return {
        "access_token": "test-access-token-12345",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "system/Patient.read system/Encounter.read",
    }


@pytest.fixture
def mock_patient_bundle() -> dict:
    """Mock FHIR Patient bundle response."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 1,
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "P12345",
                    "name": [{"family": "Smith", "given": ["John"]}],
                    "birthDate": "1980-05-15",
                    "gender": "male",
                }
            }
        ],
    }


@pytest.fixture
def mock_patient_resource() -> dict:
    """Mock FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": "P12345",
        "name": [{"family": "Smith", "given": ["John"]}],
        "birthDate": "1980-05-15",
        "gender": "male",
        "identifier": [
            {"system": "http://allscripts.com/mrn", "value": "MRN001"}
        ],
    }


@pytest.fixture
def mock_encounter_resource() -> dict:
    """Mock FHIR Encounter resource."""
    return {
        "resourceType": "Encounter",
        "id": "E98765",
        "status": "finished",
        "class": {"code": "AMB", "display": "ambulatory"},
        "subject": {"reference": "Patient/P12345"},
        "period": {
            "start": "2026-01-15T09:00:00Z",
            "end": "2026-01-15T09:30:00Z",
        },
    }


@pytest.fixture
def sample_soap_note() -> SOAPNote:
    """Create sample SOAP note."""
    return SOAPNote(
        encounter_id="E98765",
        subjective="Patient reports headache.",
        objective="Vitals stable.",
        assessment="Tension headache.",
        plan="OTC analgesics.",
        icd_codes=["G44.209"],
        cpt_codes=["99213"],
    )


# =============================================================================
# Configuration Tests
# =============================================================================


class TestAllscriptsConfig:
    """Tests for AllscriptsConfig."""
    
    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = AllscriptsConfig(
            base_url="https://test.allscripts.com/fhir/r4",
            client_id="client",
            client_secret="secret",
        )
        
        assert config.rate_limit == ALLSCRIPTS_RATE_LIMIT
        assert len(config.scopes) > 0
        assert config.app_name == "PhoenixGuardian"
    
    def test_custom_rate_limit(self) -> None:
        """Test custom rate limit."""
        config = AllscriptsConfig(
            base_url="https://test.allscripts.com/fhir/r4",
            client_id="client",
            client_secret="secret",
            rate_limit=10,
        )
        
        assert config.rate_limit == 10


# =============================================================================
# Rate Limiter Tests
# =============================================================================


class TestRateLimiter:
    """Tests for RateLimiter."""
    
    @pytest.mark.asyncio
    async def test_acquire_under_limit(self) -> None:
        """Test acquiring when under limit."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        # Should not block
        await limiter.acquire()
        
        assert limiter.remaining == 9
    
    @pytest.mark.asyncio
    async def test_remaining_count(self) -> None:
        """Test remaining request count."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        for _ in range(3):
            await limiter.acquire()
        
        assert limiter.remaining == 2
    
    @pytest.mark.asyncio
    async def test_acquire_at_limit(self) -> None:
        """Test acquiring at rate limit triggers wait."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        
        # Fill up the limit
        await limiter.acquire()
        await limiter.acquire()
        
        # Third should wait (we'll timeout to avoid long test)
        start = asyncio.get_event_loop().time()
        await asyncio.wait_for(limiter.acquire(), timeout=2.0)
        elapsed = asyncio.get_event_loop().time() - start
        
        # Should have waited close to 1 second
        assert elapsed >= 0.9


# =============================================================================
# Authentication Tests
# =============================================================================


class TestAllscriptsAuthentication:
    """Tests for Allscripts authentication."""
    
    @pytest.mark.asyncio
    async def test_authentication_success(
        self,
        allscripts_config: AllscriptsConfig,
        mock_token_response: dict,
    ) -> None:
        """Test successful authentication."""
        connector = AllscriptsConnector(allscripts_config)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_token_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            token = await connector._authenticate()
            
            assert token == "test-access-token-12345"
            assert connector._access_token == token
    
    @pytest.mark.asyncio
    async def test_authentication_failure(
        self,
        allscripts_config: AllscriptsConfig,
    ) -> None:
        """Test authentication failure."""
        connector = AllscriptsConnector(allscripts_config)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
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
    
    @pytest.mark.asyncio
    async def test_token_caching(
        self,
        allscripts_config: AllscriptsConfig,
        mock_token_response: dict,
    ) -> None:
        """Test that tokens are cached."""
        connector = AllscriptsConnector(allscripts_config)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_token_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # First call
            await connector._authenticate()
            
            # Second call should use cache
            await connector._authenticate()
            
            # Should only have called post once
            assert mock_client.post.call_count == 1


# =============================================================================
# Patient Operations Tests
# =============================================================================


class TestAllscriptsPatientOperations:
    """Tests for patient operations."""
    
    @pytest.mark.asyncio
    async def test_get_patient(
        self,
        allscripts_config: AllscriptsConfig,
        mock_patient_resource: dict,
    ) -> None:
        """Test getting patient by ID."""
        connector = AllscriptsConnector(allscripts_config)
        
        with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_patient_resource
            
            patient = await connector.get_patient("P12345")
            
            assert patient.patient_id == "P12345"
            assert patient.name == "John Smith"
            mock_request.assert_called_once_with("GET", "Patient/P12345")
    
    @pytest.mark.asyncio
    async def test_get_patient_not_found(
        self,
        allscripts_config: AllscriptsConfig,
    ) -> None:
        """Test getting non-existent patient."""
        connector = AllscriptsConnector(allscripts_config)
        
        with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = EHRNotFoundError(
                "Patient not found",
                connector_name="allscripts",
            )
            
            with pytest.raises(EHRNotFoundError):
                await connector.get_patient("NONEXISTENT")
    
    @pytest.mark.asyncio
    async def test_search_patients(
        self,
        allscripts_config: AllscriptsConfig,
        mock_patient_bundle: dict,
    ) -> None:
        """Test searching patients."""
        connector = AllscriptsConnector(allscripts_config)
        
        with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_patient_bundle
            
            patients = await connector.search_patients(name="Smith")
            
            assert len(patients) == 1
            assert patients[0].name == "John Smith"
    
    @pytest.mark.asyncio
    async def test_search_patients_no_params(
        self,
        allscripts_config: AllscriptsConfig,
    ) -> None:
        """Test search without parameters raises error."""
        connector = AllscriptsConnector(allscripts_config)
        
        with pytest.raises(EHRValidationError):
            await connector.search_patients()


# =============================================================================
# Encounter Operations Tests
# =============================================================================


class TestAllscriptsEncounterOperations:
    """Tests for encounter operations."""
    
    @pytest.mark.asyncio
    async def test_get_encounter(
        self,
        allscripts_config: AllscriptsConfig,
        mock_encounter_resource: dict,
    ) -> None:
        """Test getting encounter by ID."""
        connector = AllscriptsConnector(allscripts_config)
        
        with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_encounter_resource
            
            encounter = await connector.get_encounter("E98765")
            
            assert encounter.encounter_id == "E98765"
            assert encounter.patient_id == "P12345"
            assert encounter.status == "finished"
    
    @pytest.mark.asyncio
    async def test_get_patient_history(
        self,
        allscripts_config: AllscriptsConfig,
    ) -> None:
        """Test getting patient encounter history."""
        connector = AllscriptsConnector(allscripts_config)
        
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
            
            history = await connector.get_patient_history("P12345", days=30)
            
            assert len(history) == 2


# =============================================================================
# SOAP Note Tests
# =============================================================================


class TestAllscriptsSOAPNotes:
    """Tests for SOAP note operations."""
    
    @pytest.mark.asyncio
    async def test_write_soap_note(
        self,
        allscripts_config: AllscriptsConfig,
        sample_soap_note: SOAPNote,
        mock_encounter_resource: dict,
    ) -> None:
        """Test writing SOAP note."""
        connector = AllscriptsConnector(allscripts_config)
        
        with patch.object(connector, "_request", new_callable=AsyncMock) as mock_request:
            # First call gets encounter, second creates document
            mock_request.side_effect = [
                mock_encounter_resource,  # get_encounter
                {"id": "DOC001"},  # create document
            ]
            
            result = await connector.write_soap_note(sample_soap_note)
            
            assert result is True
            assert mock_request.call_count == 2
    
    @pytest.mark.asyncio
    async def test_write_soap_note_no_encounter_id(
        self,
        allscripts_config: AllscriptsConfig,
    ) -> None:
        """Test writing SOAP note without encounter ID."""
        connector = AllscriptsConnector(allscripts_config)
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
    async def test_write_soap_note_empty_content(
        self,
        allscripts_config: AllscriptsConfig,
    ) -> None:
        """Test writing SOAP note with empty content."""
        connector = AllscriptsConnector(allscripts_config)
        note = SOAPNote(
            encounter_id="E001",
            subjective="",
            objective="",
            assessment="Test",
            plan="Test",
        )
        
        with pytest.raises(EHRValidationError):
            await connector.write_soap_note(note)


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestAllscriptsErrorHandling:
    """Tests for error handling."""
    
    @pytest.mark.asyncio
    async def test_connection_error(
        self,
        allscripts_config: AllscriptsConfig,
    ) -> None:
        """Test handling connection error."""
        connector = AllscriptsConnector(allscripts_config)
        connector._access_token = "test-token"
        connector._token_expires_at = datetime.now() + timedelta(hours=1)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )
            mock_get_client.return_value = mock_client
            connector._rate_limiter.acquire = AsyncMock()
            
            with pytest.raises(EHRConnectionError):
                await connector._request("GET", "Patient/P001")
    
    @pytest.mark.asyncio
    async def test_http_error_handling(
        self,
        allscripts_config: AllscriptsConfig,
    ) -> None:
        """Test handling HTTP errors."""
        connector = AllscriptsConnector(allscripts_config)
        connector._access_token = "test-token"
        connector._token_expires_at = datetime.now() + timedelta(hours=1)
        
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_client.request = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "500",
                    request=MagicMock(),
                    response=mock_response,
                )
            )
            mock_get_client.return_value = mock_client
            connector._rate_limiter.acquire = AsyncMock()
            
            with pytest.raises(EHRConnectionError):
                await connector._request("GET", "Patient/P001")


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestAllscriptsFactory:
    """Tests for factory function."""
    
    def test_create_allscripts_connector(self) -> None:
        """Test creating connector via factory."""
        connector = create_allscripts_connector(
            base_url="https://test.allscripts.com/fhir/r4",
            client_id="client",
            client_secret="secret",
            token_url="https://test.allscripts.com/auth/token",
        )
        
        assert isinstance(connector, AllscriptsConnector)
        assert connector.connector_name == "allscripts"


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestAllscriptsContextManager:
    """Tests for async context manager."""
    
    @pytest.mark.asyncio
    async def test_context_manager(
        self,
        allscripts_config: AllscriptsConfig,
    ) -> None:
        """Test connector as async context manager."""
        async with AllscriptsConnector(allscripts_config) as connector:
            assert connector.connector_name == "allscripts"
        
        # Client should be closed
        assert connector._client is None or connector._client.is_closed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
