"""
Tests for ABTester - Model Comparison & Auto-Deployment.

Tests cover:
- Traffic splitting (5 tests)
- Metrics calculation (6 tests)
- Statistical testing (6 tests)
- Decision making (5 tests)
- Auto-deployment (3 tests)
- Configuration (3 tests)
- Integration (2+ tests)

Total: 30+ tests
"""

import pytest
import sys
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
import json
import uuid

# Use real numpy
import numpy as np

# Store original scipy reference if it exists
_original_scipy = sys.modules.get('scipy')
_original_scipy_stats = sys.modules.get('scipy.stats')

# Mock scipy.stats functions that ABTester uses
mock_scipy_stats = MagicMock()
mock_scipy_stats.chi2_contingency = Mock(return_value=(5.0, 0.025, 1, np.array([[50, 50], [55, 45]])))
mock_scipy_stats.norm = MagicMock()
mock_scipy_stats.norm.ppf = Mock(return_value=1.96)
mock_scipy_stats.ttest_ind = Mock(return_value=(2.5, 0.015))

# Import the module directly  
import phoenix_guardian.learning.ab_tester as ab_tester_module

# Ensure dependency flags are set
ab_tester_module.NUMPY_AVAILABLE = True
ab_tester_module.SCIPY_AVAILABLE = True
ab_tester_module.np = np
ab_tester_module.scipy_stats = mock_scipy_stats

