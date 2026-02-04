"""
Active Learner - Uncertainty Sampling for Efficient Labeling.

This module implements active learning strategies to reduce labeling burden
by identifying the most valuable examples for physician review.

Strategies:
- Least Confident: Select examples with lowest model confidence
- Margin Sampling: Select examples with smallest margin between top classes
- Entropy Sampling: Select examples with highest prediction entropy
- Diversity Sampling: Select diverse representative examples via clustering
- Hybrid: Combine uncertainty and diversity for optimal selection

Expected Benefit:
- Reduce labeling from 1000 examples to 400 (60% reduction)
- Achieve same model accuracy with less labeling effort
- Focus physician time on genuinely ambiguous cases

Example:
    from phoenix_guardian.learning import (
        ActiveLearner, ActiveLearningConfig, UnlabeledExample, QueryStrategy
    )
    
    config = ActiveLearningConfig(
        query_strategy=QueryStrategy.HYBRID,
        batch_size=50,
        uncertainty_threshold=0.7
    )
    
    learner = ActiveLearner(model_path="models/checkpoints/v1", config=config)
    requests = learner.select_for_labeling(unlabeled_pool)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set, Callable
from enum import Enum
from datetime import datetime
import uuid
import logging
import math

# Third-party imports - may not be available in all environments
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

try:
    from sklearn.cluster import KMeans
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    KMeans = None
    cosine_similarity = None

try:
    from scipy.stats import entropy as scipy_entropy
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    scipy_entropy = None

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    AutoTokenizer = None
    AutoModelForSequenceClassification = None

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_BATCH_SIZE = 50
DEFAULT_UNCERTAINTY_THRESHOLD = 0.7
DEFAULT_DIVERSITY_WEIGHT = 0.3
DEFAULT_MIN_MARGIN = 0.1
DEFAULT_MAX_ENTROPY = 0.8
DEFAULT_N_CLUSTERS = 10
DEFAULT_MAX_LENGTH = 512

# Priority thresholds
CRITICAL_THRESHOLD = 0.55
HIGH_THRESHOLD = 0.65
MEDIUM_THRESHOLD = 0.75


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class QueryStrategy(str, Enum):
    """Active learning query strategy."""
    LEAST_CONFIDENT = "least_confident"
    MARGIN_SAMPLING = "margin_sampling"
    ENTROPY_SAMPLING = "entropy_sampling"
    DIVERSITY_SAMPLING = "diversity_sampling"
    HYBRID = "hybrid"  # Combine uncertainty + diversity
    RANDOM = "random"  # Random baseline for comparison


class LabelingPriority(str, Enum):
    """Priority for labeling request."""
    CRITICAL = "critical"  # Model very uncertain, high impact
    HIGH = "high"  # Uncertain, moderate impact
    MEDIUM = "medium"  # Somewhat uncertain
    LOW = "low"  # Less urgent


class ExampleSource(str, Enum):
    """Source of unlabeled example."""
    PRODUCTION = "production"
    TEST = "test"
    SYNTHETIC = "synthetic"
    IMPORT = "import"


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class ActiveLearnerError(Exception):
    """Base exception for active learner errors."""
    pass


class ModelNotLoadedError(ActiveLearnerError):
    """Raised when model is not loaded."""
    pass


class EmptyPoolError(ActiveLearnerError):
    """Raised when unlabeled pool is empty."""
    pass


class DependencyError(ActiveLearnerError):
    """Raised when required dependencies are not available."""
    pass


class InvalidStrategyError(ActiveLearnerError):
    """Raised when invalid query strategy is specified."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class UnlabeledExample:
    """
    Example without a label (needs physician review).
    
    Attributes:
        text: Input text to be classified
        example_id: Unique identifier for the example
        context: Additional context (e.g., patient info, session)
        source: Origin of the example
        metadata: Additional metadata
        created_at: When the example was created
    """
    text: str
    example_id: str = ""
    context: Optional[Dict[str, Any]] = None
    source: str = ExampleSource.PRODUCTION.value
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate and set defaults."""
        if not self.text or not self.text.strip():
            raise ValueError("Example text cannot be empty")
        
        if not self.example_id:
            self.example_id = str(uuid.uuid4())
        
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'text': self.text,
            'example_id': self.example_id,
            'context': self.context,
            'source': self.source,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnlabeledExample':
        """Create from dictionary."""
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        return cls(
            text=data['text'],
            example_id=data.get('example_id', ''),
            context=data.get('context'),
            source=data.get('source', ExampleSource.PRODUCTION.value),
            metadata=data.get('metadata'),
            created_at=created_at
        )


@dataclass
class PredictionUncertainty:
    """
    Uncertainty metrics for a prediction.
    
    Attributes:
        confidence: Maximum probability (higher = more confident)
        margin: Difference between top 2 probabilities (smaller = more uncertain)
        entropy: Shannon entropy of distribution (higher = more uncertain)
        predicted_class: Predicted class label
        probabilities: Full probability distribution
    """
    confidence: float
    margin: float
    entropy: float
    predicted_class: int
    probabilities: List[float]
    
    def __post_init__(self):
        """Validate metrics."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")
        
        if self.margin < 0:
            raise ValueError(f"Margin must be non-negative, got {self.margin}")
        
        if self.entropy < 0:
            raise ValueError(f"Entropy must be non-negative, got {self.entropy}")
    
    @property
    def is_uncertain(self) -> bool:
        """Check if prediction is uncertain (confidence < 0.7)."""
        return self.confidence < DEFAULT_UNCERTAINTY_THRESHOLD
    
    @property
    def uncertainty_score(self) -> float:
        """Combined uncertainty score (0-1, higher = more uncertain)."""
        # Combine metrics: low confidence, small margin, high entropy
        conf_score = 1 - self.confidence
        margin_score = 1 - min(self.margin, 1.0)
        entropy_score = min(self.entropy, 1.0)
        
        return (conf_score + margin_score + entropy_score) / 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'confidence': self.confidence,
            'margin': self.margin,
            'entropy': self.entropy,
            'predicted_class': self.predicted_class,
            'probabilities': self.probabilities,
            'is_uncertain': self.is_uncertain,
            'uncertainty_score': self.uncertainty_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PredictionUncertainty':
        """Create from dictionary."""
        return cls(
            confidence=data['confidence'],
            margin=data['margin'],
            entropy=data['entropy'],
            predicted_class=data['predicted_class'],
            probabilities=data['probabilities']
        )


