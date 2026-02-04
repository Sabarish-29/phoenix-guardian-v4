# FDA Compliance - Clinical Decision Support

## Regulatory Status

Phoenix Guardian is classified as **Non-Device Clinical Decision Support (CDS)** under FDA guidance.

### FDA Exemption Criteria

Per FDA's ["Clinical Decision Support Software" Guidance (2022)](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software):

Phoenix Guardian meets exemption criteria because it:

1. **Does NOT acquire/process/analyze medical images or signals** ✅
   - No radiology, pathology, or diagnostic imaging
   - No EKG/ECG analysis
   - No continuous physiological monitoring

2. **Provides information/recommendations to inform clinical management** ✅
   - SOAP note generation (documentation aid)
   - Drug interaction checking (clinical reference)
   - Workflow suggestions (care coordination)
   - Readmission risk scores (informational)

3. **Healthcare provider can independently review** ✅
   - All AI suggestions are recommendations only
   - Clinicians make final decisions
   - System does not auto-execute clinical actions

4. **Displays basis for recommendations** ✅
   - Risk factors shown for readmission predictions
   - ICD codes linked to clinical documentation
   - Drug interactions cite evidence sources

### Not a Medical Device

Phoenix Guardian is **NOT** classified as a medical device because:
- Does not diagnose disease
- Does not treat/cure/mitigate disease
- Does not affect structure/function of the body
- Serves administrative/workflow functions primarily

### CDS Classification: Tier 1 (Lowest Risk)

- **Primary Function:** Administrative efficiency + clinical workflow
- **Clinical Risk:** Low (advisory only, provider retains control)
- **Regulatory Path:** Exempt from premarket review

---

## AI Components and Their Classification

### ScribeAgent (SOAP Note Generation)
- **Function:** Documentation assistance
- **Classification:** Non-device (administrative tool)
- **Risk Level:** Low
- **Rationale:** Assists with documentation, does not diagnose

### SafetyAgent (Drug Interaction Checking)
- **Function:** Clinical reference/alert
- **Classification:** Non-device CDS (informational)
- **Risk Level:** Low
- **Rationale:** Displays reference information, provider makes final decision

### NavigatorAgent (Patient Data Retrieval)
- **Function:** Data aggregation/display
- **Classification:** Non-device (workflow tool)
- **Risk Level:** Low
- **Rationale:** Displays existing data, no analysis or interpretation

### ReadmissionAgent (Risk Prediction)
- **Function:** Risk scoring (informational)
- **Classification:** Non-device CDS (advisory)
- **Risk Level:** Low-Medium
- **Rationale:** Provides risk information, does not recommend treatment

### SentinelAgent (Security Monitoring)
- **Function:** Cybersecurity
- **Classification:** Non-device (security tool)
- **Risk Level:** N/A
- **Rationale:** No clinical function

---

## Quality Management

While exempt from FDA device requirements, Phoenix Guardian follows software quality practices:

| Practice | Status | Details |
|----------|--------|---------|
| Version control | ✅ | Git with branching strategy |
| Automated testing | ✅ | pytest (750+ tests) |
| Code review | ✅ | Pull request requirements |
| Issue tracking | ✅ | GitHub Issues |
| Documentation | ✅ | Comprehensive docs |
| Change control | ✅ | Documented procedures |
| User feedback | 📋 | Planned for production |

---

## Clinical Validation

### Current Status: Development/Research

- **NOT validated for clinical use**
- Models trained on synthetic data only
- Requires prospective validation before deployment
- IRB approval needed for patient data

### Model Performance (Synthetic Data)

| Model | Metric | Value | Notes |
|-------|--------|-------|-------|
| Threat Detection | AUC | 1.00 | TF-IDF + Logistic Regression |
| Readmission Risk | AUC | 0.69 | XGBoost, synthetic data |

### Validation Plan (Pre-Production)

1. **Retrospective validation** on historical data
2. **Prospective pilot** with physician review
3. **Clinical accuracy** assessment
4. **Safety monitoring** for adverse events
5. **Publication** of validation results

### Validation Requirements by Component

| Component | Validation Required | Method |
|-----------|-------------------|--------|
| ScribeAgent | Documentation accuracy | Physician review |
| SafetyAgent | Drug interaction accuracy | Compare to reference databases |
| NavigatorAgent | Data retrieval accuracy | Integration testing |
| ReadmissionAgent | Predictive accuracy | External validation cohort |
| SentinelAgent | Security efficacy | Penetration testing |

---

## Labeling & Claims

### Allowed Claims
✅ "AI-powered documentation assistant"  
✅ "Clinical workflow coordination"  
✅ "Administrative burden reduction"  
✅ "Drug interaction reference"  
✅ "Readmission risk screening tool"

### Prohibited Claims
❌ "Diagnoses disease"  
❌ "Predicts clinical outcomes" (without validation)  
❌ "Replaces physician judgment"  
❌ "FDA-approved" or "FDA-cleared"  
❌ "Clinically validated" (until validated)

---

## 21st Century Cures Act Considerations

### Section 3060 Exclusions

Phoenix Guardian qualifies for exclusion under Section 3060(a) of the 21st Century Cures Act because:

1. **Administrative support:** Primary function is reducing documentation burden
2. **Population health management:** Readmission risk for care coordination
3. **Clinical decision support:** Meets all four CDS criteria for exemption
4. **Healthcare operations:** Workflow optimization, not diagnosis/treatment

### Documentation Requirements

Even exempt software should maintain:
- ✅ Software design documentation
- ✅ Risk assessment records
- ✅ Testing documentation
- ✅ User training materials
- ✅ Feedback/issue tracking

---

## Change Control

### Material Changes Requiring Review
- New clinical algorithms
- Changes to risk prediction models
- Integration with diagnostic devices
- Automated treatment recommendations
- Changes to intended use

### Change Classification

| Change Type | Review Required | Approval |
|-------------|-----------------|----------|
| Bug fixes | Internal review | Dev lead |
| UI changes | Internal review | Dev lead |
| New clinical feature | Regulatory review | Medical + Legal |
| Algorithm changes | Regulatory review | Medical + Legal |
| Integration changes | Security + regulatory | Security + Legal |

---

## International Considerations

### EU MDR (Medical Device Regulation)
- **Status:** Assessment pending
- **Classification:** Likely Class I (if device) or non-device
- **Action:** Consult EU regulatory counsel before EU launch

### UK MHRA
- **Status:** Post-Brexit requires separate assessment
- **Action:** UK-specific regulatory pathway needed

### Canada Health Canada
- **Status:** Similar to FDA CDS guidance
- **Action:** Review SaMD guidance documents

---

## Audit Trail for Regulatory Decisions

| Date | Decision | Rationale | Reviewer |
|------|----------|-----------|----------|
| Feb 2026 | Classified as non-device CDS | Meets all 4 criteria for exemption | [TBD] |
| Feb 2026 | Tier 1 risk classification | Administrative/advisory function | [TBD] |
| Feb 2026 | External validation required pre-production | Models on synthetic data only | [TBD] |

---

## References

- [FDA CDS Guidance (2022)](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software)
- [21st Century Cures Act Section 3060](https://www.fda.gov/medical-devices/digital-health-center-excellence/clinical-decision-support-software)
- [FDA Digital Health Software Precertification](https://www.fda.gov/medical-devices/digital-health-center-excellence/digital-health-software-precertification-pre-cert-program)
- [IMDRF SaMD Guidance](http://www.imdrf.org/documents/documents.asp)

---

**Last Updated:** February 2026  
**Regulatory Counsel:** [TBD - consult before production]  
**Next Review:** Annually or upon material changes
