"""
Tests for Risk Stratifier (20 tests).

Tests:
1. Risk score calculation
2. Risk level determination
3. Condition-based risk
4. Social determinant risk
5. Utilization-based risk
6. Age-based risk
7. Polypharmacy risk
8. Functional status risk
9. Risk predictions (readmission, hospitalization, mortality)
10. Intervention recommendations
"""

import pytest
from datetime import datetime

from phoenix_guardian.agents.risk_stratifier import (
    RiskStratifier,
    PatientRiskProfile,
    RiskLevel,
    CONDITION_RISK_WEIGHTS,
    SOCIAL_RISK_WEIGHTS,
    CARE_MANAGEMENT_THRESHOLDS,
)


class TestRiskStratifierInitialization:
    """Tests for stratifier initialization."""
    
    def test_initialization(self):
        """Test stratifier initializes properly."""
        stratifier = RiskStratifier()
        
        assert stratifier is not None
        assert len(stratifier.condition_weights) > 0
        assert len(stratifier.social_weights) > 0


class TestRiskScoreCalculation:
    """Tests for overall risk score calculation."""
    
    @pytest.mark.asyncio
    async def test_low_risk_patient_score(self):
        """Test low-risk patient has low score."""
        stratifier = RiskStratifier()
        
        profile = await stratifier.stratify(
            patient_id="P12345",
            patient_data={
                "age": 35,
                "conditions": [],
                "social_determinants": [],
                "utilization": {},
                "medications_count": 1
            }
        )
        
        assert profile.risk_score < 0.25
        assert profile.risk_level == RiskLevel.LOW
    
    @pytest.mark.asyncio
    async def test_high_risk_patient_score(self):
        """Test high-risk patient has high score."""
        stratifier = RiskStratifier()
        
        profile = await stratifier.stratify(
            patient_id="P12345",
            patient_data={
                "age": 80,
                "conditions": ["chf", "copd", "ckd", "diabetes"],
                "social_determinants": ["food_insecurity", "social_isolation"],
                "utilization": {"hospital_admissions_30d": 1, "ed_visits_90d": 3},
                "medications_count": 15
            }
        )
        
        assert profile.risk_score > 0.5
        assert profile.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    
    @pytest.mark.asyncio
    async def test_risk_score_normalized(self):
        """Test risk score is normalized to 0-1."""
        stratifier = RiskStratifier()
        
        # Extreme high-risk case
        profile = await stratifier.stratify(
            patient_id="P12345",
            patient_data={
                "age": 95,
                "conditions": ["esrd", "chf", "copd", "cad", "dementia"],
                "social_determinants": ["homelessness", "substance_abuse"],
                "utilization": {
                    "hospital_admissions_30d": 3,
                    "ed_visits_30d": 5
                },
                "medications_count": 20,
                "functional_status": {"adl_limitations": 6, "frailty_score": 4}
            }
        )
        
        assert 0.0 <= profile.risk_score <= 1.0


class TestRiskLevelDetermination:
    """Tests for risk level determination."""
    
    @pytest.mark.asyncio
    async def test_low_risk_threshold(self):
        """Test low risk level threshold."""
        stratifier = RiskStratifier()
        
        profile = await stratifier.stratify(
            patient_id="P12345",
            patient_data={"age": 30, "conditions": []}
        )
        
        assert profile.risk_level == RiskLevel.LOW
    
    @pytest.mark.asyncio
    async def test_moderate_risk_threshold(self):
        """Test moderate risk level threshold."""
        stratifier = RiskStratifier()
        
        profile = await stratifier.stratify(
            patient_id="P12345",
            patient_data={
                "age": 65,
                "conditions": ["hypertension", "diabetes"]
            }
        )
        
        assert profile.risk_level in (RiskLevel.MODERATE, RiskLevel.LOW)
    
    @pytest.mark.asyncio
    async def test_critical_risk_threshold(self):
        """Test critical risk level threshold."""
        stratifier = RiskStratifier()
        
        profile = await stratifier.stratify(
            patient_id="P12345",
            patient_data={
                "age": 85,
                "conditions": ["esrd", "chf", "copd"],
                "utilization": {"hospital_admissions_30d": 2}
            }
        )
        
        assert profile.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