@dataclass
class LabelingRequest:
    """
    Request for physician to label an example.
    
    Attributes:
        request_id: Unique identifier for the request
        example: The unlabeled example
        uncertainty: Uncertainty metrics for the prediction
        priority: Labeling priority
        suggested_label: Model's suggested label
        explanation: Human-readable explanation
        created_at: When the request was created
        expires_at: When the request expires
        assigned_to: Physician assigned to label
    """
    request_id: str
    example: UnlabeledExample
    uncertainty: PredictionUncertainty
    priority: LabelingPriority
    suggested_label: Optional[int] = None
    explanation: str = ""
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    
    def __post_init__(self):
        """Set defaults."""
        if self.created_at is None:
            self.created_at = datetime.now()
    
    @property
    def is_expired(self) -> bool:
        """Check if request has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'request_id': self.request_id,
            'example': self.example.to_dict(),
            'uncertainty': self.uncertainty.to_dict(),
            'priority': self.priority.value,
            'suggested_label': self.suggested_label,
            'explanation': self.explanation,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'assigned_to': self.assigned_to
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LabelingRequest':
        """Create from dictionary."""
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        expires_at = data.get('expires_at')
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        return cls(
            request_id=data['request_id'],
            example=UnlabeledExample.from_dict(data['example']),
            uncertainty=PredictionUncertainty.from_dict(data['uncertainty']),
            priority=LabelingPriority(data['priority']),
            suggested_label=data.get('suggested_label'),
            explanation=data.get('explanation', ''),
            created_at=created_at,
            expires_at=expires_at,
            assigned_to=data.get('assigned_to')
        )


@dataclass
class ActiveLearningConfig:
    """
    Configuration for active learning.
    
    Attributes:
        query_strategy: Strategy for selecting examples
        batch_size: Number of examples to request per batch
        uncertainty_threshold: Only query if confidence < threshold
        diversity_weight: Weight for diversity in hybrid sampling (0-1)
        min_margin: Minimum margin to be considered uncertain
        max_entropy: Maximum entropy threshold for entropy sampling
        clustering_n_clusters: Number of clusters for diversity sampling
        max_length: Maximum sequence length for tokenization
        include_explanation: Whether to generate explanations
        auto_assign: Automatically assign requests to physicians
    """
    query_strategy: QueryStrategy = QueryStrategy.HYBRID
    batch_size: int = DEFAULT_BATCH_SIZE
    uncertainty_threshold: float = DEFAULT_UNCERTAINTY_THRESHOLD
    diversity_weight: float = DEFAULT_DIVERSITY_WEIGHT
    min_margin: float = DEFAULT_MIN_MARGIN
    max_entropy: float = DEFAULT_MAX_ENTROPY
    clustering_n_clusters: int = DEFAULT_N_CLUSTERS
    max_length: int = DEFAULT_MAX_LENGTH
    include_explanation: bool = True
    auto_assign: bool = False
    
    def __post_init__(self):
        """Validate configuration."""
        if self.batch_size < 1:
            raise ValueError(f"Batch size must be at least 1, got {self.batch_size}")
        
        if not (0.0 < self.uncertainty_threshold <= 1.0):
            raise ValueError(f"Uncertainty threshold must be between 0 and 1, got {self.uncertainty_threshold}")
        
        if not (0.0 <= self.diversity_weight <= 1.0):
            raise ValueError(f"Diversity weight must be between 0 and 1, got {self.diversity_weight}")
        
        if self.clustering_n_clusters < 1:
            raise ValueError(f"Number of clusters must be at least 1, got {self.clustering_n_clusters}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'query_strategy': self.query_strategy.value,
            'batch_size': self.batch_size,
            'uncertainty_threshold': self.uncertainty_threshold,
            'diversity_weight': self.diversity_weight,
            'min_margin': self.min_margin,
            'max_entropy': self.max_entropy,
            'clustering_n_clusters': self.clustering_n_clusters,
            'max_length': self.max_length,
            'include_explanation': self.include_explanation,
            'auto_assign': self.auto_assign
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActiveLearningConfig':
        """Create from dictionary."""
        strategy = data.get('query_strategy', QueryStrategy.HYBRID.value)
        if isinstance(strategy, str):
            strategy = QueryStrategy(strategy)
        
        return cls(
            query_strategy=strategy,
            batch_size=data.get('batch_size', DEFAULT_BATCH_SIZE),
            uncertainty_threshold=data.get('uncertainty_threshold', DEFAULT_UNCERTAINTY_THRESHOLD),
            diversity_weight=data.get('diversity_weight', DEFAULT_DIVERSITY_WEIGHT),
            min_margin=data.get('min_margin', DEFAULT_MIN_MARGIN),
            max_entropy=data.get('max_entropy', DEFAULT_MAX_ENTROPY),
            clustering_n_clusters=data.get('clustering_n_clusters', DEFAULT_N_CLUSTERS),
            max_length=data.get('max_length', DEFAULT_MAX_LENGTH),
            include_explanation=data.get('include_explanation', True),
            auto_assign=data.get('auto_assign', False)
        )


@dataclass
class LabelingStats:
    """
    Statistics for active learning.
    
    Attributes:
        total_pool_size: Size of original unlabeled pool
        selected_count: Number of examples selected for labeling
        labeled_count: Number of examples labeled
        pending_count: Number of pending requests
        by_priority: Counts by priority level
        by_strategy: Strategy used
        reduction_rate: Percentage reduction in labeling
    """
    total_pool_size: int
    selected_count: int
    labeled_count: int
    pending_count: int
    by_priority: Dict[str, int]
    by_strategy: str
    reduction_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_pool_size': self.total_pool_size,
            'selected_count': self.selected_count,
            'labeled_count': self.labeled_count,
            'pending_count': self.pending_count,
            'by_priority': self.by_priority,
            'by_strategy': self.by_strategy,
            'reduction_rate': self.reduction_rate
        }


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_entropy(probabilities: List[float]) -> float:
    """
    Calculate Shannon entropy of probability distribution.
    
    Args:
        probabilities: Probability distribution
        
    Returns:
        Entropy value (higher = more uncertain)
    """
    if SCIPY_AVAILABLE and scipy_entropy is not None:
        return float(scipy_entropy(probabilities, base=2))
    
    # Fallback implementation
    entropy_val = 0.0
    for p in probabilities:
        if p > 0:
            entropy_val -= p * math.log2(p)
    return entropy_val


def calculate_margin(probabilities: List[float]) -> float:
    """
    Calculate margin between top 2 probabilities.
    
    Args:
        probabilities: Probability distribution
        
    Returns:
        Margin value (smaller = more uncertain)
    """
    sorted_probs = sorted(probabilities, reverse=True)
    if len(sorted_probs) >= 2:
        return sorted_probs[0] - sorted_probs[1]
    return sorted_probs[0] if sorted_probs else 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVE LEARNER
# ═══════════════════════════════════════════════════════════════════════════════

class ActiveLearner:
    """
    Active learning system for intelligent example selection.
    
    Reduces labeling burden by identifying the most valuable examples
    for the model to learn from (typically 60%+ reduction).
    
    Example:
        config = ActiveLearningConfig(
            query_strategy=QueryStrategy.HYBRID,
            batch_size=50
        )
        
        learner = ActiveLearner(model_path="models/v1", config=config)
        requests = learner.select_for_labeling(unlabeled_pool)
        
        for request in requests:
            print(f"{request.example.text}: {request.priority.value}")
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        config: Optional[ActiveLearningConfig] = None,
        tokenizer: Any = None,
        model: Any = None
    ):
        """
        Initialize active learner.
        
        Args:
            model_path: Path to trained model checkpoint
            config: Active learning configuration
            tokenizer: Pre-loaded tokenizer (optional)
            model: Pre-loaded model (optional)
        """
        self.config = config or ActiveLearningConfig()
        self.model_path = model_path
        
        # Initialize model and tokenizer
        self.tokenizer = tokenizer
        self.model = model
        self._model_loaded = False
        
        # Device selection
        self.device = None
        if TORCH_AVAILABLE and torch is not None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Load model if path provided and model not pre-loaded
        if model_path and self.model is None:
            self._load_model(model_path)
        elif self.model is not None:
            self._model_loaded = True
        
        # Track labeling requests
        self.pending_requests: List[LabelingRequest] = []
        self.labeled_examples: Set[str] = set()
        self.total_pool_size: int = 0
        
        logger.info(f"ActiveLearner initialized with strategy: {self.config.query_strategy.value}")
    
    def _load_model(self, model_path: str):
        """Load model and tokenizer from checkpoint."""
        if not TRANSFORMERS_AVAILABLE:
            logger.warning("Transformers not available, model loading skipped")
            return
        
        try:
            logger.info(f"Loading model from {model_path}...")
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
            self.model.eval()
            
            if self.device is not None:
                self.model.to(self.device)
            
            self._model_loaded = True
            logger.info("✅ Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise ModelNotLoadedError(f"Failed to load model from {model_path}: {e}")
    
    def _ensure_model_loaded(self):
        """Ensure model is loaded before prediction."""
        if not self._model_loaded or self.model is None:
            raise ModelNotLoadedError("Model not loaded. Provide model_path or pre-loaded model.")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PREDICTION WITH UNCERTAINTY
    # ═══════════════════════════════════════════════════════════════════════════
    
    def predict_with_uncertainty(self, text: str) -> PredictionUncertainty:
        """
        Make prediction with uncertainty metrics.
        
        Args:
            text: Input text to classify
            
        Returns:
            PredictionUncertainty with confidence, margin, entropy
        """
        self._ensure_model_loaded()
        
        if not TORCH_AVAILABLE or torch is None:
            raise DependencyError("PyTorch is required for prediction")
        
        # Tokenize
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self.config.max_length,
            padding=True
        )
        
        if self.device is not None:
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Predict
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
        
        # Calculate uncertainty metrics
        confidence = float(np.max(probs))
        predicted_class = int(np.argmax(probs))
        margin = calculate_margin(probs.tolist())
        prob_entropy = calculate_entropy(probs.tolist())
        
        return PredictionUncertainty(
            confidence=confidence,
            margin=margin,
            entropy=prob_entropy,
            predicted_class=predicted_class,
            probabilities=probs.tolist()
        )
    
    def predict_batch_with_uncertainty(
        self,
        texts: List[str],
        batch_size: int = 32
    ) -> List[PredictionUncertainty]:
        """
        Batch prediction with uncertainty.
        
        Args:
            texts: List of input texts
            batch_size: Batch size for processing
            
        Returns:
            List of PredictionUncertainty objects
        """
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            for text in batch:
                results.append(self.predict_with_uncertainty(text))
        
        return results
    
    # ═══════════════════════════════════════════════════════════════════════════
    # QUERY STRATEGIES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def select_for_labeling(
        self,
        unlabeled_pool: List[UnlabeledExample]
    ) -> List[LabelingRequest]:
        """
        Select most valuable examples for labeling.
        
        Args:
            unlabeled_pool: Pool of unlabeled examples
            
        Returns:
            List of LabelingRequest objects (prioritized)
        """
        if not unlabeled_pool:
            logger.warning("Empty unlabeled pool provided")
            return []
        
        self.total_pool_size = len(unlabeled_pool)
        logger.info(f"Selecting up to {self.config.batch_size} examples from pool of {len(unlabeled_pool)}...")
        
        # Filter already labeled examples
        pool = [
            ex for ex in unlabeled_pool
            if ex.example_id not in self.labeled_examples
        ]
        
        if not pool:
            logger.info("All examples already labeled")
            return []
        
        # Get predictions with uncertainty
        uncertainties: List[Tuple[UnlabeledExample, PredictionUncertainty]] = []
        for example in pool:
            try:
                uncertainty = self.predict_with_uncertainty(example.text)
                uncertainties.append((example, uncertainty))
            except Exception as e:
                logger.warning(f"Failed to predict for {example.example_id}: {e}")
        
        if not uncertainties:
            logger.warning("No valid predictions generated")
            return []
        
        # Apply query strategy
        strategy_map = {
            QueryStrategy.LEAST_CONFIDENT: self._least_confident_sampling,
            QueryStrategy.MARGIN_SAMPLING: self._margin_sampling,
            QueryStrategy.ENTROPY_SAMPLING: self._entropy_sampling,
            QueryStrategy.DIVERSITY_SAMPLING: lambda u: self._diversity_sampling(u, pool),
            QueryStrategy.HYBRID: lambda u: self._hybrid_sampling(u, pool),
            QueryStrategy.RANDOM: self._random_sampling,
        }
        
        strategy_func = strategy_map.get(self.config.query_strategy)
        if strategy_func is None:
            raise InvalidStrategyError(f"Unknown query strategy: {self.config.query_strategy}")
        
        selected = strategy_func(uncertainties)
        
        # Create labeling requests
        requests = []
        for i, (example, uncertainty) in enumerate(selected):
            priority = self._determine_priority(uncertainty)
            explanation = ""
            if self.config.include_explanation:
                explanation = self._generate_explanation(uncertainty)
            
            request = LabelingRequest(
                request_id=f"req_{example.example_id}_{i}_{uuid.uuid4().hex[:8]}",
                example=example,
                uncertainty=uncertainty,
                priority=priority,
                suggested_label=uncertainty.predicted_class,
                explanation=explanation
            )
            requests.append(request)
        
        # Sort by priority
        priority_order = {
            LabelingPriority.CRITICAL: 0,
            LabelingPriority.HIGH: 1,
            LabelingPriority.MEDIUM: 2,
            LabelingPriority.LOW: 3
        }
        requests.sort(key=lambda r: priority_order[r.priority])
        
        self.pending_requests.extend(requests)
        logger.info(f"✅ Selected {len(requests)} examples for labeling")
        
        return requests
    
    def _least_confident_sampling(
        self,
        uncertainties: List[Tuple[UnlabeledExample, PredictionUncertainty]]
    ) -> List[Tuple[UnlabeledExample, PredictionUncertainty]]:
        """
        Select examples with lowest confidence.
        
        Least confident examples are where the model is most unsure,
        making them valuable for learning decision boundaries.
        """
        # Sort by confidence (ascending - lowest first)
        sorted_uncertain = sorted(
            uncertainties,
            key=lambda x: x[1].confidence
        )
        
        # Filter by threshold
        filtered = [
            (ex, unc) for ex, unc in sorted_uncertain
            if unc.confidence < self.config.uncertainty_threshold
        ]
        
        # If not enough filtered, use all sorted
        if len(filtered) < self.config.batch_size:
            filtered = sorted_uncertain
        
        return filtered[:self.config.batch_size]
    
    def _margin_sampling(
        self,
        uncertainties: List[Tuple[UnlabeledExample, PredictionUncertainty]]
    ) -> List[Tuple[UnlabeledExample, PredictionUncertainty]]:
        """
        Select examples with smallest margin between top 2 classes.
        
        Small margins indicate the model is torn between two classes,
        making these examples informative for learning.
        """
        # Sort by margin (ascending - smallest margins first)
        sorted_uncertain = sorted(
            uncertainties,
            key=lambda x: x[1].margin
        )
        
        # Filter by threshold
        filtered = [
            (ex, unc) for ex, unc in sorted_uncertain
            if unc.margin < self.config.min_margin * 2  # Relaxed threshold
        ]
        
        # If not enough filtered, use all sorted
        if len(filtered) < self.config.batch_size:
            filtered = sorted_uncertain
        
        return filtered[:self.config.batch_size]
    
    def _entropy_sampling(
        self,
        uncertainties: List[Tuple[UnlabeledExample, PredictionUncertainty]]
    ) -> List[Tuple[UnlabeledExample, PredictionUncertainty]]:
        """
        Select examples with highest prediction entropy.
        
        High entropy indicates maximum uncertainty about the
        class distribution.
        """
        # Sort by entropy (descending - highest entropy first)
        sorted_uncertain = sorted(
            uncertainties,
            key=lambda x: x[1].entropy,
            reverse=True
        )
        
        # Filter by threshold
        filtered = [
            (ex, unc) for ex, unc in sorted_uncertain
            if unc.entropy > self.config.max_entropy * 0.5  # Relaxed threshold
        ]
        
        # If not enough filtered, use all sorted
        if len(filtered) < self.config.batch_size:
            filtered = sorted_uncertain
        
        return filtered[:self.config.batch_size]
    
    def _diversity_sampling(
        self,
        uncertainties: List[Tuple[UnlabeledExample, PredictionUncertainty]],
        unlabeled_pool: List[UnlabeledExample]
    ) -> List[Tuple[UnlabeledExample, PredictionUncertainty]]:
        """
        Select diverse examples using embedding clustering.
        
        Strategy:
        1. Get embeddings for all examples
        2. Cluster embeddings into K clusters
        3. Select most uncertain example from each cluster
        """
        if not SKLEARN_AVAILABLE or KMeans is None:
            logger.warning("sklearn not available, falling back to least confident")
            return self._least_confident_sampling(uncertainties)
        
        if not NUMPY_AVAILABLE or np is None:
            logger.warning("numpy not available, falling back to least confident")
            return self._least_confident_sampling(uncertainties)
        
        # Get embeddings
        try:
            embeddings = self._get_embeddings([ex.text for ex, _ in uncertainties])
        except Exception as e:
            logger.warning(f"Embedding extraction failed: {e}, falling back to least confident")
            return self._least_confident_sampling(uncertainties)
        
        # Cluster embeddings
        n_clusters = min(self.config.clustering_n_clusters, len(embeddings))
        if n_clusters < 2:
            return self._least_confident_sampling(uncertainties)
        
        try:
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(embeddings)
        except Exception as e:
            logger.warning(f"Clustering failed: {e}, falling back to least confident")
            return self._least_confident_sampling(uncertainties)
        
        # Select most uncertain from each cluster
        selected = []
        for cluster_id in range(n_clusters):
            # Get examples in this cluster
            cluster_examples = [
                (ex, unc) for (ex, unc), label in zip(uncertainties, cluster_labels)
                if label == cluster_id
            ]
            
            if cluster_examples:
                # Select least confident in cluster
                most_uncertain = min(cluster_examples, key=lambda x: x[1].confidence)
                selected.append(most_uncertain)
        
        return selected[:self.config.batch_size]
    
    def _hybrid_sampling(
        self,
        uncertainties: List[Tuple[UnlabeledExample, PredictionUncertainty]],
        unlabeled_pool: List[UnlabeledExample]
    ) -> List[Tuple[UnlabeledExample, PredictionUncertainty]]:
        """
        Hybrid strategy: Combine uncertainty + diversity.
        
        Strategy:
        1. Score each example by uncertainty (1 - confidence)
        2. Score each example by diversity (distance to cluster center)
        3. Final score = α * uncertainty + (1-α) * diversity
        4. Select top K by final score
        """
        if not SKLEARN_AVAILABLE or not NUMPY_AVAILABLE:
            logger.warning("Required libraries not available, falling back to least confident")
            return self._least_confident_sampling(uncertainties)
        
        alpha = 1 - self.config.diversity_weight  # Uncertainty weight
        
        # Get embeddings
        try:
            embeddings = self._get_embeddings([ex.text for ex, _ in uncertainties])
        except Exception as e:
            logger.warning(f"Embedding extraction failed: {e}, falling back to least confident")
            return self._least_confident_sampling(uncertainties)
        
        # Cluster for diversity
        n_clusters = min(self.config.clustering_n_clusters, len(embeddings))
        if n_clusters < 2:
            return self._least_confident_sampling(uncertainties)
        
        try:
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            kmeans.fit(embeddings)
        except Exception as e:
            logger.warning(f"Clustering failed: {e}, falling back to least confident")
            return self._least_confident_sampling(uncertainties)
        
        # Calculate scores
        scored = []
        max_diversity = 0.0
        
        # First pass: calculate diversity scores
        diversity_scores = []
        for emb in embeddings:
            cluster_id = kmeans.predict([emb])[0]
            cluster_center = kmeans.cluster_centers_[cluster_id]
            diversity = float(np.linalg.norm(emb - cluster_center))
            diversity_scores.append(diversity)
            max_diversity = max(max_diversity, diversity)
        
        # Normalize and combine scores
        for i, ((ex, unc), diversity) in enumerate(zip(uncertainties, diversity_scores)):
            # Uncertainty score (0-1, higher = more uncertain)
            uncertainty_score = 1 - unc.confidence
            
            # Diversity score (normalized to 0-1)
            diversity_score = diversity / max_diversity if max_diversity > 0 else 0
            
            # Combined score
            final_score = alpha * uncertainty_score + (1 - alpha) * diversity_score
            
            scored.append((ex, unc, final_score))
        
        # Sort by final score (descending)
        scored.sort(key=lambda x: x[2], reverse=True)
        
        # Return top K
        return [(ex, unc) for ex, unc, _ in scored[:self.config.batch_size]]
    
    def _random_sampling(
        self,
        uncertainties: List[Tuple[UnlabeledExample, PredictionUncertainty]]
    ) -> List[Tuple[UnlabeledExample, PredictionUncertainty]]:
        """Random sampling baseline for comparison."""
        if NUMPY_AVAILABLE and np is not None:
            indices = np.random.permutation(len(uncertainties))[:self.config.batch_size]
            return [uncertainties[i] for i in indices]
        
        import random
        sample_size = min(self.config.batch_size, len(uncertainties))
        return random.sample(uncertainties, sample_size)
    
    def _get_embeddings(self, texts: List[str]) -> 'np.ndarray':
        """
        Get embeddings for texts using the model.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            numpy array of embeddings
        """
        self._ensure_model_loaded()
        
        if not NUMPY_AVAILABLE or np is None:
            raise DependencyError("numpy is required for embeddings")
        
        embeddings = []
        
        for text in texts:
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=self.config.max_length,
                padding=True
            )
            
            if self.device is not None:
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                # Try to get embeddings from the base model
                if hasattr(self.model, 'roberta'):
                    outputs = self.model.roberta(**inputs)
                elif hasattr(self.model, 'bert'):
                    outputs = self.model.bert(**inputs)
                elif hasattr(self.model, 'base_model'):
                    outputs = self.model.base_model(**inputs)
                else:
                    # Fallback: use the full model output
                    outputs = self.model(**inputs, output_hidden_states=True)
                    if hasattr(outputs, 'hidden_states') and outputs.hidden_states:
                        embedding = outputs.hidden_states[-1][:, 0, :].cpu().numpy()[0]
                    else:
                        # Use logits as features
                        embedding = outputs.logits.cpu().numpy()[0]
                    embeddings.append(embedding)
                    continue
                
                # Use CLS token embedding
                embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()[0]
                embeddings.append(embedding)
        
        return np.array(embeddings)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIORITY & EXPLANATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _determine_priority(self, uncertainty: PredictionUncertainty) -> LabelingPriority:
        """
        Determine labeling priority based on uncertainty.
        
        Args:
            uncertainty: Prediction uncertainty metrics
            
        Returns:
            LabelingPriority based on confidence level
        """
        if uncertainty.confidence < CRITICAL_THRESHOLD:
            return LabelingPriority.CRITICAL
        elif uncertainty.confidence < HIGH_THRESHOLD:
            return LabelingPriority.HIGH
        elif uncertainty.confidence < MEDIUM_THRESHOLD:
            return LabelingPriority.MEDIUM
        else:
            return LabelingPriority.LOW
    
    def _generate_explanation(self, uncertainty: PredictionUncertainty) -> str:
        """
        Generate human-readable explanation of uncertainty.
        
        Args:
            uncertainty: Prediction uncertainty metrics
            
        Returns:
            Explanation string for physicians
        """
        predicted = "threat" if uncertainty.predicted_class == 1 else "benign"
        
        if uncertainty.confidence < CRITICAL_THRESHOLD:
            return (
                f"Model is very uncertain (confidence: {uncertainty.confidence:.1%}). "
                f"Predicted as '{predicted}' but needs verification. "
                f"Entropy: {uncertainty.entropy:.2f}, Margin: {uncertainty.margin:.2f}"
            )
        elif uncertainty.confidence < HIGH_THRESHOLD:
            return (
                f"Model is somewhat uncertain (confidence: {uncertainty.confidence:.1%}). "
                f"Predicted as '{predicted}' with low confidence."
            )
        elif uncertainty.confidence < MEDIUM_THRESHOLD:
            return (
                f"Model predicted '{predicted}' with {uncertainty.confidence:.1%} confidence. "
                f"Margin between classes is small ({uncertainty.margin:.2f})."
            )
        else:
            return (
                f"Model predicted '{predicted}' with {uncertainty.confidence:.1%} confidence. "
                f"Included for diversity coverage."
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LABELING WORKFLOW
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_pending_requests(
        self,
        priority: Optional[LabelingPriority] = None,
        limit: Optional[int] = None
    ) -> List[LabelingRequest]:
        """
        Get pending labeling requests.
        
        Args:
            priority: Filter by priority level
            limit: Maximum number of requests to return
            
        Returns:
            List of pending LabelingRequest objects
        """
        requests = self.pending_requests.copy()
        
        # Filter by priority
        if priority is not None:
            requests = [r for r in requests if r.priority == priority]
        
        # Filter expired
        requests = [r for r in requests if not r.is_expired]
        
        # Apply limit
        if limit is not None:
            requests = requests[:limit]
        
        return requests
    
    def get_request_by_id(self, request_id: str) -> Optional[LabelingRequest]:
        """Get a specific labeling request by ID."""
        for request in self.pending_requests:
            if request.request_id == request_id:
                return request
        return None
    
    def mark_as_labeled(
        self,
        request_id: str,
        label: int,
        labeler_id: Optional[str] = None
    ) -> bool:
        """
        Mark request as labeled by physician.
        
        Args:
            request_id: Request ID to mark
            label: Label assigned by physician
            labeler_id: ID of physician who labeled
            
        Returns:
            True if successfully marked, False if not found
        """
        for request in self.pending_requests:
            if request.request_id == request_id:
                self.labeled_examples.add(request.example.example_id)
                self.pending_requests.remove(request)
                logger.info(f"✅ Marked {request_id} as labeled (label={label})")
                return True
        
        logger.warning(f"Request not found: {request_id}")
        return False
    
    def mark_batch_as_labeled(
        self,
        labels: Dict[str, int]
    ) -> Tuple[int, int]:
        """
        Mark multiple requests as labeled.
        
        Args:
            labels: Dictionary mapping request_id to label
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        success = 0
        failed = 0
        
        for request_id, label in labels.items():
            if self.mark_as_labeled(request_id, label):
                success += 1
            else:
                failed += 1
        
        return success, failed
    
    def cancel_request(self, request_id: str) -> bool:
        """
        Cancel a pending labeling request.
        
        Args:
            request_id: Request ID to cancel
            
        Returns:
            True if successfully cancelled, False if not found
        """
        for request in self.pending_requests:
            if request.request_id == request_id:
                self.pending_requests.remove(request)
                logger.info(f"Cancelled request: {request_id}")
                return True
        
        logger.warning(f"Request not found: {request_id}")
        return False
    
    def clear_pending_requests(self):
        """Clear all pending requests."""
        count = len(self.pending_requests)
        self.pending_requests.clear()
        logger.info(f"Cleared {count} pending requests")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_labeling_stats(self) -> LabelingStats:
        """
        Get active learning statistics.
        
        Returns:
            LabelingStats with counts and reduction rate
        """
        by_priority = {
            priority.value: len([
                r for r in self.pending_requests
                if r.priority == priority
            ])
            for priority in LabelingPriority
        }
        
        selected_count = len(self.pending_requests) + len(self.labeled_examples)
        
        # Calculate reduction rate
        if self.total_pool_size > 0:
            reduction_rate = 1 - (selected_count / self.total_pool_size)
        else:
            reduction_rate = 0.0
        
        return LabelingStats(
            total_pool_size=self.total_pool_size,
            selected_count=selected_count,
            labeled_count=len(self.labeled_examples),
            pending_count=len(self.pending_requests),
            by_priority=by_priority,
            by_strategy=self.config.query_strategy.value,
            reduction_rate=reduction_rate
        )
    
    def get_stats_dict(self) -> Dict[str, Any]:
        """Get statistics as dictionary (for API responses)."""
        stats = self.get_labeling_stats()
        return stats.to_dict()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def reset(self):
        """Reset learner state."""
        self.pending_requests.clear()
        self.labeled_examples.clear()
        self.total_pool_size = 0
        logger.info("ActiveLearner state reset")
    
    def export_requests(self) -> List[Dict[str, Any]]:
        """Export pending requests as list of dictionaries."""
        return [r.to_dict() for r in self.pending_requests]
    
    def import_requests(self, requests_data: List[Dict[str, Any]]):
        """Import requests from list of dictionaries."""
        for data in requests_data:
            request = LabelingRequest.from_dict(data)
            self.pending_requests.append(request)
        logger.info(f"Imported {len(requests_data)} requests")
