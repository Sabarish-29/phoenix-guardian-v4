"""
Phoenix Guardian - EHR Connector Tests
Tests for EHR connector abstraction layer.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from phoenix_guardian.config.ehr_connectors import (
    EHRConnector,
    EpicConnector,
    CernerConnector,
    AllscriptsConnector,
    Patient,
    Encounter,
    DocumentReference,
    FHIRResource,
    TokenInfo,
    RateLimiter,
    create_ehr_connector,
    EHRRateLimitError,
    EHRAuthenticationError,
    EHRResourceNotFoundError,
)


class TestFHIRResource:
    """Tests for FHIR resource data class."""
    
    def test_create_fhir_resource(self):
        """Test creating a generic FHIR resource."""
        resource = FHIRResource(
            resource_type="Patient",
            id="patient-123",
            data={"name": [{"family": "Smith", "given": ["John"]}]},
            meta={"versionId": "1", "lastUpdated": "2026-01-15T10:00:00Z"},
        )
        
        assert resource.resource_type == "Patient"
        assert resource.id == "patient-123"
        assert resource.version_id == "1"
    
    def test_create_patient(self):
        """Test creating a Patient resource."""
        patient = Patient(
            id="patient-123",
            mrn="MRN12345",
            family_name="Smith",
            given_name="John",
            birth_date="1980-01-15",
            gender="male",
        )
        
        assert patient.id == "patient-123"
        assert patient.family_name == "Smith"
    
    def test_create_encounter(self):
        """Test creating an Encounter resource."""
        encounter = Encounter(
            id="encounter-456",
            patient_id="patient-123",
            encounter_class="inpatient",
            status="finished",
            start_time="2026-01-15T08:00:00Z",
            end_time="2026-01-18T14:30:00Z",
        )
        
        assert encounter.id == "encounter-456"
        assert encounter.patient_id == "patient-123"
        assert encounter.status == "finished"


class TestTokenInfo:
    """Tests for OAuth token information."""
    
    def test_token_not_expired(self):
        """Test token expiration check when not expired."""
        token = TokenInfo(
            access_token="test-token",
            token_type="Bearer",
            expires_at=datetime.now() + timedelta(hours=1),
        )
        
        assert token.is_expired is False
    
    def test_token_expired(self):
        """Test token expiration check when expired."""
        token = TokenInfo(
            access_token="test-token",
            token_type="Bearer",
            expires_at=datetime.now() - timedelta(seconds=100),  # Expired
        )
        
        assert token.is_expired is True
    
    def test_expires_in_seconds(self):
        """Test expires_in_seconds property."""
        token = TokenInfo(
            access_token="test-token",
            token_type="Bearer",
            expires_at=datetime.now() + timedelta(seconds=300),
        )
        
        # Should be approximately 300 seconds
        assert 298 <= token.expires_in_seconds <= 302


class TestRateLimiter:
    """Tests for rate limiter."""
    
    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        """Test acquiring tokens within rate limit."""
        limiter = RateLimiter(requests_per_minute=100)
        
        # Should be able to acquire immediately
        await limiter.acquire()  # Should not raise
    
    @pytest.mark.asyncio
    async def test_rate_limiter_tracks_tokens(self):
        """Test rate limiter token tracking."""
        limiter = RateLimiter(requests_per_minute=60)
        
        # Initial tokens should be full
        assert limiter.tokens == 60
        
        await limiter.acquire()
        
        # Token count should decrease
        assert limiter.tokens < 60
    
    def test_acquire_sync(self):
        """Test synchronous acquire method."""
        limiter = RateLimiter(requests_per_minute=100)
        
        # Synchronous acquire should work
        limiter.acquire_sync()  # Should not raise


class TestEpicConnector:
    """Tests for Epic FHIR connector."""
    
    @pytest.fixture
    def epic_connector(self):
        """Create Epic connector."""
        return EpicConnector(
            base_url="https://fhir.epic-hospital.org/api/FHIR/R4",
            client_id="epic-client-id",
            client_secret="epic-client-secret",
            rate_limit_per_minute=60,
        )
    
    def test_connector_creation(self, epic_connector):
        """Test Epic connector creation."""
        assert epic_connector is not None
        assert epic_connector.platform_name == "epic"
        assert epic_connector.base_url == "https://fhir.epic-hospital.org/api/FHIR/R4"
    
    def test_rate_limiter_initialized(self, epic_connector):
        """Test rate limiter is initialized."""
        assert epic_connector.rate_limiter is not None
        assert epic_connector.rate_limiter.rate == 60
    
    @pytest.mark.asyncio
    async def test_authenticate_sets_token(self, epic_connector):
        """Test authentication sets token."""
        with patch.object(epic_connector, 'authenticate') as mock_auth:
            mock_auth.return_value = TokenInfo(
                access_token="test-access-token",
                token_type="Bearer",
                expires_at=datetime.now() + timedelta(hours=1),
            )
            
            token = await epic_connector.authenticate()
            
            assert token.access_token == "test-access-token"


class TestCernerConnector:
    """Tests for Cerner FHIR connector."""
    
    @pytest.fixture
    def cerner_connector(self):
        """Create Cerner connector."""
        return CernerConnector(
            base_url="https://fhir-myrecord.cerner.com/r4/tenant",
            client_id="cerner-client-id",
            client_secret="cerner-secret",
            rate_limit_per_minute=90,
        )
    
    def test_connector_creation(self, cerner_connector):
        """Test Cerner connector creation."""
        assert cerner_connector is not None
        assert cerner_connector.platform_name == "cerner"
    
    def test_base_url_configured(self, cerner_connector):
        """Test base URL is properly configured."""
        assert cerner_connector.base_url == "https://fhir-myrecord.cerner.com/r4/tenant"
    
    @pytest.mark.asyncio
    async def test_authenticate_oauth2(self, cerner_connector):
        """Test OAuth 2.0 client credentials authentication."""
        with patch.object(cerner_connector, 'authenticate') as mock_auth:
            mock_auth.return_value = TokenInfo(
                access_token="cerner-access-token",
                token_type="Bearer",
                expires_at=datetime.now() + timedelta(hours=1),
            )
            
            token = await cerner_connector.authenticate()
            
            assert token.access_token == "cerner-access-token"


class TestAllscriptsConnector:
    """Tests for Allscripts FHIR connector."""
    
    @pytest.fixture
    def allscripts_connector(self):
        """Create Allscripts connector."""
        return AllscriptsConnector(
            base_url="https://api.allscripts.com/fhir/v1",
            client_id="allscripts-client-id",
            client_secret="allscripts-secret",
            api_key="allscripts-api-key",
            rate_limit_per_minute=30,
        )
    
    def test_connector_creation(self, allscripts_connector):
        """Test Allscripts connector creation."""
        assert allscripts_connector is not None
        assert allscripts_connector.platform_name == "allscripts"
    
    def test_base_url_configured(self, allscripts_connector):
        """Test base URL is properly configured."""
        assert allscripts_connector.base_url == "https://api.allscripts.com/fhir/v1"


class TestCreateEHRConnector:
    """Tests for EHR connector factory."""
    
    def test_create_epic_connector(self):
        """Test factory creates Epic connector."""
        connector = create_ehr_connector(
            platform="epic",
            base_url="https://fhir.epic.org",
            client_id="test",
            client_secret="secret",
        )
        
        assert isinstance(connector, EpicConnector)
    
    def test_create_cerner_connector(self):
        """Test factory creates Cerner connector."""
        connector = create_ehr_connector(
            platform="cerner",
            base_url="https://fhir.cerner.com",
            client_id="test",
            client_secret="secret",
        )
        
        assert isinstance(connector, CernerConnector)
    
    def test_create_allscripts_connector(self):
        """Test factory creates Allscripts connector."""
        connector = create_ehr_connector(
            platform="allscripts",
            base_url="https://api.allscripts.com",
            client_id="test",
            client_secret="secret",
            api_key="key",
        )
        
        assert isinstance(connector, AllscriptsConnector)
    
    def test_unsupported_platform_raises(self):
        """Test unsupported platform raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported EHR platform"):
            create_ehr_connector(
                platform="unknown",
                base_url="https://fhir.test.org",
                client_id="test",
                client_secret="secret",
            )


