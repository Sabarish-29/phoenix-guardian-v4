"""
Sprint 7: API Route Registration & Response Tests.

Verifies all API routes are:
- Properly registered in FastAPI
- Return correct response codes
- Have proper dependency injection
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport

from phoenix_guardian.api.main import app


@pytest.fixture
def mock_current_user():
    """Mock auth dependency for all tests."""
    return {"sub": "test-user", "role": "admin", "exp": 9999999999}


@pytest.fixture
async def client(mock_current_user):
    """Create an async test client with mocked auth."""
    with patch(
        "phoenix_guardian.api.routes.agents.get_current_user",
        return_value=mock_current_user,
    ), patch(
        "phoenix_guardian.api.routes.encounters.get_current_user",
        return_value=mock_current_user,
    ), patch(
        "phoenix_guardian.api.routes.pqc.get_current_user",
        return_value=mock_current_user,
    ), patch(
        "phoenix_guardian.api.routes.learning.get_current_user",
        return_value=mock_current_user,
    ), patch(
        "phoenix_guardian.api.routes.orchestration.get_current_user",
        return_value=mock_current_user,
    ), patch(
        "phoenix_guardian.api.routes.transcription.get_current_user",
        return_value=mock_current_user,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ═══════════════════════════════════════════════════════════════════════════════
# Route Registration Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouteRegistration:
    """Verify all routes are registered in the app."""

    def test_app_title(self):
        assert app.title == "Phoenix Guardian"

    def test_all_route_groups_present(self):
        """Main app should include all router groups."""
        route_paths = [r.path for r in app.routes if hasattr(r, "path")]

        # Health
        assert any("/health" in p for p in route_paths)

        # Auth / Patients existing routes
        assert any("/auth" in p for p in route_paths)
        assert any("/patients" in p for p in route_paths)

        # Sprint 1 agents
        assert any("/agents" in p for p in route_paths)

        # Sprint 2 encounters/workflow
        assert any("/encounters" in p for p in route_paths)

        # Sprint 3 PQC
        assert any("/pqc" in p for p in route_paths)

        # Sprint 4 transcription
        assert any("/transcription" in p for p in route_paths)

        # Sprint 5 learning
        assert any("/learning" in p for p in route_paths)

        # Sprint 6 orchestration
        assert any("/orchestration" in p for p in route_paths)

    def test_route_count(self):
        """Should have at least 40 routes total across all sprints."""
        route_paths = [r.path for r in app.routes if hasattr(r, "path")]
        # 20+ agent routes + existing + 7 PQC + 7 learning + 4 orchestration + encounters + misc
        assert len(route_paths) >= 40, f"Only {len(route_paths)} routes found"


# ═══════════════════════════════════════════════════════════════════════════════
# Health Endpoint Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestHealthEndpoints:
    """Health endpoints should always work without auth."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """GET /api/v1/health should return 200."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data


# ═══════════════════════════════════════════════════════════════════════════════
# PQC API Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPQCAPIRoutes:
    """PQC endpoints should respond correctly."""

    @pytest.mark.asyncio
    async def test_pqc_algorithms(self, client):
        """GET /api/v1/pqc/algorithms should list algorithms."""
        response = await client.get("/api/v1/pqc/algorithms")
        assert response.status_code == 200
        data = response.json()
        assert "kem" in data or "algorithms" in data or "key_encapsulation" in data

    @pytest.mark.asyncio
    async def test_pqc_health(self, client):
        """GET /api/v1/pqc/health should return PQC status."""
        response = await client.get("/api/v1/pqc/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_pqc_encrypt_phi(self, client):
        """POST /api/v1/pqc/encrypt-phi should encrypt PHI fields."""
        response = await client.post(
            "/api/v1/pqc/encrypt-phi",
            json={
                "patient_name": "Test Patient",
                "ssn": "123-45-6789",
                "visit_type": "outpatient",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "encrypted_data" in data


# ═══════════════════════════════════════════════════════════════════════════════
# Learning API Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestLearningAPIRoutes:
    """Learning pipeline endpoints should respond correctly."""

    @pytest.mark.asyncio
    async def test_learning_status(self, client):
        """GET /api/v1/learning/status should return pipeline status."""
        response = await client.get("/api/v1/learning/status")
        assert response.status_code == 200
        data = response.json()
        assert "pipelines" in data

    @pytest.mark.asyncio
    async def test_learning_feedback(self, client):
        """POST /api/v1/learning/feedback should accept feedback."""
        response = await client.post(
            "/api/v1/learning/feedback",
            json={
                "domain": "fraud_detection",
                "agent": "fraud",
                "action": "accept",
                "original_output": "test",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "recorded" or "recorded" in str(data)


# ═══════════════════════════════════════════════════════════════════════════════
# Orchestration API Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrchestrationAPIRoutes:
    """Orchestration endpoints should respond correctly."""

    @pytest.mark.asyncio
    async def test_orchestration_agents(self, client):
        """GET /api/v1/orchestration/agents should list 10 agents."""
        response = await client.get("/api/v1/orchestration/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert len(data["agents"]) == 10

    @pytest.mark.asyncio
    async def test_orchestration_health(self, client):
        """GET /api/v1/orchestration/health should return agent health."""
        response = await client.get("/api/v1/orchestration/health")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert len(data["agents"]) == 10


# ═══════════════════════════════════════════════════════════════════════════════
# Agent API Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentAPIRoutes:
    """Agent endpoints for all 10 agents."""

    AGENT_ENDPOINTS = [
        "/api/v1/agents/scribe/process",
        "/api/v1/agents/safety/check",
        "/api/v1/agents/coding/suggest",
        "/api/v1/agents/sentinel/scan",
        "/api/v1/agents/navigator/search",
        "/api/v1/agents/fraud/detect",
        "/api/v1/agents/clinical-decision/analyze",
        "/api/v1/agents/pharmacy/formulary-check",
        "/api/v1/agents/deception/analyze",
        "/api/v1/agents/orders/suggest-labs",
    ]

    def test_agent_endpoints_registered(self):
        """All 10 agent endpoints should be registered."""
        route_paths = [r.path for r in app.routes if hasattr(r, "path")]

        for endpoint in self.AGENT_ENDPOINTS:
            assert any(
                endpoint.rstrip("/") in p for p in route_paths
            ), f"Agent endpoint not found: {endpoint}"