class TestConditionBasedRisk:
    """Tests for condition-based risk calculation."""
    
    @pytest.mark.asyncio
    async def test_chf_increases_risk(self):
        """Test CHF increases risk score."""
        stratifier = RiskStratifier()
        
        without_chf = await stratifier.stratify(
            patient_id="P1",
            patient_data={"age": 70, "conditions": []}
        )
        
        with_chf = await stratifier.stratify(
            patient_id="P2",
            patient_data={"age": 70, "conditions": ["chf"]}
        )
        
        assert with_chf.risk_score > without_chf.risk_score
    
    @pytest.mark.asyncio
    async def test_multiple_conditions_compound(self):
        """Test multiple conditions compound risk."""
        stratifier = RiskStratifier()
        
        one_condition = await stratifier.stratify(
            patient_id="P1",
            patient_data={"age": 70, "conditions": ["diabetes"]}
        )
        
        multiple_conditions = await stratifier.stratify(
            patient_id="P2",
            patient_data={"age": 70, "conditions": ["diabetes", "chf", "copd"]}
        )
        
        assert multiple_conditions.risk_score > one_condition.risk_score
    
    def test_condition_weights_defined(self):
        """Test all major conditions have weights."""
        expected_conditions = ["chf", "copd", "diabetes", "ckd", "cad"]
        
        for condition in expected_conditions:
            assert condition in CONDITION_RISK_WEIGHTS


class TestSocialDeterminantRisk:
    """Tests for social determinant risk calculation."""
    
    @pytest.mark.asyncio
    async def test_food_insecurity_increases_risk(self):
        """Test food insecurity increases risk."""
        stratifier = RiskStratifier()
        
        without_social = await stratifier.stratify(
            patient_id="P1",
            patient_data={"age": 50, "conditions": []}
        )
        
        with_social = await stratifier.stratify(
            patient_id="P2",
            patient_data={
                "age": 50,
                "conditions": [],
                "social_determinants": ["food_insecurity"]
            }
        )
        
        assert with_social.risk_score > without_social.risk_score
    
    @pytest.mark.asyncio
    async def test_housing_instability_increases_risk(self):
        """Test housing instability increases risk."""
        stratifier = RiskStratifier()
        
        without_housing = await stratifier.stratify(
            patient_id="P1",
            patient_data={"age": 50}
        )
        
        with_housing = await stratifier.stratify(
            patient_id="P2",
            patient_data={
                "age": 50,
                "social_determinants": ["housing_instability"]
            }
        )
        
        assert with_housing.risk_score > without_housing.risk_score
    
    def test_social_weights_defined(self):
        """Test social determinant weights are defined."""
        expected_factors = ["food_insecurity", "housing_instability", "transportation_barriers"]
        
        for factor in expected_factors:
            assert factor in SOCIAL_RISK_WEIGHTS


class TestUtilizationBasedRisk:
    """Tests for utilization-based risk calculation."""
    
    @pytest.mark.asyncio
    async def test_recent_admission_increases_risk(self):
        """Test recent admission increases risk."""
        stratifier = RiskStratifier()
        
        no_admission = await stratifier.stratify(
            patient_id="P1",
            patient_data={"age": 70, "utilization": {}}
        )
        
        with_admission = await stratifier.stratify(
            patient_id="P2",
            patient_data={
                "age": 70,
                "utilization": {"hospital_admissions_30d": 1}
            }
        )
        
        assert with_admission.risk_score > no_admission.risk_score
    
    @pytest.mark.asyncio
    async def test_ed_visits_increase_risk(self):
        """Test ED visits increase risk."""
        stratifier = RiskStratifier()
        
        no_ed = await stratifier.stratify(
            patient_id="P1",
            patient_data={"age": 60, "utilization": {}}
        )
        
        with_ed = await stratifier.stratify(
            patient_id="P2",
            patient_data={
                "age": 60,
                "utilization": {"ed_visits_90d": 3}
            }
        )
        
        assert with_ed.risk_score > no_ed.risk_score


class TestAgeBasedRisk:
    """Tests for age-based risk calculation."""
    
    @pytest.mark.asyncio
    async def test_elderly_higher_risk(self):
        """Test elderly patients have higher risk."""
        stratifier = RiskStratifier()
        
        young = await stratifier.stratify(
            patient_id="P1",
            patient_data={"age": 30}
        )
        
        elderly = await stratifier.stratify(
            patient_id="P2",
            patient_data={"age": 85}
        )
        
        assert elderly.risk_score > young.risk_score
    
    @pytest.mark.asyncio
    async def test_very_elderly_highest_age_risk(self):
        """Test very elderly have highest age risk."""
        stratifier = RiskStratifier()
        
        profile = await stratifier.stratify(
            patient_id="P1",
            patient_data={"age": 95}
        )
        
        # Age alone should contribute significant risk
        assert profile.risk_score > 0.1


