"""Tests for all 10 Phoenix Guardian AI Agents.

Validates that all 10 agents can be instantiated, have required attributes,
and produce valid outputs for their core functions.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ============================================================================
# Agent Import Tests
# ============================================================================

class TestAgentImports:
    """Verify all 10 agents can be imported."""

    def test_import_scribe_agent(self):
        from phoenix_guardian.agents.scribe import ScribeAgent
        assert ScribeAgent is not None

    def test_import_safety_agent(self):
        from phoenix_guardian.agents.safety import SafetyAgent
        assert SafetyAgent is not None

    def test_import_navigator_agent(self):
        from phoenix_guardian.agents.navigator import NavigatorAgent
        assert NavigatorAgent is not None

    def test_import_coding_agent(self):
        from phoenix_guardian.agents.coding import CodingAgent
        assert CodingAgent is not None

    def test_import_sentinel_agent(self):
        from phoenix_guardian.agents.sentinel import SentinelAgent
        assert SentinelAgent is not None

    def test_import_order_management_agent(self):
        from phoenix_guardian.agents.order_management import OrderManagementAgent
        assert OrderManagementAgent is not None

    def test_import_deception_detection_agent(self):
        from phoenix_guardian.agents.deception_detection import DeceptionDetectionAgent
        assert DeceptionDetectionAgent is not None

    def test_import_fraud_agent(self):
        from phoenix_guardian.agents.fraud import FraudAgent
        assert FraudAgent is not None

    def test_import_clinical_decision_agent(self):
        from phoenix_guardian.agents.clinical_decision import ClinicalDecisionAgent
        assert ClinicalDecisionAgent is not None

    def test_import_pharmacy_agent(self):
        from phoenix_guardian.agents.pharmacy import PharmacyAgent
        assert PharmacyAgent is not None


# ============================================================================
# FraudAgent Tests
# ============================================================================

class TestFraudAgent:
    """Tests for Fraud Detection Agent."""

    @pytest.fixture
    def agent(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from phoenix_guardian.agents.fraud import FraudAgent
            return FraudAgent()

    def test_detect_unbundling_violation(self, agent):
        """Test detection of NCCI unbundling violation."""
        result = agent.detect_unbundling(["36415", "80053"])
        assert result["violations_detected"] is True
        assert len(result["violations"]) > 0
        assert result["violations"][0]["type"] == "unbundling"

    def test_detect_unbundling_no_violation(self, agent):
        """Test no false positive when codes aren't bundled."""
        result = agent.detect_unbundling(["99213", "71045"])
        assert result["violations_detected"] is False
        assert len(result["violations"]) == 0

    def test_detect_unbundling_multiple_violations(self, agent):
        """Test detection of multiple unbundling violations."""
        result = agent.detect_unbundling(["99213", "99214", "99215"])
        assert result["violations_detected"] is True
        assert len(result["violations"]) >= 2

    def test_detect_upcoding_valid(self, agent):
        """Test no upcoding flag for appropriate billing."""
        result = agent.detect_upcoding(
            encounter_complexity="low",
            billed_cpt_code="99213",
            encounter_duration=20,
            documented_elements=8,
        )
        assert result["upcoding_detected"] is False

    def test_detect_upcoding_flagged(self, agent):
        """Test upcoding detection for inappropriate billing."""
        result = agent.detect_upcoding(
            encounter_complexity="straightforward",
            billed_cpt_code="99215",
            encounter_duration=10,
            documented_elements=4,
        )
        assert result["upcoding_detected"] is True
        assert len(result["issues"]) >= 2
        assert result["severity"] == "HIGH"

    def test_detect_upcoding_duration_only(self, agent):
        """Test upcoding detection for insufficient duration only."""
        result = agent.detect_upcoding(
            encounter_complexity="moderate",
            billed_cpt_code="99214",
            encounter_duration=10,  # 25 required
            documented_elements=10,
        )
        assert result["upcoding_detected"] is True
        assert any("Duration" in issue for issue in result["issues"])

    def test_suggest_appropriate_code(self, agent):
        """Test code suggestion logic."""
        code = agent._suggest_appropriate_code("low", 20, 8)
        assert code == "99213"

    def test_suggest_appropriate_code_minimal(self, agent):
        """Test code suggestion for minimal documentation."""
        code = agent._suggest_appropriate_code("minimal", 5, 0)
        assert code == "99211"

    @pytest.mark.asyncio
    async def test_process_full(self, agent):
        """Test full fraud detection pipeline."""
        with patch.object(agent, "_call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = '{"risk_score": 0.3, "findings": [], "recommendation": "Low risk"}'
            result = await agent.process({
                "procedure_codes": ["99213", "71045"],
                "billed_cpt_code": "99213",
                "encounter_complexity": "low",
                "encounter_duration": 20,
                "documented_elements": 8,
                "clinical_note": "Routine follow-up visit",
            })
            assert result["agent"] == "fraud_detection"
            assert "risk_level" in result
            assert "risk_score" in result

    @pytest.mark.asyncio
    async def test_process_high_risk(self, agent):
        """Test fraud detection with high-risk scenario."""
        result = await agent.process({
            "procedure_codes": ["36415", "80053"],  # bundled codes
            "billed_cpt_code": "99215",
            "encounter_complexity": "straightforward",
            "encounter_duration": 5,
            "documented_elements": 3,
        })
        assert result["risk_score"] > 0.3
        assert len(result["findings"]) > 0


# ============================================================================
# ClinicalDecisionAgent Tests
# ============================================================================

class TestClinicalDecisionAgent:
    """Tests for Clinical Decision Support Agent."""

    @pytest.fixture
    def agent(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from phoenix_guardian.agents.clinical_decision import ClinicalDecisionAgent
            return ClinicalDecisionAgent()

    def test_chads2_vasc_low_risk(self, agent):
        """Test CHA₂DS₂-VASc score for low-risk patient."""
        result = agent.calculate_risk_scores("afib", {
            "age": 40, "sex": "male",
            "chf": False, "hypertension": False, "diabetes": False,
            "stroke_history": False, "vascular_disease": False,
        })
        assert result["score_name"] == "CHA₂DS₂-VASc"
        assert result["score"] == 0
        assert result["risk_level"] == "Low"

    def test_chads2_vasc_high_risk(self, agent):
        """Test CHA₂DS₂-VASc score for high-risk patient."""
        result = agent.calculate_risk_scores("afib", {
            "age": 80, "sex": "female",
            "chf": True, "hypertension": True, "diabetes": True,
            "stroke_history": True, "vascular_disease": True,
        })
        assert result["score"] >= 8
        assert result["risk_level"] == "High"
        assert "anticoagulation" in result["recommendation"].lower()

    def test_heart_score_low(self, agent):
        """Test HEART score for low-risk chest pain."""
        result = agent.calculate_risk_scores("chest pain", {
            "history": "slightly_suspicious",
            "ekg": "normal",
            "age": 35,
            "risk_factor_count": 0,
            "troponin": "normal",
        })
        assert result["score_name"] == "HEART Score"
        assert result["score"] <= 3
        assert result["risk_level"] == "Low"

    def test_heart_score_high(self, agent):
        """Test HEART score for high-risk chest pain."""
        result = agent.calculate_risk_scores("chest pain", {
            "history": "highly_suspicious",
            "ekg": "significant_st_deviation",
            "age": 70,
            "risk_factor_count": 4,
            "troponin": ">=3x_normal",
        })
        assert result["score"] >= 8
        assert result["risk_level"] == "High"

    def test_wells_score_pe_unlikely(self, agent):
        """Test Wells score for PE unlikely."""
        result = agent.calculate_risk_scores("pe", {
            "dvt_signs": False,
            "pe_most_likely": False,
            "heart_rate_over_100": True,
            "immobilization_surgery": False,
            "previous_dvt_pe": False,
            "hemoptysis": False,
            "active_cancer": False,
        })
        assert result["score_name"] == "Wells Score (PE)"
        assert result["score"] <= 4.0
        assert result["risk_level"] == "PE Unlikely"

    def test_wells_score_pe_likely(self, agent):
        """Test Wells score for PE likely."""
        result = agent.calculate_risk_scores("pe", {
            "dvt_signs": True,
            "pe_most_likely": True,
            "heart_rate_over_100": True,
        })
        assert result["score"] > 4.0
        assert result["risk_level"] == "PE Likely"

    def test_curb65_low(self, agent):
        """Test CURB-65 for low-severity pneumonia."""
        result = agent.calculate_risk_scores("pneumonia", {
            "confusion": False,
            "urea": 5,
            "respiratory_rate": 18,
            "systolic_bp": 120,
            "diastolic_bp": 75,
            "age": 50,
        })
        assert result["score_name"] == "CURB-65"
        assert result["score"] <= 1
        assert result["risk_level"] == "Low"

    def test_curb65_high(self, agent):
        """Test CURB-65 for severe pneumonia."""
        result = agent.calculate_risk_scores("pneumonia", {
            "confusion": True,
            "urea": 10,
            "respiratory_rate": 35,
            "systolic_bp": 80,
            "age": 70,
        })
        assert result["score"] >= 4
        assert result["risk_level"] == "High"

    def test_unsupported_condition(self, agent):
        """Test error for unsupported condition."""
        result = agent.calculate_risk_scores("unknown_condition", {})
        assert "error" in result
        assert "supported" in result

    @pytest.mark.asyncio
    async def test_recommend_treatment(self, agent):
        """Test treatment recommendation."""
        with patch.object(agent, "_call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = json.dumps({
                "first_line": {"treatment": "Lisinopril 10mg", "guideline": "AHA", "evidence_level": "A", "dosing": "10mg daily"},
                "alternatives": [],
                "contraindications": [],
                "monitoring": ["BP every 2 weeks"],
                "drug_interactions": [],
                "disclaimer": "Physician review required",
            })
            result = await agent.recommend_treatment(
                diagnosis="Hypertension",
                patient_factors={"age": 55, "sex": "male"},
                current_medications=[],
            )
            assert result["agent"] == "clinical_decision_support"
            assert "recommendations" in result

    @pytest.mark.asyncio
    async def test_generate_differential(self, agent):
        """Test differential diagnosis generation."""
        with patch.object(agent, "_call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = json.dumps({
                "differentials": [{"diagnosis": "Tension headache", "likelihood": "high", "key_features": ["bilateral"], "workup": ["clinical"]}],
                "red_flags": ["thunderclap onset"],
                "disclaimer": "Physician judgment required",
            })
            result = await agent.generate_differential(
                symptoms=["headache", "nausea"],
                patient_factors={"age": 35, "sex": "female"},
            )
            assert result["agent"] == "clinical_decision_support"
            assert "result" in result


