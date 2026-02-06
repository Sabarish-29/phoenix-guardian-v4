"""NavigatorAgent - Patient Medical History Retrieval from EHR.

This module implements the NavigatorAgent, which fetches patient data from
the Electronic Health Record (EHR) system. In Phase 1, this uses a mock
implementation with an in-memory JSON database.

Phase 1: Mock implementation with JSON file database
Phase 2: Real FHIR R4 API integration (Epic, Cerner)

Classes:
    PatientNotFoundError: Raised when patient MRN not found
    NavigatorAgent: Retrieves patient medical history
"""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from phoenix_guardian.agents.base_agent import BaseAgent


class PatientNotFoundError(Exception):
    """Raised when patient MRN not found in EHR system.

    This exception is raised when a patient lookup fails because
    the Medical Record Number (MRN) does not exist in the database.

    Attributes:
        mrn: The MRN that was not found
        message: Detailed error message
    """

    def __init__(self, mrn: str, message: Optional[str] = None) -> None:
        """Initialize PatientNotFoundError.

        Args:
            mrn: The Medical Record Number that was not found
            message: Optional custom error message
        """
        self.mrn = mrn
        self.message = message or (
            f"Patient with MRN '{mrn}' not found in EHR. "
            "Please verify the Medical Record Number."
        )
        super().__init__(self.message)


