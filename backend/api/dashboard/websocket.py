"""
WebSocket API endpoints
Real-time threat notifications and updates
"""

from datetime import datetime
from typing import Dict, Set, Optional
from uuid import UUID, uuid4
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

router = APIRouter(prefix="/ws", tags=["websocket"])


class ConnectionManager:
    """WebSocket connection manager for real-time updates"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # client_id -> set of channels
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.subscriptions[client_id] = {"threats", "incidents", "honeytokens"}  # Default subscriptions
    
    def disconnect(self, client_id: str):
        """Remove a disconnected client"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.subscriptions:
            del self.subscriptions[client_id]
    
    async def send_personal_message(self, message: dict, client_id: str):
        """Send a message to a specific client"""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message)
    
    async def broadcast(self, message: dict, channel: str = "all"):
        """Broadcast a message to all subscribed clients"""
        for client_id, websocket in self.active_connections.items():
            if channel == "all" or channel in self.subscriptions.get(client_id, set()):
                try:
                    await websocket.send_json(message)
                except Exception:
                    pass  # Client may have disconnected
    
    def subscribe(self, client_id: str, channel: str):
        """Subscribe a client to a channel"""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].add(channel)
    
    def unsubscribe(self, client_id: str, channel: str):
        """Unsubscribe a client from a channel"""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].discard(channel)
    
    @property
    def connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/connect")
async def websocket_endpoint(websocket: WebSocket, client_id: Optional[str] = None):
    """
    WebSocket endpoint for real-time updates
    
    Messages from client:
    - {"type": "subscribe", "channel": "threats|incidents|honeytokens|federated"}
    - {"type": "unsubscribe", "channel": "..."}
    - {"type": "acknowledge", "threatId": "..."}
    - {"type": "ping"}
    
    Messages to client:
    - {"type": "threat:new", "data": {...}}
    - {"type": "threat:update", "data": {...}}
    - {"type": "incident:new", "data": {...}}
    - {"type": "incident:update", "data": {...}}
    - {"type": "honeytoken:trigger", "data": {...}}
    - {"type": "pong"}
    - {"type": "connected", "clientId": "..."}
    """
    if not client_id:
        client_id = str(uuid4())
    
    await manager.connect(websocket, client_id)
    
    # Send connection confirmation
    await manager.send_personal_message({
        "type": "connected",
        "clientId": client_id,
        "timestamp": datetime.utcnow().isoformat(),
    }, client_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "ping":
                await manager.send_personal_message({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat(),
                }, client_id)
            
            elif msg_type == "subscribe":
                channel = data.get("channel")
                if channel:
                    manager.subscribe(client_id, channel)
                    await manager.send_personal_message({
                        "type": "subscribed",
                        "channel": channel,
                    }, client_id)
            
            elif msg_type == "unsubscribe":
                channel = data.get("channel")
                if channel:
                    manager.unsubscribe(client_id, channel)
                    await manager.send_personal_message({
                        "type": "unsubscribed",
                        "channel": channel,
                    }, client_id)
            
            elif msg_type == "acknowledge":
                threat_id = data.get("threatId")
                # In production, would update threat in database
                await manager.broadcast({
                    "type": "threat:acknowledged",
                    "data": {"threatId": threat_id, "acknowledgedBy": client_id},
                }, "threats")
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception:
        manager.disconnect(client_id)


@router.get("/status")
async def get_websocket_status():
    """Get WebSocket server status"""
    return {
        "active_connections": manager.connection_count,
        "server_time": datetime.utcnow().isoformat(),
    }


# Helper functions for broadcasting events from other parts of the application

async def broadcast_new_threat(threat: dict):
    """Broadcast a new threat to all subscribed clients"""
    await manager.broadcast({
        "type": "threat:new",
        "data": threat,
        "timestamp": datetime.utcnow().isoformat(),
    }, "threats")


async def broadcast_threat_update(threat: dict):
    """Broadcast a threat update to all subscribed clients"""
    await manager.broadcast({
        "type": "threat:update",
        "data": threat,
        "timestamp": datetime.utcnow().isoformat(),
    }, "threats")


async def broadcast_new_incident(incident: dict):
    """Broadcast a new incident to all subscribed clients"""
    await manager.broadcast({
        "type": "incident:new",
        "data": incident,
        "timestamp": datetime.utcnow().isoformat(),
    }, "incidents")


async def broadcast_incident_update(incident: dict):
    """Broadcast an incident update to all subscribed clients"""
    await manager.broadcast({
        "type": "incident:update",
        "data": incident,
        "timestamp": datetime.utcnow().isoformat(),
    }, "incidents")


async def broadcast_honeytoken_trigger(trigger: dict):
    """Broadcast a honeytoken trigger to all subscribed clients"""
    await manager.broadcast({
        "type": "honeytoken:trigger",
        "data": trigger,
        "timestamp": datetime.utcnow().isoformat(),
    }, "honeytokens")