# ============================================================================
# PharmacyAgent Tests
# ============================================================================

class TestPharmacyAgent:
    """Tests for Pharmacy Integration Agent."""

    @pytest.fixture
    def agent(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from phoenix_guardian.agents.pharmacy import PharmacyAgent
            return PharmacyAgent()

    def test_check_formulary_generic(self, agent):
        """Test formulary check for generic medication."""
        result = agent.check_formulary("lisinopril", "BlueCross", "P001")
        assert result["on_formulary"] is True
        assert result["tier"] == 1
        assert result["copay"] == 10.00
        assert result["generic_available"] is True

    def test_check_formulary_brand(self, agent):
        """Test formulary check for brand medication."""
        result = agent.check_formulary("eliquis", "BlueCross", "P001")
        assert result["on_formulary"] is True
        assert result["tier"] == 3
        assert result["copay"] == 50.00
        assert len(result["alternatives"]) > 0

    def test_check_formulary_specialty(self, agent):
        """Test formulary check for specialty medication."""
        result = agent.check_formulary("humira", "BlueCross", "P001")
        assert result["on_formulary"] is True
        assert result["tier"] == 5
        assert result["prior_auth_required"] is True

    def test_check_formulary_not_found(self, agent):
        """Test formulary check for unknown medication."""
        result = agent.check_formulary("unknownmed123", "BlueCross", "P001")
        assert result["on_formulary"] is False
        assert result["tier"] == 6

    def test_check_formulary_cost_saving(self, agent):
        """Test cost-saving suggestion for expensive medication."""
        result = agent.check_formulary("eliquis", "BlueCross", "P001")
        assert "cost_saving_suggestion" in result
        assert result["cost_saving_suggestion"]["savings"] > 0

    def test_prior_auth_required(self, agent):
        """Test PA check for medication needing PA."""
        result = agent.check_prior_auth_required("jardiance", "Type 2 Diabetes", "BlueCross")
        assert result["prior_auth_required"] is True
        assert len(result["criteria"]) > 0
        assert "turnaround" in result["approval_turnaround"].lower() or "hours" in result["approval_turnaround"].lower()

    def test_prior_auth_not_required(self, agent):
        """Test PA check for medication not needing PA."""
        result = agent.check_prior_auth_required("lisinopril", "Hypertension", "BlueCross")
        assert result["prior_auth_required"] is False

    @pytest.mark.asyncio
    async def test_send_erx(self, agent):
        """Test electronic prescription sending."""
        result = await agent.send_erx(
            prescription={
                "medication": "lisinopril",
                "dosage": "10mg",
                "frequency": "once daily",
                "quantity": 30,
                "refills": 3,
            },
            pharmacy_ncpdp="1234567",
            patient={"name": "John Doe", "dob": "1980-01-01"},
        )
        assert result["status"] == "sent"
        assert result["confirmation_number"].startswith("RX-")
        assert "script_message" in result
        assert result["script_message"]["header"]["message_type"] == "NewRx"

    @pytest.mark.asyncio
    async def test_send_erx_missing_fields(self, agent):
        """Test e-prescribing with missing fields."""
        result = await agent.send_erx(
            prescription={"medication": "lisinopril"},  # missing dosage, frequency, quantity
            pharmacy_ncpdp="1234567",
            patient={},
        )
        assert result["status"] == "error"
        assert "Missing" in result["message"]

    @pytest.mark.asyncio
    async def test_drug_utilization_review(self, agent):
        """Test DUR with mock AI response."""
        with patch.object(agent, "_call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = json.dumps({
                "interactions": [],
                "allergy_alerts": [],
                "duplicate_therapy": [],
                "dose_check": {"appropriate": True, "concerns": []},
                "overall_risk": "low",
                "recommendation": "No significant concerns",
            })
            result = await agent.drug_utilization_review(
                prescription={"medication": "lisinopril", "dosage": "10mg"},
                current_medications=["metformin"],
                allergies=["penicillin"],
                patient_factors={"age": 55, "weight": 80, "gfr": 90},
            )
            assert result["agent"] == "pharmacy"
            assert result["dur_result"]["overall_risk"] == "low"


