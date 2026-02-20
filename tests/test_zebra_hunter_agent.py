"""
Unit tests for ZebraHunterAgent — Phoenix Guardian V5 Phase 3.

Tests:
  - demo_fallback_match finds EDS for Patient A symptoms
  - demo_fallback_match returns empty for non-rare symptoms
  - create_symptom_hash is deterministic and order-independent
  - extract_symptoms _keyword_fallback extracts known keywords
  - reconstruct_missed_clues returns demo timeline for Patient A
  - analyze returns zebra_found for Patient A
  - analyze returns ghost_protocol for Patient B
  - ghost_protocol creates ghost case for unknown symptoms
"""

import asyncio
import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")


# ── Fixtures / helpers ────────────────────────────────────────────────────

def _make_agent():
    """Create a ZebraHunterAgent with mocked AI service."""
    with patch("phoenix_guardian.agents.zebra_hunter_agent.get_ai_service") as mock_ai:
        mock_service = AsyncMock()
        mock_service.chat = AsyncMock(return_value="[]")
        mock_ai.return_value = mock_service
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent
        agent = ZebraHunterAgent()
        agent._ai = mock_service
        return agent


def _patient_a_symptoms() -> List[str]:
    return [
        "fatigue", "chronic pain", "joint hypermobility", "subluxation",
        "translucent skin", "easy bruising", "dizziness", "brain fog",
        "GI dysfunction", "Beighton score 7/9", "high-arched palate",
        "skin hyperextensibility",
    ]


def _patient_b_symptoms() -> List[str]:
    return [
        "episodic facial flushing", "spontaneous bruising",
        "unexplained hypertension", "paresthesias", "muscle weakness",
    ]


def _mock_db() -> MagicMock:
    """Create a mock DB session."""
    db = MagicMock()
    db.execute = MagicMock()
    db.commit = MagicMock()
    return db


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDemoFallbackMatch:
    """Tests for the static demo_fallback_match method."""

    def test_finds_eds_for_patient_a_symptoms(self):
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent

        symptoms = _patient_a_symptoms()
        matches = ZebraHunterAgent.demo_fallback_match(symptoms)

        assert len(matches) >= 1
        top = matches[0]
        assert "ehlers" in top["disease"].lower() or "eds" in top["disease"].lower()
        assert top["confidence"] >= 70

    def test_eds_confidence_is_highest(self):
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent

        symptoms = _patient_a_symptoms()
        matches = ZebraHunterAgent.demo_fallback_match(symptoms)

        # First match should have highest confidence
        if len(matches) > 1:
            assert matches[0]["confidence"] >= matches[1]["confidence"]

    def test_returns_multiple_matches(self):
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent

        symptoms = _patient_a_symptoms()
        matches = ZebraHunterAgent.demo_fallback_match(symptoms)

        # Should find EDS + possibly POTS/Marfan
        assert len(matches) >= 1

    def test_no_match_for_common_symptoms(self):
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent

        common = ["headache", "cough", "runny nose", "fever"]
        matches = ZebraHunterAgent.demo_fallback_match(common)

        # All matches should have very low confidence
        for m in matches:
            assert m["confidence"] < 40

    def test_empty_symptoms_returns_empty(self):
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent
        matches = ZebraHunterAgent.demo_fallback_match([])
        assert matches == [] or all(m["confidence"] == 0 for m in matches)


class TestSymptomHash:
    """Tests for create_symptom_hash — deterministic, order-independent."""

    def test_deterministic(self):
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent

        s = ["fatigue", "bruising", "hypermobility"]
        h1 = ZebraHunterAgent.create_symptom_hash(s)
        h2 = ZebraHunterAgent.create_symptom_hash(s)
        assert h1 == h2

    def test_order_independent(self):
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent

        s1 = ["fatigue", "bruising", "hypermobility"]
        s2 = ["hypermobility", "fatigue", "bruising"]
        assert ZebraHunterAgent.create_symptom_hash(s1) == ZebraHunterAgent.create_symptom_hash(s2)

    def test_case_insensitive(self):
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent

        s1 = ["Fatigue", "Bruising"]
        s2 = ["fatigue", "bruising"]
        assert ZebraHunterAgent.create_symptom_hash(s1) == ZebraHunterAgent.create_symptom_hash(s2)

    def test_different_symptoms_different_hash(self):
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent

        h1 = ZebraHunterAgent.create_symptom_hash(["fatigue"])
        h2 = ZebraHunterAgent.create_symptom_hash(["pain"])
        assert h1 != h2

    def test_hash_is_12_chars(self):
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent

        h = ZebraHunterAgent.create_symptom_hash(["a", "b", "c"])
        assert len(h) == 12


