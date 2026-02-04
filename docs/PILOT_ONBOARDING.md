# Hospital Pilot Onboarding Checklist

## PHOENIX GUARDIAN - PILOT PROGRAM

### Overview

This document provides a comprehensive checklist for onboarding a new hospital to the Phoenix Guardian pilot program. Each hospital must complete all items before going live with production patients.

---

## WEEK 1: PRE-DEPLOYMENT

### Legal & Compliance

- [ ] **Business Associate Agreement (BAA) signed**
  - Required for HIPAA compliance
  - Must be executed before any PHI access
  - Template: `contracts/BAA_template.pdf`
  
- [ ] **Master Service Agreement (MSA) signed**
  - Defines service levels, liability, pricing
  - Include data processing addendum
  
- [ ] **IRB approval obtained**
  - Clinical trial approval for AI-assisted documentation
  - Copy of approval letter received
  - IRB number: ________________
  
- [ ] **Informed consent forms prepared**
  - Physicians must consent to:
    - AI-assisted documentation
    - Federated learning participation (optional)
    - Behavioral biometrics (keystroke dynamics)
  
- [ ] **PHI data flow diagram approved**
  - Reviewed and signed off by hospital CISO
  - Documents all PHI touchpoints
  - Includes encryption methods

### Technical Setup

- [ ] **EHR credentials received (sandbox first)**
  - Client ID: ________________
  - Client secret: *(stored in Secrets Manager)*
  - FHIR base URL: ________________
  - OAuth token endpoint: ________________
  - EHR vendor: [ ] Epic  [ ] Cerner  [ ] Allscripts  [ ] Meditech  [ ] athenahealth

- [ ] **VPN access configured** (if required)
  - VPN type: ________________
  - Connection verified: [ ] Yes  [ ] No

- [ ] **Firewall rules opened**
  - [ ] Hospital → Phoenix API (HTTPS 443)
  - [ ] Phoenix → Hospital EHR (HTTPS 443)
  - [ ] All traffic encrypted with TLS 1.3

- [ ] **SSL certificates exchanged** (if mutual TLS required)
  - Hospital cert fingerprint: ________________
  - Phoenix cert fingerprint: ________________

- [ ] **Test patient created in EHR sandbox**
  - Patient MRN: ________________
  - Test encounter ID: ________________

### Training

- [ ] **Physician orientation scheduled**
  - Date: ________________
  - Duration: 2 hours
  - Topics:
    - [ ] AI safety and limitations
    - [ ] How to review/edit SOAP notes
    - [ ] How to report issues
    - [ ] Federated learning overview
    - [ ] Privacy protections explained

- [ ] **IT admin training scheduled**
  - Date: ________________
  - Duration: 4 hours
  - Topics:
    - [ ] Kubernetes dashboard access
    - [ ] Log aggregation (CloudWatch/Datadog)
    - [ ] Monitoring dashboards
    - [ ] Incident response procedures
    - [ ] Runbook walkthrough

### Support Infrastructure

- [ ] **Slack channel created**
  - Channel name: `#pilot-hospital-XXX`
  - Hospital IT contact added: ________________
  - Phoenix support team added

- [ ] **On-call rotation published**
  - Primary: ________________ (phone/pager)
  - Secondary: ________________
  - Escalation: ________________

- [ ] **PagerDuty integration configured**
  - Hospital added to escalation policy
  - Test alert sent and acknowledged

- [ ] **Weekly sync meeting scheduled**
  - Day/time: Fridays 2pm ET
  - Meeting link: ________________
  - Attendees confirmed

---

## WEEK 2: DEPLOYMENT

### Day 1 (Monday) - Infrastructure

- [ ] **Deploy Phoenix to pilot namespace**
  ```bash
  kubectl apply -f infrastructure/k8s/pilot/hospital-XXX/
  ```

- [ ] **Configure EHR connector**
  ```bash
  kubectl create secret generic hospital-XXX-ehr-creds \
    --from-literal=client_id=XXX \
    --from-literal=client_secret=YYY \
    -n pilot-hospital-XXX
  ```

- [ ] **Test EHR connectivity with synthetic patient**
  ```bash
  python scripts/test_ehr_connection.py --hospital=XXX --patient=TEST-001
  ```
  - [ ] Patient demographics retrieved
  - [ ] Encounters listed
  - [ ] Observations accessible

### Day 2 (Tuesday) - Security Verification

- [ ] **Verify PHI encryption**
  - [ ] At rest: RDS encryption verified (AWS Console)
  - [ ] In transit: TLS 1.3 verified (sslyze scan)
  - [ ] No PHI in logs (CloudWatch Log Insights query)

- [ ] **Test SOAP note generation** (synthetic encounter)
  - Time to generate: __________ ms
  - Note quality score: __________/5

- [ ] **Test threat detection**
  - [ ] Inject SQL injection attempt
  - [ ] Verify alert triggered
  - [ ] Check audit log entry