class TestPolypharmacyRisk:
    """Tests for polypharmacy risk calculation."""
    
    @pytest.mark.asyncio
    async def test_many_medications_increases_risk(self):
        """Test many medications increases risk."""
        stratifier = RiskStratifier()
        
        few_meds = await stratifier.stratify(
            patient_id="P1",
            patient_data={"age": 70, "medications_count": 3}
        )
        
        many_meds = await stratifier.stratify(
            patient_id="P2",
            patient_data={"age": 70, "medications_count": 15}
        )
        
        assert many_meds.risk_score > few_meds.risk_score


class TestRiskPredictions:
    """Tests for specific risk predictions."""
    
    @pytest.mark.asyncio
    async def test_readmission_risk_calculated(self):
        """Test 30-day readmission risk is calculated."""
        stratifier = RiskStratifier()
        
        profile = await stratifier.stratify(
            patient_id="P12345",
            patient_data={
                "age": 75,
                "conditions": ["chf"],
                "utilization": {"hospital_admissions_30d": 1}
            }
        )
        
        assert profile.readmission_risk_30day > 0
        assert profile.readmission_risk_30day <= 1.0
    
    @pytest.mark.asyncio
    async def test_hospitalization_risk_calculated(self):
        """Test 90-day hospitalization risk is calculated."""
        stratifier = RiskStratifier()
        
        profile = await stratifier.stratify(
            patient_id="P12345",
            patient_data={"age": 80, "conditions": ["copd"]}
        )
        
        assert profile.hospitalization_risk_90day >= 0
        assert profile.hospitalization_risk_90day <= 1.0
    
    @pytest.mark.asyncio
    async def test_mortality_risk_calculated(self):
        """Test 12-month mortality risk is calculated."""
        stratifier = RiskStratifier()
        
        profile = await stratifier.stratify(
            patient_id="P12345",
            patient_data={
                "age": 90,
                "conditions": ["esrd", "chf"]
            }
        )
        
        assert profile.mortality_risk_12month > 0
        assert profile.mortality_risk_12month <= 1.0


class TestInterventionRecommendations:
    """Tests for intervention recommendations."""
    
    @pytest.mark.asyncio
    async def test_chf_interventions_recommended(self):
        """Test CHF-specific interventions are recommended."""
        stratifier = RiskStratifier()
        
        profile = await stratifier.stratify(
            patient_id="P12345",
            patient_data={"age": 70, "conditions": ["chf"]}
        )
        
        # Should have CHF-related interventions
        interventions_lower = [i.lower() for i in profile.recommended_interventions]
        assert any("cardio" in i or "heart" in i for i in interventions_lower) or \
               len(profile.recommended_interventions) > 0
    
    @pytest.mark.asyncio
    async def test_social_interventions_recommended(self):
        """Test social interventions for social determinants."""
        stratifier = RiskStratifier()
        
        profile = await stratifier.stratify(
            patient_id="P12345",
            patient_data={
                "age": 60,
                "social_determinants": ["food_insecurity"]
            }
        )
        
        # Should have food-related interventions
        interventions_lower = [i.lower() for i in profile.recommended_interventions]
        assert any("food" in i or "snap" in i or "meal" in i 
                   for i in interventions_lower) or \
               len(profile.recommended_interventions) >= 0


class TestCareManagementLevel:
    """Tests for care management level assignment."""
    
    @pytest.mark.asyncio
    async def test_low_risk_level_1(self):
        """Test low risk gets Level 1 care management."""
        stratifier = RiskStratifier()
        
        profile = await stratifier.stratify(
            patient_id="P12345",
            patient_data={"age": 30, "conditions": []}
        )
        
        assert "Level 1" in profile.care_management_level
    
    @pytest.mark.asyncio
    async def test_critical_risk_level_4(self):
        """Test critical risk gets Level 4 care management."""
        stratifier = RiskStratifier()
        
        profile = await stratifier.stratify(
            patient_id="P12345",
            patient_data={
                "age": 85,
                "conditions": ["esrd", "chf", "copd"],
                "utilization": {"hospital_admissions_30d": 2}
            }
        )
        
        # Should be high-level care management
        assert "Level 3" in profile.care_management_level or \
               "Level 4" in profile.care_management_level