class TestKeywordFallback:
    """Tests for _keyword_fallback extraction."""

    def test_extracts_known_keywords(self):
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent

        notes = [
            "Patient presents with chronic fatigue and joint hypermobility.",
            "Noted easy bruising and subluxation events. Dizziness on standing.",
        ]
        result = ZebraHunterAgent._keyword_fallback(notes)
        assert "fatigue" in result
        assert "hypermobility" in result
        assert "bruising" in result
        assert "subluxation" in result
        assert "dizziness" in result

    def test_no_keywords_found(self):
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent

        notes = ["The weather is nice today. Patient is happy."]
        result = ZebraHunterAgent._keyword_fallback(notes)
        assert isinstance(result, list)

    def test_deduplicated(self):
        from phoenix_guardian.agents.zebra_hunter_agent import ZebraHunterAgent

        notes = ["Fatigue and fatigue again. More fatigue."]
        result = ZebraHunterAgent._keyword_fallback(notes)
        assert result.count("fatigue") <= 1


class TestReconstructMissedClues:
    """Tests for reconstruct_missed_clues — demo timeline."""

    @pytest.mark.asyncio
    async def test_demo_timeline_returns_6_entries(self):
        agent = _make_agent()
        agent.demo_config = type("Obj", (), {"enabled": True})()  # enable demo mode
        visits = [
            {"visit_number": i, "visit_date": f"2022-0{i}-15", "diagnosis": f"Diag {i}", "soap_note": "note"}
            for i in range(1, 7)
        ]
        timeline, years_lost, first_idx = await agent.reconstruct_missed_clues(
            visits, "Hypermobile Ehlers-Danlos Syndrome"
        )
        assert len(timeline) == 6
        assert years_lost > 0
        assert first_idx == 0  # First visit is first diagnosable

    @pytest.mark.asyncio
    async def test_timeline_entries_have_required_fields(self):
        agent = _make_agent()
        agent.demo_config = type("Obj", (), {"enabled": True})()
        visits = [
            {"visit_number": i, "visit_date": f"2022-0{i}-15", "diagnosis": f"D{i}", "soap_note": "n"}
            for i in range(1, 7)
        ]
        timeline, _, _ = await agent.reconstruct_missed_clues(
            visits, "Hypermobile Ehlers-Danlos Syndrome"
        )
        for entry in timeline:
            assert "visit_number" in entry
            assert "visit_date" in entry
            assert "was_diagnosable" in entry
            assert "missed_clues" in entry
            assert "confidence" in entry

    @pytest.mark.asyncio
    async def test_first_diagnosable_is_marked(self):
        agent = _make_agent()
        agent.demo_config = type("Obj", (), {"enabled": True})()
        visits = [
            {"visit_number": i, "visit_date": f"2022-0{i}-15", "diagnosis": f"D{i}", "soap_note": "n"}
            for i in range(1, 7)
        ]
        timeline, _, first_idx = await agent.reconstruct_missed_clues(
            visits, "Hypermobile Ehlers-Danlos Syndrome"
        )
        assert timeline[first_idx].get("is_first_diagnosable") is True


class TestGhostProtocol:
    """Tests for ghost_protocol method."""

    @pytest.mark.asyncio
    async def test_patient_b_always_fires_ghost(self):
        from phoenix_guardian.agents.zebra_hunter_agent import PATIENT_B_ID

        agent = _make_agent()
        db = _mock_db()
        result = await agent.ghost_protocol(
            ["flushing", "bruising", "paresthesias"], PATIENT_B_ID, db
        )
        assert result["activated"] is True
        assert result["ghost_id"] == "GHOST-2025-0042"
        assert result["patient_count"] == 3

    @pytest.mark.asyncio
    async def test_new_symptoms_create_ghost(self):
        agent = _make_agent()
        result = await agent.ghost_protocol(
            ["unknown_symptom_xyz", "rare_sign_abc"], "test-patient-999"
        )
        assert result["activated"] is False
        assert result["patient_count"] == 1
        assert "Ghost Case created" in result["message"]

    @pytest.mark.asyncio
    async def test_second_call_triggers_cluster(self):
        agent = _make_agent()
        symptoms = ["unique_alpha", "unique_beta"]

        # First call
        r1 = await agent.ghost_protocol(symptoms, "patient-001")
        assert r1["activated"] is False

        # Second call same hash, different patient → fires
        r2 = await agent.ghost_protocol(symptoms, "patient-002")
        assert r2["activated"] is True
        assert r2["patient_count"] == 2


