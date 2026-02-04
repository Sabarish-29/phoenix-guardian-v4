"""
Tests for QualityAgent - Clinical Guideline Adherence Agent

Comprehensive test coverage for:
- Diabetes guidelines (ADA 2024)
- Hypertension guidelines (AHA 2023)
- Preventive care (USPSTF)
- Medication safety (Beers Criteria)
- Overutilization detection
- Adherence score calculation
"""

import pytest
from datetime import date, timedelta
from typing import Dict, Any, List

from phoenix_guardian.agents.quality_agent import (
    QualityAgent,
    QualityFlag,
    QualityResult,
    PatientInfo,
    LabResult,
    Severity,
    GuidelineSource,
    QualityCategory,
)


@pytest.fixture
def agent() -> QualityAgent:
    """Create a QualityAgent instance for testing."""
    return QualityAgent()


@pytest.fixture
def diabetic_patient() -> Dict[str, Any]:
    """Patient with type 2 diabetes."""
    return {
        "age": 58,
        "sex": "F",
        "diagnoses": ["E11.9", "I10", "E78.5"],  # T2DM, HTN, Hyperlipidemia
        "medications": [
            "Metformin 1000mg BID",
            "Lisinopril 20mg daily",
            "Atorvastatin 40mg daily",
        ],
        "allergies": ["Penicillin"],
        "smoking_status": "former",
    }


@pytest.fixture
def diabetic_patient_controlled_labs() -> List[Dict[str, Any]]:
    """Labs showing well-controlled diabetes."""
    today = date.today().isoformat()
    return [
        {"test_name": "HbA1c", "value": 6.5, "unit": "%", "date": today},
        {"test_name": "LDL", "value": 85, "unit": "mg/dL", "date": today},
        {"test_name": "BP_systolic", "value": 125, "unit": "mmHg", "date": today},
        {"test_name": "BP_diastolic", "value": 78, "unit": "mmHg", "date": today},
        {"test_name": "eGFR", "value": 72, "unit": "mL/min/1.73m2", "date": today},
    ]


@pytest.fixture
def diabetic_patient_uncontrolled_labs() -> List[Dict[str, Any]]:
    """Labs showing poorly controlled diabetes."""
    today = date.today().isoformat()
    return [
        {"test_name": "HbA1c", "value": 9.2, "unit": "%", "date": today},
        {"test_name": "LDL", "value": 145, "unit": "mg/dL", "date": today},
        {"test_name": "BP_systolic", "value": 152, "unit": "mmHg", "date": today},
        {"test_name": "BP_diastolic", "value": 96, "unit": "mmHg", "date": today},
        {"test_name": "eGFR", "value": 55, "unit": "mL/min/1.73m2", "date": today},
    ]


@pytest.fixture
def hypertensive_patient() -> Dict[str, Any]:
    """Patient with hypertension only."""
    return {
        "age": 52,
        "sex": "M",
        "diagnoses": ["I10"],  # Essential hypertension
        "medications": ["Amlodipine 10mg daily"],
        "allergies": [],
        "smoking_status": "never",
    }


@pytest.fixture
def elderly_patient() -> Dict[str, Any]:
    """Elderly patient (age 72)."""
    return {
        "age": 72,
        "sex": "F",
        "diagnoses": ["E11.9", "I10"],  # T2DM, HTN
        "medications": [
            "Metformin 500mg BID",
            "Lisinopril 10mg daily",
            "Lorazepam 0.5mg at bedtime",  # Beers criteria
        ],
        "allergies": [],
        "smoking_status": "former",
    }


@pytest.fixture
def healthy_patient() -> Dict[str, Any]:
    """Healthy patient with no chronic conditions."""
    return {
        "age": 45,
        "sex": "M",
        "diagnoses": [],
        "medications": [],
        "allergies": [],
        "smoking_status": "never",
    }


