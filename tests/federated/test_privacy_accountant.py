"""
Tests for Privacy Accountant - Differential Privacy Budget Tracking

These tests verify the privacy accounting system correctly tracks
epsilon spending and alerts when budgets are approaching exhaustion.
"""

import pytest
import math
from datetime import datetime
from typing import Dict, List

import sys
sys.path.insert(0, str(__file__).replace("\\", "/").rsplit("/", 3)[0])

from federated.privacy_accountant import (
    PrivacyAccountant,
    PrivacyAuditReport,
    PrivacyBudget,
    PrivacySpend,
    PrivacyAlertLevel,
    PrivacyAccountingMethod,
    RenyiDPAccountant,
)


class TestRenyiDPAccountant:
    """Test Rényi Differential Privacy accounting."""
    
    def test_rdp_gaussian_no_subsampling(self):
        """Test RDP for Gaussian mechanism without subsampling."""
        rdp = RenyiDPAccountant()
        
        sigma = 1.0
        alpha = 2.0
        
        result = rdp.compute_rdp_gaussian(sigma, sampling_rate=1.0, alpha=alpha)
        
        # Expected: α / (2σ²) = 2 / (2 * 1²) = 1.0
        assert abs(result - 1.0) < 0.01
    
    def test_rdp_gaussian_higher_sigma(self):
        """Test RDP decreases with higher noise multiplier."""
        rdp = RenyiDPAccountant()
        
        rdp_low_noise = rdp.compute_rdp_gaussian(0.5, 1.0, alpha=2.0)
        rdp_high_noise = rdp.compute_rdp_gaussian(2.0, 1.0, alpha=2.0)
        
        # Higher sigma = lower RDP (better privacy)
        assert rdp_high_noise < rdp_low_noise
    
    def test_rdp_accumulation(self):
        """Test RDP accumulates over multiple steps."""
        rdp = RenyiDPAccountant()
        
        sigma = 1.0
        steps = 10
        
        rdp.accumulate(sigma, sampling_rate=1.0, steps=steps)
        
        # RDP should accumulate linearly
        expected_per_step = 2.0 / (2 * sigma**2)
        expected_total = expected_per_step * steps
        
        assert abs(rdp.rdp_spent[2.0] - expected_total) < 0.01
    
    def test_rdp_to_epsilon_conversion(self):
        """Test converting RDP to (ε, δ)-DP."""
        rdp = RenyiDPAccountant()
        
        # Accumulate some privacy spend
        rdp.accumulate(sigma=1.1, sampling_rate=0.01, steps=100)
        
        delta = 1e-5
        epsilon, optimal_order = rdp.get_epsilon(delta)
        
        # Should get a finite epsilon
        assert epsilon > 0
        assert epsilon < float('inf')
        assert optimal_order is not None
    
    def test_rdp_subsampling_amplification(self):
        """Test that subsampling provides privacy amplification."""
        # Without subsampling
        rdp_no_subsample = RenyiDPAccountant()
        rdp_no_subsample.accumulate(sigma=1.0, sampling_rate=1.0, steps=10)
        eps_no_subsample, _ = rdp_no_subsample.get_epsilon(1e-5)
        
        # With subsampling
        rdp_subsample = RenyiDPAccountant()
        rdp_subsample.accumulate(sigma=1.0, sampling_rate=0.01, steps=10)
        eps_subsample, _ = rdp_subsample.get_epsilon(1e-5)
        
        # Subsampling should give better (lower) epsilon
        assert eps_subsample < eps_no_subsample
    
    def test_rdp_reset(self):
        """Test resetting RDP accumulator."""
        rdp = RenyiDPAccountant()
        
        rdp.accumulate(sigma=1.0, sampling_rate=1.0, steps=10)
        assert rdp.rdp_spent[2.0] > 0
        
        rdp.reset()
        
        assert all(v == 0.0 for v in rdp.rdp_spent.values())


