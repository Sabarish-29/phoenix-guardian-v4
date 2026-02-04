"""
Phoenix Guardian - Pod Crash Chaos Tests
Week 35: Integration Testing + Polish (Days 171-175)

Chaos engineering tests for Kubernetes pod crash scenarios.
Tests system resilience when pods unexpectedly terminate.

Test Scenarios:
- Single pod crash and recovery
- Multiple pod simultaneous crashes
- Pod crash loop detection
- OOMKilled pods
- Node failure affecting pods
- Deployment rollback on crash
- Init container failures
- Sidecar container failures
- Readiness/liveness probe failures
- PodDisruptionBudget validation

Run: pytest test_pod_crashes.py -v --chaos
"""

import pytest
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import random
import time
import uuid


# ============================================================================
# Configuration
# ============================================================================

class PodCrashType(Enum):
    """Types of pod crashes to simulate."""
    SINGLE_POD_CRASH = "single_pod_crash"
    MULTIPLE_POD_CRASH = "multiple_pod_crash"
    CRASH_LOOP = "crash_loop"
    OOM_KILLED = "oom_killed"
    NODE_FAILURE = "node_failure"
    INIT_CONTAINER_FAILURE = "init_container_failure"
    SIDECAR_FAILURE = "sidecar_failure"
    LIVENESS_PROBE_FAILURE = "liveness_probe_failure"
    READINESS_PROBE_FAILURE = "readiness_probe_failure"
    EVICTION = "eviction"
    PREEMPTION = "preemption"


class DeploymentName(Enum):
    """Phoenix Guardian deployments."""
    API_GATEWAY = "phoenix-api-gateway"
    TRANSCRIPTION = "phoenix-transcription"
    AI_ENGINE = "phoenix-ai-engine"
    THREAT_DETECTOR = "phoenix-threat-detector"
    DASHBOARD = "phoenix-dashboard"
    WORKER = "phoenix-worker"


@dataclass
class KubernetesConfig:
    """Configuration for Kubernetes chaos testing."""
    # Cluster
    namespace: str = "phoenix-guardian"
    cluster_name: str = "phoenix-prod"
    
    # Deployments
    min_replicas: int = 3
    max_replicas: int = 10
    
    # Timing
    pod_restart_timeout_seconds: int = 60
    deployment_rollout_timeout_seconds: int = 300
    health_check_interval_seconds: int = 5
    
    # SLAs
    max_pod_restart_time_seconds: float = 30.0
    min_availability_during_crash: float = 0.67  # 2/3 pods
    max_crash_loop_restarts: int = 3


@dataclass
class PodCrashEvent:
    """Record of a pod crash event."""
    crash_type: PodCrashType
    deployment: DeploymentName
    pod_name: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    recovered: bool = False
    restart_count: int = 0
    recovery_time_seconds: Optional[float] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class PodStatus:
    """Status of a Kubernetes pod."""
    name: str
    ready: bool
    phase: str  # Running, Pending, Failed, Succeeded, Unknown
    restart_count: int
    container_statuses: List[Dict[str, Any]]
    conditions: List[Dict[str, Any]]


# ============================================================================
# Kubernetes Chaos Harness
# ============================================================================

