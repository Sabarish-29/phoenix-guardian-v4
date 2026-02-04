"""
Tests for Disaster Recovery Simulator.

Tests cover:
- Scenario definitions
- SLA targets
- Dry run mode
- Report structure
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.ops.dr_simulator import (
    ScenarioStatus,
    DRScenario,
    DRReport,
    DRSimulator,
    create_default_simulator,
    create_minimal_simulator,
)


class TestScenarioStatus:
    """Tests for ScenarioStatus enum."""
    
    def test_all_statuses_defined(self):
        """Test all expected statuses are defined."""
        assert ScenarioStatus.PENDING.value == "pending"
        assert ScenarioStatus.RUNNING.value == "running"
        assert ScenarioStatus.PASSED.value == "passed"
        assert ScenarioStatus.FAILED.value == "failed"
        assert ScenarioStatus.SKIPPED.value == "skipped"
    
    def test_status_count(self):
        """Test total number of statuses."""
        assert len(ScenarioStatus) == 5


class TestDRScenario:
    """Tests for DRScenario dataclass."""
    
    def test_create_scenario(self):
        """Test creating a DR scenario."""
        scenario = DRScenario(
            name="test_scenario",
            description="Test scenario description",
            target_recovery_seconds=30,
            steps=["Step 1", "Step 2", "Step 3"],
        )
        
        assert scenario.name == "test_scenario"
        assert scenario.description == "Test scenario description"
        assert scenario.target_recovery_seconds == 30
        assert len(scenario.steps) == 3
        assert scenario.status == ScenarioStatus.PENDING
        assert scenario.actual_recovery_seconds is None
        assert scenario.notes == ""
    
    def test_scenario_default_values(self):
        """Test scenario default values."""
        scenario = DRScenario(
            name="test",
            description="Test",
            target_recovery_seconds=10,
            steps=[],
        )
        
        assert scenario.status == ScenarioStatus.PENDING
        assert scenario.actual_recovery_seconds is None
        assert scenario.notes == ""
    
    def test_scenario_to_dict(self):
        """Test scenario serialization."""
        scenario = DRScenario(
            name="test",
            description="Test description",
            target_recovery_seconds=30,
            steps=["Step 1"],
            status=ScenarioStatus.PASSED,
            actual_recovery_seconds=25.5,
            notes="Completed successfully",
        )
        
        result = scenario.to_dict()
        
        assert result["name"] == "test"
        assert result["description"] == "Test description"
        assert result["target_recovery_seconds"] == 30
        assert result["steps"] == ["Step 1"]
        assert result["status"] == "passed"
        assert result["actual_recovery_seconds"] == 25.5
        assert result["notes"] == "Completed successfully"
        assert result["sla_met"] is True
    
    def test_sla_met_when_under_target(self):
        """Test SLA met when recovery time is under target."""
        scenario = DRScenario(
            name="test",
            description="Test",
            target_recovery_seconds=30,
            steps=[],
            actual_recovery_seconds=25.0,
        )
        
        assert scenario.sla_met is True
    
    def test_sla_met_when_equal_to_target(self):
        """Test SLA met when recovery time equals target."""
        scenario = DRScenario(
            name="test",
            description="Test",
            target_recovery_seconds=30,
            steps=[],
            actual_recovery_seconds=30.0,
        )
        
        assert scenario.sla_met is True
    
    def test_sla_not_met_when_over_target(self):
        """Test SLA not met when recovery time exceeds target."""
        scenario = DRScenario(
            name="test",
            description="Test",
            target_recovery_seconds=30,
            steps=[],
            actual_recovery_seconds=35.0,
        )
        
        assert scenario.sla_met is False
    
    def test_sla_met_none_when_not_executed(self):
        """Test SLA met is None when not yet executed."""
        scenario = DRScenario(
            name="test",
            description="Test",
            target_recovery_seconds=30,
            steps=[],
        )
        
        assert scenario.sla_met is None


class TestDRReport:
    """Tests for DRReport dataclass."""
    
    def test_create_report(self):
        """Test creating a DR report."""
        report = DRReport(
            run_id="test-run-001",
            start_time=datetime(2026, 2, 2, 10, 0, 0),
            dry_run=True,
        )
        
        assert report.run_id == "test-run-001"
        assert report.start_time == datetime(2026, 2, 2, 10, 0, 0)
        assert report.end_time is None
        assert report.dry_run is True
        assert report.scenarios == []
    
    def test_report_overall_passed_no_scenarios(self):
        """Test overall passed when no scenarios."""
        report = DRReport(
            run_id="test",
            start_time=datetime.now(),
        )
        
        assert report.overall_passed is True
    
    def test_report_overall_passed_all_passed(self):
        """Test overall passed when all scenarios passed."""
        report = DRReport(
            run_id="test",
            start_time=datetime.now(),
            scenarios=[
                DRScenario(
                    name="s1", description="", target_recovery_seconds=10,
                    steps=[], status=ScenarioStatus.PASSED
                ),
                DRScenario(
                    name="s2", description="", target_recovery_seconds=20,
                    steps=[], status=ScenarioStatus.PASSED
                ),
            ],
        )
        
        assert report.overall_passed is True
    
    def test_report_overall_failed_one_failed(self):
        """Test overall failed when one scenario failed."""
        report = DRReport(
            run_id="test",
            start_time=datetime.now(),
            scenarios=[
                DRScenario(
                    name="s1", description="", target_recovery_seconds=10,
                    steps=[], status=ScenarioStatus.PASSED
                ),
                DRScenario(
                    name="s2", description="", target_recovery_seconds=20,
                    steps=[], status=ScenarioStatus.FAILED
                ),
            ],
        )
        
        assert report.overall_passed is False
    
    def test_report_counts(self):
        """Test report scenario counts."""
        report = DRReport(
            run_id="test",
            start_time=datetime.now(),
            scenarios=[
                DRScenario(name="s1", description="", target_recovery_seconds=10,
                          steps=[], status=ScenarioStatus.PASSED),
                DRScenario(name="s2", description="", target_recovery_seconds=20,
                          steps=[], status=ScenarioStatus.PASSED),
                DRScenario(name="s3", description="", target_recovery_seconds=30,
                          steps=[], status=ScenarioStatus.FAILED),
                DRScenario(name="s4", description="", target_recovery_seconds=40,
                          steps=[], status=ScenarioStatus.SKIPPED),
                DRScenario(name="s5", description="", target_recovery_seconds=50,
                          steps=[], status=ScenarioStatus.PENDING),
            ],
        )
        
        assert report.total_scenarios == 5
        assert report.passed_count == 2
        assert report.failed_count == 1
        assert report.skipped_count == 1
    
    def test_report_duration(self):
        """Test report duration calculation."""
        report = DRReport(
            run_id="test",
            start_time=datetime(2026, 2, 2, 10, 0, 0),
            end_time=datetime(2026, 2, 2, 10, 5, 30),
        )
        
        assert report.duration_seconds == 330.0  # 5 minutes 30 seconds
    
    def test_report_duration_none_when_not_ended(self):
        """Test duration is None when not ended."""
        report = DRReport(
            run_id="test",
            start_time=datetime.now(),
        )
        
        assert report.duration_seconds is None
    
    def test_report_to_dict(self):
        """Test report serialization."""
        report = DRReport(
            run_id="test-001",
            start_time=datetime(2026, 2, 2, 10, 0, 0),
            end_time=datetime(2026, 2, 2, 10, 1, 0),
            dry_run=True,
            scenarios=[
                DRScenario(
                    name="s1", description="Test", target_recovery_seconds=30,
                    steps=["Step 1"], status=ScenarioStatus.PASSED,
                    actual_recovery_seconds=20.0
                ),
            ],
        )
        
        result = report.to_dict()
        
        assert result["run_id"] == "test-001"
        assert result["dry_run"] is True
        assert result["duration_seconds"] == 60.0
        assert result["overall_passed"] is True
        assert result["total_scenarios"] == 1
        assert result["passed_count"] == 1
        assert len(result["scenarios"]) == 1
    
    def test_report_summary(self):
        """Test report summary generation."""
        report = DRReport(
            run_id="test-001",
            start_time=datetime(2026, 2, 2, 10, 0, 0),
            end_time=datetime(2026, 2, 2, 10, 1, 0),
            dry_run=True,
            scenarios=[
                DRScenario(
                    name="test_scenario", description="Test", target_recovery_seconds=30,
                    steps=["Step 1"], status=ScenarioStatus.PASSED,
                    actual_recovery_seconds=20.0
                ),
            ],
        )
        
        summary = report.summary()
        
        assert "DRY RUN" in summary
        assert "PASSED" in summary
        assert "test-001" in summary
        assert "test_scenario" in summary


class TestDRSimulatorScenarioDefinitions:
    """Tests for DR simulator scenario definitions."""
    
    def test_default_scenarios_count(self):
        """Test that 5 default scenarios are defined."""
        simulator = DRSimulator()
        
        assert len(simulator.scenarios) == 5
    
    def test_required_scenarios_exist(self):
        """Test all required scenarios exist."""
        simulator = DRSimulator()
        
        expected_scenarios = [
            "database_failover",
            "redis_failover",
            "api_pod_crash",
            "ehr_timeout",
            "backup_restore",
        ]
        
        for name in expected_scenarios:
            scenario = simulator.get_scenario(name)
            assert scenario is not None, f"Scenario '{name}' not found"
    
    def test_database_failover_sla(self):
        """Test database_failover has 30s SLA."""
        simulator = DRSimulator()
        scenario = simulator.get_scenario("database_failover")
        
        assert scenario is not None
        assert scenario.target_recovery_seconds == 30
    
    def test_redis_failover_sla(self):
        """Test redis_failover has 10s SLA."""
        simulator = DRSimulator()
        scenario = simulator.get_scenario("redis_failover")
        
        assert scenario is not None
        assert scenario.target_recovery_seconds == 10
    
    def test_api_pod_crash_sla(self):
        """Test api_pod_crash has 60s SLA."""
        simulator = DRSimulator()
        scenario = simulator.get_scenario("api_pod_crash")
        
        assert scenario is not None
        assert scenario.target_recovery_seconds == 60
    
    def test_ehr_timeout_sla(self):
        """Test ehr_timeout has 5s SLA."""
        simulator = DRSimulator()
        scenario = simulator.get_scenario("ehr_timeout")
        
        assert scenario is not None
        assert scenario.target_recovery_seconds == 5
    
    def test_backup_restore_sla(self):
        """Test backup_restore has 900s (15min) SLA."""
        simulator = DRSimulator()
        scenario = simulator.get_scenario("backup_restore")
        
        assert scenario is not None
        assert scenario.target_recovery_seconds == 900
    
    def test_all_scenarios_have_steps(self):
        """Test all scenarios have at least one step."""
        simulator = DRSimulator()
        
        for scenario in simulator.scenarios:
            assert len(scenario.steps) > 0, f"Scenario '{scenario.name}' has no steps"
    
    def test_all_scenarios_have_descriptions(self):
        """Test all scenarios have descriptions."""
        simulator = DRSimulator()
        
        for scenario in simulator.scenarios:
            assert scenario.description, f"Scenario '{scenario.name}' has no description"


class TestDRSimulatorDryRun:
    """Tests for dry run mode."""
    
    def test_dry_run_prints_steps(self):
        """Test dry run mode prints steps."""
        log_output = []
        simulator = DRSimulator(log_handler=log_output.append)
        
        report = simulator.run_all(dry_run=True)
        
        # Check that steps were logged
        log_text = "\n".join(log_output)
        assert "Step" in log_text or "step" in log_text.lower()
    
    def test_dry_run_all_scenarios_pass(self):
        """Test all scenarios pass in dry run mode."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        report = simulator.run_all(dry_run=True)
        
        assert report.overall_passed is True
        assert report.passed_count == 5
        assert report.failed_count == 0
    
    def test_dry_run_sets_recovery_time(self):
        """Test dry run sets simulated recovery time."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        report = simulator.run_all(dry_run=True)
        
        for scenario in report.scenarios:
            assert scenario.actual_recovery_seconds is not None
            assert scenario.actual_recovery_seconds > 0
    
    def test_dry_run_recovery_under_sla(self):
        """Test dry run recovery times are under SLA."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        report = simulator.run_all(dry_run=True)
        
        for scenario in report.scenarios:
            assert scenario.sla_met is True
    
    def test_dry_run_flag_in_report(self):
        """Test dry run flag is set in report."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        report = simulator.run_all(dry_run=True)
        assert report.dry_run is True
        
        simulator.reset_scenarios()
        
        # Would fail in live mode without K8s setup
        # Just verify flag is respected
        report_dict = report.to_dict()
        assert report_dict["dry_run"] is True


class TestDRSimulatorRunScenario:
    """Tests for running individual scenarios."""
    
    def test_run_single_scenario(self):
        """Test running a single scenario by name."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        result = simulator.run_scenario("redis_failover", dry_run=True)
        
        assert result.name == "redis_failover"
        assert result.status == ScenarioStatus.PASSED
    
    def test_run_unknown_scenario_raises_error(self):
        """Test running unknown scenario raises ValueError."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        with pytest.raises(ValueError, match="Scenario not found"):
            simulator.run_scenario("nonexistent_scenario")
    
    def test_run_scenario_returns_updated_scenario(self):
        """Test run_scenario returns updated scenario object."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        result = simulator.run_scenario("api_pod_crash", dry_run=True)
        
        assert result.actual_recovery_seconds is not None
        assert result.notes != ""


