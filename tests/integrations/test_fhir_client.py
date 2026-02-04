"""
Tests for FHIR R4 Client - Phoenix Guardian EHR Integration.

This test module provides comprehensive coverage for the FHIR client including:
- Authentication and connection tests
- Patient CRUD operations
- Observation read/write operations
- Condition read/write operations
- Medication request operations
- Document reference operations
- Diagnostic report operations
- Error handling tests
- Resource parsing tests

Test Count: 60+ test cases
Target Coverage: 90%+
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
import json
import base64

from phoenix_guardian.integrations.fhir_client import (
    FHIRClient,
    FHIRConfig,
    FHIRPatient,
    FHIRObservation,
    FHIRCondition,
    FHIRMedicationRequest,
    FHIRDocumentReference,
    FHIRDiagnosticReport,
    FHIRBundle,
    FHIRResourceType,
    ObservationStatus,
    ObservationCategory,
    ConditionClinicalStatus,
    ConditionVerificationStatus,
    MedicationRequestStatus,
    DocumentReferenceStatus,
    LOINCCodes,
    FHIRError,
    FHIRAuthenticationError,
    FHIRNotFoundError,
    FHIRValidationError,
    FHIRPermissionError,
    FHIRServerError,
    FHIRConnectionError,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def fhir_config():
    """Create test FHIR configuration."""
    return FHIRConfig(
        base_url="https://test-fhir.example.com/api/FHIR/R4/",
        client_id="test-client-id",
        client_secret="test-client-secret",
        access_token="test-access-token",
        token_url="https://test-fhir.example.com/oauth/token",
        timeout=30,
        max_retries=3
    )


@pytest.fixture
def fhir_client(fhir_config):
    """Create FHIR client with mocked session."""
    with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Set up default headers
        mock_session.headers = {}
        
        client = FHIRClient(fhir_config)
        client.session = mock_session
        return client


@pytest.fixture
def sample_patient_resource():
    """Sample FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": "patient-123",
        "active": True,
        "name": [
            {
                "use": "official",
                "family": "Smith",
                "given": ["John", "Michael"]
            }
        ],
        "gender": "male",
        "birthDate": "1980-05-15",
        "identifier": [
            {
                "type": {
                    "coding": [{"code": "MR"}],
                    "text": "MRN"
                },
                "value": "MRN123456"
            },
            {
                "type": {
                    "coding": [{"code": "SS"}],
                    "text": "SSN"
                },
                "value": "1234"
            }
        ],
        "address": [
            {
                "line": ["123 Main Street", "Apt 4B"],
                "city": "Boston",
                "state": "MA",
                "postalCode": "02101"
            }
        ],
        "telecom": [
            {"system": "phone", "value": "555-123-4567"},
            {"system": "email", "value": "john.smith@example.com"}
        ],
        "communication": [
            {
                "language": {
                    "coding": [{"code": "en", "display": "English"}]
                }
            }
        ],
        "maritalStatus": {
            "coding": [{"code": "M", "display": "Married"}]
        }
    }


@pytest.fixture
def sample_observation_resource():
    """Sample FHIR Observation resource."""
    return {
        "resourceType": "Observation",
        "id": "obs-456",
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "laboratory"
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "4548-4",
                    "display": "Hemoglobin A1c"
                }
            ],
            "text": "Hemoglobin A1c"
        },
        "subject": {"reference": "Patient/patient-123"},
        "encounter": {"reference": "Encounter/enc-789"},
        "effectiveDateTime": "2024-01-15T10:30:00Z",
        "issued": "2024-01-15T11:00:00Z",
        "performer": [
            {
                "reference": "Practitioner/prac-001",
                "display": "Dr. Jane Wilson"
            }
        ],
        "valueQuantity": {
            "value": 7.2,
            "unit": "%",
            "system": "http://unitsofmeasure.org",
            "code": "%"
        },
        "interpretation": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                        "code": "H",
                        "display": "High"
                    }
                ]
            }
        ],
        "referenceRange": [
            {
                "low": {"value": 4.0, "unit": "%"},
                "high": {"value": 5.6, "unit": "%"}
            }
        ],
        "note": [{"text": "Indicates poor glycemic control"}]
    }


@pytest.fixture
def sample_condition_resource():
    """Sample FHIR Condition resource."""
    return {
        "resourceType": "Condition",
        "id": "cond-789",
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active"
                }
            ]
        },
        "verificationStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    "code": "confirmed"
                }
            ]
        },
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                        "code": "problem-list-item"
                    }
                ]
            }
        ],
        "severity": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "24484000",
                    "display": "severe"
                }
            ]
        },
        "code": {
            "coding": [
                {
                    "system": "http://hl7.org/fhir/sid/icd-10-cm",
                    "code": "E11.9",
                    "display": "Type 2 diabetes mellitus without complications"
                }
            ],
            "text": "Type 2 Diabetes"
        },
        "subject": {"reference": "Patient/patient-123"},
        "encounter": {"reference": "Encounter/enc-789"},
        "onsetDateTime": "2020-03-15",
        "recordedDate": "2020-03-15",
        "recorder": {
            "reference": "Practitioner/prac-001",
            "display": "Dr. Jane Wilson"
        },
        "note": [{"text": "Patient managing with lifestyle changes and metformin"}]
    }