class TestPrivacyBudget:
    """Test PrivacyBudget dataclass."""
    
    def test_budget_creation(self):
        """Test creating a privacy budget."""
        budget = PrivacyBudget(
            entity_id="hospital-001",
            entity_type="hospital",
            target_epsilon=2.0,
            target_delta=1e-5,
        )
        
        assert budget.entity_id == "hospital-001"
        assert budget.target_epsilon == 2.0
        assert budget.epsilon_spent == 0.0
    
    def test_remaining_budget(self):
        """Test calculating remaining budget."""
        budget = PrivacyBudget(
            entity_id="test",
            entity_type="hospital",
            target_epsilon=2.0,
            target_delta=1e-5,
            epsilon_spent=0.8,
        )
        
        assert budget.remaining() == 1.2
    
    def test_remaining_budget_exhausted(self):
        """Test remaining budget when exhausted."""
        budget = PrivacyBudget(
            entity_id="test",
            entity_type="hospital",
            target_epsilon=2.0,
            target_delta=1e-5,
            epsilon_spent=2.5,  # Exceeded
        )
        
        assert budget.remaining() == 0.0
    
    def test_percent_used(self):
        """Test calculating percent used."""
        budget = PrivacyBudget(
            entity_id="test",
            entity_type="hospital",
            target_epsilon=2.0,
            target_delta=1e-5,
            epsilon_spent=1.0,
        )
        
        assert budget.percent_used() == 50.0
    
    def test_alert_level_normal(self):
        """Test normal alert level."""
        budget = PrivacyBudget(
            entity_id="test",
            entity_type="hospital",
            target_epsilon=2.0,
            target_delta=1e-5,
            epsilon_spent=0.5,  # 25%
        )
        
        assert budget.alert_level() == PrivacyAlertLevel.NORMAL
    
    def test_alert_level_warning(self):
        """Test warning alert level."""
        budget = PrivacyBudget(
            entity_id="test",
            entity_type="hospital",
            target_epsilon=2.0,
            target_delta=1e-5,
            epsilon_spent=1.2,  # 60%
        )
        
        assert budget.alert_level() == PrivacyAlertLevel.WARNING
    
    def test_alert_level_high(self):
        """Test high alert level."""
        budget = PrivacyBudget(
            entity_id="test",
            entity_type="hospital",
            target_epsilon=2.0,
            target_delta=1e-5,
            epsilon_spent=1.6,  # 80%
        )
        
        assert budget.alert_level() == PrivacyAlertLevel.HIGH
    
    def test_alert_level_critical(self):
        """Test critical alert level."""
        budget = PrivacyBudget(
            entity_id="test",
            entity_type="hospital",
            target_epsilon=2.0,
            target_delta=1e-5,
            epsilon_spent=1.9,  # 95%
        )
        
        assert budget.alert_level() == PrivacyAlertLevel.CRITICAL
    
    def test_alert_level_exhausted(self):
        """Test exhausted alert level."""
        budget = PrivacyBudget(
            entity_id="test",
            entity_type="hospital",
            target_epsilon=2.0,
            target_delta=1e-5,
            epsilon_spent=2.1,  # 105%
        )
        
        assert budget.alert_level() == PrivacyAlertLevel.EXHAUSTED


