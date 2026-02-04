"""
Tests for PriorAuthAgent - Insurance Pre-Authorization Agent

Comprehensive test coverage for:
- Prior authorization determination
- Carrier-specific rules (BCBS, UHC, Medicare, Medicaid)
- Urgency handling (emergency, urgent, routine)
- Form generation
- Approval likelihood estimation
- Alternative procedure suggestions
- Error handling
"""

import pytest
import asyncio
from typing import Dict, Any

from phoenix_guardian.agents.prior_auth_agent import (
    PriorAuthAgent,
    InsuranceInfo,
    PreAuthForm,
    PreAuthResult,
    Urgency,
    AuthType,
    ApprovalLikelihood,
)


@pytest.fixture
def agent() -> PriorAuthAgent:
    """Create a PriorAuthAgent instance for testing."""
    return PriorAuthAgent()


@pytest.fixture
def bcbs_insurance() -> Dict[str, Any]:
    """BCBS PPO insurance data."""
    return {
        "carrier": "Blue Cross Blue Shield",
        "plan_type": "PPO",
        "member_id": "ABC123456789",
        "group_number": "GRP987654",
    }


@pytest.fixture
def uhc_insurance() -> Dict[str, Any]:
    """UHC insurance data."""
    return {
        "carrier": "UnitedHealthcare",
        "plan_type": "HMO",
        "member_id": "UHC987654321",
        "group_number": "GRP111222",
    }


@pytest.fixture
def medicare_insurance() -> Dict[str, Any]:
    """Medicare Original insurance data."""
    return {
        "carrier": "Medicare",
        "plan_type": "Medicare Original",
        "member_id": "1EG4-TE5-MK72",
        "group_number": None,
    }


@pytest.fixture
def medicaid_insurance() -> Dict[str, Any]:
    """Medicaid insurance data."""
    return {
        "carrier": "Medicaid",
        "plan_type": "State Medicaid",
        "member_id": "MCD123456",
        "group_number": None,
    }


