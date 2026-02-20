"""
Phase 4 tests — V5 Dashboard unified status endpoint.

Tests:
  - V5StatusResponse structure and fields
  - Active alerts for all 3 agents
  - Impact summary populated
  - Agent status fields
  - Demo fallback behavior
  - Pydantic model validation
"""

import os
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

os.environ.setdefault("ANTHROPIC_API_KEY", "test-api-key-for-testing")

from phoenix_guardian.api.main import app
from phoenix_guardian.database.connection import get_db


# ── DB Mock ──────────────────────────────────────────────────────────────

class MockResult:
    """Simulates a DB scalar or fetchone result."""
    def __init__(self, value=None):
        self._value = value

    def scalar(self):
        return self._value

    def fetchone(self):
        return self._value

    def fetchall(self):
        return self._value if isinstance(self._value, list) else []


class MockDBSession:
    """Mock DB session returning demo-like data for V5 dashboard queries."""

    def execute(self, query, params=None):
        q = str(query)

        # Treatment shadow fired count
        if "alert_fired = true" in q and "COUNT" in q:
            return MockResult(1)
        # Treatment shadow watching count
        if "alert_fired = false" in q and "COUNT" in q:
            return MockResult(3)
        # Treatment shadow top alert
        if "treatment_shadows" in q and "LIMIT 1" in q:
            return MockResult((
                "a1b2c3d4-0004-4000-8000-000000000004",
                "Metformin", "vitamin_b12_depletion", "critical", -58.0, 90,
            ))
        # Silent voice alert count
        if "silent_voice_alerts" in q and "COUNT" in q:
            return MockResult(1)
        # Silent voice top alert
        if "silent_voice_alerts" in q and "LIMIT 1" in q:
            return MockResult((
                "a1b2c3d4-0003-4000-8000-000000000003",
                "critical", 18, 4, 6.2,
            ))
        # Zebra analyses count (zebra_found)
        if "zebra_analyses" in q and "COUNT" in q:
            return MockResult(1)
        # Years lost
        if "MAX(years_lost)" in q:
            return MockResult(3.0)
        # Zebra full_result
        if "full_result" in q and "zebra_found" in q:
            import json
            return MockResult((json.dumps({
                "top_matches": [{"disease": "Ehlers-Danlos Syndrome", "confidence": 81}],
            }),))
        # Ghost cases count
        if "ghost_cases" in q and "COUNT" in q:
            return MockResult(1)
        # Ghost cases detail (alert_fired LIMIT 1)
        if "ghost_cases" in q and "alert_fired" in q and "LIMIT 1" in q:
            return MockResult(("GHOST-2025-0042", 3, '["flushing","bruising"]'))
        # Ghost cases list
        if "ghost_cases" in q:
            return MockResult([])
        # Default
        return MockResult(0)

    def commit(self):
        pass

    def close(self):
        pass


