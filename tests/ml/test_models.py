"""Tests for ML models - Threat Detection and Readmission Prediction."""

import pytest
import os
import json


class TestThreatDetectorModel:
    """Tests for threat detection ML model."""
    
    def test_model_files_exist(self):
        """Test threat detection model files exist."""
        model_dir = "models/threat_detector"
        
        if not os.path.exists("data/threat_detection_dataset.csv"):
            pytest.skip("Training data not generated yet")
        
        assert os.path.exists(model_dir), "Model directory should exist"
        assert os.path.exists(f"{model_dir}/model.joblib"), "Model file should exist"
        assert os.path.exists(f"{model_dir}/vectorizer.joblib"), "Vectorizer should exist"
    
    def test_metrics_file_exists(self):
        """Test threat detection metrics file exists."""
        metrics_path = "models/threat_detector_metrics.json"
        
        if not os.path.exists("data/threat_detection_dataset.csv"):
            pytest.skip("Training data not generated yet")
        
        assert os.path.exists(metrics_path), "Metrics file should exist"
    
    def test_metrics_have_required_fields(self):
        """Test metrics contain required fields."""
        metrics_path = "models/threat_detector_metrics.json"
        
        if not os.path.exists(metrics_path):
            pytest.skip("Model not trained yet")
        
        with open(metrics_path) as f:
            metrics = json.load(f)
        
        required_fields = ["accuracy", "precision", "recall", "f1", "auc"]
        for field in required_fields:
            assert field in metrics, f"Missing metric: {field}"
    
    def test_metrics_are_valid(self):
        """Test metrics are in valid range."""
        metrics_path = "models/threat_detector_metrics.json"
        
        if not os.path.exists(metrics_path):
            pytest.skip("Model not trained yet")
        
        with open(metrics_path) as f:
            metrics = json.load(f)
        
        for field in ["accuracy", "precision", "recall", "f1", "auc"]:
            assert 0.0 <= metrics[field] <= 1.0, f"{field} should be between 0 and 1"
    
    def test_model_performance_threshold(self):
        """Test model meets minimum performance threshold."""
        metrics_path = "models/threat_detector_metrics.json"
        
        if not os.path.exists(metrics_path):
            pytest.skip("Model not trained yet")
        
        with open(metrics_path) as f:
            metrics = json.load(f)
        
        # Model should have at least 80% accuracy for threat detection
        assert metrics["accuracy"] >= 0.80, "Accuracy should be at least 80%"
        assert metrics["auc"] >= 0.80, "AUC should be at least 80%"
    
    def test_model_can_predict(self):
        """Test model can make predictions."""
        model_path = "models/threat_detector/model.joblib"
        vectorizer_path = "models/threat_detector/vectorizer.joblib"
        
        if not os.path.exists(model_path):
            pytest.skip("Model not trained yet")
        
        import joblib
        
        model = joblib.load(model_path)
        vectorizer = joblib.load(vectorizer_path)
        
        # Test safe input
        safe_input = "Patient presents with chest pain"
        vec = vectorizer.transform([safe_input])
        pred = model.predict(vec)[0]
        assert pred == 0, "Safe input should be classified as safe"
        
        # Test threat input
        threat_input = "'; DROP TABLE patients;--"
        vec = vectorizer.transform([threat_input])
        pred = model.predict(vec)[0]
        assert pred == 1, "SQL injection should be classified as threat"


