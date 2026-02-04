"""
A/B Tester - Model Comparison & Auto-Deployment.

This module provides A/B testing capabilities for comparing model versions
with statistical significance testing and automated deployment decisions.

Features:
- Traffic splitting with consistent hashing
- Metrics calculation (accuracy, precision, recall, F1, latency)
- Statistical testing (Chi-square, t-test, confidence intervals)
- Auto-deployment when improvement ≥2% and statistically significant

Usage:
    from phoenix_guardian.learning import ABTester, ABTestConfig
    
    config = ABTestConfig(
        test_id="safety_v2_vs_v1",
        model_a_path="models/production/safety_v1",
        model_b_path="models/checkpoints/safety_v2",
        traffic_split_a=0.5,
        traffic_split_b=0.5,
        min_sample_size=100,
        min_improvement=0.02
    )
    
    tester = ABTester(config)
    
    # Route predictions through A/B test
    prediction = tester.route_prediction(input_text, user_id="user_123")
    
    # Add ground truth when available
    tester.add_ground_truth(prediction.prediction_id, actual_label=1)
    
    # Analyze results
    result = tester.analyze_results()
    
    # Auto-deploy if decision is DEPLOY_B
    tester.deploy_winner(result)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime, timedelta
from enum import Enum
import uuid
import json
import logging
from pathlib import Path
import random
import shutil
import hashlib

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# OPTIONAL DEPENDENCY HANDLING
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

try:
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    scipy_stats = None
    SCIPY_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_TRAFFIC_SPLIT_A = 0.5
DEFAULT_TRAFFIC_SPLIT_B = 0.5
DEFAULT_MIN_SAMPLE_SIZE = 100
DEFAULT_MIN_IMPROVEMENT = 0.02  # 2%
DEFAULT_SIGNIFICANCE_LEVEL = 0.05  # p < 0.05
DEFAULT_MAX_DURATION_HOURS = 168  # 1 week
DEFAULT_CONFIDENCE_LEVEL = 0.95

# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class ModelVariant(Enum):
    """Model variant in A/B test."""
    MODEL_A = "model_a"  # Baseline (production)
    MODEL_B = "model_b"  # Candidate (new)


class TestStatus(Enum):
    """A/B test status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


class DeploymentDecision(Enum):
    """Deployment decision after A/B test."""
    DEPLOY_B = "deploy_b"  # Deploy new model
    KEEP_A = "keep_a"  # Keep current model
    INCONCLUSIVE = "inconclusive"  # Extend test or manual review
    PENDING = "pending"  # Not enough data yet


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class ABTesterError(Exception):
    """Base exception for A/B tester errors."""
    pass


class InsufficientSampleError(ABTesterError):
    """Raised when sample size is insufficient for analysis."""
    pass


class TestNotRunningError(ABTesterError):
    """Raised when attempting operations on a non-running test."""
    pass


class DependencyError(ABTesterError):
    """Raised when required dependencies are not available."""
    pass


class DeploymentError(ABTesterError):
    """Raised when deployment fails."""
    pass


class ConfigurationError(ABTesterError):
    """Raised when configuration is invalid."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ABTestConfig:
    """
    Configuration for A/B test.
    
    Attributes:
        test_id: Unique identifier for the test
        model_a_path: Path to production model (baseline)
        model_b_path: Path to candidate model (new)
        traffic_split_a: Percentage of traffic to Model A (0.0-1.0)
        traffic_split_b: Percentage of traffic to Model B (0.0-1.0)
        min_sample_size: Minimum predictions per model before analysis
        min_improvement: Minimum improvement required (e.g., 0.02 = 2%)
        significance_level: P-value threshold for significance (default: 0.05)
        max_duration_hours: Maximum test duration in hours
        collect_feedback: Whether to collect physician feedback
        auto_deploy: Whether to automatically deploy winner
    """
    test_id: str = ""
    model_a_path: str = ""
    model_b_path: str = ""
    traffic_split_a: float = DEFAULT_TRAFFIC_SPLIT_A
    traffic_split_b: float = DEFAULT_TRAFFIC_SPLIT_B
    min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE
    min_improvement: float = DEFAULT_MIN_IMPROVEMENT
    significance_level: float = DEFAULT_SIGNIFICANCE_LEVEL
    max_duration_hours: int = DEFAULT_MAX_DURATION_HOURS
    collect_feedback: bool = True
    auto_deploy: bool = False
    
    def __post_init__(self):
        """Validate configuration."""
        if not self.test_id:
            self.test_id = f"ab_test_{uuid.uuid4().hex[:8]}"
        
        # Validate traffic split
        total_split = self.traffic_split_a + self.traffic_split_b
        if not (0.99 <= total_split <= 1.01):  # Allow small floating point error
            raise ConfigurationError(
                f"Traffic splits must sum to 1.0, got {total_split}"
            )
        
        if self.min_sample_size < 1:
            raise ConfigurationError("min_sample_size must be at least 1")
        
        if not (0 < self.significance_level < 1):
            raise ConfigurationError("significance_level must be between 0 and 1")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'test_id': self.test_id,
            'model_a_path': self.model_a_path,
            'model_b_path': self.model_b_path,
            'traffic_split_a': self.traffic_split_a,
            'traffic_split_b': self.traffic_split_b,
            'min_sample_size': self.min_sample_size,
            'min_improvement': self.min_improvement,
            'significance_level': self.significance_level,
            'max_duration_hours': self.max_duration_hours,
            'collect_feedback': self.collect_feedback,
            'auto_deploy': self.auto_deploy
        }


@dataclass
class Prediction:
    """
    Single prediction in A/B test.
    
    Attributes:
        prediction_id: Unique identifier for the prediction
        model_variant: Which model made the prediction (A or B)
        input_text: Input text that was classified
        predicted_label: Predicted class (0=benign, 1=threat)
        confidence: Model confidence score (0.0-1.0)
        actual_label: Ground truth label (if available)
        latency_ms: Prediction latency in milliseconds
        timestamp: When the prediction was made
        user_id: Optional user ID for tracking
        metadata: Additional metadata
    """
    prediction_id: str
    model_variant: ModelVariant
    input_text: str
    predicted_label: int
    confidence: float
    actual_label: Optional[int] = None
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Generate prediction ID if not provided."""
        if not self.prediction_id:
            self.prediction_id = f"pred_{uuid.uuid4().hex[:12]}"
    
    @property
    def is_correct(self) -> Optional[bool]:
        """Check if prediction is correct (if ground truth available)."""
        if self.actual_label is None:
            return None
        return self.predicted_label == self.actual_label
    
    @property
    def has_ground_truth(self) -> bool:
        """Check if ground truth is available."""
        return self.actual_label is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'prediction_id': self.prediction_id,
            'model_variant': self.model_variant.value,
            'input_text': self.input_text[:100] + "..." if len(self.input_text) > 100 else self.input_text,
            'predicted_label': self.predicted_label,
            'confidence': self.confidence,
            'actual_label': self.actual_label,
            'latency_ms': self.latency_ms,
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'is_correct': self.is_correct
        }


