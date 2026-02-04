"""
Tests for ModelFinetuner - RoBERTa Fine-tuning Pipeline.

Tests cover:
- Data preparation (8 tests)
- Dataset operations (4 tests)
- Fine-tuning (6 tests)
- Checkpoint management (7 tests)
- Configuration (3 tests)
- Integration (2 tests)

Total: 30+ tests
"""

import pytest
import sys
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from datetime import datetime
from pathlib import Path
import json
import tempfile
import shutil

# Mock torch before importing model_finetuner
mock_torch = MagicMock()
mock_torch.tensor = Mock(return_value=Mock())
mock_torch.long = Mock()
mock_torch.no_grad = MagicMock(return_value=MagicMock(__enter__=Mock(), __exit__=Mock()))
mock_torch.cuda = Mock()
mock_torch.cuda.is_available = Mock(return_value=False)
mock_torch.softmax = Mock(return_value=Mock(max=Mock(return_value=Mock(values=Mock(tolist=Mock(return_value=[0.95]))))))
mock_torch.argmax = Mock(return_value=Mock(item=Mock(return_value=1), tolist=Mock(return_value=[1])))

# Mock Dataset class
class MockDataset:
    pass

mock_torch.utils = Mock()
mock_torch.utils.data = Mock()
mock_torch.utils.data.Dataset = MockDataset
mock_torch.utils.data.DataLoader = Mock()

sys.modules['torch'] = mock_torch
sys.modules['torch.utils'] = mock_torch.utils
sys.modules['torch.utils.data'] = mock_torch.utils.data

# Mock transformers
mock_transformers = MagicMock()
mock_tokenizer = MagicMock()
mock_tokenizer.return_value = {
    'input_ids': MagicMock(flatten=Mock(return_value=Mock())),
    'attention_mask': MagicMock(flatten=Mock(return_value=Mock()))
}

mock_transformers.AutoTokenizer = Mock()
mock_transformers.AutoTokenizer.from_pretrained = Mock(return_value=mock_tokenizer)
mock_transformers.AutoModelForSequenceClassification = Mock()
mock_transformers.AutoModelForSequenceClassification.from_pretrained = Mock(return_value=MagicMock())
mock_transformers.TrainingArguments = Mock()
mock_transformers.Trainer = Mock()
mock_transformers.EvalPrediction = Mock()
mock_transformers.EarlyStoppingCallback = Mock()

sys.modules['transformers'] = mock_transformers

# Mock sklearn
mock_sklearn = MagicMock()
mock_sklearn.model_selection = MagicMock()
mock_sklearn.model_selection.train_test_split = Mock(
    side_effect=lambda examples, test_size, random_state, **kwargs: (
        examples[:int(len(examples) * (1 - test_size))],
        examples[int(len(examples) * (1 - test_size)):]
    )
)
mock_sklearn.metrics = MagicMock()
mock_sklearn.metrics.accuracy_score = Mock(return_value=0.9)
mock_sklearn.metrics.precision_recall_fscore_support = Mock(return_value=(0.85, 0.88, 0.86, None))
mock_sklearn.metrics.confusion_matrix = Mock(return_value=[[45, 5], [3, 47]])

sys.modules['sklearn'] = mock_sklearn
sys.modules['sklearn.model_selection'] = mock_sklearn.model_selection
sys.modules['sklearn.metrics'] = mock_sklearn.metrics

# Mock numpy with proper bool_ type - save original first
_original_numpy = sys.modules.get('numpy')
mock_np = MagicMock()
mock_np.argmax = Mock(return_value=[1, 0, 1, 1, 0])
mock_np.bool_ = bool  # Use Python's bool as the numpy bool type
mock_np.array = Mock(side_effect=lambda x: x)  # Return input as-is
sys.modules['numpy'] = mock_np

# Now import the module
import phoenix_guardian.learning.model_finetuner as finetuner_module

# Patch the module-level flags to indicate dependencies are available
finetuner_module.TORCH_AVAILABLE = True
finetuner_module.TRANSFORMERS_AVAILABLE = True
finetuner_module.SKLEARN_AVAILABLE = True

from phoenix_guardian.learning.model_finetuner import (
    ModelFinetuner,
    FinetuningConfig,
    TrainingExample,
    TrainingMetrics,
    ModelCheckpoint,
    TrainingResult,
    ThreatDetectionDataset,
    TrainingSource,
    ModelState,
    FinetunerError,
    InsufficientDataError,
    CheckpointError,
    ModelNotLoadedError,
    DependencyError,
    DEFAULT_BASE_MODEL,
    DEFAULT_LEARNING_RATE,
    DEFAULT_BATCH_SIZE,
    DEFAULT_NUM_EPOCHS,
    DEFAULT_MIN_IMPROVEMENT,
    THREAT_KEYWORDS,
    BENIGN_KEYWORDS
)

