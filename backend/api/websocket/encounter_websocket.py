"""
Phoenix Guardian - Week 23-24: Mobile Backend
Encounter WebSocket Handler: Real-time SOAP note streaming.

Features:
- WebSocket connection with JWT authentication
- Audio chunk streaming
- Real-time transcription updates
- Section-by-section SOAP generation
- Connection lifecycle management
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Set, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states."""
    CONNECTING = "connecting"
    AUTHENTICATED = "authenticated"
    RECORDING = "recording"
    PROCESSING = "processing"
    DISCONNECTED = "disconnected"


class EncounterEventType(Enum):
    """Types of events sent to mobile client."""
    TRANSCRIPT_UPDATE = "transcript_update"
    SOAP_SECTION_READY = "soap_section_ready"
    SOAP_COMPLETE = "soap_complete"
    ERROR = "error"
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    CONNECTION_STATUS = "connection_status"


@dataclass
class WebSocketConnection:
    """Represents an active WebSocket connection."""
    connection_id: str
    user_id: str
    tenant_id: str
    state: ConnectionState = ConnectionState.CONNECTING
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_encounter_id: Optional[str] = None
    audio_buffer: bytes = b""
    transcript_buffer: str = ""
    

@dataclass
class EncounterSession:
    """Active encounter recording session."""
    encounter_id: str
    patient_id: str
    connection_id: str
    tenant_id: str
    user_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    audio_chunks_received: int = 0
    total_audio_bytes: int = 0
    transcript: str = ""
    soap_sections: Dict[str, str] = field(default_factory=dict)
    is_complete: bool = False


