"""
Phoenix Guardian - Load Test API (Locust)
Week 35: Integration Testing + Polish (Days 171-175)

Performance load testing with Locust framework.
Tests API endpoints under 1,000 concurrent users.

Test Scenarios:
- User authentication flow
- Encounter creation and updates
- Transcription requests
- SOAP note generation
- Threat detection API
- Dashboard metrics
- Real-time WebSocket connections

Run: locust -f load_test_api.py --host=https://api.phoenix-guardian.health
"""

from locust import HttpUser, task, between, events, tag
from locust.contrib.fasthttp import FastHttpUser
import json
import random
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional
import hashlib
import base64


# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Load test configuration."""
    
    # Target SLAs
    P95_RESPONSE_TIME_MS = 500
    P99_RESPONSE_TIME_MS = 1000
    MAX_ERROR_RATE = 0.01  # 1%
    
    # Test data
    NUM_TENANTS = 10
    PATIENTS_PER_TENANT = 100
    
    # API versions
    API_VERSION = "v1"
    
    # Weights for task distribution
    WEIGHT_AUTH = 10
    WEIGHT_ENCOUNTER = 40
    WEIGHT_TRANSCRIPTION = 30
    WEIGHT_SOAP = 15
    WEIGHT_THREAT = 5


# ============================================================================
# Test Data Generation
# ============================================================================

class TestDataGenerator:
    """Generate realistic test data for load testing."""
    
    @staticmethod
    def generate_tenant_id() -> str:
        """Generate random tenant ID."""
        return f"hospital-{random.randint(1, Config.NUM_TENANTS):03d}"
    
    @staticmethod
    def generate_user_id(tenant_id: str) -> str:
        """Generate random user ID for tenant."""
        user_num = random.randint(1, 50)
        return f"dr-{tenant_id[-3:]}-{user_num:03d}"
    
    @staticmethod
    def generate_patient_mrn(tenant_id: str) -> str:
        """Generate random patient MRN."""
        patient_num = random.randint(1, Config.PATIENTS_PER_TENANT)
        return f"MRN-{tenant_id[-3:]}-{patient_num:04d}"
    
    @staticmethod
    def generate_encounter_data(tenant_id: str) -> Dict[str, Any]:
        """Generate encounter creation payload."""
        return {
            "patient_mrn": TestDataGenerator.generate_patient_mrn(tenant_id),
            "physician_id": TestDataGenerator.generate_user_id(tenant_id),
            "encounter_type": random.choice([
                "office_visit",
                "follow_up",
                "consultation",
                "urgent_care"
            ]),
            "chief_complaint": random.choice([
                "Chest pain",
                "Headache",
                "Back pain",
                "Fever",
                "Cough",
                "Fatigue"
            ]),
            "start_time": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def generate_transcription_request() -> Dict[str, Any]:
        """Generate transcription request payload."""
        # Simulate audio metadata (not actual audio for load test)
        return {
            "audio_format": "wav",
            "sample_rate": 16000,
            "duration_seconds": random.randint(30, 300),
            "language": random.choice(["en", "es", "zh"]),
            "streaming": random.choice([True, False])
        }
    
    @staticmethod
    def generate_soap_request(encounter_id: str) -> Dict[str, Any]:
        """Generate SOAP note generation request."""
        return {
            "encounter_id": encounter_id,
            "transcription_complete": True,
            "include_codes": True,
            "language": random.choice(["en", "es"])
        }
    
    @staticmethod
    def generate_jwt_token(tenant_id: str, user_id: str) -> str:
        """Generate simulated JWT token for testing."""
        # In real tests, would get actual token from auth server
        payload = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600
        }
        # Simulated token (not cryptographically valid)
        token_data = base64.b64encode(json.dumps(payload).encode()).decode()
        return f"Bearer eyJhbGciOiJSUzI1NiJ9.{token_data}.signature"


# ============================================================================
# Performance Metrics Tracking
# ============================================================================

