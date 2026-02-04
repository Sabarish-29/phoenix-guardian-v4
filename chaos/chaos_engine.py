"""
Phoenix Guardian - Chaos Engineering Framework
Sprint 71-72: Chaos Engineering

Production chaos experiments for resilience validation.
"""

import asyncio
import json
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ExperimentState(Enum):
    """Chaos experiment lifecycle states."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    ROLLED_BACK = "rolled_back"


class FaultType(Enum):
    """Types of fault injection."""
    
    # Network faults
    NETWORK_LATENCY = "network_latency"
    NETWORK_PARTITION = "network_partition"
    NETWORK_PACKET_LOSS = "network_packet_loss"
    NETWORK_BANDWIDTH = "network_bandwidth"
    DNS_FAILURE = "dns_failure"
    
    # Pod faults
    POD_KILL = "pod_kill"
    POD_FAILURE = "pod_failure"
    CONTAINER_KILL = "container_kill"
    
    # Resource faults
    CPU_STRESS = "cpu_stress"
    MEMORY_STRESS = "memory_stress"
    DISK_FILL = "disk_fill"
    IO_STRESS = "io_stress"
    
    # Application faults
    HTTP_ABORT = "http_abort"
    HTTP_DELAY = "http_delay"
    GRPC_ABORT = "grpc_abort"
    
    # AWS faults
    EC2_TERMINATE = "ec2_terminate"
    RDS_FAILOVER = "rds_failover"
    AZ_FAILURE = "az_failure"


class TargetType(Enum):
    """Chaos experiment target types."""
    
    DEPLOYMENT = "deployment"
    STATEFULSET = "statefulset"
    DAEMONSET = "daemonset"
    POD = "pod"
    NODE = "node"
    SERVICE = "service"
    NAMESPACE = "namespace"


@dataclass
class SteadyStateHypothesis:
    """
    Defines the expected steady state before and after experiment.
    
    Based on Chaos Engineering Principles:
    "Define 'steady state' as some measurable output of a system 
    that indicates normal behavior."
    """
    
    name: str
    description: str
    
    # Probes to check steady state
    probes: list[dict[str, Any]] = field(default_factory=list)
    
    # Tolerance for deviation
    tolerance: float = 0.05  # 5% deviation allowed
    
    # Timeout for checking
    timeout_seconds: int = 60


@dataclass
class ChaosAction:
    """Single chaos action to perform."""
    
    type: FaultType
    duration_seconds: int = 60
    
    # Target specification
    target_type: TargetType = TargetType.DEPLOYMENT
    target_name: str = ""
    target_namespace: str = "phoenix-production"
    
    # Fault-specific parameters
    parameters: dict[str, Any] = field(default_factory=dict)
    
    # Blast radius control
    percentage: int = 50  # Affect 50% of targets by default
    
    # Labels for targeting
    label_selectors: dict[str, str] = field(default_factory=dict)


@dataclass
class ChaosExperiment:
    """
    Complete chaos experiment definition.
    
    Follows the Chaos Engineering experiment workflow:
    1. Define steady state
    2. Hypothesize steady state continues during/after experiment
    3. Introduce variables (faults)
    4. Disprove hypothesis by observing impact
    """
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    
    # Tags for organization
    tags: list[str] = field(default_factory=list)
    
    # Steady state hypothesis
    steady_state: Optional[SteadyStateHypothesis] = None
    
    # Chaos actions to perform
    actions: list[ChaosAction] = field(default_factory=list)
    
    # Rollback actions
    rollback_actions: list[dict[str, Any]] = field(default_factory=list)
    
    # Scheduling
    schedule: Optional[str] = None  # Cron expression
    
    # Safety controls
    dry_run: bool = False
    auto_rollback: bool = True
    abort_on_failure: bool = True
    
    # Blast radius limits
    max_affected_pods: int = 5
    max_duration_seconds: int = 300
    
    # State
    state: ExperimentState = ExperimentState.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Results
    results: dict[str, Any] = field(default_factory=dict)
    
    def to_chaos_mesh(self) -> dict[str, Any]:
        """Convert to Chaos Mesh CRD format."""
        if not self.actions:
            raise ValueError("Experiment has no actions")
        
        action = self.actions[0]  # Primary action
        
        # Build Chaos Mesh spec based on fault type
        if action.type in [FaultType.POD_KILL, FaultType.POD_FAILURE, FaultType.CONTAINER_KILL]:
            return self._build_pod_chaos(action)
        elif action.type in [FaultType.NETWORK_LATENCY, FaultType.NETWORK_PARTITION, FaultType.NETWORK_PACKET_LOSS]:
            return self._build_network_chaos(action)
        elif action.type in [FaultType.CPU_STRESS, FaultType.MEMORY_STRESS]:
            return self._build_stress_chaos(action)
        elif action.type in [FaultType.HTTP_ABORT, FaultType.HTTP_DELAY]:
            return self._build_http_chaos(action)
        else:
            raise ValueError(f"Unsupported fault type: {action.type}")
    
    def _build_pod_chaos(self, action: ChaosAction) -> dict[str, Any]:
        """Build PodChaos CRD."""
        return {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "PodChaos",
            "metadata": {
                "name": self.name,
                "namespace": action.target_namespace,
                "labels": {
                    "experiment-id": self.id,
                    "phoenix-chaos": "true",
                },
            },
            "spec": {
                "action": action.type.value.replace("pod_", ""),
                "mode": "fixed-percent",
                "value": str(action.percentage),
                "duration": f"{action.duration_seconds}s",
                "selector": {
                    "namespaces": [action.target_namespace],
                    "labelSelectors": action.label_selectors or {
                        "app": action.target_name,
                    },
                },
            },
        }
    
    def _build_network_chaos(self, action: ChaosAction) -> dict[str, Any]:
        """Build NetworkChaos CRD."""
        spec = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "NetworkChaos",
            "metadata": {
                "name": self.name,
                "namespace": action.target_namespace,
                "labels": {
                    "experiment-id": self.id,
                    "phoenix-chaos": "true",
                },
            },
            "spec": {
                "action": action.type.value.replace("network_", ""),
                "mode": "fixed-percent",
                "value": str(action.percentage),
                "duration": f"{action.duration_seconds}s",
                "selector": {
                    "namespaces": [action.target_namespace],
                    "labelSelectors": action.label_selectors or {
                        "app": action.target_name,
                    },
                },
            },
        }
        
        # Add fault-specific parameters
        if action.type == FaultType.NETWORK_LATENCY:
            spec["spec"]["delay"] = {
                "latency": action.parameters.get("latency", "100ms"),
                "jitter": action.parameters.get("jitter", "10ms"),
                "correlation": action.parameters.get("correlation", "50"),
            }
        elif action.type == FaultType.NETWORK_PACKET_LOSS:
            spec["spec"]["loss"] = {
                "loss": action.parameters.get("loss", "10"),
                "correlation": action.parameters.get("correlation", "50"),
            }
        
        return spec
    
    def _build_stress_chaos(self, action: ChaosAction) -> dict[str, Any]:
        """Build StressChaos CRD."""
        spec = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "StressChaos",
            "metadata": {
                "name": self.name,
                "namespace": action.target_namespace,
                "labels": {
                    "experiment-id": self.id,
                    "phoenix-chaos": "true",
                },
            },
            "spec": {
                "mode": "fixed-percent",
                "value": str(action.percentage),
                "duration": f"{action.duration_seconds}s",
                "selector": {
                    "namespaces": [action.target_namespace],
                    "labelSelectors": action.label_selectors or {
                        "app": action.target_name,
                    },
                },
                "stressors": {},
            },
        }
        
        if action.type == FaultType.CPU_STRESS:
            spec["spec"]["stressors"]["cpu"] = {
                "workers": action.parameters.get("workers", 2),
                "load": action.parameters.get("load", 80),
            }
        elif action.type == FaultType.MEMORY_STRESS:
            spec["spec"]["stressors"]["memory"] = {
                "workers": action.parameters.get("workers", 2),
                "size": action.parameters.get("size", "256MB"),
            }
        
        return spec
    
    def _build_http_chaos(self, action: ChaosAction) -> dict[str, Any]:
        """Build HTTPChaos CRD."""
        spec = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "HTTPChaos",
            "metadata": {
                "name": self.name,
                "namespace": action.target_namespace,
                "labels": {
                    "experiment-id": self.id,
                    "phoenix-chaos": "true",
                },
            },
            "spec": {
                "mode": "fixed-percent",
                "value": str(action.percentage),
                "duration": f"{action.duration_seconds}s",
                "target": "Request",
                "selector": {
                    "namespaces": [action.target_namespace],
                    "labelSelectors": action.label_selectors or {
                        "app": action.target_name,
                    },
                },
                "port": action.parameters.get("port", 8000),
            },
        }
        
        if action.type == FaultType.HTTP_ABORT:
            spec["spec"]["abort"] = True
        elif action.type == FaultType.HTTP_DELAY:
            spec["spec"]["delay"] = action.parameters.get("delay", "1s")
        
        return spec


class ChaosRunner(ABC):
    """Abstract base for chaos experiment runners."""
    
    @abstractmethod
    async def run_experiment(self, experiment: ChaosExperiment) -> dict[str, Any]:
        """Execute a chaos experiment."""
        pass
    
    @abstractmethod
    async def abort_experiment(self, experiment_id: str) -> bool:
        """Abort a running experiment."""
        pass
    
    @abstractmethod
    async def rollback_experiment(self, experiment_id: str) -> bool:
        """Rollback experiment effects."""
        pass


class ChaosMeshRunner(ChaosRunner):
    """
    Chaos Mesh-based experiment runner.
    
    Uses Chaos Mesh CRDs for Kubernetes-native chaos engineering.
    """
    
    def __init__(self, kubeconfig: Optional[str] = None):
        self.kubeconfig = kubeconfig
        self._experiments: dict[str, ChaosExperiment] = {}
    
    async def run_experiment(self, experiment: ChaosExperiment) -> dict[str, Any]:
        """Execute chaos experiment using Chaos Mesh."""
        logger.info(f"Starting chaos experiment: {experiment.name}")
        
        experiment.state = ExperimentState.RUNNING
        experiment.started_at = datetime.utcnow()
        self._experiments[experiment.id] = experiment
        
        results = {
            "experiment_id": experiment.id,
            "name": experiment.name,
            "started_at": experiment.started_at.isoformat(),
            "actions": [],
            "steady_state_before": None,
            "steady_state_after": None,
            "success": False,
        }
        
        try:
            # 1. Check steady state before
            if experiment.steady_state:
                logger.info("Checking steady state before experiment...")
                results["steady_state_before"] = await self._check_steady_state(
                    experiment.steady_state
                )
                
                if not results["steady_state_before"]["passed"]:
                    logger.warning("Steady state check failed before experiment")
                    if experiment.abort_on_failure:
                        experiment.state = ExperimentState.FAILED
                        results["error"] = "Pre-experiment steady state check failed"
                        return results
            
            # 2. Execute chaos actions
            for i, action in enumerate(experiment.actions):
                logger.info(f"Executing action {i+1}/{len(experiment.actions)}: {action.type.value}")
                
                if experiment.dry_run:
                    action_result = {"action": action.type.value, "dry_run": True, "success": True}
                else:
                    action_result = await self._execute_action(experiment, action)
                
                results["actions"].append(action_result)
                
                if not action_result.get("success") and experiment.abort_on_failure:
                    logger.error(f"Action failed, aborting experiment")
                    if experiment.auto_rollback:
                        await self.rollback_experiment(experiment.id)
                    experiment.state = ExperimentState.FAILED
                    return results
            
            # 3. Wait for actions to complete
            total_duration = sum(a.duration_seconds for a in experiment.actions)
            logger.info(f"Waiting {total_duration}s for chaos actions to complete...")
            await asyncio.sleep(total_duration if not experiment.dry_run else 1)
            
            # 4. Check steady state after
            if experiment.steady_state:
                logger.info("Checking steady state after experiment...")
                results["steady_state_after"] = await self._check_steady_state(
                    experiment.steady_state
                )
            
            # 5. Determine success
            results["success"] = self._evaluate_success(experiment, results)
            experiment.state = ExperimentState.COMPLETED
            experiment.completed_at = datetime.utcnow()
            
            # 6. Cleanup
            await self._cleanup_chaos_resources(experiment)
            
        except Exception as e:
            logger.error(f"Experiment failed with exception: {e}")
            experiment.state = ExperimentState.FAILED
            results["error"] = str(e)
            
            if experiment.auto_rollback:
                await self.rollback_experiment(experiment.id)
        
        experiment.results = results
        results["completed_at"] = datetime.utcnow().isoformat()
        results["duration_seconds"] = (
            experiment.completed_at - experiment.started_at
        ).total_seconds() if experiment.completed_at else 0
        
        return results
    
    async def _execute_action(
        self, 
        experiment: ChaosExperiment, 
        action: ChaosAction
    ) -> dict[str, Any]:
        """Execute a single chaos action."""
        try:
            # Build Chaos Mesh manifest
            manifest = experiment.to_chaos_mesh()
            
            # Apply to cluster (using kubectl or kubernetes client)
            # In production, this would use kubernetes.client
            logger.info(f"Applying Chaos Mesh manifest: {manifest['kind']}")
            
            # Simulated apply
            return {
                "action": action.type.value,
                "target": action.target_name,
                "namespace": action.target_namespace,
                "duration": action.duration_seconds,
                "success": True,
                "chaos_resource": manifest["metadata"]["name"],
            }
            
        except Exception as e:
            return {
                "action": action.type.value,
                "success": False,
                "error": str(e),
            }
    
    async def _check_steady_state(
        self, 
        hypothesis: SteadyStateHypothesis
    ) -> dict[str, Any]:
        """Check steady state hypothesis."""
        results = {
            "name": hypothesis.name,
            "probes": [],
            "passed": True,
        }
        
        for probe in hypothesis.probes:
            probe_result = await self._execute_probe(probe)
            results["probes"].append(probe_result)
            
            if not probe_result.get("passed"):
                results["passed"] = False
        
        return results
    
    async def _execute_probe(self, probe: dict[str, Any]) -> dict[str, Any]:
        """Execute a steady state probe."""
        probe_type = probe.get("type", "http")
        
        if probe_type == "http":
            return await self._http_probe(probe)
        elif probe_type == "prometheus":
            return await self._prometheus_probe(probe)
        elif probe_type == "kubernetes":
            return await self._kubernetes_probe(probe)
        else:
            return {"type": probe_type, "passed": False, "error": "Unknown probe type"}
    
    async def _http_probe(self, probe: dict[str, Any]) -> dict[str, Any]:
        """Execute HTTP health check probe."""
        import aiohttp
        
        url = probe.get("url", "http://localhost:8000/health")
        expected_status = probe.get("expected_status", 200)
        timeout = probe.get("timeout", 10)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    passed = response.status == expected_status
                    return {
                        "type": "http",
                        "url": url,
                        "status": response.status,
                        "expected": expected_status,
                        "passed": passed,
                    }
        except Exception as e:
            return {
                "type": "http",
                "url": url,
                "passed": False,
                "error": str(e),
            }
    
    async def _prometheus_probe(self, probe: dict[str, Any]) -> dict[str, Any]:
        """Execute Prometheus query probe."""
        query = probe.get("query", "")
        expected_value = probe.get("expected_value", 1.0)
        operator = probe.get("operator", ">=")
        
        # In production, query Prometheus
        # Simulated response
        actual_value = 0.95  # Simulated
        
        if operator == ">=":
            passed = actual_value >= expected_value
        elif operator == "<=":
            passed = actual_value <= expected_value
        elif operator == "==":
            passed = abs(actual_value - expected_value) < 0.01
        else:
            passed = False
        
        return {
            "type": "prometheus",
            "query": query,
            "actual_value": actual_value,
            "expected_value": expected_value,
            "operator": operator,
            "passed": passed,
        }
    
    async def _kubernetes_probe(self, probe: dict[str, Any]) -> dict[str, Any]:
        """Execute Kubernetes resource probe."""
        resource_type = probe.get("resource_type", "deployment")
        name = probe.get("name", "")
        namespace = probe.get("namespace", "default")
        condition = probe.get("condition", "Available")
        
        # In production, use kubernetes client
        # Simulated response
        return {
            "type": "kubernetes",
            "resource": f"{resource_type}/{name}",
            "namespace": namespace,
            "condition": condition,
            "status": "True",
            "passed": True,
        }
    
    def _evaluate_success(
        self, 
        experiment: ChaosExperiment, 
        results: dict[str, Any]
    ) -> bool:
        """Evaluate if experiment was successful."""
        # All actions succeeded
        actions_passed = all(a.get("success") for a in results.get("actions", []))
        
        # Steady state maintained
        steady_state_passed = True
        if experiment.steady_state:
            if results.get("steady_state_after"):
                steady_state_passed = results["steady_state_after"].get("passed", False)
        
        return actions_passed and steady_state_passed
    
    async def _cleanup_chaos_resources(self, experiment: ChaosExperiment) -> None:
        """Cleanup Chaos Mesh resources after experiment."""
        logger.info(f"Cleaning up chaos resources for experiment: {experiment.name}")
        # In production, delete Chaos Mesh CRDs
    
    async def abort_experiment(self, experiment_id: str) -> bool:
        """Abort a running experiment."""
        if experiment_id not in self._experiments:
            return False
        
        experiment = self._experiments[experiment_id]
        if experiment.state != ExperimentState.RUNNING:
            return False
        
        logger.warning(f"Aborting experiment: {experiment.name}")
        experiment.state = ExperimentState.ABORTED
        
        # Cleanup chaos resources
        await self._cleanup_chaos_resources(experiment)
        
        return True
    
    async def rollback_experiment(self, experiment_id: str) -> bool:
        """Rollback experiment effects."""
        if experiment_id not in self._experiments:
            return False
        
        experiment = self._experiments[experiment_id]
        logger.info(f"Rolling back experiment: {experiment.name}")
        
        # Execute rollback actions
        for rollback in experiment.rollback_actions:
            logger.info(f"Executing rollback: {rollback}")
            # In production, execute rollback actions
        
        # Cleanup chaos resources
        await self._cleanup_chaos_resources(experiment)
        
        experiment.state = ExperimentState.ROLLED_BACK
        return True


# =============================================================================
# PREDEFINED EXPERIMENTS FOR PHOENIX GUARDIAN
# =============================================================================

class PhoenixExperiments:
    """Pre-defined chaos experiments for Phoenix Guardian."""
    
    @staticmethod
    def api_pod_failure() -> ChaosExperiment:
        """Test API resilience to pod failures."""
        return ChaosExperiment(
            name="phoenix-api-pod-failure",
            description="Kill 30% of API pods to test auto-scaling and load balancing",
            tags=["api", "pod-failure", "resilience"],
            steady_state=SteadyStateHypothesis(
                name="API availability",
                description="API responds to health checks",
                probes=[
                    {
                        "type": "http",
                        "url": "http://phoenix-api:8000/health",
                        "expected_status": 200,
                    },
                    {
                        "type": "prometheus",
                        "query": "sum(up{job='phoenix-api'})",
                        "expected_value": 3,
                        "operator": ">=",
                    },
                ],
            ),
            actions=[
                ChaosAction(
                    type=FaultType.POD_KILL,
                    target_name="phoenix-api",
                    target_namespace="phoenix-production",
                    percentage=30,
                    duration_seconds=60,
                ),
            ],
            max_affected_pods=3,
            max_duration_seconds=120,
        )
    
    @staticmethod
    def database_latency() -> ChaosExperiment:
        """Test application behavior under database latency."""
        return ChaosExperiment(
            name="phoenix-db-latency",
            description="Inject 500ms latency to database connections",
            tags=["database", "network", "latency"],
            steady_state=SteadyStateHypothesis(
                name="SOAP generation works",
                description="SOAP notes can be generated within SLO",
                probes=[
                    {
                        "type": "http",
                        "url": "http://phoenix-api:8000/health",
                        "expected_status": 200,
                    },
                ],
            ),
            actions=[
                ChaosAction(
                    type=FaultType.NETWORK_LATENCY,
                    target_name="phoenix-api",
                    target_namespace="phoenix-production",
                    percentage=100,
                    duration_seconds=120,
                    parameters={
                        "latency": "500ms",
                        "jitter": "50ms",
                    },
                    label_selectors={
                        "app": "phoenix-api",
                    },
                ),
            ],
        )
    
    @staticmethod
    def redis_failure() -> ChaosExperiment:
        """Test behavior when Redis cache is unavailable."""
        return ChaosExperiment(
            name="phoenix-redis-failure",
            description="Kill Redis pods to test cache failure handling",
            tags=["redis", "cache", "pod-failure"],
            steady_state=SteadyStateHypothesis(
                name="System operational without cache",
                description="API continues to work (with degraded performance)",
                probes=[
                    {
                        "type": "http",
                        "url": "http://phoenix-api:8000/health",
                        "expected_status": 200,
                    },
                ],
            ),
            actions=[
                ChaosAction(
                    type=FaultType.POD_KILL,
                    target_name="redis",
                    target_namespace="phoenix-production",
                    percentage=100,
                    duration_seconds=60,
                    label_selectors={
                        "app": "redis",
                    },
                ),
            ],
        )
    
    @staticmethod
    def ml_node_failure() -> ChaosExperiment:
        """Test ML inference when GPU nodes fail."""
        return ChaosExperiment(
            name="phoenix-ml-node-failure",
            description="Test ML inference failover when GPU node is unavailable",
            tags=["ml", "gpu", "node-failure"],
            steady_state=SteadyStateHypothesis(
                name="ML inference available",
                description="Beacon ML service responds",
                probes=[
                    {
                        "type": "http",
                        "url": "http://phoenix-beacon:8080/health",
                        "expected_status": 200,
                    },
                ],
            ),
            actions=[
                ChaosAction(
                    type=FaultType.POD_KILL,
                    target_name="phoenix-beacon",
                    target_namespace="phoenix-production",
                    percentage=50,
                    duration_seconds=180,
                ),
            ],
        )
    
    @staticmethod
    def cpu_stress() -> ChaosExperiment:
        """Test behavior under CPU pressure."""
        return ChaosExperiment(
            name="phoenix-cpu-stress",
            description="Apply CPU stress to test auto-scaling",
            tags=["cpu", "stress", "autoscaling"],
            steady_state=SteadyStateHypothesis(
                name="API responsive under load",
                description="API responds within latency SLO",
                probes=[
                    {
                        "type": "http",
                        "url": "http://phoenix-api:8000/health",
                        "expected_status": 200,
                        "timeout": 5,
                    },
                ],
            ),
            actions=[
                ChaosAction(
                    type=FaultType.CPU_STRESS,
                    target_name="phoenix-api",
                    target_namespace="phoenix-production",
                    percentage=50,
                    duration_seconds=120,
                    parameters={
                        "workers": 4,
                        "load": 90,
                    },
                ),
            ],
        )
    
    @staticmethod
    def az_partition() -> ChaosExperiment:
        """Simulate availability zone network partition."""
        return ChaosExperiment(
            name="phoenix-az-partition",
            description="Simulate network partition between AZs",
            tags=["network", "az", "partition"],
            steady_state=SteadyStateHypothesis(
                name="Multi-AZ resilience",
                description="Service remains available during AZ partition",
                probes=[
                    {
                        "type": "http",
                        "url": "http://phoenix-api:8000/health",
                        "expected_status": 200,
                    },
                    {
                        "type": "kubernetes",
                        "resource_type": "deployment",
                        "name": "phoenix-api",
                        "namespace": "phoenix-production",
                        "condition": "Available",
                    },
                ],
            ),
            actions=[
                ChaosAction(
                    type=FaultType.NETWORK_PARTITION,
                    target_name="phoenix-api",
                    target_namespace="phoenix-production",
                    percentage=33,  # ~1 AZ
                    duration_seconds=180,
                    label_selectors={
                        "topology.kubernetes.io/zone": "us-east-1a",
                    },
                ),
            ],
        )


# =============================================================================
# EXPERIMENT SCHEDULER
# =============================================================================

class ChaosScheduler:
    """
    Schedule and manage chaos experiments.
    
    Implements Game Day automation and continuous chaos.
    """
    
    def __init__(self, runner: ChaosRunner):
        self.runner = runner
        self._scheduled: dict[str, ChaosExperiment] = {}
        self._running = False
    
    async def schedule_experiment(
        self,
        experiment: ChaosExperiment,
        run_at: Optional[datetime] = None,
    ) -> str:
        """Schedule an experiment for future execution."""
        self._scheduled[experiment.id] = experiment
        logger.info(f"Scheduled experiment {experiment.name} for {run_at or 'immediate execution'}")
        return experiment.id
    
    async def run_game_day(
        self,
        experiments: list[ChaosExperiment],
        interval_seconds: int = 300,
    ) -> list[dict[str, Any]]:
        """
        Run a Game Day with multiple experiments.
        
        Game Days are scheduled chaos sessions where teams practice
        incident response and validate resilience.
        """
        logger.info(f"Starting Game Day with {len(experiments)} experiments")
        results = []
        
        for i, experiment in enumerate(experiments):
            logger.info(f"Game Day experiment {i+1}/{len(experiments)}: {experiment.name}")
            
            result = await self.runner.run_experiment(experiment)
            results.append(result)
            
            if i < len(experiments) - 1:
                logger.info(f"Waiting {interval_seconds}s before next experiment...")
                await asyncio.sleep(interval_seconds)
        
        logger.info("Game Day complete")
        return results
    
    async def continuous_chaos(
        self,
        experiments: list[ChaosExperiment],
        interval_hours: int = 4,
    ) -> None:
        """
        Run continuous chaos experiments.
        
        Continuously validates system resilience by running
        random experiments at regular intervals.
        """
        self._running = True
        logger.info(f"Starting continuous chaos with {len(experiments)} experiment types")
        
        while self._running:
            # Select random experiment
            experiment = random.choice(experiments)
            experiment.id = str(uuid4())  # New ID for each run
            
            logger.info(f"Running continuous chaos experiment: {experiment.name}")
            await self.runner.run_experiment(experiment)
            
            logger.info(f"Waiting {interval_hours}h until next experiment...")
            await asyncio.sleep(interval_hours * 3600)
    
    def stop_continuous(self) -> None:
        """Stop continuous chaos."""
        self._running = False
        logger.info("Stopping continuous chaos")
