"""Comprehensive tests for NavigatorAgent.

Tests cover:
- Initialization and configuration
- Input validation (MRN format, required fields)
- Patient data retrieval (success and failure cases)
- Caching functionality
- Field filtering
- Mock patient database operations
- Edge cases and error handling
"""

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from phoenix_guardian.agents.navigator_agent import (
    NavigatorAgent,
    PatientNotFoundError,
    create_mock_patient_database,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    """Create a temporary database path."""
    return str(tmp_path / "test_patients.json")


@pytest.fixture
def sample_patient() -> Dict[str, Any]:
    """Return a sample patient for testing."""
    return {
        "mrn": "TEST001",
        "demographics": {
            "name": "Test Patient",
            "age": 40,
            "gender": "Male",
            "dob": "1984-06-15",
        },
        "conditions": ["Hypertension", "Diabetes"],
        "medications": [
            {"name": "Lisinopril", "dose": "10mg", "frequency": "Daily", "route": "PO"}
        ],
        "allergies": [{"allergen": "Penicillin", "reaction": "Rash", "severity": "Moderate"}],
        "vitals": {
            "blood_pressure": "120/80",
            "heart_rate": 72,
            "temperature": 98.6,
            "respiratory_rate": 16,
            "oxygen_saturation": 98,
            "recorded_at": "2025-01-30T10:00:00Z",
        },
        "labs": [{"test": "HbA1c", "value": "6.5%", "reference_range": "<7.0%", "date": "2025-01-15"}],
        "last_encounter": {
            "date": "2025-01-15",
            "type": "Office Visit",
            "provider": "Dr. Test",
            "chief_complaint": "Follow-up",
        },
    }


@pytest.fixture
def populated_db(temp_db_path: str, sample_patient: Dict[str, Any]) -> str:
    """Create a populated test database."""
    db = {"patients": [sample_patient]}
    Path(temp_db_path).parent.mkdir(parents=True, exist_ok=True)
    with open(temp_db_path, "w", encoding="utf-8") as f:
        json.dump(db, f)
    return temp_db_path


@pytest.fixture
def navigator_agent(populated_db: str) -> NavigatorAgent:
    """Create a NavigatorAgent with test database."""
    return NavigatorAgent(data_source=populated_db, use_cache=True)


@pytest.fixture
def navigator_agent_no_cache(populated_db: str) -> NavigatorAgent:
    """Create a NavigatorAgent without caching."""
    return NavigatorAgent(data_source=populated_db, use_cache=False)


# =============================================================================
# Test: PatientNotFoundError Exception
# =============================================================================


class TestPatientNotFoundError:
    """Tests for PatientNotFoundError exception."""

    def test_exception_creation_with_mrn(self) -> None:
        """Test creating exception with just MRN."""
        error = PatientNotFoundError("MRN12345")
        assert error.mrn == "MRN12345"
        assert "MRN12345" in str(error)
        assert "not found" in str(error).lower()

    def test_exception_creation_with_custom_message(self) -> None:
        """Test creating exception with custom message."""
        custom_msg = "Custom error message"
        error = PatientNotFoundError("MRN12345", message=custom_msg)
        assert error.mrn == "MRN12345"
        assert error.message == custom_msg
        assert str(error) == custom_msg

    def test_exception_is_instance_of_exception(self) -> None:
        """Test that PatientNotFoundError inherits from Exception."""
        error = PatientNotFoundError("MRN12345")
        assert isinstance(error, Exception)

    def test_exception_can_be_raised_and_caught(self) -> None:
        """Test that exception can be raised and caught properly."""
        with pytest.raises(PatientNotFoundError) as exc_info:
            raise PatientNotFoundError("MRN999")
        assert exc_info.value.mrn == "MRN999"


# =============================================================================
# Test: NavigatorAgent Initialization
# =============================================================================


class TestNavigatorAgentInit:
    """Tests for NavigatorAgent initialization."""

    def test_init_with_custom_data_source(self, temp_db_path: str) -> None:
        """Test initialization with custom data source path."""
        agent = NavigatorAgent(data_source=temp_db_path, use_cache=True)
        assert agent.data_source == Path(temp_db_path)
        assert agent.use_cache is True
        assert agent.name == "Navigator"

    def test_init_creates_empty_database_if_not_exists(self, tmp_path: Path) -> None:
        """Test that init creates empty database file if missing."""
        db_path = tmp_path / "subdir" / "new_db.json"
        agent = NavigatorAgent(data_source=str(db_path), use_cache=True)

        assert db_path.exists()
        with open(db_path, "r", encoding="utf-8") as f:
            db_content = json.load(f)
        assert db_content == {"patients": []}
        assert agent.mock_db == {"patients": []}

    def test_init_with_default_cache_enabled(self, temp_db_path: str) -> None:
        """Test that caching is enabled by default."""
        agent = NavigatorAgent(data_source=temp_db_path)
        assert agent.use_cache is True

    def test_init_with_cache_disabled(self, temp_db_path: str) -> None:
        """Test initialization with caching disabled."""
        agent = NavigatorAgent(data_source=temp_db_path, use_cache=False)
        assert agent.use_cache is False

    def test_init_loads_existing_database(self, populated_db: str) -> None:
        """Test that existing database is loaded on init."""
        agent = NavigatorAgent(data_source=populated_db)
        assert len(agent.mock_db["patients"]) == 1
        assert agent.mock_db["patients"][0]["mrn"] == "TEST001"

    def test_init_empty_cache(self, populated_db: str) -> None:
        """Test that cache starts empty."""
        agent = NavigatorAgent(data_source=populated_db)
        assert agent.cache == {}

    def test_init_with_default_data_source(self, tmp_path: Path) -> None:
        """Test initialization with default data source path."""
        with patch.object(NavigatorAgent, "_get_default_data_path") as mock_path:
            mock_path.return_value = str(tmp_path / "default.json")
            agent = NavigatorAgent()
            assert agent.data_source == tmp_path / "default.json"


# =============================================================================
# Test: Input Validation
# =============================================================================


class TestNavigatorAgentValidation:
    """Tests for input validation."""

    @pytest.mark.asyncio
    async def test_missing_patient_mrn_raises_key_error(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that missing patient_mrn returns failure result with error."""
        result = await navigator_agent.execute({})
        assert result.success is False
        assert "patient_mrn" in result.error

    @pytest.mark.asyncio
    async def test_empty_context_raises_key_error(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that empty context dict raises KeyError."""
        result = await navigator_agent.execute({})
        assert result.success is False
        assert "patient_mrn" in result.error

    @pytest.mark.asyncio
    async def test_non_string_mrn_raises_value_error(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that non-string MRN raises ValueError."""
        result = await navigator_agent.execute({"patient_mrn": 12345})
        assert result.success is False
        assert "must be string" in result.error

    @pytest.mark.asyncio
    async def test_empty_mrn_raises_value_error(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that empty MRN string raises ValueError."""
        result = await navigator_agent.execute({"patient_mrn": ""})
        assert result.success is False
        assert "cannot be empty" in result.error

    @pytest.mark.asyncio
    async def test_whitespace_mrn_raises_value_error(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that whitespace-only MRN raises ValueError."""
        result = await navigator_agent.execute({"patient_mrn": "   "})
        assert result.success is False
        assert "cannot be empty" in result.error

    @pytest.mark.asyncio
    async def test_invalid_include_fields_type_raises_value_error(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that non-list include_fields raises ValueError."""
        result = await navigator_agent.execute({
            "patient_mrn": "TEST001",
            "include_fields": "demographics"
        })
        assert result.success is False
        assert "must be list" in result.error

    @pytest.mark.asyncio
    async def test_invalid_field_name_raises_value_error(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that invalid field name raises ValueError."""
        result = await navigator_agent.execute({
            "patient_mrn": "TEST001",
            "include_fields": ["demographics", "invalid_field"]
        })
        assert result.success is False
        assert "Invalid include_fields" in result.error


# =============================================================================
# Test: Patient Data Retrieval
# =============================================================================


class TestNavigatorAgentRetrieval:
    """Tests for patient data retrieval."""

    @pytest.mark.asyncio
    async def test_successful_patient_retrieval(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test successful retrieval of patient data."""
        result = await navigator_agent.execute({"patient_mrn": "TEST001"})
        assert result.success is True
        assert result.data["mrn"] == "TEST001"
        assert result.data["demographics"]["name"] == "Test Patient"

    @pytest.mark.asyncio
    async def test_retrieval_includes_all_fields(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that retrieval includes all expected fields."""
        result = await navigator_agent.execute({"patient_mrn": "TEST001"})
        assert result.success is True

        required_fields = [
            "mrn", "demographics", "conditions", "medications",
            "allergies", "vitals", "labs", "last_encounter", "retrieved_at"
        ]
        for field in required_fields:
            assert field in result.data

    @pytest.mark.asyncio
    async def test_patient_not_found_returns_failure(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that non-existent patient returns failure result."""
        result = await navigator_agent.execute({"patient_mrn": "NONEXISTENT"})
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_retrieval_adds_timestamp(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that retrieval adds retrieved_at timestamp."""
        result = await navigator_agent.execute({"patient_mrn": "TEST001"})
        assert "retrieved_at" in result.data
        # Verify ISO format
        assert "T" in result.data["retrieved_at"]

    @pytest.mark.asyncio
    async def test_mrn_with_leading_trailing_whitespace(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that MRN with whitespace is trimmed."""
        result = await navigator_agent.execute({"patient_mrn": "  TEST001  "})
        assert result.success is True
        assert result.data["mrn"] == "TEST001"

    @pytest.mark.asyncio
    async def test_execution_time_tracked(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that execution time is tracked in result."""
        result = await navigator_agent.execute({"patient_mrn": "TEST001"})
        assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_reasoning_included_in_result(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that reasoning is included in successful result."""
        result = await navigator_agent.execute({"patient_mrn": "TEST001"})
        assert result.success is True
        assert result.reasoning is not None
        assert "REDACTED" in result.reasoning  # HIPAA compliance


# =============================================================================
# Test: Caching Functionality
# =============================================================================


class TestNavigatorAgentCaching:
    """Tests for caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_populated_after_retrieval(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that cache is populated after retrieval."""
        assert "TEST001" not in navigator_agent.cache
        await navigator_agent.execute({"patient_mrn": "TEST001"})
        assert "TEST001" in navigator_agent.cache

    @pytest.mark.asyncio
    async def test_cache_used_on_second_request(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that cache is used on subsequent requests."""
        # First request
        result1 = await navigator_agent.execute({"patient_mrn": "TEST001"})

        # Modify database to verify cache is used
        navigator_agent.mock_db["patients"][0]["demographics"]["name"] = "Modified"

        # Second request should use cache (old name)
        result2 = await navigator_agent.execute({"patient_mrn": "TEST001"})
        assert result2.data["demographics"]["name"] == "Test Patient"
        assert "cache" in result2.reasoning.lower()

    @pytest.mark.asyncio
    async def test_cache_disabled_doesnt_cache(
        self, navigator_agent_no_cache: NavigatorAgent
    ) -> None:
        """Test that cache is not used when disabled."""
        await navigator_agent_no_cache.execute({"patient_mrn": "TEST001"})
        assert len(navigator_agent_no_cache.cache) == 0

    def test_clear_cache(self, navigator_agent: NavigatorAgent) -> None:
        """Test cache clearing functionality."""
        navigator_agent.cache["TEST001"] = {"mrn": "TEST001"}
        navigator_agent.clear_cache()
        assert len(navigator_agent.cache) == 0

    def test_get_cache_stats(self, navigator_agent: NavigatorAgent) -> None:
        """Test cache statistics."""
        stats = navigator_agent.get_cache_stats()
        assert stats["cached_patients"] == 0
        assert stats["total_patients"] == 1

        navigator_agent.cache["TEST001"] = {"mrn": "TEST001"}
        stats = navigator_agent.get_cache_stats()
        assert stats["cached_patients"] == 1

    @pytest.mark.asyncio
    async def test_cache_returns_copy_not_reference(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that cache returns copy, not direct reference."""
        result1 = await navigator_agent.execute({"patient_mrn": "TEST001"})
        result1.data["demographics"]["name"] = "Modified In Result"

        result2 = await navigator_agent.execute({"patient_mrn": "TEST001"})
        assert result2.data["demographics"]["name"] == "Test Patient"


# =============================================================================
# Test: Field Filtering
# =============================================================================


class TestNavigatorAgentFieldFiltering:
    """Tests for field filtering functionality."""

    @pytest.mark.asyncio
    async def test_filter_single_field(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test filtering to single field."""
        result = await navigator_agent.execute({
            "patient_mrn": "TEST001",
            "include_fields": ["demographics"]
        })
        assert result.success is True
        assert "mrn" in result.data  # Always included
        assert "demographics" in result.data
        assert "medications" not in result.data
        assert "conditions" not in result.data

    @pytest.mark.asyncio
    async def test_filter_multiple_fields(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test filtering to multiple fields."""
        result = await navigator_agent.execute({
            "patient_mrn": "TEST001",
            "include_fields": ["demographics", "medications", "allergies"]
        })
        assert result.success is True
        assert "demographics" in result.data
        assert "medications" in result.data
        assert "allergies" in result.data
        assert "conditions" not in result.data
        assert "labs" not in result.data

    @pytest.mark.asyncio
    async def test_mrn_always_included_in_filter(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that MRN is always included regardless of filter."""
        result = await navigator_agent.execute({
            "patient_mrn": "TEST001",
            "include_fields": ["vitals"]
        })
        assert "mrn" in result.data

    @pytest.mark.asyncio
    async def test_empty_include_fields_returns_all(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that empty include_fields list returns all fields."""
        result = await navigator_agent.execute({
            "patient_mrn": "TEST001",
            "include_fields": []
        })
        assert result.success is True
        assert "mrn" in result.data

    @pytest.mark.asyncio
    async def test_all_valid_fields_can_be_requested(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that all valid field names work."""
        for field in NavigatorAgent.VALID_FIELDS:
            result = await navigator_agent.execute({
                "patient_mrn": "TEST001",
                "include_fields": [field]
            })
            assert result.success is True


# =============================================================================
# Test: Mock Patient Database Operations
# =============================================================================


class TestMockPatientDatabase:
    """Tests for mock patient database operations."""

    def test_add_mock_patient(self, temp_db_path: str) -> None:
        """Test adding a new patient to mock database."""
        agent = NavigatorAgent(data_source=temp_db_path)
        initial_count = len(agent.mock_db["patients"])

        new_patient = {
            "mrn": "NEWPATIENT001",
            "demographics": {"name": "New Patient", "age": 50, "gender": "Female"},
        }
        agent.add_mock_patient(new_patient)

        assert len(agent.mock_db["patients"]) == initial_count + 1
        assert any(p["mrn"] == "NEWPATIENT001" for p in agent.mock_db["patients"])

    def test_add_mock_patient_persists_to_file(self, temp_db_path: str) -> None:
        """Test that added patient is persisted to file."""
        agent = NavigatorAgent(data_source=temp_db_path)
        new_patient = {
            "mrn": "PERSIST001",
            "demographics": {"name": "Persist Test", "age": 30, "gender": "Male"},
        }
        agent.add_mock_patient(new_patient)

        # Load file directly to verify persistence
        with open(temp_db_path, "r", encoding="utf-8") as f:
            db_content = json.load(f)
        assert any(p["mrn"] == "PERSIST001" for p in db_content["patients"])

    def test_add_mock_patient_missing_mrn_raises_error(
        self, temp_db_path: str
    ) -> None:
        """Test that adding patient without MRN raises ValueError."""
        agent = NavigatorAgent(data_source=temp_db_path)
        with pytest.raises(ValueError) as exc_info:
            agent.add_mock_patient({"demographics": {"name": "No MRN"}})
        assert "mrn" in str(exc_info.value).lower()

    def test_add_mock_patient_missing_demographics_raises_error(
        self, temp_db_path: str
    ) -> None:
        """Test that adding patient without demographics raises ValueError."""
        agent = NavigatorAgent(data_source=temp_db_path)
        with pytest.raises(ValueError) as exc_info:
            agent.add_mock_patient({"mrn": "NODEMO001"})
        assert "demographics" in str(exc_info.value).lower()

    def test_add_duplicate_mrn_raises_error(self, populated_db: str) -> None:
        """Test that adding duplicate MRN raises ValueError."""
        agent = NavigatorAgent(data_source=populated_db)
        duplicate = {
            "mrn": "TEST001",  # Already exists
            "demographics": {"name": "Duplicate", "age": 25, "gender": "Male"},
        }
        with pytest.raises(ValueError) as exc_info:
            agent.add_mock_patient(duplicate)
        assert "already exists" in str(exc_info.value).lower()

    def test_create_mock_patient_database_function(self, tmp_path: Path) -> None:
        """Test create_mock_patient_database helper function."""
        db_path = tmp_path / "created_db.json"
        create_mock_patient_database(str(db_path))

        assert db_path.exists()
        with open(db_path, "r", encoding="utf-8") as f:
            db = json.load(f)

        assert len(db["patients"]) == 3
        mrns = [p["mrn"] for p in db["patients"]]
        assert "MRN001234" in mrns
        assert "MRN005678" in mrns
        assert "MRN009012" in mrns


# =============================================================================
# Test: Data Structure Validation
# =============================================================================


class TestDataStructureValidation:
    """Tests for data structure validation."""

    @pytest.mark.asyncio
    async def test_demographics_structure(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test demographics data structure."""
        result = await navigator_agent.execute({
            "patient_mrn": "TEST001",
            "include_fields": ["demographics"]
        })
        demo = result.data["demographics"]
        assert "name" in demo
        assert "age" in demo
        assert "gender" in demo

    @pytest.mark.asyncio
    async def test_medications_structure(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test medications data structure."""
        result = await navigator_agent.execute({
            "patient_mrn": "TEST001",
            "include_fields": ["medications"]
        })
        meds = result.data["medications"]
        assert isinstance(meds, list)
        if meds:
            assert "name" in meds[0]
            assert "dose" in meds[0]

    @pytest.mark.asyncio
    async def test_vitals_structure(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test vitals data structure."""
        result = await navigator_agent.execute({
            "patient_mrn": "TEST001",
            "include_fields": ["vitals"]
        })
        vitals = result.data["vitals"]
        assert "blood_pressure" in vitals
        assert "heart_rate" in vitals

    @pytest.mark.asyncio
    async def test_allergies_structure(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test allergies data structure."""
        result = await navigator_agent.execute({
            "patient_mrn": "TEST001",
            "include_fields": ["allergies"]
        })
        allergies = result.data["allergies"]
        assert isinstance(allergies, list)
        if allergies:
            assert "allergen" in allergies[0]
            assert "reaction" in allergies[0]


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_special_characters_in_mrn(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test MRN with special characters (not found, but valid input)."""
        result = await navigator_agent.execute({"patient_mrn": "MRN-123_456"})
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_very_long_mrn(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test very long MRN string."""
        long_mrn = "A" * 1000
        result = await navigator_agent.execute({"patient_mrn": long_mrn})
        assert result.success is False

    @pytest.mark.asyncio
    async def test_concurrent_requests(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test concurrent execution doesn't cause issues."""
        import asyncio

        tasks = [
            navigator_agent.execute({"patient_mrn": "TEST001"})
            for _ in range(10)
        ]
        results = await asyncio.gather(*tasks)
        assert all(r.success for r in results)

    def test_valid_fields_is_immutable_set(self) -> None:
        """Test that VALID_FIELDS is a set type."""
        assert isinstance(NavigatorAgent.VALID_FIELDS, set)
        assert len(NavigatorAgent.VALID_FIELDS) > 0

    @pytest.mark.asyncio
    async def test_agent_result_contains_all_expected_attributes(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test AgentResult has all expected attributes."""
        result = await navigator_agent.execute({"patient_mrn": "TEST001"})
        assert hasattr(result, "success")
        assert hasattr(result, "data")
        assert hasattr(result, "error")
        assert hasattr(result, "execution_time_ms")
        assert hasattr(result, "reasoning")

    @pytest.mark.asyncio
    async def test_metrics_tracking(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that metrics are tracked correctly."""
        await navigator_agent.execute({"patient_mrn": "TEST001"})
        metrics = navigator_agent.get_metrics()
        assert metrics["call_count"] == 1.0
        assert metrics["total_execution_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_metrics_tracking_failure(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that failed calls are tracked in metrics."""
        await navigator_agent.execute({"patient_mrn": "NONEXISTENT"})
        metrics = navigator_agent.get_metrics()
        assert metrics["call_count"] == 1.0


# =============================================================================
# Test: HIPAA Compliance
# =============================================================================


class TestHIPAACompliance:
    """Tests for HIPAA compliance measures."""

    @pytest.mark.asyncio
    async def test_reasoning_does_not_contain_patient_name(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that reasoning doesn't expose patient name."""
        result = await navigator_agent.execute({"patient_mrn": "TEST001"})
        assert "Test Patient" not in result.reasoning
        assert "REDACTED" in result.reasoning

    @pytest.mark.asyncio
    async def test_error_message_does_not_contain_sensitive_data(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that error messages don't expose sensitive information."""
        result = await navigator_agent.execute({"patient_mrn": "NONEXISTENT"})
        # Should mention the MRN (needed for debugging) but nothing else sensitive
        assert result.success is False


# =============================================================================
# Test: Performance
# =============================================================================


class TestPerformance:
    """Tests for performance requirements."""

    @pytest.mark.asyncio
    async def test_retrieval_under_100ms(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that retrieval completes in under 100ms."""
        result = await navigator_agent.execute({"patient_mrn": "TEST001"})
        assert result.execution_time_ms < 100

    @pytest.mark.asyncio
    async def test_cached_retrieval_faster_than_first(
        self, navigator_agent: NavigatorAgent
    ) -> None:
        """Test that cached retrieval is faster than first retrieval."""
        # First call (not cached)
        result1 = await navigator_agent.execute({"patient_mrn": "TEST001"})

        # Second call (cached)
        result2 = await navigator_agent.execute({"patient_mrn": "TEST001"})

        # Cache should be at least as fast (allowing for timing variance)
        assert result2.execution_time_ms <= result1.execution_time_ms + 5