class TestDRSimulatorReportStructure:
    """Tests for report structure and content."""
    
    def test_report_has_run_id(self):
        """Test report has unique run ID."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        report = simulator.run_all(dry_run=True)
        
        assert report.run_id is not None
        assert report.run_id.startswith("dr-")
    
    def test_report_has_timestamps(self):
        """Test report has start and end timestamps."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        report = simulator.run_all(dry_run=True)
        
        assert report.start_time is not None
        assert report.end_time is not None
        assert report.end_time >= report.start_time
    
    def test_report_scenarios_match_simulator(self):
        """Test report contains all simulator scenarios."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        report = simulator.run_all(dry_run=True)
        
        assert len(report.scenarios) == len(simulator.scenarios)
        
        report_names = {s.name for s in report.scenarios}
        simulator_names = {s.name for s in simulator.scenarios}
        assert report_names == simulator_names
    
    def test_report_serializable(self):
        """Test report can be serialized to dict."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        report = simulator.run_all(dry_run=True)
        result = report.to_dict()
        
        assert isinstance(result, dict)
        assert "run_id" in result
        assert "scenarios" in result
        assert isinstance(result["scenarios"], list)


class TestDRSimulatorCustomScenarios:
    """Tests for custom scenario support."""
    
    def test_custom_scenarios(self):
        """Test simulator with custom scenarios."""
        custom = [
            DRScenario(
                name="custom_test",
                description="Custom test scenario",
                target_recovery_seconds=15,
                steps=["Custom step 1"],
            ),
        ]
        
        simulator = DRSimulator(scenarios=custom, log_handler=lambda x: None)
        
        assert len(simulator.scenarios) == 1
        assert simulator.scenarios[0].name == "custom_test"
    
    def test_get_scenario_names(self):
        """Test getting list of scenario names."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        names = simulator.get_scenario_names()
        
        assert len(names) == 5
        assert "database_failover" in names
        assert "redis_failover" in names
    
    def test_register_custom_executor(self):
        """Test registering custom executor."""
        def custom_executor(sim: DRSimulator, scenario: DRScenario) -> float:
            return 5.0  # Always return 5 seconds
        
        simulator = DRSimulator(log_handler=lambda x: None)
        simulator.register_executor("redis_failover", custom_executor)
        
        # Run in non-dry mode with custom executor
        result = simulator.run_scenario("redis_failover", dry_run=False)
        
        assert result.actual_recovery_seconds == 5.0
        assert result.status == ScenarioStatus.PASSED


class TestDRSimulatorSkipAndReset:
    """Tests for skip and reset functionality."""
    
    def test_skip_scenario(self):
        """Test skipping a scenario."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        simulator.skip_scenario("backup_restore", "Too slow for test run")
        
        scenario = simulator.get_scenario("backup_restore")
        assert scenario.status == ScenarioStatus.SKIPPED
        assert "Too slow" in scenario.notes
    
    def test_skip_unknown_scenario_raises_error(self):
        """Test skipping unknown scenario raises ValueError."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        with pytest.raises(ValueError, match="Scenario not found"):
            simulator.skip_scenario("nonexistent")
    
    def test_reset_scenarios(self):
        """Test resetting all scenarios."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        # Run scenarios first
        simulator.run_all(dry_run=True)
        
        # Verify scenarios have results
        for scenario in simulator.scenarios:
            assert scenario.status != ScenarioStatus.PENDING
        
        # Reset
        simulator.reset_scenarios()
        
        # Verify all reset
        for scenario in simulator.scenarios:
            assert scenario.status == ScenarioStatus.PENDING
            assert scenario.actual_recovery_seconds is None
            assert scenario.notes == ""


