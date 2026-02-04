"""Tests for ReadmissionAgent - 30-day Readmission Risk Prediction."""

import pytest
import os
from phoenix_guardian.agents.readmission import ReadmissionAgent


class TestReadmissionAgentInitialization:
    """Tests for ReadmissionAgent initialization."""
    
    def test_agent_initialization(self):
        """Test ReadmissionAgent initializes without error."""
        agent = ReadmissionAgent()
        assert agent is not None
    
    def test_model_loading(self):
        """Test model loads if available."""
        agent = ReadmissionAgent()
        # Model may or may not be loaded depending on training
        if os.path.exists("models/readmission_xgb.json"):
            assert agent.model is not None
        else:
            pytest.skip("Model not trained yet")
    
    def test_metrics_loading(self):
        """Test metrics load if available."""
        agent = ReadmissionAgent()
        if os.path.exists("models/readmission_xgb_metrics.json"):
            assert agent.metrics is not None
            assert "auc" in agent.metrics
        else:
            pytest.skip("Metrics not available yet")


class TestReadmissionPrediction:
    """Tests for readmission risk prediction."""
    
    @pytest.fixture
    def agent(self):
        """Create ReadmissionAgent instance."""
        return ReadmissionAgent()
    
    @pytest.fixture
    def high_risk_patient(self):
        """High risk patient data."""
        return {
            "age": 80,
            "has_heart_failure": True,
            "has_diabetes": True,
            "has_copd": True,
            "comorbidity_count": 3,
            "length_of_stay": 10,
            "visits_30d": 2,
            "visits_90d": 4,
            "discharge_disposition": "snf"
        }
    
    @pytest.fixture
    def low_risk_patient(self):
        """Low risk patient data."""
        return {
            "age": 45,
            "has_heart_failure": False,
            "has_diabetes": False,
            "has_copd": False,
            "comorbidity_count": 0,
            "length_of_stay": 2,
            "visits_30d": 0,
            "visits_90d": 0,
            "discharge_disposition": "home"
        }
    
    def test_prediction_returns_required_fields(self, agent, high_risk_patient):
        """Test prediction returns all required fields."""
        if not agent.model:
            pytest.skip("Model not trained yet")
        
        result = agent.predict(high_risk_patient)
        
        assert "risk_score" in result
        assert "probability" in result
        assert "risk_level" in result
        assert "alert" in result
        assert "factors" in result
        assert "agent" in result
    
    def test_risk_score_range(self, agent, high_risk_patient):
        """Test risk score is in valid range."""
        if not agent.model:
            pytest.skip("Model not trained yet")
        
        result = agent.predict(high_risk_patient)
        
        assert 0 <= result["risk_score"] <= 100
        assert 0.0 <= result["probability"] <= 1.0
    
    def test_risk_level_values(self, agent, high_risk_patient):
        """Test risk level is valid category."""
        if not agent.model:
            pytest.skip("Model not trained yet")
        
        result = agent.predict(high_risk_patient)
        
        assert result["risk_level"] in ["LOW", "MODERATE", "HIGH"]
    
    def test_high_risk_vs_low_risk(self, agent, high_risk_patient, low_risk_patient):
        """Test high risk patient has higher score than low risk."""
        if not agent.model:
            pytest.skip("Model not trained yet")
        
        high_result = agent.predict(high_risk_patient)
        low_result = agent.predict(low_risk_patient)
        
        assert high_result["risk_score"] >= low_result["risk_score"]
    
    def test_agent_attribution(self, agent, low_risk_patient):
        """Test agent is properly attributed."""
        if not agent.model:
            pytest.skip("Model not trained yet")
        
        result = agent.predict(low_risk_patient)
        
        assert result["agent"] == "ReadmissionAgent"