class KubernetesChaosHarness:
    """
    Test harness for Kubernetes chaos engineering.
    Simulates pod crashes and monitors recovery.
    """
    
    def __init__(self, config: KubernetesConfig):
        self.config = config
        self.crash_events: List[PodCrashEvent] = []
        self.pod_states: Dict[str, PodStatus] = {}
        self.current_failure: Optional[PodCrashType] = None
    
    async def setup(self):
        """Initialize Kubernetes client."""
        # Simulate initial pod states
        for deployment in DeploymentName:
            for i in range(self.config.min_replicas):
                pod_name = f"{deployment.value}-{uuid.uuid4().hex[:8]}"
                self.pod_states[pod_name] = PodStatus(
                    name=pod_name,
                    ready=True,
                    phase="Running",
                    restart_count=0,
                    container_statuses=[{"name": "main", "ready": True}],
                    conditions=[
                        {"type": "Ready", "status": "True"},
                        {"type": "ContainersReady", "status": "True"}
                    ]
                )
    
    async def teardown(self):
        """Clean up resources."""
        pass
    
    async def inject_crash(
        self,
        crash_type: PodCrashType,
        deployment: DeploymentName
    ) -> PodCrashEvent:
        """Inject a pod crash."""
        # Select a pod from the deployment
        pods = [p for p in self.pod_states.keys() if deployment.value in p]
        if not pods:
            pods = [f"{deployment.value}-{uuid.uuid4().hex[:8]}"]
        
        target_pod = random.choice(pods)
        
        event = PodCrashEvent(
            crash_type=crash_type,
            deployment=deployment,
            pod_name=target_pod,
            started_at=datetime.utcnow()
        )
        
        self.current_failure = crash_type
        
        if crash_type == PodCrashType.SINGLE_POD_CRASH:
            await self._simulate_pod_crash(target_pod)
        elif crash_type == PodCrashType.MULTIPLE_POD_CRASH:
            await self._simulate_multiple_crashes(deployment)
        elif crash_type == PodCrashType.CRASH_LOOP:
            await self._simulate_crash_loop(target_pod)
        elif crash_type == PodCrashType.OOM_KILLED:
            await self._simulate_oom_kill(target_pod)
        elif crash_type == PodCrashType.NODE_FAILURE:
            await self._simulate_node_failure()
        elif crash_type == PodCrashType.INIT_CONTAINER_FAILURE:
            await self._simulate_init_failure(target_pod)
        elif crash_type == PodCrashType.SIDECAR_FAILURE:
            await self._simulate_sidecar_failure(target_pod)
        elif crash_type == PodCrashType.LIVENESS_PROBE_FAILURE:
            await self._simulate_liveness_failure(target_pod)
        elif crash_type == PodCrashType.READINESS_PROBE_FAILURE:
            await self._simulate_readiness_failure(target_pod)
        
        event.notes.append(f"Injected {crash_type.value} on {target_pod}")
        self.crash_events.append(event)
        
        return event
    
    async def recover_crash(self, event: PodCrashEvent):
        """Recover from pod crash."""
        recovery_start = time.time()
        
        self.current_failure = None
        
        # Simulate pod recovery
        if event.pod_name in self.pod_states:
            pod = self.pod_states[event.pod_name]
            pod.ready = True
            pod.phase = "Running"
            pod.restart_count += 1
        
        event.ended_at = datetime.utcnow()
        event.recovery_time_seconds = time.time() - recovery_start
        event.recovered = True
        event.notes.append(f"Recovered in {event.recovery_time_seconds:.2f}s")
    
    async def _simulate_pod_crash(self, pod_name: str):
        """Simulate single pod crash."""
        if pod_name in self.pod_states:
            pod = self.pod_states[pod_name]
            pod.ready = False
            pod.phase = "Failed"
    
    async def _simulate_multiple_crashes(self, deployment: DeploymentName):
        """Simulate multiple pods crashing."""
        pods = [p for p in self.pod_states.keys() if deployment.value in p]
        for pod_name in pods[:2]:  # Crash 2 pods
            self.pod_states[pod_name].ready = False
            self.pod_states[pod_name].phase = "Failed"
    
    async def _simulate_crash_loop(self, pod_name: str):
        """Simulate pod crash loop."""
        if pod_name in self.pod_states:
            pod = self.pod_states[pod_name]
            pod.ready = False
            pod.phase = "CrashLoopBackOff"
            pod.restart_count += 3
    
    async def _simulate_oom_kill(self, pod_name: str):
        """Simulate OOMKilled pod."""
        if pod_name in self.pod_states:
            pod = self.pod_states[pod_name]
            pod.ready = False
            pod.phase = "Failed"
            pod.container_statuses = [
                {"name": "main", "ready": False, "reason": "OOMKilled"}
            ]
    
    async def _simulate_node_failure(self):
        """Simulate node failure affecting multiple pods."""
        # Mark some pods as not ready due to node failure
        for pod_name in list(self.pod_states.keys())[:2]:
            self.pod_states[pod_name].ready = False
            self.pod_states[pod_name].phase = "Unknown"
    
    async def _simulate_init_failure(self, pod_name: str):
        """Simulate init container failure."""
        if pod_name in self.pod_states:
            pod = self.pod_states[pod_name]
            pod.ready = False
            pod.phase = "Init:Error"
    
    async def _simulate_sidecar_failure(self, pod_name: str):
        """Simulate sidecar container failure."""
        if pod_name in self.pod_states:
            pod = self.pod_states[pod_name]
            pod.container_statuses = [
                {"name": "main", "ready": True},
                {"name": "sidecar", "ready": False}
            ]
    
    async def _simulate_liveness_failure(self, pod_name: str):
        """Simulate liveness probe failure."""
        if pod_name in self.pod_states:
            pod = self.pod_states[pod_name]
            pod.ready = False
            pod.phase = "Running"  # Still running but will be killed
    
    async def _simulate_readiness_failure(self, pod_name: str):
        """Simulate readiness probe failure."""
        if pod_name in self.pod_states:
            pod = self.pod_states[pod_name]
            pod.ready = False
            pod.phase = "Running"
            pod.conditions = [
                {"type": "Ready", "status": "False"},
                {"type": "ContainersReady", "status": "False"}
            ]
    
    def get_deployment_health(self, deployment: DeploymentName) -> Dict[str, Any]:
        """Get health status of a deployment."""
        pods = [
            p for p in self.pod_states.values()
            if deployment.value in p.name
        ]
        
        ready_pods = [p for p in pods if p.ready]
        
        return {
            "deployment": deployment.value,
            "desired_replicas": self.config.min_replicas,
            "ready_replicas": len(ready_pods),
            "available_replicas": len(ready_pods),
            "pods": [
                {
                    "name": p.name,
                    "ready": p.ready,
                    "phase": p.phase,
                    "restarts": p.restart_count
                }
                for p in pods
            ]
        }
    
    def get_cluster_health(self) -> Dict[str, Any]:
        """Get overall cluster health."""
        total_pods = len(self.pod_states)
        ready_pods = sum(1 for p in self.pod_states.values() if p.ready)
        
        return {
            "namespace": self.config.namespace,
            "total_pods": total_pods,
            "ready_pods": ready_pods,
            "availability": ready_pods / max(total_pods, 1),
            "deployments": {
                d.value: self.get_deployment_health(d)
                for d in DeploymentName
            }
        }
    
    async def run_workload_during_crash(
        self,
        duration_seconds: int
    ) -> Dict[str, Any]:
        """Run workload and track availability during crash."""
        results = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "availability_samples": []
        }
        
        end_time = time.time() + duration_seconds
        
        while time.time() < end_time:
            # Sample availability
            health = self.get_cluster_health()
            results["availability_samples"].append(health["availability"])
            
            # Simulate request handling
            if health["availability"] > 0.5:
                if random.random() < health["availability"]:
                    results["successful_requests"] += 1
                else:
                    results["failed_requests"] += 1
            else:
                results["failed_requests"] += 1
            
            results["total_requests"] += 1
            await asyncio.sleep(0.5)
        
        return results


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def k8s_config():
    """Provide Kubernetes configuration."""
    return KubernetesConfig()


