"""
Tests for the DeceptionAgent - Intelligent Honeytoken Deployment Orchestration.

This test suite verifies:
1. Decision logic based on confidence thresholds
2. Attack-specific overrides (prompt injection, jailbreak, etc.)
3. Repeat attacker escalation
4. Honeytoken deployment execution
5. Interaction tracking
6. Report generation
7. Thread safety

Test Categories:
- Decision Logic Tests (8): Confidence-based decisions
- Attack Override Tests (4): Attack-type-specific rules
- Deployment Tests (4): Honeytoken deployment execution
- Interaction Tests (3): Tracking attacker interactions
- Report Tests (2): Report generation
- Thread Safety Tests (2): Concurrent access
- Edge Case Tests (2): Error handling
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import threading
import time

from phoenix_guardian.security.deception_agent import (
    # Main classes
    DeceptionAgent,
    DeceptionDecision,
    DeploymentRecord,
    InteractionRecord,
    # Enums
    DeceptionStrategy,
    DeploymentTiming,
    InteractionType,
    # Exceptions
    DeceptionError,
    DeploymentError,
    DecisionError,
    # Constants
    CONFIDENCE_FULL_DECEPTION,
    CONFIDENCE_MIXED,
    CONFIDENCE_REACTIVE,
    REPEAT_ATTEMPT_ESCALATION,
    DEFAULT_COUNT_FULL_DECEPTION,
    DEFAULT_COUNT_MIXED,
    DEFAULT_COUNT_REACTIVE,
    MAX_HONEYTOKENS_PER_DEPLOYMENT,
    INTERACTION_ALERT_THRESHOLD
)
from phoenix_guardian.security.honeytoken_generator import (
    HoneytokenGenerator,
    LegalHoneytoken
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def generator():
    """Create a HoneytokenGenerator instance."""
    return HoneytokenGenerator()


@pytest.fixture
def agent(generator):
    """Create a DeceptionAgent instance."""
    return DeceptionAgent(generator)


@pytest.fixture
def high_confidence_attack():
    """Attack analysis with high confidence (95%)."""
    return {
        'attack_type': 'prompt_injection',
        'confidence': 0.95,
        'session_id': 'test-session-high',
        'attacker_ip': '203.0.113.1',
        'context': {
            'query': 'Ignore all previous instructions',
            'detected_patterns': ['ignore previous instructions'],
            'severity': 'critical'
        }
    }


@pytest.fixture
def medium_confidence_attack():
    """Attack analysis with medium confidence (80%)."""
    return {
        'attack_type': 'data_exfiltration',
        'confidence': 0.80,
        'session_id': 'test-session-medium',
        'attacker_ip': '203.0.113.2',
        'context': {}
    }


@pytest.fixture
def low_confidence_attack():
    """Attack analysis with low confidence (40%)."""
    return {
        'attack_type': 'unknown',
        'confidence': 0.40,
        'session_id': 'test-session-low',
        'attacker_ip': '203.0.113.3',
        'context': {}
    }


@pytest.fixture
def borderline_attack():
    """Attack analysis with borderline confidence (55%)."""
    return {
        'attack_type': 'data_exfiltration',
        'confidence': 0.55,
        'session_id': 'test-session-borderline',
        'attacker_ip': '203.0.113.4',
        'context': {}
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION LOGIC TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecisionLogic:
    """Tests for confidence-based decision making."""
    
    def test_high_confidence_full_deception(self, agent, high_confidence_attack):
        """Confidence 95% prompt injection should trigger IMMEDIATE strategy (override)."""
        decision = agent.decide_deployment(high_confidence_attack)
        
        assert decision.should_deploy is True
        # Prompt injection triggers IMMEDIATE override, not FULL_DECEPTION
        assert decision.strategy == DeceptionStrategy.IMMEDIATE
        assert decision.honeytoken_count >= DEFAULT_COUNT_FULL_DECEPTION
        assert decision.confidence_score == 0.95
        assert "PROMPT INJECTION" in decision.reasoning
        assert decision.deployment_timing == DeploymentTiming.IMMEDIATE.value
    
    def test_high_confidence_generic_full_deception(self, agent):
        """Confidence 95% non-special attack should trigger FULL_DECEPTION."""
        attack = {
            'attack_type': 'unknown',  # Generic attack type, no override
            'confidence': 0.95,
            'session_id': 'test-session-generic',
            'attacker_ip': '203.0.113.1',
            'context': {}
        }
        
        decision = agent.decide_deployment(attack)
        
        assert decision.should_deploy is True
        assert decision.strategy == DeceptionStrategy.FULL_DECEPTION
        assert decision.honeytoken_count >= DEFAULT_COUNT_FULL_DECEPTION
        assert "High confidence" in decision.reasoning
    
    def test_medium_confidence_mixed_strategy(self, agent, medium_confidence_attack):
        """Confidence 80% should trigger MIXED strategy."""
        decision = agent.decide_deployment(medium_confidence_attack)
        
        assert decision.should_deploy is True
        assert decision.strategy == DeceptionStrategy.MIXED
        assert decision.honeytoken_count >= DEFAULT_COUNT_MIXED
        assert decision.mix_ratio is not None
        assert 0.0 < decision.mix_ratio <= 0.5  # 30-40% fake
    
    def test_low_confidence_no_deployment(self, agent, low_confidence_attack):
        """Confidence 40% should NOT deploy honeytokens."""
        decision = agent.decide_deployment(low_confidence_attack)
        
        assert decision.should_deploy is False
        assert decision.honeytoken_count == 0
        assert decision.deployment_timing == DeploymentTiming.NONE.value
        assert "Low confidence" in decision.reasoning
    
    def test_borderline_first_attempt_no_deploy(self, agent, borderline_attack):
        """First attempt at 55% confidence should NOT deploy."""
        decision = agent.decide_deployment(borderline_attack)
        
        assert decision.should_deploy is False
        assert decision.strategy == DeceptionStrategy.REACTIVE
        assert "Waiting for repeat" in decision.reasoning
        assert decision.attempt_number == 1
    
    def test_borderline_second_attempt_deploys(self, agent, borderline_attack):
        """Second attempt from same session should trigger deployment."""
        # First attempt
        decision1 = agent.decide_deployment(borderline_attack)
        assert decision1.should_deploy is False
        
        # Second attempt (same session_id)
        decision2 = agent.decide_deployment(borderline_attack)
        
        assert decision2.should_deploy is True
        assert decision2.strategy == DeceptionStrategy.REACTIVE
        assert decision2.attempt_number == 2
        assert "Repeat attempt" in decision2.reasoning
        assert decision2.confidence_score > borderline_attack['confidence']
    
    def test_confidence_escalation_per_attempt(self, agent):
        """Confidence should escalate by 10% per repeat attempt."""
        session_id = 'test-escalation-session'
        base_confidence = 0.55
        
        attack = {
            'attack_type': 'test',
            'confidence': base_confidence,
            'session_id': session_id,
            'attacker_ip': '1.2.3.4'
        }
        
        # First attempt: 55%
        d1 = agent.decide_deployment(attack)
        assert d1.confidence_score == base_confidence
        
        # Second attempt: 55% + 10% = 65%
        d2 = agent.decide_deployment(attack)
        assert d2.confidence_score == pytest.approx(base_confidence + REPEAT_ATTEMPT_ESCALATION, abs=0.01)
        
        # Third attempt: 55% + 20% = 75%
        d3 = agent.decide_deployment(attack)
        assert d3.confidence_score == pytest.approx(base_confidence + 2 * REPEAT_ATTEMPT_ESCALATION, abs=0.01)
    
    def test_confidence_capped_at_100(self, agent):
        """Escalated confidence should not exceed 100%."""
        session_id = 'test-cap-session'
        
        attack = {
            'attack_type': 'test',
            'confidence': 0.95,
            'session_id': session_id,
            'attacker_ip': '1.2.3.4'
        }
        
        # Multiple attempts
        for _ in range(5):
            decision = agent.decide_deployment(attack)
        
        assert decision.confidence_score <= 1.0
    
    def test_different_sessions_independent(self, agent):
        """Different sessions should have independent attempt counts."""
        attack1 = {
            'attack_type': 'test',
            'confidence': 0.55,
            'session_id': 'session-A',
            'attacker_ip': '1.1.1.1'
        }
        
        attack2 = {
            'attack_type': 'test',
            'confidence': 0.55,
            'session_id': 'session-B',
            'attacker_ip': '2.2.2.2'
        }
        
        # Session A: 3 attempts
        for _ in range(3):
            agent.decide_deployment(attack1)
        
        # Session B: 1 attempt
        decision_b = agent.decide_deployment(attack2)
        
        assert decision_b.attempt_number == 1
        assert decision_b.confidence_score == 0.55


# ═══════════════════════════════════════════════════════════════════════════════
# ATTACK OVERRIDE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAttackOverrides:
    """Tests for attack-type-specific overrides."""
    
    def test_prompt_injection_immediate_deployment(self, agent):
        """Prompt injection should always deploy immediately at 70%+ confidence."""
        attack = {
            'attack_type': 'prompt_injection',
            'confidence': 0.75,
            'session_id': 'test-pi',
            'attacker_ip': '1.2.3.4'
        }
        
        decision = agent.decide_deployment(attack)
        
        assert decision.should_deploy is True
        assert decision.strategy == DeceptionStrategy.IMMEDIATE
        assert decision.deployment_timing == DeploymentTiming.IMMEDIATE.value
        assert "PROMPT INJECTION" in decision.reasoning
    
    def test_jailbreak_full_deception(self, agent):
        """Jailbreak attempts should trigger FULL_DECEPTION at 80%+ confidence."""
        attack = {
            'attack_type': 'jailbreak',
            'confidence': 0.85,
            'session_id': 'test-jailbreak',
            'attacker_ip': '1.2.3.4'
        }
        
        decision = agent.decide_deployment(attack)
        
        assert decision.should_deploy is True
        assert decision.strategy == DeceptionStrategy.FULL_DECEPTION
        assert decision.honeytoken_count == MAX_HONEYTOKENS_PER_DEPLOYMENT
        assert "JAILBREAK" in decision.reasoning
    
    def test_pii_extraction_immediate(self, agent):
        """PII extraction should trigger immediate deployment."""
        attack = {
            'attack_type': 'pii_extraction',
            'confidence': 0.75,
            'session_id': 'test-pii',
            'attacker_ip': '1.2.3.4'
        }
        
        decision = agent.decide_deployment(attack)
        
        assert decision.should_deploy is True
        assert decision.strategy == DeceptionStrategy.IMMEDIATE
        assert "PII EXTRACTION" in decision.reasoning
    
    def test_data_exfiltration_mixed_strategy(self, agent):
        """Data exfiltration should use MIXED strategy for intelligence gathering."""
        attack = {
            'attack_type': 'data_exfiltration',
            'confidence': 0.78,
            'session_id': 'test-exfil',
            'attacker_ip': '1.2.3.4'
        }
        
        decision = agent.decide_deployment(attack)
        
        assert decision.should_deploy is True
        assert decision.strategy == DeceptionStrategy.MIXED
        assert decision.mix_ratio is not None


# ═══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeployment:
    """Tests for honeytoken deployment execution."""
    
    def test_deploy_creates_honeytokens(self, agent, high_confidence_attack):
        """Deployment should create the specified number of honeytokens."""
        decision = agent.decide_deployment(high_confidence_attack)
        honeytokens = agent.deploy_honeytoken(decision, high_confidence_attack)
        
        assert len(honeytokens) == decision.honeytoken_count
        assert all(isinstance(ht, LegalHoneytoken) for ht in honeytokens)
    
    def test_deploy_stores_active_honeytokens(self, agent, high_confidence_attack):
        """Deployed honeytokens should be stored in active_honeytokens."""
        decision = agent.decide_deployment(high_confidence_attack)
        honeytokens = agent.deploy_honeytoken(decision, high_confidence_attack)
        
        active = agent.get_active_honeytokens()
        
        for ht in honeytokens:
            assert ht.honeytoken_id in active
    
    def test_deploy_records_deployment_history(self, agent, high_confidence_attack):
        """Deployment should be recorded in deployment_history."""
        decision = agent.decide_deployment(high_confidence_attack)
        honeytokens = agent.deploy_honeytoken(decision, high_confidence_attack)
        
        history = agent.get_deployment_history(high_confidence_attack['session_id'])
        
        assert len(history) == 1
        assert history[0].attack_type == high_confidence_attack['attack_type']
        assert len(history[0].honeytoken_ids) == len(honeytokens)
    
    def test_deploy_with_no_deploy_decision_returns_empty(self, agent, low_confidence_attack):
        """Deployment with should_deploy=False should return empty list."""
        decision = agent.decide_deployment(low_confidence_attack)
        honeytokens = agent.deploy_honeytoken(decision, low_confidence_attack)
        
        assert honeytokens == []


# ═══════════════════════════════════════════════════════════════════════════════
# INTERACTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestInteractionTracking:
    """Tests for tracking attacker interactions with honeytokens."""
    
    def test_track_interaction_records_data(self, agent, high_confidence_attack):
        """Tracking interaction should record the data."""
        decision = agent.decide_deployment(high_confidence_attack)
        honeytokens = agent.deploy_honeytoken(decision, high_confidence_attack)
        
        ht_id = honeytokens[0].honeytoken_id
        interaction_data = {
            'interaction_type': 'view',
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0 Test',
            'session_id': 'attacker-session'
        }
        
        record = agent.track_honeytoken_interaction(ht_id, interaction_data)
        
        assert record is not None
        assert record.honeytoken_id == ht_id
        assert record.interaction_type == InteractionType.VIEW
        assert record.ip_address == '192.168.1.100'
    
    def test_track_interaction_updates_honeytoken(self, agent, high_confidence_attack):
        """Tracking should update the honeytoken with attacker data."""
        decision = agent.decide_deployment(high_confidence_attack)
        honeytokens = agent.deploy_honeytoken(decision, high_confidence_attack)
        
        ht_id = honeytokens[0].honeytoken_id
        agent.track_honeytoken_interaction(ht_id, {
            'interaction_type': 'download',
            'ip_address': '10.0.0.50',
            'user_agent': 'curl/7.68.0'
        })
        
        ht = agent.get_active_honeytokens()[ht_id]
        
        assert ht.attacker_ip == '10.0.0.50'
        assert ht.user_agent == 'curl/7.68.0'
        assert ht.trigger_count >= 1
    
    def test_track_unknown_honeytoken_returns_none(self, agent):
        """Tracking unknown honeytoken should return None."""
        record = agent.track_honeytoken_interaction('unknown-id', {
            'interaction_type': 'view',
            'ip_address': '1.2.3.4'
        })
        
        assert record is None


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestReports:
    """Tests for report generation."""
    
    def test_deception_report_content(self, agent, high_confidence_attack, medium_confidence_attack):
        """Deception report should contain deployment statistics."""
        # Make some deployments
        d1 = agent.decide_deployment(high_confidence_attack)
        agent.deploy_honeytoken(d1, high_confidence_attack)
        
        d2 = agent.decide_deployment(medium_confidence_attack)
        agent.deploy_honeytoken(d2, medium_confidence_attack)
        
        report = agent.generate_deception_report()
        
        assert "DECEPTION AGENT ACTIVITY REPORT" in report
        assert "Total Deployments:" in report
        assert "DEPLOYMENTS BY STRATEGY" in report
        assert "RECENT DEPLOYMENTS" in report
    
    def test_export_forensic_evidence(self, agent, high_confidence_attack):
        """Forensic evidence export should include all data."""
        decision = agent.decide_deployment(high_confidence_attack)
        honeytokens = agent.deploy_honeytoken(decision, high_confidence_attack)
        
        # Track an interaction
        ht_id = honeytokens[0].honeytoken_id
        agent.track_honeytoken_interaction(ht_id, {
            'interaction_type': 'exfiltrate',
            'ip_address': '192.168.1.200'
        })
        
        evidence = agent.export_forensic_evidence(high_confidence_attack['session_id'])
        
        assert evidence['session_id'] == high_confidence_attack['session_id']
        assert len(evidence['deployments']) >= 1
        assert len(evidence['honeytokens']) >= 1
        assert len(evidence['interactions']) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# THREAD SAFETY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestThreadSafety:
    """Tests for thread-safe operations."""
    
    def test_concurrent_deployments(self, agent):
        """Multiple concurrent deployments should not corrupt state."""
        results = []
        errors = []
        
        def deploy_attack(attack_num):
            try:
                attack = {
                    'attack_type': 'prompt_injection',
                    'confidence': 0.92,
                    'session_id': f'concurrent-session-{attack_num}',
                    'attacker_ip': f'10.0.0.{attack_num}'
                }
                decision = agent.decide_deployment(attack)
                honeytokens = agent.deploy_honeytoken(decision, attack)
                results.append(len(honeytokens))
            except Exception as e:
                errors.append(str(e))
        
        threads = [threading.Thread(target=deploy_attack, args=(i,)) for i in range(10)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        assert all(count > 0 for count in results)
    
    def test_concurrent_session_tracking(self, agent):
        """Concurrent access to session tracking should be safe."""
        session_id = 'shared-session'
        
        def make_attempts(attempt_count):
            for _ in range(attempt_count):
                attack = {
                    'attack_type': 'test',
                    'confidence': 0.55,
                    'session_id': session_id,
                    'attacker_ip': '1.2.3.4'
                }
                agent.decide_deployment(attack)
        
        threads = [threading.Thread(target=make_attempts, args=(5,)) for _ in range(4)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Total attempts should be 4 threads * 5 attempts = 20
        assert agent.get_session_attempt_count(session_id) == 20


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_missing_confidence_defaults_to_zero(self, agent):
        """Missing confidence should default to 0 (no deployment)."""
        attack = {
            'attack_type': 'test',
            'session_id': 'test-missing',
            'attacker_ip': '1.2.3.4'
            # confidence missing
        }
        
        decision = agent.decide_deployment(attack)
        
        assert decision.should_deploy is False
        assert decision.confidence_score == 0.0
    
    def test_reset_session_tracking(self, agent):
        """Session tracking reset should clear attempt counts."""
        session_id = 'test-reset'
        
        attack = {
            'attack_type': 'test',
            'confidence': 0.55,
            'session_id': session_id,
            'attacker_ip': '1.2.3.4'
        }
        
        # Make some attempts
        for _ in range(3):
            agent.decide_deployment(attack)
        
        assert agent.get_session_attempt_count(session_id) == 3
        
        # Reset
        agent.reset_session_tracking(session_id)
        
        assert agent.get_session_attempt_count(session_id) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataclasses:
    """Tests for dataclass functionality."""
    
    def test_deception_decision_to_dict(self):
        """DeceptionDecision.to_dict() should return proper dictionary."""
        decision = DeceptionDecision(
            should_deploy=True,
            strategy=DeceptionStrategy.MIXED,
            honeytoken_count=3,
            confidence_score=0.82,
            reasoning="Test reasoning",
            deployment_timing="immediate",
            mix_ratio=0.3,
            attack_type="test"
        )
        
        data = decision.to_dict()
        
        assert data['should_deploy'] is True
        assert data['strategy'] == 'mixed'
        assert data['honeytoken_count'] == 3
        assert data['mix_ratio'] == 0.3
    
    def test_deployment_record_to_dict(self):
        """DeploymentRecord.to_dict() should return proper dictionary."""
        record = DeploymentRecord(
            deployment_id="dep_test123",
            honeytoken_ids=["ht_1", "ht_2"],
            attack_type="prompt_injection",
            confidence_score=0.95,
            strategy=DeceptionStrategy.FULL_DECEPTION,
            deployment_timestamp=datetime.now(timezone.utc),
            session_id="sess_test"
        )
        
        data = record.to_dict()
        
        assert data['deployment_id'] == "dep_test123"
        assert data['strategy'] == 'full_deception'
        assert isinstance(data['deployment_timestamp'], str)


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANT VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstants:
    """Tests for constant values."""
    
    def test_confidence_thresholds_ordered(self):
        """Confidence thresholds should be properly ordered."""
        assert CONFIDENCE_FULL_DECEPTION > CONFIDENCE_MIXED
        assert CONFIDENCE_MIXED > CONFIDENCE_REACTIVE
        assert CONFIDENCE_REACTIVE > 0.0
    
    def test_default_counts_reasonable(self):
        """Default honeytoken counts should be reasonable."""
        assert 1 <= DEFAULT_COUNT_REACTIVE <= MAX_HONEYTOKENS_PER_DEPLOYMENT
        assert 1 <= DEFAULT_COUNT_MIXED <= MAX_HONEYTOKENS_PER_DEPLOYMENT
        assert 1 <= DEFAULT_COUNT_FULL_DECEPTION <= MAX_HONEYTOKENS_PER_DEPLOYMENT