class TestBasicFunctionality:
    """Test basic prior authorization functionality."""
    
    @pytest.mark.asyncio
    async def test_requires_prior_auth_mri_bcbs(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """MRI requires auth for BCBS."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain with contrast",
            "diagnosis_codes": ["G43.909"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["requires_auth"] is True
        assert result.data["auth_type"] == "prior_authorization"
        assert "3-5 business days" in result.data["estimated_timeline"]
    
    @pytest.mark.asyncio
    async def test_no_prior_auth_xray(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """X-ray doesn't require auth."""
        context = {
            "procedure_code": "71046",
            "procedure_name": "Chest X-ray 2 views",
            "diagnosis_codes": ["J06.9"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["requires_auth"] is False
        assert result.data["auth_type"] == "none"
    
    @pytest.mark.asyncio
    async def test_requires_prior_auth_cardiac_cath(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Cardiac catheterization requires auth for BCBS."""
        context = {
            "procedure_code": "93458",
            "procedure_name": "Cardiac catheterization",
            "diagnosis_codes": ["I21.09", "I25.10"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
            "clinical_rationale": "Patient with STEMI requires catheterization per AHA guidelines",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["requires_auth"] is True
        assert "cardiac" in result.reasoning.lower() or "cath" in result.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_requires_prior_auth_specialty_med(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """High-cost procedures typically require auth."""
        context = {
            "procedure_code": "27447",  # Total knee replacement
            "procedure_name": "Total knee arthroplasty",
            "diagnosis_codes": ["M17.11"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["requires_auth"] is True
    
    @pytest.mark.asyncio
    async def test_medicare_wheelchair_prior_auth(
        self, agent: PriorAuthAgent, medicare_insurance: Dict[str, Any]
    ):
        """Medicare wheelchair requires prior auth."""
        context = {
            "procedure_code": "K0800",
            "procedure_name": "Power wheelchair group 1",
            "diagnosis_codes": ["G20"],
            "insurance": medicare_insurance,
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["requires_auth"] is True
        # DME typically needs predetermination
        assert result.data["auth_type"] in ["prior_authorization", "predetermination"]
    
    @pytest.mark.asyncio
    async def test_uhc_imaging_prior_auth(
        self, agent: PriorAuthAgent, uhc_insurance: Dict[str, Any]
    ):
        """UHC imaging rules - MRI requires auth."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain with contrast",
            "diagnosis_codes": ["R51.9"],
            "insurance": uhc_insurance,
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["requires_auth"] is True
        assert "2-4 business days" in result.data["estimated_timeline"]
    
    @pytest.mark.asyncio
    async def test_medicaid_specialist_referral(
        self, agent: PriorAuthAgent, medicaid_insurance: Dict[str, Any]
    ):
        """Medicaid specialist referral auth."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain",
            "diagnosis_codes": ["G43.909"],
            "insurance": medicaid_insurance,
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["requires_auth"] is True
    
    @pytest.mark.asyncio
    async def test_no_prior_auth_office_visit(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Office visits don't require auth."""
        context = {
            "procedure_code": "99214",
            "procedure_name": "Office visit, established patient, moderate",
            "diagnosis_codes": ["J06.9"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["requires_auth"] is False


class TestUrgencyHandling:
    """Test urgency-based timeline adjustments."""
    
    @pytest.mark.asyncio
    async def test_emergency_bypass(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Emergency bypasses prior auth."""
        context = {
            "procedure_code": "93458",
            "procedure_name": "Cardiac catheterization",
            "diagnosis_codes": ["I21.09"],
            "insurance": bcbs_insurance,
            "urgency": "emergency",
            "clinical_rationale": "STEMI - emergency cardiac cath required",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["requires_auth"] is False
        assert "retrospective" in result.data["estimated_timeline"].lower()
    
    @pytest.mark.asyncio
    async def test_urgent_expedited_timeline(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Urgent gets 24-48hr timeline."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain",
            "diagnosis_codes": ["I63.9"],  # Stroke
            "insurance": bcbs_insurance,
            "urgency": "urgent",
            "clinical_rationale": "Acute stroke workup",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert "24" in result.data["estimated_timeline"]
    
    @pytest.mark.asyncio
    async def test_routine_standard_timeline(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Routine gets 3-5 days."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain",
            "diagnosis_codes": ["G43.909"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert "3-5" in result.data["estimated_timeline"] or "business days" in result.data["estimated_timeline"]
    
    @pytest.mark.asyncio
    async def test_emergency_retrospective_review(
        self, agent: PriorAuthAgent, uhc_insurance: Dict[str, Any]
    ):
        """Emergency gets retro review notice."""
        context = {
            "procedure_code": "93458",
            "procedure_name": "Cardiac catheterization",
            "diagnosis_codes": ["I21.11"],
            "insurance": uhc_insurance,
            "urgency": "emergency",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        # Check for EMTALA bypass mention
        bypass_conditions = result.data["bypass_conditions"]
        assert any("emergency" in c.lower() or "emtala" in c.lower() for c in bypass_conditions)
    
    @pytest.mark.asyncio
    async def test_urgent_cardiac_case(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Urgent STEMI expedited."""
        context = {
            "procedure_code": "93458",
            "procedure_name": "Cardiac catheterization",
            "diagnosis_codes": ["I21.09"],  # STEMI
            "insurance": bcbs_insurance,
            "urgency": "urgent",
            "clinical_rationale": "STEMI patient needs urgent cardiac cath per AHA guidelines",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        # Should have expedited timeline
        timeline = result.data["estimated_timeline"]
        assert "24" in timeline or "48" in timeline or "expedited" in timeline.lower()


class TestFormGeneration:
    """Test pre-auth form generation."""
    
    @pytest.mark.asyncio
    async def test_form_generation_complete(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """All form fields populated."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain with contrast",
            "diagnosis_codes": ["G43.909", "R51.9"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
            "clinical_rationale": "Chronic migraine evaluation, failed conservative treatment",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        form = result.data["pre_auth_form"]
        assert form is not None
        
        # Check form fields
        fields = form["fields"]
        assert fields["member_id"] == "ABC123456789"
        assert fields["procedure_code"] == "70553"
        assert "G43.909" in fields["diagnosis_codes"]
        assert fields["urgency_level"] == "routine"
    
    @pytest.mark.asyncio
    async def test_form_includes_attachments(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Required attachments listed."""
        context = {
            "procedure_code": "93458",
            "procedure_name": "Cardiac catheterization",
            "diagnosis_codes": ["I21.09"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        form = result.data["pre_auth_form"]
        assert form is not None
        
        attachments = form["required_attachments"]
        assert len(attachments) > 0
        # Cardiac procedures should require EKG
        assert any("ekg" in a.lower() or "clinical" in a.lower() for a in attachments)
    
    @pytest.mark.asyncio
    async def test_form_carrier_contact_info(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Carrier contact info present."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain",
            "diagnosis_codes": ["R51.9"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        form = result.data["pre_auth_form"]
        assert form is not None
        
        contact = form["carrier_contact"]
        assert "phone" in contact
        assert "portal_url" in contact or "fax" in contact
    
    @pytest.mark.asyncio
    async def test_form_clinical_rationale(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Clinical rationale included."""
        rationale = "Patient with persistent headaches unresponsive to conservative treatment"
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain",
            "diagnosis_codes": ["R51.9"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
            "clinical_rationale": rationale,
        }
        
        result = await agent.execute(context)
        
        assert result.success
        form = result.data["pre_auth_form"]
        fields = form["fields"]
        assert rationale in fields["clinical_rationale"]


class TestApprovalLikelihood:
    """Test approval likelihood estimation."""
    
    @pytest.mark.asyncio
    async def test_approval_high_guideline_based(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """High likelihood for guideline-based."""
        context = {
            "procedure_code": "93458",
            "procedure_name": "Cardiac catheterization",
            "diagnosis_codes": ["I21.09"],
            "insurance": bcbs_insurance,
            "urgency": "urgent",
            "clinical_rationale": "STEMI patient per AHA guideline recommendations, evidence-based indication",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["approval_likelihood"] == "high"
    
    @pytest.mark.asyncio
    async def test_approval_medium_symptomatic(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Medium for symptomatic."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain",
            "diagnosis_codes": ["G43.909"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
            "clinical_rationale": "Patient symptomatic with chronic migraines",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["approval_likelihood"] in ["medium", "high"]
    
    @pytest.mark.asyncio
    async def test_approval_low_screening(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Low for screening in average risk."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain",
            "diagnosis_codes": ["Z00.00"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
            "clinical_rationale": "Screening MRI for average risk patient with no symptoms",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["approval_likelihood"] == "low"
    
    @pytest.mark.asyncio
    async def test_approval_uncertain_experimental(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Uncertain/low for experimental."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain",
            "diagnosis_codes": ["R51.9"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
            "clinical_rationale": "Experimental protocol for headache evaluation",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["approval_likelihood"] in ["low", "uncertain"]


class TestAlternativeProcedures:
    """Test alternative procedure suggestions."""
    
    @pytest.mark.asyncio
    async def test_alternatives_suggested_low_approval(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Alternatives for low approval."""
        context = {
            "procedure_code": "74177",  # CT with contrast
            "procedure_name": "CT Abdomen/Pelvis with contrast",
            "diagnosis_codes": ["R10.9"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
            "clinical_rationale": "Screening CT for average risk patient",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        # Low approval should suggest alternatives
        if result.data["approval_likelihood"] == "low":
            assert len(result.data["alternative_procedures"]) > 0
    
    @pytest.mark.asyncio
    async def test_alternatives_ct_to_ultrasound(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Suggest ultrasound vs CT."""
        context = {
            "procedure_code": "74177",
            "procedure_name": "CT Abdomen/Pelvis with contrast",
            "diagnosis_codes": ["R10.9"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
            "clinical_rationale": "Experimental imaging protocol",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        alternatives = result.data["alternative_procedures"]
        
        # Should suggest ultrasound as alternative
        if len(alternatives) > 0:
            alt_names = [a.get("procedure", "").lower() for a in alternatives]
            assert any("ultrasound" in name or "ct" in name for name in alt_names)
    
    @pytest.mark.asyncio
    async def test_no_alternatives_high_approval(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """No alternatives if high approval."""
        context = {
            "procedure_code": "93458",
            "procedure_name": "Cardiac catheterization",
            "diagnosis_codes": ["I21.09"],
            "insurance": bcbs_insurance,
            "urgency": "urgent",
            "clinical_rationale": "Acute STEMI per AHA guidelines, life-threatening emergency",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        if result.data["approval_likelihood"] == "high":
            # High approval cases don't need alternatives
            assert len(result.data["alternative_procedures"]) == 0


class TestErrorHandling:
    """Test error handling."""
    
    @pytest.mark.asyncio
    async def test_missing_procedure_code(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Error on missing CPT."""
        context = {
            "procedure_name": "MRI Brain",
            "diagnosis_codes": ["R51.9"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success is False
        assert "procedure code" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_missing_insurance_carrier(
        self, agent: PriorAuthAgent
    ):
        """Error on missing carrier."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain",
            "diagnosis_codes": ["R51.9"],
            "insurance": {},
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success is False
        assert "insurance" in result.error.lower() or "carrier" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_unknown_carrier(
        self, agent: PriorAuthAgent
    ):
        """Handle unknown carrier gracefully."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain",
            "diagnosis_codes": [],  # No diagnoses for uncertain
            "insurance": {
                "carrier": "Unknown Small Carrier XYZ",
                "plan_type": "PPO",
                "member_id": "12345",
            },
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        # Unknown carrier should default to requiring auth
        assert result.data["requires_auth"] is True
        assert result.data["approval_likelihood"] == "uncertain"
        assert "unknown" in result.data["carrier_specific_notes"].lower() or "contact" in result.data["carrier_specific_notes"].lower()
    
    @pytest.mark.asyncio
    async def test_invalid_urgency(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Default to routine for invalid urgency."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain",
            "diagnosis_codes": ["R51.9"],
            "insurance": bcbs_insurance,
            "urgency": "super_urgent_invalid",  # Invalid
        }
        
        result = await agent.execute(context)
        
        assert result.success
        # Should default to routine timeline
        assert "3-5" in result.data["estimated_timeline"] or "business days" in result.data["estimated_timeline"]


class TestIntegration:
    """Integration tests for complete workflows."""
    
    @pytest.mark.asyncio
    async def test_full_workflow_bcbs_mri(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Complete BCBS MRI workflow."""
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain with contrast",
            "diagnosis_codes": ["G43.909", "R51.9"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
            "patient_age": 45,
            "clinical_rationale": "Chronic migraine evaluation. Patient has failed conservative treatment including medications. MRI needed to rule out structural causes per medical guidelines.",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        
        # Verify complete response structure
        data = result.data
        assert "requires_auth" in data
        assert "auth_type" in data
        assert "estimated_timeline" in data
        assert "bypass_conditions" in data
        assert "required_documents" in data
        assert "approval_likelihood" in data
        assert "alternative_procedures" in data
        assert "carrier_specific_notes" in data
        
        # Verify form generated
        assert data["pre_auth_form"] is not None
        form = data["pre_auth_form"]
        assert "fields" in form
        assert "required_attachments" in form
        assert "submission_method" in form
        assert "carrier_contact" in form
        
        # Verify reasoning provided
        assert result.reasoning is not None
        assert len(result.reasoning) > 20
    
    @pytest.mark.asyncio
    async def test_full_workflow_medicare_wheelchair(
        self, agent: PriorAuthAgent, medicare_insurance: Dict[str, Any]
    ):
        """Complete Medicare DME workflow."""
        context = {
            "procedure_code": "K0800",
            "procedure_name": "Power wheelchair group 1",
            "diagnosis_codes": ["G20", "G35"],
            "insurance": medicare_insurance,
            "urgency": "routine",
            "patient_age": 72,
            "clinical_rationale": "Patient with Parkinson's disease requires power wheelchair for mobility. Unable to self-propel manual wheelchair. Face-to-face evaluation completed.",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        
        data = result.data
        
        # Medicare DME should require auth
        assert data["requires_auth"] is True
        
        # Should request CMN (Certificate of Medical Necessity)
        form = data["pre_auth_form"]
        assert form is not None
        
        # Check required documents include DME-specific items
        docs = data["required_documents"]
        assert any("medical necessity" in d.lower() or "cmn" in d.lower() or "face-to-face" in d.lower() for d in docs)


class TestPerformance:
    """Test performance requirements."""
    
    @pytest.mark.asyncio
    async def test_processing_time_under_500ms(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any]
    ):
        """Processing should complete in under 500ms."""
        import time
        
        context = {
            "procedure_code": "70553",
            "procedure_name": "MRI Brain",
            "diagnosis_codes": ["G43.909", "R51.9"],
            "insurance": bcbs_insurance,
            "urgency": "routine",
            "clinical_rationale": "Chronic migraine evaluation per guidelines",
        }
        
        start_time = time.perf_counter()
        result = await agent.execute(context)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        assert result.success
        assert elapsed_ms < 500, f"Processing took {elapsed_ms:.2f}ms, expected < 500ms"
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(
        self, agent: PriorAuthAgent, bcbs_insurance: Dict[str, Any], uhc_insurance: Dict[str, Any]
    ):
        """Handle concurrent requests."""
        contexts = [
            {
                "procedure_code": "70553",
                "diagnosis_codes": ["R51.9"],
                "insurance": bcbs_insurance,
                "urgency": "routine",
            },
            {
                "procedure_code": "93458",
                "diagnosis_codes": ["I21.09"],
                "insurance": uhc_insurance,
                "urgency": "urgent",
            },
        ]
        
        # Run concurrently
        tasks = [agent.execute(ctx) for ctx in contexts]
        results = await asyncio.gather(*tasks)
        
        assert all(r.success for r in results)


class TestDataclasses:
    """Test dataclass functionality."""
    
    def test_insurance_info_to_dict(self):
        """InsuranceInfo converts to dict."""
        info = InsuranceInfo(
            carrier="Blue Cross Blue Shield",
            plan_type="PPO",
            member_id="ABC123",
            group_number="GRP456",
        )
        
        d = info.to_dict()
        
        assert d["carrier"] == "Blue Cross Blue Shield"
        assert d["plan_type"] == "PPO"
        assert d["member_id"] == "ABC123"
        assert d["group_number"] == "GRP456"
    
    def test_pre_auth_form_to_dict(self):
        """PreAuthForm converts to dict."""
        form = PreAuthForm(
            form_type="prior_authorization",
            fields={"test": "value"},
            required_attachments=["doc1", "doc2"],
            submission_method="portal",
            carrier_contact={"phone": "1-800-TEST"},
        )
        
        d = form.to_dict()
        
        assert d["form_type"] == "prior_authorization"
        assert d["fields"]["test"] == "value"
        assert "doc1" in d["required_attachments"]
    
    def test_pre_auth_result_to_dict(self):
        """PreAuthResult converts to dict."""
        result = PreAuthResult(
            requires_auth=True,
            auth_type="prior_authorization",
            estimated_timeline="3-5 business days",
            bypass_conditions=["Emergency bypass"],
            required_documents=["Clinical notes"],
            pre_auth_form=None,
            approval_likelihood="high",
            alternative_procedures=[],
            carrier_specific_notes="Test notes",
        )
        
        d = result.to_dict()
        
        assert d["requires_auth"] is True
        assert d["auth_type"] == "prior_authorization"
        assert d["approval_likelihood"] == "high"


class TestCarrierAliases:
    """Test carrier name normalization."""
    
    @pytest.mark.asyncio
    async def test_bcbs_alias(self, agent: PriorAuthAgent):
        """BCBS alias works."""
        context = {
            "procedure_code": "70553",
            "diagnosis_codes": ["R51.9"],
            "insurance": {
                "carrier": "BCBS",
                "plan_type": "PPO",
                "member_id": "123",
            },
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["requires_auth"] is True
    
    @pytest.mark.asyncio
    async def test_uhc_alias(self, agent: PriorAuthAgent):
        """UHC alias works."""
        context = {
            "procedure_code": "70553",
            "diagnosis_codes": ["R51.9"],
            "insurance": {
                "carrier": "UHC",
                "plan_type": "HMO",
                "member_id": "456",
            },
            "urgency": "routine",
        }
        
        result = await agent.execute(context)
        
        assert result.success
        assert result.data["requires_auth"] is True


class TestEnums:
    """Test enum classes."""
    
    def test_urgency_values(self):
        """Urgency enum values."""
        assert Urgency.EMERGENCY.value == "emergency"
        assert Urgency.URGENT.value == "urgent"
        assert Urgency.ROUTINE.value == "routine"
    
    def test_auth_type_values(self):
        """AuthType enum values."""
        assert AuthType.PRIOR_AUTHORIZATION.value == "prior_authorization"
        assert AuthType.PREDETERMINATION.value == "predetermination"
        assert AuthType.REFERRAL.value == "referral"
        assert AuthType.NONE.value == "none"
    
    def test_approval_likelihood_values(self):
        """ApprovalLikelihood enum values."""
        assert ApprovalLikelihood.HIGH.value == "high"
        assert ApprovalLikelihood.MEDIUM.value == "medium"
        assert ApprovalLikelihood.LOW.value == "low"
        assert ApprovalLikelihood.UNCERTAIN.value == "uncertain"
