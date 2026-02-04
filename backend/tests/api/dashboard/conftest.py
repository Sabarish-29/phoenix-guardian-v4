"""
Pytest configuration and fixtures for dashboard tests
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dashboard import router as dashboard_router


@pytest.fixture
def app():
    """Create test FastAPI application"""
    app = FastAPI(title="Phoenix Guardian Dashboard API - Test")
    app.include_router(dashboard_router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def sample_threat():
    """Sample threat data"""
    return {
        "title": "Ransomware Attack Detected",
        "description": "BlackCat ransomware encryption patterns detected on EHR system",
        "severity": "critical",
        "threatType": "ransomware",
        "sourceIp": "192.168.1.100",
        "targetSystem": "EHR-Primary",
        "location": {"lat": 40.7128, "lng": -74.0060}
    }


@pytest.fixture
def sample_honeytoken():
    """Sample honeytoken data"""
    return {
        "name": "VIP Patient Record",
        "type": "patient_record",
        "description": "Decoy VIP patient record for detecting unauthorized access",
        "location": "/data/patients/vip_records/",
        "alertLevel": "critical"
    }


@pytest.fixture
def sample_incident():
    """Sample incident data"""
    return {
        "title": "Critical Ransomware Incident",
        "description": "Active ransomware attack affecting multiple systems",
        "priority": "P1",
        "severity": "critical",
        "category": "ransomware",
        "affectedAssets": ["EHR-Primary", "Lab-System", "Radiology-PACS"],
        "affectedDepartments": ["Radiology", "Laboratory"]
    }


@pytest.fixture
def sample_evidence_package(sample_incident, client):
    """Sample evidence package with linked incident"""
    from uuid import uuid4
    return {
        "incidentId": str(uuid4()),
        "incidentTitle": "Test Incident",
        "items": [
            {"type": "network_logs", "name": "capture.pcap", "size": 1024000},
            {"type": "system_logs", "name": "syslog.txt", "size": 256000},
            {"type": "memory_dump", "name": "memory.dmp", "size": 4096000}
        ]
    }


@pytest.fixture
def mock_websocket_connection():
    """Mock WebSocket connection for testing"""
    class MockWebSocket:
        def __init__(self):
            self.sent_messages = []
            self.closed = False
        
        async def accept(self):
            pass
        
        async def send_json(self, data):
            self.sent_messages.append(data)
        
        async def receive_json(self):
            return {"type": "ping"}
        
        async def close(self):
            self.closed = True
    
    return MockWebSocket()


@pytest.fixture
def auth_headers():
    """Mock authentication headers"""
    return {
        "Authorization": "Bearer test-token-12345",
        "X-Request-ID": "test-request-001"
    }


@pytest.fixture(autouse=True)
def cleanup_stores():
    """Clean up in-memory stores before and after each test"""
    from backend.api.dashboard.threats import _threats_store
    from backend.api.dashboard.honeytokens import _honeytokens_store, _triggers_store
    from backend.api.dashboard.evidence import _packages_store
    from backend.api.dashboard.incidents import _incidents_store
    
    # Clear before
    _threats_store.clear()
    _honeytokens_store.clear()
    _triggers_store.clear()
    _packages_store.clear()
    _incidents_store.clear()
    
    yield
    
    # Clear after
    _threats_store.clear()
    _honeytokens_store.clear()
    _triggers_store.clear()
    _packages_store.clear()
    _incidents_store.clear()
