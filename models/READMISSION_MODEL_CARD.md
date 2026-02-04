# Readmission Prediction Model Card

## Model Overview
- **Model:** XGBoost Gradient Boosting
- **Task:** Binary classification (readmit vs no readmit within 30 days)
- **Training Data:** 2,000 synthetic patient encounters
- **Framework:** XGBoost 2.0+

## Performance Metrics (Test Set)
- **AUC:** 0.6899
- **Accuracy:** 0.5975
- **Precision:** 0.2591
- **Recall:** 0.7353 (catches 74% of readmissions)
- **F1 Score:** 0.3831
- **Specificity:** 0.5693

**Test Set Size:** 400 samples (20% holdout)

## Clinical Interpretation
- **Recall 0.7353:** Model catches 74% of patients who will be readmitted
- **Precision 0.2591:** Of flagged patients, 26% actually readmit
- **Use case:** Screening tool to prioritize care coordination resources

## Features Used (9 total)
1. **age** - Patient age in years
2. **has_heart_failure** - Heart failure diagnosis (0/1)
3. **has_diabetes** - Diabetes diagnosis (0/1)
4. **has_copd** - COPD diagnosis (0/1)
5. **comorbidity_count** - Total comorbidities
6. **length_of_stay** - Hospital stay duration (days)
7. **visits_30d** - Hospital visits in past 30 days
8. **visits_90d** - Hospital visits in past 90 days
9. **discharge_disposition** - Discharge destination (home=0, SNF=1, rehab=2)

## Feature Importance (Top 5)
1. **comorbidity_count** - 37.89% (Most predictive)
2. **has_heart_failure** - 19.50%
3. **has_copd** - 17.97%
4. **discharge_encoded** - 14.63%
5. **length_of_stay** - 11.35%

## Training Details
- **Training samples:** 1,600
- **Test samples:** 400
- **Max depth:** 6
- **Learning rate:** 0.1
- **Boosting rounds:** 200 (with early stopping)
- **Readmission rate (training):** ~17%

## Confusion Matrix (Test Set)
```
                Predicted
              No Readmit  Readmit
Actual  No      189        143      = 332 (no readmit)
        Yes      18         50      = 68 (readmit)
                           
              = 207       = 193
```

**Interpretation:**
- True Negatives: 189 (correctly predicted no readmit)
- False Positives: 143 (predicted readmit but didn't)
- False Negatives: 18 (predicted no readmit but did)
- True Positives: 50 (correctly predicted readmit)

## Intended Use
- **Primary:** Identify patients at high risk for 30-day readmission
- **Secondary:** Support care transition planning and resource allocation
- **Clinical workflow:** Inform discharge planning, not replace clinical judgment

**NOT FOR:**
- Sole determinant of patient care decisions
- Billing or reimbursement decisions
- Discriminating against patient populations
- Use without physician review

## Risk Stratification
- **HIGH (≥70%):** Recommend care coordinator, close follow-up, post-discharge calls
- **MODERATE (40-69%):** Standard discharge planning with enhanced education
- **LOW (<40%):** Routine follow-up

## Limitations

### Data Limitations
- **Synthetic training data:** Not validated on real patient data
- **Missing features:** No social determinants, medications, lab values, comorbidity details
- **Population:** May not generalize to all demographics or hospital types
- **Temporal:** Does not account for trends over time

### Model Limitations
- **AUC 0.69:** Moderate discriminative ability, not highly accurate
- **Recall 0.74:** Misses 26% of readmissions
- **Precision 0.26:** 74% of high-risk flags are false positives

### Clinical Limitations
- **Not diagnostic:** Does not identify cause of readmission risk
- **No treatment guidance:** Does not suggest specific interventions
- **Requires validation:** Must be prospectively validated before clinical use

## Ethical Considerations

### Bias & Fairness
- **Training bias:** Synthetic data may not represent all demographics
- **Outcome bias:** Readmission influenced by access to care, not just clinical factors
- **Recommendation:** Monitor performance across age, sex, race, socioeconomic status

### Clinical Integration
- **Transparency:** Patients/providers should understand model limitations
- **Autonomy:** Predictions inform, never replace clinical judgment
- **Accountability:** Final care decisions rest with physicians

### Equity
- **Risk:** High false positive rate may burden certain populations with unnecessary interventions
- **Mitigation:** Use as screening tool, not definitive assessment

## Validation Requirements for Clinical Use

**Before deploying in clinical setting:**
1. **External validation** on real patient data from target hospital
2. **Prospective study** assessing real-world performance
3. **Bias audit** across demographic groups
4. **IRB approval** for use in patient care decisions
5. **Clinical workflow integration** testing
6. **Provider training** on interpretation and limitations
7. **Ongoing monitoring** of actual vs predicted outcomes

## Model Architecture
```
9 Input Features
    ↓
XGBoost Gradient Boosting
├── 200 boosting rounds
├── Max depth: 6
├── Learning rate: 0.1
└── Binary logistic objective
    ↓
Probability [0-1]
    ↓
Risk Score [0-100]
```

## Usage Example
```python
from phoenix_guardian.agents.readmission_agent import ReadmissionAgent

agent = ReadmissionAgent()
result = agent.predict({
    "age": 75,
    "has_heart_failure": True,
    "has_diabetes": True,
    "has_copd": False,
    "comorbidity_count": 2,
    "length_of_stay": 8,
    "visits_30d": 1,
    "visits_90d": 3,
    "discharge_disposition": "snf"
})
# Returns: {"risk_score": 78, "risk_level": "HIGH", "alert": True, ...}
```

## Calibration
Model outputs probabilities that should be calibrated before deployment. Current model not calibrated.

## Maintenance
- **Retraining:** Quarterly with updated real patient data (once validated)
- **Performance monitoring:** Track actual vs predicted readmissions monthly
- **Feature drift:** Monitor for changes in patient population characteristics
- **Model updates:** Version improvements in repository

## Version History
- **v1.0 (Feb 2025):** Initial training on 2,000 synthetic samples, AUC 0.6899

## References
- Training script: `scripts/train_readmission_model.py`
- Model file: `models/readmission_xgb.json`
- Metrics: `models/readmission_xgb_metrics.json`
- Literature: [Include relevant readmission prediction studies]

---
**Last Updated:** February 2025  
**Status:** Research/Development - NOT VALIDATED FOR CLINICAL USE  
**Regulatory:** NOT FDA-approved, NOT for clinical decision-making  
**IRB:** Approval required before use with real patient data
