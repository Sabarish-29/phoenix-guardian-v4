# FDA Clinical Decision Support (CDS) Classification Documentation

## Phoenix Guardian FDA Compliance Framework

### Document Information
- **Document ID**: PG-FDA-CDS-001
- **Version**: 1.0.0
- **Classification**: Regulatory Compliance
- **Last Updated**: Week 39-40, Phase 4
- **Author**: Phoenix Guardian Compliance Team

---

## 1. Overview

Phoenix Guardian implements a comprehensive FDA Clinical Decision Support (CDS) classification framework in accordance with:

- **FDA Guidance**: Clinical Decision Support Software (September 2022)
- **21 CFR Part 820**: Quality System Regulation
- **IEC 62304:2006+A1:2015**: Medical Device Software Lifecycle
- **ISO 14971:2019**: Medical Device Risk Management

### 1.1 Regulatory Context

The FDA distinguishes between:
- **Non-Device CDS**: Software that meets all 4 criteria - not regulated as a medical device
- **Device CDS**: Software that doesn't meet all 4 criteria - regulated as a medical device (Class I, II, or III)

Phoenix Guardian is designed and implemented to function as **Non-Device CDS** by meeting all 4 FDA criteria.

---

## 2. The Four FDA Criteria for Non-Device CDS

For CDS software to be classified as Non-Device (not regulated), it must meet ALL of the following criteria:

### Criterion 1: Not for Image/Signal Processing
> The software is NOT intended to acquire, process, or analyze a medical image or a signal from an in vitro diagnostic device or a pattern or signal from a signal acquisition system.

**Phoenix Guardian Compliance**: ✅ COMPLIANT
- Phoenix Guardian does not process medical images (X-rays, MRI, CT scans)
- Does not analyze signals from diagnostic devices
- Operates on structured clinical data (diagnoses, medications, demographics)

### Criterion 2: Displays Medical Information
> The software IS intended for the purpose of displaying, analyzing, or printing medical information about a patient or other medical information.

**Phoenix Guardian Compliance**: ✅ COMPLIANT
- Displays patient clinical summaries and risk assessments
- Analyzes clinical patterns and care gaps
- Generates reports for healthcare provider review

### Criterion 3: Supports Healthcare Professionals
> The software IS intended for the purpose of supporting or providing recommendations to a healthcare professional about prevention, diagnosis, or treatment of a disease or condition.

**Phoenix Guardian Compliance**: ✅ COMPLIANT
- All recommendations are targeted at licensed healthcare professionals
- Provides decision support, not autonomous decisions
- Supports HCP clinical judgment, does not replace it

### Criterion 4: HCP Independent Review
> The software IS intended for the purpose of enabling such healthcare professional to independently review the basis for such recommendations that such software presents so that it is not the intent that such healthcare professional rely primarily on any of such recommendations to make a clinical decision regarding an individual patient.

**Phoenix Guardian Compliance**: ✅ COMPLIANT
- All recommendations include transparent basis and evidence
- HCPs can drill down into recommendation rationale
- Model explanations provided (SHAP values, feature importance)
- No autonomous actions - all require HCP confirmation

---

## 3. Phoenix Guardian CDS Functions

### 3.1 Classified Functions

| Function ID | Name | Type | Category | Risk Level |
|-------------|------|------|----------|------------|
| pg-cds-001 | Drug-Drug Interaction Checker | Drug Interaction | Non-Device | Low |
| pg-cds-002 | Drug Allergy Alert | Allergy Check | Non-Device | Low |
| pg-cds-003 | AI Scribe Assistant | Documentation | Non-Device | Minimal |
| pg-cds-004 | Readmission Risk Predictor | Risk Prediction | Non-Device | Moderate |
| pg-cds-005 | Prior Authorization Assistant | Administrative | Non-Device | Minimal |
| pg-cds-006 | Dosage Calculator | Dosing | Non-Device | Moderate |
| pg-cds-007 | ICD-10 Coding Assistant | Coding | Non-Device | Minimal |
| pg-cds-008 | Sepsis Early Warning | Risk Prediction | Non-Device | Moderate |

### 3.2 Classification Rationale

Each function is evaluated against the 4 FDA criteria:

```
Function: Drug-Drug Interaction Checker
├── Criterion 1 (No Image/Signal): ✅ Analyzes medication lists only
├── Criterion 2 (Displays Info): ✅ Displays interaction alerts and severity
├── Criterion 3 (Supports HCP): ✅ Intended for prescriber review
└── Criterion 4 (HCP Review): ✅ Shows mechanism, references, alternatives
Result: NON-DEVICE CDS
```

---

## 4. Risk Scoring Methodology

### 4.1 Multi-Dimensional Risk Assessment

Phoenix Guardian implements quantitative risk scoring across 5 dimensions:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Clinical Impact | 30% | Potential harm from incorrect recommendations |
| Autonomy Level | 25% | Degree of human oversight required |
| Decision Criticality | 20% | Time sensitivity and reversibility |
| Population Vulnerability | 15% | Patient population characteristics |
| Data Quality | 10% | Input data reliability and validation |

### 4.2 Risk Score Calculation

```
Raw Risk Score = Σ (Dimension Score × Weight)

Where each dimension score is 0.0 - 1.0 based on:
- Clinical Impact: negligible(0.05) → catastrophic(1.0)
- Autonomy: informational(0.05) → fully autonomous(1.0)
- Criticality: reversible/non-urgent(0.2) → irreversible/urgent(0.9)
- Population: general(0.2) → critical/neonatal(0.9)
- Data Quality: high/validated(0.1) → unknown/unvalidated(0.9)
```