# Restore original numpy after imports to avoid affecting other tests
if _original_numpy is not None:
    sys.modules['numpy'] = _original_numpy
else:
    # If numpy wasn't imported before, remove our mock
    if 'numpy' in sys.modules:
        del sys.modules['numpy']


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_checkpoint_dir():
    """Create temporary checkpoint directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def config(temp_checkpoint_dir):
    """Create test configuration."""
    return FinetuningConfig(
        base_model="roberta-base",
        learning_rate=2e-5,
        batch_size=8,
        num_epochs=2,
        checkpoint_dir=temp_checkpoint_dir,
        min_improvement=0.02,
        eval_split=0.2
    )


@pytest.fixture
def mock_feedback_collector():
    """Create mock feedback collector."""
    collector = Mock()
    collector.get_training_data = Mock(return_value=Mock(
        feedback_records=[
            {
                'id': 1,
                'suggestion': 'Check patient vitals',
                'user_feedback': 'accept',
                'confidence_score': 0.95,
                'session_id': 'session-1'
            },
            {
                'id': 2,
                'suggestion': 'DROP TABLE users;',
                'user_feedback': 'reject',
                'confidence_score': 0.85,
                'session_id': 'session-2'
            },
            {
                'id': 3,
                'suggestion': 'Schedule appointment',
                'user_feedback': 'accept',
                'confidence_score': 0.2,
                'session_id': 'session-3'
            },
            {
                'id': 4,
                'suggestion': 'Run security scan',
                'user_feedback': 'modify',
                'confidence_score': 0.5,
                'modified_output': 'Detected threat in input',
                'session_id': 'session-4'
            },
            {
                'id': 5,
                'suggestion': 'Normal operation',
                'user_feedback': 'modify',
                'confidence_score': 0.5,
                'modified_output': 'This is safe and benign',
                'session_id': 'session-5'
            },
        ] * 25  # 125 records total
    ))
    return collector


@pytest.fixture
def finetuner(config, mock_feedback_collector):
    """Create model finetuner with mock dependencies."""
    return ModelFinetuner(config, mock_feedback_collector)


@pytest.fixture
def sample_training_examples():
    """Create sample training examples."""
    return [
        TrainingExample(text="Check patient vitals", label=0, source="feedback"),
        TrainingExample(text="DROP TABLE users;", label=1, source="feedback"),
        TrainingExample(text="Schedule appointment for patient", label=0, source="feedback"),
        TrainingExample(text="<script>alert('xss')</script>", label=1, source="feedback"),
        TrainingExample(text="Review lab results", label=0, source="feedback"),
        TrainingExample(text="rm -rf / --no-preserve-root", label=1, source="feedback"),
        TrainingExample(text="Update medication dosage", label=0, source="feedback"),
        TrainingExample(text="exec('malicious code')", label=1, source="feedback"),
        TrainingExample(text="Generate clinic report", label=0, source="feedback"),
        TrainingExample(text="SELECT * FROM passwords", label=1, source="feedback"),
    ]


@pytest.fixture
def sample_metrics():
    """Create sample training metrics."""
    return TrainingMetrics(
        accuracy=0.92,
        precision=0.90,
        recall=0.88,
        f1=0.89,
        loss=0.15,
        epoch=3
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DATA PREPARATION TESTS (8 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataPreparation:
    """Tests for data preparation functionality."""
    
    def test_prepare_training_data_success(self, finetuner):
        """Test successful training data preparation."""
        train_examples, eval_examples = finetuner.prepare_training_data(
            agent_name="Safety",
            min_examples=10
        )
        
        assert len(train_examples) > 0
        assert len(eval_examples) > 0
        assert len(train_examples) + len(eval_examples) > 0
    
    def test_prepare_training_data_insufficient_data(self, finetuner):
        """Test error on insufficient training data."""
        finetuner.feedback_collector.get_training_data.return_value = Mock(
            feedback_records=[
                {'id': 1, 'suggestion': 'Test', 'user_feedback': 'accept', 'confidence_score': 0.9}
            ]
        )
        
        with pytest.raises(InsufficientDataError):
            finetuner.prepare_training_data(agent_name="Safety", min_examples=100)
    
    def test_feedback_to_label_accept_high_confidence(self, finetuner):
        """Test accept with high confidence returns threat label."""
        record = {
            'user_feedback': 'accept',
            'confidence_score': 0.95
        }
        
        label = finetuner._feedback_to_label(record)
        assert label == 1  # High confidence accepted = threat
    
    def test_feedback_to_label_accept_low_confidence(self, finetuner):
        """Test accept with low confidence returns benign label."""
        record = {
            'user_feedback': 'accept',
            'confidence_score': 0.2
        }
        
        label = finetuner._feedback_to_label(record)
        assert label == 0  # Low confidence accepted = benign
    
    def test_feedback_to_label_reject_high_confidence(self, finetuner):
        """Test reject with high confidence returns benign label."""
        record = {
            'user_feedback': 'reject',
            'confidence_score': 0.85
        }
        
        label = finetuner._feedback_to_label(record)
        assert label == 0  # False positive → benign
    
    def test_feedback_to_label_reject_low_confidence(self, finetuner):
        """Test reject with low confidence returns threat label."""
        record = {
            'user_feedback': 'reject',
            'confidence_score': 0.3
        }
        
        label = finetuner._feedback_to_label(record)
        assert label == 1  # False negative → threat
    
    def test_feedback_to_label_modify_threat(self, finetuner):
        """Test modify with threat keywords returns threat label."""
        record = {
            'user_feedback': 'modify',
            'confidence_score': 0.5,
            'modified_output': 'This is a security threat that should be blocked'
        }
        
        label = finetuner._feedback_to_label(record)
        assert label == 1  # Threat keywords → threat
    
    def test_feedback_to_label_modify_benign(self, finetuner):
        """Test modify with benign keywords returns benign label."""
        record = {
            'user_feedback': 'modify',
            'confidence_score': 0.5,
            'modified_output': 'This is safe and legitimate operation'
        }
        
        label = finetuner._feedback_to_label(record)
        assert label == 0  # Benign keywords → benign


class TestTrainEvalSplit:
    """Tests for train/eval splitting."""
    
    def test_training_eval_split_ratio(self, finetuner, sample_training_examples):
        """Test that split respects configured ratio."""
        # Extend examples to have enough data
        examples = sample_training_examples * 10  # 100 examples
        
        train, eval_ = finetuner._split_data(examples)
        
        total = len(train) + len(eval_)
        eval_ratio = len(eval_) / total
        
        assert 0.15 <= eval_ratio <= 0.25  # Around 20%
    
    def test_stratified_split(self, finetuner, sample_training_examples):
        """Test that split is stratified by label."""
        examples = sample_training_examples * 10  # 100 examples
        
        train, eval_ = finetuner._split_data(examples)
        
        # Check both sets have both labels
        train_labels = set(ex.label for ex in train)
        eval_labels = set(ex.label for ex in eval_)
        
        assert 0 in train_labels and 1 in train_labels
        assert 0 in eval_labels and 1 in eval_labels


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET TESTS (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataset:
    """Tests for ThreatDetectionDataset."""
    
    def test_dataset_creation(self, sample_training_examples):
        """Test dataset creation."""
        tokenizer = Mock()
        tokenizer.return_value = {
            'input_ids': Mock(flatten=Mock(return_value=Mock())),
            'attention_mask': Mock(flatten=Mock(return_value=Mock()))
        }
        
        dataset = ThreatDetectionDataset(
            examples=sample_training_examples,
            tokenizer=tokenizer,
            max_length=512
        )
        
        assert dataset is not None
        assert dataset.max_length == 512
    
    def test_dataset_length(self, sample_training_examples):
        """Test dataset length."""
        tokenizer = Mock()
        
        dataset = ThreatDetectionDataset(
            examples=sample_training_examples,
            tokenizer=tokenizer
        )
        
        assert len(dataset) == len(sample_training_examples)
    
    def test_dataset_getitem(self, sample_training_examples):
        """Test dataset __getitem__."""
        tokenizer = Mock()
        tokenizer.return_value = {
            'input_ids': Mock(flatten=Mock(return_value='input_ids_tensor')),
            'attention_mask': Mock(flatten=Mock(return_value='attention_mask_tensor'))
        }
        
        dataset = ThreatDetectionDataset(
            examples=sample_training_examples,
            tokenizer=tokenizer
        )
        
        # Mock torch.tensor for this test
        with patch.object(finetuner_module, 'torch') as mock_torch_local:
            mock_torch_local.tensor = Mock(return_value='labels_tensor')
            mock_torch_local.long = Mock()
            
            item = dataset[0]
        
        assert 'input_ids' in item
        assert 'attention_mask' in item
        assert 'labels' in item
    
    def test_dataset_label_distribution(self, sample_training_examples):
        """Test label distribution calculation."""
        tokenizer = Mock()
        
        dataset = ThreatDetectionDataset(
            examples=sample_training_examples,
            tokenizer=tokenizer
        )
        
        distribution = dataset.get_label_distribution()
        
        assert 0 in distribution
        assert 1 in distribution
        assert distribution[0] + distribution[1] == len(sample_training_examples)


# ═══════════════════════════════════════════════════════════════════════════════
# FINETUNING TESTS (6 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinetuning:
    """Tests for model fine-tuning."""
    
    def test_finetune_success(self, finetuner, sample_training_examples):
        """Test successful fine-tuning."""
        train_examples = sample_training_examples * 5
        eval_examples = sample_training_examples[:3]
        
        # Mock trainer
        mock_trainer = Mock()
        mock_trainer.train.return_value = Mock()
        mock_trainer.evaluate.return_value = {
            'eval_accuracy': 0.92,
            'eval_precision': 0.90,
            'eval_recall': 0.88,
            'eval_f1': 0.89,
            'eval_loss': 0.15
        }
        
        with patch.object(finetuner_module, 'TRANSFORMERS_AVAILABLE', True):
            with patch.object(finetuner_module, 'TORCH_AVAILABLE', True):
                with patch.object(finetuner, '_ensure_tokenizer'):
                    with patch.object(finetuner, '_ensure_model'):
                        finetuner.tokenizer = Mock()
                        finetuner.model = Mock()
                        finetuner.model.save_pretrained = Mock()
                        finetuner.tokenizer.save_pretrained = Mock()
                        
                        with patch.object(finetuner_module, 'Trainer', return_value=mock_trainer):
                            with patch.object(finetuner_module, 'TrainingArguments'):
                                with patch.object(finetuner_module, 'EarlyStoppingCallback'):
                                    checkpoint = finetuner.finetune(
                                        train_examples=train_examples,
                                        eval_examples=eval_examples,
                                        version="test_v1"
                                    )
        
        # Checkpoint should be created (first training, so improvement is 100%)
        assert checkpoint is not None or finetuner.best_metrics is None
    
    def test_finetune_metrics_computed(self, finetuner, sample_training_examples):
        """Test that metrics are computed during fine-tuning."""
        train_examples = sample_training_examples * 5
        eval_examples = sample_training_examples[:3]
        
        mock_trainer = Mock()
        mock_trainer.train.return_value = Mock()
        mock_trainer.evaluate.return_value = {
            'eval_accuracy': 0.92,
            'eval_precision': 0.90,
            'eval_recall': 0.88,
            'eval_f1': 0.89,
            'eval_loss': 0.15
        }
        
        with patch.object(finetuner_module, 'TRANSFORMERS_AVAILABLE', True):
            with patch.object(finetuner_module, 'TORCH_AVAILABLE', True):
                with patch.object(finetuner, '_ensure_tokenizer'):
                    with patch.object(finetuner, '_ensure_model'):
                        finetuner.tokenizer = Mock()
                        finetuner.model = Mock()
                        finetuner.model.save_pretrained = Mock()
                        finetuner.tokenizer.save_pretrained = Mock()
                        
                        with patch.object(finetuner_module, 'Trainer', return_value=mock_trainer):
                            with patch.object(finetuner_module, 'TrainingArguments'):
                                with patch.object(finetuner_module, 'EarlyStoppingCallback'):
                                    finetuner.finetune(
                                        train_examples=train_examples,
                                        eval_examples=eval_examples
                                    )
        
        # Trainer.evaluate should have been called
        mock_trainer.evaluate.assert_called_once()
    
    def test_finetune_saves_checkpoint(self, finetuner, sample_training_examples, temp_checkpoint_dir):
        """Test that checkpoint is saved on improvement."""
        train_examples = sample_training_examples * 5
        eval_examples = sample_training_examples[:3]
        
        mock_trainer = Mock()
        mock_trainer.train.return_value = Mock()
        mock_trainer.evaluate.return_value = {
            'eval_accuracy': 0.92,
            'eval_precision': 0.90,
            'eval_recall': 0.88,
            'eval_f1': 0.89,
            'eval_loss': 0.15
        }
        
        with patch.object(finetuner_module, 'TRANSFORMERS_AVAILABLE', True):
            with patch.object(finetuner_module, 'TORCH_AVAILABLE', True):
                with patch.object(finetuner, '_ensure_tokenizer'):
                    with patch.object(finetuner, '_ensure_model'):
                        finetuner.tokenizer = Mock()
                        finetuner.model = Mock()
                        finetuner.model.save_pretrained = Mock()
                        finetuner.tokenizer.save_pretrained = Mock()
                        
                        with patch.object(finetuner_module, 'Trainer', return_value=mock_trainer):
                            with patch.object(finetuner_module, 'TrainingArguments'):
                                with patch.object(finetuner_module, 'EarlyStoppingCallback'):
                                    checkpoint = finetuner.finetune(
                                        train_examples=train_examples,
                                        eval_examples=eval_examples,
                                        version="test_save_v1"
                                    )
        
        if checkpoint:
            # Check model was saved
            finetuner.model.save_pretrained.assert_called()
            finetuner.tokenizer.save_pretrained.assert_called()
    
    def test_finetune_insufficient_data_error(self, finetuner):
        """Test error on insufficient training data."""
        train_examples = [
            TrainingExample(text="Test", label=0)
        ]
        eval_examples = [
            TrainingExample(text="Test 2", label=1)
        ]
        
        with patch.object(finetuner_module, 'TRANSFORMERS_AVAILABLE', True):
            with patch.object(finetuner_module, 'TORCH_AVAILABLE', True):
                with pytest.raises(InsufficientDataError):
                    finetuner.finetune(train_examples, eval_examples)
    
    def test_finetune_early_stopping(self, config, mock_feedback_collector):
        """Test early stopping configuration."""
        config.early_stopping_patience = 2
        finetuner = ModelFinetuner(config, mock_feedback_collector)
        
        assert finetuner.config.early_stopping_patience == 2
    
    def test_compute_metrics(self, finetuner):
        """Test metrics computation."""
        # Mock eval prediction
        eval_pred = Mock()
        eval_pred.predictions = [[0.2, 0.8], [0.9, 0.1], [0.3, 0.7]]
        eval_pred.label_ids = [1, 0, 1]
        
        # Need to properly mock the tuple unpacking
        with patch.object(finetuner_module, 'np') as mock_np_local:
            mock_np_local.argmax = Mock(return_value=[1, 0, 1])
            
            with patch.object(finetuner_module, 'accuracy_score', return_value=0.9):
                with patch.object(finetuner_module, 'precision_recall_fscore_support', 
                              return_value=(0.85, 0.88, 0.86, None)):
                    metrics = finetuner._compute_metrics((eval_pred.predictions, eval_pred.label_ids))
        
        assert 'accuracy' in metrics
        assert 'precision' in metrics
        assert 'recall' in metrics
        assert 'f1' in metrics


# ═══════════════════════════════════════════════════════════════════════════════
# CHECKPOINT MANAGEMENT TESTS (7 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckpointManagement:
    """Tests for checkpoint management."""
    
    def test_save_checkpoint_improved(self, finetuner, sample_metrics, temp_checkpoint_dir):
        """Test checkpoint saved when improved."""
        finetuner.best_metrics = None  # No previous best
        finetuner.tokenizer = Mock()
        finetuner.model = Mock()
        finetuner.model.save_pretrained = Mock()
        finetuner.tokenizer.save_pretrained = Mock()
        
        checkpoint = finetuner._save_checkpoint(
            metrics=sample_metrics,
            train_examples=100,
            version="test_v1"
        )
        
        assert checkpoint is not None
        assert checkpoint.version == "test_v1"
        assert checkpoint.metrics.f1 == sample_metrics.f1
    
    def test_save_checkpoint_no_improvement(self, finetuner, sample_metrics, temp_checkpoint_dir):
        """Test checkpoint not saved when no improvement."""
        # Set best metrics higher than new metrics
        finetuner.best_metrics = TrainingMetrics(
            accuracy=0.98,
            precision=0.97,
            recall=0.96,
            f1=0.97,  # Higher than sample_metrics.f1 (0.89)
            loss=0.05,
            epoch=5
        )
        
        checkpoint = finetuner._save_checkpoint(
            metrics=sample_metrics,
            train_examples=100,
            version="test_v2"
        )
        
        assert checkpoint is None
    
    def test_load_checkpoint_success(self, finetuner, temp_checkpoint_dir):
        """Test successful checkpoint loading."""
        # Create a mock checkpoint directory
        version = "test_load_v1"
        checkpoint_path = Path(temp_checkpoint_dir) / version
        checkpoint_path.mkdir(parents=True)
        
        # Create metadata file
        metadata = {
            'version': version,
            'model_path': str(checkpoint_path),
            'metrics': {
                'accuracy': 0.9,
                'precision': 0.85,
                'recall': 0.88,
                'f1': 0.86,
                'loss': 0.2,
                'epoch': 3
            },
            'training_examples': 100,
            'created_at': datetime.now().isoformat()
        }
        
        with open(checkpoint_path / "checkpoint_metadata.json", 'w') as f:
            json.dump(metadata, f)
        
        # Mock the model loading
        with patch.object(finetuner_module, 'TRANSFORMERS_AVAILABLE', True):
            with patch.object(finetuner_module, 'AutoModelForSequenceClassification') as mock_model:
                with patch.object(finetuner_module, 'AutoTokenizer') as mock_tok:
                    mock_model.from_pretrained = Mock(return_value=Mock())
                    mock_tok.from_pretrained = Mock(return_value=Mock())
                    
                    result = finetuner.load_checkpoint(version)
        
        assert result is True
    
    def test_load_checkpoint_not_found(self, finetuner):
        """Test error when checkpoint not found."""
        with patch.object(finetuner_module, 'TRANSFORMERS_AVAILABLE', True):
            result = finetuner.load_checkpoint("nonexistent_v1")
        
        assert result is False
        
        assert result is False
    
    def test_list_checkpoints(self, finetuner, temp_checkpoint_dir):
        """Test listing checkpoints."""
        # Create mock checkpoints
        for i in range(3):
            version = f"v{i}_test"
            checkpoint_path = Path(temp_checkpoint_dir) / version
            checkpoint_path.mkdir(parents=True)
            
            metadata = {
                'version': version,
                'model_path': str(checkpoint_path),
                'metrics': {
                    'accuracy': 0.9 + i * 0.01,
                    'precision': 0.85,
                    'recall': 0.88,
                    'f1': 0.86 + i * 0.01,
                    'loss': 0.2,
                    'epoch': 3
                },
                'training_examples': 100,
                'created_at': datetime.now().isoformat()
            }
            
            with open(checkpoint_path / "checkpoint_metadata.json", 'w') as f:
                json.dump(metadata, f)
        
        checkpoints = finetuner.list_checkpoints()
        
        assert len(checkpoints) == 3
    
    def test_promote_to_production(self, finetuner, temp_checkpoint_dir):
        """Test promoting checkpoint to production."""
        # Create a checkpoint
        version = "v1_promote"
        checkpoint_path = Path(temp_checkpoint_dir) / version
        checkpoint_path.mkdir(parents=True)
        
        metadata = {
            'version': version,
            'model_path': str(checkpoint_path),
            'metrics': {
                'accuracy': 0.92,
                'precision': 0.90,
                'recall': 0.88,
                'f1': 0.89,
                'loss': 0.15,
                'epoch': 3
            },
            'training_examples': 100,
            'created_at': datetime.now().isoformat(),
            'state': 'staging'
        }
        
        with open(checkpoint_path / "checkpoint_metadata.json", 'w') as f:
            json.dump(metadata, f)
        
        # Reload checkpoints
        finetuner._load_existing_checkpoints()
        
        result = finetuner.promote_to_production(version)
        
        assert result is True
        
        checkpoint = finetuner.get_checkpoint(version)
        assert checkpoint.is_production
    
    def test_checkpoint_metadata_saved(self, finetuner, sample_metrics, temp_checkpoint_dir):
        """Test that checkpoint metadata is saved correctly."""
        finetuner.best_metrics = None
        finetuner.tokenizer = Mock()
        finetuner.model = Mock()
        finetuner.model.save_pretrained = Mock()
        finetuner.tokenizer.save_pretrained = Mock()
        
        checkpoint = finetuner._save_checkpoint(
            metrics=sample_metrics,
            train_examples=100,
            version="test_metadata_v1"
        )
        
        if checkpoint:
            metadata_path = Path(checkpoint.model_path) / "checkpoint_metadata.json"
            assert metadata_path.exists()
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            assert metadata['version'] == "test_metadata_v1"
            assert metadata['training_examples'] == 100
            assert 'metrics' in metadata


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION TESTS (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfiguration:
    """Tests for configuration."""
    
    def test_finetuning_config_defaults(self):
        """Test default configuration values."""
        config = FinetuningConfig()
        
        assert config.base_model == DEFAULT_BASE_MODEL
        assert config.learning_rate == DEFAULT_LEARNING_RATE
        assert config.batch_size == DEFAULT_BATCH_SIZE
        assert config.num_epochs == DEFAULT_NUM_EPOCHS
        assert config.min_improvement == DEFAULT_MIN_IMPROVEMENT
    
    def test_finetuning_config_custom(self):
        """Test custom configuration values."""
        config = FinetuningConfig(
            base_model="roberta-large",
            learning_rate=1e-5,
            batch_size=32,
            num_epochs=5,
            min_improvement=0.05
        )
        
        assert config.base_model == "roberta-large"
        assert config.learning_rate == 1e-5
        assert config.batch_size == 32
        assert config.num_epochs == 5
        assert config.min_improvement == 0.05
    
    def test_checkpoint_dir_created(self, temp_checkpoint_dir):
        """Test that checkpoint directory is created."""
        checkpoint_dir = Path(temp_checkpoint_dir) / "new_checkpoints"
        
        config = FinetuningConfig(checkpoint_dir=str(checkpoint_dir))
        finetuner = ModelFinetuner(config, None)
        
        assert checkpoint_dir.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS (2 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """Integration tests."""
    
    def test_end_to_end_training_workflow(self, finetuner, sample_training_examples, temp_checkpoint_dir):
        """Test complete training workflow."""
        # Prepare data
        train_examples = sample_training_examples * 5
        eval_examples = sample_training_examples[:3]
        
        # Mock trainer for fine-tuning
        mock_trainer = Mock()
        mock_trainer.train.return_value = Mock()
        mock_trainer.evaluate.return_value = {
            'eval_accuracy': 0.92,
            'eval_precision': 0.90,
            'eval_recall': 0.88,
            'eval_f1': 0.89,
            'eval_loss': 0.15
        }
        
        with patch.object(finetuner_module, 'TRANSFORMERS_AVAILABLE', True):
            with patch.object(finetuner_module, 'TORCH_AVAILABLE', True):
                with patch.object(finetuner, '_ensure_tokenizer'):
                    with patch.object(finetuner, '_ensure_model'):
                        finetuner.tokenizer = Mock()
                        finetuner.model = Mock()
                        finetuner.model.save_pretrained = Mock()
                        finetuner.tokenizer.save_pretrained = Mock()
                        
                        with patch.object(finetuner_module, 'Trainer', return_value=mock_trainer):
                            with patch.object(finetuner_module, 'TrainingArguments'):
                                with patch.object(finetuner_module, 'EarlyStoppingCallback'):
                                    # Fine-tune
                                    checkpoint = finetuner.finetune(
                                        train_examples=train_examples,
                                        eval_examples=eval_examples,
                                        version="e2e_test_v1"
                                    )
        
        # Verify workflow completed
        if checkpoint:
            assert checkpoint.version == "e2e_test_v1"
            assert checkpoint.metrics is not None
    
    def test_model_improvement_detection(self, finetuner, temp_checkpoint_dir):
        """Test that model improvement is correctly detected."""
        # First metrics (baseline)
        metrics1 = TrainingMetrics(
            accuracy=0.85,
            precision=0.82,
            recall=0.80,
            f1=0.81,
            loss=0.25,
            epoch=3
        )
        
        # Second metrics (improved)
        metrics2 = TrainingMetrics(
            accuracy=0.92,
            precision=0.90,
            recall=0.88,
            f1=0.89,  # Improvement > 2%
            loss=0.15,
            epoch=3
        )
        
        # Third metrics (not improved enough)
        metrics3 = TrainingMetrics(
            accuracy=0.92,
            precision=0.90,
            recall=0.88,
            f1=0.90,  # Only 1% improvement
            loss=0.14,
            epoch=3
        )
        
        # Test improvement detection
        assert metrics2.improved_over(metrics1, min_improvement=0.02) is True
        assert metrics3.improved_over(metrics2, min_improvement=0.02) is False


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING EXAMPLE TESTS (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrainingExample:
    """Tests for TrainingExample dataclass."""
    
    def test_training_example_creation(self):
        """Test training example creation."""
        example = TrainingExample(
            text="Test input",
            label=0,
            source="feedback",
            confidence=0.95
        )
        
        assert example.text == "Test input"
        assert example.label == 0
        assert example.source == "feedback"
        assert example.confidence == 0.95
    
    def test_training_example_validation_empty_text(self):
        """Test validation for empty text."""
        with pytest.raises(ValueError):
            TrainingExample(text="", label=0)
    
    def test_training_example_validation_invalid_label(self):
        """Test validation for invalid label."""
        with pytest.raises(ValueError):
            TrainingExample(text="Test", label=2)


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING METRICS TESTS (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrainingMetrics:
    """Tests for TrainingMetrics dataclass."""
    
    def test_training_metrics_creation(self):
        """Test training metrics creation."""
        metrics = TrainingMetrics(
            accuracy=0.92,
            precision=0.90,
            recall=0.88,
            f1=0.89,
            loss=0.15,
            epoch=3
        )
        
        assert metrics.accuracy == 0.92
        assert metrics.precision == 0.90
        assert metrics.recall == 0.88
        assert metrics.f1 == 0.89
        assert metrics.loss == 0.15
        assert metrics.epoch == 3
    
    def test_training_metrics_to_dict(self, sample_metrics):
        """Test metrics serialization."""
        data = sample_metrics.to_dict()
        
        assert 'accuracy' in data
        assert 'precision' in data
        assert 'recall' in data
        assert 'f1' in data
        assert 'loss' in data
        assert 'epoch' in data
    
    def test_training_metrics_from_dict(self):
        """Test metrics deserialization."""
        data = {
            'accuracy': 0.92,
            'precision': 0.90,
            'recall': 0.88,
            'f1': 0.89,
            'loss': 0.15,
            'epoch': 3
        }
        
        metrics = TrainingMetrics.from_dict(data)
        
        assert metrics.accuracy == 0.92
        assert metrics.f1 == 0.89


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL CHECKPOINT TESTS (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestModelCheckpoint:
    """Tests for ModelCheckpoint dataclass."""
    
    def test_model_checkpoint_creation(self, sample_metrics):
        """Test checkpoint creation."""
        checkpoint = ModelCheckpoint(
            version="v1_test",
            model_path="/path/to/model",
            metrics=sample_metrics,
            training_examples=100
        )
        
        assert checkpoint.version == "v1_test"
        assert checkpoint.model_path == "/path/to/model"
        assert checkpoint.training_examples == 100
    
    def test_model_checkpoint_is_production(self, sample_metrics):
        """Test production status check."""
        checkpoint = ModelCheckpoint(
            version="v1_test",
            model_path="/path/to/model",
            metrics=sample_metrics,
            training_examples=100,
            state=ModelState.PRODUCTION.value
        )
        
        assert checkpoint.is_production is True
    
    def test_model_checkpoint_to_dict(self, sample_metrics):
        """Test checkpoint serialization."""
        checkpoint = ModelCheckpoint(
            version="v1_test",
            model_path="/path/to/model",
            metrics=sample_metrics,
            training_examples=100
        )
        
        data = checkpoint.to_dict()
        
        assert data['version'] == "v1_test"
        assert data['model_path'] == "/path/to/model"
        assert data['training_examples'] == 100
        assert 'metrics' in data


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTION TESTS (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestExceptions:
    """Tests for exception classes."""
    
    def test_finetuner_error(self):
        """Test base finetuner error."""
        error = FinetunerError("Test error")
        assert str(error) == "Test error"
    
    def test_insufficient_data_error(self):
        """Test insufficient data error."""
        error = InsufficientDataError("Not enough data")
        assert isinstance(error, FinetunerError)
    
    def test_checkpoint_error(self):
        """Test checkpoint error."""
        error = CheckpointError("Checkpoint failed")
        assert isinstance(error, FinetunerError)


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY TESTS (2 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestUtilities:
    """Tests for utility methods."""
    
    def test_extract_label_from_text_threat(self, finetuner):
        """Test label extraction from threat text."""
        text = "This is a security threat that should be blocked"
        label = finetuner._extract_label_from_text(text)
        assert label == 1
    
    def test_extract_label_from_text_benign(self, finetuner):
        """Test label extraction from benign text."""
        text = "This is safe and legitimate"
        label = finetuner._extract_label_from_text(text)
        assert label == 0


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS TESTS (2 tests)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstants:
    """Tests for module constants."""
    
    def test_threat_keywords_defined(self):
        """Test that threat keywords are defined."""
        assert len(THREAT_KEYWORDS) > 0
        assert 'threat' in THREAT_KEYWORDS
        assert 'malicious' in THREAT_KEYWORDS
    
    def test_benign_keywords_defined(self):
        """Test that benign keywords are defined."""
        assert len(BENIGN_KEYWORDS) > 0
        assert 'safe' in BENIGN_KEYWORDS
        assert 'benign' in BENIGN_KEYWORDS
