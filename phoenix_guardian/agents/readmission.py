"""ReadmissionAgent - 30-day Readmission Risk Prediction.

Uses trained XGBoost model to predict hospital readmission risk
based on patient demographics, comorbidities, and encounter data.
"""

import xgboost as xgb
import json
import os
from typing import Dict, Any, List, Optional


class ReadmissionAgent:
    """Predicts 30-day readmission risk using trained XGBoost model.
    
    This agent provides clinical decision support for discharge planning
    by identifying patients at high risk for hospital readmission.
    
    Attributes:
        model: Trained XGBoost model
        metrics: Model performance metrics
        feature_names: List of feature names used by model
    """
    
    def __init__(self):
        """Initialize agent and load trained model."""
        self.model: Optional[xgb.Booster] = None
        self.metrics: Optional[Dict[str, Any]] = None
        self.feature_names: List[str] = []
        self._load_model()
    
    def _load_model(self):
        """Load trained XGBoost model and metrics."""
        model_path = "models/readmission_xgb.json"
        metrics_path = "models/readmission_xgb_metrics.json"
        
        if os.path.exists(model_path):
            try:
                self.model = xgb.Booster()
                self.model.load_model(model_path)
            except Exception as e:
                print(f"Warning: Could not load readmission model: {e}")
        
        if os.path.exists(metrics_path):
            try:
                with open(metrics_path) as f:
                    self.metrics = json.load(f)
                    self.feature_names = self.metrics.get('feature_names', [])
            except Exception as e:
                print(f"Warning: Could not load metrics: {e}")
    
    def predict(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict readmission risk for a patient.
        
        Args:
            patient_data: {
                "age": float,
                "has_heart_failure": bool,
                "has_diabetes": bool,
                "has_copd": bool,
                "comorbidity_count": int,
                "length_of_stay": int,
                "visits_30d": int,
                "visits_90d": int,
                "discharge_disposition": str  # "home", "snf", "rehab"
            }
        
        Returns:
            {
                "risk_score": int (0-100),
                "probability": float (0.0-1.0),
                "risk_level": str ("LOW", "MODERATE", "HIGH"),
                "alert": bool,
                "model_auc": float,
                "factors": list[str],
                "recommendations": list[str],
                "agent": str
            }
        """
        if not self.model:
            return {
                "error": "Model not loaded. Please train the model first.",
                "agent": "ReadmissionAgent"
            }
        
        # Encode features
        features = self._encode_features(patient_data)
        
        # Predict
        dmatrix = xgb.DMatrix([features], feature_names=self.feature_names)
        probability = float(self.model.predict(dmatrix)[0])
        risk_score = int(probability * 100)
        
        # Classify risk level
        if risk_score >= 70:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"
        
        # Identify risk factors
        factors = self._identify_risk_factors(patient_data)
        
        # Generate recommendations based on risk level
        recommendations = self._generate_recommendations(risk_level, factors)
        
        return {
            "risk_score": risk_score,
            "probability": round(probability, 4),
            "risk_level": risk_level,
            "alert": risk_score >= 70,
            "model_auc": self.metrics.get('auc', 0.0) if self.metrics else 0.0,
            "factors": factors,
            "recommendations": recommendations,
            "agent": "ReadmissionAgent"
        }
    
    def _encode_features(self, data: Dict[str, Any]) -> List[float]:
        """Encode patient data into feature vector.
        
        Args:
            data: Patient data dictionary
            
        Returns:
            List of numeric features in correct order for model
        """
        discharge_map = {'home': 0, 'snf': 1, 'rehab': 2}
        
        return [
            float(data.get('age', 65)),
            int(data.get('has_heart_failure', False)),
            int(data.get('has_diabetes', False)),
            int(data.get('has_copd', False)),
            int(data.get('comorbidity_count', 0)),
            int(data.get('length_of_stay', 3)),
            int(data.get('visits_30d', 0)),
            int(data.get('visits_90d', 0)),
            discharge_map.get(data.get('discharge_disposition', 'home'), 0)
        ]
    
    def _identify_risk_factors(self, data: Dict[str, Any]) -> List[str]:
        """Identify present risk factors.
        
        Args:
            data: Patient data dictionary
            
        Returns:
            List of identified risk factors
        """
        factors = []
        
        if data.get('has_heart_failure'):
            factors.append("Heart failure diagnosis")
        if data.get('has_diabetes'):
            factors.append("Diabetes mellitus")
        if data.get('has_copd'):
            factors.append("COPD diagnosis")
        if data.get('comorbidity_count', 0) >= 2:
            factors.append("Multiple comorbidities")
        if data.get('length_of_stay', 0) > 7:
            factors.append("Extended hospital stay (>7 days)")
        if data.get('visits_30d', 0) > 1:
            factors.append("Recent frequent hospital visits")
        if data.get('discharge_disposition') == 'snf':
            factors.append("Discharge to skilled nursing facility")
        if data.get('age', 0) > 75:
            factors.append("Age over 75")
        
        return factors
    
    def _generate_recommendations(
        self, 
        risk_level: str, 
        factors: List[str]
    ) -> List[str]:
        """Generate care recommendations based on risk level.
        
        Args:
            risk_level: LOW, MODERATE, or HIGH
            factors: List of identified risk factors
            
        Returns:
            List of care recommendations
        """
        recommendations = []
        
        if risk_level == "HIGH":
            recommendations.append("Schedule follow-up within 7 days of discharge")
            recommendations.append("Assign care coordinator for transition planning")
            recommendations.append("Medication reconciliation before discharge")
            recommendations.append("Consider home health referral")
        elif risk_level == "MODERATE":
            recommendations.append("Schedule follow-up within 14 days of discharge")
            recommendations.append("Provide detailed discharge instructions")
            recommendations.append("Ensure patient has access to medications")
        else:
            recommendations.append("Standard discharge planning")
            recommendations.append("Schedule routine follow-up")
        
        # Factor-specific recommendations
        if "Heart failure diagnosis" in factors:
            recommendations.append("Provide heart failure self-management education")
            recommendations.append("Ensure daily weight monitoring plan")
        if "Diabetes mellitus" in factors:
            recommendations.append("Review glucose monitoring and medication regimen")
        if "COPD diagnosis" in factors:
            recommendations.append("Verify inhaler technique before discharge")
        
        return recommendations
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model.
        
        Returns:
            Dictionary with model metadata and performance metrics
        """
        return {
            "model_loaded": self.model is not None,
            "model_type": "XGBoost Gradient Boosting",
            "metrics": self.metrics,
            "feature_names": self.feature_names,
            "agent": "ReadmissionAgent"
        }
