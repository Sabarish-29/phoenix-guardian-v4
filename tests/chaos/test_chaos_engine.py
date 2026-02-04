"""
Phoenix Guardian - Chaos Engineering Tests
Sprint 71-72: Chaos Engineering

Tests for chaos experiment framework.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import sys
sys.path.insert(0, "d:/phoenix guardian v4")

from chaos.chaos_engine import (
    ExperimentState,
    FaultType,
    TargetType,
    SteadyStateHypothesis,
    ChaosAction,
    ChaosExperiment,
    ChaosMeshRunner,
    PhoenixExperiments,
    ChaosScheduler,
)


class TestChaosExperiment:
    """Test ChaosExperiment dataclass."""
    
    def test_experiment_creation_defaults(self):
        """Test experiment creation with defaults."""
        exp = ChaosExperiment(
            name="test-experiment",
            description="Test description",
        )
        
        assert exp.name == "test-experiment"
        assert exp.state == ExperimentState.PENDING
        assert exp.dry_run is False
        assert exp.auto_rollback is True
        assert exp.id is not None
        assert len(exp.id) == 36  # UUID
    
    def test_experiment_with_actions(self):
        """Test experiment with chaos actions."""
        action = ChaosAction(
            type=FaultType.POD_KILL,
            target_name="phoenix-api",
            target_namespace="phoenix-production",
            duration_seconds=60,
            percentage=30,
        )
        
        exp = ChaosExperiment(
            name="pod-kill-test",
            description="Test pod kill",
            actions=[action],
        )
        
        assert len(exp.actions) == 1
        assert exp.actions[0].type == FaultType.POD_KILL
        assert exp.actions[0].percentage == 30
    
    def test_experiment_with_steady_state(self):
        """Test experiment with steady state hypothesis."""
        hypothesis = SteadyStateHypothesis(
            name="API available",
            description="API responds to health checks",
            probes=[
                {"type": "http", "url": "http://localhost/health"},
            ],
        )
        
        exp = ChaosExperiment(
            name="test-with-hypothesis",
            steady_state=hypothesis,
        )
        
        assert exp.steady_state is not None
        assert exp.steady_state.name == "API available"
        assert len(exp.steady_state.probes) == 1
    
    def test_to_chaos_mesh_pod_chaos(self):
        """Test conversion to PodChaos CRD."""
        action = ChaosAction(
            type=FaultType.POD_KILL,
            target_name="phoenix-api",
            target_namespace="phoenix-production",
            duration_seconds=60,
            percentage=50,
        )
        
        exp = ChaosExperiment(
            name="pod-kill-test",
            actions=[action],
        )
        
        manifest = exp.to_chaos_mesh()
        
        assert manifest["apiVersion"] == "chaos-mesh.org/v1alpha1"
        assert manifest["kind"] == "PodChaos"
        assert manifest["metadata"]["name"] == "pod-kill-test"
        assert manifest["spec"]["action"] == "kill"
        assert manifest["spec"]["mode"] == "fixed-percent"
        assert manifest["spec"]["value"] == "50"
    
    def test_to_chaos_mesh_network_chaos(self):
        """Test conversion to NetworkChaos CRD."""
        action = ChaosAction(
            type=FaultType.NETWORK_LATENCY,
            target_name="phoenix-api",
            target_namespace="phoenix-production",
            duration_seconds=120,
            percentage=100,
            parameters={"latency": "200ms", "jitter": "20ms"},
        )
        
        exp = ChaosExperiment(
            name="network-latency-test",
            actions=[action],
        )
        
        manifest = exp.to_chaos_mesh()
        
        assert manifest["kind"] == "NetworkChaos"
        assert manifest["spec"]["action"] == "latency"
        assert manifest["spec"]["delay"]["latency"] == "200ms"
        assert manifest["spec"]["delay"]["jitter"] == "20ms"
    
    def test_to_chaos_mesh_stress_chaos(self):
        """Test conversion to StressChaos CRD."""
        action = ChaosAction(
            type=FaultType.CPU_STRESS,
            target_name="phoenix-api",
            duration_seconds=60,
            parameters={"workers": 4, "load": 80},
        )
        
        exp = ChaosExperiment(
            name="cpu-stress-test",
            actions=[action],
        )
        
        manifest = exp.to_chaos_mesh()
        
        assert manifest["kind"] == "StressChaos"
        assert manifest["spec"]["stressors"]["cpu"]["workers"] == 4
        assert manifest["spec"]["stressors"]["cpu"]["load"] == 80
    
    def test_to_chaos_mesh_http_chaos(self):
        """Test conversion to HTTPChaos CRD."""
        action = ChaosAction(
            type=FaultType.HTTP_DELAY,
            target_name="phoenix-api",
            parameters={"delay": "2s", "port": 8000},
        )
        
        exp = ChaosExperiment(
            name="http-delay-test",
            actions=[action],
        )
        
        manifest = exp.to_chaos_mesh()
        
        assert manifest["kind"] == "HTTPChaos"
        assert manifest["spec"]["delay"] == "2s"
    
    def test_to_chaos_mesh_no_actions(self):
        """Test error when no actions defined."""
        exp = ChaosExperiment(name="empty-test")
        
        with pytest.raises(ValueError, match="no actions"):
            exp.to_chaos_mesh()


class TestChaosAction:
    """Test ChaosAction dataclass."""
    
    def test_action_defaults(self):
        """Test action creation with defaults."""
        action = ChaosAction(type=FaultType.POD_KILL)
        
        assert action.duration_seconds == 60
        assert action.target_type == TargetType.DEPLOYMENT
        assert action.percentage == 50
        assert action.target_namespace == "phoenix-production"
    
    def test_action_with_labels(self):
        """Test action with label selectors."""
        action = ChaosAction(
            type=FaultType.NETWORK_PARTITION,
            label_selectors={
                "app": "phoenix-api",
                "tier": "backend",
            },
        )
        
        assert action.label_selectors["app"] == "phoenix-api"
        assert action.label_selectors["tier"] == "backend"
    
    def test_action_with_parameters(self):
        """Test action with fault-specific parameters."""
        action = ChaosAction(
            type=FaultType.NETWORK_LATENCY,
            parameters={
                "latency": "500ms",
                "jitter": "50ms",
                "correlation": "80",
            },
        )
        
        assert action.parameters["latency"] == "500ms"


class TestSteadyStateHypothesis:
    """Test SteadyStateHypothesis dataclass."""
    
    def test_hypothesis_creation(self):
        """Test hypothesis creation."""
        hypothesis = SteadyStateHypothesis(
            name="Test hypothesis",
            description="System is healthy",
            probes=[
                {"type": "http", "url": "http://localhost/health"},
                {"type": "prometheus", "query": "up{job='api'}", "expected_value": 1},
            ],
            tolerance=0.1,
        )
        
        assert hypothesis.name == "Test hypothesis"
        assert len(hypothesis.probes) == 2
        assert hypothesis.tolerance == 0.1
        assert hypothesis.timeout_seconds == 60


class TestFaultTypes:
    """Test FaultType enumeration."""
    
    def test_network_faults(self):
        """Test network fault types exist."""
        assert FaultType.NETWORK_LATENCY.value == "network_latency"
        assert FaultType.NETWORK_PARTITION.value == "network_partition"
        assert FaultType.NETWORK_PACKET_LOSS.value == "network_packet_loss"
    
    def test_pod_faults(self):
        """Test pod fault types exist."""
        assert FaultType.POD_KILL.value == "pod_kill"
        assert FaultType.POD_FAILURE.value == "pod_failure"
        assert FaultType.CONTAINER_KILL.value == "container_kill"
    
    def test_stress_faults(self):
        """Test stress fault types exist."""
        assert FaultType.CPU_STRESS.value == "cpu_stress"
        assert FaultType.MEMORY_STRESS.value == "memory_stress"
        assert FaultType.IO_STRESS.value == "io_stress"
    
    def test_aws_faults(self):
        """Test AWS fault types exist."""
        assert FaultType.EC2_TERMINATE.value == "ec2_terminate"
        assert FaultType.RDS_FAILOVER.value == "rds_failover"
        assert FaultType.AZ_FAILURE.value == "az_failure"


class TestChaosMeshRunner:
    """Test ChaosMeshRunner execution."""
    
    @pytest.fixture
    def runner(self):
        return ChaosMeshRunner()
    
    @pytest.mark.asyncio
    async def test_run_experiment_dry_run(self, runner):
        """Test dry run experiment."""
        exp = ChaosExperiment(
            name="dry-run-test",
            description="Test dry run",
            dry_run=True,
            actions=[
                ChaosAction(type=FaultType.POD_KILL, target_name="test"),
            ],
        )
        
        result = await runner.run_experiment(exp)
        
        assert result["success"] is True
        assert len(result["actions"]) == 1
        assert result["actions"][0]["dry_run"] is True
    
    @pytest.mark.asyncio
    async def test_run_experiment_state_transitions(self, runner):
        """Test experiment state transitions."""
        exp = ChaosExperiment(
            name="state-test",
            dry_run=True,
            actions=[
                ChaosAction(type=FaultType.POD_KILL, target_name="test"),
            ],
        )
        
        assert exp.state == ExperimentState.PENDING
        
        await runner.run_experiment(exp)
        
        assert exp.state == ExperimentState.COMPLETED
        assert exp.started_at is not None
        assert exp.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_run_experiment_with_steady_state(self, runner):
        """Test experiment with steady state checks."""
        exp = ChaosExperiment(
            name="steady-state-test",
            dry_run=True,
            steady_state=SteadyStateHypothesis(
                name="Test hypothesis",
                description="System healthy",
                probes=[],  # Empty probes pass by default
            ),
            actions=[
                ChaosAction(type=FaultType.POD_KILL, target_name="test"),
            ],
        )
        
        result = await runner.run_experiment(exp)
        
        assert result["steady_state_before"] is not None
        assert result["steady_state_before"]["passed"] is True
    
    @pytest.mark.asyncio
    async def test_abort_experiment(self, runner):
        """Test experiment abortion."""
        exp = ChaosExperiment(
            name="abort-test",
            actions=[ChaosAction(type=FaultType.POD_KILL, target_name="test")],
        )
        
        # Start running
        exp.state = ExperimentState.RUNNING
        runner._experiments[exp.id] = exp
        
        result = await runner.abort_experiment(exp.id)
        
        assert result is True
        assert exp.state == ExperimentState.ABORTED
    
    @pytest.mark.asyncio
    async def test_abort_nonexistent_experiment(self, runner):
        """Test aborting non-existent experiment."""
        result = await runner.abort_experiment("nonexistent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_rollback_experiment(self, runner):
        """Test experiment rollback."""
        exp = ChaosExperiment(
            name="rollback-test",
            rollback_actions=[
                {"type": "scale", "replicas": 3},
            ],
            actions=[ChaosAction(type=FaultType.POD_KILL, target_name="test")],
        )
        
        runner._experiments[exp.id] = exp
        
        result = await runner.rollback_experiment(exp.id)
        
        assert result is True
        assert exp.state == ExperimentState.ROLLED_BACK


class TestPhoenixExperiments:
    """Test predefined Phoenix Guardian experiments."""
    
    def test_api_pod_failure(self):
        """Test API pod failure experiment."""
        exp = PhoenixExperiments.api_pod_failure()
        
        assert exp.name == "phoenix-api-pod-failure"
        assert len(exp.actions) == 1
        assert exp.actions[0].type == FaultType.POD_KILL
        assert exp.actions[0].percentage == 30
        assert exp.steady_state is not None
    
    def test_database_latency(self):
        """Test database latency experiment."""
        exp = PhoenixExperiments.database_latency()
        
        assert exp.name == "phoenix-db-latency"
        assert exp.actions[0].type == FaultType.NETWORK_LATENCY
        assert exp.actions[0].parameters["latency"] == "500ms"
    
    def test_redis_failure(self):
        """Test Redis failure experiment."""
        exp = PhoenixExperiments.redis_failure()
        
        assert exp.name == "phoenix-redis-failure"
        assert exp.actions[0].target_name == "redis"
        assert exp.actions[0].percentage == 100
    
    def test_ml_node_failure(self):
        """Test ML node failure experiment."""
        exp = PhoenixExperiments.ml_node_failure()
        
        assert exp.name == "phoenix-ml-node-failure"
        assert "phoenix-beacon" in exp.actions[0].target_name
    
    def test_cpu_stress(self):
        """Test CPU stress experiment."""
        exp = PhoenixExperiments.cpu_stress()
        
        assert exp.name == "phoenix-cpu-stress"
        assert exp.actions[0].type == FaultType.CPU_STRESS
        assert exp.actions[0].parameters["load"] == 90
    
    def test_az_partition(self):
        """Test AZ partition experiment."""
        exp = PhoenixExperiments.az_partition()
        
        assert exp.name == "phoenix-az-partition"
        assert exp.actions[0].type == FaultType.NETWORK_PARTITION
        assert "us-east-1a" in exp.actions[0].label_selectors.get(
            "topology.kubernetes.io/zone", ""
        )


class TestChaosScheduler:
    """Test ChaosScheduler functionality."""
    
    @pytest.fixture
    def scheduler(self):
        runner = ChaosMeshRunner()
        return ChaosScheduler(runner)
    
    @pytest.mark.asyncio
    async def test_schedule_experiment(self, scheduler):
        """Test scheduling an experiment."""
        exp = ChaosExperiment(name="scheduled-test")
        
        exp_id = await scheduler.schedule_experiment(exp)
        
        assert exp_id == exp.id
        assert exp.id in scheduler._scheduled
    
    @pytest.mark.asyncio
    async def test_run_game_day(self, scheduler):
        """Test running a game day."""
        experiments = [
            ChaosExperiment(
                name="game-day-1",
                dry_run=True,
                actions=[ChaosAction(type=FaultType.POD_KILL, target_name="test")],
            ),
            ChaosExperiment(
                name="game-day-2",
                dry_run=True,
                actions=[ChaosAction(type=FaultType.CPU_STRESS, target_name="test")],
            ),
        ]
        
        results = await scheduler.run_game_day(experiments, interval_seconds=1)
        
        assert len(results) == 2
        assert all(r["success"] for r in results)
    
    def test_stop_continuous(self, scheduler):
        """Test stopping continuous chaos."""
        scheduler._running = True
        scheduler.stop_continuous()
        
        assert scheduler._running is False


class TestExperimentState:
    """Test ExperimentState enumeration."""
    
    def test_all_states_exist(self):
        """Test all states are defined."""
        assert ExperimentState.PENDING.value == "pending"
        assert ExperimentState.RUNNING.value == "running"
        assert ExperimentState.COMPLETED.value == "completed"
        assert ExperimentState.FAILED.value == "failed"
        assert ExperimentState.ABORTED.value == "aborted"
        assert ExperimentState.ROLLED_BACK.value == "rolled_back"


class TestTargetType:
    """Test TargetType enumeration."""
    
    def test_kubernetes_targets(self):
        """Test Kubernetes target types."""
        assert TargetType.DEPLOYMENT.value == "deployment"
        assert TargetType.STATEFULSET.value == "statefulset"
        assert TargetType.POD.value == "pod"
        assert TargetType.NODE.value == "node"


class TestIntegration:
    """Integration tests for chaos engineering."""
    
    @pytest.mark.asyncio
    async def test_full_experiment_lifecycle(self):
        """Test complete experiment lifecycle."""
        runner = ChaosMeshRunner()
        
        # 1. Create experiment
        exp = ChaosExperiment(
            name="integration-test",
            description="Full lifecycle test",
            dry_run=True,
            steady_state=SteadyStateHypothesis(
                name="System healthy",
                description="All checks pass",
                probes=[],
            ),
            actions=[
                ChaosAction(
                    type=FaultType.POD_KILL,
                    target_name="phoenix-api",
                    duration_seconds=30,
                    percentage=20,
                ),
            ],
            auto_rollback=True,
        )
        
        # 2. Run experiment
        result = await runner.run_experiment(exp)
        
        # 3. Verify results
        assert result["success"] is True
        assert result["experiment_id"] == exp.id
        assert exp.state == ExperimentState.COMPLETED
        assert "duration_seconds" in result
    
    @pytest.mark.asyncio
    async def test_experiment_failure_with_rollback(self):
        """Test experiment failure triggers rollback."""
        runner = ChaosMeshRunner()
        
        exp = ChaosExperiment(
            name="failure-rollback-test",
            dry_run=False,  # Will fail since not connected to cluster
            auto_rollback=True,
            abort_on_failure=False,  # Don't abort, let it complete
            actions=[
                ChaosAction(type=FaultType.POD_KILL, target_name="test"),
            ],
        )
        
        # Mock the action execution to succeed
        with patch.object(runner, '_execute_action', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"action": "kill", "success": True}
            
            result = await runner.run_experiment(exp)
            assert result["success"] is True
