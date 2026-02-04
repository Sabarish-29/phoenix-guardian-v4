"""
Phoenix Guardian - Readmission Prediction Model.

XGBoost-based 30-day hospital readmission risk prediction model.
Designed for GPU-accelerated training (RTX 3050) with CPU fallback.

Clinical Context:
- CMS Hospital Readmissions Reduction Program (HRRP) targets
- 30-day all-cause readmission as outcome
- Risk stratification for care management

Model Specifications:
- Algorithm: XGBoost (Gradient Boosted Decision Trees)
- Training: 80/20 train/validation split
- Early stopping: 20 rounds on validation AUC
- Target metric: AUC-ROC > 0.60

Compliance:
- FDA 21 CFR Part 820: Documented model parameters
- IEC 62304: Class B software component
- HIPAA: No PHI stored in model artifacts
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import logging
import time

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Model Metrics
# =============================================================================


@dataclass
class ModelMetrics:
    """Training and validation metrics for the model."""
    
    # Performance metrics
    auc_roc: float = 0.0
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    
    # Training metadata
    training_samples: int = 0
    validation_samples: int = 0
    num_boost_rounds: int = 0
    best_iteration: int = 0
    training_time_seconds: float = 0.0
    
    # Model info
    feature_count: int = 12
    model_path: str = ""
    gpu_used: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "auc_roc": self.auc_roc,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "training_samples": self.training_samples,
            "validation_samples": self.validation_samples,
            "num_boost_rounds": self.num_boost_rounds,
            "best_iteration": self.best_iteration,
            "training_time_seconds": self.training_time_seconds,
            "feature_count": self.feature_count,
            "model_path": self.model_path,
            "gpu_used": self.gpu_used,
        }


@dataclass
class PredictionResult:
    """Result of a readmission risk prediction."""
    
    risk_score: int  # 0-100 scale
    risk_category: str  # "low", "medium", "high"
    probability: float  # Raw model probability
    alert: bool  # Whether high-risk threshold exceeded
    confidence: float = 0.0  # Model confidence estimate
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "risk_score": self.risk_score,
            "risk_category": self.risk_category,
            "probability": self.probability,
            "alert": self.alert,
            "confidence": self.confidence,
        }


# =============================================================================
# Readmission Model
# =============================================================================


class ReadmissionModel:
    """
    XGBoost-based 30-day readmission risk prediction model.
    
    Provides GPU-accelerated training with automatic CPU fallback.
    Designed for healthcare CDS integration with risk stratification.
    
    Attributes:
        FEATURE_NAMES: Ordered list of 12 input features
        HIGH_RISK_THRESHOLD: Score above which alert=True (default 70)
        MEDIUM_RISK_THRESHOLD: Score for medium vs low (default 40)
    
    Example:
        >>> model = ReadmissionModel()
        >>> X, y = generate_patient_encounters(num_patients=1000)
        >>> metrics = model.train(X, y, use_gpu=True)
        >>> print(f"AUC: {metrics.auc_roc:.3f}")
        
        >>> features = [5, 1, 1, 0, 0, 3, 2, 3, 4, 7, 0, 2]
        >>> result = model.predict(features)
        >>> if result["alert"]:
        ...     trigger_care_management()
    """
    
    # Feature definitions (must match feature_engineering.py order)
    FEATURE_NAMES = [
        "num_diagnoses",
        "has_heart_failure",
        "has_diabetes",
        "has_copd",
        "has_pneumonia",
        "comorbidity_index",
        "visits_30d",
        "visits_60d",
        "visits_90d",
        "length_of_stay",
        "discharge_disposition_encoded",
        "specialty_encoded",
    ]
    
    # Risk thresholds (0-100 scale)
    HIGH_RISK_THRESHOLD = 70
    MEDIUM_RISK_THRESHOLD = 40
    
    # Default model path
    DEFAULT_MODEL_PATH = "models/readmission_xgb.json"
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        high_risk_threshold: int = 70,
        medium_risk_threshold: int = 40,
    ) -> None:
        """
        Initialize the readmission model.
        
        Args:
            model_path: Path to save/load model (default: models/readmission_xgb.json)
            high_risk_threshold: Score threshold for high risk alert
            medium_risk_threshold: Score threshold for medium vs low
        """
        self.model_path = model_path or self.DEFAULT_MODEL_PATH
        self.HIGH_RISK_THRESHOLD = high_risk_threshold
        self.MEDIUM_RISK_THRESHOLD = medium_risk_threshold
        
        self._model = None
        self._is_trained = False
        self._metrics: Optional[ModelMetrics] = None
        
        # Check for XGBoost availability
        try:
            import xgboost as xgb
            self._xgb = xgb
            self._xgb_available = True
        except ImportError:
            logger.warning("XGBoost not available. Install with: pip install xgboost")
            self._xgb = None
            self._xgb_available = False
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        use_gpu: bool = True,
        validation_split: float = 0.2,
        random_state: int = 42,
    ) -> ModelMetrics:
        """
        Train the readmission prediction model.
        
        Args:
            X: Feature matrix (N, 12)
            y: Binary labels (N,) - 1=readmitted, 0=not readmitted
            use_gpu: Whether to use GPU acceleration (falls back to CPU)
            validation_split: Fraction for validation (default 0.2)
            random_state: Random seed for reproducibility
            
        Returns:
            ModelMetrics with training results
        """
        if not self._xgb_available:
            raise RuntimeError("XGBoost not installed")
        
        start_time = time.time()
        
        # Validate inputs
        if X.shape[1] != len(self.FEATURE_NAMES):
            raise ValueError(
                f"Expected {len(self.FEATURE_NAMES)} features, got {X.shape[1]}"
            )
        
        if len(X) != len(y):
            raise ValueError("X and y must have same number of samples")
        
        # Split data
        from sklearn.model_selection import train_test_split
        
        X_train, X_val, y_train, y_val = train_test_split(
            X, y,
            test_size=validation_split,
            random_state=random_state,
            stratify=y,
        )
        
        # Create DMatrix
        dtrain = self._xgb.DMatrix(X_train, label=y_train, feature_names=self.FEATURE_NAMES)
        dval = self._xgb.DMatrix(X_val, label=y_val, feature_names=self.FEATURE_NAMES)
        
        # Determine tree method based on GPU availability
        tree_method = "hist"  # Default CPU
        gpu_used = False
        
        if use_gpu:
            try:
                # Try GPU training with a small test
                test_params = {"tree_method": "gpu_hist", "device": "cuda"}
                test_dtrain = self._xgb.DMatrix(X_train[:10], label=y_train[:10])
                self._xgb.train(test_params, test_dtrain, num_boost_round=1)
                tree_method = "gpu_hist"
                gpu_used = True
                logger.info("GPU training enabled (CUDA)")
            except Exception as e:
                logger.warning(f"GPU not available, using CPU: {e}")
                tree_method = "hist"
        
        # XGBoost parameters
        params = {
            "objective": "binary:logistic",
            "eval_metric": "auc",
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "tree_method": tree_method,
            "seed": random_state,
        }
        
        if gpu_used:
            params["device"] = "cuda"
        
        # Training with early stopping
        evals = [(dtrain, "train"), (dval, "eval")]
        evals_result: Dict[str, Any] = {}
        
        self._model = self._xgb.train(
            params,
            dtrain,
            num_boost_round=200,
            evals=evals,
            early_stopping_rounds=20,
            evals_result=evals_result,
            verbose_eval=False,
        )
        
        self._is_trained = True
        
        # Calculate metrics
        y_pred_proba = self._model.predict(dval)
        y_pred = (y_pred_proba >= 0.5).astype(int)
        
        from sklearn.metrics import (
            roc_auc_score,
            accuracy_score,
            precision_score,
            recall_score,
            f1_score,
        )
        
        auc = roc_auc_score(y_val, y_pred_proba)
        accuracy = accuracy_score(y_val, y_pred)
        precision = precision_score(y_val, y_pred, zero_division=0)
        recall = recall_score(y_val, y_pred, zero_division=0)
        f1 = f1_score(y_val, y_pred, zero_division=0)
        
        training_time = time.time() - start_time
        
        # Save model
        self._save_model()
        
        # Create metrics
        self._metrics = ModelMetrics(
            auc_roc=float(auc),
            accuracy=float(accuracy),
            precision=float(precision),
            recall=float(recall),
            f1_score=float(f1),
            training_samples=len(X_train),
            validation_samples=len(X_val),
            num_boost_rounds=self._model.best_iteration + 1,
            best_iteration=self._model.best_iteration,
            training_time_seconds=training_time,
            feature_count=len(self.FEATURE_NAMES),
            model_path=self.model_path,
            gpu_used=gpu_used,
        )
        
        logger.info(
            f"Model trained: AUC={auc:.3f}, Accuracy={accuracy:.3f}, "
            f"Time={training_time:.1f}s, GPU={gpu_used}"
        )
        
        return self._metrics
    
    def predict(
        self,
        features: List[float],
    ) -> Dict[str, Any]:
        """
        Predict readmission risk for a single patient.
        
        Args:
            features: List of 12 feature values in standard order
            
        Returns:
            Dict with:
                - risk_score: 0-100 integer scale
                - risk_category: "low", "medium", or "high"
                - probability: Raw model probability (0.0-1.0)
                - alert: True if high-risk threshold exceeded
        """
        if not self._is_trained and not self._load_model():
            raise RuntimeError("Model not trained. Call train() first.")
        
        if len(features) != len(self.FEATURE_NAMES):
            raise ValueError(
                f"Expected {len(self.FEATURE_NAMES)} features, got {len(features)}"
            )
        
        # Create DMatrix for prediction
        X = np.array([features])
        dmatrix = self._xgb.DMatrix(X, feature_names=self.FEATURE_NAMES)
        
        # Get probability
        probability = float(self._model.predict(dmatrix)[0])
        
        # Convert to 0-100 score
        risk_score = int(round(probability * 100))
        
        # Categorize
        if risk_score >= self.HIGH_RISK_THRESHOLD:
            risk_category = "high"
            alert = True
        elif risk_score >= self.MEDIUM_RISK_THRESHOLD:
            risk_category = "medium"
            alert = False
        else:
            risk_category = "low"
            alert = False
        
        return {
            "risk_score": risk_score,
            "risk_category": risk_category,
            "probability": probability,
            "alert": alert,
        }
    
    def predict_batch(
        self,
        X: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """
        Predict readmission risk for multiple patients.
        
        Args:
            X: Feature matrix (N, 12)
            
        Returns:
            List of prediction dictionaries
        """
        if not self._is_trained and not self._load_model():
            raise RuntimeError("Model not trained. Call train() first.")
        
        if X.shape[1] != len(self.FEATURE_NAMES):
            raise ValueError(
                f"Expected {len(self.FEATURE_NAMES)} features, got {X.shape[1]}"
            )
        
        dmatrix = self._xgb.DMatrix(X, feature_names=self.FEATURE_NAMES)
        probabilities = self._model.predict(dmatrix)
        
        results = []
        for prob in probabilities:
            risk_score = int(round(prob * 100))
            
            if risk_score >= self.HIGH_RISK_THRESHOLD:
                risk_category = "high"
                alert = True
            elif risk_score >= self.MEDIUM_RISK_THRESHOLD:
                risk_category = "medium"
                alert = False
            else:
                risk_category = "low"
                alert = False
            
            results.append({
                "risk_score": risk_score,
                "risk_category": risk_category,
                "probability": float(prob),
                "alert": alert,
            })
        
        return results
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        if not self._is_trained and not self._load_model():
            raise RuntimeError("Model not trained")
        
        importance = self._model.get_score(importance_type="gain")
        
        # Normalize to sum to 1
        total = sum(importance.values())
        if total > 0:
            importance = {k: v / total for k, v in importance.items()}
        
        return importance
    
    def _save_model(self) -> None:
        """Save model to disk."""
        if self._model is None:
            return
        
        # Ensure directory exists
        model_path = Path(self.model_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save model
        self._model.save_model(str(model_path))
        
        # Save metadata
        metadata = {
            "feature_names": self.FEATURE_NAMES,
            "high_risk_threshold": self.HIGH_RISK_THRESHOLD,
            "medium_risk_threshold": self.MEDIUM_RISK_THRESHOLD,
            "metrics": self._metrics.to_dict() if self._metrics else None,
        }
        
        metadata_path = model_path.with_suffix(".meta.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Model saved to {model_path}")
    
    def _load_model(self) -> bool:
        """Load model from disk if available."""
        if not self._xgb_available:
            return False
        
        model_path = Path(self.model_path)
        if not model_path.exists():
            return False
        
        try:
            self._model = self._xgb.Booster()
            self._model.load_model(str(model_path))
            self._is_trained = True
            
            logger.info(f"Model loaded from {model_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False
    
    def get_metrics(self) -> Optional[ModelMetrics]:
        """Get training metrics if available."""
        return self._metrics
    
    @property
    def is_trained(self) -> bool:
        """Check if model is trained or loaded."""
        return self._is_trained


# =============================================================================
# Module Entry Point
# =============================================================================


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Demo with synthetic data
    from phoenix_guardian.ml.synthetic_data_generator import generate_patient_encounters
    
    logger.info("Generating synthetic data...")
    X, y = generate_patient_encounters(num_patients=1000, seed=42)
    
    logger.info(f"Data shape: X={X.shape}, y={y.shape}")
    logger.info(f"Readmission rate: {y.mean():.1%}")
    
    # Train model
    model = ReadmissionModel()
    metrics = model.train(X, y, use_gpu=True)
    
    logger.info(f"Training complete: {metrics.to_dict()}")
    
    # Test prediction
    sample_features = X[0].tolist()
    result = model.predict(sample_features)
    logger.info(f"Sample prediction: {result}")