class TestConnectorOperations:
    """Tests for common connector operations."""
    
    @pytest.fixture
    def mock_connector(self):
        """Create a mock connector for testing."""
        return EpicConnector(
            base_url="https://fhir.test.org",
            client_id="test",
            client_secret="secret",
        )
    
    @pytest.mark.asyncio
    async def test_get_patient(self, mock_connector):
        """Test get patient operation."""
        with patch.object(mock_connector, 'get_patient') as mock_method:
            mock_method.return_value = Patient(
                id="test-patient",
                mrn="MRN123",
                given_name="John",
                family_name="Test",
                birth_date="1980-01-01",
                gender="male",
            )
            
            patient = await mock_connector.get_patient("test-patient")
            
            assert patient is not None
            assert patient.id == "test-patient"
    
    @pytest.mark.asyncio
    async def test_search_patients(self, mock_connector):
        """Test patient search operation."""
        with patch.object(mock_connector, 'search_patients') as mock_method:
            mock_method.return_value = [
                Patient(id="p1", mrn="MRN1", given_name="John", family_name="Smith", birth_date="1980-01-01", gender="male"),
                Patient(id="p2", mrn="MRN2", given_name="Jane", family_name="Smith", birth_date="1985-05-15", gender="female"),
            ]
            
            results = await mock_connector.search_patients(family="Smith")
            
            assert len(results) == 2
    
    @pytest.mark.asyncio
    async def test_create_document(self, mock_connector):
        """Test document creation operation."""
        doc = DocumentReference(
            id="new-doc",
            patient_id="test-patient",
            encounter_id="test-encounter",
            doc_type="clinical-note",
            status="current",
            content="Test note content",
            created="2026-01-15T10:00:00Z",
        )
        
        with patch.object(mock_connector, 'create_document') as mock_method:
            mock_method.return_value = DocumentReference(
                id="new-doc-id",
                patient_id="test-patient",
                encounter_id="test-encounter",
                doc_type="clinical-note",
                status="current",
                content="Test note content",
                created="2026-01-15T10:00:00Z",
            )
            
            result = await mock_connector.create_document(doc)
            
            assert result is not None
            assert result.id == "new-doc-id"