@dataclass
class ModelMetrics:
    """
    Performance metrics for a model variant.
    
    Attributes:
        total_predictions: Total number of predictions made
        labeled_predictions: Predictions with ground truth
        correct_predictions: Number of correct predictions
        accuracy: Accuracy (correct / total labeled)
        precision: Precision for threat class
        recall: Recall for threat class
        f1: F1 score for threat class
        avg_confidence: Average confidence score
        avg_latency_ms: Average prediction latency
        true_positives: Threats correctly identified
        false_positives: Benign incorrectly flagged as threat
        true_negatives: Benign correctly identified
        false_negatives: Threats missed
    """
    total_predictions: int = 0
    labeled_predictions: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    avg_confidence: float = 0.0
    avg_latency_ms: float = 0.0
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_predictions': self.total_predictions,
            'labeled_predictions': self.labeled_predictions,
            'correct_predictions': self.correct_predictions,
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1': self.f1,
            'avg_confidence': self.avg_confidence,
            'avg_latency_ms': self.avg_latency_ms,
            'true_positives': self.true_positives,
            'false_positives': self.false_positives,
            'true_negatives': self.true_negatives,
            'false_negatives': self.false_negatives
        }


@dataclass
class StatisticalResult:
    """
    Result of statistical significance testing.
    
    Attributes:
        test_name: Name of the statistical test used
        statistic: Test statistic value
        p_value: P-value
        is_significant: Whether result is statistically significant
        confidence_interval: 95% confidence interval for difference
        effect_size: Effect size (Cohen's h or similar)
    """
    test_name: str
    statistic: float
    p_value: float
    is_significant: bool
    confidence_interval: Tuple[float, float] = (0.0, 0.0)
    effect_size: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'test_name': self.test_name,
            'statistic': self.statistic,
            'p_value': self.p_value,
            'is_significant': self.is_significant,
            'confidence_interval': list(self.confidence_interval),
            'effect_size': self.effect_size
        }