@pytest.fixture
def sample_medication_request_resource():
    """Sample FHIR MedicationRequest resource."""
    return {
        "resourceType": "MedicationRequest",
        "id": "medrx-001",
        "status": "active",
        "intent": "order",
        "priority": "routine",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": "860975",
                    "display": "Metformin 1000 MG"
                }
            ],
            "text": "Metformin 1000mg"
        },
        "subject": {"reference": "Patient/patient-123"},
        "encounter": {"reference": "Encounter/enc-789"},
        "authoredOn": "2024-01-10T09:00:00Z",
        "requester": {
            "reference": "Practitioner/prac-001",
            "display": "Dr. Jane Wilson"
        },
        "reasonCode": [
            {
                "coding": [
                    {
                        "code": "E11.9",
                        "display": "Type 2 diabetes"
                    }
                ]
            }
        ],
        "dosageInstruction": [
            {
                "text": "Take 1 tablet by mouth twice daily with meals",
                "route": {
                    "coding": [{"display": "oral"}]
                },
                "timing": {
                    "code": {
                        "coding": [{"code": "BID"}]
                    }
                },
                "doseAndRate": [
                    {
                        "doseQuantity": {
                            "value": 1000,
                            "unit": "mg"
                        }
                    }
                ]
            }
        ],
        "dispenseRequest": {
            "quantity": {"value": 60},
            "numberOfRepeatsAllowed": 5
        },
        "note": [{"text": "Take with food to minimize GI upset"}]
    }


@pytest.fixture
def sample_document_reference_resource():
    """Sample FHIR DocumentReference resource."""
    return {
        "resourceType": "DocumentReference",
        "id": "doc-001",
        "status": "current",
        "docStatus": "final",
        "type": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "11506-3",
                    "display": "Progress note"
                }
            ],
            "text": "Progress Note"
        },
        "subject": {"reference": "Patient/patient-123"},
        "date": "2024-01-15T14:30:00Z",
        "author": [
            {
                "reference": "Practitioner/prac-001",
                "display": "Dr. Jane Wilson"
            }
        ],
        "description": "Routine follow-up visit for diabetes management",
        "content": [
            {
                "attachment": {
                    "contentType": "text/plain",
                    "data": base64.b64encode(b"Patient visit notes: Blood sugar stable.").decode()
                }
            }
        ]
    }


@pytest.fixture
def sample_diagnostic_report_resource():
    """Sample FHIR DiagnosticReport resource."""
    return {
        "resourceType": "DiagnosticReport",
        "id": "report-001",
        "status": "final",
        "category": [
            {
                "coding": [{"code": "LAB", "display": "Laboratory"}]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "58410-2",
                    "display": "Complete Blood Count panel"
                }
            ],
            "text": "Complete Blood Count"
        },
        "subject": {"reference": "Patient/patient-123"},
        "encounter": {"reference": "Encounter/enc-789"},
        "effectiveDateTime": "2024-01-15T08:00:00Z",
        "issued": "2024-01-15T10:00:00Z",
        "performer": [
            {
                "reference": "Organization/lab-001",
                "display": "Quest Diagnostics"
            }
        ],
        "result": [
            {"reference": "Observation/obs-wbc"},
            {"reference": "Observation/obs-rbc"},
            {"reference": "Observation/obs-hgb"}
        ],
        "conclusion": "All values within normal limits"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestFHIRConfig:
    """Tests for FHIRConfig dataclass."""
    
    def test_config_creation(self, fhir_config):
        """Test FHIRConfig creation."""
        assert fhir_config.base_url == "https://test-fhir.example.com/api/FHIR/R4/"
        assert fhir_config.client_id == "test-client-id"
        assert fhir_config.timeout == 30
        assert fhir_config.max_retries == 3
    
    def test_config_to_dict_excludes_secrets(self, fhir_config):
        """Test that to_dict excludes sensitive information."""
        config_dict = fhir_config.to_dict()
        
        assert "base_url" in config_dict
        assert "client_id" in config_dict
        assert "client_secret" not in config_dict
        assert "access_token" not in config_dict
    
    def test_config_default_values(self):
        """Test default values."""
        config = FHIRConfig(
            base_url="https://test.com/",
            client_id="test"
        )
        
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_backoff_factor == 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# TEST AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthentication:
    """Tests for FHIR authentication."""
    
    def test_authenticate_success(self, fhir_config):
        """Test successful OAuth authentication."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "new-access-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "refresh_token": "new-refresh-token"
            }
            mock_post.return_value = mock_response
            
            with patch('phoenix_guardian.integrations.fhir_client.requests.Session'):
                client = FHIRClient(fhir_config)
                result = client.authenticate()
            
            assert result is True
            assert client.config.access_token == "new-access-token"
            assert client.config.refresh_token == "new-refresh-token"
    
    def test_authenticate_failure(self, fhir_config):
        """Test authentication failure."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Invalid credentials"
            mock_post.return_value = mock_response
            
            with patch('phoenix_guardian.integrations.fhir_client.requests.Session'):
                client = FHIRClient(fhir_config)
                
                with pytest.raises(FHIRAuthenticationError):
                    client.authenticate()
    
    def test_authenticate_no_token_url(self):
        """Test authentication without token URL configured."""
        config = FHIRConfig(
            base_url="https://test.com/",
            client_id="test"
        )
        
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session'):
            client = FHIRClient(config)
            result = client.authenticate()
        
        assert result is False
    
    def test_refresh_authentication_success(self, fhir_config):
        """Test successful token refresh."""
        fhir_config.refresh_token = "existing-refresh-token"
        
        with patch('phoenix_guardian.integrations.fhir_client.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "refreshed-token",
                "expires_in": 3600,
                "refresh_token": "new-refresh-token"
            }
            mock_post.return_value = mock_response
            
            with patch('phoenix_guardian.integrations.fhir_client.requests.Session'):
                client = FHIRClient(fhir_config)
                result = client.refresh_authentication()
            
            assert result is True
            assert client.config.access_token == "refreshed-token"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CONNECTION