class TestPrivacyAccountant:
    """Test main PrivacyAccountant class."""
    
    def test_accountant_creation(self):
        """Test creating a privacy accountant."""
        accountant = PrivacyAccountant(
            global_epsilon=10.0,
            per_hospital_epsilon=2.0,
        )
        
        assert accountant.global_epsilon == 10.0
        assert accountant.per_hospital_epsilon == 2.0
        assert accountant.global_budget.target_epsilon == 10.0
    
    def test_register_hospital(self):
        """Test registering a hospital."""
        accountant = PrivacyAccountant()
        
        budget = accountant.register_hospital("hospital-001")
        
        assert budget.entity_id == "hospital-001"
        assert "hospital-001" in accountant.hospital_budgets
        assert "hospital-001" in accountant.hospital_rdp
    
    def test_register_hospital_idempotent(self):
        """Test registering same hospital twice returns same budget."""
        accountant = PrivacyAccountant()
        
        budget1 = accountant.register_hospital("hospital-001")
        budget2 = accountant.register_hospital("hospital-001")
        
        assert budget1 is budget2
    
    def test_record_spend_global(self):
        """Test recording global privacy spend."""
        accountant = PrivacyAccountant(global_epsilon=10.0)
        
        spend = accountant.record_spend(
            operation_id="op-001",
            operation_type="training_round",
            noise_multiplier=1.1,
            clip_norm=1.0,
            num_samples=1000,
            sampling_rate=0.01,
        )
        
        assert spend.operation_id == "op-001"
        assert spend.epsilon > 0
        assert accountant.global_budget.epsilon_spent > 0
        assert len(accountant.global_budget.spend_history) == 1
    
    def test_record_spend_hospital(self):
        """Test recording hospital-specific privacy spend."""
        accountant = PrivacyAccountant(per_hospital_epsilon=2.0)
        
        spend = accountant.record_spend(
            operation_id="op-001",
            operation_type="training_round",
            noise_multiplier=1.1,
            clip_norm=1.0,
            num_samples=1000,
            sampling_rate=0.01,
            hospital_id="hospital-001",
        )
        
        assert spend.hospital_id == "hospital-001"
        assert "hospital-001" in accountant.hospital_budgets
        assert accountant.hospital_budgets["hospital-001"].epsilon_spent > 0
    
    def test_record_spend_updates_both(self):
        """Test that hospital spend also updates global budget."""
        accountant = PrivacyAccountant()
        
        accountant.record_spend(
            operation_id="op-001",
            operation_type="training_round",
            noise_multiplier=1.1,
            clip_norm=1.0,
            num_samples=1000,
            hospital_id="hospital-001",
        )
        
        # Both should be updated
        assert accountant.global_budget.epsilon_spent > 0
        assert accountant.hospital_budgets["hospital-001"].epsilon_spent > 0
    
    def test_can_perform_operation_success(self):
        """Test operation allowed when budget available."""
        accountant = PrivacyAccountant(
            global_epsilon=10.0,
            per_hospital_epsilon=2.0,
        )
        accountant.register_hospital("hospital-001")
        
        can_perform, reason = accountant.can_perform_operation(
            estimated_epsilon=0.5,
            hospital_id="hospital-001"
        )
        
        assert can_perform is True
        assert reason == "OK"
    
    def test_can_perform_operation_exceeds_hospital(self):
        """Test operation blocked when hospital budget exceeded."""
        accountant = PrivacyAccountant(
            global_epsilon=10.0,
            per_hospital_epsilon=2.0,
        )
        
        budget = accountant.register_hospital("hospital-001")
        budget.epsilon_spent = 1.8
        
        can_perform, reason = accountant.can_perform_operation(
            estimated_epsilon=0.5,
            hospital_id="hospital-001"
        )
        
        assert can_perform is False
        assert "hospital" in reason.lower()
    
    def test_can_perform_operation_exceeds_global(self):
        """Test operation blocked when global budget exceeded."""
        accountant = PrivacyAccountant(
            global_epsilon=10.0,
            per_hospital_epsilon=20.0,  # Higher than global
        )
        
        accountant.global_budget.epsilon_spent = 9.8
        
        can_perform, reason = accountant.can_perform_operation(
            estimated_epsilon=0.5,
            hospital_id="hospital-001"
        )
        
        assert can_perform is False
        assert "global" in reason.lower()
    
    def test_get_budget_status(self):
        """Test getting budget status."""
        accountant = PrivacyAccountant(global_epsilon=10.0)
        accountant.global_budget.epsilon_spent = 2.5
        
        status = accountant.get_budget_status(None)
        
        assert status["entity_id"] == "global"
        assert status["target_epsilon"] == 10.0
        assert status["epsilon_spent"] == 2.5
        assert status["epsilon_remaining"] == 7.5
        assert status["percent_used"] == 25.0
    
    def test_get_all_budgets(self):
        """Test getting all budget statuses."""
        accountant = PrivacyAccountant()
        accountant.register_hospital("hospital-001")
        accountant.register_hospital("hospital-002")
        
        all_budgets = accountant.get_all_budgets()
        
        assert "global" in all_budgets
        assert "hospitals" in all_budgets
        assert "hospital-001" in all_budgets["hospitals"]
        assert "hospital-002" in all_budgets["hospitals"]
    
    def test_get_audit_trail(self):
        """Test getting audit trail."""
        accountant = PrivacyAccountant()
        
        # Record multiple operations
        for i in range(5):
            accountant.record_spend(
                operation_id=f"op-{i}",
                operation_type="training_round",
                noise_multiplier=1.1,
                clip_norm=1.0,
                num_samples=1000,
            )
        
        trail = accountant.get_audit_trail(limit=3)
        
        assert len(trail) == 3
        # Should be sorted by timestamp descending
        assert trail[0]["operation_id"] == "op-4"
    
    def test_estimate_epsilon_for_rounds(self):
        """Test estimating epsilon for multiple rounds."""
        accountant = PrivacyAccountant()
        
        epsilon = accountant.estimate_epsilon_for_rounds(
            noise_multiplier=1.1,
            sampling_rate=0.01,
            num_rounds=10,
            delta=1e-5,
        )
        
        assert epsilon > 0
        assert epsilon < float('inf')
    
    def test_recommend_noise_multiplier(self):
        """Test recommending noise multiplier for target epsilon."""
        accountant = PrivacyAccountant()
        
        sigma = accountant.recommend_noise_multiplier(
            target_epsilon=1.0,
            num_rounds=10,
            sampling_rate=0.01,
            delta=1e-5,
        )
        
        # Verify the recommendation achieves target
        actual_epsilon = accountant.estimate_epsilon_for_rounds(
            sigma, 0.01, 10, 1e-5
        )
        
        assert abs(actual_epsilon - 1.0) < 0.1  # Within 10%


