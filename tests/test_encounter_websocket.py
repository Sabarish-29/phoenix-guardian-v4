"""
Phoenix Guardian - Week 23-24: Backend Tests
WebSocket Handler Tests

Tests for the encounter WebSocket handler.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import json

from backend.api.websocket.encounter_websocket import (
    EncounterWebSocketHandler,
    ConnectionState,
    EncounterEventType,
    WebSocketConnection,
    EncounterSession,
)


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.sent_messages: list = []
        self.closed = False
        self.close_code = None
        self.close_reason = None
        
    async def send(self, message: str) -> None:
        self.sent_messages.append(message)
        
    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.close_code = code
        self.close_reason = reason
        
    def get_sent_events(self) -> list:
        return [json.loads(m) for m in self.sent_messages]


class TestConnectionState:
    """Tests for ConnectionState enum."""
    
    def test_all_states_exist(self):
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.AUTHENTICATED.value == "authenticated"
        assert ConnectionState.RECORDING.value == "recording"
        assert ConnectionState.PROCESSING.value == "processing"
        assert ConnectionState.DISCONNECTED.value == "disconnected"


class TestEncounterEventType:
    """Tests for EncounterEventType enum."""
    
    def test_all_event_types_exist(self):
        assert EncounterEventType.TRANSCRIPT_UPDATE.value == "transcript_update"
        assert EncounterEventType.SOAP_SECTION_READY.value == "soap_section_ready"
        assert EncounterEventType.SOAP_COMPLETE.value == "soap_complete"
        assert EncounterEventType.ERROR.value == "error"
        assert EncounterEventType.RECORDING_STARTED.value == "recording_started"
        assert EncounterEventType.RECORDING_STOPPED.value == "recording_stopped"


class TestWebSocketConnection:
    """Tests for WebSocketConnection dataclass."""
    
    def test_create_connection(self):
        conn = WebSocketConnection(
            connection_id="conn_001",
            user_id="user_001",
            tenant_id="hospital_a",
        )
        
        assert conn.connection_id == "conn_001"
        assert conn.user_id == "user_001"
        assert conn.tenant_id == "hospital_a"
        assert conn.state == ConnectionState.CONNECTING
        assert conn.active_encounter_id is None
        
    def test_connection_with_state(self):
        conn = WebSocketConnection(
            connection_id="conn_001",
            user_id="user_001",
            tenant_id="hospital_a",
            state=ConnectionState.AUTHENTICATED,
        )
        
        assert conn.state == ConnectionState.AUTHENTICATED


class TestEncounterSession:
    """Tests for EncounterSession dataclass."""
    
    def test_create_session(self):
        session = EncounterSession(
            encounter_id="enc_001",
            patient_id="P12345",
            connection_id="conn_001",
            tenant_id="hospital_a",
            user_id="user_001",
        )
        
        assert session.encounter_id == "enc_001"
        assert session.patient_id == "P12345"
        assert session.audio_chunks_received == 0
        assert session.total_audio_bytes == 0
        assert session.transcript == ""
        assert session.soap_sections == {}
        assert session.is_complete is False


class TestEncounterWebSocketHandler:
    """Tests for EncounterWebSocketHandler class."""
    
    def setup_method(self):
        self.handler = EncounterWebSocketHandler()
        self.websocket = MockWebSocket()
        
    # Connection Tests
    @pytest.mark.asyncio
    async def test_validate_token_success(self):
        result = await self.handler._validate_token("valid_token")
        
        assert result is not None
        assert "user_id" in result
        assert "tenant_id" in result
        
    @pytest.mark.asyncio
    async def test_send_event(self):
        await self.handler._send_event(
            self.websocket,
            EncounterEventType.CONNECTION_STATUS,
            {"status": "connected"},
        )
        
        events = self.websocket.get_sent_events()
        assert len(events) == 1
        assert events[0]["type"] == "connection_status"
        assert events[0]["status"] == "connected"
        
    @pytest.mark.asyncio
    async def test_send_error(self):
        await self.handler._send_error(self.websocket, "Test error")
        
        events = self.websocket.get_sent_events()
        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert events[0]["message"] == "Test error"
        
    # Message Handling Tests
    @pytest.mark.asyncio
    async def test_handle_start_encounter(self):
        # Setup connection
        conn = WebSocketConnection(
            connection_id="conn_001",
            user_id="user_001",
            tenant_id="hospital_a",
            state=ConnectionState.AUTHENTICATED,
        )
        self.handler.connections["conn_001"] = conn
        
        await self.handler._handle_start_encounter(
            self.websocket,
            "conn_001",
            {"patient_id": "P12345", "encounter_id": "enc_001"},
        )
        
        # Check session created
        assert "enc_001" in self.handler.sessions
        session = self.handler.sessions["enc_001"]
        assert session.patient_id == "P12345"
        
        # Check event sent
        events = self.websocket.get_sent_events()
        assert any(e["type"] == "recording_started" for e in events)
        
    @pytest.mark.asyncio
    async def test_handle_start_encounter_missing_patient_id(self):
        conn = WebSocketConnection(
            connection_id="conn_001",
            user_id="user_001",
            tenant_id="hospital_a",
        )
        self.handler.connections["conn_001"] = conn
        
        await self.handler._handle_start_encounter(
            self.websocket,
            "conn_001",
            {},  # Missing patient_id
        )
        
        events = self.websocket.get_sent_events()
        assert any(e["type"] == "error" for e in events)
        
    @pytest.mark.asyncio
    async def test_handle_audio_chunk(self):
        # Setup connection and session
        conn = WebSocketConnection(
            connection_id="conn_001",
            user_id="user_001",
            tenant_id="hospital_a",
            state=ConnectionState.RECORDING,
            active_encounter_id="enc_001",
        )
        self.handler.connections["conn_001"] = conn
        
        session = EncounterSession(
            encounter_id="enc_001",
            patient_id="P12345",
            connection_id="conn_001",
            tenant_id="hospital_a",
            user_id="user_001",
        )
        self.handler.sessions["enc_001"] = session
        
        # Send audio chunk
        audio_data = b"\x00" * 1024
        await self.handler._handle_audio_chunk(
            self.websocket,
            "conn_001",
            audio_data,
        )
        
        # Check session updated
        assert session.audio_chunks_received == 1
        assert session.total_audio_bytes == 1024
        
    @pytest.mark.asyncio
    async def test_handle_stop_encounter(self):
        # Setup connection and session
        conn = WebSocketConnection(
            connection_id="conn_001",
            user_id="user_001",
            tenant_id="hospital_a",
            state=ConnectionState.RECORDING,
            active_encounter_id="enc_001",
        )
        self.handler.connections["conn_001"] = conn
        
        session = EncounterSession(
            encounter_id="enc_001",
            patient_id="P12345",
            connection_id="conn_001",
            tenant_id="hospital_a",
            user_id="user_001",
        )
        session.transcript = "Test transcript"
        self.handler.sessions["enc_001"] = session
        
        await self.handler._handle_stop_encounter(
            self.websocket,
            "conn_001",
            {},
        )
        
        # Check events sent
        events = self.websocket.get_sent_events()
        assert any(e["type"] == "recording_stopped" for e in events)
        
    @pytest.mark.asyncio
    async def test_handle_ping(self):
        await self.handler._handle_ping(
            self.websocket,
            "conn_001",
            {},
        )
        
        events = self.websocket.get_sent_events()
        assert len(events) == 1
        assert events[0]["type"] == "pong"
        
    # SOAP Generation Tests
    @pytest.mark.asyncio
    async def test_generate_soap_note(self):
        session = EncounterSession(
            encounter_id="enc_001",
            patient_id="P12345",
            connection_id="conn_001",
            tenant_id="hospital_a",
            user_id="user_001",
        )
        session.transcript = "Patient presents with cough and fever"
        
        await self.handler._generate_soap_note(self.websocket, session)
        
        # Check all sections generated
        assert "subjective" in session.soap_sections
        assert "objective" in session.soap_sections
        assert "assessment" in session.soap_sections
        assert "plan" in session.soap_sections
        assert session.is_complete is True
        
        # Check events sent
        events = self.websocket.get_sent_events()
        section_events = [e for e in events if e["type"] == "soap_section_ready"]
        assert len(section_events) == 4
        
        complete_events = [e for e in events if e["type"] == "soap_complete"]
        assert len(complete_events) == 1
        
    def test_get_mock_soap_content(self):
        content = self.handler._get_mock_soap_content("subjective")
        assert "Patient presents" in content
        
        content = self.handler._get_mock_soap_content("objective")
        assert "Vitals" in content
        
        content = self.handler._get_mock_soap_content("assessment")
        assert "infection" in content
        
        content = self.handler._get_mock_soap_content("plan")
        assert "Supportive care" in content
        
    # Connection Management Tests
    @pytest.mark.asyncio
    async def test_cleanup_connection(self):
        conn = WebSocketConnection(
            connection_id="conn_001",
            user_id="user_001",
            tenant_id="hospital_a",
        )
        self.handler.connections["conn_001"] = conn
        
        await self.handler._cleanup_connection("conn_001")
        
        assert "conn_001" not in self.handler.connections
        
    def test_get_active_connections(self):
        # Add connections
        self.handler.connections["conn_001"] = WebSocketConnection(
            connection_id="conn_001",
            user_id="user_001",
            tenant_id="hospital_a",
            state=ConnectionState.AUTHENTICATED,
        )
        self.handler.connections["conn_002"] = WebSocketConnection(
            connection_id="conn_002",
            user_id="user_002",
            tenant_id="hospital_a",
            state=ConnectionState.RECORDING,
        )
        self.handler.connections["conn_003"] = WebSocketConnection(
            connection_id="conn_003",
            user_id="user_003",
            tenant_id="hospital_b",
            state=ConnectionState.AUTHENTICATED,
        )
        
        count = self.handler.get_active_connections("hospital_a")
        assert count == 2
        
    def test_get_connection_stats(self):
        self.handler.connections["conn_001"] = WebSocketConnection(
            connection_id="conn_001",
            user_id="user_001",
            tenant_id="hospital_a",
            state=ConnectionState.RECORDING,
        )
        self.handler.sessions["enc_001"] = EncounterSession(
            encounter_id="enc_001",
            patient_id="P12345",
            connection_id="conn_001",
            tenant_id="hospital_a",
            user_id="user_001",
        )
        
        stats = self.handler.get_connection_stats()
        
        assert stats["total_connections"] == 1
        assert stats["active_sessions"] == 1
        assert stats["by_state"][ConnectionState.RECORDING.value] == 1


# ==============================================================================
# Test Count: ~25 tests for WebSocket handler
# ==============================================================================