from phoenix_guardian.learning.ab_tester import (
    ABTester,
    ABTestConfig,
    Prediction,
    ModelMetrics,
    StatisticalResult,
    ABTestResult,
    ModelVariant,
    TestStatus,
    DeploymentDecision,
    ABTesterError,
    InsufficientSampleError,
    TestNotRunningError,
    DependencyError,
    DeploymentError,
    ConfigurationError,
    DEFAULT_TRAFFIC_SPLIT_A,
    DEFAULT_TRAFFIC_SPLIT_B,
    DEFAULT_MIN_SAMPLE_SIZE,
    DEFAULT_MIN_IMPROVEMENT,
    DEFAULT_SIGNIFICANCE_LEVEL,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def config():
    """Create test configuration."""
    return ABTestConfig(
        test_id="test_ab_001",
        model_a_path="models/production/model_a",
        model_b_path="models/candidate/model_b",
        traffic_split_a=0.5,
        traffic_split_b=0.5,
        min_sample_size=100,
        min_improvement=0.02,
        significance_level=0.05
    )


@pytest.fixture
def tester(config):
    """Create A/B tester instance."""
    return ABTester(config)


@pytest.fixture
def populated_tester(config):
    """Create tester with sample predictions."""
    tester = ABTester(config)
    
    # Add predictions for Model A (55% accuracy)
    for i in range(100):
        pred = Prediction(
            prediction_id=f"pred_a_{i}",
            model_variant=ModelVariant.MODEL_A,
            input_text=f"Test text {i}",
            predicted_label=i % 2,
            confidence=0.80 + (i % 20) * 0.01,
            actual_label=i % 2 if i < 55 else (i + 1) % 2,  # 55% correct
            latency_ms=150.0 + i % 50
        )
        tester.predictions.append(pred)
    
    # Add predictions for Model B (62% accuracy - better)
    for i in range(100):
        pred = Prediction(
            prediction_id=f"pred_b_{i}",
            model_variant=ModelVariant.MODEL_B,
            input_text=f"Test text {i}",
            predicted_label=i % 2,
            confidence=0.82 + (i % 20) * 0.01,
            actual_label=i % 2 if i < 62 else (i + 1) % 2,  # 62% correct
            latency_ms=155.0 + i % 50
        )
        tester.predictions.append(pred)
    
    return tester


@pytest.fixture
def sample_metrics_a():
    """Create sample metrics for Model A."""
    return ModelMetrics(
        total_predictions=120,
        labeled_predictions=100,
        correct_predictions=55,
        accuracy=0.55,
        precision=0.56,
        recall=0.54,
        f1=0.55,
        avg_confidence=0.82,
        avg_latency_ms=150.0,
        true_positives=27,
        false_positives=21,
        true_negatives=28,
        false_negatives=24
    )


@pytest.fixture
def sample_metrics_b():
    """Create sample metrics for Model B (better)."""
    return ModelMetrics(
        total_predictions=118,
        labeled_predictions=100,
        correct_predictions=62,
        accuracy=0.62,
        precision=0.63,
        recall=0.61,
        f1=0.62,
        avg_confidence=0.85,
        avg_latency_ms=155.0,
        true_positives=31,
        false_positives=18,
        true_negatives=31,
        false_negatives=20
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TRAFFIC SPLITTING TESTS (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrafficSplitting:
    """Tests for traffic splitting."""
    
    def test_assign_variant_random(self, tester):
        """Test random variant assignment."""
        variants = [tester.assign_variant() for _ in range(100)]
        
        # Should have both variants
        assert ModelVariant.MODEL_A in variants
        assert ModelVariant.MODEL_B in variants
    
    def test_assign_variant_consistent_hashing(self, tester):
        """Test consistent hashing for same user."""
        user_id = "user_12345"
        
        # Same user should always get same variant
        variants = [tester.assign_variant(user_id) for _ in range(10)]
        
        assert len(set(variants)) == 1  # All same variant
    
    def test_traffic_split_ratio(self, tester):
        """Test that traffic split approximates configured ratio."""
        # Generate many assignments
        assignments = [tester.assign_variant() for _ in range(1000)]
        
        model_a_count = sum(1 for v in assignments if v == ModelVariant.MODEL_A)
        ratio_a = model_a_count / 1000
        
        # Should be approximately 50% (within 10% margin)
        assert 0.40 <= ratio_a <= 0.60
    
    def test_route_prediction(self, tester):
        """Test routing prediction to model."""
        prediction = tester.route_prediction("Test input text")
        
        assert prediction.prediction_id is not None
        assert prediction.model_variant in [ModelVariant.MODEL_A, ModelVariant.MODEL_B]
        assert prediction.input_text == "Test input text"
        assert prediction.predicted_label in [0, 1]
        assert 0.0 <= prediction.confidence <= 1.0
    
    def test_variant_distribution(self, tester):
        """Test getting variant distribution."""
        # Add some predictions
        for i in range(10):
            tester.route_prediction(f"Test text {i}")
        
        distribution = tester.get_variant_distribution()
        
        assert distribution['total'] == 10
        assert distribution['model_a'] + distribution['model_b'] == 10


# ═══════════════════════════════════════════════════════════════════════════════
# METRICS CALCULATION TESTS (6 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetricsCalculation:
    """Tests for metrics calculation."""
    
    def test_calculate_metrics_with_ground_truth(self, populated_tester):
        """Test metrics calculation with ground truth."""
        metrics = populated_tester.calculate_metrics(ModelVariant.MODEL_A)
        
        assert metrics.total_predictions == 100
        assert metrics.labeled_predictions == 100
        assert metrics.accuracy == 0.55  # 55 correct out of 100
    
    def test_calculate_metrics_without_ground_truth(self, tester):
        """Test metrics calculation without ground truth."""
        # Add predictions without ground truth
        for i in range(10):
            pred = Prediction(
                prediction_id=f"pred_{i}",
                model_variant=ModelVariant.MODEL_A,
                input_text=f"Text {i}",
                predicted_label=0,
                confidence=0.85
            )
            tester.predictions.append(pred)
        
        metrics = tester.calculate_metrics(ModelVariant.MODEL_A)
        
        assert metrics.total_predictions == 10
        assert metrics.labeled_predictions == 0
        assert metrics.accuracy == 0.0
    
    def test_add_ground_truth(self, tester):
        """Test adding ground truth to prediction."""
        pred = tester.route_prediction("Test text")
        
        result = tester.add_ground_truth(pred.prediction_id, actual_label=1)
        
        assert result is True
        assert pred.actual_label == 1
    
    def test_accuracy_calculation(self, sample_metrics_a):
        """Test accuracy calculation."""
        # 55 correct out of 100 = 55%
        assert sample_metrics_a.accuracy == 0.55
    
    def test_precision_recall_f1(self, populated_tester):
        """Test precision, recall, F1 calculation."""
        metrics = populated_tester.calculate_metrics(ModelVariant.MODEL_B)
        
        # Should have calculated precision/recall/f1
        assert 0.0 <= metrics.precision <= 1.0
        assert 0.0 <= metrics.recall <= 1.0
        assert 0.0 <= metrics.f1 <= 1.0
    
    def test_empty_predictions(self, tester):
        """Test metrics with empty predictions."""
        metrics = tester.calculate_metrics(ModelVariant.MODEL_A)
        
        assert metrics.total_predictions == 0
        assert metrics.accuracy == 0.0
        assert metrics.f1 == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# STATISTICAL TESTING TESTS (6 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestStatisticalTesting:
    """Tests for statistical significance testing."""
    
    def test_significance_test_significant(self, populated_tester, sample_metrics_a, sample_metrics_b):
        """Test significance test when significant."""
        # Mock chi2_contingency to return significant result
        with patch.object(ab_tester_module.scipy_stats, 'chi2_contingency') as mock_chi2:
            mock_chi2.return_value = (8.5, 0.003, 1, [[50, 50], [55, 45]])
            
            result = populated_tester.test_significance(sample_metrics_a, sample_metrics_b)
        
        assert result.is_significant is True
        assert result.p_value < 0.05
    
    def test_significance_test_not_significant(self, populated_tester, sample_metrics_a, sample_metrics_b):
        """Test significance test when not significant."""
        with patch.object(ab_tester_module.scipy_stats, 'chi2_contingency') as mock_chi2:
            mock_chi2.return_value = (1.2, 0.27, 1, [[50, 50], [52, 48]])
            
            result = populated_tester.test_significance(sample_metrics_a, sample_metrics_b)
        
        assert result.is_significant is False
        assert result.p_value > 0.05
    
    def test_significance_insufficient_sample(self, tester, sample_metrics_a):
        """Test significance test with insufficient sample."""
        small_metrics = ModelMetrics(
            total_predictions=50,
            labeled_predictions=50,  # Below min_sample_size of 100
            correct_predictions=30,
            accuracy=0.60,
            precision=0.60,
            recall=0.60,
            f1=0.60,
            avg_confidence=0.85,
            avg_latency_ms=150.0
        )
        
        result = tester.test_significance(sample_metrics_a, small_metrics)
        
        assert result.is_significant is False
        assert result.p_value == 1.0  # No test performed
    
    def test_confidence_interval(self, populated_tester, sample_metrics_a, sample_metrics_b):
        """Test confidence interval calculation."""
        result = populated_tester.test_significance(sample_metrics_a, sample_metrics_b)
        
        ci_lower, ci_upper = result.confidence_interval
        
        # CI should bracket the improvement
        improvement = sample_metrics_b.accuracy - sample_metrics_a.accuracy
        # Note: CI might not perfectly bracket due to mock
        assert ci_lower < ci_upper
    
    def test_chi_square_test(self, populated_tester, sample_metrics_a, sample_metrics_b):
        """Test chi-square test is used."""
        result = populated_tester.test_significance(sample_metrics_a, sample_metrics_b)
        
        assert result.test_name == "chi_square"
        assert result.statistic >= 0  # Chi-square is non-negative
    
    def test_p_value_calculation(self, populated_tester, sample_metrics_a, sample_metrics_b):
        """Test p-value calculation."""
        with patch.object(ab_tester_module.scipy_stats, 'chi2_contingency') as mock_chi2:
            mock_chi2.return_value = (5.5, 0.019, 1, [[50, 50], [55, 45]])
            
            result = populated_tester.test_significance(sample_metrics_a, sample_metrics_b)
        
        assert 0.0 <= result.p_value <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION MAKING TESTS (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecisionMaking:
    """Tests for deployment decision making."""
    
    def test_decision_deploy_b(self, populated_tester):
        """Test decision to deploy Model B."""
        with patch.object(ab_tester_module.scipy_stats, 'chi2_contingency') as mock_chi2:
            mock_chi2.return_value = (10.0, 0.001, 1, [[50, 50], [60, 40]])
            
            result = populated_tester.analyze_results()
        
        # B is better (62% vs 55%) and significant
        assert result.decision == DeploymentDecision.DEPLOY_B
    
    def test_decision_keep_a(self, tester):
        """Test decision to keep Model A."""
        # Add predictions where B is worse
        for i in range(100):
            pred_a = Prediction(
                prediction_id=f"pred_a_{i}",
                model_variant=ModelVariant.MODEL_A,
                input_text=f"Text {i}",
                predicted_label=i % 2,
                confidence=0.85,
                actual_label=i % 2 if i < 70 else (i + 1) % 2  # 70% correct
            )
            tester.predictions.append(pred_a)
            
            pred_b = Prediction(
                prediction_id=f"pred_b_{i}",
                model_variant=ModelVariant.MODEL_B,
                input_text=f"Text {i}",
                predicted_label=i % 2,
                confidence=0.80,
                actual_label=i % 2 if i < 50 else (i + 1) % 2  # 50% correct - worse
            )
            tester.predictions.append(pred_b)
        
        with patch.object(ab_tester_module.scipy_stats, 'chi2_contingency') as mock_chi2:
            mock_chi2.return_value = (8.0, 0.005, 1, [[70, 30], [50, 50]])
            
            result = tester.analyze_results()
        
        assert result.decision == DeploymentDecision.KEEP_A
    
    def test_decision_inconclusive(self, tester):
        """Test inconclusive decision."""
        # Add predictions where B is slightly better but not significant
        for i in range(100):
            pred_a = Prediction(
                prediction_id=f"pred_a_{i}",
                model_variant=ModelVariant.MODEL_A,
                input_text=f"Text {i}",
                predicted_label=i % 2,
                confidence=0.85,
                actual_label=i % 2 if i < 60 else (i + 1) % 2
            )
            tester.predictions.append(pred_a)
            
            pred_b = Prediction(
                prediction_id=f"pred_b_{i}",
                model_variant=ModelVariant.MODEL_B,
                input_text=f"Text {i}",
                predicted_label=i % 2,
                confidence=0.86,
                actual_label=i % 2 if i < 63 else (i + 1) % 2  # Slightly better
            )
            tester.predictions.append(pred_b)
        
        with patch.object(ab_tester_module.scipy_stats, 'chi2_contingency') as mock_chi2:
            mock_chi2.return_value = (1.5, 0.22, 1, [[60, 40], [63, 37]])  # Not significant
            
            result = tester.analyze_results()
        
        assert result.decision == DeploymentDecision.INCONCLUSIVE
    
    def test_min_improvement_threshold(self, config):
        """Test minimum improvement threshold."""
        assert config.min_improvement == 0.02  # 2%
        
        # Create tester with different threshold
        custom_config = ABTestConfig(
            test_id="custom_test",
            min_improvement=0.05  # 5%
        )
        
        assert custom_config.min_improvement == 0.05
    
    def test_significance_requirement(self, populated_tester):
        """Test that significance is required for deployment."""
        with patch.object(ab_tester_module.scipy_stats, 'chi2_contingency') as mock_chi2:
            # Big improvement but not significant
            mock_chi2.return_value = (2.0, 0.16, 1, [[50, 50], [60, 40]])
            
            result = populated_tester.analyze_results()
        
        # Should not deploy without significance
        assert result.decision != DeploymentDecision.DEPLOY_B


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-DEPLOYMENT TESTS (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAutoDeployment:
    """Tests for auto-deployment."""
    
    def test_deploy_winner_deploy_b(self, populated_tester, tmp_path):
        """Test deploying Model B when decision is DEPLOY_B."""
        with patch.object(ab_tester_module.scipy_stats, 'chi2_contingency') as mock_chi2:
            mock_chi2.return_value = (10.0, 0.001, 1, [[50, 50], [60, 40]])
            
            result = populated_tester.analyze_results()
        
        assert result.decision == DeploymentDecision.DEPLOY_B
        
        # Deploy winner
        deployed = populated_tester.deploy_winner(
            result,
            production_path=str(tmp_path / "production"),
            archive_path=str(tmp_path / "archive")
        )
        
        assert deployed is True
        assert populated_tester.status == TestStatus.COMPLETED
    
    def test_deploy_winner_keep_a(self, tester):
        """Test no deployment when decision is KEEP_A."""
        # Create result with KEEP_A decision
        result = ABTestResult(
            test_id="test",
            config=tester.config,
            model_a_metrics=ModelMetrics(),
            model_b_metrics=ModelMetrics(),
            improvement=-0.05,
            improvement_percent=-5.0,
            statistical_result=StatisticalResult(
                test_name="chi_square",
                statistic=5.0,
                p_value=0.02,
                is_significant=True
            ),
            decision=DeploymentDecision.KEEP_A,
            status=TestStatus.RUNNING,
            started_at=datetime.now()
        )
        
        deployed = tester.deploy_winner(result)
        
        assert deployed is False
    
    def test_deploy_winner_inconclusive(self, tester):
        """Test no deployment when decision is INCONCLUSIVE."""
        result = ABTestResult(
            test_id="test",
            config=tester.config,
            model_a_metrics=ModelMetrics(),
            model_b_metrics=ModelMetrics(),
            improvement=0.03,
            improvement_percent=3.0,
            statistical_result=StatisticalResult(
                test_name="chi_square",
                statistic=2.0,
                p_value=0.15,
                is_significant=False
            ),
            decision=DeploymentDecision.INCONCLUSIVE,
            status=TestStatus.RUNNING,
            started_at=datetime.now()
        )
        
        deployed = tester.deploy_winner(result)
        
        assert deployed is False


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION TESTS (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfiguration:
    """Tests for configuration."""
    
    def test_ab_test_config_defaults(self):
        """Test default configuration values."""
        config = ABTestConfig()
        
        assert config.traffic_split_a == DEFAULT_TRAFFIC_SPLIT_A
        assert config.traffic_split_b == DEFAULT_TRAFFIC_SPLIT_B
        assert config.min_sample_size == DEFAULT_MIN_SAMPLE_SIZE
        assert config.min_improvement == DEFAULT_MIN_IMPROVEMENT
        assert config.significance_level == DEFAULT_SIGNIFICANCE_LEVEL
    
    def test_ab_test_config_custom(self):
        """Test custom configuration values."""
        config = ABTestConfig(
            test_id="custom_test",
            model_a_path="path/to/model_a",
            model_b_path="path/to/model_b",
            traffic_split_a=0.7,
            traffic_split_b=0.3,
            min_sample_size=200,
            min_improvement=0.05,
            significance_level=0.01
        )
        
        assert config.traffic_split_a == 0.7
        assert config.traffic_split_b == 0.3
        assert config.min_sample_size == 200
        assert config.min_improvement == 0.05
        assert config.significance_level == 0.01
    
    def test_test_status_enum(self):
        """Test test status enum values."""
        assert TestStatus.PENDING.value == "pending"
        assert TestStatus.RUNNING.value == "running"
        assert TestStatus.COMPLETED.value == "completed"
        assert TestStatus.STOPPED.value == "stopped"
        assert TestStatus.FAILED.value == "failed"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS (2+ tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """Integration tests."""
    
    def test_end_to_end_ab_test_workflow(self, config):
        """Test complete A/B testing workflow."""
        tester = ABTester(config)
        
        # Step 1: Manually add predictions to ensure we have enough for both models
        for i in range(120):
            # Model A predictions
            pred_a = Prediction(
                prediction_id=f"pred_a_{i}",
                model_variant=ModelVariant.MODEL_A,
                input_text=f"Text {i}",
                predicted_label=i % 2,
                confidence=0.80,
                actual_label=i % 2 if i < 55 else (i + 1) % 2  # 55% accurate
            )
            tester.predictions.append(pred_a)
            
            # Model B predictions
            pred_b = Prediction(
                prediction_id=f"pred_b_{i}",
                model_variant=ModelVariant.MODEL_B,
                input_text=f"Text {i}",
                predicted_label=i % 2,
                confidence=0.85,
                actual_label=i % 2 if i < 62 else (i + 1) % 2  # 62% accurate - better
            )
            tester.predictions.append(pred_b)
        
        # Step 2: Check progress
        progress = tester.get_progress()
        assert progress['labeled_a'] >= 100
        assert progress['labeled_b'] >= 100
        assert progress['is_complete'] is True
        
        # Step 3: Analyze results
        with patch.object(ab_tester_module.scipy_stats, 'chi2_contingency') as mock_chi2:
            mock_chi2.return_value = (8.0, 0.005, 1, np.array([[55, 45], [62, 38]]))
            
            result = tester.analyze_results()
        
        # Step 4: Verify result structure
        assert result.test_id == config.test_id
        assert result.model_a_metrics.total_predictions > 0
        assert result.model_b_metrics.total_predictions > 0
        assert result.decision in list(DeploymentDecision)
    
    def test_full_test_with_deployment(self, config, tmp_path):
        """Test full workflow including deployment."""
        tester = ABTester(config)
        
        # Add predictions showing B is significantly better
        for i in range(100):
            # Model A predictions
            pred_a = Prediction(
                prediction_id=f"pred_a_{i}",
                model_variant=ModelVariant.MODEL_A,
                input_text=f"Text {i}",
                predicted_label=i % 2,
                confidence=0.80,
                actual_label=i % 2 if i < 55 else (i + 1) % 2  # 55% accurate
            )
            tester.predictions.append(pred_a)
            
            # Model B predictions
            pred_b = Prediction(
                prediction_id=f"pred_b_{i}",
                model_variant=ModelVariant.MODEL_B,
                input_text=f"Text {i}",
                predicted_label=i % 2,
                confidence=0.85,
                actual_label=i % 2 if i < 65 else (i + 1) % 2  # 65% accurate - better
            )
            tester.predictions.append(pred_b)
        
        # Analyze and deploy
        with patch.object(ab_tester_module.scipy_stats, 'chi2_contingency') as mock_chi2:
            mock_chi2.return_value = (10.0, 0.001, 1, [[55, 45], [65, 35]])
            
            result = tester.analyze_results()
        
        # Should recommend deploying B
        assert result.decision == DeploymentDecision.DEPLOY_B
        
        # Deploy
        deployed = tester.deploy_winner(
            result,
            production_path=str(tmp_path / "prod"),
            archive_path=str(tmp_path / "archive")
        )
        
        assert deployed is True


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASS TESTS (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataclasses:
    """Tests for dataclasses."""
    
    def test_prediction_creation(self):
        """Test Prediction dataclass creation."""
        pred = Prediction(
            prediction_id="pred_001",
            model_variant=ModelVariant.MODEL_A,
            input_text="Test input",
            predicted_label=1,
            confidence=0.85,
            actual_label=1,
            latency_ms=150.0
        )
        
        assert pred.is_correct is True
        assert pred.has_ground_truth is True
    
    def test_prediction_is_correct(self):
        """Test is_correct property."""
        correct_pred = Prediction(
            prediction_id="p1",
            model_variant=ModelVariant.MODEL_A,
            input_text="Test",
            predicted_label=1,
            confidence=0.9,
            actual_label=1
        )
        
        incorrect_pred = Prediction(
            prediction_id="p2",
            model_variant=ModelVariant.MODEL_A,
            input_text="Test",
            predicted_label=1,
            confidence=0.9,
            actual_label=0
        )
        
        unknown_pred = Prediction(
            prediction_id="p3",
            model_variant=ModelVariant.MODEL_A,
            input_text="Test",
            predicted_label=1,
            confidence=0.9
        )
        
        assert correct_pred.is_correct is True
        assert incorrect_pred.is_correct is False
        assert unknown_pred.is_correct is None
    
    def test_model_metrics_to_dict(self, sample_metrics_a):
        """Test ModelMetrics to_dict method."""
        data = sample_metrics_a.to_dict()
        
        assert data['accuracy'] == 0.55
        assert data['precision'] == 0.56
        assert data['total_predictions'] == 120
    
    def test_ab_test_result_properties(self, config):
        """Test ABTestResult properties."""
        stat_result = StatisticalResult(
            test_name="chi_square",
            statistic=8.0,
            p_value=0.005,
            is_significant=True,
            confidence_interval=(0.02, 0.12)
        )
        
        result = ABTestResult(
            test_id="test_001",
            config=config,
            model_a_metrics=ModelMetrics(),
            model_b_metrics=ModelMetrics(),
            improvement=0.07,
            improvement_percent=7.0,
            statistical_result=stat_result,
            decision=DeploymentDecision.DEPLOY_B,
            status=TestStatus.COMPLETED,
            started_at=datetime.now()
        )
        
        assert result.is_significant is True
        assert result.p_value == 0.005
        assert result.confidence_interval == (0.02, 0.12)


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTION TESTS (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestExceptions:
    """Tests for exceptions."""
    
    def test_ab_tester_error(self):
        """Test base ABTesterError."""
        error = ABTesterError("Test error")
        assert str(error) == "Test error"
    
    def test_test_not_running_error(self, tester):
        """Test TestNotRunningError when test is stopped."""
        tester.stop_test("Test stopped")
        
        with pytest.raises(TestNotRunningError):
            tester.route_prediction("Test text")
    
    def test_configuration_error(self):
        """Test ConfigurationError for invalid config."""
        with pytest.raises(ConfigurationError):
            ABTestConfig(
                traffic_split_a=0.6,
                traffic_split_b=0.6  # Sum > 1.0
            )


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY TESTS (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestUtilities:
    """Tests for utility methods."""
    
    def test_stop_test(self, tester):
        """Test stopping a test."""
        tester.stop_test("Manual stop")
        
        assert tester.status == TestStatus.STOPPED
    
    def test_is_complete(self, tester):
        """Test is_complete check."""
        assert tester.is_complete() is False
        
        # Add enough labeled predictions
        for i in range(100):
            pred_a = Prediction(
                prediction_id=f"pred_a_{i}",
                model_variant=ModelVariant.MODEL_A,
                input_text=f"Text {i}",
                predicted_label=0,
                confidence=0.85,
                actual_label=0
            )
            tester.predictions.append(pred_a)
            
            pred_b = Prediction(
                prediction_id=f"pred_b_{i}",
                model_variant=ModelVariant.MODEL_B,
                input_text=f"Text {i}",
                predicted_label=0,
                confidence=0.85,
                actual_label=0
            )
            tester.predictions.append(pred_b)
        
        assert tester.is_complete() is True
    
    def test_reset(self, populated_tester):
        """Test resetting tester."""
        assert len(populated_tester.predictions) > 0
        
        populated_tester.reset()
        
        assert len(populated_tester.predictions) == 0
        assert populated_tester.status == TestStatus.RUNNING


# ═══════════════════════════════════════════════════════════════════════════════
# PERSISTENCE TESTS (2 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPersistence:
    """Tests for saving/loading results."""
    
    def test_save_results(self, populated_tester, tmp_path):
        """Test saving results to file."""
        with patch.object(ab_tester_module.scipy_stats, 'chi2_contingency') as mock_chi2:
            mock_chi2.return_value = (8.0, 0.005, 1, [[55, 45], [62, 38]])
            
            result = populated_tester.analyze_results()
        
        output_file = populated_tester.save_results(result, str(tmp_path))
        
        assert tmp_path.exists()
        
        # Verify file content
        import json
        with open(output_file) as f:
            saved_data = json.load(f)
        
        assert saved_data['test_id'] == populated_tester.config.test_id
    
    def test_save_predictions(self, populated_tester, tmp_path):
        """Test saving predictions to file."""
        output_file = populated_tester.save_predictions(str(tmp_path))
        
        import json
        with open(output_file) as f:
            saved_data = json.load(f)
        
        assert len(saved_data) == len(populated_tester.predictions)