- [ ] **Verify audit logs**
  - [ ] All actions logged with timestamps
  - [ ] User IDs tracked
  - [ ] PHI access recorded (without logging PHI itself)

### Day 3 (Wednesday) - DR and Load Testing

- [ ] **Run DR drill**
  - [ ] Kill primary PostgreSQL pod
  - [ ] Verify replica promotion
  - [ ] Recovery time: __________ seconds (target: <30s)
  - [ ] Verify zero data loss

- [ ] **Load test (50 concurrent physicians)**
  - [ ] P95 latency: __________ ms (target: <100ms)
  - [ ] Error rate: __________% (target: <0.1%)
  - [ ] No degradation under load

### Days 4-5 (Thursday-Friday) - Beta Onboarding

- [ ] **Beta physician onboarding (5 physicians)**
  
  | Physician | Credentials | Training | Test Encounters |
  |-----------|-------------|----------|-----------------|
  | 1. ______ | [ ] Done    | [ ] Done | ____/10         |
  | 2. ______ | [ ] Done    | [ ] Done | ____/10         |
  | 3. ______ | [ ] Done    | [ ] Done | ____/10         |
  | 4. ______ | [ ] Done    | [ ] Done | ____/10         |
  | 5. ______ | [ ] Done    | [ ] Done | ____/10         |

- [ ] **Collect beta feedback**
  - Survey sent: [ ] Yes
  - Responses received: ____/5

- [ ] **Daily check-in meetings** (30 min standup)
  - Day 4: [ ] Complete
  - Day 5: [ ] Complete

### Week 2 Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| System uptime | ____% | >99% | [ ] Met |
| SOAP notes generated | ____ | 50+ | [ ] Met |
| Physician satisfaction | ____/5 | >4.0 | [ ] Met |
| Documentation time saved | ____ min | >10 min | [ ] Met |
| Support tickets | ____ | <10 | [ ] Met |
| P0/P1 incidents | ____ | 0 | [ ] Met |

---

## WEEK 3: PRODUCTION CUTOVER

### Readiness Gate

All criteria must be met before production rollout:

- [ ] All 5 beta physicians approve production rollout
- [ ] Zero P0/P1 incidents during beta period
- [ ] System uptime >99% during beta
- [ ] Physician satisfaction >4.0
- [ ] Security audit passed
- [ ] Compliance review completed

### Cutover Day

- [ ] **All physicians activated**
  - Total physicians: ____
  - Credentials provisioned: ____
  - Training completed: ____

- [ ] **24/7 support channel live**
  - On-call rotation active
  - PagerDuty configured
  - Escalation path documented

- [ ] **Monitoring alerts configured**
  - Error rate >1%: [ ] Alert configured
  - P95 >200ms: [ ] Alert configured
  - Pod restart: [ ] Alert configured
  - Database connection failures: [ ] Alert configured

- [ ] **Runbook distributed to IT staff**
  - Location: `docs/runbooks/pilot-hospital-XXX.md`
  - IT staff acknowledged receipt

- [ ] **Weekly sync meetings scheduled** (ongoing)
  - Calendar invites sent
  - Meeting cadence: Weekly → Biweekly → Monthly

### Post-Cutover Monitoring (Weeks 3-4)

- [ ] **Daily metrics review** (first week)
  - Day 1: [ ] Reviewed
  - Day 2: [ ] Reviewed
  - Day 3: [ ] Reviewed
  - Day 4: [ ] Reviewed
  - Day 5: [ ] Reviewed

- [ ] **Support ticket triage**
  - All tickets responded within 24 hours
  - P0: Respond immediately
  - P1: Respond within 4 hours
  - P2: Respond within 24 hours

- [ ] **Weekly physician surveys**
  - Week 3 satisfaction: ____/5
  - Week 4 satisfaction: ____/5
  - NPS score: ____

- [ ] **Monthly executive report generated**
  - ROI calculation included
  - Time savings documented
  - Recommendations provided

---

## CONTACTS

### Phoenix Guardian Team

| Role | Name | Email | Phone |
|------|------|-------|-------|
| Project Lead | | | |
| Integration Specialist | | | |
| DevOps Lead | | | |
| ML/Clinical Lead | | | |

### Hospital Team

| Role | Name | Email | Phone |
|------|------|-------|-------|
| IT Director | | | |
| CMIO | | | |
| IT Contact (Primary) | | | |
| IT Contact (Secondary) | | | |

---

## SIGN-OFF

### Pre-Deployment Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Hospital IT Director | | | |
| Hospital CISO | | | |
| Phoenix Project Lead | | | |

### Production Go-Live Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Hospital CMIO | | | |
| Beta Physician Representative | | | |
| Phoenix Clinical Lead | | | |

---

*Document Version: 1.0*
*Last Updated: 2026-02-02*