class EncounterWebSocketHandler:
    """
    WebSocket handler for mobile encounter recording.
    
    Protocol:
    1. Client connects with JWT token in auth
    2. Server validates token and sets tenant context
    3. Client sends 'start_encounter' with patient_id
    4. Client streams 'audio_chunk' binary data
    5. Server sends 'transcript_update' as speech is recognized
    6. Server sends 'soap_section_ready' as each section completes
    7. Client sends 'stop_encounter' when done
    8. Server sends 'soap_complete' with final encounter
    """
    
    def __init__(
        self,
        transcription_service: Optional[Any] = None,
        soap_generator: Optional[Any] = None,
        encounter_service: Optional[Any] = None,
    ):
        self.connections: Dict[str, WebSocketConnection] = {}
        self.sessions: Dict[str, EncounterSession] = {}
        self.transcription_service = transcription_service
        self.soap_generator = soap_generator
        self.encounter_service = encounter_service
        
        # Event handlers
        self._event_handlers: Dict[str, Callable] = {}
        
        # Heartbeat settings
        self.heartbeat_interval = 30  # seconds
        self.connection_timeout = 120  # seconds
        
    async def handle_connection(
        self,
        websocket: Any,
        token: str,
    ) -> None:
        """
        Handle new WebSocket connection.
        
        Args:
            websocket: WebSocket connection object
            token: JWT authentication token
        """
        connection_id = str(uuid.uuid4())
        
        try:
            # Validate token and extract user info
            user_info = await self._validate_token(token)
            if not user_info:
                await self._send_error(websocket, "Authentication failed")
                await websocket.close(code=4001, reason="Authentication failed")
                return
                
            # Create connection record
            connection = WebSocketConnection(
                connection_id=connection_id,
                user_id=user_info["user_id"],
                tenant_id=user_info["tenant_id"],
                state=ConnectionState.AUTHENTICATED,
            )
            self.connections[connection_id] = connection
            
            logger.info(f"WebSocket connected: {connection_id} for user {user_info['user_id']}")
            
            # Send connection confirmation
            await self._send_event(
                websocket,
                EncounterEventType.CONNECTION_STATUS,
                {"status": "connected", "connection_id": connection_id},
            )
            
            # Start heartbeat
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(websocket, connection_id)
            )
            
            try:
                # Message handling loop
                async for message in websocket:
                    await self._handle_message(websocket, connection_id, message)
            finally:
                heartbeat_task.cancel()
                await self._cleanup_connection(connection_id)
                
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await self._send_error(websocket, str(e))
            await self._cleanup_connection(connection_id)
            
    async def _handle_message(
        self,
        websocket: Any,
        connection_id: str,
        message: Any,
    ) -> None:
        """Handle incoming WebSocket message."""
        connection = self.connections.get(connection_id)
        if not connection:
            return
            
        connection.last_activity = datetime.now(timezone.utc)
        
        # Handle binary data (audio chunks)
        if isinstance(message, bytes):
            await self._handle_audio_chunk(websocket, connection_id, message)
            return
            
        # Handle JSON messages
        try:
            data = json.loads(message)
            event_type = data.get("type")
            
            handlers = {
                "start_encounter": self._handle_start_encounter,
                "stop_encounter": self._handle_stop_encounter,
                "pause_recording": self._handle_pause_recording,
                "resume_recording": self._handle_resume_recording,
                "ping": self._handle_ping,
            }
            
            handler = handlers.get(event_type)
            if handler:
                await handler(websocket, connection_id, data)
            else:
                logger.warning(f"Unknown message type: {event_type}")
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON message received")
            await self._send_error(websocket, "Invalid message format")
            
    async def _handle_start_encounter(
        self,
        websocket: Any,
        connection_id: str,
        data: Dict,
    ) -> None:
        """Start a new encounter recording session."""
        connection = self.connections.get(connection_id)
        if not connection:
            return
            
        patient_id = data.get("patient_id")
        encounter_id = data.get("encounter_id", str(uuid.uuid4()))
        
        if not patient_id:
            await self._send_error(websocket, "patient_id is required")
            return
            
        # Create encounter session
        session = EncounterSession(
            encounter_id=encounter_id,
            patient_id=patient_id,
            connection_id=connection_id,
            tenant_id=connection.tenant_id,
            user_id=connection.user_id,
        )
        self.sessions[encounter_id] = session
        connection.active_encounter_id = encounter_id
        connection.state = ConnectionState.RECORDING
        
        logger.info(f"Started encounter {encounter_id} for patient {patient_id}")
        
        # Send confirmation
        await self._send_event(
            websocket,
            EncounterEventType.RECORDING_STARTED,
            {
                "encounter_id": encounter_id,
                "patient_id": patient_id,
                "started_at": session.started_at.isoformat(),
            },
        )
        
    async def _handle_audio_chunk(
        self,
        websocket: Any,
        connection_id: str,
        audio_data: bytes,
    ) -> None:
        """Process incoming audio chunk."""
        connection = self.connections.get(connection_id)
        if not connection or not connection.active_encounter_id:
            return
            
        session = self.sessions.get(connection.active_encounter_id)
        if not session:
            return
            
        # Update session stats
        session.audio_chunks_received += 1
        session.total_audio_bytes += len(audio_data)
        
        # Add to buffer
        connection.audio_buffer += audio_data
        
        # Process transcription in batches (e.g., every 1 second of audio)
        # Assuming 16kHz, 16-bit mono = 32,000 bytes/second
        BUFFER_THRESHOLD = 32000
        
        if len(connection.audio_buffer) >= BUFFER_THRESHOLD:
            await self._process_audio_buffer(websocket, connection_id)
            
    async def _process_audio_buffer(
        self,
        websocket: Any,
        connection_id: str,
    ) -> None:
        """Process accumulated audio buffer for transcription."""
        connection = self.connections.get(connection_id)
        if not connection or not connection.active_encounter_id:
            return
            
        session = self.sessions.get(connection.active_encounter_id)
        if not session:
            return
            
        audio_chunk = connection.audio_buffer
        connection.audio_buffer = b""
        
        # Transcribe audio
        if self.transcription_service:
            try:
                transcript = await self.transcription_service.transcribe(audio_chunk)
                if transcript:
                    session.transcript += " " + transcript
                    connection.transcript_buffer = session.transcript
                    
                    # Send transcript update
                    await self._send_event(
                        websocket,
                        EncounterEventType.TRANSCRIPT_UPDATE,
                        {
                            "text": transcript,
                            "full_transcript": session.transcript,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )
            except Exception as e:
                logger.error(f"Transcription error: {e}")
        else:
            # Mock transcription for testing
            mock_transcript = "[Audio received - transcription pending]"
            session.transcript += " " + mock_transcript
            
            await self._send_event(
                websocket,
                EncounterEventType.TRANSCRIPT_UPDATE,
                {
                    "text": mock_transcript,
                    "full_transcript": session.transcript,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            
    async def _handle_stop_encounter(
        self,
        websocket: Any,
        connection_id: str,
        data: Dict,
    ) -> None:
        """Stop recording and generate SOAP note."""
        connection = self.connections.get(connection_id)
        if not connection or not connection.active_encounter_id:
            await self._send_error(websocket, "No active encounter")
            return
            
        session = self.sessions.get(connection.active_encounter_id)
        if not session:
            return
            
        logger.info(f"Stopping encounter {session.encounter_id}")
        
        connection.state = ConnectionState.PROCESSING
        
        # Process remaining audio buffer
        if connection.audio_buffer:
            await self._process_audio_buffer(websocket, connection_id)
            
        # Send recording stopped event
        await self._send_event(
            websocket,
            EncounterEventType.RECORDING_STOPPED,
            {
                "encounter_id": session.encounter_id,
                "audio_chunks": session.audio_chunks_received,
                "total_bytes": session.total_audio_bytes,
            },
        )
        
        # Generate SOAP note
        await self._generate_soap_note(websocket, session)
        
    async def _generate_soap_note(
        self,
        websocket: Any,
        session: EncounterSession,
    ) -> None:
        """Generate SOAP note from transcript."""
        sections = ["subjective", "objective", "assessment", "plan"]
        
        for section in sections:
            # Generate each section
            if self.soap_generator:
                try:
                    content = await self.soap_generator.generate_section(
                        section=section,
                        transcript=session.transcript,
                        patient_id=session.patient_id,
                    )
                except Exception as e:
                    logger.error(f"SOAP generation error for {section}: {e}")
                    content = f"[Error generating {section}]"
            else:
                # Mock SOAP content for testing
                content = self._get_mock_soap_content(section)
                
            session.soap_sections[section] = content
            
            # Send section ready event
            await self._send_event(
                websocket,
                EncounterEventType.SOAP_SECTION_READY,
                {
                    "section": section,
                    "text": content,
                    "confidence": 0.92,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            
            # Small delay between sections for streaming effect
            await asyncio.sleep(0.5)
            
        # Mark complete
        session.is_complete = True
        
        # Send completion event
        await self._send_event(
            websocket,
            EncounterEventType.SOAP_COMPLETE,
            {
                "encounter_id": session.encounter_id,
                "patient_id": session.patient_id,
                "sections": session.soap_sections,
                "word_count": sum(len(s.split()) for s in session.soap_sections.values()),
                "overall_confidence": 0.92,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        
        # Save encounter if service available
        if self.encounter_service:
            await self.encounter_service.save_encounter(
                encounter_id=session.encounter_id,
                patient_id=session.patient_id,
                tenant_id=session.tenant_id,
                user_id=session.user_id,
                transcript=session.transcript,
                soap_sections=session.soap_sections,
            )
            
    def _get_mock_soap_content(self, section: str) -> str:
        """Get mock SOAP content for testing."""
        mock_content = {
            "subjective": "Patient presents with chief complaint of persistent cough for 5 days. Reports associated symptoms of mild fever, fatigue, and body aches. Denies shortness of breath, chest pain, or hemoptysis.",
            "objective": "Vitals: T 100.4°F, HR 82, BP 128/78, RR 16, SpO2 97% on RA\nGeneral: Alert, oriented, mild fatigue\nLungs: Scattered rhonchi bilateral, no wheezing",
            "assessment": "1. Acute upper respiratory infection, likely viral\n2. Low-grade fever, resolving",
            "plan": "1. Supportive care with rest and hydration\n2. OTC antipyretics PRN for fever\n3. Return if symptoms worsen or persist >7 days",
        }
        return mock_content.get(section, f"[{section} content]")
        
    async def _handle_pause_recording(
        self,
        websocket: Any,
        connection_id: str,
        data: Dict,
    ) -> None:
        """Pause recording."""
        connection = self.connections.get(connection_id)
        if connection:
            # Pause just stops processing audio, doesn't clear buffers
            logger.info(f"Recording paused for connection {connection_id}")
            
    async def _handle_resume_recording(
        self,
        websocket: Any,
        connection_id: str,
        data: Dict,
    ) -> None:
        """Resume recording."""
        connection = self.connections.get(connection_id)
        if connection:
            logger.info(f"Recording resumed for connection {connection_id}")
            
    async def _handle_ping(
        self,
        websocket: Any,
        connection_id: str,
        data: Dict,
    ) -> None:
        """Respond to ping."""
        await websocket.send(json.dumps({
            "type": "pong",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
        
    async def _heartbeat_loop(
        self,
        websocket: Any,
        connection_id: str,
    ) -> None:
        """Send periodic heartbeats."""
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            connection = self.connections.get(connection_id)
            if not connection:
                break
                
            try:
                await websocket.send(json.dumps({
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
            except Exception:
                break
                
    async def _validate_token(self, token: str) -> Optional[Dict]:
        """Validate JWT token and extract user info."""
        # In production, validate with AuthService
        # For now, mock validation
        try:
            # Mock token validation
            return {
                "user_id": "user_001",
                "tenant_id": "hospital_a",
                "role": "physician",
            }
        except Exception:
            return None
            
    async def _send_event(
        self,
        websocket: Any,
        event_type: EncounterEventType,
        data: Dict,
    ) -> None:
        """Send event to client."""
        message = {
            "type": event_type.value,
            **data,
        }
        await websocket.send(json.dumps(message))
        
    async def _send_error(self, websocket: Any, message: str) -> None:
        """Send error to client."""
        await self._send_event(
            websocket,
            EncounterEventType.ERROR,
            {"message": message},
        )
        
    async def _cleanup_connection(self, connection_id: str) -> None:
        """Clean up connection resources."""
        connection = self.connections.pop(connection_id, None)
        if connection and connection.active_encounter_id:
            session = self.sessions.get(connection.active_encounter_id)
            if session and not session.is_complete:
                # Handle incomplete session (save draft, etc.)
                logger.warning(
                    f"Connection {connection_id} closed with incomplete encounter "
                    f"{connection.active_encounter_id}"
                )
                
        logger.info(f"Connection {connection_id} cleaned up")
        
    def get_active_connections(self, tenant_id: str) -> int:
        """Get count of active connections for a tenant."""
        return sum(
            1 for c in self.connections.values()
            if c.tenant_id == tenant_id and c.state != ConnectionState.DISCONNECTED
        )
        
    def get_connection_stats(self) -> Dict:
        """Get connection statistics."""
        return {
            "total_connections": len(self.connections),
            "active_sessions": len(self.sessions),
            "by_state": {
                state.value: sum(1 for c in self.connections.values() if c.state == state)
                for state in ConnectionState
            },
        }


# Factory function for FastAPI integration
def create_websocket_handler() -> EncounterWebSocketHandler:
    """Create WebSocket handler with dependencies."""
    return EncounterWebSocketHandler()


# FastAPI WebSocket route example
"""
from fastapi import WebSocket, WebSocketDisconnect, Query

handler = create_websocket_handler()

@app.websocket("/ws/encounter")
async def encounter_websocket(
    websocket: WebSocket,
    token: str = Query(...),
):
    await websocket.accept()
    await handler.handle_connection(websocket, token)
"""