# ═══════════════════════════════════════════════════════════════════════════════


class TestConnection:
    """Tests for FHIR server connection."""
    
    def test_test_connection_success(self, fhir_client):
        """Test successful connection test."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "CapabilityStatement",
            "status": "active"
        }
        fhir_client.session.request.return_value = mock_response
        
        result = fhir_client.test_connection()
        
        assert result is True
    
    def test_test_connection_failure(self, fhir_client):
        """Test failed connection test."""
        fhir_client.session.request.side_effect = Exception("Connection refused")
        
        result = fhir_client.test_connection()
        
        assert result is False
    
    def test_get_server_capabilities(self, fhir_client):
        """Test getting server capability statement."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "CapabilityStatement",
            "fhirVersion": "4.0.1",
            "format": ["json", "xml"]
        }
        fhir_client.session.request.return_value = mock_response
        
        capabilities = fhir_client.get_server_capabilities()
        
        assert capabilities["resourceType"] == "CapabilityStatement"
        assert capabilities["fhirVersion"] == "4.0.1"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST PATIENT OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestPatientOperations:
    """Tests for Patient CRUD operations."""
    
    def test_get_patient_success(self, fhir_client, sample_patient_resource):
        """Test successful patient retrieval."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = sample_patient_resource
        fhir_client.session.request.return_value = mock_response
        
        patient = fhir_client.get_patient("patient-123")
        
        assert patient is not None
        assert patient.id == "patient-123"
        assert patient.name == "John Michael Smith"
        assert patient.sex == "male"
        assert patient.birth_date == date(1980, 5, 15)
        assert patient.mrn == "MRN123456"
        assert patient.city == "Boston"
        assert patient.state == "MA"
        assert patient.phone == "555-123-4567"
        assert patient.email == "john.smith@example.com"
        assert patient.language == "English"
        assert patient.marital_status == "Married"
        assert patient.active is True
    
    def test_get_patient_not_found(self, fhir_client):
        """Test patient not found."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = "Patient not found"
        mock_response.json.return_value = {
            "resourceType": "OperationOutcome",
            "issue": [{"diagnostics": "Patient not found"}]
        }
        fhir_client.session.request.return_value = mock_response
        
        patient = fhir_client.get_patient("nonexistent")
        
        assert patient is None
    
    def test_search_patients(self, fhir_client, sample_patient_resource):
        """Test patient search."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": 1,
            "entry": [{"resource": sample_patient_resource}]
        }
        fhir_client.session.request.return_value = mock_response
        
        patients = fhir_client.search_patients(name="Smith")
        
        assert len(patients) == 1
        assert patients[0].name == "John Michael Smith"
    
    def test_patient_age_calculation(self, fhir_client, sample_patient_resource):
        """Test patient age calculation."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = sample_patient_resource
        fhir_client.session.request.return_value = mock_response
        
        patient = fhir_client.get_patient("patient-123")
        
        # Born 1980-05-15
        expected_age = date.today().year - 1980
        if (date.today().month, date.today().day) < (5, 15):
            expected_age -= 1
        
        assert patient.age == expected_age
    
    def test_patient_to_dict(self, fhir_client, sample_patient_resource):
        """Test patient to_dict method."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = sample_patient_resource
        fhir_client.session.request.return_value = mock_response
        
        patient = fhir_client.get_patient("patient-123")
        patient_dict = patient.to_dict()
        
        assert patient_dict["id"] == "patient-123"
        assert patient_dict["name"] == "John Michael Smith"
        assert patient_dict["birth_date"] == "1980-05-15"
        assert patient_dict["sex"] == "male"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST OBSERVATION OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestObservationOperations:
    """Tests for Observation CRUD operations."""
    
    def test_get_observation_success(self, fhir_client, sample_observation_resource):
        """Test successful observation retrieval."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = sample_observation_resource
        fhir_client.session.request.return_value = mock_response
        
        observation = fhir_client.get_observation("obs-456")
        
        assert observation is not None
        assert observation.id == "obs-456"
        assert observation.code == "4548-4"
        assert observation.display == "Hemoglobin A1c"
        assert observation.value == 7.2
        assert observation.unit == "%"
        assert observation.status == ObservationStatus.FINAL
        assert observation.category == ObservationCategory.LABORATORY
        assert observation.interpretation == "High"
        assert observation.reference_range_low == 4.0
        assert observation.reference_range_high == 5.6
    
    def test_get_observations_for_patient(self, fhir_client, sample_observation_resource):
        """Test getting observations for patient."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "Bundle",
            "type": "searchset",
            "entry": [{"resource": sample_observation_resource}]
        }
        fhir_client.session.request.return_value = mock_response
        
        observations = fhir_client.get_observations("patient-123")
        
        assert len(observations) == 1
        assert observations[0].code == "4548-4"
    
    def test_get_vital_signs(self, fhir_client):
        """Test getting vital signs."""
        bp_resource = {
            "resourceType": "Observation",
            "id": "bp-001",
            "status": "final",
            "category": [
                {"coding": [{"code": "vital-signs"}]}
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "85354-9",
                        "display": "Blood Pressure"
                    }
                ]
            },
            "subject": {"reference": "Patient/patient-123"},
            "effectiveDateTime": "2024-01-15T10:00:00Z",
            "component": [
                {
                    "code": {
                        "coding": [{"code": "8480-6"}]
                    },
                    "valueQuantity": {"value": 120, "unit": "mmHg"}
                },
                {
                    "code": {
                        "coding": [{"code": "8462-4"}]
                    },
                    "valueQuantity": {"value": 80, "unit": "mmHg"}
                }
            ]
        }
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "Bundle",
            "entry": [{"resource": bp_resource}]
        }
        fhir_client.session.request.return_value = mock_response
        
        vitals = fhir_client.get_vital_signs("patient-123")
        
        assert len(vitals) == 1
        assert vitals[0].component_systolic == 120
        assert vitals[0].component_diastolic == 80
    
    def test_get_lab_results(self, fhir_client, sample_observation_resource):
        """Test getting lab results."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "Bundle",
            "entry": [{"resource": sample_observation_resource}]
        }
        fhir_client.session.request.return_value = mock_response
        
        labs = fhir_client.get_lab_results("patient-123")
        
        assert len(labs) == 1
        assert labs[0].category == ObservationCategory.LABORATORY
    
    def test_create_observation(self, fhir_client):
        """Test creating observation."""
        observation = FHIRObservation(
            patient_id="patient-123",
            code="4548-4",
            display="Hemoglobin A1c",
            category=ObservationCategory.LABORATORY,
            value=6.8,
            unit="%",
            status=ObservationStatus.FINAL
        )
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "Observation",
            "id": "new-obs-123"
        }
        fhir_client.session.request.return_value = mock_response
        
        obs_id = fhir_client.create_observation(observation)
        
        assert obs_id == "new-obs-123"
    
    def test_create_blood_pressure_observation(self, fhir_client):
        """Test creating blood pressure observation with components."""
        observation = FHIRObservation(
            patient_id="patient-123",
            code="85354-9",
            display="Blood Pressure",
            category=ObservationCategory.VITAL_SIGNS,
            component_systolic=120,
            component_diastolic=80,
            status=ObservationStatus.FINAL
        )
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "Observation",
            "id": "bp-new-123"
        }
        fhir_client.session.request.return_value = mock_response
        
        obs_id = fhir_client.create_observation(observation)
        
        assert obs_id == "bp-new-123"
        
        # Verify the request was made with component structure
        call_args = fhir_client.session.request.call_args
        request_body = call_args[1]['json']
        assert 'component' in request_body
        assert len(request_body['component']) == 2
    
    def test_update_observation(self, fhir_client):
        """Test updating observation."""
        observation = FHIRObservation(
            id="obs-456",
            patient_id="patient-123",
            code="4548-4",
            display="Hemoglobin A1c",
            value=6.5,
            unit="%",
            status=ObservationStatus.AMENDED
        )
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"resourceType": "Observation", "id": "obs-456"}
        fhir_client.session.request.return_value = mock_response
        
        result = fhir_client.update_observation(observation)
        
        assert result is True
    
    def test_update_observation_without_id_raises_error(self, fhir_client):
        """Test that update without ID raises error."""
        observation = FHIRObservation(
            patient_id="patient-123",
            code="4548-4",
            value=6.5,
            unit="%"
        )
        
        with pytest.raises(FHIRValidationError):
            fhir_client.update_observation(observation)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CONDITION OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestConditionOperations:
    """Tests for Condition CRUD operations."""
    
    def test_get_condition_success(self, fhir_client, sample_condition_resource):
        """Test successful condition retrieval."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = sample_condition_resource
        fhir_client.session.request.return_value = mock_response
        
        condition = fhir_client.get_condition("cond-789")
        
        assert condition is not None
        assert condition.id == "cond-789"
        assert condition.code == "E11.9"
        assert condition.display == "Type 2 diabetes mellitus without complications"
        assert condition.clinical_status == ConditionClinicalStatus.ACTIVE
        assert condition.verification_status == ConditionVerificationStatus.CONFIRMED
        assert condition.severity == "severe"
        assert condition.category == "problem-list-item"
    
    def test_get_conditions_for_patient(self, fhir_client, sample_condition_resource):
        """Test getting conditions for patient."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "Bundle",
            "entry": [{"resource": sample_condition_resource}]
        }
        fhir_client.session.request.return_value = mock_response
        
        conditions = fhir_client.get_conditions("patient-123")
        
        assert len(conditions) == 1
        assert conditions[0].code == "E11.9"
    
    def test_get_active_conditions(self, fhir_client, sample_condition_resource):
        """Test getting active conditions."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "Bundle",
            "entry": [{"resource": sample_condition_resource}]
        }
        fhir_client.session.request.return_value = mock_response
        
        conditions = fhir_client.get_active_conditions("patient-123")
        
        assert len(conditions) == 1
        assert conditions[0].clinical_status == ConditionClinicalStatus.ACTIVE
    
    def test_create_condition(self, fhir_client):
        """Test creating condition."""
        condition = FHIRCondition(
            patient_id="patient-123",
            code="E11.9",
            display="Type 2 Diabetes",
            clinical_status=ConditionClinicalStatus.ACTIVE,
            verification_status=ConditionVerificationStatus.CONFIRMED
        )
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "Condition",
            "id": "new-cond-123"
        }
        fhir_client.session.request.return_value = mock_response
        
        cond_id = fhir_client.create_condition(condition)
        
        assert cond_id == "new-cond-123"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST MEDICATION REQUEST OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMedicationRequestOperations:
    """Tests for MedicationRequest CRUD operations."""
    
    def test_get_medication_success(self, fhir_client, sample_medication_request_resource):
        """Test successful medication retrieval."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = sample_medication_request_resource
        fhir_client.session.request.return_value = mock_response
        
        medication = fhir_client.get_medication("medrx-001")
        
        assert medication is not None
        assert medication.id == "medrx-001"
        assert medication.medication_code == "860975"
        assert medication.medication_display == "Metformin 1000 MG"
        assert medication.status == MedicationRequestStatus.ACTIVE
        assert medication.dosage_text == "Take 1 tablet by mouth twice daily with meals"
        assert medication.dosage_route == "oral"
        assert medication.dosage_frequency == "BID"
        assert medication.dosage_quantity == 1000
        assert medication.dosage_unit == "mg"
        assert medication.dispense_quantity == 60
        assert medication.refills_allowed == 5
    
    def test_get_medications_for_patient(self, fhir_client, sample_medication_request_resource):
        """Test getting medications for patient."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "Bundle",
            "entry": [{"resource": sample_medication_request_resource}]
        }
        fhir_client.session.request.return_value = mock_response
        
        medications = fhir_client.get_medications("patient-123")
        
        assert len(medications) == 1
        assert medications[0].medication_code == "860975"
    
    def test_get_active_medications(self, fhir_client, sample_medication_request_resource):
        """Test getting active medications."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "Bundle",
            "entry": [{"resource": sample_medication_request_resource}]
        }
        fhir_client.session.request.return_value = mock_response
        
        medications = fhir_client.get_active_medications("patient-123")
        
        assert len(medications) == 1
        assert medications[0].status == MedicationRequestStatus.ACTIVE
    
    def test_create_medication_request(self, fhir_client):
        """Test creating medication request."""
        medication = FHIRMedicationRequest(
            patient_id="patient-123",
            medication_code="860975",
            medication_display="Metformin 1000mg",
            dosage_text="Take twice daily",
            status=MedicationRequestStatus.ACTIVE
        )
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "MedicationRequest",
            "id": "new-medrx-123"
        }
        fhir_client.session.request.return_value = mock_response
        
        med_id = fhir_client.create_medication_request(medication)
        
        assert med_id == "new-medrx-123"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST DOCUMENT REFERENCE OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDocumentReferenceOperations:
    """Tests for DocumentReference CRUD operations."""
    
    def test_get_document_reference(self, fhir_client, sample_document_reference_resource):
        """Test successful document retrieval."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = sample_document_reference_resource
        fhir_client.session.request.return_value = mock_response
        
        document = fhir_client.get_document_reference("doc-001")
        
        assert document is not None
        assert document.id == "doc-001"
        assert document.document_type_code == "11506-3"
        assert document.document_type_display == "Progress note"
        assert document.status == DocumentReferenceStatus.CURRENT
        assert document.doc_status == "final"
        assert document.author_name == "Dr. Jane Wilson"
    
    def test_get_document_references_for_patient(self, fhir_client, sample_document_reference_resource):
        """Test getting documents for patient."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "Bundle",
            "entry": [{"resource": sample_document_reference_resource}]
        }
        fhir_client.session.request.return_value = mock_response
        
        documents = fhir_client.get_document_references("patient-123")
        
        assert len(documents) == 1
        assert documents[0].document_type_code == "11506-3"
    
    def test_create_document_reference(self, fhir_client):
        """Test creating document reference."""
        document = FHIRDocumentReference(
            patient_id="patient-123",
            document_type_code="11506-3",
            document_type_display="Progress Note",
            content="Patient visit notes: Condition improving.",
            content_type="text/plain",
            status=DocumentReferenceStatus.CURRENT
        )
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "DocumentReference",
            "id": "new-doc-123"
        }
        fhir_client.session.request.return_value = mock_response
        
        doc_id = fhir_client.create_document_reference(document)
        
        assert doc_id == "new-doc-123"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST DIAGNOSTIC REPORT OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDiagnosticReportOperations:
    """Tests for DiagnosticReport operations."""
    
    def test_get_diagnostic_report(self, fhir_client, sample_diagnostic_report_resource):
        """Test successful diagnostic report retrieval."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = sample_diagnostic_report_resource
        fhir_client.session.request.return_value = mock_response
        
        report = fhir_client.get_diagnostic_report("report-001")
        
        assert report is not None
        assert report.id == "report-001"
        assert report.code == "58410-2"
        assert report.display == "Complete Blood Count panel"
        assert report.category == "LAB"
        assert report.conclusion == "All values within normal limits"
        assert len(report.result_ids) == 3
    
    def test_get_diagnostic_reports_for_patient(self, fhir_client, sample_diagnostic_report_resource):
        """Test getting diagnostic reports for patient."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "resourceType": "Bundle",
            "entry": [{"resource": sample_diagnostic_report_resource}]
        }
        fhir_client.session.request.return_value = mock_response
        
        reports = fhir_client.get_diagnostic_reports("patient-123")
        
        assert len(reports) == 1
        assert reports[0].code == "58410-2"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_authentication_error_401(self, fhir_client):
        """Test 401 authentication error."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.json.return_value = {}
        fhir_client.session.request.return_value = mock_response
        
        with pytest.raises(FHIRAuthenticationError) as exc_info:
            fhir_client.get_patient("test")
        
        assert exc_info.value.status_code == 401
    
    def test_permission_error_403(self, fhir_client):
        """Test 403 permission error."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_response.json.return_value = {}
        fhir_client.session.request.return_value = mock_response
        
        with pytest.raises(FHIRPermissionError) as exc_info:
            fhir_client.get_patient("test")
        
        assert exc_info.value.status_code == 403
    
    def test_not_found_error_404(self, fhir_client):
        """Test 404 not found error handling."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_response.json.return_value = {
            "resourceType": "OperationOutcome",
            "issue": [{"diagnostics": "Resource not found"}]
        }
        fhir_client.session.request.return_value = mock_response
        
        # get_patient handles 404 gracefully
        patient = fhir_client.get_patient("nonexistent")
        assert patient is None
    
    def test_validation_error_400(self, fhir_client):
        """Test 400 validation error."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.json.return_value = {
            "resourceType": "OperationOutcome",
            "issue": [{"diagnostics": "Invalid resource format"}]
        }
        fhir_client.session.request.return_value = mock_response
        
        observation = FHIRObservation(patient_id="test", code="test")
        
        with pytest.raises(FHIRValidationError) as exc_info:
            fhir_client.create_observation(observation)
        
        assert exc_info.value.status_code == 400
    
    def test_server_error_500(self, fhir_client):
        """Test 500 server error."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json.return_value = {}
        fhir_client.session.request.return_value = mock_response
        
        with pytest.raises(FHIRServerError) as exc_info:
            fhir_client.get_patient("test")
        
        assert exc_info.value.status_code == 500
    
    def test_connection_error(self, fhir_client):
        """Test connection error."""
        import requests
        fhir_client.session.request.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        with pytest.raises(FHIRConnectionError):
            fhir_client.get_patient("test")
    
    def test_timeout_error(self, fhir_client):
        """Test timeout error."""
        import requests
        fhir_client.session.request.side_effect = requests.exceptions.Timeout("Request timed out")
        
        with pytest.raises(FHIRConnectionError):
            fhir_client.get_patient("test")
    
    def test_operation_outcome_parsing(self, fhir_client):
        """Test OperationOutcome error message parsing."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = "Error"
        mock_response.json.return_value = {
            "resourceType": "OperationOutcome",
            "issue": [
                {
                    "severity": "error",
                    "code": "invalid",
                    "diagnostics": "Patient reference is required"
                }
            ]
        }
        fhir_client.session.request.return_value = mock_response
        
        with pytest.raises(FHIRValidationError) as exc_info:
            observation = FHIRObservation(patient_id="", code="test")
            fhir_client.create_observation(observation)
        
        assert "Patient reference is required" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST BATCH OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestBatchOperations:
    """Tests for batch operations."""
    
    def test_get_patient_summary(self, fhir_client, sample_patient_resource, 
                                  sample_condition_resource, sample_medication_request_resource,
                                  sample_observation_resource):
        """Test getting patient summary."""
        # Mock responses for all API calls
        def mock_request(method, url, **kwargs):
            mock_resp = Mock()
            mock_resp.ok = True
            
            if "Patient/" in url and not "?" in url:
                mock_resp.json.return_value = sample_patient_resource
            elif "Condition" in url:
                mock_resp.json.return_value = {
                    "resourceType": "Bundle",
                    "entry": [{"resource": sample_condition_resource}]
                }
            elif "MedicationRequest" in url:
                mock_resp.json.return_value = {
                    "resourceType": "Bundle",
                    "entry": [{"resource": sample_medication_request_resource}]
                }
            elif "Observation" in url:
                mock_resp.json.return_value = {
                    "resourceType": "Bundle",
                    "entry": [{"resource": sample_observation_resource}]
                }
            
            return mock_resp
        
        fhir_client.session.request.side_effect = mock_request
        
        summary = fhir_client.get_patient_summary("patient-123")
        
        assert "patient" in summary
        assert "conditions" in summary
        assert "medications" in summary
        assert "vital_signs" in summary
        assert "lab_results" in summary
        
        assert summary["patient"]["name"] == "John Michael Smith"
        assert len(summary["conditions"]) == 1
        assert len(summary["medications"]) == 1
    
    def test_get_patient_summary_patient_not_found(self, fhir_client):
        """Test patient summary when patient not found."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_response.json.return_value = {}
        fhir_client.session.request.return_value = mock_response
        
        with pytest.raises(FHIRNotFoundError):
            fhir_client.get_patient_summary("nonexistent")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST ENUMS
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnums:
    """Tests for FHIR enums."""
    
    def test_observation_status_values(self):
        """Test ObservationStatus enum values."""
        assert ObservationStatus.FINAL.value == "final"
        assert ObservationStatus.PRELIMINARY.value == "preliminary"
        assert ObservationStatus.AMENDED.value == "amended"
        assert ObservationStatus.ENTERED_IN_ERROR.value == "entered-in-error"
    
    def test_observation_category_values(self):
        """Test ObservationCategory enum values."""
        assert ObservationCategory.VITAL_SIGNS.value == "vital-signs"
        assert ObservationCategory.LABORATORY.value == "laboratory"
        assert ObservationCategory.IMAGING.value == "imaging"
    
    def test_condition_clinical_status_values(self):
        """Test ConditionClinicalStatus enum values."""
        assert ConditionClinicalStatus.ACTIVE.value == "active"
        assert ConditionClinicalStatus.RESOLVED.value == "resolved"
        assert ConditionClinicalStatus.REMISSION.value == "remission"
    
    def test_medication_request_status_values(self):
        """Test MedicationRequestStatus enum values."""
        assert MedicationRequestStatus.ACTIVE.value == "active"
        assert MedicationRequestStatus.COMPLETED.value == "completed"
        assert MedicationRequestStatus.STOPPED.value == "stopped"
    
    def test_fhir_resource_type_values(self):
        """Test FHIRResourceType enum values."""
        assert FHIRResourceType.PATIENT.value == "Patient"
        assert FHIRResourceType.OBSERVATION.value == "Observation"
        assert FHIRResourceType.CONDITION.value == "Condition"
        assert FHIRResourceType.MEDICATION_REQUEST.value == "MedicationRequest"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST LOINC CODES
# ═══════════════════════════════════════════════════════════════════════════════


class TestLOINCCodes:
    """Tests for LOINC code constants."""
    
    def test_vital_signs_codes(self):
        """Test vital signs LOINC codes."""
        assert LOINCCodes.BLOOD_PRESSURE_SYSTOLIC == "8480-6"
        assert LOINCCodes.BLOOD_PRESSURE_DIASTOLIC == "8462-4"
        assert LOINCCodes.HEART_RATE == "8867-4"
        assert LOINCCodes.BODY_TEMPERATURE == "8310-5"
    
    def test_laboratory_codes(self):
        """Test laboratory LOINC codes."""
        assert LOINCCodes.GLUCOSE == "2345-7"
        assert LOINCCodes.HBA1C == "4548-4"
        assert LOINCCodes.CREATININE == "2160-0"
        assert LOINCCodes.HEMOGLOBIN == "718-7"
    
    def test_document_type_codes(self):
        """Test document type LOINC codes."""
        assert LOINCCodes.PROGRESS_NOTE == "11506-3"
        assert LOINCCodes.DISCHARGE_SUMMARY == "18842-5"
        assert LOINCCodes.HISTORY_AND_PHYSICAL == "34117-2"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST DATACLASS METHODS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDataclassMethods:
    """Tests for dataclass methods."""
    
    def test_observation_to_dict(self):
        """Test FHIRObservation to_dict method."""
        observation = FHIRObservation(
            id="obs-1",
            patient_id="patient-1",
            code="4548-4",
            display="HbA1c",
            value=7.0,
            unit="%",
            status=ObservationStatus.FINAL,
            category=ObservationCategory.LABORATORY
        )
        
        obs_dict = observation.to_dict()
        
        assert obs_dict["id"] == "obs-1"
        assert obs_dict["code"] == "4548-4"
        assert obs_dict["value"] == 7.0
        assert obs_dict["status"] == "final"
        assert obs_dict["category"] == "laboratory"
    
    def test_condition_to_dict(self):
        """Test FHIRCondition to_dict method."""
        condition = FHIRCondition(
            id="cond-1",
            patient_id="patient-1",
            code="E11.9",
            display="Type 2 Diabetes",
            clinical_status=ConditionClinicalStatus.ACTIVE
        )
        
        cond_dict = condition.to_dict()
        
        assert cond_dict["id"] == "cond-1"
        assert cond_dict["code"] == "E11.9"
        assert cond_dict["clinical_status"] == "active"
    
    def test_medication_to_dict(self):
        """Test FHIRMedicationRequest to_dict method."""
        medication = FHIRMedicationRequest(
            id="med-1",
            patient_id="patient-1",
            medication_code="860975",
            medication_display="Metformin",
            status=MedicationRequestStatus.ACTIVE
        )
        
        med_dict = medication.to_dict()
        
        assert med_dict["id"] == "med-1"
        assert med_dict["medication_code"] == "860975"
        assert med_dict["status"] == "active"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CONTEXT MANAGER
# ═══════════════════════════════════════════════════════════════════════════════


class TestContextManager:
    """Tests for context manager functionality."""
    
    def test_context_manager_closes_session(self, fhir_config):
        """Test that context manager closes session."""
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            with FHIRClient(fhir_config) as client:
                assert client is not None
            
            mock_session.close.assert_called_once()
    
    def test_close_method(self, fhir_client):
        """Test explicit close method."""
        fhir_client.close()
        fhir_client.session.close.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# TEST URL BUILDING
# ═══════════════════════════════════════════════════════════════════════════════


class TestURLBuilding:
    """Tests for URL building."""
    
    def test_build_url_with_id(self, fhir_client):
        """Test URL building with resource ID."""
        url = fhir_client._build_url("Patient", "123")
        assert url == "https://test-fhir.example.com/api/FHIR/R4/Patient/123"
    
    def test_build_url_without_id(self, fhir_client):
        """Test URL building without resource ID."""
        url = fhir_client._build_url("Patient")
        assert url == "https://test-fhir.example.com/api/FHIR/R4/Patient"
    
    def test_base_url_trailing_slash(self):
        """Test that base URL gets trailing slash if missing."""
        config = FHIRConfig(
            base_url="https://test.com/api/FHIR/R4",  # No trailing slash
            client_id="test"
        )
        
        with patch('phoenix_guardian.integrations.fhir_client.requests.Session'):
            client = FHIRClient(config)
        
        assert client.config.base_url.endswith('/')


# ═══════════════════════════════════════════════════════════════════════════════
# TEST PERFORMANCE
# ═══════════════════════════════════════════════════════════════════════════════


class TestPerformance:
    """Tests for performance requirements."""
    
    def test_api_call_under_2_seconds(self, fhir_client, sample_patient_resource):
        """Test that API calls complete under 2 seconds."""
        import time
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = sample_patient_resource
        fhir_client.session.request.return_value = mock_response
        
        start = time.time()
        patient = fhir_client.get_patient("patient-123")
        elapsed = time.time() - start
        
        assert elapsed < 2.0
        assert patient is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