class TestPrivacyAlerts:
    """Test privacy alert functionality."""
    
    def test_alert_triggered_on_high_usage(self):
        """Test that alerts are triggered at high usage."""
        alerts_received = []
        
        def alert_callback(alert):
            alerts_received.append(alert)
        
        accountant = PrivacyAccountant(global_epsilon=1.0)
        accountant.add_alert_callback(alert_callback)
        
        # Spend enough to trigger high alert
        for i in range(20):
            accountant.record_spend(
                operation_id=f"op-{i}",
                operation_type="training_round",
                noise_multiplier=1.1,
                clip_norm=1.0,
                num_samples=1000,
                sampling_rate=0.1,
            )
        
        # Should have received alerts
        assert len(alerts_received) > 0
    
    def test_alert_contains_required_fields(self):
        """Test alert contains all required fields."""
        alerts_received = []
        
        accountant = PrivacyAccountant(global_epsilon=0.5)
        accountant.add_alert_callback(lambda a: alerts_received.append(a))
        
        # Trigger alert
        for i in range(10):
            accountant.record_spend(
                operation_id=f"op-{i}",
                operation_type="training_round",
                noise_multiplier=0.5,
                clip_norm=1.0,
                num_samples=1000,
            )
        
        if alerts_received:
            alert = alerts_received[-1]
            assert "entity_id" in alert
            assert "level" in alert
            assert "epsilon_spent" in alert
            assert "target_epsilon" in alert
            assert "percent_used" in alert


class TestPrivacyAuditReport:
    """Test privacy audit report generation."""
    
    @pytest.fixture
    def accountant_with_data(self):
        """Create accountant with test data."""
        accountant = PrivacyAccountant(
            global_epsilon=10.0,
            per_hospital_epsilon=2.0,
        )
        
        for i in range(10):
            accountant.record_spend(
                operation_id=f"op-{i}",
                operation_type="training_round",
                noise_multiplier=1.1,
                clip_norm=1.0,
                num_samples=1000,
                hospital_id="hospital-001",
                session_id="session-001",
                round_id=i,
            )
        
        return accountant
    
    def test_generate_json_report(self, accountant_with_data):
        """Test generating JSON format report."""
        report = PrivacyAuditReport(accountant_with_data)
        
        json_report = report.generate_report(
            hospital_id="hospital-001",
            include_history=True,
            format="json"
        )
        
        import json
        data = json.loads(json_report)
        
        assert data["report_type"] == "privacy_audit"
        assert data["entity"] == "hospital-001"
        assert "budget_status" in data
        assert "operation_history" in data
    
    def test_generate_markdown_report(self, accountant_with_data):
        """Test generating Markdown format report."""
        report = PrivacyAuditReport(accountant_with_data)
        
        md_report = report.generate_report(
            hospital_id="hospital-001",
            include_history=True,
            format="markdown"
        )
        
        assert "# Privacy Audit Report" in md_report
        assert "hospital-001" in md_report
        assert "Budget Status" in md_report
        assert "Recent Operations" in md_report
    
    def test_report_without_history(self, accountant_with_data):
        """Test report without operation history."""
        report = PrivacyAuditReport(accountant_with_data)
        
        json_report = report.generate_report(
            hospital_id="hospital-001",
            include_history=False,
            format="json"
        )
        
        import json
        data = json.loads(json_report)
        
        assert "operation_history" not in data
    
    def test_global_report(self, accountant_with_data):
        """Test generating global report."""
        report = PrivacyAuditReport(accountant_with_data)
        
        json_report = report.generate_report(
            hospital_id=None,
            format="json"
        )
        
        import json
        data = json.loads(json_report)
        
        assert data["entity"] == "global"


class TestPrivacySpend:
    """Test PrivacySpend dataclass."""
    
    def test_spend_creation(self):
        """Test creating a privacy spend record."""
        spend = PrivacySpend(
            operation_id="op-001",
            operation_type="training_round",
            hospital_id="hospital-001",
            epsilon=0.5,
            delta=1e-5,
            noise_multiplier=1.1,
            clip_norm=1.0,
            num_samples=1000,
        )
        
        assert spend.operation_id == "op-001"
        assert spend.epsilon == 0.5
        assert spend.num_samples == 1000
        assert spend.timestamp is not None
    
    def test_spend_with_session_context(self):
        """Test spend with training session context."""
        spend = PrivacySpend(
            operation_id="op-001",
            operation_type="training_round",
            hospital_id="hospital-001",
            epsilon=0.5,
            delta=1e-5,
            noise_multiplier=1.1,
            clip_norm=1.0,
            session_id="session-123",
            round_id=5,
        )
        
        assert spend.session_id == "session-123"
        assert spend.round_id == 5