def get_mock_db():
    yield MockDBSession()


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_overrides():
    """Override DB and auth for all tests."""
    from phoenix_guardian.api.auth.utils import get_current_active_user

    mock_user = MagicMock()
    mock_user.email = "test@test.com"
    mock_user.first_name = "Test"
    mock_user.last_name = "User"
    mock_user.role = "physician"
    mock_user.is_active = True

    app.dependency_overrides[get_db] = get_mock_db
    app.dependency_overrides[get_current_active_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.fixture
def client():
    return TestClient(app)


# ── Endpoint Tests ───────────────────────────────────────────────────────

class TestV5StatusEndpoint:
    """Tests against GET /api/v1/v5/status."""

    def test_returns_200(self, client):
        resp = client.get("/api/v1/v5/status")
        assert resp.status_code == 200

    def test_has_timestamp(self, client):
        data = client.get("/api/v1/v5/status").json()
        assert "timestamp" in data
        assert len(data["timestamp"]) > 10

    def test_has_active_alerts(self, client):
        data = client.get("/api/v1/v5/status").json()
        assert "active_alerts" in data
        assert isinstance(data["active_alerts"], list)
        assert len(data["active_alerts"]) >= 1

    def test_active_alerts_have_required_fields(self, client):
        data = client.get("/api/v1/v5/status").json()
        for alert in data["active_alerts"]:
            for key in ("agent", "patient_name", "summary", "link", "severity", "agent_icon"):
                assert key in alert, f"Missing field: {key}"

    def test_silent_voice_alert_present(self, client):
        data = client.get("/api/v1/v5/status").json()
        agents = [a["agent"] for a in data["active_alerts"]]
        assert "SilentVoice" in agents

    def test_treatment_shadow_alert_present(self, client):
        data = client.get("/api/v1/v5/status").json()
        agents = [a["agent"] for a in data["active_alerts"]]
        assert "TreatmentShadow" in agents

    def test_zebra_hunter_alert_present(self, client):
        data = client.get("/api/v1/v5/status").json()
        agents = [a["agent"] for a in data["active_alerts"]]
        assert "ZebraHunter" in agents

    def test_has_all_three_agents(self, client):
        agents = client.get("/api/v1/v5/status").json()["agents"]
        assert "treatment_shadow" in agents
        assert "silent_voice" in agents
        assert "zebra_hunter" in agents

    def test_treatment_shadow_fields(self, client):
        s = client.get("/api/v1/v5/status").json()["agents"]["treatment_shadow"]
        assert s["fired_count"] >= 1
        assert "watching_count" in s
        assert s["b12_pct_change"] == 58

    def test_silent_voice_fields(self, client):
        s = client.get("/api/v1/v5/status").json()["agents"]["silent_voice"]
        assert s["distress_duration_minutes"] == 18
        assert s["signals_detected"] == 4

    def test_zebra_hunter_fields(self, client):
        z = client.get("/api/v1/v5/status").json()["agents"]["zebra_hunter"]
        assert z["zebra_count"] >= 1
        assert z["ghost_count"] >= 1
        assert z["years_lost"] >= 3.0

    def test_has_impact_summary(self, client):
        impact = client.get("/api/v1/v5/status").json()["impact"]
        for key in ("rare_diseases_detected", "silent_distress_caught",
                     "treatment_harms_prevented", "ghost_cases_created",
                     "years_suffering_prevented"):
            assert key in impact
        assert impact["years_suffering_prevented"] >= 3.0

    def test_has_existing_agents(self, client):
        existing = client.get("/api/v1/v5/status").json()["existing_agents"]
        assert existing["all_operational"] is True
        assert existing["count"] == 10
        assert existing["security_block_rate"] == "100%"

    def test_demo_patients_loaded(self, client):
        assert client.get("/api/v1/v5/status").json()["demo_patients_loaded"] == 4

    def test_all_agents_healthy(self, client):
        assert client.get("/api/v1/v5/status").json()["all_agents_healthy"] is True

    def test_alert_links_are_deep_links(self, client):
        data = client.get("/api/v1/v5/status").json()
        for alert in data["active_alerts"]:
            link = alert["link"]
            assert any(x in link for x in ["/treatment-shadow", "/silent-voice", "/zebra-hunter"])


# ── Model Tests ──────────────────────────────────────────────────────────

class TestV5DashboardModels:
    """Test Pydantic model validation."""

    def test_v5_status_response_model(self):
        from phoenix_guardian.api.routes.v5_dashboard import V5StatusResponse
        data = V5StatusResponse(timestamp="2026-02-20T00:00:00Z", demo_patients_loaded=4, all_agents_healthy=True)
        assert data.timestamp == "2026-02-20T00:00:00Z"
        assert data.active_alerts == []

    def test_active_alert_model(self):
        from phoenix_guardian.api.routes.v5_dashboard import ActiveAlert
        alert = ActiveAlert(agent="SilentVoice", agent_icon="x", patient_name="T", patient_id="1",
                            location="ICU", summary="s", detail="d", severity="critical", link="/x")
        assert alert.agent == "SilentVoice"

    def test_impact_summary_defaults(self):
        from phoenix_guardian.api.routes.v5_dashboard import ImpactSummary
        assert ImpactSummary().rare_diseases_detected == 0

    def test_agent_statuses_defaults(self):
        from phoenix_guardian.api.routes.v5_dashboard import AgentStatuses
        a = AgentStatuses()
        assert a.treatment_shadow.status == "healthy"
        assert a.silent_voice.status == "healthy"
        assert a.zebra_hunter.status == "healthy"

    def test_top_alert_model(self):
        from phoenix_guardian.api.routes.v5_dashboard import TopAlert
        alert = TopAlert(patient_id="a", patient_name="T", summary="s", severity="critical", agent="X", link="/x")
        assert alert.patient_id == "a"