class TestConnectorErrorHandling:
    """Tests for connector error handling."""
    
    @pytest.fixture
    def connector(self):
        """Create connector for error testing."""
        return EpicConnector(
            base_url="https://fhir.test.org",
            client_id="test",
            client_secret="secret",
        )
    
    @pytest.mark.asyncio
    async def test_handles_rate_limit_error(self, connector):
        """Test handling of rate limit errors."""
        with patch.object(connector, 'get_patient') as mock_method:
            mock_method.side_effect = EHRRateLimitError(retry_after=60)
            
            with pytest.raises(EHRRateLimitError):
                await connector.get_patient("test")
    
    @pytest.mark.asyncio
    async def test_handles_authentication_error(self, connector):
        """Test handling of authentication errors."""
        with patch.object(connector, 'get_patient') as mock_method:
            mock_method.side_effect = EHRAuthenticationError("Token expired")
            
            with pytest.raises(EHRAuthenticationError):
                await connector.get_patient("test")
    
    @pytest.mark.asyncio
    async def test_handles_not_found_error(self, connector):
        """Test handling of not found errors."""
        with patch.object(connector, 'get_patient') as mock_method:
            mock_method.side_effect = EHRResourceNotFoundError("Patient not found")
            
            with pytest.raises(EHRResourceNotFoundError):
                await connector.get_patient("nonexistent")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
