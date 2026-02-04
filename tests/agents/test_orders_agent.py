"""
Tests for OrdersAgent - Lab and imaging order validation.

Tests cover:
- Basic order validation
- Duplicate detection
- Contraindication checking
- Protocol-based suggestions
- Panel recommendations
- Cost optimization
"""

import pytest
from datetime import date, timedelta
from phoenix_guardian.agents.orders_agent import (
    OrdersAgent,
    Order,
    RecentOrder,
    PatientContext,
    ValidatedOrder,
    SuggestedOrder,
    CostOptimization,
    OrdersResult,
    OrderType,
    Urgency,
    OrderStatus,
    Priority,
)


@pytest.fixture
def agent():
    """Create OrdersAgent instance."""
    return OrdersAgent()


@pytest.fixture
def basic_patient():
    """Basic patient context."""
    return {
        "age": 55,
        "sex": "M",
        "creatinine": 1.0,
        "egfr": 85,
        "allergies": [],
        "pregnancy_status": "not_pregnant",
        "weight_kg": 80,
        "conditions": []
    }


@pytest.fixture
def renal_impaired_patient():
    """Patient with renal impairment."""
    return {
        "age": 72,
        "sex": "F",
        "creatinine": 2.5,
        "egfr": 28,
        "allergies": [],
        "pregnancy_status": "not_pregnant",
        "weight_kg": 65,
        "conditions": ["CKD Stage 4"]
    }


@pytest.fixture
def contrast_allergic_patient():
    """Patient with contrast allergy."""
    return {
        "age": 45,
        "sex": "M",
        "creatinine": 0.9,
        "egfr": 95,
        "allergies": ["Contrast dye", "Penicillin"],
        "pregnancy_status": "not_pregnant",
        "weight_kg": 75,
        "conditions": []
    }


@pytest.fixture
def pregnant_patient():
    """Pregnant patient."""
    return {
        "age": 28,
        "sex": "F",
        "creatinine": 0.6,
        "egfr": 120,
        "allergies": [],
        "pregnancy_status": "pregnant",
        "weight_kg": 70,
        "conditions": []
    }


@pytest.fixture
def pacemaker_patient():
    """Patient with pacemaker."""
    return {
        "age": 68,
        "sex": "M",
        "creatinine": 1.2,
        "egfr": 60,
        "allergies": [],
        "pregnancy_status": "not_pregnant",
        "weight_kg": 85,
        "conditions": ["Heart failure"],
        "has_pacemaker": True
    }