class NavigatorAgent(BaseAgent):
    """Retrieves patient medical history from EHR system.

    In Phase 1, uses a mock JSON database to simulate EHR lookups.
    In Phase 2, will integrate with real FHIR R4 APIs (Epic, Cerner).

    The agent provides:
    - Fast patient data retrieval (< 100ms target)
    - Optional in-memory caching for repeated lookups
    - Field filtering to retrieve only needed data
    - Graceful handling of missing patients

    Attributes:
        data_source: Path to mock patient database file
        use_cache: Whether caching is enabled
        cache: In-memory cache for patient data
        mock_db: Loaded mock patient database

    Example:
        >>> agent = NavigatorAgent()
        >>> result = await agent.execute({'patient_mrn': 'MRN001234'})
        >>> if result.success:
        ...     print(f"Patient: {result.data['demographics']['name']}")
    """

    # Valid fields that can be requested via include_fields
    VALID_FIELDS: Set[str] = {
        "demographics",
        "conditions",
        "medications",
        "allergies",
        "vitals",
        "labs",
        "encounters",
        "last_encounter",
    }

    def __init__(
        self,
        data_source: Optional[str] = None,
        use_cache: bool = True,
    ) -> None:
        """Initialize NavigatorAgent with data source configuration.

        Args:
            data_source: Path to mock patient database JSON file.
                        If None, uses default path at
                        phoenix_guardian/data/mock_patients.json
            use_cache: Whether to cache patient data in memory.
                      Improves performance for repeated lookups.
        """
        super().__init__(name="Navigator")

        # Set up data source path
        if data_source is None:
            data_source = self._get_default_data_path()

        self.data_source = Path(data_source)
        self.use_cache = use_cache
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.mock_db: Dict[str, List[Dict[str, Any]]] = {"patients": []}

        # Load mock database
        self._load_mock_database()

    def _get_default_data_path(self) -> str:
        """Get path to default mock patient database.

        Returns:
            Absolute path to mock_patients.json file
        """
        base_path = Path(__file__).parent.parent
        return str(base_path / "data" / "mock_patients.json")

    def _load_mock_database(self) -> None:
        """Load mock patient database from JSON file.

        If the file doesn't exist, creates an empty database file.
        This allows the agent to start without pre-existing data.
        """
        if not self.data_source.exists():
            # Create directory and empty database
            self.data_source.parent.mkdir(parents=True, exist_ok=True)
            empty_db: Dict[str, List[Dict[str, Any]]] = {"patients": []}
            self.data_source.write_text(
                json.dumps(empty_db, indent=2), encoding="utf-8"
            )
            self.mock_db = empty_db
        else:
            with open(self.data_source, "r", encoding="utf-8") as file:
                self.mock_db = json.load(file)

    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch patient medical history from EHR.

        Retrieves patient data based on Medical Record Number (MRN).
        Supports optional field filtering and caching.

        Args:
            context: Must contain:
                - 'patient_mrn' (str): Medical Record Number (required)
                - 'include_fields' (List[str]): Optional fields to include
                    Options: demographics, conditions, medications,
                            allergies, vitals, labs, encounters, last_encounter
                    Default: All fields returned

        Returns:
            Dict with structure:
                {
                    'data': {
                        'mrn': str,
                        'demographics': {...},
                        'conditions': [...],
                        'medications': [...],
                        'allergies': [...],
                        'vitals': {...},
                        'labs': [...],
                        'last_encounter': {...},
                        'retrieved_at': str (ISO timestamp)
                    },
                    'reasoning': str
                }

        Raises:
            KeyError: If patient_mrn not provided
            ValueError: If input validation fails
            PatientNotFoundError: If MRN not found in database
        """
        # Step 1: Validate input
        self._validate_context(context)

        # Step 2: Extract parameters
        patient_mrn = context["patient_mrn"].strip()
        include_fields = context.get("include_fields")

        # Step 3: Check cache first
        if self.use_cache and patient_mrn in self.cache:
            patient_data = copy.deepcopy(self.cache[patient_mrn])
            reasoning = "Retrieved patient [REDACTED] from cache"
        else:
            # Step 4: Fetch from mock database
            patient_data = self._fetch_patient_data(patient_mrn)

            # Step 5: Cache result if caching enabled
            if self.use_cache:
                self.cache[patient_mrn] = copy.deepcopy(patient_data)

            reasoning = "Retrieved patient [REDACTED] from EHR database"

        # Step 6: Filter fields if requested
        if include_fields:
            patient_data = self._filter_fields(patient_data, include_fields)

        # Step 7: Add retrieval timestamp
        patient_data["retrieved_at"] = datetime.now(timezone.utc).isoformat()

        return {"data": patient_data, "reasoning": reasoning}

    def _validate_context(self, context: Dict[str, Any]) -> None:
        """Validate input context for required fields and format.

        Args:
            context: Input dictionary to validate

        Raises:
            KeyError: If required 'patient_mrn' field is missing
            ValueError: If field values are invalid
        """
        # Check patient_mrn exists
        if "patient_mrn" not in context:
            keys_str = ", ".join(context.keys()) if context else "none"
            raise KeyError(
                f"Context must contain 'patient_mrn' key. Received keys: {keys_str}"
            )

        patient_mrn = context["patient_mrn"]

        # Validate MRN type
        if not isinstance(patient_mrn, str):
            raise ValueError(
                f"patient_mrn must be string, got {type(patient_mrn).__name__}"
            )

        # Validate MRN not empty
        if not patient_mrn.strip():
            raise ValueError("patient_mrn cannot be empty")

        # Validate include_fields if provided
        if "include_fields" in context:
            include_fields = context["include_fields"]

            if not isinstance(include_fields, list):
                raise ValueError(
                    f"include_fields must be list, got {type(include_fields).__name__}"
                )

            # Check for invalid field names
            invalid_fields = set(include_fields) - self.VALID_FIELDS
            if invalid_fields:
                raise ValueError(
                    f"Invalid include_fields: {invalid_fields}. "
                    f"Valid fields: {self.VALID_FIELDS}"
                )

    def _fetch_patient_data(self, patient_mrn: str) -> Dict[str, Any]:
        """Fetch patient data from mock database.

        If the patient is not found, returns a default placeholder record
        so that new/demo MRNs can still be used for encounter creation.

        Args:
            patient_mrn: Medical Record Number to look up

        Returns:
            Copy of patient data dictionary
        """
        for patient in self.mock_db.get("patients", []):
            if patient.get("mrn") == patient_mrn:
                return patient.copy()

        # Patient not found — return a default placeholder record
        # This allows demo/testing with any MRN without pre-registration
        return {
            "mrn": patient_mrn,
            "demographics": {
                "name": "New Patient",
                "age": 0,
                "gender": "Unknown",
                "dob": "2000-01-01",
            },
            "conditions": [],
            "medications": [],
            "allergies": [],
            "vitals": {},
            "labs": [],
            "encounters": [],
        }

    def _filter_fields(
        self, patient_data: Dict[str, Any], include_fields: List[str]
    ) -> Dict[str, Any]:
        """Filter patient data to only include requested fields.

        Always includes 'mrn' field regardless of filter.

        Args:
            patient_data: Full patient data dictionary
            include_fields: List of field names to include

        Returns:
            Filtered patient data with only requested fields
        """
        # Always include MRN
        filtered: Dict[str, Any] = {"mrn": patient_data["mrn"]}

        # Include only requested fields
        for field in include_fields:
            if field in patient_data:
                filtered[field] = patient_data[field]

        return filtered

    def add_mock_patient(self, patient_data: Dict[str, Any]) -> None:
        """Add a patient to the mock database.

        Useful for testing and development. Validates required fields
        and prevents duplicate MRNs.

        Args:
            patient_data: Patient data dictionary with required fields:
                - mrn: Medical Record Number (required)
                - demographics: Patient demographics (required)

        Raises:
            ValueError: If required fields missing or MRN already exists
        """
        # Validate required fields
        required_fields = {"mrn", "demographics"}
        missing = required_fields - set(patient_data.keys())
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Check for duplicate MRN
        existing_mrns = [p["mrn"] for p in self.mock_db["patients"]]
        if patient_data["mrn"] in existing_mrns:
            raise ValueError(f"Patient with MRN '{patient_data['mrn']}' already exists")

        # Add to in-memory database
        self.mock_db["patients"].append(patient_data)

        # Persist to file
        self._save_mock_database()

    def _save_mock_database(self) -> None:
        """Save mock database to JSON file."""
        with open(self.data_source, "w", encoding="utf-8") as file:
            json.dump(self.mock_db, file, indent=2)

    def clear_cache(self) -> None:
        """Clear the in-memory patient data cache.

        Call this to force fresh database lookups on next request.
        """
        self.cache.clear()

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics for monitoring.

        Returns:
            Dictionary with:
                - cached_patients: Number of patients in cache
                - total_patients: Total patients in database
        """
        return {
            "cached_patients": len(self.cache),
            "total_patients": len(self.mock_db.get("patients", [])),
        }


