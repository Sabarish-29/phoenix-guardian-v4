"""
Test fixtures for Cerner connector tests.

This module provides sample data for Cerner integration testing.
"""

# Cerner Sandbox Test Patients
SAMPLE_CERNER_PATIENTS = {
    "smart_nancy": {
        "resourceType": "Patient",
        "id": "12724066",
        "name": [{"use": "official", "family": "Smart", "given": ["Nancy"]}],
        "gender": "female",
        "birthDate": "1980-08-11",
        "identifier": [
            {
                "use": "usual",
                "type": {"coding": [{"code": "MR"}]},
                "system": "urn:oid:2.16.840.1.113883.6.1000",
                "value": "MRN12724066"
            }
        ]
    },
    "smart_joe": {
        "resourceType": "Patient",
        "id": "12742400",
        "name": [{"use": "official", "family": "Smart", "given": ["Joe"]}],
        "gender": "male",
        "birthDate": "1976-04-29",
        "identifier": [
            {
                "use": "usual",
                "type": {"coding": [{"code": "MR"}]},
                "system": "urn:oid:2.16.840.1.113883.6.1000",
                "value": "MRN12742400"
            }
        ]
    },
    "smart_timmy": {
        "resourceType": "Patient",
        "id": "12742633",
        "name": [{"use": "official", "family": "Smart", "given": ["Timmy"]}],
        "gender": "male",
        "birthDate": "2012-05-03",
        "identifier": [
            {
                "use": "usual",
                "type": {"coding": [{"code": "MR"}]},
                "system": "urn:oid:2.16.840.1.113883.6.1000",
                "value": "MRN12742633"
            }
        ]
    }
}

# Sample Cerner observation data
SAMPLE_CERNER_OBSERVATIONS = {
    "blood_pressure": {
        "resourceType": "Observation",
        "id": "bp-123",
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "vital-signs",
                        "display": "Vital Signs"
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "85354-9",
                    "display": "Blood pressure panel"
                }
            ]
        },
        "subject": {"reference": "Patient/12724066"},
        "effectiveDateTime": "2024-01-15T10:30:00Z",
        "component": [
            {
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic"}]
                },
                "valueQuantity": {"value": 120, "unit": "mmHg"}
            },
            {
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic"}]
                },
                "valueQuantity": {"value": 80, "unit": "mmHg"}
            }
        ]
    },
    "heart_rate": {
        "resourceType": "Observation",
        "id": "hr-456",
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "vital-signs",
                        "display": "Vital Signs"
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "8867-4",
                    "display": "Heart rate"
                }
            ]
        },
        "subject": {"reference": "Patient/12724066"},
        "effectiveDateTime": "2024-01-15T10:30:00Z",
        "valueQuantity": {"value": 72, "unit": "/min"}
    },
    "hemoglobin_a1c": {
        "resourceType": "Observation",
        "id": "lab-789",
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "laboratory",
                        "display": "Laboratory"
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
            ]
        },
        "subject": {"reference": "Patient/12724066"},
        "effectiveDateTime": "2024-01-10T08:00:00Z",
        "valueQuantity": {"value": 6.5, "unit": "%"}
    }
}

# Sample Cerner conditions
SAMPLE_CERNER_CONDITIONS = {
    "hypertension": {
        "resourceType": "Condition",
        "id": "cond-001",
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
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "38341003",
                    "display": "Hypertensive disorder"
                }
            ]
        },
        "subject": {"reference": "Patient/12724066"},
        "onsetDateTime": "2020-06-15"
    },
    "diabetes": {
        "resourceType": "Condition",
        "id": "cond-002",
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
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "44054006",
                    "display": "Type 2 diabetes mellitus"
                }
            ]
        },
        "subject": {"reference": "Patient/12724066"},
        "onsetDateTime": "2019-03-20"
    }
}

