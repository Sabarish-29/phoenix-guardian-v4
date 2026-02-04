"""
Phoenix Guardian Bidirectional Learning Module.

This module provides continuous learning capabilities through:
- FeedbackCollector: Collect and store physician feedback
- ModelFinetuner: Fine-tune RoBERTa models on collected feedback
- ActiveLearner: Uncertainty sampling for efficient labeling
- ABTester: A/B testing framework for model comparison and auto-deployment

Usage:
    from phoenix_guardian.learning import FeedbackCollector, Feedback
    
    collector = FeedbackCollector(db_config)
    collector.connect()
    
    feedback = Feedback(
        agent_name="safety_agent",
        user_id=123,
        session_id=uuid.uuid4(),
        suggestion="Check drug interaction",
        user_feedback="accept"
    )
    
    feedback_id = collector.collect_feedback(feedback)
    
    # Fine-tuning example
    from phoenix_guardian.learning import ModelFinetuner, FinetuningConfig
    
    config = FinetuningConfig(base_model="roberta-base", num_epochs=3)
    finetuner = ModelFinetuner(config, collector)
    
    train_examples, eval_examples = finetuner.prepare_training_data("Safety")
    checkpoint = finetuner.finetune(train_examples, eval_examples)
    
    # Active learning example
    from phoenix_guardian.learning import ActiveLearner, ActiveLearningConfig, QueryStrategy
    
    config = ActiveLearningConfig(
        query_strategy=QueryStrategy.HYBRID,
        batch_size=50
    )
    learner = ActiveLearner(config, model, tokenizer)
    
    # Select most informative examples for labeling
    requests = learner.select_for_labeling(unlabeled_pool)
    
    # Physician labels selected examples
    for request in requests:
        learner.mark_as_labeled(request.request_id, label=1)
    
    # Check labeling reduction statistics
    stats = learner.get_labeling_stats()
    print(f"Reduction rate: {stats.reduction_rate:.1%}")
    
    # A/B testing example
    from phoenix_guardian.learning import ABTester, ABTestConfig, DeploymentDecision
    
    config = ABTestConfig(
        test_id="safety_v2_vs_v1",
        model_a_path="models/production/safety_v1",
        model_b_path="models/checkpoints/safety_v2",
        min_sample_size=100,
        min_improvement=0.02  # 2% improvement required
    )
    tester = ABTester(config)
    
    # Route predictions through A/B test
    prediction = tester.route_prediction(input_text, user_id="user_123")
    tester.add_ground_truth(prediction.prediction_id, actual_label=1)
    
    # Analyze results and auto-deploy if B is significantly better
    result = tester.analyze_results()
    if result.decision == DeploymentDecision.DEPLOY_B:
        tester.deploy_winner(result)
"""

from .feedback_collector import (
    # Core Classes
    FeedbackCollector,
    Feedback,
    FeedbackType,
    FeedbackStats,
    TrainingBatch,
    
    # Exceptions
    FeedbackError,
    FeedbackDatabaseError,
    FeedbackValidationError,
    FeedbackConnectionError,
    
    # Constants
    VALID_FEEDBACK_TYPES,
    FEEDBACK_SCHEMA_VERSION,
    CREATE_FEEDBACK_TABLE_SQL,
)

from .model_finetuner import (
    # Core Classes
    ModelFinetuner,
    FinetuningConfig,
    TrainingExample,
    TrainingMetrics,
    ModelCheckpoint,
    TrainingResult,
    ThreatDetectionDataset,
    
    # Enums
    TrainingSource,
    ModelState,
    
    # Exceptions
    FinetunerError,
    InsufficientDataError,
    CheckpointError,
    ModelNotLoadedError as FinetunerModelNotLoadedError,
    DependencyError as FinetunerDependencyError,
    
    # Constants
    DEFAULT_BASE_MODEL,
    DEFAULT_LEARNING_RATE,
    DEFAULT_BATCH_SIZE,
    DEFAULT_NUM_EPOCHS,
    DEFAULT_MIN_IMPROVEMENT,
    THREAT_KEYWORDS,
    BENIGN_KEYWORDS,
)

from .active_learner import (
    # Core Classes
    ActiveLearner,
    ActiveLearningConfig,
    UnlabeledExample,
    PredictionUncertainty,
    LabelingRequest,
    LabelingStats,
    
    # Enums
    QueryStrategy,
    LabelingPriority,
    ExampleSource,
    
    # Exceptions
    ActiveLearnerError,
    ModelNotLoadedError,
    EmptyPoolError,
    DependencyError,
    InvalidStrategyError,
    
    # Utility Functions
    calculate_entropy,
    calculate_margin,
    
    # Constants
    DEFAULT_BATCH_SIZE as AL_DEFAULT_BATCH_SIZE,
    DEFAULT_UNCERTAINTY_THRESHOLD,
    DEFAULT_DIVERSITY_WEIGHT,
    CRITICAL_THRESHOLD,
    HIGH_THRESHOLD,
    MEDIUM_THRESHOLD,
)