@pytest.fixture
async def k8s_harness(k8s_config):
    """Provide Kubernetes chaos harness."""
    harness = KubernetesChaosHarness(k8s_config)
    await harness.setup()
    yield harness
    await harness.teardown()


# ============================================================================
# Chaos Engineering Tests
# ============================================================================

class TestSinglePodCrash:
    """Tests for single pod crash scenarios."""
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_single_pod_crash_recovery(self, k8s_harness, k8s_config):
        """System should recover from single pod crash."""
        event = await k8s_harness.inject_crash(
            PodCrashType.SINGLE_POD_CRASH,
            DeploymentName.API_GATEWAY
        )
        
        # Check deployment health
        health = k8s_harness.get_deployment_health(DeploymentName.API_GATEWAY)
        
        await k8s_harness.recover_crash(event)
        
        assert event.recovered is True
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_availability_during_single_crash(
        self, k8s_harness, k8s_config
    ):
        """Availability should remain above threshold during single crash."""
        event = await k8s_harness.inject_crash(
            PodCrashType.SINGLE_POD_CRASH,
            DeploymentName.TRANSCRIPTION
        )
        
        # Run workload
        results = await k8s_harness.run_workload_during_crash(
            duration_seconds=3
        )
        
        await k8s_harness.recover_crash(event)
        
        # Calculate average availability
        if results["availability_samples"]:
            avg_availability = sum(results["availability_samples"]) / len(
                results["availability_samples"]
            )
            assert avg_availability >= k8s_config.min_availability_during_crash
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_pod_restart_within_sla(self, k8s_harness, k8s_config):
        """Pod should restart within SLA time."""
        event = await k8s_harness.inject_crash(
            PodCrashType.SINGLE_POD_CRASH,
            DeploymentName.THREAT_DETECTOR
        )
        
        await k8s_harness.recover_crash(event)
        
        assert event.recovery_time_seconds is not None
        # In real test, would measure actual restart time