# Sample Cerner medication requests
SAMPLE_CERNER_MEDICATIONS = {
    "lisinopril": {
        "resourceType": "MedicationRequest",
        "id": "med-001",
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": "314076",
                    "display": "Lisinopril 10 MG Oral Tablet"
                }
            ]
        },
        "subject": {"reference": "Patient/12724066"},
        "authoredOn": "2024-01-01",
        "dosageInstruction": [
            {
                "text": "Take 1 tablet by mouth daily",
                "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d"}},
                "doseAndRate": [
                    {"doseQuantity": {"value": 10, "unit": "mg"}}
                ]
            }
        ]
    },
    "metformin": {
        "resourceType": "MedicationRequest",
        "id": "med-002",
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": "860974",
                    "display": "Metformin 500 MG Oral Tablet"
                }
            ]
        },
        "subject": {"reference": "Patient/12724066"},
        "authoredOn": "2024-01-01",
        "dosageInstruction": [
            {
                "text": "Take 1 tablet by mouth twice daily with meals",
                "timing": {"repeat": {"frequency": 2, "period": 1, "periodUnit": "d"}},
                "doseAndRate": [
                    {"doseQuantity": {"value": 500, "unit": "mg"}}
                ]
            }
        ]
    }
}

# Sample Cerner capability statement
SAMPLE_CERNER_CAPABILITY_STATEMENT = {
    "resourceType": "CapabilityStatement",
    "status": "active",
    "date": "2024-01-01",
    "publisher": "Cerner Corporation",
    "kind": "instance",
    "software": {
        "name": "Cerner Millennium",
        "version": "2024.01"
    },
    "implementation": {
        "description": "Cerner FHIR R4 Implementation"
    },
    "fhirVersion": "4.0.1",
    "format": ["json", "xml"],
    "rest": [
        {
            "mode": "server",
            "resource": [
                {
                    "type": "Patient",
                    "interaction": [
                        {"code": "read"},
                        {"code": "search-type"}
                    ],
                    "searchParam": [
                        {"name": "identifier", "type": "token"},
                        {"name": "family", "type": "string"},
                        {"name": "given", "type": "string"},
                        {"name": "birthdate", "type": "date"}
                    ]
                },
                {
                    "type": "Observation",
                    "interaction": [
                        {"code": "read"},
                        {"code": "search-type"}
                    ],
                    "searchParam": [
                        {"name": "patient", "type": "reference"},
                        {"name": "category", "type": "token"},
                        {"name": "code", "type": "token"}
                    ]
                },
                {
                    "type": "Condition",
                    "interaction": [
                        {"code": "read"},
                        {"code": "search-type"}
                    ],
                    "searchParam": [
                        {"name": "patient", "type": "reference"},
                        {"name": "clinical-status", "type": "token"}
                    ]
                },
                {
                    "type": "MedicationRequest",
                    "interaction": [
                        {"code": "read"},
                        {"code": "search-type"}
                    ],
                    "searchParam": [
                        {"name": "patient", "type": "reference"},
                        {"name": "status", "type": "token"}
                    ]
                },
                {"type": "DocumentReference"},
                {"type": "DiagnosticReport"},
                {"type": "Encounter"},
                {"type": "Practitioner"},
                {"type": "Organization"},
                {"type": "AllergyIntolerance"},
                {"type": "Immunization"},
                {"type": "Procedure"}
            ]
        }
    ]
}

# Sample Cerner token response
SAMPLE_CERNER_TOKEN_RESPONSE = {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.example-cerner-token",
    "token_type": "Bearer",
    "expires_in": 570,
    "scope": "system/Patient.read system/Observation.read system/Condition.read system/MedicationRequest.read"
}

# Sample patient search bundle
SAMPLE_PATIENT_SEARCH_BUNDLE = {
    "resourceType": "Bundle",
    "type": "searchset",
    "total": 1,
    "entry": [
        {
            "fullUrl": "https://fhir-open.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d/Patient/12724066",
            "resource": SAMPLE_CERNER_PATIENTS["smart_nancy"]
        }
    ]
}

# Sample observation search bundle
SAMPLE_OBSERVATION_SEARCH_BUNDLE = {
    "resourceType": "Bundle",
    "type": "searchset",
    "total": 3,
    "entry": [
        {
            "fullUrl": f"https://fhir-open.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d/Observation/{obs['id']}",
            "resource": obs
        }
        for obs in SAMPLE_CERNER_OBSERVATIONS.values()
    ]
}

# Cerner-specific error responses
SAMPLE_CERNER_ERRORS = {
    "unauthorized": {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "login",
                "details": {"text": "Invalid or expired access token"}
            }
        ]
    },
    "not_found": {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "not-found",
                "details": {"text": "Resource not found"}
            }
        ]
    },
    "invalid_request": {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "invalid",
                "details": {"text": "Invalid request parameters"}
            }
        ]
    }
}