class TestRiskFactorIdentification:
    """Tests for risk factor identification."""
    
    @pytest.fixture
    def agent(self):
        """Create ReadmissionAgent instance."""
        return ReadmissionAgent()
    
    def test_heart_failure_factor(self, agent):
        """Test heart failure is identified as risk factor."""
        patient = {"has_heart_failure": True}
        factors = agent._identify_risk_factors(patient)
        
        assert any("Heart failure" in f for f in factors)
    
    def test_diabetes_factor(self, agent):
        """Test diabetes is identified as risk factor."""
        patient = {"has_diabetes": True}
        factors = agent._identify_risk_factors(patient)
        
        assert any("Diabetes" in f for f in factors)
    
    def test_copd_factor(self, agent):
        """Test COPD is identified as risk factor."""
        patient = {"has_copd": True}
        factors = agent._identify_risk_factors(patient)
        
        assert any("COPD" in f for f in factors)
    
    def test_multiple_comorbidities_factor(self, agent):
        """Test multiple comorbidities identified."""
        patient = {"comorbidity_count": 3}
        factors = agent._identify_risk_factors(patient)
        
        assert any("comorbidities" in f.lower() for f in factors)
    
    def test_extended_stay_factor(self, agent):
        """Test extended stay is identified."""
        patient = {"length_of_stay": 10}
        factors = agent._identify_risk_factors(patient)
        
        assert any("stay" in f.lower() for f in factors)
    
    def test_snf_discharge_factor(self, agent):
        """Test SNF discharge is identified."""
        patient = {"discharge_disposition": "snf"}
        factors = agent._identify_risk_factors(patient)
        
        assert any("nursing" in f.lower() for f in factors)
    
    def test_elderly_factor(self, agent):
        """Test age over 75 is identified."""
        patient = {"age": 82}
        factors = agent._identify_risk_factors(patient)
        
        assert any("75" in f for f in factors)


class TestFeatureEncoding:
    """Tests for feature encoding."""
    
    @pytest.fixture
    def agent(self):
        """Create ReadmissionAgent instance."""
        return ReadmissionAgent()
    
    def test_feature_vector_length(self, agent):
        """Test feature vector has correct length."""
        patient = {
            "age": 65,
            "has_heart_failure": True,
            "has_diabetes": False,
            "has_copd": False,
            "comorbidity_count": 1,
            "length_of_stay": 5,
            "visits_30d": 1,
            "visits_90d": 2,
            "discharge_disposition": "home"
        }
        
        features = agent._encode_features(patient)
        
        assert len(features) == 9
    
    def test_age_encoding(self, agent):
        """Test age is correctly encoded."""
        patient = {"age": 72.5}
        features = agent._encode_features(patient)
        
        assert features[0] == 72.5
    
    def test_boolean_encoding(self, agent):
        """Test boolean fields are correctly encoded."""
        patient = {
            "has_heart_failure": True,
            "has_diabetes": False,
            "has_copd": True
        }
        features = agent._encode_features(patient)
        
        assert features[1] == 1  # has_heart_failure
        assert features[2] == 0  # has_diabetes
        assert features[3] == 1  # has_copd
    
    def test_discharge_encoding(self, agent):
        """Test discharge disposition encoding."""
        for disposition, expected in [("home", 0), ("snf", 1), ("rehab", 2)]:
            patient = {"discharge_disposition": disposition}
            features = agent._encode_features(patient)
            
            assert features[8] == expected
    
    def test_default_values(self, agent):
        """Test default values are used for missing fields."""
        features = agent._encode_features({})
        
        assert features[0] == 65  # default age
        assert features[8] == 0   # default discharge (home)


class TestRecommendations:
    """Tests for care recommendations."""
    
    @pytest.fixture
    def agent(self):
        """Create ReadmissionAgent instance."""
        return ReadmissionAgent()
    
    def test_high_risk_recommendations(self, agent):
        """Test high risk generates appropriate recommendations."""
        recommendations = agent._generate_recommendations("HIGH", [])
        
        assert len(recommendations) > 0
        assert any("7 days" in r for r in recommendations)
        assert any("coordinator" in r.lower() for r in recommendations)
    
    def test_moderate_risk_recommendations(self, agent):
        """Test moderate risk generates appropriate recommendations."""
        recommendations = agent._generate_recommendations("MODERATE", [])
        
        assert len(recommendations) > 0
        assert any("14 days" in r for r in recommendations)
    
    def test_low_risk_recommendations(self, agent):
        """Test low risk generates standard recommendations."""
        recommendations = agent._generate_recommendations("LOW", [])
        
        assert len(recommendations) > 0
        assert any("routine" in r.lower() for r in recommendations)
    
    def test_heart_failure_specific_recommendations(self, agent):
        """Test heart failure generates specific recommendations."""
        factors = ["Heart failure diagnosis"]
        recommendations = agent._generate_recommendations("HIGH", factors)
        
        assert any("heart failure" in r.lower() for r in recommendations)
    
    def test_diabetes_specific_recommendations(self, agent):
        """Test diabetes generates specific recommendations."""
        factors = ["Diabetes mellitus"]
        recommendations = agent._generate_recommendations("MODERATE", factors)
        
        assert any("glucose" in r.lower() for r in recommendations)


class TestModelInfo:
    """Tests for model info endpoint."""
    
    def test_get_model_info(self):
        """Test model info returns expected fields."""
        agent = ReadmissionAgent()
        info = agent.get_model_info()
        
        assert "model_loaded" in info
        assert "model_type" in info
        assert "agent" in info
        assert info["agent"] == "ReadmissionAgent"