class TestAnalyzeIntegration:
    """Integration tests for the full analyze method (mocked AI + DB)."""

    @pytest.mark.asyncio
    async def test_patient_a_returns_zebra_found(self):
        from phoenix_guardian.agents.zebra_hunter_agent import PATIENT_A_ID

        agent = _make_agent()

        # Mock AI chat to return symptoms JSON
        symptoms_json = json.dumps(_patient_a_symptoms())
        agent._ai.chat = AsyncMock(side_effect=[
            symptoms_json,  # extract_symptoms
            # reconstruct_missed_clues calls are skipped (demo mode)
            json.dumps({"referral": "geneticist"}),  # generate_recommendation
        ])

        # Mock DB
        db = _mock_db()
        # patient_visits query returns rows
        visit_rows = [
            (f"visit-{i}", i, f"2022-0{i}-15", f"Diag {i}", f"SOAP note {i}", f"Dr. {i}", "Internal Medicine")
            for i in range(1, 7)
        ]
        name_row = MagicMock()
        name_row.__getitem__ = lambda self, idx: "Priya Sharma"

        call_count = [0]
        def mock_execute(query, params=None):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.fetchall = MagicMock(return_value=visit_rows)
            elif call_count[0] == 2:
                result.fetchone = MagicMock(return_value=name_row)
            else:
                result.fetchone = MagicMock(return_value=None)
                result.fetchall = MagicMock(return_value=[])
            return result

        db.execute = mock_execute

        result = await agent.analyze(PATIENT_A_ID, db)

        assert result["status"] == "zebra_found"
        assert result["patient_name"] == "Priya Sharma"
        assert result["total_visits"] == 6
        assert len(result["symptoms_found"]) > 0
        assert len(result["top_matches"]) >= 1
        assert result["top_matches"][0]["confidence"] >= 70
        assert result["analysis_time_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_patient_b_returns_ghost_protocol(self):
        from phoenix_guardian.agents.zebra_hunter_agent import PATIENT_B_ID

        agent = _make_agent()

        # Mock AI chat
        symptoms_json = json.dumps(_patient_b_symptoms())
        agent._ai.chat = AsyncMock(return_value=symptoms_json)

        # Mock DB
        db = _mock_db()
        visit_rows = [
            (f"visit-{i}", i, f"2024-0{i+4}-15", f"Diag {i}", f"SOAP note {i}", f"Dr. {i}", "Dermatology")
            for i in range(1, 5)
        ]
        name_row = MagicMock()
        name_row.__getitem__ = lambda self, idx: "Arjun Nair"

        call_count = [0]
        def mock_execute(query, params=None):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.fetchall = MagicMock(return_value=visit_rows)
            elif call_count[0] == 2:
                result.fetchone = MagicMock(return_value=name_row)
            else:
                result.fetchone = MagicMock(return_value=None)
                result.fetchall = MagicMock(return_value=[])
            return result

        db.execute = mock_execute

        result = await agent.analyze(PATIENT_B_ID, db)

        assert result["status"] == "ghost_protocol"
        assert result["patient_name"] == "Arjun Nair"
        assert result["ghost_protocol"]["activated"] is True
        assert result["ghost_protocol"]["ghost_id"] == "GHOST-2025-0042"


class TestHealthEndpoint:
    """Tests for the health endpoint response shape."""

    def test_health_response_fields(self):
        """Validate the HealthResponse Pydantic model."""
        from phoenix_guardian.api.routes.zebra_hunter import HealthResponse

        h = HealthResponse()
        assert h.status == "healthy"
        assert h.demo_fallback_loaded is True
        assert h.orphadata_reachable is False
        assert h.redis_connected is False
        assert h.patient_a_ready is False
        assert h.patient_b_ready is False

    def test_analyze_response_fields(self):
        """Validate the AnalyzeResponse Pydantic model."""
        from phoenix_guardian.api.routes.zebra_hunter import AnalyzeResponse

        r = AnalyzeResponse()
        assert r.status == ""
        assert r.patient_id == ""
        assert r.top_matches == []
        assert r.missed_clue_timeline == []
        assert r.ghost_protocol is None
        assert r.analysis_time_seconds == 0.0