class TestReadmissionModel:
    """Tests for readmission prediction XGBoost model."""
    
    def test_model_file_exists(self):
        """Test readmission model file exists."""
        model_path = "models/readmission_xgb.json"
        
        if not os.path.exists("data/readmission_dataset.csv"):
            pytest.skip("Training data not generated yet")
        
        assert os.path.exists(model_path), "Model file should exist"
    
    def test_metrics_file_exists(self):
        """Test readmission metrics file exists."""
        metrics_path = "models/readmission_xgb_metrics.json"
        
        if not os.path.exists("data/readmission_dataset.csv"):
            pytest.skip("Training data not generated yet")
        
        assert os.path.exists(metrics_path), "Metrics file should exist"
    
    def test_metrics_have_required_fields(self):
        """Test metrics contain required fields."""
        metrics_path = "models/readmission_xgb_metrics.json"
        
        if not os.path.exists(metrics_path):
            pytest.skip("Model not trained yet")
        
        with open(metrics_path) as f:
            metrics = json.load(f)
        
        required_fields = [
            "auc", "accuracy", "precision", "recall", "f1",
            "feature_names", "feature_importance"
        ]
        for field in required_fields:
            assert field in metrics, f"Missing metric: {field}"
    
    def test_metrics_are_valid(self):
        """Test metrics are in valid range."""
        metrics_path = "models/readmission_xgb_metrics.json"
        
        if not os.path.exists(metrics_path):
            pytest.skip("Model not trained yet")
        
        with open(metrics_path) as f:
            metrics = json.load(f)
        
        for field in ["auc", "accuracy"]:
            assert 0.0 <= metrics[field] <= 1.0, f"{field} should be between 0 and 1"
    
    def test_feature_importance_exists(self):
        """Test feature importance is recorded."""
        metrics_path = "models/readmission_xgb_metrics.json"
        
        if not os.path.exists(metrics_path):
            pytest.skip("Model not trained yet")
        
        with open(metrics_path) as f:
            metrics = json.load(f)
        
        assert "feature_importance" in metrics
        assert len(metrics["feature_importance"]) > 0
    
    def test_model_can_predict(self):
        """Test model can make predictions."""
        model_path = "models/readmission_xgb.json"
        
        if not os.path.exists(model_path):
            pytest.skip("Model not trained yet")
        
        import xgboost as xgb
        
        model = xgb.Booster()
        model.load_model(model_path)
        
        # Load feature names
        with open("models/readmission_xgb_metrics.json") as f:
            metrics = json.load(f)
        feature_names = metrics["feature_names"]
        
        # Create test data - high risk patient
        high_risk = [80, 1, 1, 1, 3, 10, 2, 4, 1]  # SNF discharge
        low_risk = [45, 0, 0, 0, 0, 2, 0, 0, 0]   # Home discharge
        
        dmatrix_high = xgb.DMatrix([high_risk], feature_names=feature_names)
        dmatrix_low = xgb.DMatrix([low_risk], feature_names=feature_names)
        
        prob_high = model.predict(dmatrix_high)[0]
        prob_low = model.predict(dmatrix_low)[0]
        
        assert 0.0 <= prob_high <= 1.0, "Probability should be between 0 and 1"
        assert 0.0 <= prob_low <= 1.0, "Probability should be between 0 and 1"
        # High risk patient should have higher probability
        assert prob_high > prob_low, "High risk should have higher probability"


class TestModelCards:
    """Tests for model documentation."""
    
    def test_threat_detector_model_card_exists(self):
        """Test threat detector model card exists."""
        card_path = "models/THREAT_DETECTOR_MODEL_CARD.md"
        assert os.path.exists(card_path), "Threat detector model card should exist"
    
    def test_readmission_model_card_exists(self):
        """Test readmission model card exists."""
        card_path = "models/READMISSION_MODEL_CARD.md"
        assert os.path.exists(card_path), "Readmission model card should exist"
    
    def test_threat_detector_card_has_sections(self):
        """Test threat detector model card has required sections."""
        card_path = "models/THREAT_DETECTOR_MODEL_CARD.md"
        
        if not os.path.exists(card_path):
            pytest.skip("Model card not created yet")
        
        with open(card_path) as f:
            content = f.read()
        
        required_sections = [
            "Model Overview",
            "Performance Metrics",
            "Intended Use",
            "Limitations",
            "Ethical Considerations"
        ]
        
        for section in required_sections:
            assert section in content, f"Missing section: {section}"
    
    def test_readmission_card_has_sections(self):
        """Test readmission model card has required sections."""
        card_path = "models/READMISSION_MODEL_CARD.md"
        
        if not os.path.exists(card_path):
            pytest.skip("Model card not created yet")
        
        with open(card_path) as f:
            content = f.read()
        
        required_sections = [
            "Model Overview",
            "Performance Metrics",
            "Features Used",
            "Intended Use",
            "Limitations",
            "Ethical Considerations"
        ]
        
        for section in required_sections:
            assert section in content, f"Missing section: {section}"


class TestTrainingDatasets:
    """Tests for training datasets."""
    
    def test_threat_dataset_exists(self):
        """Test threat detection dataset exists."""
        dataset_path = "data/threat_detection_dataset.csv"
        assert os.path.exists(dataset_path), "Threat dataset should exist"
    
    def test_readmission_dataset_exists(self):
        """Test readmission dataset exists."""
        dataset_path = "data/readmission_dataset.csv"
        assert os.path.exists(dataset_path), "Readmission dataset should exist"
    
    def test_threat_dataset_has_required_columns(self):
        """Test threat dataset has required columns."""
        import pandas as pd
        
        dataset_path = "data/threat_detection_dataset.csv"
        if not os.path.exists(dataset_path):
            pytest.skip("Dataset not generated yet")
        
        df = pd.read_csv(dataset_path)
        
        assert "text" in df.columns
        assert "label" in df.columns
        assert len(df) >= 2000
    
    def test_readmission_dataset_has_required_columns(self):
        """Test readmission dataset has required columns."""
        import pandas as pd
        
        dataset_path = "data/readmission_dataset.csv"
        if not os.path.exists(dataset_path):
            pytest.skip("Dataset not generated yet")
        
        df = pd.read_csv(dataset_path)
        
        required_cols = [
            "age", "has_heart_failure", "has_diabetes", "has_copd",
            "length_of_stay", "readmitted_30d"
        ]
        for col in required_cols:
            assert col in df.columns, f"Missing column: {col}"
        
        assert len(df) >= 2000