### 4.3 IEC 62304 Safety Classification

Based on risk scoring, functions are classified per IEC 62304:

| Safety Class | Criteria | Documentation Requirements |
|--------------|----------|---------------------------|
| Class A | Risk Score < 0.30 | Basic software documentation |
| Class B | Risk Score 0.30-0.60 | Detailed design documentation |
| Class C | Risk Score > 0.60 | Full lifecycle documentation + verification |

### 4.4 Standard Mitigations

Phoenix Guardian implements these standard mitigations:

| Mitigation | Effectiveness | Status |
|------------|---------------|--------|
| Mandatory physician review | 25% risk reduction | ✅ Implemented |
| Recommendation basis display | 15% risk reduction | ✅ Implemented |
| Input data validation | 10% risk reduction | ✅ Implemented |
| Alert fatigue reduction | 8% risk reduction | ✅ Implemented |
| Real-time monitoring | 12% risk reduction | ✅ Implemented |
| User training verification | 10% risk reduction | ✅ Implemented |
| Fail-safe defaults | 8% risk reduction | ✅ Implemented |
| Complete audit trail | 5% risk reduction | ✅ Implemented |

---

## 5. Transparency Requirements

### 5.1 Recommendation Basis Display

All Phoenix Guardian recommendations include:

1. **Evidence Sources**: Links to clinical guidelines, studies, or reference databases
2. **Contributing Factors**: Patient-specific data that influenced the recommendation
3. **Confidence Level**: Model confidence score (0-100%)
4. **Feature Importance**: Top factors via SHAP or similar explanations
5. **Alternative Actions**: Other options the HCP might consider

### 5.2 Example Transparency Display

```json
{
  "recommendation": "Consider alternative to Warfarin due to interaction",
  "confidence": 0.87,
  "basis": {
    "interaction_type": "Pharmacokinetic - CYP2C9 inhibition",
    "severity": "Major",
    "mechanism": "Fluconazole inhibits CYP2C9 metabolism of Warfarin",
    "evidence": "Lexicomp Drug Interactions, FDA label",
    "patient_factors": [
      "Current INR: 2.8 (therapeutic)",
      "Age: 72 (increased sensitivity)",
      "Duration: Long-term anticoagulation"
    ]
  },
  "alternatives": [
    "Reduce Warfarin dose and monitor INR closely",
    "Consider DOAC if appropriate for indication",
    "Use alternative antifungal without CYP2C9 inhibition"
  ],
  "hcp_action_required": true
}
```

---

## 6. Audit Trail and Documentation

### 6.1 SHA-256 Signatures

All classification assessments and risk scores include cryptographic signatures:

```python
signature = SHA-256({
    "function_id": "pg-cds-001",
    "category": "non_device_cds",
    "risk_level": "low",
    "risk_score": 0.23,
    "assessed_at": "2024-01-15T10:30:00Z"
})
```

### 6.2 Required Documentation

For each CDS function, we maintain:
- [ ] Function specification document
- [ ] Risk assessment with scoring rationale
- [ ] Criteria evaluation worksheet
- [ ] Validation evidence (test results)
- [ ] Change history and version control
- [ ] User training materials
- [ ] Clinical validation evidence

---

## 7. Compliance Verification

### 7.1 Automated Tests

Run FDA compliance tests:
```bash
pytest tests/fda/test_cds_classifier.py -v
```

Expected results:
- 49 tests passing
- All Phoenix Guardian functions classified as Non-Device
- All risk scores within acceptable thresholds

### 7.2 Manual Review Checklist

- [ ] All 8 CDS functions meet 4 FDA criteria
- [ ] Risk scores documented with rationale
- [ ] Transparency features verified in UI
- [ ] Audit trail captures all recommendations
- [ ] HCP review workflow enforced
- [ ] No autonomous clinical actions

---

## 8. Regulatory Pathway

### 8.1 Current Status

**Classification**: Non-Device CDS
**Regulatory Pathway**: Not FDA regulated as medical device
**Required Actions**:
- Maintain quality management practices
- Keep clinical validation evidence current
- Document any changes affecting criteria compliance
- Annual re-assessment of classification

### 8.2 Future Considerations

If Phoenix Guardian were to add features that:
- Process medical images → Would require 510(k) clearance
- Make autonomous clinical decisions → Would require Device classification
- Target patients directly → Would need to reassess Criterion 3

Such changes would trigger a re-classification assessment.

---

## 9. References

1. FDA Guidance: Clinical Decision Support Software (September 2022)
   - https://www.fda.gov/regulatory-information/search-fda-guidance-documents

2. 21 CFR Part 820 - Quality System Regulation
   - https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-820

3. IEC 62304:2006+A1:2015 - Medical Device Software Lifecycle
   - International Electrotechnical Commission

4. ISO 14971:2019 - Medical Device Risk Management
   - International Organization for Standardization

5. FDA Digital Health Center of Excellence
   - https://www.fda.gov/medical-devices/digital-health-center-excellence

---

## 10. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | Week 39-40 | Compliance Team | Initial documentation |

---

*This document is part of Phoenix Guardian's regulatory compliance framework. For questions, contact the compliance team.*