def create_mock_patient_database(output_path: str) -> None:
    """Create a mock patient database with sample patients.

    Creates a JSON file with 3 sample patients for testing:
    - MRN001234: 65yo male with HTN, DM, HLD
    - MRN005678: 45yo female with asthma, allergies
    - MRN009012: 32yo healthy male

    Args:
        output_path: Path where JSON file should be created
    """
    mock_patients = {
        "patients": [
            {
                "mrn": "MRN001234",
                "demographics": {
                    "name": "John Smith",
                    "age": 65,
                    "gender": "Male",
                    "dob": "1959-03-15",
                },
                "conditions": [
                    "Hypertension",
                    "Type 2 Diabetes Mellitus",
                    "Hyperlipidemia",
                    "Chronic Kidney Disease Stage 3",
                ],
                "medications": [
                    {
                        "name": "Lisinopril",
                        "dose": "10mg",
                        "frequency": "Once daily",
                        "route": "PO",
                    },
                    {
                        "name": "Metformin",
                        "dose": "1000mg",
                        "frequency": "Twice daily",
                        "route": "PO",
                    },
                    {
                        "name": "Atorvastatin",
                        "dose": "40mg",
                        "frequency": "Once daily at bedtime",
                        "route": "PO",
                    },
                ],
                "allergies": [
                    {
                        "allergen": "Penicillin",
                        "reaction": "Rash",
                        "severity": "Moderate",
                    }
                ],
                "vitals": {
                    "blood_pressure": "135/85",
                    "heart_rate": 78,
                    "temperature": 98.4,
                    "respiratory_rate": 16,
                    "oxygen_saturation": 97,
                    "recorded_at": "2025-01-28T10:30:00Z",
                },
                "labs": [
                    {
                        "test": "HbA1c",
                        "value": "7.2%",
                        "reference_range": "<7.0%",
                        "date": "2025-01-15",
                    },
                    {
                        "test": "Creatinine",
                        "value": "1.4 mg/dL",
                        "reference_range": "0.7-1.3 mg/dL",
                        "date": "2025-01-15",
                    },
                ],
                "last_encounter": {
                    "date": "2025-01-10",
                    "type": "Office Visit",
                    "provider": "Dr. Sarah Johnson",
                    "chief_complaint": "Routine diabetes follow-up",
                },
            },
            {
                "mrn": "MRN005678",
                "demographics": {
                    "name": "Maria Garcia",
                    "age": 45,
                    "gender": "Female",
                    "dob": "1979-07-22",
                },
                "conditions": [
                    "Asthma",
                    "Seasonal Allergies",
                    "Migraine Headaches",
                ],
                "medications": [
                    {
                        "name": "Albuterol",
                        "dose": "90mcg",
                        "frequency": "As needed",
                        "route": "Inhaled",
                    },
                    {
                        "name": "Fluticasone",
                        "dose": "50mcg",
                        "frequency": "Two sprays each nostril daily",
                        "route": "Nasal",
                    },
                    {
                        "name": "Sumatriptan",
                        "dose": "100mg",
                        "frequency": "As needed for migraine",
                        "route": "PO",
                    },
                ],
                "allergies": [
                    {
                        "allergen": "Sulfa drugs",
                        "reaction": "Hives",
                        "severity": "Moderate",
                    }
                ],
                "vitals": {
                    "blood_pressure": "118/72",
                    "heart_rate": 72,
                    "temperature": 98.2,
                    "respiratory_rate": 14,
                    "oxygen_saturation": 99,
                    "recorded_at": "2025-01-29T14:15:00Z",
                },
                "labs": [],
                "last_encounter": {
                    "date": "2024-12-05",
                    "type": "Urgent Care",
                    "provider": "Dr. Michael Chen",
                    "chief_complaint": "Asthma exacerbation",
                },
            },
            {
                "mrn": "MRN009012",
                "demographics": {
                    "name": "Robert Williams",
                    "age": 32,
                    "gender": "Male",
                    "dob": "1992-11-08",
                },
                "conditions": [],
                "medications": [],
                "allergies": [
                    {
                        "allergen": "NKDA",
                        "reaction": "No Known Drug Allergies",
                        "severity": "N/A",
                    }
                ],
                "vitals": {
                    "blood_pressure": "122/78",
                    "heart_rate": 68,
                    "temperature": 98.6,
                    "respiratory_rate": 14,
                    "oxygen_saturation": 99,
                    "recorded_at": "2025-01-30T09:00:00Z",
                },
                "labs": [],
                "last_encounter": {
                    "date": "2023-06-15",
                    "type": "Annual Physical",
                    "provider": "Dr. Emily Thompson",
                    "chief_complaint": "Annual wellness exam",
                },
            },
        ]
    }

    # Create directory if needed
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Write database file
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(mock_patients, file, indent=2)

    print(f"✅ Created mock patient database: {output_path}")
    print(f"   Total patients: {len(mock_patients['patients'])}")