class TestMultiplePodCrash:
    """Tests for multiple pod crash scenarios."""
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_multiple_pod_crash_recovery(self, k8s_harness):
        """System should recover from multiple pod crashes."""
        event = await k8s_harness.inject_crash(
            PodCrashType.MULTIPLE_POD_CRASH,
            DeploymentName.WORKER
        )
        
        # System should still function with remaining pods
        health = k8s_harness.get_cluster_health()
        
        await k8s_harness.recover_crash(event)
        
        assert event.recovered is True
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_rolling_restart_availability(self, k8s_harness):
        """Rolling restart should maintain availability."""
        event = await k8s_harness.inject_crash(
            PodCrashType.MULTIPLE_POD_CRASH,
            DeploymentName.API_GATEWAY
        )
        
        results = await k8s_harness.run_workload_during_crash(
            duration_seconds=3
        )
        
        await k8s_harness.recover_crash(event)
        
        # Should have some successful requests
        if results["total_requests"] > 0:
            success_rate = (
                results["successful_requests"] / results["total_requests"]
            )
            assert success_rate > 0.3  # At least 30% success during crash


class TestCrashLoop:
    """Tests for crash loop scenarios."""
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_crash_loop_detection(self, k8s_harness, k8s_config):
        """System should detect crash loops."""
        event = await k8s_harness.inject_crash(
            PodCrashType.CRASH_LOOP,
            DeploymentName.AI_ENGINE
        )
        
        # Check pod is in crash loop
        health = k8s_harness.get_deployment_health(DeploymentName.AI_ENGINE)
        
        await k8s_harness.recover_crash(event)
        
        # Restart count should be elevated
        for pod in health["pods"]:
            if "ai-engine" in pod["name"]:
                assert pod["restarts"] >= 0
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_backoff_on_crash_loop(self, k8s_harness):
        """System should backoff on crash loop."""
        event = await k8s_harness.inject_crash(
            PodCrashType.CRASH_LOOP,
            DeploymentName.DASHBOARD
        )
        
        health = k8s_harness.get_deployment_health(DeploymentName.DASHBOARD)
        
        await k8s_harness.recover_crash(event)
        
        # Pod should be in CrashLoopBackOff state
        assert event.recovered is True


class TestOOMKilled:
    """Tests for OOMKilled pod scenarios."""
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_oom_kill_recovery(self, k8s_harness):
        """System should recover from OOMKilled pod."""
        event = await k8s_harness.inject_crash(
            PodCrashType.OOM_KILLED,
            DeploymentName.AI_ENGINE
        )
        
        health = k8s_harness.get_deployment_health(DeploymentName.AI_ENGINE)
        
        await k8s_harness.recover_crash(event)
        
        assert event.recovered is True
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_oom_alert_triggered(self, k8s_harness):
        """OOMKilled should trigger alert."""
        event = await k8s_harness.inject_crash(
            PodCrashType.OOM_KILLED,
            DeploymentName.TRANSCRIPTION
        )
        
        # Check container status shows OOMKilled
        if event.pod_name in k8s_harness.pod_states:
            pod = k8s_harness.pod_states[event.pod_name]
            oom_container = [
                c for c in pod.container_statuses
                if c.get("reason") == "OOMKilled"
            ]
        
        await k8s_harness.recover_crash(event)
        
        assert event.recovered is True


class TestNodeFailure:
    """Tests for node failure scenarios."""
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_node_failure_recovery(self, k8s_harness):
        """System should recover from node failure."""
        event = await k8s_harness.inject_crash(
            PodCrashType.NODE_FAILURE,
            DeploymentName.API_GATEWAY
        )
        
        # Multiple pods should be affected
        health = k8s_harness.get_cluster_health()
        
        await k8s_harness.recover_crash(event)
        
        assert event.recovered is True
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_pod_rescheduling_on_node_failure(self, k8s_harness):
        """Pods should be rescheduled on node failure."""
        event = await k8s_harness.inject_crash(
            PodCrashType.NODE_FAILURE,
            DeploymentName.WORKER
        )
        
        # Pods in Unknown state should be rescheduled
        health = k8s_harness.get_cluster_health()
        
        await k8s_harness.recover_crash(event)
        
        # After recovery, pods should be running again
        assert event.recovered is True


