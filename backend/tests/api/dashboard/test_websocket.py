"""
Tests for WebSocket API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.api.dashboard.websocket import router, manager


@pytest.fixture
def app():
    """Create test FastAPI app"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestWebSocketStatus:
    """Tests for GET /ws/status endpoint"""
    
    def test_get_status(self, client):
        """Test getting WebSocket status"""
        response = client.get("/ws/status")
        assert response.status_code == 200
        data = response.json()
        assert "active_connections" in data
        assert "server_time" in data
        assert isinstance(data["active_connections"], int)


class TestConnectionManager:
    """Tests for ConnectionManager class"""
    
    def test_connection_count_initially_zero(self):
        """Test that connection count starts at zero"""
        # Clear any existing connections
        manager.active_connections.clear()
        manager.subscriptions.clear()
        assert manager.connection_count == 0
    
    def test_subscribe_channel(self):
        """Test subscribing to a channel"""
        client_id = "test-client"
        manager.subscriptions[client_id] = set()
        
        manager.subscribe(client_id, "threats")
        assert "threats" in manager.subscriptions[client_id]
    
    def test_unsubscribe_channel(self):
        """Test unsubscribing from a channel"""
        client_id = "test-client"
        manager.subscriptions[client_id] = {"threats", "incidents"}
        
        manager.unsubscribe(client_id, "threats")
        assert "threats" not in manager.subscriptions[client_id]
        assert "incidents" in manager.subscriptions[client_id]
    
    def test_disconnect_removes_client(self):
        """Test that disconnect removes client"""
        client_id = "test-client"
        manager.subscriptions[client_id] = {"threats"}
        
        manager.disconnect(client_id)
        assert client_id not in manager.subscriptions


class TestWebSocketConnection:
    """Tests for WebSocket connection endpoint"""
    
    def test_websocket_connect(self, app):
        """Test WebSocket connection"""
        client = TestClient(app)
        
        with client.websocket_connect("/ws/connect") as websocket:
            # Should receive connected message
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert "clientId" in data
            assert "timestamp" in data
    
    def test_websocket_ping_pong(self, app):
        """Test ping/pong messages"""
        client = TestClient(app)
        
        with client.websocket_connect("/ws/connect") as websocket:
            # Skip connected message
            websocket.receive_json()
            
            # Send ping
            websocket.send_json({"type": "ping"})
            
            # Should receive pong
            data = websocket.receive_json()
            assert data["type"] == "pong"
            assert "timestamp" in data
    
    def test_websocket_subscribe(self, app):
        """Test subscribing to channel"""
        client = TestClient(app)
        
        with client.websocket_connect("/ws/connect") as websocket:
            # Skip connected message
            websocket.receive_json()
            
            # Subscribe to channel
            websocket.send_json({"type": "subscribe", "channel": "federated"})
            
            # Should receive subscribed confirmation
            data = websocket.receive_json()
            assert data["type"] == "subscribed"
            assert data["channel"] == "federated"
    
    def test_websocket_unsubscribe(self, app):
        """Test unsubscribing from channel"""
        client = TestClient(app)
        
        with client.websocket_connect("/ws/connect") as websocket:
            # Skip connected message
            websocket.receive_json()
            
            # Unsubscribe from channel
            websocket.send_json({"type": "unsubscribe", "channel": "threats"})
            
            # Should receive unsubscribed confirmation
            data = websocket.receive_json()
            assert data["type"] == "unsubscribed"
            assert data["channel"] == "threats"
    
    def test_websocket_acknowledge_threat(self, app):
        """Test acknowledging a threat via WebSocket"""
        client = TestClient(app)
        
        with client.websocket_connect("/ws/connect") as websocket:
            # Skip connected message
            websocket.receive_json()
            
            # Acknowledge threat
            websocket.send_json({
                "type": "acknowledge",
                "threatId": "threat-123"
            })
            
            # Should receive broadcast (since we're subscribed to threats by default)
            data = websocket.receive_json()
            assert data["type"] == "threat:acknowledged"
            assert data["data"]["threatId"] == "threat-123"
    
    def test_websocket_custom_client_id(self, app):
        """Test connecting with custom client ID"""
        client = TestClient(app)
        
        with client.websocket_connect("/ws/connect?client_id=custom-123") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert data["clientId"] == "custom-123"