# ============================================================================
# DeceptionDetectionAgent Tests
# ============================================================================

class TestDeceptionDetectionAgent:
    """Tests for Deception Detection Agent."""

    @pytest.fixture
    def agent(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from phoenix_guardian.agents.deception_detection import DeceptionDetectionAgent
            return DeceptionDetectionAgent()

    def test_rule_based_timeline_discrepancy(self, agent):
        """Test rule-based timeline discrepancy detection."""
        flags = agent._rule_based_consistency_check(
            history=["Pain started last week"],
            current="Pain started today",
        )
        assert len(flags) > 0
        assert flags[0]["type"] == "timeline_discrepancy"

    def test_rule_based_contradiction(self, agent):
        """Test rule-based contradiction detection."""
        flags = agent._rule_based_consistency_check(
            history=["Patient denies chest pain"],
            current="Patient reports severe pain",
        )
        assert len(flags) > 0
        assert flags[0]["type"] == "contradiction"

    def test_rule_based_no_flags(self, agent):
        """Test no false positives for consistent statements."""
        flags = agent._rule_based_consistency_check(
            history=["Patient has mild headache"],
            current="Headache is getting better with medication",
        )
        assert len(flags) == 0

    @pytest.mark.asyncio
    async def test_analyze_consistency(self, agent):
        """Test consistency analysis with mock AI."""
        with patch.object(agent, "_call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = json.dumps({
                "consistency_score": 85,
                "contradictions": [],
                "timeline_issues": [],
                "clinical_impact": "low",
                "recommendation": "No significant concerns",
            })
            result = await agent.analyze_consistency(
                patient_history=["Feels fine today"],
                current_statement="Still feeling well, no new symptoms",
            )
            assert result["agent"] == "deception_detection"
            assert result["consistency_score"] == 85
            assert "disclaimer" in result

    @pytest.mark.asyncio
    async def test_detect_drug_seeking(self, agent):
        """Test drug-seeking behavior detection."""
        with patch.object(agent, "_call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = json.dumps({
                "risk_level": "moderate",
                "identified_red_flags": ["Requests specific opioid"],
                "mitigating_factors": ["Documented chronic pain condition"],
                "recommendation": "Check PDMP, review pain management agreement",
                "pdmp_check_recommended": True,
            })
            result = await agent.detect_drug_seeking(
                patient_request="I need oxycodone 30mg, nothing else works for my back",
                medical_history="Chronic lower back pain",
                current_medications=["ibuprofen"],
            )
            assert result["agent"] == "deception_detection"
            assert result["risk_level"] == "moderate"
            assert result["pdmp_check_recommended"] is True
            # Should flag controlled substance request
            assert len(result["rule_based_flags"]) > 0

    @pytest.mark.asyncio
    async def test_analyze_consistency_no_statement(self, agent):
        """Test error handling for missing statement."""
        result = await agent.analyze_consistency(
            patient_history=[],
            current_statement="",
        )
        assert "error" in result