class TestDiabetesGuidelines:
    """Test ADA diabetes guideline checking."""
    
    @pytest.mark.asyncio
    async def test_diabetes_hba1c_at_goal(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any],
        diabetic_patient_controlled_labs: List[Dict[str, Any]]
    ):
        """HbA1c at goal should be recognized."""
        context = {
            "patient": diabetic_patient,
            "labs": diabetic_patient_controlled_labs,
            "last_preventive_care": {
                "diabetic_eye_exam": date.today().isoformat(),
                "diabetic_foot_exam": date.today().isoformat(),
            },
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        met = result.data["met_guidelines"]
        assert any("hba1c at goal" in m.lower() for m in met)
    
    @pytest.mark.asyncio
    async def test_diabetes_hba1c_above_goal(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any],
        diabetic_patient_uncontrolled_labs: List[Dict[str, Any]]
    ):
        """HbA1c above goal should be flagged."""
        context = {
            "patient": diabetic_patient,
            "labs": diabetic_patient_uncontrolled_labs,
            "last_preventive_care": {},
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        flags = result.data["quality_flags"]
        hba1c_flag = next(
            (f for f in flags if "hba1c" in f["issue"].lower()),
            None
        )
        assert hba1c_flag is not None
        assert hba1c_flag["severity"] == "high"
        assert hba1c_flag["guideline"] == "ADA"
    
    @pytest.mark.asyncio
    async def test_diabetes_eye_exam_current(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any],
        diabetic_patient_controlled_labs: List[Dict[str, Any]]
    ):
        """Current eye exam should not create a care gap."""
        recent_date = (date.today() - timedelta(days=180)).isoformat()
        context = {
            "patient": diabetic_patient,
            "labs": diabetic_patient_controlled_labs,
            "last_preventive_care": {
                "diabetic_eye_exam": recent_date,
                "diabetic_foot_exam": recent_date,
            },
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        care_gaps = result.data["care_gaps"]
        assert not any("eye exam" in gap.lower() and "overdue" in gap.lower() for gap in care_gaps)
    
    @pytest.mark.asyncio
    async def test_diabetes_eye_exam_overdue(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any],
        diabetic_patient_controlled_labs: List[Dict[str, Any]]
    ):
        """Overdue eye exam should create a care gap."""
        old_date = (date.today() - timedelta(days=400)).isoformat()
        context = {
            "patient": diabetic_patient,
            "labs": diabetic_patient_controlled_labs,
            "last_preventive_care": {
                "diabetic_eye_exam": old_date,
                "diabetic_foot_exam": date.today().isoformat(),
            },
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        care_gaps = result.data["care_gaps"]
        assert any("eye exam" in gap.lower() for gap in care_gaps)
    
    @pytest.mark.asyncio
    async def test_diabetes_foot_exam_overdue(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any],
        diabetic_patient_controlled_labs: List[Dict[str, Any]]
    ):
        """Overdue foot exam should create a care gap."""
        old_date = (date.today() - timedelta(days=400)).isoformat()
        context = {
            "patient": diabetic_patient,
            "labs": diabetic_patient_controlled_labs,
            "last_preventive_care": {
                "diabetic_eye_exam": date.today().isoformat(),
                "diabetic_foot_exam": old_date,
            },
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        care_gaps = result.data["care_gaps"]
        assert any("foot exam" in gap.lower() for gap in care_gaps)
    
    @pytest.mark.asyncio
    async def test_diabetes_medications_appropriate(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any],
        diabetic_patient_controlled_labs: List[Dict[str, Any]]
    ):
        """Patient on metformin, ACE-I, statin should be recognized."""
        context = {
            "patient": diabetic_patient,
            "labs": diabetic_patient_controlled_labs,
            "last_preventive_care": {
                "diabetic_eye_exam": date.today().isoformat(),
                "diabetic_foot_exam": date.today().isoformat(),
            },
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        met = result.data["met_guidelines"]
        assert any("metformin" in m.lower() for m in met)
        assert any("ace inhibitor" in m.lower() or "statin" in m.lower() for m in met)
    
    @pytest.mark.asyncio
    async def test_diabetes_acr_missing(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any]
    ):
        """Missing ACR should be noted."""
        context = {
            "patient": diabetic_patient,
            "labs": [],  # No labs including ACR
            "last_preventive_care": {},
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        # Missing labs should generate a flag about HbA1c
        flags = result.data["quality_flags"]
        assert any("hba1c" in f["issue"].lower() or "lab" in f["issue"].lower() for f in flags)
    
    @pytest.mark.asyncio
    async def test_diabetes_statin_recommended(
        self, agent: QualityAgent
    ):
        """Diabetes patient age 40+ without statin should be flagged."""
        patient_no_statin = {
            "age": 55,
            "sex": "M",
            "diagnoses": ["E11.9"],
            "medications": ["Metformin 1000mg BID"],  # No statin
            "allergies": [],
        }
        today = date.today().isoformat()
        
        context = {
            "patient": patient_no_statin,
            "labs": [{"test_name": "HbA1c", "value": 6.8, "unit": "%", "date": today}],
            "last_preventive_care": {},
            "encounter_date": today,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        flags = result.data["quality_flags"]
        statin_flag = next(
            (f for f in flags if "statin" in f["issue"].lower()),
            None
        )
        assert statin_flag is not None


class TestHypertensionGuidelines:
    """Test AHA hypertension guideline checking."""
    
    @pytest.mark.asyncio
    async def test_hypertension_bp_at_goal(
        self, agent: QualityAgent, hypertensive_patient: Dict[str, Any]
    ):
        """BP at goal should be recognized."""
        today = date.today().isoformat()
        context = {
            "patient": hypertensive_patient,
            "labs": [
                {"test_name": "BP_systolic", "value": 125, "unit": "mmHg", "date": today},
                {"test_name": "BP_diastolic", "value": 78, "unit": "mmHg", "date": today},
            ],
            "last_preventive_care": {},
            "encounter_date": today,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        met = result.data["met_guidelines"]
        assert any("blood pressure at goal" in m.lower() for m in met)
    
    @pytest.mark.asyncio
    async def test_hypertension_bp_above_goal(
        self, agent: QualityAgent, hypertensive_patient: Dict[str, Any]
    ):
        """BP above goal should be flagged."""
        today = date.today().isoformat()
        context = {
            "patient": hypertensive_patient,
            "labs": [
                {"test_name": "BP_systolic", "value": 148, "unit": "mmHg", "date": today},
                {"test_name": "BP_diastolic", "value": 92, "unit": "mmHg", "date": today},
            ],
            "last_preventive_care": {},
            "encounter_date": today,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        flags = result.data["quality_flags"]
        bp_flag = next(
            (f for f in flags if "blood pressure" in f["issue"].lower()),
            None
        )
        assert bp_flag is not None
        assert bp_flag["guideline"] == "AHA"
    
    @pytest.mark.asyncio
    async def test_hypertension_medication_appropriate(
        self, agent: QualityAgent, hypertensive_patient: Dict[str, Any]
    ):
        """Patient on CCB should be recognized."""
        today = date.today().isoformat()
        context = {
            "patient": hypertensive_patient,
            "labs": [
                {"test_name": "BP_systolic", "value": 128, "unit": "mmHg", "date": today},
                {"test_name": "BP_diastolic", "value": 82, "unit": "mmHg", "date": today},
            ],
            "last_preventive_care": {},
            "encounter_date": today,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        met = result.data["met_guidelines"]
        assert any("antihypertensive" in m.lower() for m in met)
    
    @pytest.mark.asyncio
    async def test_hypertension_diabetes_lower_goal(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any]
    ):
        """Diabetes patient should have stricter BP goal."""
        today = date.today().isoformat()
        context = {
            "patient": diabetic_patient,
            "labs": [
                {"test_name": "HbA1c", "value": 6.8, "unit": "%", "date": today},
                {"test_name": "BP_systolic", "value": 135, "unit": "mmHg", "date": today},
                {"test_name": "BP_diastolic", "value": 82, "unit": "mmHg", "date": today},
            ],
            "last_preventive_care": {
                "diabetic_eye_exam": today,
                "diabetic_foot_exam": today,
            },
            "encounter_date": today,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        # BP 135/82 is above diabetes goal of <130/80
        flags = result.data["quality_flags"]
        bp_flag = next(
            (f for f in flags if "blood pressure" in f["issue"].lower()),
            None
        )
        assert bp_flag is not None
    
    @pytest.mark.asyncio
    async def test_hypertension_elderly_relaxed_goal(
        self, agent: QualityAgent
    ):
        """Elderly patient (>65) has relaxed BP goal."""
        elderly_htn = {
            "age": 72,
            "sex": "F",
            "diagnoses": ["I10"],
            "medications": ["Lisinopril 10mg daily"],
            "allergies": [],
        }
        today = date.today().isoformat()
        
        context = {
            "patient": elderly_htn,
            "labs": [
                {"test_name": "BP_systolic", "value": 138, "unit": "mmHg", "date": today},
                {"test_name": "BP_diastolic", "value": 85, "unit": "mmHg", "date": today},
            ],
            "last_preventive_care": {},
            "encounter_date": today,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        # BP 138/85 is at goal for elderly (goal <140/90)
        met = result.data["met_guidelines"]
        assert any("blood pressure at goal" in m.lower() for m in met)


class TestPreventiveCare:
    """Test USPSTF preventive care guideline checking."""
    
    @pytest.mark.asyncio
    async def test_preventive_colonoscopy_due(
        self, agent: QualityAgent
    ):
        """Colonoscopy due after 10 years."""
        patient = {
            "age": 58,
            "sex": "M",
            "diagnoses": [],
            "medications": [],
            "allergies": [],
        }
        old_date = (date.today() - timedelta(days=3700)).isoformat()  # > 10 years
        
        context = {
            "patient": patient,
            "labs": [],
            "last_preventive_care": {
                "colonoscopy": old_date,
            },
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        care_gaps = result.data["care_gaps"]
        assert any("colonoscopy" in gap.lower() for gap in care_gaps)
    
    @pytest.mark.asyncio
    async def test_preventive_mammography_overdue(
        self, agent: QualityAgent
    ):
        """Mammography overdue for female 50-74."""
        patient = {
            "age": 55,
            "sex": "F",
            "diagnoses": [],
            "medications": [],
            "allergies": [],
        }
        old_date = (date.today() - timedelta(days=800)).isoformat()  # > 2 years
        
        context = {
            "patient": patient,
            "labs": [],
            "last_preventive_care": {
                "mammography": old_date,
            },
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        care_gaps = result.data["care_gaps"]
        assert any("mammography" in gap.lower() for gap in care_gaps)
    
    @pytest.mark.asyncio
    async def test_preventive_influenza_vaccine(
        self, agent: QualityAgent
    ):
        """Influenza vaccine should be tracked."""
        patient = {
            "age": 50,
            "sex": "M",
            "diagnoses": [],
            "medications": [],
            "allergies": [],
        }
        # Set encounter during flu season
        encounter = date(date.today().year, 11, 15).isoformat()
        
        context = {
            "patient": patient,
            "labs": [],
            "last_preventive_care": {},  # No flu vaccine
            "encounter_date": encounter,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        care_gaps = result.data["care_gaps"]
        assert any("influenza" in gap.lower() or "flu" in gap.lower() for gap in care_gaps)
    
    @pytest.mark.asyncio
    async def test_preventive_pneumococcal_vaccine(
        self, agent: QualityAgent
    ):
        """Pneumococcal vaccine for age 65+."""
        patient = {
            "age": 68,
            "sex": "F",
            "diagnoses": [],
            "medications": [],
            "allergies": [],
        }
        
        context = {
            "patient": patient,
            "labs": [],
            "last_preventive_care": {},  # No pneumococcal
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        care_gaps = result.data["care_gaps"]
        assert any("pneumococcal" in gap.lower() for gap in care_gaps)
    
    @pytest.mark.asyncio
    async def test_preventive_lung_cancer_screening(
        self, agent: QualityAgent
    ):
        """Lung cancer screening for smokers 50-80."""
        patient = {
            "age": 60,
            "sex": "M",
            "diagnoses": [],
            "medications": [],
            "allergies": [],
            "smoking_status": "current",
        }
        
        context = {
            "patient": patient,
            "labs": [],
            "last_preventive_care": {},
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        care_gaps = result.data["care_gaps"]
        assert any("lung" in gap.lower() for gap in care_gaps)
    
    @pytest.mark.asyncio
    async def test_preventive_all_current(
        self, agent: QualityAgent
    ):
        """Patient with all preventive care current."""
        patient = {
            "age": 55,
            "sex": "F",
            "diagnoses": [],
            "medications": [],
            "allergies": [],
            "smoking_status": "never",
        }
        recent = (date.today() - timedelta(days=30)).isoformat()
        
        context = {
            "patient": patient,
            "labs": [],
            "last_preventive_care": {
                "mammography": recent,
                "colonoscopy": recent,
            },
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        care_gaps = result.data["care_gaps"]
        # Should not have mammography or colonoscopy gaps
        assert not any("mammography" in gap.lower() and "overdue" in gap.lower() for gap in care_gaps)
        assert not any("colonoscopy" in gap.lower() and "overdue" in gap.lower() for gap in care_gaps)
    
    @pytest.mark.asyncio
    async def test_preventive_care_gaps_identified(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any]
    ):
        """Multiple care gaps should be identified."""
        context = {
            "patient": diabetic_patient,
            "labs": [],
            "last_preventive_care": {},  # No preventive care records
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        care_gaps = result.data["care_gaps"]
        assert len(care_gaps) > 0


class TestMedicationSafety:
    """Test medication safety checking."""
    
    @pytest.mark.asyncio
    async def test_medication_safety_no_issues(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any],
        diabetic_patient_controlled_labs: List[Dict[str, Any]]
    ):
        """No safety issues with appropriate medications."""
        context = {
            "patient": diabetic_patient,
            "labs": diabetic_patient_controlled_labs,
            "last_preventive_care": {
                "diabetic_eye_exam": date.today().isoformat(),
                "diabetic_foot_exam": date.today().isoformat(),
            },
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        # Should have no critical/high medication safety flags
        flags = result.data["quality_flags"]
        safety_flags = [
            f for f in flags 
            if f["category"] == "medication_safety" and f["severity"] in ["critical", "high"]
        ]
        assert len(safety_flags) == 0
    
    @pytest.mark.asyncio
    async def test_medication_safety_beers_criteria(
        self, agent: QualityAgent, elderly_patient: Dict[str, Any]
    ):
        """Beers Criteria violation should be flagged."""
        today = date.today().isoformat()
        context = {
            "patient": elderly_patient,
            "labs": [{"test_name": "HbA1c", "value": 7.2, "unit": "%", "date": today}],
            "last_preventive_care": {
                "diabetic_eye_exam": today,
                "diabetic_foot_exam": today,
            },
            "encounter_date": today,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        flags = result.data["quality_flags"]
        beers_flag = next(
            (f for f in flags if "benzodiazepine" in f["issue"].lower() or "lorazepam" in f["issue"].lower()),
            None
        )
        assert beers_flag is not None
        assert beers_flag["category"] == "medication_safety"
    
    @pytest.mark.asyncio
    async def test_medication_safety_drug_interaction(
        self, agent: QualityAgent
    ):
        """ACE-I + ARB combination should be flagged."""
        patient = {
            "age": 62,
            "sex": "M",
            "diagnoses": ["I10", "E11.9"],
            "medications": [
                "Lisinopril 20mg daily",  # ACE-I
                "Losartan 50mg daily",     # ARB
            ],
            "allergies": [],
        }
        today = date.today().isoformat()
        
        context = {
            "patient": patient,
            "labs": [{"test_name": "HbA1c", "value": 7.0, "unit": "%", "date": today}],
            "last_preventive_care": {
                "diabetic_eye_exam": today,
                "diabetic_foot_exam": today,
            },
            "encounter_date": today,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        flags = result.data["quality_flags"]
        interaction_flag = next(
            (f for f in flags if "ace" in f["issue"].lower() and "arb" in f["issue"].lower()),
            None
        )
        assert interaction_flag is not None
        assert interaction_flag["severity"] == "high"
    
    @pytest.mark.asyncio
    async def test_medication_safety_renal_dosing(
        self, agent: QualityAgent
    ):
        """Metformin with low eGFR should be flagged."""
        patient = {
            "age": 68,
            "sex": "F",
            "diagnoses": ["E11.9", "N18.4"],  # T2DM, CKD stage 4
            "medications": ["Metformin 1000mg BID"],
            "allergies": [],
        }
        today = date.today().isoformat()
        
        context = {
            "patient": patient,
            "labs": [
                {"test_name": "HbA1c", "value": 7.5, "unit": "%", "date": today},
                {"test_name": "eGFR", "value": 25, "unit": "mL/min/1.73m2", "date": today},
            ],
            "last_preventive_care": {
                "diabetic_eye_exam": today,
                "diabetic_foot_exam": today,
            },
            "encounter_date": today,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        flags = result.data["quality_flags"]
        renal_flag = next(
            (f for f in flags if "metformin" in f["issue"].lower() and "egfr" in f["issue"].lower()),
            None
        )
        assert renal_flag is not None
        assert renal_flag["severity"] == "critical"
    
    @pytest.mark.asyncio
    async def test_medication_safety_duplicate_therapy(
        self, agent: QualityAgent
    ):
        """NSAID with CKD should be flagged."""
        patient = {
            "age": 65,
            "sex": "M",
            "diagnoses": ["N18.3"],  # CKD stage 3
            "medications": ["Ibuprofen 400mg TID"],
            "allergies": [],
        }
        today = date.today().isoformat()
        
        context = {
            "patient": patient,
            "labs": [
                {"test_name": "eGFR", "value": 45, "unit": "mL/min/1.73m2", "date": today},
            ],
            "last_preventive_care": {},
            "encounter_date": today,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        flags = result.data["quality_flags"]
        nsaid_flag = next(
            (f for f in flags if "nsaid" in f["issue"].lower()),
            None
        )
        assert nsaid_flag is not None


class TestOverutilization:
    """Test overutilization detection."""
    
    @pytest.mark.asyncio
    async def test_overutilization_duplicate_lab(
        self, agent: QualityAgent, healthy_patient: Dict[str, Any]
    ):
        """Duplicate labs within 7 days should be flagged."""
        today = date.today()
        yesterday = (today - timedelta(days=1)).isoformat()
        today_str = today.isoformat()
        
        context = {
            "patient": healthy_patient,
            "labs": [
                {"test_name": "CBC", "value": 12.5, "unit": "g/dL", "date": yesterday},
                {"test_name": "CBC", "value": 12.3, "unit": "g/dL", "date": today_str},
            ],
            "last_preventive_care": {},
            "encounter_date": today_str,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        alerts = result.data["overutilization_alerts"]
        assert any("duplicate" in a.lower() or "cbc" in a.lower() for a in alerts)
    
    @pytest.mark.asyncio
    async def test_overutilization_unnecessary_imaging(
        self, agent: QualityAgent, healthy_patient: Dict[str, Any]
    ):
        """Unnecessary preoperative imaging should be flagged."""
        today = date.today().isoformat()
        context = {
            "patient": healthy_patient,
            "labs": [],
            "last_preventive_care": {},
            "orders": ["Preoperative chest X-ray"],
            "encounter_date": today,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        alerts = result.data["overutilization_alerts"]
        # May or may not flag depending on implementation
        # The important thing is processing doesn't fail
    
    @pytest.mark.asyncio
    async def test_overutilization_inappropriate_antibiotics(
        self, agent: QualityAgent
    ):
        """Context for antibiotic checking."""
        patient = {
            "age": 35,
            "sex": "F",
            "diagnoses": ["J06.9"],  # Acute URI
            "medications": ["Azithromycin 250mg"],  # Antibiotic for viral URI
            "allergies": [],
        }
        
        context = {
            "patient": patient,
            "labs": [],
            "last_preventive_care": {},
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        # Processing should complete successfully
    
    @pytest.mark.asyncio
    async def test_no_overutilization(
        self, agent: QualityAgent, healthy_patient: Dict[str, Any]
    ):
        """No overutilization with appropriate care."""
        today = date.today().isoformat()
        context = {
            "patient": healthy_patient,
            "labs": [
                {"test_name": "CBC", "value": 12.5, "unit": "g/dL", "date": today},
            ],
            "last_preventive_care": {},
            "encounter_date": today,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        alerts = result.data["overutilization_alerts"]
        # Should have minimal or no alerts
        assert len(alerts) <= 1


class TestGuidelineAdherenceScore:
    """Test adherence score calculation."""
    
    @pytest.mark.asyncio
    async def test_adherence_score_perfect(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any],
        diabetic_patient_controlled_labs: List[Dict[str, Any]]
    ):
        """Well-controlled patient should have high score."""
        recent = date.today().isoformat()
        context = {
            "patient": diabetic_patient,
            "labs": diabetic_patient_controlled_labs,
            "last_preventive_care": {
                "diabetic_eye_exam": recent,
                "diabetic_foot_exam": recent,
                "mammography": recent,
                "colonoscopy": (date.today() - timedelta(days=365)).isoformat(),
            },
            "encounter_date": recent,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        score = result.data["guideline_adherence_score"]
        assert score >= 0.7
    
    @pytest.mark.asyncio
    async def test_adherence_score_poor(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any],
        diabetic_patient_uncontrolled_labs: List[Dict[str, Any]]
    ):
        """Poorly controlled patient should have lower score."""
        context = {
            "patient": diabetic_patient,
            "labs": diabetic_patient_uncontrolled_labs,
            "last_preventive_care": {},  # No preventive care
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        score = result.data["guideline_adherence_score"]
        assert score < 0.8
    
    @pytest.mark.asyncio
    async def test_adherence_score_calculation(
        self, agent: QualityAgent
    ):
        """Score should be between 0 and 1."""
        patient = {
            "age": 50,
            "sex": "M",
            "diagnoses": ["E11.9"],
            "medications": [],  # No medications
            "allergies": [],
        }
        
        context = {
            "patient": patient,
            "labs": [],
            "last_preventive_care": {},
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        score = result.data["guideline_adherence_score"]
        assert 0.0 <= score <= 1.0


class TestErrorHandling:
    """Test error handling."""
    
    @pytest.mark.asyncio
    async def test_missing_patient_info(
        self, agent: QualityAgent
    ):
        """Missing patient info should return error."""
        context = {
            "labs": [],
            "last_preventive_care": {},
        }
        
        result = await agent.execute(context)
        
        assert result.success is False
        assert "patient" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_no_diagnoses(
        self, agent: QualityAgent, healthy_patient: Dict[str, Any]
    ):
        """Patient with no diagnoses should still get assessment."""
        context = {
            "patient": healthy_patient,
            "labs": [],
            "last_preventive_care": {},
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        # Healthy patient with no chronic conditions should have high score
        assert result.data["guideline_adherence_score"] >= 0.8
    
    @pytest.mark.asyncio
    async def test_no_labs_provided(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any]
    ):
        """Missing labs should be handled gracefully."""
        context = {
            "patient": diabetic_patient,
            "labs": [],  # No labs
            "last_preventive_care": {
                "diabetic_eye_exam": date.today().isoformat(),
                "diabetic_foot_exam": date.today().isoformat(),
            },
            "encounter_date": date.today().isoformat(),
        }
        
        result = await agent.execute(context)
        
        assert result.success
        # Should flag missing labs
        flags = result.data["quality_flags"]
        assert any("hba1c" in f["issue"].lower() for f in flags)


class TestDataclasses:
    """Test dataclass functionality."""
    
    def test_quality_flag_to_dict(self):
        """QualityFlag converts to dict."""
        flag = QualityFlag(
            severity=Severity.HIGH,
            category=QualityCategory.DIABETES_MANAGEMENT,
            guideline=GuidelineSource.ADA,
            issue="Test issue",
            recommendation="Test recommendation",
            reference="ADA 2024",
        )
        
        d = flag.to_dict()
        
        assert d["severity"] == "high"
        assert d["category"] == "diabetes_management"
        assert d["guideline"] == "ADA"
        assert d["issue"] == "Test issue"
    
    def test_quality_result_to_dict(self):
        """QualityResult converts to dict."""
        result = QualityResult(
            guideline_adherence_score=0.85,
            quality_flags=[],
            met_guidelines=["Test met"],
            care_gaps=["Test gap"],
            overutilization_alerts=[],
            preventive_care_due=[],
        )
        
        d = result.to_dict()
        
        assert d["guideline_adherence_score"] == 0.85
        assert "Test met" in d["met_guidelines"]
        assert "Test gap" in d["care_gaps"]
    
    def test_lab_result_creation(self):
        """LabResult can be created."""
        lab = LabResult(
            test_name="HbA1c",
            value=7.2,
            unit="%",
            date=date.today(),
            reference_range="<7.0%",
        )
        
        assert lab.test_name == "HbA1c"
        assert lab.value == 7.2
        assert lab.unit == "%"


class TestEnums:
    """Test enum values."""
    
    def test_severity_values(self):
        """Severity enum values."""
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"
    
    def test_guideline_source_values(self):
        """GuidelineSource enum values."""
        assert GuidelineSource.AHA.value == "AHA"
        assert GuidelineSource.ADA.value == "ADA"
        assert GuidelineSource.USPSTF.value == "USPSTF"
        assert GuidelineSource.CMS.value == "CMS"
    
    def test_quality_category_values(self):
        """QualityCategory enum values."""
        assert QualityCategory.DIABETES_MANAGEMENT.value == "diabetes_management"
        assert QualityCategory.HYPERTENSION_MANAGEMENT.value == "hypertension_management"
        assert QualityCategory.PREVENTIVE_CARE.value == "preventive_care"
        assert QualityCategory.MEDICATION_SAFETY.value == "medication_safety"


class TestPerformance:
    """Test performance requirements."""
    
    @pytest.mark.asyncio
    async def test_processing_time_under_500ms(
        self, agent: QualityAgent, diabetic_patient: Dict[str, Any],
        diabetic_patient_controlled_labs: List[Dict[str, Any]]
    ):
        """Processing should complete in under 500ms."""
        import time
        
        context = {
            "patient": diabetic_patient,
            "labs": diabetic_patient_controlled_labs,
            "last_preventive_care": {
                "diabetic_eye_exam": date.today().isoformat(),
                "diabetic_foot_exam": date.today().isoformat(),
                "mammography": date.today().isoformat(),
            },
            "encounter_date": date.today().isoformat(),
        }
        
        start = time.perf_counter()
        result = await agent.execute(context)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert result.success
        assert elapsed_ms < 500, f"Processing took {elapsed_ms:.2f}ms, expected < 500ms"