class TestDRSimulatorValidation:
    """Tests for SLA validation."""
    
    def test_validate_sla_targets(self):
        """Test SLA target validation."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        validations = simulator.validate_sla_targets()
        
        assert len(validations) == 5
        assert all(v is True for v in validations.values())
    
    def test_validate_invalid_sla(self):
        """Test validation catches invalid SLAs."""
        custom = [
            DRScenario(
                name="zero_sla",
                description="Invalid zero SLA",
                target_recovery_seconds=0,
                steps=["Step 1"],
            ),
        ]
        
        simulator = DRSimulator(scenarios=custom, log_handler=lambda x: None)
        validations = simulator.validate_sla_targets()
        
        assert validations["zero_sla"] is False
    
    def test_get_sla_summary(self):
        """Test getting SLA summary."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        summary = simulator.get_sla_summary()
        
        assert "database_failover" in summary
        assert summary["database_failover"]["target_seconds"] == 30
        assert "description" in summary["database_failover"]


class TestDRSimulatorLiveMode:
    """Tests for live mode behavior."""
    
    def test_live_mode_without_executor_raises_error(self):
        """Test live mode raises error without custom executor."""
        simulator = DRSimulator(log_handler=lambda x: None)
        
        # Live mode should fail without K8s setup or custom executor
        result = simulator.run_scenario("redis_failover", dry_run=False)
        
        # Should be marked as failed due to NotImplementedError
        assert result.status == ScenarioStatus.FAILED
        assert "requires Kubernetes" in result.notes or "Error" in result.notes
    
    def test_live_mode_with_executor(self):
        """Test live mode works with custom executor."""
        def mock_executor(sim: DRSimulator, scenario: DRScenario) -> float:
            return scenario.target_recovery_seconds * 0.5
        
        simulator = DRSimulator(log_handler=lambda x: None)
        simulator.register_executor("redis_failover", mock_executor)
        
        result = simulator.run_scenario("redis_failover", dry_run=False)
        
        assert result.status == ScenarioStatus.PASSED
        assert result.actual_recovery_seconds == 5.0  # 10 * 0.5