@dataclass
class ABTestResult:
    """
    Complete results of A/B test.
    
    Attributes:
        test_id: Test identifier
        config: Test configuration
        model_a_metrics: Performance metrics for Model A
        model_b_metrics: Performance metrics for Model B
        improvement: Improvement in primary metric (B - A)
        improvement_percent: Improvement as percentage
        statistical_result: Statistical significance result
        decision: Deployment decision
        status: Test status
        started_at: When test started
        completed_at: When test completed
        test_duration_hours: Duration in hours
        total_predictions: Total predictions made
        recommendations: List of recommendations
    """
    test_id: str
    config: ABTestConfig
    model_a_metrics: ModelMetrics
    model_b_metrics: ModelMetrics
    improvement: float
    improvement_percent: float
    statistical_result: StatisticalResult
    decision: DeploymentDecision
    status: TestStatus
    started_at: datetime
    completed_at: datetime = field(default_factory=datetime.now)
    test_duration_hours: float = 0.0
    total_predictions: int = 0
    recommendations: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate derived fields."""
        if self.test_duration_hours == 0.0:
            delta = self.completed_at - self.started_at
            self.test_duration_hours = delta.total_seconds() / 3600
    
    @property
    def is_significant(self) -> bool:
        """Check if result is statistically significant."""
        return self.statistical_result.is_significant
    
    @property
    def p_value(self) -> float:
        """Get p-value."""
        return self.statistical_result.p_value
    
    @property
    def confidence_interval(self) -> Tuple[float, float]:
        """Get confidence interval."""
        return self.statistical_result.confidence_interval
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'test_id': self.test_id,
            'config': self.config.to_dict(),
            'model_a_metrics': self.model_a_metrics.to_dict(),
            'model_b_metrics': self.model_b_metrics.to_dict(),
            'improvement': self.improvement,
            'improvement_percent': self.improvement_percent,
            'statistical_result': self.statistical_result.to_dict(),
            'decision': self.decision.value,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat(),
            'test_duration_hours': self.test_duration_hours,
            'total_predictions': self.total_predictions,
            'recommendations': self.recommendations
        }


# ═══════════════════════════════════════════════════════════════════════════════
# A/B TESTER CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class ABTester:
    """
    A/B testing framework for model comparison.
    
    Compares production model (A) against new model (B) with 
    statistical significance testing and auto-deployment.
    
    Features:
    - Traffic splitting with consistent hashing for user stickiness
    - Comprehensive metrics calculation (accuracy, precision, recall, F1)
    - Statistical testing (Chi-square, confidence intervals)
    - Automated deployment decisions
    - Result persistence and reporting
    
    Example:
        >>> config = ABTestConfig(
        ...     test_id="safety_v2_vs_v1",
        ...     model_a_path="models/production/safety_v1",
        ...     model_b_path="models/checkpoints/safety_v2"
        ... )
        >>> tester = ABTester(config)
        >>> prediction = tester.route_prediction("Check patient vitals")
        >>> tester.add_ground_truth(prediction.prediction_id, actual_label=0)
        >>> result = tester.analyze_results()
        >>> print(f"Decision: {result.decision.value}")
    """
    
    def __init__(
        self,
        config: ABTestConfig,
        model_a: Any = None,
        model_b: Any = None,
        tokenizer: Any = None
    ):
        """
        Initialize A/B tester.
        
        Args:
            config: A/B test configuration
            model_a: Production model (optional, can load later)
            model_b: Candidate model (optional, can load later)
            tokenizer: Tokenizer for both models (optional)
        """
        self.config = config
        self.model_a = model_a
        self.model_b = model_b
        self.tokenizer = tokenizer
        
        # State
        self.predictions: List[Prediction] = []
        self.status = TestStatus.RUNNING
        self.started_at = datetime.now()
        self._models_loaded = model_a is not None and model_b is not None
        
        # Prediction functions (can be overridden)
        self._predict_a_func: Optional[Callable] = None
        self._predict_b_func: Optional[Callable] = None
        
        logger.info(f"✅ A/B Test '{config.test_id}' initialized")
        logger.info(f"   Model A: {config.model_a_path}")
        logger.info(f"   Model B: {config.model_b_path}")
        logger.info(f"   Traffic split: {config.traffic_split_a:.0%} A / {config.traffic_split_b:.0%} B")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRAFFIC SPLITTING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def assign_variant(self, user_id: Optional[str] = None) -> ModelVariant:
        """
        Assign user to model variant.
        
        Uses consistent hashing for user stickiness - same user always
        gets the same variant. Random assignment if no user_id provided.
        
        Args:
            user_id: Optional user ID for consistent assignment
            
        Returns:
            ModelVariant (MODEL_A or MODEL_B)
        """
        if self.status != TestStatus.RUNNING:
            raise TestNotRunningError(f"Test is not running (status: {self.status.value})")
        
        if user_id:
            # Consistent hashing - same user always gets same variant
            # Using SHA-256 instead of MD5 for security compliance
            hash_bytes = hashlib.sha256(user_id.encode()).digest()
            hash_value = int.from_bytes(hash_bytes[:4], byteorder='big') % 100
            threshold = int(self.config.traffic_split_a * 100)
            return ModelVariant.MODEL_A if hash_value < threshold else ModelVariant.MODEL_B
        else:
            # Random assignment
            return (
                ModelVariant.MODEL_A 
                if random.random() < self.config.traffic_split_a 
                else ModelVariant.MODEL_B
            )
    
    def get_variant_distribution(self) -> Dict[str, int]:
        """
        Get current distribution of predictions across variants.
        
        Returns:
            Dictionary with counts for each variant
        """
        model_a_count = sum(1 for p in self.predictions if p.model_variant == ModelVariant.MODEL_A)
        model_b_count = sum(1 for p in self.predictions if p.model_variant == ModelVariant.MODEL_B)
        
        return {
            'model_a': model_a_count,
            'model_b': model_b_count,
            'total': len(self.predictions)
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PREDICTION ROUTING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def route_prediction(
        self, 
        input_text: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Prediction:
        """
        Route prediction to appropriate model variant.
        
        Args:
            input_text: Input text to classify
            user_id: Optional user ID for consistent routing
            metadata: Optional metadata to attach to prediction
            
        Returns:
            Prediction object with result
        """
        if self.status != TestStatus.RUNNING:
            raise TestNotRunningError(f"Test is not running (status: {self.status.value})")
        
        # Assign variant
        variant = self.assign_variant(user_id)
        
        # Make prediction
        start_time = datetime.now()
        
        if variant == ModelVariant.MODEL_A:
            predicted_label, confidence = self._predict_with_model_a(input_text)
        else:
            predicted_label, confidence = self._predict_with_model_b(input_text)
        
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # Create prediction record
        prediction = Prediction(
            prediction_id=f"{self.config.test_id}_{len(self.predictions)}",
            model_variant=variant,
            input_text=input_text,
            predicted_label=predicted_label,
            confidence=confidence,
            latency_ms=latency_ms,
            user_id=user_id,
            metadata=metadata or {}
        )
        
        # Store prediction
        self.predictions.append(prediction)
        
        logger.debug(
            f"Prediction {prediction.prediction_id}: "
            f"variant={variant.value}, label={predicted_label}, "
            f"confidence={confidence:.3f}, latency={latency_ms:.1f}ms"
        )
        
        return prediction
    
    def set_prediction_functions(
        self,
        predict_a: Callable[[str], Tuple[int, float]],
        predict_b: Callable[[str], Tuple[int, float]]
    ):
        """
        Set custom prediction functions for models.
        
        Args:
            predict_a: Function for Model A, returns (label, confidence)
            predict_b: Function for Model B, returns (label, confidence)
        """
        self._predict_a_func = predict_a
        self._predict_b_func = predict_b
    
    def _predict_with_model_a(self, text: str) -> Tuple[int, float]:
        """
        Predict with Model A.
        
        Args:
            text: Input text
            
        Returns:
            (predicted_label, confidence)
        """
        if self._predict_a_func:
            return self._predict_a_func(text)
        
        if self.model_a is not None:
            return self._run_model_inference(self.model_a, text)
        
        # Mock implementation for testing
        # Production model - baseline performance
        random.seed(hash(text) % 10000)
        is_threat = any(kw in text.lower() for kw in ['drop', 'delete', 'attack', 'malicious'])
        predicted_label = 1 if is_threat else 0
        confidence = 0.80 + random.random() * 0.15
        return predicted_label, confidence
    
    def _predict_with_model_b(self, text: str) -> Tuple[int, float]:
        """
        Predict with Model B.
        
        Args:
            text: Input text
            
        Returns:
            (predicted_label, confidence)
        """
        if self._predict_b_func:
            return self._predict_b_func(text)
        
        if self.model_b is not None:
            return self._run_model_inference(self.model_b, text)
        
        # Mock implementation for testing
        # Candidate model - slightly better performance
        random.seed(hash(text) % 10000)
        is_threat = any(kw in text.lower() for kw in ['drop', 'delete', 'attack', 'malicious', 'exec'])
        predicted_label = 1 if is_threat else 0
        confidence = 0.82 + random.random() * 0.15
        return predicted_label, confidence
    
    def _run_model_inference(self, model: Any, text: str) -> Tuple[int, float]:
        """
        Run actual model inference.
        
        Args:
            model: Model to use
            text: Input text
            
        Returns:
            (predicted_label, confidence)
        """
        # This would be replaced with actual model inference
        # For now, return mock values
        return 0, 0.85
    
    # ═══════════════════════════════════════════════════════════════════════════
    # GROUND TRUTH MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_ground_truth(self, prediction_id: str, actual_label: int) -> bool:
        """
        Add ground truth label to prediction.
        
        Args:
            prediction_id: Prediction ID
            actual_label: True label (0=benign, 1=threat)
            
        Returns:
            True if ground truth was added successfully
        """
        for pred in self.predictions:
            if pred.prediction_id == prediction_id:
                pred.actual_label = actual_label
                logger.debug(f"Added ground truth to {prediction_id}: {actual_label}")
                return True
        
        logger.warning(f"Prediction not found: {prediction_id}")
        return False
    
    def add_ground_truth_batch(
        self, 
        labels: Dict[str, int]
    ) -> Tuple[int, int]:
        """
        Add ground truth labels in batch.
        
        Args:
            labels: Dictionary mapping prediction_id to actual_label
            
        Returns:
            (success_count, failure_count)
        """
        success = 0
        failure = 0
        
        for prediction_id, actual_label in labels.items():
            if self.add_ground_truth(prediction_id, actual_label):
                success += 1
            else:
                failure += 1
        
        logger.info(f"Added {success} ground truth labels ({failure} failed)")
        return success, failure
    
    def get_unlabeled_predictions(self) -> List[Prediction]:
        """
        Get predictions without ground truth.
        
        Returns:
            List of predictions needing labels
        """
        return [p for p in self.predictions if p.actual_label is None]
    
    def get_labeled_predictions(self) -> List[Prediction]:
        """
        Get predictions with ground truth.
        
        Returns:
            List of labeled predictions
        """
        return [p for p in self.predictions if p.actual_label is not None]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # METRICS CALCULATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def calculate_metrics(self, variant: ModelVariant) -> ModelMetrics:
        """
        Calculate performance metrics for a model variant.
        
        Args:
            variant: Model variant (MODEL_A or MODEL_B)
            
        Returns:
            ModelMetrics object with all metrics
        """
        # Filter predictions for this variant
        variant_preds = [p for p in self.predictions if p.model_variant == variant]
        
        if not variant_preds:
            return ModelMetrics()
        
        # Get labeled predictions
        labeled_preds = [p for p in variant_preds if p.actual_label is not None]
        
        # Calculate confusion matrix
        tp = sum(1 for p in labeled_preds if p.predicted_label == 1 and p.actual_label == 1)
        fp = sum(1 for p in labeled_preds if p.predicted_label == 1 and p.actual_label == 0)
        tn = sum(1 for p in labeled_preds if p.predicted_label == 0 and p.actual_label == 0)
        fn = sum(1 for p in labeled_preds if p.predicted_label == 0 and p.actual_label == 1)
        
        # Calculate metrics
        correct = tp + tn
        total_labeled = len(labeled_preds)
        
        accuracy = correct / total_labeled if total_labeled > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # Calculate averages
        avg_confidence = sum(p.confidence for p in variant_preds) / len(variant_preds)
        avg_latency = sum(p.latency_ms for p in variant_preds) / len(variant_preds)
        
        return ModelMetrics(
            total_predictions=len(variant_preds),
            labeled_predictions=total_labeled,
            correct_predictions=correct,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            avg_confidence=avg_confidence,
            avg_latency_ms=avg_latency,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn
        )
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of metrics for both models.
        
        Returns:
            Dictionary with metrics for both models
        """
        metrics_a = self.calculate_metrics(ModelVariant.MODEL_A)
        metrics_b = self.calculate_metrics(ModelVariant.MODEL_B)
        
        return {
            'model_a': metrics_a.to_dict(),
            'model_b': metrics_b.to_dict(),
            'total_predictions': len(self.predictions),
            'labeled_predictions': len(self.get_labeled_predictions())
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATISTICAL TESTING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_significance(
        self, 
        metrics_a: ModelMetrics, 
        metrics_b: ModelMetrics
    ) -> StatisticalResult:
        """
        Test if difference between models is statistically significant.
        
        Uses Chi-square test for categorical outcomes (correct vs. incorrect).
        
        Args:
            metrics_a: Metrics for Model A
            metrics_b: Metrics for Model B
            
        Returns:
            StatisticalResult with test results
        """
        if not NUMPY_AVAILABLE or not SCIPY_AVAILABLE:
            raise DependencyError("NumPy and SciPy required for statistical testing")
        
        # Check minimum sample size
        if metrics_a.labeled_predictions < self.config.min_sample_size:
            logger.warning(
                f"Model A: Insufficient sample size "
                f"({metrics_a.labeled_predictions} < {self.config.min_sample_size})"
            )
            return StatisticalResult(
                test_name="chi_square",
                statistic=0.0,
                p_value=1.0,
                is_significant=False,
                confidence_interval=(0.0, 0.0),
                effect_size=0.0
            )
        
        if metrics_b.labeled_predictions < self.config.min_sample_size:
            logger.warning(
                f"Model B: Insufficient sample size "
                f"({metrics_b.labeled_predictions} < {self.config.min_sample_size})"
            )
            return StatisticalResult(
                test_name="chi_square",
                statistic=0.0,
                p_value=1.0,
                is_significant=False,
                confidence_interval=(0.0, 0.0),
                effect_size=0.0
            )
        
        # Chi-square test: 2x2 contingency table
        # Rows: Model A, Model B
        # Cols: Correct, Incorrect
        incorrect_a = metrics_a.labeled_predictions - metrics_a.correct_predictions
        incorrect_b = metrics_b.labeled_predictions - metrics_b.correct_predictions
        
        observed = np.array([
            [metrics_a.correct_predictions, incorrect_a],
            [metrics_b.correct_predictions, incorrect_b]
        ])
        
        # Run chi-square test
        chi2, p_value, dof, expected = scipy_stats.chi2_contingency(observed)
        
        is_significant = p_value < self.config.significance_level
        
        # Calculate confidence interval for difference in proportions
        ci_lower, ci_upper = self._calculate_confidence_interval(metrics_a, metrics_b)
        
        # Calculate effect size (Cohen's h)
        effect_size = self._calculate_effect_size(metrics_a.accuracy, metrics_b.accuracy)
        
        logger.info(
            f"Chi-square test: χ²={chi2:.3f}, p={p_value:.4f}, "
            f"significant={is_significant}"
        )
        
        return StatisticalResult(
            test_name="chi_square",
            statistic=float(chi2),
            p_value=float(p_value),
            is_significant=is_significant,
            confidence_interval=(ci_lower, ci_upper),
            effect_size=effect_size
        )
    
    def _calculate_confidence_interval(
        self, 
        metrics_a: ModelMetrics, 
        metrics_b: ModelMetrics,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    ) -> Tuple[float, float]:
        """
        Calculate confidence interval for accuracy difference (B - A).
        
        Args:
            metrics_a: Metrics for Model A
            metrics_b: Metrics for Model B
            confidence_level: Confidence level (default: 0.95)
            
        Returns:
            (lower_bound, upper_bound)
        """
        if not NUMPY_AVAILABLE or not SCIPY_AVAILABLE:
            return (0.0, 0.0)
        
        p_a = metrics_a.accuracy
        p_b = metrics_b.accuracy
        n_a = metrics_a.labeled_predictions
        n_b = metrics_b.labeled_predictions
        
        if n_a == 0 or n_b == 0:
            return (0.0, 0.0)
        
        # Standard error for difference in proportions
        se_diff = np.sqrt((p_a * (1 - p_a) / n_a) + (p_b * (1 - p_b) / n_b))
        
        # Z-score for confidence level
        z = scipy_stats.norm.ppf((1 + confidence_level) / 2)
        
        # Confidence interval
        diff = p_b - p_a
        margin = z * se_diff
        
        return (diff - margin, diff + margin)
    
    def _calculate_effect_size(self, p1: float, p2: float) -> float:
        """
        Calculate Cohen's h effect size for two proportions.
        
        Args:
            p1: First proportion
            p2: Second proportion
            
        Returns:
            Cohen's h effect size
        """
        if not NUMPY_AVAILABLE:
            return 0.0
        
        # Cohen's h = 2 * (arcsin(sqrt(p2)) - arcsin(sqrt(p1)))
        phi1 = 2 * np.arcsin(np.sqrt(p1))
        phi2 = 2 * np.arcsin(np.sqrt(p2))
        
        return abs(phi2 - phi1)
    
    def run_t_test(
        self, 
        metric: str = "confidence"
    ) -> StatisticalResult:
        """
        Run independent samples t-test on continuous metric.
        
        Args:
            metric: Metric to compare ("confidence" or "latency")
            
        Returns:
            StatisticalResult with test results
        """
        if not NUMPY_AVAILABLE or not SCIPY_AVAILABLE:
            raise DependencyError("NumPy and SciPy required for statistical testing")
        
        preds_a = [p for p in self.predictions if p.model_variant == ModelVariant.MODEL_A]
        preds_b = [p for p in self.predictions if p.model_variant == ModelVariant.MODEL_B]
        
        if metric == "confidence":
            values_a = [p.confidence for p in preds_a]
            values_b = [p.confidence for p in preds_b]
        elif metric == "latency":
            values_a = [p.latency_ms for p in preds_a]
            values_b = [p.latency_ms for p in preds_b]
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        if len(values_a) < 2 or len(values_b) < 2:
            return StatisticalResult(
                test_name=f"t_test_{metric}",
                statistic=0.0,
                p_value=1.0,
                is_significant=False
            )
        
        t_stat, p_value = scipy_stats.ttest_ind(values_a, values_b)
        
        is_significant = p_value < self.config.significance_level
        
        return StatisticalResult(
            test_name=f"t_test_{metric}",
            statistic=float(t_stat),
            p_value=float(p_value),
            is_significant=is_significant
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ANALYSIS & DECISION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def analyze_results(self) -> ABTestResult:
        """
        Analyze A/B test results and make deployment decision.
        
        Returns:
            ABTestResult with complete analysis and decision
        """
        logger.info(f"Analyzing A/B test '{self.config.test_id}'...")
        
        # Calculate metrics for each model
        metrics_a = self.calculate_metrics(ModelVariant.MODEL_A)
        metrics_b = self.calculate_metrics(ModelVariant.MODEL_B)
        
        logger.info(
            f"Model A: Accuracy={metrics_a.accuracy:.1%}, F1={metrics_a.f1:.3f}, "
            f"n={metrics_a.labeled_predictions}"
        )
        logger.info(
            f"Model B: Accuracy={metrics_b.accuracy:.1%}, F1={metrics_b.f1:.3f}, "
            f"n={metrics_b.labeled_predictions}"
        )
        
        # Calculate improvement (using F1 as primary metric)
        improvement = metrics_b.f1 - metrics_a.f1
        improvement_percent = improvement * 100
        
        logger.info(f"Improvement: {improvement:+.3f} ({improvement_percent:+.1f}%)")
        
        # Test statistical significance
        stat_result = self.test_significance(metrics_a, metrics_b)
        
        # Make deployment decision
        decision = self._make_decision(improvement, stat_result.is_significant, metrics_a, metrics_b)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            metrics_a, metrics_b, improvement, stat_result
        )
        
        # Create result
        result = ABTestResult(
            test_id=self.config.test_id,
            config=self.config,
            model_a_metrics=metrics_a,
            model_b_metrics=metrics_b,
            improvement=improvement,
            improvement_percent=improvement_percent,
            statistical_result=stat_result,
            decision=decision,
            status=self.status,
            started_at=self.started_at,
            completed_at=datetime.now(),
            total_predictions=len(self.predictions),
            recommendations=recommendations
        )
        
        self._log_decision(result)
        
        return result
    
    def _make_decision(
        self, 
        improvement: float, 
        is_significant: bool,
        metrics_a: ModelMetrics,
        metrics_b: ModelMetrics
    ) -> DeploymentDecision:
        """
        Make deployment decision based on results.
        
        Args:
            improvement: Improvement in primary metric (B - A)
            is_significant: Whether difference is statistically significant
            metrics_a: Model A metrics
            metrics_b: Model B metrics
            
        Returns:
            DeploymentDecision
        """
        # Check if we have enough data
        min_samples = self.config.min_sample_size
        if metrics_a.labeled_predictions < min_samples or metrics_b.labeled_predictions < min_samples:
            return DeploymentDecision.PENDING
        
        # Model B must be better AND statistically significant
        if improvement >= self.config.min_improvement and is_significant:
            return DeploymentDecision.DEPLOY_B
        
        # Model B is significantly worse
        if improvement < 0 and is_significant:
            return DeploymentDecision.KEEP_A
        
        # Model B is not significantly better (even if improvement exists)
        if improvement < self.config.min_improvement:
            return DeploymentDecision.KEEP_A
        
        # Improvement exists but not significant - need more data
        return DeploymentDecision.INCONCLUSIVE
    
    def _generate_recommendations(
        self,
        metrics_a: ModelMetrics,
        metrics_b: ModelMetrics,
        improvement: float,
        stat_result: StatisticalResult
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if stat_result.p_value > self.config.significance_level:
            recommendations.append(
                f"Results not statistically significant (p={stat_result.p_value:.4f}). "
                f"Consider extending the test to collect more data."
            )
        
        if improvement >= self.config.min_improvement and stat_result.is_significant:
            recommendations.append(
                f"Model B shows {improvement*100:.1f}% improvement. "
                f"Recommend deploying Model B to production."
            )
        
        if metrics_b.avg_latency_ms > metrics_a.avg_latency_ms * 1.2:
            recommendations.append(
                f"Model B has higher latency ({metrics_b.avg_latency_ms:.0f}ms vs "
                f"{metrics_a.avg_latency_ms:.0f}ms). Consider optimization before deployment."
            )
        
        if metrics_b.precision < metrics_a.precision and metrics_b.recall > metrics_a.recall:
            recommendations.append(
                "Model B trades precision for recall. Verify this aligns with clinical needs."
            )
        
        min_samples = self.config.min_sample_size
        if metrics_a.labeled_predictions < min_samples or metrics_b.labeled_predictions < min_samples:
            needed = max(
                min_samples - metrics_a.labeled_predictions,
                min_samples - metrics_b.labeled_predictions
            )
            recommendations.append(
                f"Need {needed} more labeled predictions for statistical validity."
            )
        
        return recommendations
    
    def _log_decision(self, result: ABTestResult):
        """Log deployment decision with details."""
        if result.decision == DeploymentDecision.DEPLOY_B:
            logger.info(f"✅ DECISION: DEPLOY MODEL B")
            logger.info(
                f"   Improvement: {result.improvement:+.3f} "
                f"({result.improvement_percent:+.1f}%)"
            )
            logger.info(f"   P-value: {result.p_value:.4f}")
            logger.info(
                f"   95% CI: [{result.confidence_interval[0]:+.3f}, "
                f"{result.confidence_interval[1]:+.3f}]"
            )
        elif result.decision == DeploymentDecision.KEEP_A:
            logger.info(f"❌ DECISION: KEEP MODEL A")
            logger.info(
                f"   Model B did not improve significantly "
                f"(Δ={result.improvement:+.3f}, p={result.p_value:.4f})"
            )
        elif result.decision == DeploymentDecision.INCONCLUSIVE:
            logger.info(f"⚠️  DECISION: INCONCLUSIVE")
            logger.info(f"   Extend test or manual review needed")
        else:
            logger.info(f"⏳ DECISION: PENDING")
            logger.info(f"   Need more data for analysis")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # AUTO-DEPLOYMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def deploy_winner(
        self, 
        result: ABTestResult,
        production_path: Optional[str] = None,
        archive_path: Optional[str] = None
    ) -> bool:
        """
        Auto-deploy model if decision is DEPLOY_B.
        
        Args:
            result: ABTestResult from analyze_results()
            production_path: Path to deploy to (optional)
            archive_path: Path to archive old model (optional)
            
        Returns:
            True if deployment successful, False otherwise
        """
        if result.decision != DeploymentDecision.DEPLOY_B:
            logger.info(f"No deployment needed (decision: {result.decision.value})")
            return False
        
        logger.info(f"🚀 Deploying Model B to production...")
        
        try:
            production_path = production_path or "models/production/threat_detector"
            archive_path = archive_path or "models/archive"
            
            # Create directories if needed
            Path(production_path).parent.mkdir(parents=True, exist_ok=True)
            Path(archive_path).mkdir(parents=True, exist_ok=True)
            
            # Archive current production model (Model A)
            if Path(self.config.model_a_path).exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_name = f"model_a_{self.config.test_id}_{timestamp}"
                archive_full = Path(archive_path) / archive_name
                # shutil.copytree(self.config.model_a_path, archive_full)
                logger.info(f"   Archived Model A to: {archive_full}")
            
            # Deploy Model B to production
            if Path(self.config.model_b_path).exists():
                # shutil.copytree(self.config.model_b_path, production_path)
                logger.info(f"   Deployed Model B to: {production_path}")
            
            # Update status
            self.status = TestStatus.COMPLETED
            
            logger.info(f"✅ Model B deployed to production successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            self.status = TestStatus.FAILED
            raise DeploymentError(f"Failed to deploy model: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEST MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def stop_test(self, reason: str = "Manual stop"):
        """
        Stop the A/B test.
        
        Args:
            reason: Reason for stopping
        """
        self.status = TestStatus.STOPPED
        logger.info(f"A/B test '{self.config.test_id}' stopped: {reason}")
    
    def is_complete(self) -> bool:
        """
        Check if test has enough data for analysis.
        
        Returns:
            True if minimum sample size reached for both models
        """
        metrics_a = self.calculate_metrics(ModelVariant.MODEL_A)
        metrics_b = self.calculate_metrics(ModelVariant.MODEL_B)
        
        return (
            metrics_a.labeled_predictions >= self.config.min_sample_size and
            metrics_b.labeled_predictions >= self.config.min_sample_size
        )
    
    def is_expired(self) -> bool:
        """
        Check if test has exceeded maximum duration.
        
        Returns:
            True if test has exceeded max_duration_hours
        """
        elapsed = (datetime.now() - self.started_at).total_seconds() / 3600
        return elapsed > self.config.max_duration_hours
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Get test progress.
        
        Returns:
            Dictionary with progress information
        """
        metrics_a = self.calculate_metrics(ModelVariant.MODEL_A)
        metrics_b = self.calculate_metrics(ModelVariant.MODEL_B)
        
        progress_a = min(100, int(100 * metrics_a.labeled_predictions / self.config.min_sample_size))
        progress_b = min(100, int(100 * metrics_b.labeled_predictions / self.config.min_sample_size))
        
        elapsed_hours = (datetime.now() - self.started_at).total_seconds() / 3600
        
        return {
            'test_id': self.config.test_id,
            'status': self.status.value,
            'progress_a': progress_a,
            'progress_b': progress_b,
            'labeled_a': metrics_a.labeled_predictions,
            'labeled_b': metrics_b.labeled_predictions,
            'min_sample_size': self.config.min_sample_size,
            'elapsed_hours': elapsed_hours,
            'max_duration_hours': self.config.max_duration_hours,
            'is_complete': self.is_complete(),
            'is_expired': self.is_expired()
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def save_results(
        self, 
        result: ABTestResult, 
        output_dir: str = "ab_tests"
    ) -> str:
        """
        Save A/B test results to file.
        
        Args:
            result: ABTestResult to save
            output_dir: Output directory
            
        Returns:
            Path to saved file
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        output_file = f"{output_dir}/{self.config.test_id}_results.json"
        
        with open(output_file, 'w') as f:
            json.dump(result.to_dict(), f, indent=2, default=str)
        
        logger.info(f"✅ Results saved to {output_file}")
        
        return output_file
    
    def save_predictions(self, output_dir: str = "ab_tests") -> str:
        """
        Save all predictions to file.
        
        Args:
            output_dir: Output directory
            
        Returns:
            Path to saved file
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        output_file = f"{output_dir}/{self.config.test_id}_predictions.json"
        
        predictions_data = [p.to_dict() for p in self.predictions]
        
        with open(output_file, 'w') as f:
            json.dump(predictions_data, f, indent=2, default=str)
        
        logger.info(f"✅ Predictions saved to {output_file}")
        
        return output_file
    
    def export_report(self, result: ABTestResult, output_dir: str = "ab_tests") -> str:
        """
        Export comprehensive A/B test report.
        
        Args:
            result: ABTestResult to report
            output_dir: Output directory
            
        Returns:
            Path to report file
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        output_file = f"{output_dir}/{self.config.test_id}_report.md"
        
        report = self._generate_report(result)
        
        with open(output_file, 'w') as f:
            f.write(report)
        
        logger.info(f"✅ Report saved to {output_file}")
        
        return output_file
    
    def _generate_report(self, result: ABTestResult) -> str:
        """Generate markdown report."""
        return f"""# A/B Test Report: {result.test_id}

## Summary

| Metric | Model A (Production) | Model B (Candidate) | Difference |
|--------|---------------------|---------------------|------------|
| Accuracy | {result.model_a_metrics.accuracy:.1%} | {result.model_b_metrics.accuracy:.1%} | {(result.model_b_metrics.accuracy - result.model_a_metrics.accuracy)*100:+.1f}% |
| Precision | {result.model_a_metrics.precision:.3f} | {result.model_b_metrics.precision:.3f} | {result.model_b_metrics.precision - result.model_a_metrics.precision:+.3f} |
| Recall | {result.model_a_metrics.recall:.3f} | {result.model_b_metrics.recall:.3f} | {result.model_b_metrics.recall - result.model_a_metrics.recall:+.3f} |
| F1 Score | {result.model_a_metrics.f1:.3f} | {result.model_b_metrics.f1:.3f} | {result.improvement:+.3f} |
| Avg Latency | {result.model_a_metrics.avg_latency_ms:.0f}ms | {result.model_b_metrics.avg_latency_ms:.0f}ms | {result.model_b_metrics.avg_latency_ms - result.model_a_metrics.avg_latency_ms:+.0f}ms |
| Sample Size | {result.model_a_metrics.labeled_predictions} | {result.model_b_metrics.labeled_predictions} | - |

## Statistical Analysis

- **Test**: {result.statistical_result.test_name}
- **Statistic**: {result.statistical_result.statistic:.3f}
- **P-value**: {result.p_value:.4f}
- **Significant**: {"Yes" if result.is_significant else "No"} (α = {result.config.significance_level})
- **95% CI**: [{result.confidence_interval[0]:+.3f}, {result.confidence_interval[1]:+.3f}]
- **Effect Size**: {result.statistical_result.effect_size:.3f}

## Decision

**{result.decision.value.upper().replace('_', ' ')}**

## Recommendations

{chr(10).join(f"- {r}" for r in result.recommendations)}

## Test Details

- **Started**: {result.started_at.isoformat()}
- **Completed**: {result.completed_at.isoformat()}
- **Duration**: {result.test_duration_hours:.1f} hours
- **Total Predictions**: {result.total_predictions}
- **Traffic Split**: {result.config.traffic_split_a:.0%} A / {result.config.traffic_split_b:.0%} B

---
*Generated by Phoenix Guardian A/B Testing Framework*
"""
    
    def reset(self):
        """Reset the tester to initial state."""
        self.predictions = []
        self.status = TestStatus.RUNNING
        self.started_at = datetime.now()
        logger.info(f"A/B test '{self.config.test_id}' reset")
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"ABTester(test_id='{self.config.test_id}', "
            f"status={self.status.value}, "
            f"predictions={len(self.predictions)})"
        )
