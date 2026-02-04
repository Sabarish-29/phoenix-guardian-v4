"""
Disaster Recovery Simulator for Phoenix Guardian.

Simulates and validates disaster recovery scenarios to ensure
the platform meets SLA requirements for recovery time objectives (RTO).
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ScenarioStatus(Enum):
    """Status of a DR scenario execution."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DRScenario:
    """A disaster recovery scenario definition.
    
    Attributes:
        name: Unique identifier for the scenario.
        description: Human-readable description of the scenario.
        target_recovery_seconds: SLA target for recovery time.
        steps: List of steps to execute for this scenario.
        status: Current status of the scenario.
        actual_recovery_seconds: Measured recovery time (after execution).
        notes: Additional notes or error messages.
    """
    name: str
    description: str
    target_recovery_seconds: int
    steps: list[str]
    status: ScenarioStatus = ScenarioStatus.PENDING
    actual_recovery_seconds: float | None = None
    notes: str = ""
    
    def to_dict(self) -> dict:
        """Convert scenario to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "target_recovery_seconds": self.target_recovery_seconds,
            "steps": self.steps,
            "status": self.status.value,
            "actual_recovery_seconds": self.actual_recovery_seconds,
            "notes": self.notes,
            "sla_met": self.sla_met,
        }
    
    @property
    def sla_met(self) -> bool | None:
        """Check if SLA was met. Returns None if not yet executed."""
        if self.actual_recovery_seconds is None:
            return None
        return self.actual_recovery_seconds <= self.target_recovery_seconds


@dataclass
class DRReport:
    """Report from a DR simulation run.
    
    Attributes:
        run_id: Unique identifier for this run.
        start_time: When the simulation started.
        end_time: When the simulation ended.
        dry_run: Whether this was a dry run (no actual changes).
        scenarios: List of scenario results.
        overall_passed: Whether all scenarios passed.
        total_scenarios: Total number of scenarios.
        passed_count: Number of passed scenarios.
        failed_count: Number of failed scenarios.
        skipped_count: Number of skipped scenarios.
    """
    run_id: str
    start_time: datetime
    end_time: datetime | None = None
    dry_run: bool = True
    scenarios: list[DRScenario] = field(default_factory=list)
    
    @property
    def overall_passed(self) -> bool:
        """Check if all executed scenarios passed."""
        executed = [s for s in self.scenarios if s.status in (ScenarioStatus.PASSED, ScenarioStatus.FAILED)]
        if not executed:
            return True
        return all(s.status == ScenarioStatus.PASSED for s in executed)
    
    @property
    def total_scenarios(self) -> int:
        """Total number of scenarios."""
        return len(self.scenarios)
    
    @property
    def passed_count(self) -> int:
        """Number of passed scenarios."""
        return sum(1 for s in self.scenarios if s.status == ScenarioStatus.PASSED)
    
    @property
    def failed_count(self) -> int:
        """Number of failed scenarios."""
        return sum(1 for s in self.scenarios if s.status == ScenarioStatus.FAILED)
    
    @property
    def skipped_count(self) -> int:
        """Number of skipped scenarios."""
        return sum(1 for s in self.scenarios if s.status == ScenarioStatus.SKIPPED)
    
    @property
    def duration_seconds(self) -> float | None:
        """Total duration of the simulation."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()
    
    def to_dict(self) -> dict:
        """Convert report to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "dry_run": self.dry_run,
            "duration_seconds": self.duration_seconds,
            "overall_passed": self.overall_passed,
            "total_scenarios": self.total_scenarios,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "scenarios": [s.to_dict() for s in self.scenarios],
        }
    
    def summary(self) -> str:
        """Generate a human-readable summary."""
        mode = "DRY RUN" if self.dry_run else "LIVE"
        status = "PASSED" if self.overall_passed else "FAILED"
        
        lines = [
            f"DR Simulation Report [{mode}] - {status}",
            "=" * 50,
            f"Run ID: {self.run_id}",
            f"Start: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        
        if self.end_time:
            lines.append(f"End: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Duration: {self.duration_seconds:.2f}s")
        
        lines.extend([
            "",
            f"Scenarios: {self.passed_count}/{self.total_scenarios} passed, "
            f"{self.failed_count} failed, {self.skipped_count} skipped",
            "",
            "Scenario Details:",
            "-" * 40,
        ])
        
        for scenario in self.scenarios:
            status_icon = {
                ScenarioStatus.PASSED: "✓",
                ScenarioStatus.FAILED: "✗",
                ScenarioStatus.SKIPPED: "○",
                ScenarioStatus.PENDING: "·",
                ScenarioStatus.RUNNING: "→",
            }[scenario.status]
            
            time_str = (
                f"{scenario.actual_recovery_seconds:.2f}s"
                if scenario.actual_recovery_seconds is not None
                else "N/A"
            )
            sla_str = f"(SLA: {scenario.target_recovery_seconds}s)"
            
            lines.append(f"  {status_icon} {scenario.name}: {time_str} {sla_str}")
            if scenario.notes:
                lines.append(f"      Note: {scenario.notes}")
        
        return "\n".join(lines)


class DRSimulator:
    """Disaster Recovery Simulator.
    
    Simulates disaster recovery scenarios to validate RTO SLAs.
    Supports both dry-run mode (prints steps only) and live mode
    (executes actual K8s/infrastructure commands).
    
    Example:
        >>> simulator = DRSimulator()
        >>> report = simulator.run_all(dry_run=True)
        >>> print(report.summary())
    """
    
    # Default scenario definitions
    DEFAULT_SCENARIOS: list[DRScenario] = [
        DRScenario(
            name="database_failover",
            description="Simulate PostgreSQL primary database failure and failover to replica",
            target_recovery_seconds=30,
            steps=[
                "1. Identify current primary database pod",
                "2. Terminate primary database pod",
                "3. Wait for replica promotion",
                "4. Verify new primary is accepting connections",
                "5. Confirm application reconnection",
                "6. Validate data integrity check",
            ],
        ),
        DRScenario(
            name="redis_failover",
            description="Simulate Redis cache failure and failover to replica",
            target_recovery_seconds=10,
            steps=[
                "1. Identify current Redis master",
                "2. Terminate Redis master pod",
                "3. Wait for Sentinel to promote replica",
                "4. Verify new master is operational",
                "5. Confirm cache hit rates restored",
            ],
        ),
        DRScenario(
            name="api_pod_crash",
            description="Simulate API server pod crash and auto-recovery",
            target_recovery_seconds=60,
            steps=[
                "1. Select random API pod for termination",
                "2. Terminate selected pod",
                "3. Wait for Kubernetes to detect failure",
                "4. Wait for new pod to be scheduled",
                "5. Wait for new pod to pass health checks",
                "6. Verify traffic routing to new pod",
            ],
        ),
        DRScenario(
            name="ehr_timeout",
            description="Simulate EHR integration timeout and circuit breaker activation",
            target_recovery_seconds=5,
            steps=[
                "1. Configure EHR mock to inject 30s latency",
                "2. Send test request to EHR endpoint",
                "3. Verify circuit breaker opens",
                "4. Verify fallback response returned",
                "5. Reset EHR mock latency",
                "6. Verify circuit breaker closes after recovery",
            ],
        ),
        DRScenario(
            name="backup_restore",
            description="Simulate full database restore from backup",
            target_recovery_seconds=900,  # 15 minutes
            steps=[
                "1. Create test checkpoint in database",
                "2. Identify latest valid backup",
                "3. Provision new database instance",
                "4. Initiate backup restore process",
                "5. Wait for restore completion",
                "6. Validate restored data integrity",
                "7. Verify checkpoint data present",
                "8. Switch traffic to restored database",
            ],
        ),
    ]
    
    def __init__(
        self,
        scenarios: list[DRScenario] | None = None,
        k8s_namespace: str = "phoenix-guardian",
        log_handler: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the DR simulator.
        
        Args:
            scenarios: Custom scenarios to use. Defaults to DEFAULT_SCENARIOS.
            k8s_namespace: Kubernetes namespace for live operations.
            log_handler: Custom log handler for output.
        """
        self.scenarios = scenarios or [
            DRScenario(
                name=s.name,
                description=s.description,
                target_recovery_seconds=s.target_recovery_seconds,
                steps=s.steps.copy(),
            )
            for s in self.DEFAULT_SCENARIOS
        ]
        self.k8s_namespace = k8s_namespace
        self.log_handler = log_handler or self._default_log
        self._step_executors: dict[str, Callable] = {}
    
    def _default_log(self, message: str) -> None:
        """Default log handler."""
        logger.info(message)
        print(message)
    
    def get_scenario(self, name: str) -> DRScenario | None:
        """Get a scenario by name."""
        for scenario in self.scenarios:
            if scenario.name == name:
                return scenario
        return None
    
    def get_scenario_names(self) -> list[str]:
        """Get list of all scenario names."""
        return [s.name for s in self.scenarios]
    
    def register_executor(
        self,
        scenario_name: str,
        executor: Callable[["DRSimulator", DRScenario], float],
    ) -> None:
        """Register a custom executor for a scenario.
        
        Args:
            scenario_name: Name of the scenario.
            executor: Callable that executes the scenario and returns recovery time.
        """
        self._step_executors[scenario_name] = executor
    
    def run_all(self, dry_run: bool = True) -> DRReport:
        """Run all DR scenarios.
        
        Args:
            dry_run: If True, only print steps without executing.
                    If False, execute actual recovery operations.
        
        Returns:
            DRReport with results of all scenarios.
        """
        run_id = f"dr-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        report = DRReport(
            run_id=run_id,
            start_time=datetime.now(),
            dry_run=dry_run,
        )
        
        self.log_handler(f"\n{'=' * 60}")
        self.log_handler(f"Starting DR Simulation: {run_id}")
        self.log_handler(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        self.log_handler(f"Scenarios: {len(self.scenarios)}")
        self.log_handler(f"{'=' * 60}\n")
        
        for scenario in self.scenarios:
            result = self._run_scenario(scenario, dry_run)
            report.scenarios.append(result)
        
        report.end_time = datetime.now()
        
        self.log_handler(f"\n{'=' * 60}")
        self.log_handler(report.summary())
        
        return report
    
    def run_scenario(self, name: str, dry_run: bool = True) -> DRScenario:
        """Run a single scenario by name.
        
        Args:
            name: Name of the scenario to run.
            dry_run: If True, only print steps without executing.
        
        Returns:
            Updated DRScenario with results.
        
        Raises:
            ValueError: If scenario name is not found.
        """
        scenario = self.get_scenario(name)
        if scenario is None:
            raise ValueError(f"Scenario not found: {name}")
        
        return self._run_scenario(scenario, dry_run)
    
    def _run_scenario(self, scenario: DRScenario, dry_run: bool) -> DRScenario:
        """Execute a single scenario.
        
        Args:
            scenario: The scenario to execute.
            dry_run: If True, only print steps without executing.
        
        Returns:
            Updated scenario with results.
        """
        self.log_handler(f"\n[{scenario.name}] Starting scenario...")
        self.log_handler(f"  Description: {scenario.description}")
        self.log_handler(f"  SLA Target: {scenario.target_recovery_seconds}s")
        
        scenario.status = ScenarioStatus.RUNNING
        start_time = time.monotonic()
        
        try:
            if dry_run:
                # Dry run: just print steps
                self.log_handler(f"  Steps (dry run):")
                for step in scenario.steps:
                    self.log_handler(f"    {step}")
                    time.sleep(0.01)  # Small delay for realistic simulation
                
                # Simulate a successful recovery time (under SLA)
                simulated_time = scenario.target_recovery_seconds * 0.7
                scenario.actual_recovery_seconds = simulated_time
                scenario.status = ScenarioStatus.PASSED
                scenario.notes = "Dry run completed successfully"
                
            else:
                # Live execution
                if scenario.name in self._step_executors:
                    # Use custom executor
                    executor = self._step_executors[scenario.name]
                    recovery_time = executor(self, scenario)
                    scenario.actual_recovery_seconds = recovery_time
                else:
                    # Default live execution (requires K8s setup)
                    scenario.actual_recovery_seconds = self._execute_live(scenario)
                
                # Check if SLA was met
                if scenario.actual_recovery_seconds <= scenario.target_recovery_seconds:
                    scenario.status = ScenarioStatus.PASSED
                    scenario.notes = "Recovery completed within SLA"
                else:
                    scenario.status = ScenarioStatus.FAILED
                    scenario.notes = (
                        f"Recovery took {scenario.actual_recovery_seconds:.2f}s, "
                        f"exceeding SLA of {scenario.target_recovery_seconds}s"
                    )
        
        except Exception as e:
            scenario.status = ScenarioStatus.FAILED
            scenario.actual_recovery_seconds = time.monotonic() - start_time
            scenario.notes = f"Error during execution: {str(e)}"
            logger.exception(f"Scenario {scenario.name} failed with error")
        
        status_str = scenario.status.value.upper()
        self.log_handler(
            f"  Result: {status_str} "
            f"(actual: {scenario.actual_recovery_seconds:.2f}s, "
            f"target: {scenario.target_recovery_seconds}s)"
        )
        
        return scenario
    
    def _execute_live(self, scenario: DRScenario) -> float:
        """Execute scenario steps in live mode.
        
        This method requires Kubernetes configuration and
        appropriate permissions to execute DR operations.
        
        Args:
            scenario: The scenario to execute.
        
        Returns:
            Actual recovery time in seconds.
        
        Raises:
            NotImplementedError: If K8s execution is not configured.
        """
        # Default implementation raises error - needs K8s setup
        raise NotImplementedError(
            f"Live execution for '{scenario.name}' requires Kubernetes configuration. "
            "Register a custom executor using register_executor() or configure K8s access."
        )
    
    def skip_scenario(self, name: str, reason: str = "Manually skipped") -> None:
        """Skip a scenario by name.
        
        Args:
            name: Name of the scenario to skip.
            reason: Reason for skipping.
        
        Raises:
            ValueError: If scenario name is not found.
        """
        scenario = self.get_scenario(name)
        if scenario is None:
            raise ValueError(f"Scenario not found: {name}")
        
        scenario.status = ScenarioStatus.SKIPPED
        scenario.notes = reason
    
    def reset_scenarios(self) -> None:
        """Reset all scenarios to pending state."""
        for scenario in self.scenarios:
            scenario.status = ScenarioStatus.PENDING
            scenario.actual_recovery_seconds = None
            scenario.notes = ""
    
    def validate_sla_targets(self) -> dict[str, bool]:
        """Validate that all scenarios have reasonable SLA targets.
        
        Returns:
            Dictionary mapping scenario names to validation status.
        """
        validations = {}
        
        for scenario in self.scenarios:
            # Check target is positive
            if scenario.target_recovery_seconds <= 0:
                validations[scenario.name] = False
                continue
            
            # Check target is within reasonable bounds (< 1 hour)
            if scenario.target_recovery_seconds > 3600:
                validations[scenario.name] = False
                continue
            
            validations[scenario.name] = True
        
        return validations
    
    def get_sla_summary(self) -> dict[str, dict]:
        """Get summary of all scenario SLAs.
        
        Returns:
            Dictionary with scenario SLA information.
        """
        return {
            scenario.name: {
                "target_seconds": scenario.target_recovery_seconds,
                "description": scenario.description,
                "steps_count": len(scenario.steps),
                "status": scenario.status.value,
                "actual_seconds": scenario.actual_recovery_seconds,
                "sla_met": scenario.sla_met,
            }
            for scenario in self.scenarios
        }


# Factory functions for common use cases
def create_default_simulator() -> DRSimulator:
    """Create a simulator with default scenarios."""
    return DRSimulator()


def create_minimal_simulator() -> DRSimulator:
    """Create a simulator with minimal scenarios for quick testing."""
    minimal_scenarios = [
        DRScenario(
            name="redis_failover",
            description="Redis cache failover",
            target_recovery_seconds=10,
            steps=["1. Fail Redis", "2. Verify failover"],
        ),
        DRScenario(
            name="api_pod_crash",
            description="API pod crash recovery",
            target_recovery_seconds=60,
            steps=["1. Kill pod", "2. Verify restart"],
        ),
    ]
    return DRSimulator(scenarios=minimal_scenarios)