class TestDRSimulatorFactories:
    """Tests for factory functions."""
    
    def test_create_default_simulator(self):
        """Test creating default simulator."""
        simulator = create_default_simulator()
        
        assert len(simulator.scenarios) == 5
    
    def test_create_minimal_simulator(self):
        """Test creating minimal simulator."""
        simulator = create_minimal_simulator()
        
        assert len(simulator.scenarios) == 2
        names = simulator.get_scenario_names()
        assert "redis_failover" in names
        assert "api_pod_crash" in names


class TestDRSimulatorErrorHandling:
    """Tests for error handling."""
    
    def test_executor_exception_handled(self):
        """Test exceptions in executor are handled."""
        def failing_executor(sim: DRSimulator, scenario: DRScenario) -> float:
            raise RuntimeError("Simulated failure")
        
        simulator = DRSimulator(log_handler=lambda x: None)
        simulator.register_executor("redis_failover", failing_executor)
        
        result = simulator.run_scenario("redis_failover", dry_run=False)
        
        assert result.status == ScenarioStatus.FAILED
        assert "Simulated failure" in result.notes
    
    def test_run_all_continues_after_failure(self):
        """Test run_all continues after a scenario fails."""
        def failing_executor(sim: DRSimulator, scenario: DRScenario) -> float:
            raise RuntimeError("Fail")
        
        simulator = DRSimulator(log_handler=lambda x: None)
        simulator.register_executor("database_failover", failing_executor)
        
        report = simulator.run_all(dry_run=False)
        
        # Should have run all scenarios despite failure
        assert report.total_scenarios == 5
        # database_failover should have failed
        db_scenario = next(s for s in report.scenarios if s.name == "database_failover")
        assert db_scenario.status == ScenarioStatus.FAILED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