from .ab_tester import (
    # Core Classes
    ABTester,
    ABTestConfig,
    Prediction,
    ModelMetrics,
    StatisticalResult,
    ABTestResult,
    
    # Enums
    ModelVariant,
    TestStatus,
    DeploymentDecision,
    
    # Exceptions
    ABTesterError,
    InsufficientSampleError,
    TestNotRunningError,
    DependencyError as ABTesterDependencyError,
    DeploymentError,
    ConfigurationError,
    
    # Constants
    DEFAULT_TRAFFIC_SPLIT_A,
    DEFAULT_TRAFFIC_SPLIT_B,
    DEFAULT_MIN_SAMPLE_SIZE,
    DEFAULT_MIN_IMPROVEMENT as AB_DEFAULT_MIN_IMPROVEMENT,
    DEFAULT_SIGNIFICANCE_LEVEL,
    DEFAULT_MAX_DURATION_HOURS,
    DEFAULT_CONFIDENCE_LEVEL,
)

__all__ = [
    # Feedback Collector Classes
    "FeedbackCollector",
    "Feedback",
    "FeedbackType",
    "FeedbackStats",
    "TrainingBatch",
    
    # Feedback Collector Exceptions
    "FeedbackError",
    "FeedbackDatabaseError",
    "FeedbackValidationError",
    "FeedbackConnectionError",
    
    # Feedback Collector Constants
    "VALID_FEEDBACK_TYPES",
    "FEEDBACK_SCHEMA_VERSION",
    "CREATE_FEEDBACK_TABLE_SQL",
    
    # Model Finetuner Classes
    "ModelFinetuner",
    "FinetuningConfig",
    "TrainingExample",
    "TrainingMetrics",
    "ModelCheckpoint",
    "TrainingResult",
    "ThreatDetectionDataset",
    
    # Model Finetuner Enums
    "TrainingSource",
    "ModelState",
    
    # Model Finetuner Exceptions
    "FinetunerError",
    "InsufficientDataError",
    "CheckpointError",
    "FinetunerModelNotLoadedError",
    "FinetunerDependencyError",
    
    # Model Finetuner Constants
    "DEFAULT_BASE_MODEL",
    "DEFAULT_LEARNING_RATE",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_NUM_EPOCHS",
    "DEFAULT_MIN_IMPROVEMENT",
    "THREAT_KEYWORDS",
    "BENIGN_KEYWORDS",
    
    # Active Learner Classes
    "ActiveLearner",
    "ActiveLearningConfig",
    "UnlabeledExample",
    "PredictionUncertainty",
    "LabelingRequest",
    "LabelingStats",
    
    # Active Learner Enums
    "QueryStrategy",
    "LabelingPriority",
    "ExampleSource",
    
    # Active Learner Exceptions
    "ActiveLearnerError",
    "ModelNotLoadedError",
    "EmptyPoolError",
    "DependencyError",
    "InvalidStrategyError",
    
    # Active Learner Utility Functions
    "calculate_entropy",
    "calculate_margin",
    
    # Active Learner Constants
    "AL_DEFAULT_BATCH_SIZE",
    "DEFAULT_UNCERTAINTY_THRESHOLD",
    "DEFAULT_DIVERSITY_WEIGHT",
    "CRITICAL_THRESHOLD",
    "HIGH_THRESHOLD",
    "MEDIUM_THRESHOLD",
    
    # A/B Tester Classes
    "ABTester",
    "ABTestConfig",
    "Prediction",
    "ModelMetrics",
    "StatisticalResult",
    "ABTestResult",
    
    # A/B Tester Enums
    "ModelVariant",
    "TestStatus",
    "DeploymentDecision",
    
    # A/B Tester Exceptions
    "ABTesterError",
    "InsufficientSampleError",
    "TestNotRunningError",
    "ABTesterDependencyError",
    "DeploymentError",
    "ConfigurationError",
    
    # A/B Tester Constants
    "DEFAULT_TRAFFIC_SPLIT_A",
    "DEFAULT_TRAFFIC_SPLIT_B",
    "DEFAULT_MIN_SAMPLE_SIZE",
    "AB_DEFAULT_MIN_IMPROVEMENT",
    "DEFAULT_SIGNIFICANCE_LEVEL",
    "DEFAULT_MAX_DURATION_HOURS",
    "DEFAULT_CONFIDENCE_LEVEL",
]
