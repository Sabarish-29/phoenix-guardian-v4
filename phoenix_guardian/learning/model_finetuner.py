"""
Model Finetuner - RoBERTa Fine-tuning Pipeline for Threat Detection.

This module provides a comprehensive fine-tuning pipeline for the RoBERTa
threat detection model using physician-labeled feedback data.

Features:
- Fine-tune RoBERTa on feedback data
- Training pipeline with data preparation, training, validation
- Model versioning with checkpoint management
- Performance metrics tracking (accuracy, precision, recall, F1)
- Rollback support for model versions

Example:
    from phoenix_guardian.learning import (
        ModelFinetuner, FinetuningConfig, FeedbackCollector
    )
    
    config = FinetuningConfig(
        base_model="roberta-base",
        num_epochs=3,
        batch_size=16
    )
    
    finetuner = ModelFinetuner(config, feedback_collector)
    train_examples, eval_examples = finetuner.prepare_training_data("Safety")
    checkpoint = finetuner.finetune(train_examples, eval_examples)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
from pathlib import Path
from enum import Enum
import json
import logging
import os
import shutil

# Third-party imports - these may not be available in all environments
try:
    import torch
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    Dataset = object
    DataLoader = None

try:
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        TrainingArguments,
        Trainer,
        EvalPrediction,
        EarlyStoppingCallback
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    AutoTokenizer = None
    AutoModelForSequenceClassification = None
    TrainingArguments = None
    Trainer = None
    EvalPrediction = None
    EarlyStoppingCallback = None

try:
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        accuracy_score,
        precision_recall_fscore_support,
        confusion_matrix
    )
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    train_test_split = None
    accuracy_score = None
    precision_recall_fscore_support = None
    confusion_matrix = None
    np = None

from .feedback_collector import FeedbackCollector, TrainingBatch

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_BASE_MODEL = "roberta-base"
DEFAULT_LEARNING_RATE = 2e-5
DEFAULT_BATCH_SIZE = 16
DEFAULT_NUM_EPOCHS = 3
DEFAULT_WARMUP_STEPS = 500
DEFAULT_WEIGHT_DECAY = 0.01
DEFAULT_MAX_LENGTH = 512
DEFAULT_EVAL_SPLIT = 0.2
DEFAULT_MIN_IMPROVEMENT = 0.02  # 2% minimum improvement
DEFAULT_CHECKPOINT_DIR = "models/checkpoints"
DEFAULT_EARLY_STOPPING_PATIENCE = 3
MIN_TRAINING_EXAMPLES = 10

# Threat detection keywords for label extraction
THREAT_KEYWORDS = [
    'threat', 'attack', 'malicious', 'security', 'block',
    'dangerous', 'suspicious', 'unauthorized', 'injection',
    'exploit', 'vulnerability', 'breach', 'intrusion'
]

BENIGN_KEYWORDS = [
    'safe', 'benign', 'legitimate', 'authorized', 'normal',
    'valid', 'trusted', 'approved', 'harmless'
]


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class TrainingSource(str, Enum):
    """Source of training data."""
    FEEDBACK = "feedback"
    SYNTHETIC = "synthetic"
    MANUAL = "manual"
    AUGMENTED = "augmented"


class ModelState(str, Enum):
    """Model deployment state."""
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class FinetunerError(Exception):
    """Base exception for model finetuner errors."""
    pass


class InsufficientDataError(FinetunerError):
    """Raised when insufficient training data is available."""
    pass


class CheckpointError(FinetunerError):
    """Raised when checkpoint operations fail."""
    pass


class ModelNotLoadedError(FinetunerError):
    """Raised when model operations attempted without loaded model."""
    pass


class DependencyError(FinetunerError):
    """Raised when required dependencies are not available."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TrainingExample:
    """
    Single training example for threat detection.
    
    Attributes:
        text: Input text to classify
        label: 0 = benign, 1 = threat
        source: Origin of the training example
        confidence: Original model confidence (if from feedback)
        feedback_id: Reference to original feedback record
        metadata: Additional metadata
    """
    text: str
    label: int  # 0 = benign, 1 = threat
    source: str = TrainingSource.FEEDBACK.value
    confidence: Optional[float] = None
    feedback_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate training example."""
        if not self.text or not self.text.strip():
            raise ValueError("Training example text cannot be empty")
        
        if self.label not in (0, 1):
            raise ValueError(f"Label must be 0 or 1, got {self.label}")
        
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'text': self.text,
            'label': self.label,
            'source': self.source,
            'confidence': self.confidence,
            'feedback_id': self.feedback_id,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrainingExample':
        """Create from dictionary."""
        return cls(
            text=data['text'],
            label=data['label'],
            source=data.get('source', TrainingSource.FEEDBACK.value),
            confidence=data.get('confidence'),
            feedback_id=data.get('feedback_id'),
            metadata=data.get('metadata')
        )


@dataclass
class TrainingMetrics:
    """
    Training metrics for model evaluation.
    
    Attributes:
        accuracy: Classification accuracy
        precision: Precision for threat class
        recall: Recall for threat class
        f1: F1 score for threat class
        loss: Evaluation loss
        epoch: Training epoch number
        timestamp: When metrics were recorded
        confusion_matrix: Optional confusion matrix
    """
    accuracy: float
    precision: float
    recall: float
    f1: float
    loss: float
    epoch: int
    timestamp: datetime = field(default_factory=datetime.now)
    confusion_matrix: Optional[List[List[int]]] = None
    
    def __post_init__(self):
        """Validate metrics."""
        for metric_name in ['accuracy', 'precision', 'recall', 'f1']:
            value = getattr(self, metric_name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{metric_name} must be between 0 and 1, got {value}")
        
        if self.loss < 0:
            raise ValueError(f"Loss must be non-negative, got {self.loss}")
        
        if self.epoch < 0:
            raise ValueError(f"Epoch must be non-negative, got {self.epoch}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1': self.f1,
            'loss': self.loss,
            'epoch': self.epoch,
            'timestamp': self.timestamp.isoformat(),
            'confusion_matrix': self.confusion_matrix
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrainingMetrics':
        """Create from dictionary."""
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()
        
        return cls(
            accuracy=data['accuracy'],
            precision=data['precision'],
            recall=data['recall'],
            f1=data['f1'],
            loss=data['loss'],
            epoch=data.get('epoch', 0),
            timestamp=timestamp,
            confusion_matrix=data.get('confusion_matrix')
        )
    
    def improved_over(self, other: 'TrainingMetrics', min_improvement: float = 0.02) -> bool:
        """Check if this metrics improved over another by at least min_improvement."""
        if other is None:
            return True
        return (self.f1 - other.f1) >= min_improvement


@dataclass
class ModelCheckpoint:
    """
    Model checkpoint metadata.
    
    Attributes:
        version: Unique version identifier
        model_path: Path to saved model files
        metrics: Training metrics at checkpoint
        training_examples: Number of examples used for training
        created_at: When checkpoint was created
        state: Deployment state (staging, production, etc.)
        base_model: Base model used for fine-tuning
        config_snapshot: Copy of training configuration
    """
    version: str
    model_path: str
    metrics: TrainingMetrics
    training_examples: int
    created_at: datetime = field(default_factory=datetime.now)
    state: str = ModelState.STAGING.value
    base_model: str = DEFAULT_BASE_MODEL
    config_snapshot: Optional[Dict[str, Any]] = None
    
    @property
    def is_production(self) -> bool:
        """Check if checkpoint is in production."""
        return self.state == ModelState.PRODUCTION.value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'version': self.version,
            'model_path': self.model_path,
            'metrics': self.metrics.to_dict(),
            'training_examples': self.training_examples,
            'created_at': self.created_at.isoformat(),
            'state': self.state,
            'base_model': self.base_model,
            'config_snapshot': self.config_snapshot
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelCheckpoint':
        """Create from dictionary."""
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()
        
        return cls(
            version=data['version'],
            model_path=data['model_path'],
            metrics=TrainingMetrics.from_dict(data['metrics']),
            training_examples=data['training_examples'],
            created_at=created_at,
            state=data.get('state', ModelState.STAGING.value),
            base_model=data.get('base_model', DEFAULT_BASE_MODEL),
            config_snapshot=data.get('config_snapshot')
        )


@dataclass
class FinetuningConfig:
    """
    Configuration for model fine-tuning.
    
    Attributes:
        base_model: HuggingFace model identifier
        learning_rate: Learning rate for optimizer
        batch_size: Training batch size
        num_epochs: Number of training epochs
        warmup_steps: Number of warmup steps
        weight_decay: Weight decay for regularization
        max_length: Maximum sequence length
        eval_split: Fraction for evaluation set
        min_improvement: Minimum F1 improvement to save checkpoint
        checkpoint_dir: Directory for saving checkpoints
        early_stopping_patience: Epochs without improvement before stopping
        gradient_accumulation_steps: Steps for gradient accumulation
        fp16: Use mixed precision training
        seed: Random seed for reproducibility
    """
    base_model: str = DEFAULT_BASE_MODEL
    learning_rate: float = DEFAULT_LEARNING_RATE
    batch_size: int = DEFAULT_BATCH_SIZE
    num_epochs: int = DEFAULT_NUM_EPOCHS
    warmup_steps: int = DEFAULT_WARMUP_STEPS
    weight_decay: float = DEFAULT_WEIGHT_DECAY
    max_length: int = DEFAULT_MAX_LENGTH
    eval_split: float = DEFAULT_EVAL_SPLIT
    min_improvement: float = DEFAULT_MIN_IMPROVEMENT
    checkpoint_dir: str = DEFAULT_CHECKPOINT_DIR
    early_stopping_patience: int = DEFAULT_EARLY_STOPPING_PATIENCE
    gradient_accumulation_steps: int = 1
    fp16: bool = False
    seed: int = 42
    
    def __post_init__(self):
        """Validate configuration."""
        if self.learning_rate <= 0:
            raise ValueError(f"Learning rate must be positive, got {self.learning_rate}")
        
        if self.batch_size < 1:
            raise ValueError(f"Batch size must be at least 1, got {self.batch_size}")
        
        if self.num_epochs < 1:
            raise ValueError(f"Number of epochs must be at least 1, got {self.num_epochs}")
        
        if not (0.0 < self.eval_split < 1.0):
            raise ValueError(f"Eval split must be between 0 and 1, got {self.eval_split}")
        
        if self.min_improvement < 0:
            raise ValueError(f"Min improvement must be non-negative, got {self.min_improvement}")
        
        if self.max_length < 1:
            raise ValueError(f"Max length must be at least 1, got {self.max_length}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'base_model': self.base_model,
            'learning_rate': self.learning_rate,
            'batch_size': self.batch_size,
            'num_epochs': self.num_epochs,
            'warmup_steps': self.warmup_steps,
            'weight_decay': self.weight_decay,
            'max_length': self.max_length,
            'eval_split': self.eval_split,
            'min_improvement': self.min_improvement,
            'checkpoint_dir': self.checkpoint_dir,
            'early_stopping_patience': self.early_stopping_patience,
            'gradient_accumulation_steps': self.gradient_accumulation_steps,
            'fp16': self.fp16,
            'seed': self.seed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FinetuningConfig':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TrainingResult:
    """
    Result of a training run.
    
    Attributes:
        success: Whether training completed successfully
        checkpoint: Saved checkpoint (if any)
        final_metrics: Final evaluation metrics
        training_history: Metrics per epoch
        error_message: Error message if failed
    """
    success: bool
    checkpoint: Optional[ModelCheckpoint] = None
    final_metrics: Optional[TrainingMetrics] = None
    training_history: List[TrainingMetrics] = field(default_factory=list)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'success': self.success,
            'checkpoint': self.checkpoint.to_dict() if self.checkpoint else None,
            'final_metrics': self.final_metrics.to_dict() if self.final_metrics else None,
            'training_history': [m.to_dict() for m in self.training_history],
            'error_message': self.error_message
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET
# ═══════════════════════════════════════════════════════════════════════════════

class ThreatDetectionDataset(Dataset):
    """
    PyTorch Dataset for threat detection.
    
    Converts TrainingExample objects into tokenized tensors suitable
    for training transformer models.
    """
    
    def __init__(
        self,
        examples: List[TrainingExample],
        tokenizer,
        max_length: int = DEFAULT_MAX_LENGTH
    ):
        """
        Initialize dataset.
        
        Args:
            examples: List of training examples
            tokenizer: HuggingFace tokenizer
            max_length: Maximum sequence length
        """
        if not TORCH_AVAILABLE:
            raise DependencyError("PyTorch is required for ThreatDetectionDataset")
        
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self) -> int:
        """Return number of examples."""
        return len(self.examples)
    
    def __getitem__(self, idx: int) -> Dict[str, Any]:
        """
        Get tokenized example.
        
        Args:
            idx: Example index
            
        Returns:
            Dictionary with input_ids, attention_mask, and labels
        """
        example = self.examples[idx]
        
        encoding = self.tokenizer(
            example.text,
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(example.label, dtype=torch.long)
        }
    
    def get_label_distribution(self) -> Dict[int, int]:
        """Get distribution of labels in dataset."""
        distribution = {0: 0, 1: 0}
        for example in self.examples:
            distribution[example.label] += 1
        return distribution


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL FINETUNER
# ═══════════════════════════════════════════════════════════════════════════════

class ModelFinetuner:
    """
    Fine-tune RoBERTa threat detection model on physician feedback.
    
    This class provides a complete pipeline for:
    - Preparing training data from feedback
    - Fine-tuning the model
    - Evaluating performance
    - Managing model checkpoints
    - Promoting models to production
    
    Example:
        config = FinetuningConfig(base_model="roberta-base", num_epochs=3)
        finetuner = ModelFinetuner(config, feedback_collector)
        
        train_examples, eval_examples = finetuner.prepare_training_data("Safety")
        checkpoint = finetuner.finetune(train_examples, eval_examples)
        
        if checkpoint and checkpoint.metrics.f1 >= 0.95:
            finetuner.promote_to_production(checkpoint.version)
    """
    
    def __init__(
        self,
        config: FinetuningConfig,
        feedback_collector: Optional[FeedbackCollector] = None
    ):
        """
        Initialize model finetuner.
        
        Args:
            config: Fine-tuning configuration
            feedback_collector: FeedbackCollector instance (optional)
            
        Raises:
            DependencyError: If required dependencies not available
        """
        self.config = config
        self.feedback_collector = feedback_collector
        
        # Check dependencies
        self._check_dependencies()
        
        # Initialize tokenizer (lazy load model)
        self.tokenizer = None
        self.model = None
        self._tokenizer_loaded = False
        
        # Create checkpoint directory
        Path(config.checkpoint_dir).mkdir(parents=True, exist_ok=True)
        
        # Track metrics and checkpoints
        self.best_metrics: Optional[TrainingMetrics] = None
        self.checkpoints: List[ModelCheckpoint] = []
        self.training_history: List[TrainingMetrics] = []
        
        # Load existing checkpoints
        self._load_existing_checkpoints()
        
        logger.info(f"ModelFinetuner initialized with base model: {config.base_model}")
    
    def _check_dependencies(self):
        """Check if required dependencies are available."""
        missing = []
        
        if not TORCH_AVAILABLE:
            missing.append("torch")
        
        if not TRANSFORMERS_AVAILABLE:
            missing.append("transformers")
        
        if not SKLEARN_AVAILABLE:
            missing.append("scikit-learn")
        
        if missing:
            logger.warning(
                f"Missing dependencies: {', '.join(missing)}. "
                f"Some functionality may be limited."
            )
    
    def _ensure_tokenizer(self):
        """Ensure tokenizer is loaded."""
        if self.tokenizer is None:
            if not TRANSFORMERS_AVAILABLE:
                raise DependencyError("transformers is required for tokenization")
            
            logger.info(f"Loading tokenizer: {self.config.base_model}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.base_model)
            self._tokenizer_loaded = True
    
    def _ensure_model(self):
        """Ensure model is loaded."""
        if self.model is None:
            if not TRANSFORMERS_AVAILABLE:
                raise DependencyError("transformers is required for model loading")
            
            logger.info(f"Loading model: {self.config.base_model}")
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.config.base_model,
                num_labels=2
            )
    
    def _load_existing_checkpoints(self):
        """Load metadata of existing checkpoints."""
        checkpoint_dir = Path(self.config.checkpoint_dir)
        
        if not checkpoint_dir.exists():
            return
        
        for path in checkpoint_dir.glob("v*"):
            metadata_path = path / "checkpoint_metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    checkpoint = ModelCheckpoint.from_dict(metadata)
                    self.checkpoints.append(checkpoint)
                    
                    # Track best metrics from production model
                    if checkpoint.is_production:
                        self.best_metrics = checkpoint.metrics
                    
                except Exception as e:
                    logger.warning(f"Failed to load checkpoint metadata from {path}: {e}")
        
        # Sort by creation date
        self.checkpoints.sort(key=lambda x: x.created_at, reverse=True)
        
        if self.checkpoints:
            logger.info(f"Loaded {len(self.checkpoints)} existing checkpoints")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DATA PREPARATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def prepare_training_data(
        self,
        agent_name: str = "Safety",
        min_examples: int = 100,
        include_synthetic: bool = False
    ) -> Tuple[List[TrainingExample], List[TrainingExample]]:
        """
        Prepare training data from feedback.
        
        Args:
            agent_name: Agent to get feedback for
            min_examples: Minimum examples required for training
            include_synthetic: Whether to include synthetic examples
            
        Returns:
            Tuple of (train_examples, eval_examples)
            
        Raises:
            InsufficientDataError: If insufficient training data
            ValueError: If feedback collector not configured
        """
        if self.feedback_collector is None:
            raise ValueError("FeedbackCollector not configured")
        
        logger.info(f"Fetching training data for {agent_name}...")
        
        # Get feedback from database
        training_batch = self.feedback_collector.get_training_data(
            agent_name=agent_name,
            limit=10000
        )
        
        if not training_batch.feedback_records:
            raise InsufficientDataError("No feedback data available for training")
        
        # Convert feedback to training examples
        examples = []
        skipped = 0
        
        for record in training_batch.feedback_records:
            try:
                label = self._feedback_to_label(record)
                
                if label is not None:
                    examples.append(TrainingExample(
                        text=record['suggestion'],
                        label=label,
                        source=TrainingSource.FEEDBACK.value,
                        confidence=record.get('confidence_score'),
                        feedback_id=record.get('id'),
                        metadata={
                            'user_feedback': record.get('user_feedback'),
                            'session_id': str(record.get('session_id', ''))
                        }
                    ))
                else:
                    skipped += 1
            except Exception as e:
                logger.warning(f"Failed to process feedback record: {e}")
                skipped += 1
        
        logger.info(f"Processed {len(examples)} examples, skipped {skipped}")
        
        # Add synthetic examples if requested and needed
        if include_synthetic and len(examples) < min_examples:
            synthetic = self._generate_synthetic_examples(
                count=min_examples - len(examples)
            )
            examples.extend(synthetic)
            logger.info(f"Added {len(synthetic)} synthetic examples")
        
        if len(examples) < min_examples:
            raise InsufficientDataError(
                f"Insufficient training data: {len(examples)} examples "
                f"(minimum: {min_examples})"
            )
        
        logger.info(f"✅ Prepared {len(examples)} training examples")
        
        # Split into train/eval with stratification
        train_examples, eval_examples = self._split_data(examples)
        
        logger.info(f"   Train: {len(train_examples)}, Eval: {len(eval_examples)}")
        
        return train_examples, eval_examples
    
    def _feedback_to_label(self, record: Dict[str, Any]) -> Optional[int]:
        """
        Convert feedback record to training label.
        
        Logic:
        - accept → trust original prediction
        - reject → flip original prediction
        - modify → extract label from modified output
        
        Args:
            record: Feedback record from database
            
        Returns:
            0 (benign) or 1 (threat), or None if unclear
        """
        user_feedback = record.get('user_feedback', '').lower()
        confidence = record.get('confidence_score', 0.5)
        
        # Validate user feedback
        if user_feedback not in ('accept', 'reject', 'modify'):
            return None
        
        # For accepted predictions - trust the original model decision
        if user_feedback == 'accept':
            # High confidence predictions accepted = threat
            # Low confidence predictions accepted = benign
            if confidence >= 0.8:
                return 1  # Threat
            elif confidence <= 0.3:
                return 0  # Benign
            else:
                # Medium confidence - unclear, skip
                return None
        
        # For rejected predictions - flip the label
        if user_feedback == 'reject':
            # If model was confident (predicted threat) and user rejected → benign
            if confidence >= 0.7:
                return 0  # False positive → benign
            # If model was not confident (predicted benign) and user rejected → threat
            elif confidence <= 0.4:
                return 1  # False negative → threat
            else:
                # Medium confidence - unclear, skip
                return None
        
        # For modified outputs - try to extract intent
        if user_feedback == 'modify':
            modified = record.get('modified_output', '')
            if modified:
                return self._extract_label_from_text(modified)
            return None
        
        return None
    
    def _extract_label_from_text(self, text: str) -> Optional[int]:
        """
        Extract label from modified output text.
        
        Args:
            text: Modified output text
            
        Returns:
            0 (benign) or 1 (threat), or None if unclear
        """
        text_lower = text.lower()
        
        threat_score = sum(1 for kw in THREAT_KEYWORDS if kw in text_lower)
        benign_score = sum(1 for kw in BENIGN_KEYWORDS if kw in text_lower)
        
        if threat_score > benign_score:
            return 1  # Threat
        elif benign_score > threat_score:
            return 0  # Benign
        else:
            return None  # Unclear
    
    def _split_data(
        self,
        examples: List[TrainingExample]
    ) -> Tuple[List[TrainingExample], List[TrainingExample]]:
        """
        Split data into train and eval sets.
        
        Args:
            examples: All training examples
            
        Returns:
            Tuple of (train_examples, eval_examples)
        """
        if not SKLEARN_AVAILABLE:
            # Simple split without sklearn
            split_idx = int(len(examples) * (1 - self.config.eval_split))
            return examples[:split_idx], examples[split_idx:]
        
        # Get labels for stratification
        labels = [ex.label for ex in examples]
        
        # Check if stratification is possible (need at least 2 of each class)
        label_counts = {0: labels.count(0), 1: labels.count(1)}
        
        if min(label_counts.values()) < 2:
            # Not enough of each class for stratification
            logger.warning("Insufficient class diversity for stratified split")
            train_examples, eval_examples = train_test_split(
                examples,
                test_size=self.config.eval_split,
                random_state=self.config.seed
            )
        else:
            # Stratified split
            train_examples, eval_examples = train_test_split(
                examples,
                test_size=self.config.eval_split,
                random_state=self.config.seed,
                stratify=labels
            )
        
        return train_examples, eval_examples
    
    def _generate_synthetic_examples(self, count: int) -> List[TrainingExample]:
        """
        Generate synthetic training examples.
        
        Args:
            count: Number of examples to generate
            
        Returns:
            List of synthetic training examples
        """
        # Basic templates for synthetic data
        threat_templates = [
            "DROP TABLE users; --",
            "SELECT * FROM passwords WHERE 1=1",
            "<script>alert('xss')</script>",
            "rm -rf / --no-preserve-root",
            "exec('malicious code')",
        ]
        
        benign_templates = [
            "Please check the patient's vitals",
            "Schedule a follow-up appointment",
            "Review the lab results for patient",
            "Update medication dosage",
            "Generate summary report for clinic",
        ]
        
        examples = []
        
        for i in range(count):
            if i % 2 == 0 and threat_templates:
                template = threat_templates[i % len(threat_templates)]
                examples.append(TrainingExample(
                    text=template,
                    label=1,
                    source=TrainingSource.SYNTHETIC.value,
                    metadata={'template_id': i}
                ))
            elif benign_templates:
                template = benign_templates[i % len(benign_templates)]
                examples.append(TrainingExample(
                    text=template,
                    label=0,
                    source=TrainingSource.SYNTHETIC.value,
                    metadata={'template_id': i}
                ))
        
        return examples
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRAINING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def finetune(
        self,
        train_examples: List[TrainingExample],
        eval_examples: List[TrainingExample],
        version: Optional[str] = None
    ) -> Optional[ModelCheckpoint]:
        """
        Fine-tune model on training data.
        
        Args:
            train_examples: Training examples
            eval_examples: Evaluation examples
            version: Model version string (auto-generated if None)
            
        Returns:
            ModelCheckpoint if improvement meets threshold, else None
            
        Raises:
            InsufficientDataError: If insufficient training data
            DependencyError: If required dependencies not available
        """
        if not TRANSFORMERS_AVAILABLE or not TORCH_AVAILABLE:
            raise DependencyError(
                "transformers and torch are required for fine-tuning"
            )
        
        if len(train_examples) < MIN_TRAINING_EXAMPLES:
            raise InsufficientDataError(
                f"Need at least {MIN_TRAINING_EXAMPLES} training examples, "
                f"got {len(train_examples)}"
            )
        
        logger.info("🚀 Starting model fine-tuning...")
        logger.info(f"   Training examples: {len(train_examples)}")
        logger.info(f"   Evaluation examples: {len(eval_examples)}")
        
        # Clear training history
        self.training_history = []
        
        # Load tokenizer and model
        self._ensure_tokenizer()
        self._ensure_model()
        
        # Create datasets
        train_dataset = ThreatDetectionDataset(
            train_examples,
            self.tokenizer,
            self.config.max_length
        )
        eval_dataset = ThreatDetectionDataset(
            eval_examples,
            self.tokenizer,
            self.config.max_length
        )
        
        # Log label distribution
        train_dist = train_dataset.get_label_distribution()
        eval_dist = eval_dataset.get_label_distribution()
        logger.info(f"   Train distribution: {train_dist}")
        logger.info(f"   Eval distribution: {eval_dist}")
        
        # Training arguments
        output_dir = f"{self.config.checkpoint_dir}/training_output"
        
        training_args = TrainingArguments(
            output_dir=output_dir,
            learning_rate=self.config.learning_rate,
            per_device_train_batch_size=self.config.batch_size,
            per_device_eval_batch_size=self.config.batch_size,
            num_train_epochs=self.config.num_epochs,
            weight_decay=self.config.weight_decay,
            warmup_steps=self.config.warmup_steps,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="f1",
            greater_is_better=True,
            logging_dir=f"{output_dir}/logs",
            logging_steps=10,
            save_total_limit=3,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            fp16=self.config.fp16 and torch.cuda.is_available(),
            seed=self.config.seed,
            report_to="none",  # Disable wandb/tensorboard
        )
        
        # Callbacks
        callbacks = []
        if self.config.early_stopping_patience > 0:
            callbacks.append(
                EarlyStoppingCallback(
                    early_stopping_patience=self.config.early_stopping_patience
                )
            )
        
        # Trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            compute_metrics=self._compute_metrics,
            callbacks=callbacks
        )
        
        # Train
        logger.info("Training model...")
        train_result = trainer.train()
        
        # Evaluate
        logger.info("Evaluating model...")
        eval_result = trainer.evaluate()
        
        # Extract metrics
        metrics = TrainingMetrics(
            accuracy=eval_result.get('eval_accuracy', 0.0),
            precision=eval_result.get('eval_precision', 0.0),
            recall=eval_result.get('eval_recall', 0.0),
            f1=eval_result.get('eval_f1', 0.0),
            loss=eval_result.get('eval_loss', 0.0),
            epoch=self.config.num_epochs
        )
        
        logger.info(f"✅ Training complete!")
        logger.info(f"   Accuracy: {metrics.accuracy:.3f}")
        logger.info(f"   Precision: {metrics.precision:.3f}")
        logger.info(f"   Recall: {metrics.recall:.3f}")
        logger.info(f"   F1: {metrics.f1:.3f}")
        
        # Save checkpoint if improved
        checkpoint = self._save_checkpoint(
            metrics=metrics,
            train_examples=len(train_examples),
            version=version
        )
        
        # Cleanup training output
        self._cleanup_training_output(output_dir)
        
        return checkpoint
    
    def _compute_metrics(self, eval_pred) -> Dict[str, float]:
        """
        Compute metrics for evaluation.
        
        Args:
            eval_pred: EvalPrediction from trainer
            
        Returns:
            Dictionary of metric values
        """
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)
        
        accuracy = accuracy_score(labels, predictions)
        precision, recall, f1, _ = precision_recall_fscore_support(
            labels, predictions, average='binary', zero_division=0
        )
        
        # Store in history
        metrics = TrainingMetrics(
            accuracy=float(accuracy),
            precision=float(precision),
            recall=float(recall),
            f1=float(f1),
            loss=0.0,  # Will be updated by trainer
            epoch=len(self.training_history)
        )
        self.training_history.append(metrics)
        
        return {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1
        }
    
    def _cleanup_training_output(self, output_dir: str):
        """Clean up temporary training output directory."""
        try:
            if Path(output_dir).exists():
                shutil.rmtree(output_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup training output: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CHECKPOINT MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _save_checkpoint(
        self,
        metrics: TrainingMetrics,
        train_examples: int,
        version: Optional[str] = None
    ) -> Optional[ModelCheckpoint]:
        """
        Save model checkpoint if improved.
        
        Args:
            metrics: Training metrics
            train_examples: Number of training examples
            version: Version string (auto-generated if None)
            
        Returns:
            ModelCheckpoint if saved, else None
        """
        # Check if improvement meets threshold
        if not metrics.improved_over(self.best_metrics, self.config.min_improvement):
            current_f1 = self.best_metrics.f1 if self.best_metrics else 0.0
            improvement = metrics.f1 - current_f1
            
            logger.info(
                f"⚠️  Model did not improve sufficiently "
                f"(+{improvement:.3f} < {self.config.min_improvement}). "
                f"Not saving checkpoint."
            )
            return None
        
        # Generate version if not provided
        if version is None:
            version = f"v{len(self.checkpoints) + 1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create model directory
        model_path = f"{self.config.checkpoint_dir}/{version}"
        Path(model_path).mkdir(parents=True, exist_ok=True)
        
        # Save model and tokenizer
        self.model.save_pretrained(model_path)
        self.tokenizer.save_pretrained(model_path)
        
        # Create checkpoint
        checkpoint = ModelCheckpoint(
            version=version,
            model_path=model_path,
            metrics=metrics,
            training_examples=train_examples,
            base_model=self.config.base_model,
            config_snapshot=self.config.to_dict()
        )
        
        # Save checkpoint metadata
        metadata_path = f"{model_path}/checkpoint_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
        
        # Update best metrics
        self.best_metrics = metrics
        self.checkpoints.insert(0, checkpoint)  # Add to front (most recent)
        
        logger.info(f"✅ Saved checkpoint: {version}")
        return checkpoint
    
    def load_checkpoint(self, version: str) -> bool:
        """
        Load model checkpoint.
        
        Args:
            version: Checkpoint version to load
            
        Returns:
            True if loaded successfully, False otherwise
        """
        if not TRANSFORMERS_AVAILABLE:
            raise DependencyError("transformers is required for checkpoint loading")
        
        model_path = f"{self.config.checkpoint_dir}/{version}"
        
        if not Path(model_path).exists():
            logger.error(f"Checkpoint not found: {model_path}")
            return False
        
        try:
            self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self._tokenizer_loaded = True
            
            logger.info(f"✅ Loaded checkpoint: {version}")
            return True
        except Exception as e:
            logger.error(f"Failed to load checkpoint {version}: {e}")
            return False
    
    def list_checkpoints(self) -> List[ModelCheckpoint]:
        """
        List all available checkpoints.
        
        Returns:
            List of ModelCheckpoint objects sorted by creation date (newest first)
        """
        # Refresh from disk
        self._load_existing_checkpoints()
        return self.checkpoints
    
    def get_checkpoint(self, version: str) -> Optional[ModelCheckpoint]:
        """
        Get specific checkpoint by version.
        
        Args:
            version: Checkpoint version
            
        Returns:
            ModelCheckpoint if found, else None
        """
        for checkpoint in self.checkpoints:
            if checkpoint.version == version:
                return checkpoint
        return None
    
    def get_production_checkpoint(self) -> Optional[ModelCheckpoint]:
        """
        Get the current production checkpoint.
        
        Returns:
            Production ModelCheckpoint if any, else None
        """
        for checkpoint in self.checkpoints:
            if checkpoint.is_production:
                return checkpoint
        return None
    
    def promote_to_production(self, version: str) -> bool:
        """
        Mark checkpoint as production model.
        
        Args:
            version: Checkpoint version to promote
            
        Returns:
            True if promoted successfully, False otherwise
        """
        # Find checkpoint
        target_checkpoint = None
        for checkpoint in self.checkpoints:
            if checkpoint.version == version:
                target_checkpoint = checkpoint
                break
        
        if target_checkpoint is None:
            logger.error(f"Checkpoint not found: {version}")
            return False
        
        # Demote current production
        for checkpoint in self.checkpoints:
            if checkpoint.is_production:
                checkpoint.state = ModelState.STAGING.value
                self._update_checkpoint_metadata(checkpoint)
        
        # Promote new checkpoint
        target_checkpoint.state = ModelState.PRODUCTION.value
        self._update_checkpoint_metadata(target_checkpoint)
        
        logger.info(f"✅ Promoted {version} to production")
        return True
    
    def demote_from_production(self, version: str) -> bool:
        """
        Remove checkpoint from production.
        
        Args:
            version: Checkpoint version to demote
            
        Returns:
            True if demoted successfully, False otherwise
        """
        for checkpoint in self.checkpoints:
            if checkpoint.version == version:
                checkpoint.state = ModelState.STAGING.value
                self._update_checkpoint_metadata(checkpoint)
                logger.info(f"✅ Demoted {version} from production")
                return True
        
        logger.error(f"Checkpoint not found: {version}")
        return False
    
    def delete_checkpoint(self, version: str) -> bool:
        """
        Delete a checkpoint.
        
        Args:
            version: Checkpoint version to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        model_path = f"{self.config.checkpoint_dir}/{version}"
        
        if not Path(model_path).exists():
            logger.error(f"Checkpoint not found: {model_path}")
            return False
        
        # Check if production
        checkpoint = self.get_checkpoint(version)
        if checkpoint and checkpoint.is_production:
            logger.error(f"Cannot delete production checkpoint: {version}")
            return False
        
        try:
            shutil.rmtree(model_path)
            
            # Remove from list
            self.checkpoints = [c for c in self.checkpoints if c.version != version]
            
            logger.info(f"✅ Deleted checkpoint: {version}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete checkpoint {version}: {e}")
            return False
    
    def _update_checkpoint_metadata(self, checkpoint: ModelCheckpoint):
        """Update checkpoint metadata file."""
        metadata_path = f"{checkpoint.model_path}/checkpoint_metadata.json"
        
        try:
            with open(metadata_path, 'w') as f:
                json.dump(checkpoint.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to update checkpoint metadata: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PREDICTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def predict(self, text: str) -> Tuple[int, float]:
        """
        Predict threat label for text.
        
        Args:
            text: Input text to classify
            
        Returns:
            Tuple of (label, confidence)
            
        Raises:
            ModelNotLoadedError: If model not loaded
        """
        if self.model is None:
            raise ModelNotLoadedError("Model not loaded. Call load_checkpoint first.")
        
        if not TORCH_AVAILABLE:
            raise DependencyError("PyTorch is required for prediction")
        
        self._ensure_tokenizer()
        
        # Tokenize
        encoding = self.tokenizer(
            text,
            truncation=True,
            padding='max_length',
            max_length=self.config.max_length,
            return_tensors='pt'
        )
        
        # Predict
        self.model.eval()
        with torch.no_grad():
            outputs = self.model(**encoding)
            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=1)
            
            predicted_class = torch.argmax(probabilities, dim=1).item()
            confidence = probabilities[0][predicted_class].item()
        
        return predicted_class, confidence
    
    def predict_batch(
        self,
        texts: List[str],
        batch_size: int = 32
    ) -> List[Tuple[int, float]]:
        """
        Predict threat labels for multiple texts.
        
        Args:
            texts: List of input texts
            batch_size: Batch size for inference
            
        Returns:
            List of (label, confidence) tuples
        """
        if self.model is None:
            raise ModelNotLoadedError("Model not loaded. Call load_checkpoint first.")
        
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Tokenize batch
            encoding = self.tokenizer(
                batch,
                truncation=True,
                padding='max_length',
                max_length=self.config.max_length,
                return_tensors='pt'
            )
            
            # Predict
            self.model.eval()
            with torch.no_grad():
                outputs = self.model(**encoding)
                logits = outputs.logits
                probabilities = torch.softmax(logits, dim=1)
                
                predicted_classes = torch.argmax(probabilities, dim=1).tolist()
                confidences = probabilities.max(dim=1).values.tolist()
                
                results.extend(zip(predicted_classes, confidences))
        
        return results
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_training_history(self) -> List[TrainingMetrics]:
        """Get training history from last training run."""
        return self.training_history
    
    def get_best_metrics(self) -> Optional[TrainingMetrics]:
        """Get best metrics achieved."""
        return self.best_metrics
    
    def compare_checkpoints(
        self,
        version1: str,
        version2: str
    ) -> Dict[str, Any]:
        """
        Compare two checkpoints.
        
        Args:
            version1: First checkpoint version
            version2: Second checkpoint version
            
        Returns:
            Dictionary with comparison results
        """
        cp1 = self.get_checkpoint(version1)
        cp2 = self.get_checkpoint(version2)
        
        if cp1 is None or cp2 is None:
            return {'error': 'One or both checkpoints not found'}
        
        return {
            'version1': version1,
            'version2': version2,
            'metrics_comparison': {
                'accuracy': {
                    'v1': cp1.metrics.accuracy,
                    'v2': cp2.metrics.accuracy,
                    'diff': cp2.metrics.accuracy - cp1.metrics.accuracy
                },
                'precision': {
                    'v1': cp1.metrics.precision,
                    'v2': cp2.metrics.precision,
                    'diff': cp2.metrics.precision - cp1.metrics.precision
                },
                'recall': {
                    'v1': cp1.metrics.recall,
                    'v2': cp2.metrics.recall,
                    'diff': cp2.metrics.recall - cp1.metrics.recall
                },
                'f1': {
                    'v1': cp1.metrics.f1,
                    'v2': cp2.metrics.f1,
                    'diff': cp2.metrics.f1 - cp1.metrics.f1
                }
            },
            'training_examples': {
                'v1': cp1.training_examples,
                'v2': cp2.training_examples
            },
            'recommendation': 'v2' if cp2.metrics.f1 > cp1.metrics.f1 else 'v1'
        }
    
    def export_checkpoint(self, version: str, export_path: str) -> bool:
        """
        Export checkpoint to specified path.
        
        Args:
            version: Checkpoint version to export
            export_path: Destination path
            
        Returns:
            True if exported successfully
        """
        model_path = f"{self.config.checkpoint_dir}/{version}"
        
        if not Path(model_path).exists():
            logger.error(f"Checkpoint not found: {model_path}")
            return False
        
        try:
            shutil.copytree(model_path, export_path)
            logger.info(f"✅ Exported {version} to {export_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export checkpoint: {e}")
            return False
    
    def import_checkpoint(self, import_path: str, version: str) -> bool:
        """
        Import checkpoint from specified path.
        
        Args:
            import_path: Source path
            version: Version name for imported checkpoint
            
        Returns:
            True if imported successfully
        """
        if not Path(import_path).exists():
            logger.error(f"Import path not found: {import_path}")
            return False
        
        dest_path = f"{self.config.checkpoint_dir}/{version}"
        
        try:
            shutil.copytree(import_path, dest_path)
            
            # Reload checkpoints
            self._load_existing_checkpoints()
            
            logger.info(f"✅ Imported checkpoint as {version}")
            return True
        except Exception as e:
            logger.error(f"Failed to import checkpoint: {e}")
            return False
