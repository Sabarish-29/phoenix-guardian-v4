"""
Mock FHIR R4 server for demonstrations.

This server provides realistic FHIR R4 resources for testing and demo purposes.
It simulates an EHR system with patients, encounters, and observations.

Usage:
    python scripts/mock_fhir_server.py
    
The server runs on port 8001 by default.
API docs available at: http://localhost:8001/docs
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uvicorn

app = FastAPI(
    title="Mock FHIR R4 Server",
    description="Demo FHIR R4 server for Phoenix Guardian integration testing",
    version="1.0.0"
)

# Enable CORS for frontend testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_current_timestamp() -> str:
    """Return current UTC timestamp in FHIR format."""
    return datetime.utcnow().isoformat() + "Z"


# Mock patient data (FHIR R4 format)
MOCK_PATIENTS: Dict[str, Dict[str, Any]] = {
    "patient-001": {
        "resourceType": "Patient",
        "id": "patient-001",
        "meta": {
            "versionId": "1",
            "lastUpdated": "2024-01-15T10:00:00Z"
        },
        "identifier": [
            {
                "system": "http://hospital.example.org/mrn",
                "value": "12345"
            }
        ],
        "active": True,
        "name": [
            {
                "use": "official",
                "family": "Doe",
                "given": ["John", "A."]
            }
        ],
        "telecom": [
            {
                "system": "phone",
                "value": "555-1234",
                "use": "home"
            },
            {
                "system": "email",
                "value": "john.doe@example.com"
            }
        ],
        "gender": "male",
        "birthDate": "1975-05-15",
        "address": [
            {
                "use": "home",
                "line": ["123 Main St"],
                "city": "Springfield",
                "state": "IL",
                "postalCode": "62701"
            }
        ]
    },
    "patient-002": {
        "resourceType": "Patient",
        "id": "patient-002",
        "meta": {
            "versionId": "1",
            "lastUpdated": "2024-02-20T14:30:00Z"
        },
        "identifier": [
            {
                "system": "http://hospital.example.org/mrn",
                "value": "67890"
            }
        ],
        "active": True,
        "name": [
            {
                "use": "official",
                "family": "Smith",
                "given": ["Jane", "Marie"]
            }
        ],
        "telecom": [
            {
                "system": "phone",
                "value": "555-5678",
                "use": "mobile"
            },
            {
                "system": "email",
                "value": "jane.smith@example.com"
            }
        ],
        "gender": "female",
        "birthDate": "1982-08-22",
        "address": [
            {
                "use": "home",
                "line": ["456 Oak Ave"],
                "city": "Chicago",
                "state": "IL",
                "postalCode": "60601"
            }
        ]
    },
    "patient-003": {
        "resourceType": "Patient",
        "id": "patient-003",
        "meta": {
            "versionId": "2",
            "lastUpdated": "2024-03-10T09:15:00Z"
        },
        "identifier": [
            {
                "system": "http://hospital.example.org/mrn",
                "value": "11111"
            }
        ],
        "active": True,
        "name": [
            {
                "use": "official",
                "family": "Johnson",
                "given": ["Robert"]
            }
        ],
        "gender": "male",
        "birthDate": "1948-11-03",
        "address": [
            {
                "use": "home",
                "line": ["789 Elm St"],
                "city": "Springfield",
                "state": "IL",
                "postalCode": "62702"
            }
        ]
    }
}

# Mock encounters
MOCK_ENCOUNTERS: Dict[str, Dict[str, Any]] = {
    "encounter-001": {
        "resourceType": "Encounter",
        "id": "encounter-001",
        "meta": {
            "versionId": "1",
            "lastUpdated": get_current_timestamp()
        },
        "status": "in-progress",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "IMP",
            "display": "inpatient encounter"
        },
        "type": [
            {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "183452005",
                        "display": "Emergency hospital admission"
                    }
                ]
            }
        ],
        "subject": {"reference": "Patient/patient-001"},
        "participant": [
            {
                "type": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                                "code": "ATND",
                                "display": "attender"
                            }
                        ]
                    }
                ],
                "individual": {"reference": "Practitioner/dr-smith", "display": "Dr. Sarah Smith"}
            }
        ],
        "period": {
            "start": (datetime.utcnow() - timedelta(hours=2)).isoformat() + "Z"
        },
        "reasonCode": [
            {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "233604007",
                        "display": "Pneumonia"
                    }
                ],
                "text": "Community-acquired pneumonia"
            }
        ],
        "hospitalization": {
            "admitSource": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/admit-source",
                        "code": "emd",
                        "display": "From accident/emergency department"
                    }
                ]
            }
        }
    },
    "encounter-002": {
        "resourceType": "Encounter",
        "id": "encounter-002",
        "meta": {
            "versionId": "1",
            "lastUpdated": get_current_timestamp()
        },
        "status": "finished",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory"
        },
        "type": [
            {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "270427003",
                        "display": "Patient-initiated encounter"
                    }
                ]
            }
        ],
        "subject": {"reference": "Patient/patient-002"},
        "participant": [
            {
                "individual": {"reference": "Practitioner/dr-jones", "display": "Dr. Michael Jones"}
            }
        ],
        "period": {
            "start": (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z",
            "end": (datetime.utcnow() - timedelta(days=1, hours=-1)).isoformat() + "Z"
        },
        "reasonCode": [
            {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "25064002",
                        "display": "Headache"
                    }
                ],
                "text": "Chronic migraine follow-up"
            }
        ]
    },
    "encounter-003": {
        "resourceType": "Encounter",
        "id": "encounter-003",
        "meta": {
            "versionId": "1",
            "lastUpdated": get_current_timestamp()
        },
        "status": "in-progress",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "IMP",
            "display": "inpatient encounter"
        },
        "subject": {"reference": "Patient/patient-003"},
        "period": {
            "start": (datetime.utcnow() - timedelta(days=3)).isoformat() + "Z"
        },
        "reasonCode": [
            {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "84114007",
                        "display": "Heart failure"
                    }
                ],
                "text": "Acute decompensated heart failure"
            }
        ]
    }
}

# Mock observations (vitals, labs)
MOCK_OBSERVATIONS: Dict[str, Dict[str, Any]] = {
    "obs-001": {
        "resourceType": "Observation",
        "id": "obs-001",
        "meta": {
            "versionId": "1",
            "lastUpdated": get_current_timestamp()
        },
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
                    "code": "8310-5",
                    "display": "Body temperature"
                }
            ],
            "text": "Body Temperature"
        },
        "subject": {"reference": "Patient/patient-001"},
        "encounter": {"reference": "Encounter/encounter-001"},
        "effectiveDateTime": datetime.utcnow().isoformat() + "Z",
        "valueQuantity": {
            "value": 101.2,
            "unit": "°F",
            "system": "http://unitsofmeasure.org",
            "code": "[degF]"
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
        ]
    },
    "obs-002": {
        "resourceType": "Observation",
        "id": "obs-002",
        "meta": {
            "versionId": "1",
            "lastUpdated": get_current_timestamp()
        },
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
            ],
            "text": "Blood Pressure"
        },
        "subject": {"reference": "Patient/patient-001"},
        "encounter": {"reference": "Encounter/encounter-001"},
        "effectiveDateTime": datetime.utcnow().isoformat() + "Z",
        "component": [
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "8480-6",
                            "display": "Systolic blood pressure"
                        }
                    ]
                },
                "valueQuantity": {
                    "value": 120,
                    "unit": "mmHg",
                    "system": "http://unitsofmeasure.org",
                    "code": "mm[Hg]"
                }
            },
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "8462-4",
                            "display": "Diastolic blood pressure"
                        }
                    ]
                },
                "valueQuantity": {
                    "value": 80,
                    "unit": "mmHg",
                    "system": "http://unitsofmeasure.org",
                    "code": "mm[Hg]"
                }
            }
        ]
    },
    "obs-003": {
        "resourceType": "Observation",
        "id": "obs-003",
        "meta": {
            "versionId": "1",
            "lastUpdated": get_current_timestamp()
        },
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
            ],
            "text": "Heart Rate"
        },
        "subject": {"reference": "Patient/patient-001"},
        "encounter": {"reference": "Encounter/encounter-001"},
        "effectiveDateTime": datetime.utcnow().isoformat() + "Z",
        "valueQuantity": {
            "value": 88,
            "unit": "beats/minute",
            "system": "http://unitsofmeasure.org",
            "code": "/min"
        }
    },
    "obs-004": {
        "resourceType": "Observation",
        "id": "obs-004",
        "meta": {
            "versionId": "1",
            "lastUpdated": get_current_timestamp()
        },
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
                    "code": "9279-1",
                    "display": "Respiratory rate"
                }
            ],
            "text": "Respiratory Rate"
        },
        "subject": {"reference": "Patient/patient-001"},
        "encounter": {"reference": "Encounter/encounter-001"},
        "effectiveDateTime": datetime.utcnow().isoformat() + "Z",
        "valueQuantity": {
            "value": 18,
            "unit": "breaths/minute",
            "system": "http://unitsofmeasure.org",
            "code": "/min"
        }
    },
    "obs-005": {
        "resourceType": "Observation",
        "id": "obs-005",
        "meta": {
            "versionId": "1",
            "lastUpdated": get_current_timestamp()
        },
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
                    "code": "6690-2",
                    "display": "Leukocytes [#/volume] in Blood"
                }
            ],
            "text": "White Blood Cell Count"
        },
        "subject": {"reference": "Patient/patient-001"},
        "encounter": {"reference": "Encounter/encounter-001"},
        "effectiveDateTime": datetime.utcnow().isoformat() + "Z",
        "valueQuantity": {
            "value": 15.2,
            "unit": "10*3/uL",
            "system": "http://unitsofmeasure.org",
            "code": "10*3/uL"
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
                "low": {"value": 4.5, "unit": "10*3/uL"},
                "high": {"value": 11.0, "unit": "10*3/uL"}
            }
        ]
    }
}

# Mock conditions
MOCK_CONDITIONS: Dict[str, Dict[str, Any]] = {
    "condition-001": {
        "resourceType": "Condition",
        "id": "condition-001",
        "meta": {
            "versionId": "1",
            "lastUpdated": get_current_timestamp()
        },
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
                        "code": "encounter-diagnosis"
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "233604007",
                    "display": "Pneumonia"
                },
                {
                    "system": "http://hl7.org/fhir/sid/icd-10-cm",
                    "code": "J18.9",
                    "display": "Pneumonia, unspecified organism"
                }
            ],
            "text": "Community-acquired pneumonia"
        },
        "subject": {"reference": "Patient/patient-001"},
        "encounter": {"reference": "Encounter/encounter-001"},
        "onsetDateTime": (datetime.utcnow() - timedelta(days=3)).isoformat() + "Z"
    }
}

# Mock medication requests
MOCK_MEDICATION_REQUESTS: Dict[str, Dict[str, Any]] = {
    "medrx-001": {
        "resourceType": "MedicationRequest",
        "id": "medrx-001",
        "meta": {
            "versionId": "1",
            "lastUpdated": get_current_timestamp()
        },
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": "197696",
                    "display": "Azithromycin 250 MG Oral Tablet"
                }
            ],
            "text": "Azithromycin 250mg"
        },
        "subject": {"reference": "Patient/patient-001"},
        "encounter": {"reference": "Encounter/encounter-001"},
        "authoredOn": datetime.utcnow().isoformat() + "Z",
        "requester": {"reference": "Practitioner/dr-smith", "display": "Dr. Sarah Smith"},
        "dosageInstruction": [
            {
                "text": "Take 2 tablets on day 1, then 1 tablet daily for 4 days",
                "timing": {
                    "repeat": {
                        "frequency": 1,
                        "period": 1,
                        "periodUnit": "d"
                    }
                },
                "doseAndRate": [
                    {
                        "doseQuantity": {
                            "value": 1,
                            "unit": "tablet"
                        }
                    }
                ]
            }
        ]
    }
}


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """FHIR server capability statement (metadata)."""
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": get_current_timestamp(),
        "kind": "instance",
        "software": {
            "name": "Phoenix Guardian Mock FHIR Server",
            "version": "1.0.0"
        },
        "implementation": {
            "description": "Mock FHIR R4 server for demonstration",
            "url": "http://localhost:8001"
        },
        "fhirVersion": "4.0.1",
        "format": ["json"],
        "rest": [
            {
                "mode": "server",
                "resource": [
                    {"type": "Patient", "interaction": [{"code": "read"}, {"code": "search-type"}]},
                    {"type": "Encounter", "interaction": [{"code": "read"}, {"code": "search-type"}]},
                    {"type": "Observation", "interaction": [{"code": "read"}, {"code": "search-type"}]},
                    {"type": "Condition", "interaction": [{"code": "read"}, {"code": "search-type"}]},
                    {"type": "MedicationRequest", "interaction": [{"code": "read"}, {"code": "search-type"}]}
                ]
            }
        ]
    }


@app.get("/metadata")
async def metadata():
    """FHIR capability statement (alias for root)."""
    return await root()


# Patient endpoints
@app.get("/Patient/{patient_id}")
async def get_patient(patient_id: str):
    """Get patient by ID (FHIR R4)."""
    if patient_id not in MOCK_PATIENTS:
        raise HTTPException(
            status_code=404, 
            detail={
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "not-found",
                        "diagnostics": f"Patient/{patient_id} not found"
                    }
                ]
            }
        )
    return MOCK_PATIENTS[patient_id]


@app.get("/Patient")
async def search_patients(
    family: Optional[str] = Query(None, description="Family name"),
    given: Optional[str] = Query(None, description="Given name"),
    identifier: Optional[str] = Query(None, description="Patient identifier")
):
    """Search patients (FHIR R4)."""
    results = list(MOCK_PATIENTS.values())
    
    if family:
        results = [
            p for p in results 
            if any(family.lower() in n.get("family", "").lower() for n in p.get("name", []))
        ]
    
    if given:
        results = [
            p for p in results 
            if any(
                any(given.lower() in g.lower() for g in n.get("given", []))
                for n in p.get("name", [])
            )
        ]
    
    if identifier:
        results = [
            p for p in results 
            if any(identifier in i.get("value", "") for i in p.get("identifier", []))
        ]
    
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(results),
        "entry": [{"resource": p, "fullUrl": f"Patient/{p['id']}"} for p in results]
    }


# Encounter endpoints
@app.get("/Encounter/{encounter_id}")
async def get_encounter(encounter_id: str):
    """Get encounter by ID (FHIR R4)."""
    if encounter_id not in MOCK_ENCOUNTERS:
        raise HTTPException(
            status_code=404, 
            detail={
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "not-found",
                        "diagnostics": f"Encounter/{encounter_id} not found"
                    }
                ]
            }
        )
    return MOCK_ENCOUNTERS[encounter_id]


@app.get("/Encounter")
async def search_encounters(
    patient: Optional[str] = Query(None, description="Patient reference"),
    status: Optional[str] = Query(None, description="Encounter status")
):
    """Search encounters (FHIR R4)."""
    results = list(MOCK_ENCOUNTERS.values())
    
    if patient:
        patient_ref = f"Patient/{patient}" if not patient.startswith("Patient/") else patient
        results = [e for e in results if e.get("subject", {}).get("reference") == patient_ref]
    
    if status:
        results = [e for e in results if e.get("status") == status]
    
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(results),
        "entry": [{"resource": e, "fullUrl": f"Encounter/{e['id']}"} for e in results]
    }


@app.get("/Patient/{patient_id}/Encounter")
async def get_patient_encounters(patient_id: str):
    """Get all encounters for a patient."""
    patient_ref = f"Patient/{patient_id}"
    encounters = [
        enc for enc in MOCK_ENCOUNTERS.values()
        if enc.get("subject", {}).get("reference") == patient_ref
    ]
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(encounters),
        "entry": [{"resource": enc, "fullUrl": f"Encounter/{enc['id']}"} for enc in encounters]
    }


# Observation endpoints
@app.get("/Observation/{observation_id}")
async def get_observation(observation_id: str):
    """Get observation by ID (FHIR R4)."""
    if observation_id not in MOCK_OBSERVATIONS:
        raise HTTPException(
            status_code=404, 
            detail={
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "not-found",
                        "diagnostics": f"Observation/{observation_id} not found"
                    }
                ]
            }
        )
    return MOCK_OBSERVATIONS[observation_id]


@app.get("/Observation")
async def search_observations(
    patient: Optional[str] = Query(None, description="Patient reference"),
    encounter: Optional[str] = Query(None, description="Encounter reference"),
    category: Optional[str] = Query(None, description="Observation category")
):
    """Search observations (FHIR R4)."""
    results = list(MOCK_OBSERVATIONS.values())
    
    if patient:
        patient_ref = f"Patient/{patient}" if not patient.startswith("Patient/") else patient
        results = [o for o in results if o.get("subject", {}).get("reference") == patient_ref]
    
    if encounter:
        enc_ref = f"Encounter/{encounter}" if not encounter.startswith("Encounter/") else encounter
        results = [o for o in results if o.get("encounter", {}).get("reference") == enc_ref]
    
    if category:
        results = [
            o for o in results 
            if any(
                any(c.get("code") == category for c in cat.get("coding", []))
                for cat in o.get("category", [])
            )
        ]
    
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(results),
        "entry": [{"resource": o, "fullUrl": f"Observation/{o['id']}"} for o in results]
    }


@app.get("/Patient/{patient_id}/Observation")
async def get_patient_observations(patient_id: str, category: Optional[str] = None):
    """Get all observations for a patient."""
    patient_ref = f"Patient/{patient_id}"
    results = [
        obs for obs in MOCK_OBSERVATIONS.values()
        if obs.get("subject", {}).get("reference") == patient_ref
    ]
    
    if category:
        results = [
            o for o in results 
            if any(
                any(c.get("code") == category for c in cat.get("coding", []))
                for cat in o.get("category", [])
            )
        ]
    
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(results),
        "entry": [{"resource": obs, "fullUrl": f"Observation/{obs['id']}"} for obs in results]
    }


# Condition endpoints
@app.get("/Condition/{condition_id}")
async def get_condition(condition_id: str):
    """Get condition by ID (FHIR R4)."""
    if condition_id not in MOCK_CONDITIONS:
        raise HTTPException(
            status_code=404, 
            detail={
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "not-found",
                        "diagnostics": f"Condition/{condition_id} not found"
                    }
                ]
            }
        )
    return MOCK_CONDITIONS[condition_id]


@app.get("/Condition")
async def search_conditions(
    patient: Optional[str] = Query(None, description="Patient reference"),
    encounter: Optional[str] = Query(None, description="Encounter reference")
):
    """Search conditions (FHIR R4)."""
    results = list(MOCK_CONDITIONS.values())
    
    if patient:
        patient_ref = f"Patient/{patient}" if not patient.startswith("Patient/") else patient
        results = [c for c in results if c.get("subject", {}).get("reference") == patient_ref]
    
    if encounter:
        enc_ref = f"Encounter/{encounter}" if not encounter.startswith("Encounter/") else encounter
        results = [c for c in results if c.get("encounter", {}).get("reference") == enc_ref]
    
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(results),
        "entry": [{"resource": c, "fullUrl": f"Condition/{c['id']}"} for c in results]
    }


# MedicationRequest endpoints
@app.get("/MedicationRequest/{medrx_id}")
async def get_medication_request(medrx_id: str):
    """Get medication request by ID (FHIR R4)."""
    if medrx_id not in MOCK_MEDICATION_REQUESTS:
        raise HTTPException(
            status_code=404, 
            detail={
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "not-found",
                        "diagnostics": f"MedicationRequest/{medrx_id} not found"
                    }
                ]
            }
        )
    return MOCK_MEDICATION_REQUESTS[medrx_id]


@app.get("/MedicationRequest")
async def search_medication_requests(
    patient: Optional[str] = Query(None, description="Patient reference"),
    encounter: Optional[str] = Query(None, description="Encounter reference"),
    status: Optional[str] = Query(None, description="Medication request status")
):
    """Search medication requests (FHIR R4)."""
    results = list(MOCK_MEDICATION_REQUESTS.values())
    
    if patient:
        patient_ref = f"Patient/{patient}" if not patient.startswith("Patient/") else patient
        results = [m for m in results if m.get("subject", {}).get("reference") == patient_ref]
    
    if encounter:
        enc_ref = f"Encounter/{encounter}" if not encounter.startswith("Encounter/") else encounter
        results = [m for m in results if m.get("encounter", {}).get("reference") == enc_ref]
    
    if status:
        results = [m for m in results if m.get("status") == status]
    
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(results),
        "entry": [{"resource": m, "fullUrl": f"MedicationRequest/{m['id']}"} for m in results]
    }


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "server": "Mock FHIR R4 Server",
        "version": "1.0.0",
        "fhirVersion": "4.0.1",
        "timestamp": get_current_timestamp(),
        "resources": {
            "patients": len(MOCK_PATIENTS),
            "encounters": len(MOCK_ENCOUNTERS),
            "observations": len(MOCK_OBSERVATIONS),
            "conditions": len(MOCK_CONDITIONS),
            "medicationRequests": len(MOCK_MEDICATION_REQUESTS)
        }
    }


if __name__ == "__main__":
    print("=" * 60)
    print("🏥 Phoenix Guardian - Mock FHIR R4 Server")
    print("=" * 60)
    print()
    print("📍 Server URL:      http://localhost:8001")
    print("📖 API Docs:        http://localhost:8001/docs")
    print("🔍 Capability:      http://localhost:8001/metadata")
    print("❤️  Health Check:   http://localhost:8001/health")
    print()
    print("Available Resources:")
    print(f"  - {len(MOCK_PATIENTS)} Patients")
    print(f"  - {len(MOCK_ENCOUNTERS)} Encounters")
    print(f"  - {len(MOCK_OBSERVATIONS)} Observations")
    print(f"  - {len(MOCK_CONDITIONS)} Conditions")
    print(f"  - {len(MOCK_MEDICATION_REQUESTS)} Medication Requests")
    print()
    print("Example queries:")
    print("  GET /Patient/patient-001")
    print("  GET /Encounter?patient=patient-001")
    print("  GET /Observation?patient=patient-001&category=vital-signs")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