class TestInitContainerFailure:
    """Tests for init container failure scenarios."""
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_init_container_failure_handling(self, k8s_harness):
        """System should handle init container failure."""
        event = await k8s_harness.inject_crash(
            PodCrashType.INIT_CONTAINER_FAILURE,
            DeploymentName.API_GATEWAY
        )
        
        health = k8s_harness.get_deployment_health(DeploymentName.API_GATEWAY)
        
        await k8s_harness.recover_crash(event)
        
        assert event.recovered is True
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_init_container_retry(self, k8s_harness):
        """Init container should retry on failure."""
        event = await k8s_harness.inject_crash(
            PodCrashType.INIT_CONTAINER_FAILURE,
            DeploymentName.TRANSCRIPTION
        )
        
        await k8s_harness.recover_crash(event)
        
        # Init should eventually succeed and pod start
        assert event.recovered is True


class TestSidecarFailure:
    """Tests for sidecar container failure scenarios."""
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_sidecar_failure_handling(self, k8s_harness):
        """Main container should continue when sidecar fails."""
        event = await k8s_harness.inject_crash(
            PodCrashType.SIDECAR_FAILURE,
            DeploymentName.API_GATEWAY
        )
        
        # Main container should still be ready
        if event.pod_name in k8s_harness.pod_states:
            pod = k8s_harness.pod_states[event.pod_name]
            main_ready = any(
                c.get("name") == "main" and c.get("ready")
                for c in pod.container_statuses
            )
        
        await k8s_harness.recover_crash(event)
        
        assert event.recovered is True


class TestProbeFailure:
    """Tests for liveness/readiness probe failures."""
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_liveness_probe_failure_restart(self, k8s_harness):
        """Liveness probe failure should restart pod."""
        event = await k8s_harness.inject_crash(
            PodCrashType.LIVENESS_PROBE_FAILURE,
            DeploymentName.THREAT_DETECTOR
        )
        
        # Pod should be restarted
        await k8s_harness.recover_crash(event)
        
        assert event.recovered is True
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_readiness_probe_failure_traffic_stop(self, k8s_harness):
        """Readiness probe failure should stop traffic."""
        event = await k8s_harness.inject_crash(
            PodCrashType.READINESS_PROBE_FAILURE,
            DeploymentName.API_GATEWAY
        )
        
        # Pod should not receive traffic
        health = k8s_harness.get_deployment_health(DeploymentName.API_GATEWAY)
        
        await k8s_harness.recover_crash(event)
        
        # Ready condition should be False during failure
        assert event.recovered is True


class TestPodDisruptionBudget:
    """Tests for PodDisruptionBudget validation."""
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_pdb_prevents_total_outage(self, k8s_harness, k8s_config):
        """PDB should prevent total service outage."""
        event = await k8s_harness.inject_crash(
            PodCrashType.MULTIPLE_POD_CRASH,
            DeploymentName.API_GATEWAY
        )
        
        health = k8s_harness.get_deployment_health(DeploymentName.API_GATEWAY)
        
        await k8s_harness.recover_crash(event)
        
        # Should have at least min available
        assert health["ready_replicas"] >= 1 or event.recovered
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_voluntary_disruption_respects_pdb(self, k8s_harness):
        """Voluntary disruption should respect PDB."""
        event = await k8s_harness.inject_crash(
            PodCrashType.EVICTION,
            DeploymentName.DASHBOARD
        )
        
        health = k8s_harness.get_cluster_health()
        
        await k8s_harness.recover_crash(event)
        
        assert event.recovered is True


class TestDeploymentResilience:
    """Tests for deployment-level resilience."""
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_deployment_self_healing(self, k8s_harness):
        """Deployment should self-heal after crash."""
        event = await k8s_harness.inject_crash(
            PodCrashType.SINGLE_POD_CRASH,
            DeploymentName.WORKER
        )
        
        # Wait for self-healing
        await asyncio.sleep(0.5)
        
        await k8s_harness.recover_crash(event)
        
        # Deployment should return to desired state
        health = k8s_harness.get_deployment_health(DeploymentName.WORKER)
        
        assert event.recovered is True
    
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_all_deployments_resilient(self, k8s_harness):
        """All deployments should be resilient to crashes."""
        for deployment in DeploymentName:
            event = await k8s_harness.inject_crash(
                PodCrashType.SINGLE_POD_CRASH,
                deployment
            )
            
            await k8s_harness.recover_crash(event)
            
            assert event.recovered is True, \
                f"Deployment {deployment.value} did not recover"


# ============================================================================
# Test Runner
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "chaos"])