class PerformanceMetrics:
    """Track performance metrics during load test."""
    
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.response_times: list = []
        self.start_time = time.time()
    
    def record_request(self, response_time_ms: float, success: bool):
        """Record a request."""
        self.request_count += 1
        self.response_times.append(response_time_ms)
        if not success:
            self.error_count += 1
    
    def get_p95_latency(self) -> float:
        """Get P95 latency."""
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        index = int(len(sorted_times) * 0.95)
        return sorted_times[min(index, len(sorted_times) - 1)]
    
    def get_p99_latency(self) -> float:
        """Get P99 latency."""
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        index = int(len(sorted_times) * 0.99)
        return sorted_times[min(index, len(sorted_times) - 1)]
    
    def get_error_rate(self) -> float:
        """Get error rate."""
        if self.request_count == 0:
            return 0
        return self.error_count / self.request_count
    
    def get_throughput(self) -> float:
        """Get requests per second."""
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0
        return self.request_count / elapsed


metrics = PerformanceMetrics()


# ============================================================================
# Locust User Classes
# ============================================================================

class PhoenixGuardianUser(FastHttpUser):
    """
    Simulates a Phoenix Guardian user (physician/admin).
    
    Performs realistic workflow:
    1. Authenticate
    2. Create encounters
    3. Submit audio for transcription
    4. Generate SOAP notes
    5. View dashboard
    """
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Set up user session."""
        self.tenant_id = TestDataGenerator.generate_tenant_id()
        self.user_id = TestDataGenerator.generate_user_id(self.tenant_id)
        self.token = TestDataGenerator.generate_jwt_token(self.tenant_id, self.user_id)
        self.current_encounter_id: Optional[str] = None
        
        # Authenticate on start
        self._authenticate()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with auth token."""
        return {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "X-Tenant-ID": self.tenant_id,
            "X-Request-ID": str(uuid.uuid4())
        }
    
    def _authenticate(self):
        """Perform authentication."""
        auth_payload = {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "grant_type": "password"
        }
        
        with self.client.post(
            f"/api/{Config.API_VERSION}/auth/token",
            json=auth_payload,
            headers={"Content-Type": "application/json"},
            catch_response=True,
            name="POST /auth/token"
        ) as response:
            if response.status_code == 200:
                response.success()
                # In real test, would extract and store actual token
            else:
                response.failure(f"Auth failed: {response.status_code}")
    
    @task(Config.WEIGHT_ENCOUNTER)
    @tag("encounter")
    def create_encounter(self):
        """Create a new patient encounter."""
        encounter_data = TestDataGenerator.generate_encounter_data(self.tenant_id)
        
        with self.client.post(
            f"/api/{Config.API_VERSION}/encounters",
            json=encounter_data,
            headers=self._get_headers(),
            catch_response=True,
            name="POST /encounters"
        ) as response:
            start = time.time()
            if response.status_code == 201:
                response.success()
                try:
                    data = response.json()
                    self.current_encounter_id = data.get("encounter_id")
                except Exception:
                    pass
                metrics.record_request((time.time() - start) * 1000, True)
            else:
                response.failure(f"Create encounter failed: {response.status_code}")
                metrics.record_request((time.time() - start) * 1000, False)
    
    @task(Config.WEIGHT_ENCOUNTER // 2)
    @tag("encounter")
    def get_encounter(self):
        """Get encounter details."""
        if not self.current_encounter_id:
            self.current_encounter_id = f"enc-{uuid.uuid4().hex[:12]}"
        
        with self.client.get(
            f"/api/{Config.API_VERSION}/encounters/{self.current_encounter_id}",
            headers=self._get_headers(),
            catch_response=True,
            name="GET /encounters/{id}"
        ) as response:
            start = time.time()
            if response.status_code in [200, 404]:  # 404 OK for simulated IDs
                response.success()
                metrics.record_request((time.time() - start) * 1000, True)
            else:
                response.failure(f"Get encounter failed: {response.status_code}")
                metrics.record_request((time.time() - start) * 1000, False)
    
    @task(Config.WEIGHT_TRANSCRIPTION)
    @tag("transcription")
    def submit_transcription(self):
        """Submit audio for transcription."""
        if not self.current_encounter_id:
            self.current_encounter_id = f"enc-{uuid.uuid4().hex[:12]}"
        
        trans_data = TestDataGenerator.generate_transcription_request()
        trans_data["encounter_id"] = self.current_encounter_id
        
        with self.client.post(
            f"/api/{Config.API_VERSION}/transcription/submit",
            json=trans_data,
            headers=self._get_headers(),
            catch_response=True,
            name="POST /transcription/submit"
        ) as response:
            start = time.time()
            if response.status_code in [200, 202]:
                response.success()
                metrics.record_request((time.time() - start) * 1000, True)
            else:
                response.failure(f"Transcription failed: {response.status_code}")
                metrics.record_request((time.time() - start) * 1000, False)
    
    @task(Config.WEIGHT_TRANSCRIPTION // 3)
    @tag("transcription")
    def get_transcription_status(self):
        """Check transcription status."""
        if not self.current_encounter_id:
            return
        
        with self.client.get(
            f"/api/{Config.API_VERSION}/transcription/{self.current_encounter_id}/status",
            headers=self._get_headers(),
            catch_response=True,
            name="GET /transcription/{id}/status"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Get status failed: {response.status_code}")
    
    @task(Config.WEIGHT_SOAP)
    @tag("soap")
    def generate_soap_note(self):
        """Generate SOAP note for encounter."""
        if not self.current_encounter_id:
            self.current_encounter_id = f"enc-{uuid.uuid4().hex[:12]}"
        
        soap_data = TestDataGenerator.generate_soap_request(self.current_encounter_id)
        
        with self.client.post(
            f"/api/{Config.API_VERSION}/soap/generate",
            json=soap_data,
            headers=self._get_headers(),
            catch_response=True,
            name="POST /soap/generate"
        ) as response:
            start = time.time()
            if response.status_code in [200, 202]:
                response.success()
                metrics.record_request((time.time() - start) * 1000, True)
            else:
                response.failure(f"SOAP generation failed: {response.status_code}")
                metrics.record_request((time.time() - start) * 1000, False)
    
    @task(Config.WEIGHT_SOAP // 3)
    @tag("soap")
    def get_soap_note(self):
        """Get generated SOAP note."""
        if not self.current_encounter_id:
            return
        
        with self.client.get(
            f"/api/{Config.API_VERSION}/soap/{self.current_encounter_id}",
            headers=self._get_headers(),
            catch_response=True,
            name="GET /soap/{id}"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Get SOAP failed: {response.status_code}")
    
    @task(Config.WEIGHT_THREAT)
    @tag("threat")
    def get_threats(self):
        """Get recent threats for dashboard."""
        with self.client.get(
            f"/api/{Config.API_VERSION}/threats/recent",
            headers=self._get_headers(),
            params={"limit": 10},
            catch_response=True,
            name="GET /threats/recent"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Get threats failed: {response.status_code}")
    
    @task(Config.WEIGHT_AUTH)
    @tag("dashboard")
    def get_dashboard_metrics(self):
        """Get dashboard metrics."""
        with self.client.get(
            f"/api/{Config.API_VERSION}/dashboard/metrics",
            headers=self._get_headers(),
            catch_response=True,
            name="GET /dashboard/metrics"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Get metrics failed: {response.status_code}")
    
    @task(Config.WEIGHT_AUTH // 2)
    @tag("patient")
    def search_patients(self):
        """Search for patients."""
        search_query = random.choice(["Smith", "Johnson", "Williams", "Brown", "Jones"])
        
        with self.client.get(
            f"/api/{Config.API_VERSION}/patients/search",
            headers=self._get_headers(),
            params={"q": search_query, "limit": 10},
            catch_response=True,
            name="GET /patients/search"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Search failed: {response.status_code}")


class AdminUser(FastHttpUser):
    """
    Simulates an admin user with heavier dashboard usage.
    """
    
    wait_time = between(2, 5)
    weight = 1  # Less common than regular users
    
    def on_start(self):
        """Set up admin session."""
        self.tenant_id = TestDataGenerator.generate_tenant_id()
        self.user_id = f"admin-{self.tenant_id[-3:]}-001"
        self.token = TestDataGenerator.generate_jwt_token(self.tenant_id, self.user_id)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "X-Tenant-ID": self.tenant_id
        }
    
    @task(10)
    @tag("admin", "dashboard")
    def view_dashboard(self):
        """View admin dashboard."""
        with self.client.get(
            f"/api/{Config.API_VERSION}/admin/dashboard",
            headers=self._get_headers(),
            catch_response=True,
            name="GET /admin/dashboard"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Dashboard failed: {response.status_code}")
    
    @task(5)
    @tag("admin", "compliance")
    def view_compliance_report(self):
        """View compliance reports."""
        with self.client.get(
            f"/api/{Config.API_VERSION}/admin/compliance/soc2",
            headers=self._get_headers(),
            catch_response=True,
            name="GET /admin/compliance/soc2"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Compliance failed: {response.status_code}")
    
    @task(3)
    @tag("admin", "audit")
    def view_audit_logs(self):
        """View audit logs."""
        with self.client.get(
            f"/api/{Config.API_VERSION}/admin/audit/logs",
            headers=self._get_headers(),
            params={"limit": 100, "days": 7},
            catch_response=True,
            name="GET /admin/audit/logs"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Audit logs failed: {response.status_code}")


# ============================================================================
# Event Hooks for Reporting
# ============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    print("\n" + "=" * 60)
    print("Phoenix Guardian Load Test Starting")
    print("=" * 60)
    print(f"Target Host: {environment.host}")
    print(f"P95 SLA: {Config.P95_RESPONSE_TIME_MS}ms")
    print(f"P99 SLA: {Config.P99_RESPONSE_TIME_MS}ms")
    print(f"Max Error Rate: {Config.MAX_ERROR_RATE * 100}%")
    print("=" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    print("\n" + "=" * 60)
    print("Phoenix Guardian Load Test Results")
    print("=" * 60)
    
    p95 = metrics.get_p95_latency()
    p99 = metrics.get_p99_latency()
    error_rate = metrics.get_error_rate()
    throughput = metrics.get_throughput()
    
    print(f"Total Requests: {metrics.request_count}")
    print(f"Error Count: {metrics.error_count}")
    print(f"Error Rate: {error_rate * 100:.2f}%")
    print(f"Throughput: {throughput:.2f} req/s")
    print(f"P95 Latency: {p95:.2f}ms")
    print(f"P99 Latency: {p99:.2f}ms")
    print()
    
    # Check SLAs
    sla_passed = True
    
    if p95 > Config.P95_RESPONSE_TIME_MS:
        print(f"❌ FAILED: P95 ({p95:.2f}ms) > SLA ({Config.P95_RESPONSE_TIME_MS}ms)")
        sla_passed = False
    else:
        print(f"✅ PASSED: P95 ({p95:.2f}ms) <= SLA ({Config.P95_RESPONSE_TIME_MS}ms)")
    
    if p99 > Config.P99_RESPONSE_TIME_MS:
        print(f"❌ FAILED: P99 ({p99:.2f}ms) > SLA ({Config.P99_RESPONSE_TIME_MS}ms)")
        sla_passed = False
    else:
        print(f"✅ PASSED: P99 ({p99:.2f}ms) <= SLA ({Config.P99_RESPONSE_TIME_MS}ms)")
    
    if error_rate > Config.MAX_ERROR_RATE:
        print(f"❌ FAILED: Error rate ({error_rate * 100:.2f}%) > SLA ({Config.MAX_ERROR_RATE * 100}%)")
        sla_passed = False
    else:
        print(f"✅ PASSED: Error rate ({error_rate * 100:.2f}%) <= SLA ({Config.MAX_ERROR_RATE * 100}%)")
    
    print()
    if sla_passed:
        print("🎉 ALL SLAs PASSED")
    else:
        print("⚠️  SOME SLAs FAILED")
    
    print("=" * 60 + "\n")


# ============================================================================
# Standalone Test Runner
# ============================================================================

if __name__ == "__main__":
    import subprocess
    import sys
    
    # Example command to run:
    # locust -f load_test_api.py --host=https://api.phoenix-guardian.health
    #        --users=1000 --spawn-rate=50 --run-time=10m
    
    print("Phoenix Guardian Load Test")
    print()
    print("To run this load test, use:")
    print()
    print("  locust -f load_test_api.py --host=https://api.phoenix-guardian.health \\")
    print("         --users=1000 --spawn-rate=50 --run-time=10m")
    print()
    print("Or run with web UI:")
    print()
    print("  locust -f load_test_api.py --host=https://api.phoenix-guardian.health")
    print()
    print("Then open http://localhost:8089 in your browser")
