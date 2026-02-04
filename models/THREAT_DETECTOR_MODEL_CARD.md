# Threat Detection Model Card

## Model Overview
- **Model:** TF-IDF + Logistic Regression
- **Task:** Binary classification (safe vs threat)
- **Training Data:** 2,000 synthetic samples
- **Framework:** scikit-learn 1.3+

## Performance Metrics (Test Set)
- **AUC:** 1.0000
- **Accuracy:** 1.0000
- **Precision:** 1.0000
- **Recall:** 1.0000
- **F1 Score:** 1.0000

**Test Set Size:** 400 samples (20% holdout)

## Training Details
- **Training samples:** 1,600
- **Validation samples:** 400
- **Algorithm:** Logistic Regression with L2 regularization
- **Features:** TF-IDF vectors (max 5,000 features)
- **Training time:** ~2 seconds

## Confusion Matrix (Test Set)
```
                Predicted
              Safe     Threat
Actual Safe   200        0       = 200
      Threat    0      200       = 200
              
              = 200    = 200
```

**Interpretation:**
- True Negatives: 200 (correctly predicted safe)
- False Positives: 0 (no false alarms)
- False Negatives: 0 (no missed threats)
- True Positives: 200 (correctly detected threats)

## Intended Use
- Detect potential SQL injection attacks
- Identify XSS (Cross-Site Scripting) attempts
- Flag path traversal attempts
- Recognize prompt injection patterns
- First-line security screening for user inputs

## Limitations
- **Training data:** Synthetic only - may miss novel real-world attacks
- **Scope:** Limited to text-based threats in English
- **Updates needed:** Requires retraining on new attack patterns
- **False positives:** Medical terminology with special characters may trigger
- **Not comprehensive:** Should be used alongside other security measures (WAF, IDS)

## Threat Categories Detected
1. **SQL Injection:** DROP TABLE, UNION SELECT, comment sequences
2. **XSS:** `<script>` tags, JavaScript events, iframe injection
3. **Path Traversal:** ../ sequences, directory navigation
4. **Credential Probes:** admin/password patterns
5. **Prompt Injection:** System override attempts

## Ethical Considerations
- **False positives:** May block legitimate medical queries containing technical terms
- **Human review:** Always include human oversight for flagged content
- **Bias:** Training data may not represent all attack vectors
- **Transparency:** Users should know when input is being analyzed for threats

## Model Architecture
```
Input Text
    ↓
TF-IDF Vectorization (max 5000 features)
    ↓
Logistic Regression Classifier
    ↓
Binary Output: [Safe, Threat]
```

## Usage Example
```python
from phoenix_guardian.agents.sentinel_agent import SentinelAgent

agent = SentinelAgent()
result = await agent.process({
    "user_input": "'; DROP TABLE patients;--"
})
# Returns: {"threat_detected": True, "confidence": 1.0, ...}
```

## Training Data Distribution
- **Safe samples:** 1,000 (50%)
  - Medical queries
  - Clinical documentation
  - Workflow instructions
  
- **Threat samples:** 1,000 (50%)
  - SQL injection: 200
  - XSS attacks: 200
  - Path traversal: 200
  - Prompt injection: 200
  - Credential probes: 200

## Maintenance
- **Retraining schedule:** Quarterly or when new attack patterns emerge
- **Monitoring:** Track false positive/negative rates in production
- **Updates:** Model improvements versioned in repository

## Version History
- **v1.0 (Feb 2025):** Initial training on 2,000 synthetic samples, AUC 1.0

## References
- Training script: `scripts/train_threat_model_fast.py`
- Model files: `models/threat_detector/`
- Metrics: `models/threat_detector_metrics.json`

---
**Last Updated:** February 2025  
**Status:** Development - Not validated on real attack data  
**Clinical Use:** NOT APPROVED