# ============================================================================
# OrderManagementAgent Tests
# ============================================================================

class TestOrderManagementAgent:
    """Tests for Order Management Agent."""

    @pytest.fixture
    def agent(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from phoenix_guardian.agents.order_management import OrderManagementAgent
            return OrderManagementAgent()

    @pytest.mark.asyncio
    async def test_suggest_labs_diabetes(self, agent):
        """Test lab suggestions for diabetes."""
        with patch.object(agent, "_call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = "[]"
            result = await agent.suggest_labs(
                clinical_note="Follow-up for diabetes management",
                diagnosis="diabetes",
                patient_age=55,
            )
            assert result["agent"] == "order_management"
            assert result["total_suggested"] > 0
            lab_names = [l["test_name"] for l in result["suggested_labs"]]
            assert "HbA1c" in lab_names

    @pytest.mark.asyncio
    async def test_suggest_labs_chest_pain(self, agent):
        """Test lab suggestions for chest pain."""
        with patch.object(agent, "_call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = "[]"
            result = await agent.suggest_labs(
                clinical_note="",
                diagnosis="chest pain",
                patient_age=60,
            )
            lab_names = [l["test_name"].lower() for l in result["suggested_labs"]]
            assert any("troponin" in name for name in lab_names)

    @pytest.mark.asyncio
    async def test_suggest_labs_age_screening(self, agent):
        """Test age-appropriate screening additions."""
        with patch.object(agent, "_call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = "[]"
            result = await agent.suggest_labs(
                clinical_note="Annual physical",
                diagnosis="wellness visit",
                patient_age=55,
            )
            lab_names = [l["test_name"] for l in result["suggested_labs"]]
            assert "Lipid Panel" in lab_names

    @pytest.mark.asyncio
    async def test_suggest_imaging_chest_pain(self, agent):
        """Test imaging suggestions for chest pain."""
        with patch.object(agent, "_call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = "[]"
            result = await agent.suggest_imaging(
                chief_complaint="chest pain",
                physical_exam="Tachycardic, diaphoretic",
                patient_age=60,
            )
            assert result["total_suggested"] > 0
            modalities = [i["modality"] for i in result["suggested_imaging"]]
            assert "chest_xray" in modalities

    @pytest.mark.asyncio
    async def test_suggest_imaging_pediatric_warning(self, agent):
        """Test radiation warning for pediatric imaging."""
        with patch.object(agent, "_call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = "[]"
            result = await agent.suggest_imaging(
                chief_complaint="abdominal pain",
                physical_exam="Tenderness RLQ",
                patient_age=10,
            )
            has_warning = any(
                "pediatric_warning" in study
                for study in result["suggested_imaging"]
            )
            assert has_warning

    @pytest.mark.asyncio
    async def test_generate_prescription(self, agent):
        """Test prescription generation."""
        with patch.object(agent, "_call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = json.dumps({
                "medication": "lisinopril",
                "dosage": "10mg",
                "frequency": "once daily",
                "route": "oral",
                "duration": "ongoing",
                "quantity": 30,
                "refills": 11,
                "counseling": ["May cause dry cough"],
                "monitoring": ["Renal function", "Potassium"],
                "black_box_warning": None,
            })
            result = await agent.generate_prescription(
                medication="lisinopril",
                condition="hypertension",
                patient_weight=80.0,
                patient_age=55,
            )
            assert result["agent"] == "order_management"
            assert result["prescription"]["medication"] == "lisinopril"


# ============================================================================
# All 10 Agents Summary Test
# ============================================================================

class TestAll10AgentsSummary:
    """Verify the complete 10-agent system."""

    def test_10_agent_classes_exist(self):
        """Verify all 10 agent classes can be imported."""
        from phoenix_guardian.agents.scribe import ScribeAgent
        from phoenix_guardian.agents.safety import SafetyAgent
        from phoenix_guardian.agents.navigator import NavigatorAgent
        from phoenix_guardian.agents.coding import CodingAgent
        from phoenix_guardian.agents.sentinel import SentinelAgent
        from phoenix_guardian.agents.order_management import OrderManagementAgent
        from phoenix_guardian.agents.deception_detection import DeceptionDetectionAgent
        from phoenix_guardian.agents.fraud import FraudAgent
        from phoenix_guardian.agents.clinical_decision import ClinicalDecisionAgent
        from phoenix_guardian.agents.pharmacy import PharmacyAgent

        agents = [
            ScribeAgent, SafetyAgent, NavigatorAgent, CodingAgent, SentinelAgent,
            OrderManagementAgent, DeceptionDetectionAgent, FraudAgent,
            ClinicalDecisionAgent, PharmacyAgent,
        ]
        assert len(agents) == 10, f"Expected 10 agents, got {len(agents)}"

    def test_all_agents_in_package_init(self):
        """Verify all new agents are exported from package __init__."""
        from phoenix_guardian.agents import (
            FraudAgent,
            ClinicalDecisionAgent,
            PharmacyAgent,
            DeceptionDetectionAgent,
            OrderManagementAgent,
        )
        assert FraudAgent is not None
        assert ClinicalDecisionAgent is not None
        assert PharmacyAgent is not None
        assert DeceptionDetectionAgent is not None
        assert OrderManagementAgent is not None


# Need json import for test data
import json