class TestBasicValidation:
    """Test basic order validation functionality."""
    
    @pytest.mark.asyncio
    async def test_validate_cbc_appropriate(self, agent, basic_patient):
        """Test validation of appropriate CBC order."""
        context = {
            "orders": [{"test": "CBC", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Anemia evaluation",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        assert result.data is not None
        validated = result.data["validated_orders"]
        assert len(validated) == 1
        assert validated[0]["status"] == "approved"
    
    @pytest.mark.asyncio
    async def test_validate_bmp_appropriate(self, agent, basic_patient):
        """Test validation of appropriate BMP order."""
        context = {
            "orders": [{"test": "BMP", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Electrolyte monitoring",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        assert result.data is not None
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "approved"
    
    @pytest.mark.asyncio
    async def test_validate_imaging_appropriate(self, agent, basic_patient):
        """Test validation of appropriate imaging order."""
        context = {
            "orders": [{"test": "Chest X-ray", "order_type": "imaging", "urgency": "routine"}],
            "diagnosis": "Cough evaluation",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "approved"
    
    @pytest.mark.asyncio
    async def test_validate_multiple_orders(self, agent, basic_patient):
        """Test validation of multiple orders."""
        context = {
            "orders": [
                {"test": "CBC", "order_type": "lab", "urgency": "stat"},
                {"test": "BMP", "order_type": "lab", "urgency": "stat"},
                {"test": "Chest X-ray", "order_type": "imaging", "urgency": "stat"}
            ],
            "diagnosis": "Pneumonia (J18.9)",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert len(validated) == 3
        # All should be approved
        for order in validated:
            assert order["status"] in ["approved", "duplicate"]
    
    @pytest.mark.asyncio
    async def test_invalid_test_name(self, agent, basic_patient):
        """Test handling of unrecognized test name."""
        context = {
            "orders": [{"test": "XYZ Unknown Test", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "questionable"
        assert "not recognized" in validated[0]["issue"]
    
    @pytest.mark.asyncio
    async def test_no_orders_error(self, agent, basic_patient):
        """Test error when no orders provided."""
        context = {
            "orders": [],
            "diagnosis": "Test",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        assert result.error is not None
        assert "At least one order is required" in result.error
    
    @pytest.mark.asyncio
    async def test_approved_status(self, agent, basic_patient):
        """Test that appropriate orders get approved status."""
        context = {
            "orders": [{"test": "Lipid panel", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Hyperlipidemia screening",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "approved"
    
    @pytest.mark.asyncio
    async def test_questionable_status(self, agent, basic_patient):
        """Test questionable status for unrecognized tests."""
        context = {
            "orders": [{"test": "Fake Test 123", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "questionable"


class TestDuplicateDetection:
    """Test duplicate order detection."""
    
    @pytest.mark.asyncio
    async def test_detect_duplicate_cbc(self, agent, basic_patient):
        """Test detection of duplicate CBC within validity period."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        
        context = {
            "orders": [{"test": "CBC", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Routine monitoring",
            "recent_orders": [{"test": "CBC", "date": yesterday, "result": "WBC 8.5"}],
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "duplicate"
    
    @pytest.mark.asyncio
    async def test_detect_duplicate_within_validity(self, agent, basic_patient):
        """Test duplicate detection within validity period."""
        two_days_ago = (date.today() - timedelta(days=2)).isoformat()
        
        context = {
            "orders": [{"test": "BMP", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Routine labs",
            "recent_orders": [{"test": "BMP", "date": two_days_ago, "result": "Normal"}],
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "duplicate"
    
    @pytest.mark.asyncio
    async def test_no_duplicate_outside_validity(self, agent, basic_patient):
        """Test no duplicate flag when outside validity period."""
        ten_days_ago = (date.today() - timedelta(days=10)).isoformat()
        
        context = {
            "orders": [{"test": "CBC", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Routine follow-up",
            "recent_orders": [{"test": "CBC", "date": ten_days_ago, "result": "Normal"}],
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "approved"
    
    @pytest.mark.asyncio
    async def test_duplicate_acute_illness_shorter_validity(self, agent, basic_patient):
        """Test shorter validity period for acute illness."""
        two_days_ago = (date.today() - timedelta(days=2)).isoformat()
        
        context = {
            "orders": [{"test": "CBC", "order_type": "lab", "urgency": "stat"}],
            "diagnosis": "Sepsis (A41.9)",
            "recent_orders": [{"test": "CBC", "date": two_days_ago, "result": "WBC 18.5"}],
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        # In acute illness, validity is 1 day, so 2-day-old CBC is NOT duplicate
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "approved"
    
    @pytest.mark.asyncio
    async def test_duplicate_with_recent_result(self, agent, basic_patient):
        """Test that duplicate includes recent result information."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        
        context = {
            "orders": [{"test": "CBC", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Routine",
            "recent_orders": [{"test": "CBC", "date": yesterday, "result": "WBC 12.5, Hgb 14.2"}],
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "duplicate"
        assert "WBC 12.5" in validated[0]["issue"]
    
    @pytest.mark.asyncio
    async def test_serial_troponins_not_duplicate(self, agent, basic_patient):
        """Test that serial troponins are not flagged as duplicates."""
        one_hour_ago = date.today().isoformat()
        
        context = {
            "orders": [{"test": "Troponin", "order_type": "lab", "urgency": "stat"}],
            "diagnosis": "Chest pain (R07.9)",
            "recent_orders": [{"test": "Troponin", "date": one_hour_ago, "result": "0.02"}],
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        # Troponins should never be duplicates (serial testing)
        assert validated[0]["status"] == "approved"
    
    @pytest.mark.asyncio
    async def test_blood_cultures_never_duplicate(self, agent, basic_patient):
        """Test that blood cultures are never flagged as duplicates."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        
        context = {
            "orders": [{"test": "Blood cultures", "order_type": "lab", "urgency": "stat"}],
            "diagnosis": "Sepsis",
            "recent_orders": [{"test": "Blood cultures", "date": yesterday, "result": "Pending"}],
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "approved"


class TestContraindications:
    """Test contraindication checking."""
    
    @pytest.mark.asyncio
    async def test_contrast_allergy_contraindication(self, agent, contrast_allergic_patient):
        """Test contrast allergy contraindication detection."""
        context = {
            "orders": [{"test": "CT abdomen with contrast", "order_type": "imaging", "urgency": "routine"}],
            "diagnosis": "Abdominal pain",
            "patient_context": contrast_allergic_patient
        }
        
        result = await agent.execute(context)
        
        # Should have contraindication warning
        contraindications = result.data["contraindications"]
        assert len(contraindications) > 0
        assert any("contrast" in ci.lower() and "allergy" in ci.lower() for ci in contraindications)
    
    @pytest.mark.asyncio
    async def test_contrast_renal_contraindication(self, agent, renal_impaired_patient):
        """Test contrast contraindication for renal impairment."""
        context = {
            "orders": [{"test": "CT abdomen", "order_type": "imaging", "urgency": "routine"}],
            "diagnosis": "Abdominal pain",
            "patient_context": renal_impaired_patient
        }
        
        result = await agent.execute(context)
        
        contraindications = result.data["contraindications"]
        assert len(contraindications) > 0
        assert any("egfr" in ci.lower() or "renal" in ci.lower() or "nephropathy" in ci.lower() 
                   for ci in contraindications)
    
    @pytest.mark.asyncio
    async def test_mri_pacemaker_contraindication(self, agent, pacemaker_patient):
        """Test MRI contraindication for pacemaker."""
        context = {
            "orders": [{"test": "MRI brain", "order_type": "imaging", "urgency": "routine"}],
            "diagnosis": "Headache evaluation",
            "patient_context": pacemaker_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "contraindicated"
        assert any("pacemaker" in ci.lower() for ci in validated[0]["contraindications"])
    
    @pytest.mark.asyncio
    async def test_gadolinium_low_egfr_contraindication(self, agent, renal_impaired_patient):
        """Test gadolinium contraindication for low eGFR."""
        context = {
            "orders": [{"test": "MRI with contrast", "order_type": "imaging", "urgency": "routine"}],
            "diagnosis": "Tumor evaluation",
            "patient_context": renal_impaired_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        # Should be contraindicated or have warnings
        has_renal_warning = any(
            "egfr" in ci.lower() or "nsf" in ci.lower() or "nephrogenic" in ci.lower()
            for ci in validated[0].get("contraindications", [])
        )
        assert has_renal_warning or validated[0]["status"] == "contraindicated"
    
    @pytest.mark.asyncio
    async def test_pregnancy_ct_contraindication(self, agent, pregnant_patient):
        """Test CT contraindication for pregnancy."""
        context = {
            "orders": [{"test": "CT abdomen/pelvis", "order_type": "imaging", "urgency": "routine"}],
            "diagnosis": "Abdominal pain",
            "patient_context": pregnant_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        # Should have pregnancy warning
        has_pregnancy_warning = any(
            "pregnant" in ci.lower() or "pregnancy" in ci.lower()
            for ci in validated[0].get("contraindications", [])
        )
        assert has_pregnancy_warning or validated[0]["status"] == "contraindicated"
    
    @pytest.mark.asyncio
    async def test_pregnancy_allows_ultrasound(self, agent, pregnant_patient):
        """Test that ultrasound is allowed in pregnancy."""
        context = {
            "orders": [{"test": "Ultrasound abdomen", "order_type": "imaging", "urgency": "routine"}],
            "diagnosis": "Abdominal pain",
            "patient_context": pregnant_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "approved"
        # Should have no pregnancy-related contraindications
        pregnancy_contraindications = [
            ci for ci in validated[0].get("contraindications", [])
            if "pregnant" in ci.lower()
        ]
        assert len(pregnancy_contraindications) == 0
    
    @pytest.mark.asyncio
    async def test_no_contraindications(self, agent, basic_patient):
        """Test order with no contraindications."""
        context = {
            "orders": [{"test": "CBC", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Anemia workup",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "approved"
        assert len(validated[0]["contraindications"]) == 0
    
    @pytest.mark.asyncio
    async def test_multiple_contraindications(self, agent):
        """Test patient with multiple contraindications."""
        multi_risk_patient = {
            "age": 75,
            "sex": "F",
            "creatinine": 3.0,
            "egfr": 22,
            "allergies": ["Contrast dye", "Shellfish"],
            "pregnancy_status": "not_pregnant",
            "conditions": ["CKD Stage 4"],
            "has_pacemaker": True
        }
        
        context = {
            "orders": [{"test": "MRI brain", "order_type": "imaging", "urgency": "routine"}],
            "diagnosis": "Stroke workup",
            "patient_context": multi_risk_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        # Should have pacemaker contraindication at minimum
        assert validated[0]["status"] == "contraindicated"


class TestProtocolBasedSuggestions:
    """Test protocol-based test suggestions."""
    
    @pytest.mark.asyncio
    async def test_sepsis_protocol_suggestions(self, agent, basic_patient):
        """Test sepsis protocol suggests appropriate tests."""
        context = {
            "orders": [{"test": "CBC", "order_type": "lab", "urgency": "stat"}],
            "diagnosis": "Sepsis (A41.9)",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        suggestions = result.data["suggested_additions"]
        suggested_tests = [s["test"] for s in suggestions]
        
        # Should suggest critical sepsis workup tests
        assert any("lactate" in t.lower() for t in suggested_tests)
        assert any("blood cultures" in t.lower() for t in suggested_tests)
    
    @pytest.mark.asyncio
    async def test_chest_pain_protocol_suggestions(self, agent, basic_patient):
        """Test chest pain protocol suggests appropriate tests."""
        context = {
            "orders": [{"test": "EKG", "order_type": "procedure", "urgency": "stat"}],
            "diagnosis": "Chest pain (R07.9)",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        suggestions = result.data["suggested_additions"]
        suggested_tests = [s["test"].lower() for s in suggestions]
        
        # Should suggest troponin for chest pain
        assert any("troponin" in t for t in suggested_tests)
    
    @pytest.mark.asyncio
    async def test_dka_protocol_suggestions(self, agent, basic_patient):
        """Test DKA protocol suggests appropriate tests."""
        context = {
            "orders": [{"test": "Glucose", "order_type": "lab", "urgency": "stat"}],
            "diagnosis": "Diabetic ketoacidosis (E10.10)",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        suggestions = result.data["suggested_additions"]
        suggested_tests = [s["test"].lower() for s in suggestions]
        
        # Should suggest BMP and blood gas
        assert any("bmp" in t or "metabolic" in t for t in suggested_tests)
        assert any("gas" in t or "beta-hydroxybutyrate" in t for t in suggested_tests)
    
    @pytest.mark.asyncio
    async def test_stroke_protocol_suggestions(self, agent, basic_patient):
        """Test stroke protocol suggests appropriate tests."""
        context = {
            "orders": [{"test": "CT head", "order_type": "imaging", "urgency": "stat"}],
            "diagnosis": "Stroke (I63.9)",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        suggestions = result.data["suggested_additions"]
        suggested_tests = [s["test"].lower() for s in suggestions]
        
        # Should suggest glucose and coagulation studies
        assert any("glucose" in t for t in suggested_tests)
        assert any("pt" in t or "inr" in t or "ptt" in t for t in suggested_tests)
    
    @pytest.mark.asyncio
    async def test_pneumonia_protocol_suggestions(self, agent, basic_patient):
        """Test pneumonia protocol suggests appropriate tests."""
        context = {
            "orders": [{"test": "CBC", "order_type": "lab", "urgency": "stat"}],
            "diagnosis": "Pneumonia (J18.9)",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        suggestions = result.data["suggested_additions"]
        suggested_tests = [s["test"].lower() for s in suggestions]
        
        # Should suggest chest x-ray
        assert any("chest" in t and ("x-ray" in t or "xray" in t) for t in suggested_tests)
    
    @pytest.mark.asyncio
    async def test_aki_protocol_suggestions(self, agent, basic_patient):
        """Test AKI protocol suggests appropriate tests."""
        context = {
            "orders": [{"test": "Creatinine", "order_type": "lab", "urgency": "stat"}],
            "diagnosis": "Acute kidney injury (N17.9)",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        suggestions = result.data["suggested_additions"]
        suggested_tests = [s["test"].lower() for s in suggestions]
        
        # Should suggest urinalysis and renal ultrasound
        assert any("urinalysis" in t or "urine" in t for t in suggested_tests)
    
    @pytest.mark.asyncio
    async def test_missing_critical_sepsis_tests(self, agent, basic_patient):
        """Test that missing critical tests are flagged as critical priority."""
        context = {
            "orders": [{"test": "CBC", "order_type": "lab", "urgency": "stat"}],
            "diagnosis": "Sepsis",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        suggestions = result.data["suggested_additions"]
        critical_suggestions = [s for s in suggestions if s["priority"] == "critical"]
        
        # Should have critical priority suggestions
        assert len(critical_suggestions) > 0
    
    @pytest.mark.asyncio
    async def test_no_suggestions_complete_workup(self, agent, basic_patient):
        """Test minimal suggestions when workup is complete."""
        context = {
            "orders": [
                {"test": "CBC with differential", "order_type": "lab", "urgency": "stat"},
                {"test": "CMP", "order_type": "lab", "urgency": "stat"},
                {"test": "Blood cultures", "order_type": "lab", "urgency": "stat"},
                {"test": "Lactate", "order_type": "lab", "urgency": "stat"},
                {"test": "Procalcitonin", "order_type": "lab", "urgency": "stat"},
                {"test": "Urinalysis", "order_type": "lab", "urgency": "stat"},
                {"test": "Chest X-ray", "order_type": "imaging", "urgency": "stat"},
            ],
            "diagnosis": "Sepsis (A41.9)",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        # Should have fewer critical suggestions since workup is mostly complete
        suggestions = result.data["suggested_additions"]
        critical = [s for s in suggestions if s["priority"] == "critical"]
        # Most critical tests already ordered
        assert len(critical) <= 2


class TestPanelRecommendations:
    """Test panel vs individual test recommendations."""
    
    @pytest.mark.asyncio
    async def test_recommend_cmp_over_bmp(self, agent, basic_patient):
        """Test recommendation of CMP over BMP."""
        context = {
            "orders": [{"test": "BMP", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Metabolic workup",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        panel_recs = result.data["panel_recommendations"]
        assert any("cmp" in r.lower() for r in panel_recs)
    
    @pytest.mark.asyncio
    async def test_recommend_cbc_with_diff(self, agent, basic_patient):
        """Test recommendation of CBC with diff for infection."""
        context = {
            "orders": [{"test": "CBC", "order_type": "lab", "urgency": "stat"}],
            "diagnosis": "Sepsis evaluation",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        panel_recs = result.data["panel_recommendations"]
        assert any("differential" in r.lower() for r in panel_recs)
    
    @pytest.mark.asyncio
    async def test_recommend_lipid_panel(self, agent, basic_patient):
        """Test lipid panel is appropriately ordered."""
        context = {
            "orders": [{"test": "Lipid panel", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Hyperlipidemia screening",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "approved"
    
    @pytest.mark.asyncio
    async def test_recommend_hepatic_panel(self, agent, basic_patient):
        """Test hepatic panel recommendation."""
        context = {
            "orders": [{"test": "Hepatic function panel", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Liver disease evaluation",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        validated = result.data["validated_orders"]
        assert validated[0]["status"] == "approved"
    
    @pytest.mark.asyncio
    async def test_no_panel_recommendation(self, agent, basic_patient):
        """Test no panel recommendation when already ordering appropriate panel."""
        context = {
            "orders": [{"test": "CMP", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Metabolic workup",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        panel_recs = result.data["panel_recommendations"]
        # Should not recommend CMP since already ordering it
        assert not any("bmp" in r.lower() and "cmp" in r.lower() for r in panel_recs) or len(panel_recs) == 0


class TestCostOptimization:
    """Test cost optimization recommendations."""
    
    @pytest.mark.asyncio
    async def test_cost_optimization_cmp_vs_bmp(self, agent, basic_patient):
        """Test cost optimization suggests CMP over BMP."""
        context = {
            "orders": [{"test": "BMP", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Electrolyte check",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        cost_opt = result.data["cost_optimization"]
        if cost_opt:
            assert "cmp" in cost_opt["suggestion"].lower()
    
    @pytest.mark.asyncio
    async def test_cost_optimization_panel_vs_individual(self, agent, basic_patient):
        """Test cost optimization recommends panel over individual tests."""
        context = {
            "orders": [{"test": "BMP", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Full metabolic assessment",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        cost_opt = result.data["cost_optimization"]
        if cost_opt:
            assert cost_opt["suggestion"] != ""
    
    @pytest.mark.asyncio
    async def test_cost_optimization_savings(self, agent, basic_patient):
        """Test cost optimization calculates savings/value correctly."""
        context = {
            "orders": [{"test": "BMP", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Labs",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        cost_opt = result.data["cost_optimization"]
        if cost_opt:
            # CMP costs more but provides more value
            assert cost_opt["optimized_cost"] >= cost_opt["current_cost"]
            assert "additional" in cost_opt["suggestion"].lower()
    
    @pytest.mark.asyncio
    async def test_no_cost_optimization_opportunity(self, agent, basic_patient):
        """Test no cost optimization when already optimal."""
        context = {
            "orders": [{"test": "CMP", "order_type": "lab", "urgency": "routine"}],
            "diagnosis": "Metabolic workup",
            "patient_context": basic_patient
        }
        
        result = await agent.execute(context)
        
        # When CMP already ordered, no optimization for BMP->CMP
        cost_opt = result.data["cost_optimization"]
        # Should be None or not suggest CMP
        if cost_opt:
            assert "bmp" not in cost_opt["suggestion"].lower() or "cmp" not in cost_opt["suggestion"].lower()


class TestDataclasses:
    """Test dataclass functionality."""
    
    def test_order_to_dict(self):
        """Test Order to_dict method."""
        order = Order(test="CBC", order_type=OrderType.LAB, urgency=Urgency.STAT)
        d = order.to_dict()
        
        assert d["test"] == "CBC"
        assert d["order_type"] == "lab"
        assert d["urgency"] == "stat"
    
    def test_recent_order_to_dict(self):
        """Test RecentOrder to_dict method."""
        recent = RecentOrder(test="BMP", date=date(2026, 1, 30), result="Normal")
        d = recent.to_dict()
        
        assert d["test"] == "BMP"
        assert d["date"] == "2026-01-30"
        assert d["result"] == "Normal"
    
    def test_validated_order_to_dict(self):
        """Test ValidatedOrder to_dict method."""
        validated = ValidatedOrder(
            test="CBC",
            status=OrderStatus.APPROVED,
            issue=None,
            recommendation="Consider CBC with diff",
            contraindications=[]
        )
        d = validated.to_dict()
        
        assert d["test"] == "CBC"
        assert d["status"] == "approved"
        assert d["recommendation"] == "Consider CBC with diff"
    
    def test_suggested_order_to_dict(self):
        """Test SuggestedOrder to_dict method."""
        suggested = SuggestedOrder(
            test="Lactate",
            rationale="Required for sepsis",
            urgency=Urgency.STAT,
            priority=Priority.CRITICAL,
            order_type=OrderType.LAB
        )
        d = suggested.to_dict()
        
        assert d["test"] == "Lactate"
        assert d["urgency"] == "stat"
        assert d["priority"] == "critical"
    
    def test_cost_optimization_to_dict(self):
        """Test CostOptimization to_dict method."""
        cost_opt = CostOptimization(
            current_cost=45.0,
            optimized_cost=50.0,
            savings=-5.0,
            suggestion="Order CMP instead of BMP"
        )
        d = cost_opt.to_dict()
        
        assert d["current_cost"] == 45.0
        assert d["optimized_cost"] == 50.0
        assert d["savings"] == -5.0


class TestEnums:
    """Test enum values."""
    
    def test_order_type_values(self):
        """Test OrderType enum values."""
        assert OrderType.LAB.value == "lab"
        assert OrderType.IMAGING.value == "imaging"
        assert OrderType.PROCEDURE.value == "procedure"
    
    def test_urgency_values(self):
        """Test Urgency enum values."""
        assert Urgency.STAT.value == "stat"
        assert Urgency.URGENT.value == "urgent"
        assert Urgency.ROUTINE.value == "routine"
        assert Urgency.SCHEDULED.value == "scheduled"
    
    def test_order_status_values(self):
        """Test OrderStatus enum values."""
        assert OrderStatus.APPROVED.value == "approved"
        assert OrderStatus.DUPLICATE.value == "duplicate"
        assert OrderStatus.CONTRAINDICATED.value == "contraindicated"
        assert OrderStatus.QUESTIONABLE.value == "questionable"
    
    def test_priority_values(self):
        """Test Priority enum values."""
        assert Priority.CRITICAL.value == "critical"
        assert Priority.HIGH.value == "high"
        assert Priority.MEDIUM.value == "medium"
        assert Priority.LOW.value == "low"


class TestPerformance:
    """Test performance requirements."""
    
    @pytest.mark.asyncio
    async def test_processing_time_under_500ms(self, agent, basic_patient):
        """Test that processing completes under 500ms."""
        import time
        
        context = {
            "orders": [
                {"test": "CBC", "order_type": "lab", "urgency": "stat"},
                {"test": "CMP", "order_type": "lab", "urgency": "stat"},
                {"test": "Troponin", "order_type": "lab", "urgency": "stat"},
                {"test": "Chest X-ray", "order_type": "imaging", "urgency": "stat"},
            ],
            "diagnosis": "Chest pain evaluation",
            "recent_orders": [
                {"test": "CBC", "date": (date.today() - timedelta(days=5)).isoformat()},
            ],
            "patient_context": basic_patient
        }
        
        start_time = time.time()
        result = await agent.execute(context)
        elapsed_time = time.time() - start_time
        
        assert elapsed_time < 0.5, f"Processing took {elapsed_time:.3f}s (>500ms)"
        assert result.data is not None
