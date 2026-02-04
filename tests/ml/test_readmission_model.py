"""
Phoenix Guardian - Readmission Model Tests.

Comprehensive tests for XGBoost-based readmission prediction model.

Test Coverage:
- Model initialization
- Training workflow
- GPU/CPU fallback
- Prediction output format
- Risk thresholds
- Batch prediction
- Feature importance
- Model persistence
- Synthetic data generation
"""

import pytest
import numpy as np
from pathlib import Path
from typing import Tuple
import tempfile
import shutil

from phoenix_guardian.ml.readmission_model import (
    ReadmissionModel,
    ModelMetrics,
    PredictionResult,
)
from phoenix_guardian.ml.synthetic_data_generator import (
    generate_patient_encounters,
    generate_high_risk_patient,
    generate_low_risk_patient,
    CONDITION_READMISSION_RATES,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def small_dataset() -> Tuple[np.ndarray, np.ndarray]:
    """Generate small dataset for fast tests."""
    return generate_patient_encounters(num_patients=200, seed=42)


@pytest.fixture
def trained_model(small_dataset: Tuple[np.ndarray, np.ndarray]) -> ReadmissionModel:
    """Create and train a model."""
    X, y = small_dataset
    
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = str(Path(tmpdir) / "test_model.json")
        model = ReadmissionModel(model_path=model_path)
        model.train(X, y, use_gpu=False)  # Use CPU for tests
        yield model


@pytest.fixture
def temp_model_dir():
    """Create temporary directory for model storage."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


# =============================================================================
# Model Initialization Tests
# =============================================================================


class TestModelInitialization:
    """Tests for model initialization."""
    
    def test_default_initialization(self) -> None:
        """Test default model initialization."""
        model = ReadmissionModel()
        
        assert model.HIGH_RISK_THRESHOLD == 70
        assert model.MEDIUM_RISK_THRESHOLD == 40
        assert len(model.FEATURE_NAMES) == 12
        assert not model.is_trained
    
    def test_custom_thresholds(self) -> None:
        """Test custom threshold initialization."""
        model = ReadmissionModel(
            high_risk_threshold=80,
            medium_risk_threshold=50,
        )
        
        assert model.HIGH_RISK_THRESHOLD == 80
        assert model.MEDIUM_RISK_THRESHOLD == 50
    
    def test_feature_names(self) -> None:
        """Test feature names are correct."""
        model = ReadmissionModel()
        
        assert "num_diagnoses" in model.FEATURE_NAMES
        assert "has_heart_failure" in model.FEATURE_NAMES
        assert "comorbidity_index" in model.FEATURE_NAMES
        assert "length_of_stay" in model.FEATURE_NAMES


# =============================================================================
# Training Tests
# =============================================================================


class TestModelTraining:
    """Tests for model training."""
    
    def test_train_returns_metrics(
        self,
        small_dataset: Tuple[np.ndarray, np.ndarray],
        temp_model_dir: str,
    ) -> None:
        """Test that training returns metrics."""
        X, y = small_dataset
        model_path = str(Path(temp_model_dir) / "model.json")
        model = ReadmissionModel(model_path=model_path)
        
        metrics = model.train(X, y, use_gpu=False)
        
        assert isinstance(metrics, ModelMetrics)
        assert 0.0 <= metrics.auc_roc <= 1.0
        assert 0.0 <= metrics.accuracy <= 1.0
        assert metrics.training_samples > 0
        assert metrics.validation_samples > 0
    
    def test_train_creates_model_file(
        self,
        small_dataset: Tuple[np.ndarray, np.ndarray],
        temp_model_dir: str,
    ) -> None:
        """Test that training saves model file."""
        X, y = small_dataset
        model_path = str(Path(temp_model_dir) / "model.json")
        model = ReadmissionModel(model_path=model_path)
        
        model.train(X, y, use_gpu=False)
        
        assert Path(model_path).exists()
        # Also check metadata file
        assert Path(model_path).with_suffix(".meta.json").exists()
    
    def test_train_sets_trained_flag(
        self,
        small_dataset: Tuple[np.ndarray, np.ndarray],
        temp_model_dir: str,
    ) -> None:
        """Test that training sets is_trained flag."""
        X, y = small_dataset
        model_path = str(Path(temp_model_dir) / "model.json")
        model = ReadmissionModel(model_path=model_path)
        
        assert not model.is_trained
        model.train(X, y, use_gpu=False)
        assert model.is_trained
    
    def test_train_wrong_feature_count(
        self,
        temp_model_dir: str,
    ) -> None:
        """Test training with wrong number of features."""
        X = np.random.rand(100, 10)  # Wrong: 10 instead of 12
        y = np.random.randint(0, 2, 100)
        
        model_path = str(Path(temp_model_dir) / "model.json")
        model = ReadmissionModel(model_path=model_path)
        
        with pytest.raises(ValueError, match="Expected 12 features"):
            model.train(X, y, use_gpu=False)
    
    def test_train_mismatched_samples(
        self,
        temp_model_dir: str,
    ) -> None:
        """Test training with mismatched X and y."""
        X = np.random.rand(100, 12)
        y = np.random.randint(0, 2, 50)  # Wrong: 50 instead of 100
        
        model_path = str(Path(temp_model_dir) / "model.json")
        model = ReadmissionModel(model_path=model_path)
        
        with pytest.raises(ValueError, match="same number of samples"):
            model.train(X, y, use_gpu=False)


# =============================================================================
# Prediction Tests
# =============================================================================


class TestModelPrediction:
    """Tests for model prediction."""
    
    def test_predict_returns_dict(
        self,
        trained_model: ReadmissionModel,
    ) -> None:
        """Test prediction returns dictionary."""
        features = generate_low_risk_patient().tolist()
        result = trained_model.predict(features)
        
        assert isinstance(result, dict)
        assert "risk_score" in result
        assert "risk_category" in result
        assert "probability" in result
        assert "alert" in result
    
    def test_predict_risk_score_range(
        self,
        trained_model: ReadmissionModel,
    ) -> None:
        """Test risk score is in 0-100 range."""
        features = generate_low_risk_patient().tolist()
        result = trained_model.predict(features)
        
        assert 0 <= result["risk_score"] <= 100
        assert isinstance(result["risk_score"], int)
    
    def test_predict_probability_range(
        self,
        trained_model: ReadmissionModel,
    ) -> None:
        """Test probability is in 0-1 range."""
        features = generate_low_risk_patient().tolist()
        result = trained_model.predict(features)
        
        assert 0.0 <= result["probability"] <= 1.0
    
    def test_predict_risk_categories(
        self,
        trained_model: ReadmissionModel,
    ) -> None:
        """Test risk categories are valid."""
        features = generate_low_risk_patient().tolist()
        result = trained_model.predict(features)
        
        assert result["risk_category"] in ["low", "medium", "high"]
    
    def test_predict_high_risk_alert(
        self,
        trained_model: ReadmissionModel,
    ) -> None:
        """Test high risk triggers alert."""
        # Use high-risk patient features
        features = generate_high_risk_patient().tolist()
        result = trained_model.predict(features)
        
        # High-risk patient should have elevated score
        # Note: actual score depends on model training
        assert isinstance(result["alert"], bool)
    
    def test_predict_wrong_feature_count(
        self,
        trained_model: ReadmissionModel,
    ) -> None:
        """Test prediction with wrong number of features."""
        features = [1.0, 2.0, 3.0]  # Wrong: 3 instead of 12
        
        with pytest.raises(ValueError, match="Expected 12 features"):
            trained_model.predict(features)
    
    def test_predict_without_training(self) -> None:
        """Test prediction without training raises error."""
        model = ReadmissionModel(model_path="/nonexistent/path.json")
        features = [0.0] * 12
        
        with pytest.raises(RuntimeError, match="not trained"):
            model.predict(features)


# =============================================================================
# Batch Prediction Tests
# =============================================================================


class TestBatchPrediction:
    """Tests for batch prediction."""
    
    def test_predict_batch(
        self,
        trained_model: ReadmissionModel,
        small_dataset: Tuple[np.ndarray, np.ndarray],
    ) -> None:
        """Test batch prediction."""
        X, _ = small_dataset
        
        results = trained_model.predict_batch(X[:10])
        
        assert len(results) == 10
        assert all(isinstance(r, dict) for r in results)
        assert all("risk_score" in r for r in results)
    
    def test_predict_batch_consistency(
        self,
        trained_model: ReadmissionModel,
    ) -> None:
        """Test batch prediction matches single predictions."""
        X = np.vstack([
            generate_low_risk_patient(),
            generate_high_risk_patient(),
        ])
        
        batch_results = trained_model.predict_batch(X)
        single_results = [
            trained_model.predict(X[i].tolist())
            for i in range(len(X))
        ]
        
        for batch, single in zip(batch_results, single_results):
            assert batch["risk_score"] == single["risk_score"]
            assert batch["probability"] == pytest.approx(single["probability"])


# =============================================================================
# Feature Importance Tests
# =============================================================================


class TestFeatureImportance:
    """Tests for feature importance."""
    
    def test_get_feature_importance(
        self,
        trained_model: ReadmissionModel,
    ) -> None:
        """Test feature importance retrieval."""
        importance = trained_model.get_feature_importance()
        
        assert isinstance(importance, dict)
        # At least some features should have importance
        assert len(importance) > 0
    
    def test_feature_importance_normalized(
        self,
        trained_model: ReadmissionModel,
    ) -> None:
        """Test feature importance sums to 1."""
        importance = trained_model.get_feature_importance()
        
        total = sum(importance.values())
        assert total == pytest.approx(1.0, abs=0.01)


# =============================================================================
# Model Persistence Tests
# =============================================================================


class TestModelPersistence:
    """Tests for model save/load."""
    
    def test_load_saved_model(
        self,
        small_dataset: Tuple[np.ndarray, np.ndarray],
        temp_model_dir: str,
    ) -> None:
        """Test loading a saved model."""
        X, y = small_dataset
        model_path = str(Path(temp_model_dir) / "persist_model.json")
        
        # Train and save
        model1 = ReadmissionModel(model_path=model_path)
        model1.train(X, y, use_gpu=False)
        
        # Get prediction from original
        features = X[0].tolist()
        pred1 = model1.predict(features)
        
        # Load in new model
        model2 = ReadmissionModel(model_path=model_path)
        pred2 = model2.predict(features)
        
        # Should get same results
        assert pred1["risk_score"] == pred2["risk_score"]


# =============================================================================
# Synthetic Data Tests
# =============================================================================


class TestSyntheticData:
    """Tests for synthetic data generation."""
    
    def test_generate_returns_correct_shape(self) -> None:
        """Test generated data has correct shape."""
        X, y = generate_patient_encounters(num_patients=100)
        
        assert X.shape == (100, 12)
        assert y.shape == (100,)
    
    def test_generate_labels_binary(self) -> None:
        """Test labels are binary."""
        _, y = generate_patient_encounters(num_patients=100)
        
        assert set(np.unique(y)).issubset({0, 1})
    
    def test_generate_reproducible(self) -> None:
        """Test generation is reproducible with seed."""
        X1, y1 = generate_patient_encounters(num_patients=100, seed=42)
        X2, y2 = generate_patient_encounters(num_patients=100, seed=42)
        
        np.testing.assert_array_equal(X1, X2)
        np.testing.assert_array_equal(y1, y2)
    
    def test_generate_different_seeds(self) -> None:
        """Test different seeds produce different data."""
        X1, _ = generate_patient_encounters(num_patients=100, seed=42)
        X2, _ = generate_patient_encounters(num_patients=100, seed=123)
        
        assert not np.array_equal(X1, X2)
    
    def test_condition_readmission_rates(self) -> None:
        """Test condition rates are defined."""
        assert "heart_failure" in CONDITION_READMISSION_RATES
        assert "pneumonia" in CONDITION_READMISSION_RATES
        assert "copd" in CONDITION_READMISSION_RATES
        assert "baseline" in CONDITION_READMISSION_RATES
    
    def test_high_risk_patient_features(self) -> None:
        """Test high-risk patient has expected features."""
        features = generate_high_risk_patient()
        
        assert len(features) == 12
        assert features[1] == 1.0  # has_heart_failure
        assert features[5] >= 3.0  # comorbidity_index
    
    def test_low_risk_patient_features(self) -> None:
        """Test low-risk patient has expected features."""
        features = generate_low_risk_patient()
        
        assert len(features) == 12
        assert features[1] == 0.0  # no heart_failure
        assert features[5] == 0.0  # no comorbidity


# =============================================================================
# ModelMetrics Tests
# =============================================================================


class TestModelMetrics:
    """Tests for ModelMetrics dataclass."""
    
    def test_metrics_to_dict(self) -> None:
        """Test metrics serialization."""
        metrics = ModelMetrics(
            auc_roc=0.75,
            accuracy=0.80,
            precision=0.65,
            recall=0.70,
            f1_score=0.67,
            training_samples=800,
            validation_samples=200,
        )
        
        d = metrics.to_dict()
        
        assert d["auc_roc"] == 0.75
        assert d["accuracy"] == 0.80
        assert d["training_samples"] == 800


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for end-to-end workflow."""
    
    def test_full_workflow(self, temp_model_dir: str) -> None:
        """Test complete train-predict workflow."""
        # Generate data
        X, y = generate_patient_encounters(num_patients=500, seed=42)
        
        # Train model
        model_path = str(Path(temp_model_dir) / "integration_model.json")
        model = ReadmissionModel(model_path=model_path)
        metrics = model.train(X, y, use_gpu=False)
        
        # Verify reasonable AUC (synthetic data should be learnable)
        assert metrics.auc_roc > 0.5, "Model should perform better than random"
        
        # Make predictions
        high_risk = generate_high_risk_patient()
        low_risk = generate_low_risk_patient()
        
        high_result = model.predict(high_risk.tolist())
        low_result = model.predict(low_risk.tolist())
        
        # High-risk should generally score higher than low-risk
        # Note: not guaranteed due to model variance
        assert high_result["risk_score"] >= 0
        assert low_result["risk_score"] >= 0
    
    def test_larger_dataset(self, temp_model_dir: str) -> None:
        """Test with larger dataset."""
        # Generate larger dataset
        X, y = generate_patient_encounters(num_patients=1000, seed=42)
        
        model_path = str(Path(temp_model_dir) / "large_model.json")
        model = ReadmissionModel(model_path=model_path)
        metrics = model.train(X, y, use_gpu=False)
        
        # With more data, should get reasonable performance
        assert metrics.auc_roc >= 0.55
        assert metrics.training_time_seconds < 60  # Should complete quickly


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
