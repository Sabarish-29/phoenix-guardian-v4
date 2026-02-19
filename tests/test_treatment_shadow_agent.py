"""
Unit tests for TreatmentShadowAgent — Phoenix Guardian V5 Phase 1.

All external dependencies (DB, Redis, AI, OpenFDA) are mocked.
No network or database access required.

Run:
    pytest tests/test_treatment_shadow_agent.py -v
"""

import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Agent under test ──────────────────────────────────────────────────────

from phoenix_guardian.agents.treatment_shadow_agent import (
    TreatmentShadowAgent,
    SHADOW_LIBRARY,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def agent():
    """Create an agent instance with mocked AI service."""
    with patch(
        "phoenix_guardian.agents.treatment_shadow_agent.get_ai_service"
    ) as mock_ai_factory:
        mock_ai = MagicMock()
        mock_ai.chat = AsyncMock(
            return_value="B12 declining for 10 months. Moderate stage, reversible now. Start supplementation immediately."
        )
        mock_ai_factory.return_value = mock_ai
        a = TreatmentShadowAgent()
        yield a


# ── Test calculate_trend ──────────────────────────────────────────────────

class TestCalculateTrend:
    """Tests for TreatmentShadowAgent.calculate_trend()"""

    def test_declining(self, agent):
        """Patient D data: 620 → 540 → 480 → 410 → 350 → 310  →  declining ~-50%."""
        result = agent.calculate_trend([620, 540, 480, 410, 350, 310])
        assert result["direction"] == "declining"
        assert result["pct_change"] == pytest.approx(-50.0, abs=1)
        assert result["slope"] < 0
        assert result["r_squared"] > 0.9

    def test_declining_four_readings(self, agent):
        """4-reading variant: 498 → 412 → 310 → 210  →  declining ~-58%."""
        result = agent.calculate_trend([498, 412, 310, 210])
        assert result["direction"] == "declining"
        assert result["pct_change"] == pytest.approx(-57.8, abs=1)
        assert result["slope"] < 0

    def test_insufficient_data_single(self, agent):
        """Single reading → insufficient_data."""
        result = agent.calculate_trend([210])
        assert result["direction"] == "insufficient_data"
        assert result["slope"] == 0.0

    def test_insufficient_data_empty(self, agent):
        """Empty list → insufficient_data."""
        result = agent.calculate_trend([])
        assert result["direction"] == "insufficient_data"

    def test_stable(self, agent):
        """Near-identical readings → stable."""
        result = agent.calculate_trend([200, 201, 199, 200])
        assert result["direction"] == "stable"
        assert abs(result["pct_change"]) < 5

    def test_all_same(self, agent):
        """Identical readings → stable, slope = 0."""
        result = agent.calculate_trend([100, 100, 100, 100])
        assert result["direction"] == "stable"
        assert result["slope"] == 0.0
        assert result["r_squared"] == 1.0

    def test_rising(self, agent):
        """Rising values → rising direction."""
        result = agent.calculate_trend([100, 150, 200, 250])
        assert result["direction"] == "rising"
        assert result["pct_change"] > 0

    def test_trend_summary_not_empty(self, agent):
        """trend_summary should be a non-empty string."""
        result = agent.calculate_trend([620, 540, 480, 410])
        assert isinstance(result["trend_summary"], str)
        assert len(result["trend_summary"]) > 0


# ── Test SHADOW_LIBRARY ───────────────────────────────────────────────────

class TestShadowLibrary:
    """Verify SHADOW_LIBRARY has expected drugs and configs."""

    def test_has_metformin(self):
        assert "metformin" in SHADOW_LIBRARY
        entries = SHADOW_LIBRARY["metformin"]
        assert len(entries) >= 1
        assert entries[0]["watch_lab"] == "vitamin_b12"
        assert entries[0]["shadow_type"] == "Vitamin B12 Depletion"

    def test_has_atorvastatin(self):
        assert "atorvastatin" in SHADOW_LIBRARY
        assert SHADOW_LIBRARY["atorvastatin"][0]["watch_lab"] == "creatine_kinase"

    def test_has_lisinopril(self):
        assert "lisinopril" in SHADOW_LIBRARY
        assert SHADOW_LIBRARY["lisinopril"][0]["watch_lab"] == "creatinine"

    def test_has_amiodarone(self):
        assert "amiodarone" in SHADOW_LIBRARY

    def test_has_warfarin(self):
        assert "warfarin" in SHADOW_LIBRARY

    def test_all_entries_have_required_fields(self):
        required = {"shadow_type", "watch_lab", "watch_window_months", "severity_on_fire"}
        for drug, entries in SHADOW_LIBRARY.items():
            for entry in entries:
                for field in required:
                    assert field in entry, f"{drug} missing field: {field}"


# ── Test estimate_harm_timeline ───────────────────────────────────────────

class TestEstimateHarmTimeline:
    """Tests for TreatmentShadowAgent.estimate_harm_timeline()"""

    def test_moderate_declining(self, agent):
        """50% decline → current_stage should contain 'reversible'."""
        result = agent.estimate_harm_timeline(
            drug="metformin",
            lab_values=[620, 540, 480, 410, 350, 310],
            lab_dates=["2023-08-15", "2023-11-20", "2024-02-14",
                       "2024-06-10", "2024-10-05", "2025-01-18"],
            shadow_config=SHADOW_LIBRARY["metformin"][0],
        )
        assert "reversible" in result["current_stage"].lower()
        assert "Moderate" in result["current_stage"]
        assert result["harm_started_estimate"] != "Unknown"
        assert result["days_until_irreversible"] > 0

    def test_insufficient_data(self, agent):
        """Less than 2 values → insufficient."""
        result = agent.estimate_harm_timeline(
            drug="metformin",
            lab_values=[500],
            lab_dates=["2024-01-01"],
            shadow_config=SHADOW_LIBRARY["metformin"][0],
        )
        assert "insufficient" in result["current_stage"].lower()

    def test_mild_decline(self, agent):
        """<20% decline → mild stage."""
        result = agent.estimate_harm_timeline(
            drug="metformin",
            lab_values=[500, 480, 450],
            lab_dates=["2024-01-01", "2024-04-01", "2024-07-01"],
            shadow_config=SHADOW_LIBRARY["metformin"][0],
        )
        assert "Mild" in result["current_stage"]


# ── Test get_drug_risks ───────────────────────────────────────────────────

class TestGetDrugRisks:

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self, agent):
        """When OpenFDA times out, returns SHADOW_LIBRARY fallback."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await agent.get_drug_risks("metformin")
            assert len(result) >= 1
            assert result[0]["shadow_type"] == "Vitamin B12 Depletion"

    @pytest.mark.asyncio
    async def test_unknown_drug_returns_empty(self, agent):
        """Unknown drug → empty list, no exception."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await agent.get_drug_risks("totally_unknown_drug_xyz")
            assert result == []

    @pytest.mark.asyncio
    async def test_case_insensitive(self, agent):
        """Drug name lookup should be case insensitive."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await agent.get_drug_risks("METFORMIN")
            assert len(result) >= 1


# ── Test generate_clinical_output ─────────────────────────────────────────

class TestGenerateClinicalOutput:

    @pytest.mark.asyncio
    async def test_calls_ai_service(self, agent):
        """Verify AI service is called and returns non-empty output."""
        result = await agent.generate_clinical_output(
            drug="Metformin",
            shadow_type="Vitamin B12 Depletion",
            trend={"pct_change": -50.0, "readings": 6},
            timeline={"current_stage": "Moderate — reversible now"},
            last_prescription_date="2023-08-01",
        )
        assert isinstance(result, str)
        assert len(result) > 20
        agent._ai.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_ai_failure(self, agent):
        """When AI fails, should return deterministic fallback."""
        agent._ai.chat = AsyncMock(side_effect=Exception("AI down"))
        result = await agent.generate_clinical_output(
            drug="Metformin",
            shadow_type="Vitamin B12 Depletion",
            trend={"pct_change": -50.0},
            timeline={"current_stage": "Moderate"},
            last_prescription_date="2023-08-01",
        )
        assert "Metformin" in result
        assert "B12" in result


# ── Test analyze_patient ──────────────────────────────────────────────────

class TestAnalyzePatient:

    @pytest.mark.asyncio
    async def test_fires_metformin_shadow(self, agent):
        """Mock DB with Patient D data → Metformin shadow should fire."""
        mock_session = MagicMock()

        # Mock the DB query result for treatment_shadows
        mock_row = (
            "e1000000-0001-4000-8000-000000000001",  # id
            "Metformin 1000mg BID",                   # drug_name
            "metformin",                              # drug_name_normalized
            "Vitamin B12 Depletion",                  # shadow_type
            "vitamin_b12",                            # watch_lab
            "moderate",                               # severity
            True,                                     # alert_fired
            [620, 540, 480, 410, 350, 310],           # lab_values (jsonb → list)
            ["2023-08-15", "2023-11-20", "2024-02-14",
             "2024-06-10", "2024-10-05", "2025-01-18"],  # lab_dates
            -62.57,                                   # trend_slope
            -50.0,                                    # trend_pct_change
            "declining",                              # trend_direction
            0.99,                                     # trend_r_squared
            "",                                       # clinical_output (empty→generate)
            "~February 2024",                         # harm_started_estimate
            "Moderate — reversible now",              # current_stage
            "Peripheral neuropathy — partially irreversible",  # projection_90_days
            "Start B12 supplementation 1000mcg daily.",        # recommended_action
            "2023-08-01",                             # prescribed_since
            "2023-08-01",                             # watch_started
            "2023-08-01",                             # created_at
        )

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        result = await agent.analyze_patient(
            patient_id="a1b2c3d4-0004-4000-8000-000000000004",
            db_session=mock_session,
        )

        assert result["fired_count"] == 1
        assert result["total_shadows"] == 1
        assert len(result["active_shadows"]) == 1

        shadow = result["active_shadows"][0]
        assert shadow["drug"] == "Metformin 1000mg BID"
        assert shadow["alert_fired"] is True
        assert shadow["severity"] == "moderate"
        assert shadow["trend"]["direction"] == "declining"
        assert shadow["trend"]["pct_change"] == pytest.approx(-50.0, abs=1)
        assert len(shadow["clinical_output"]) > 0

    @pytest.mark.asyncio
    async def test_no_shadows_returns_empty(self, agent):
        """No rows in DB → empty analysis."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        result = await agent.analyze_patient(
            patient_id="nonexistent-patient-id",
            db_session=mock_session,
        )

        assert result["fired_count"] == 0
        assert result["total_shadows"] == 0
        assert result["active_shadows"] == []
