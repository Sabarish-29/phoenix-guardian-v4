"""
End-to-end integration tests for Security Dashboard
"""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4


class TestThreatToIncidentWorkflow:
    """E2E: Threat detection → Incident creation → Containment → Resolution"""
    
    def test_complete_threat_response_workflow(self, client, sample_threat):
        """Test complete threat response workflow"""
        # 1. Threat is detected
        threat_response = client.post("/threats", json=sample_threat)
        assert threat_response.status_code == 201
        threat = threat_response.json()
        threat_id = threat["id"]
        
        # 2. Security analyst acknowledges the threat
        ack_response = client.post(f"/threats/{threat_id}/acknowledge")
        assert ack_response.status_code == 200
        
        # 3. Create incident from threat
        incident_response = client.post("/incidents", json={
            "title": f"Incident: {threat['title']}",
            "description": f"Auto-created from threat {threat_id}",
            "priority": "P1",
            "severity": threat["severity"],
            "category": threat["threatType"],
            "relatedThreats": [threat_id],
            "affectedAssets": [threat.get("targetSystem", "Unknown")]
        })
        assert incident_response.status_code == 201
        incident = incident_response.json()
        incident_id = incident["id"]
        
        # 4. Assign analyst to incident
        assign_response = client.put(
            f"/incidents/{incident_id}/assign",
            json={"userId": "user-1"}
        )
        assert assign_response.status_code == 200
        
        # 5. Update status to investigating
        status_response = client.put(
            f"/incidents/{incident_id}/status",
            json={"status": "investigating"}
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "investigating"
        
        # 6. Add containment action
        containment_response = client.post(
            f"/incidents/{incident_id}/containment",
            params={"action": "Isolated affected system from network"}
        )
        assert containment_response.status_code == 200
        
        # 7. Update threat status to mitigated
        threat_status_response = client.put(
            f"/threats/{threat_id}/status",
            json={"status": "mitigated"}
        )
        assert threat_status_response.status_code == 200
        
        # 8. Update incident to contained
        contained_response = client.put(
            f"/incidents/{incident_id}/status",
            json={"status": "contained"}
        )
        assert contained_response.status_code == 200
        
        # 9. Resolve incident
        resolve_response = client.put(
            f"/incidents/{incident_id}/status",
            json={"status": "resolved"}
        )
        assert resolve_response.status_code == 200
        assert resolve_response.json()["resolvedAt"] is not None
        
        # 10. Verify final states
        final_threat = client.get(f"/threats/{threat_id}").json()
        final_incident = client.get(f"/incidents/{incident_id}").json()
        
        assert final_threat["status"] == "mitigated"
        assert final_threat["acknowledged"] == True
        assert final_incident["status"] == "resolved"


class TestHoneytokenDetectionWorkflow:
    """E2E: Honeytoken creation → Trigger → Alert → Investigation"""
    
    def test_honeytoken_breach_detection(self, client, sample_honeytoken):
        """Test honeytoken breach detection workflow"""
        # 1. Deploy honeytoken
        create_response = client.post("/honeytokens", json=sample_honeytoken)
        assert create_response.status_code == 201
        honeytoken = create_response.json()
        honeytoken_id = honeytoken["id"]
        
        # 2. Verify honeytoken is active
        assert honeytoken["status"] == "active"
        assert honeytoken["triggerCount"] == 0
        
        # 3. Simulate trigger event (unauthorized access)
        trigger_response = client.post(
            f"/honeytokens/{honeytoken_id}/trigger",
            params={
                "source_ip": "10.0.0.50",
                "access_type": "read",
                "target_system": "AD-Server",
                "source_user": "attacker_account"
            }
        )
        assert trigger_response.status_code == 200
        trigger = trigger_response.json()
        
        # 4. Verify trigger recorded
        updated_honeytoken = client.get(f"/honeytokens/{honeytoken_id}").json()
        assert updated_honeytoken["triggerCount"] == 1
        
        # 5. Get trigger details
        triggers_response = client.get(f"/honeytokens/{honeytoken_id}/triggers")
        assert triggers_response.status_code == 200
        triggers = triggers_response.json()
        assert len(triggers) == 1
        assert triggers[0]["sourceIp"] == "10.0.0.50"
        
        # 6. Create incident from trigger
        incident_response = client.post("/incidents", json={
            "title": f"Honeytoken Access: {honeytoken['name']}",
            "description": f"Unauthorized access detected from {trigger['sourceIp']}",
            "priority": "P1",
            "severity": "critical",
            "category": "unauthorized_access",
            "affectedAssets": ["AD-Server"]
        })
        assert incident_response.status_code == 201
        
        # 7. Verify honeytoken appears in recent triggers
        recent_response = client.get("/honeytokens/triggers/recent")
        assert len(recent_response.json()) >= 1


class TestEvidenceCollectionWorkflow:
    """E2E: Incident → Evidence collection → Verification → Export"""
    
    def test_evidence_collection_workflow(self, client, sample_incident):
        """Test evidence collection for incident"""
        # 1. Create incident
        incident_response = client.post("/incidents", json=sample_incident)
        assert incident_response.status_code == 201
        incident = incident_response.json()
        incident_id = incident["id"]
        
        # 2. Create evidence package
        evidence_response = client.post("/evidence/packages", json={
            "incidentId": str(incident_id),
            "incidentTitle": incident["title"],
            "items": [
                {"type": "network_logs", "name": "traffic_capture.pcap", "size": 2048000},
                {"type": "system_logs", "name": "windows_events.evtx", "size": 512000},
                {"type": "memory_dump", "name": "system_memory.dmp", "size": 8192000},
                {"type": "disk_image", "name": "affected_drive.dd", "size": 50000000}
            ]
        })
        assert evidence_response.status_code == 201
        package = evidence_response.json()
        package_id = package["id"]
        
        # 3. Verify package details
        assert len(package["items"]) == 4
        assert package["totalSize"] == 60752000
        
        # 4. Verify integrity
        verify_response = client.post(f"/evidence/packages/{package_id}/verify")
        assert verify_response.status_code == 200
        verification = verify_response.json()
        assert verification["verified"] == True
        assert verification["items_checked"] == 4
        
        # 5. Download package
        download_response = client.get(f"/evidence/packages/{package_id}/download")
        assert download_response.status_code == 200
        assert download_response.headers["content-type"] == "application/zip"
        
        # 6. Get evidence stats
        stats_response = client.get("/evidence/stats/summary")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["total_packages"] >= 1


class TestFederatedLearningIntegration:
    """E2E: Signature detection → Contribution → Model update"""
    
    def test_federated_learning_integration(self, client):
        """Test federated learning integration"""
        # 1. Get current model status
        model_status = client.get("/federated/model/status").json()
        initial_version = model_status["modelVersion"]
        
        # 2. Get available signatures
        signatures_response = client.get("/federated/signatures")
        assert signatures_response.status_code == 200
        signatures = signatures_response.json()
        assert len(signatures) > 0
        
        # 3. Check privacy metrics
        privacy_response = client.get("/federated/privacy/metrics")
        assert privacy_response.status_code == 200
        privacy = privacy_response.json()
        assert privacy["budgetUsed"] <= privacy["budgetTotal"]
        
        # 4. Submit contribution
        contribution_response = client.post("/federated/contributions", json={
            "signatures": [
                {"hash": "newSig123", "type": "lateral_movement"},
                {"hash": "newSig456", "type": "data_exfiltration"}
            ],
            "privacyLevel": "high"
        })
        assert contribution_response.status_code == 200
        assert contribution_response.json()["signatures_accepted"] == 2
        
        # 5. Get contribution stats
        contributions_response = client.get("/federated/contributions")
        assert contributions_response.status_code == 200
        
        # 6. Verify federated stats
        stats_response = client.get("/federated/stats/summary")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert "model" in stats
        assert "privacy" in stats
        assert "network" in stats


class TestDashboardDataAggregation:
    """E2E: Test dashboard data aggregation across all modules"""
    
    def test_dashboard_data_aggregation(self, client, sample_threat, sample_honeytoken, sample_incident):
        """Test aggregating data for dashboard display"""
        # 1. Create multiple threats
        for i in range(3):
            threat_data = {**sample_threat, "title": f"Threat {i}"}
            client.post("/threats", json=threat_data)
        
        # 2. Create honeytokens
        for i in range(2):
            token_data = {**sample_honeytoken, "name": f"Token {i}"}
            client.post("/honeytokens", json=token_data)
        
        # 3. Create incidents
        for i in range(2):
            incident_data = {**sample_incident, "title": f"Incident {i}"}
            client.post("/incidents", json=incident_data)
        
        # 4. Get stats from all modules
        threat_stats = client.get("/threats/stats/summary").json()
        honeytoken_stats = client.get("/honeytokens/stats/summary").json()
        incident_stats = client.get("/incidents/stats/summary").json()
        evidence_stats = client.get("/evidence/stats/summary").json()
        federated_stats = client.get("/federated/stats/summary").json()
        
        # 5. Verify aggregated data
        assert threat_stats["total"] == 3
        assert honeytoken_stats["total_honeytokens"] == 2
        assert incident_stats["total"] == 2
        
        # 6. Verify filters work
        filtered_threats = client.get("/threats?severity=critical").json()
        assert all(t["severity"] == "critical" for t in filtered_threats)


class TestRealTimeUpdatesSimulation:
    """E2E: Test simulating real-time updates flow"""
    
    def test_realtime_update_simulation(self, client, sample_threat):
        """Test the flow of real-time updates"""
        # 1. Create threat
        threat = client.post("/threats", json=sample_threat).json()
        threat_id = threat["id"]
        
        # 2. Simulate rapid status updates
        statuses = ["active", "investigating", "mitigated"]
        for status in statuses:
            response = client.put(
                f"/threats/{threat_id}/status",
                json={"status": status}
            )
            assert response.status_code == 200
            assert response.json()["status"] == status
        
        # 3. Create incident with multiple updates
        incident = client.post("/incidents", json={
            "title": "Rapid Response Incident",
            "priority": "P1",
            "severity": "critical",
            "category": "ransomware"
        }).json()
        incident_id = incident["id"]
        
        # 4. Simulate incident workflow
        client.put(f"/incidents/{incident_id}/assign", json={"userId": "user-1"})
        client.put(f"/incidents/{incident_id}/status", json={"status": "investigating"})
        client.post(f"/incidents/{incident_id}/containment", params={"action": "Step 1"})
        client.post(f"/incidents/{incident_id}/containment", params={"action": "Step 2"})
        client.put(f"/incidents/{incident_id}/status", json={"status": "contained"})
        
        # 5. Verify final state
        final_incident = client.get(f"/incidents/{incident_id}").json()
        assert final_incident["status"] == "contained"
        assert len(final_incident["actions"]) == 2
        assert final_incident["assignee"] is not None
