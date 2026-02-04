# Final Testing Plan - Week 6

## Overview

This test plan ensures Phoenix Guardian is ready for competition submission and demo presentations. All tests should pass before final delivery.

---

## Test Categories

### 1. Fresh System Test (Simulate Judge's Experience)

**Objective:** Verify system works from clean git clone

**Procedure:**
```powershell
# On clean machine or VM
git clone https://github.com/Sabarish-29/phoenix-guardian-v4.git
cd phoenix-guardian-v4

# Follow README.md exactly
.\setup.ps1

# Verify tests pass
.\.venv\Scripts\Activate.ps1
pytest tests/ -v --tb=short

# Verify frontend builds
cd phoenix-ui
npm install --legacy-peer-deps
npm run build
npm start
```

**Success Criteria:**
- [ ] `setup.ps1` completes without errors
- [ ] All dependencies install successfully
- [ ] Database migrations run
- [ ] Test data seeds
- [ ] All 797 tests pass
- [ ] Frontend builds without errors
- [ ] Frontend runs on localhost:3000

**Issues Found:**
| Issue | Severity | Fixed? | Notes |
|-------|----------|--------|-------|
| | | | |

---

### 2. End-to-End Demo Test

**Objective:** Verify complete demo flow works

**Procedure:**
1. Start backend: `uvicorn phoenix_guardian.api.main:app --reload`
2. Start frontend: `cd phoenix-ui && npm start`
3. Login: dr.smith@phoenixguardian.health / Doctor123!
4. Navigate to SOAP Generator (/soap-generator)
5. Click "Load Sample Data"
6. Click "Generate SOAP Note"
7. Verify all 4 SOAP sections appear
8. Verify ICD codes extracted
9. Copy note to clipboard
10. Test drug interaction endpoint via API
11. Test readmission prediction via API
12. Check audit logs

**API Tests:**
```powershell
# Get auth token
$response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"dr.smith@phoenixguardian.health","password":"Doctor123!"}'
$token = $response.access_token

# Test SOAP generation
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/agents/scribe/generate-soap" `
  -Headers @{"Authorization"="Bearer $token"} `
  -ContentType "application/json" `
  -Body '{"chief_complaint":"Cough and fever","vitals":{"temp":"101.2F"},"symptoms":["cough","fever"],"exam_findings":"Crackles in right lung"}'

# Test drug interactions
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/agents/safety/check-interactions" `
  -Headers @{"Authorization"="Bearer $token"} `
  -ContentType "application/json" `
  -Body '{"medications":["lisinopril","potassium","aspirin"]}'

# Test readmission prediction
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/agents/readmission/predict-risk" `
  -Headers @{"Authorization"="Bearer $token"} `
  -ContentType "application/json" `
  -Body '{"age":75,"has_heart_failure":true,"has_diabetes":true,"has_copd":false,"comorbidity_count":2,"length_of_stay":8,"visits_30d":1,"visits_90d":3,"discharge_disposition":"snf"}'
```

**Success Criteria:**
- [ ] Login works
- [ ] SOAP generation completes in <15 seconds
- [ ] All 4 SOAP sections present (S, O, A, P)
- [ ] ICD codes extracted
- [ ] Drug interaction API returns result
- [ ] Readmission API returns risk score
- [ ] No console errors (browser)
- [ ] No backend errors (terminal)
- [ ] Audit logs capture actions

**Issues Found:**
| Issue | Severity | Fixed? | Notes |
|-------|----------|--------|-------|
| | | | |

---

### 3. Cross-Browser Testing

**Browsers to Test:**
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest, if on Mac)
- [ ] Edge (latest)

**Test Cases for Each Browser:**
- [ ] Login page renders correctly
- [ ] SOAP Generator page renders
- [ ] Forms are usable (input, submit)
- [ ] API calls succeed
- [ ] Error messages display properly
- [ ] Copy to clipboard works
- [ ] No layout breaks

**Issues Found:**
| Browser | Issue | Severity | Fixed? |
|---------|-------|----------|--------|
| | | | |

---

### 4. Performance Testing

**SOAP Generation Speed:**
```powershell
# Time 5 consecutive SOAP generations
$token = "YOUR_TOKEN_HERE"

for ($i = 1; $i -le 5; $i++) {
    $start = Get-Date
    Invoke-RestMethod -Method Post -Uri "http://localhost:8000/agents/scribe/generate-soap" `
      -Headers @{"Authorization"="Bearer $token"} `
      -ContentType "application/json" `
      -Body '{"chief_complaint":"Cough and fever","vitals":{"temp":"101.2F"},"symptoms":["cough","fever"],"exam_findings":"Crackles in right lung"}'
    $end = Get-Date
    $duration = ($end - $start).TotalSeconds
    Write-Host "Attempt $i : $duration seconds"
}
```

**Acceptance Criteria:**
- [ ] Average time <15 seconds
- [ ] No timeouts
- [ ] Consistent performance (within 2x variance)

**Results:**
| Attempt | Time (seconds) |
|---------|----------------|
| 1 | |
| 2 | |
| 3 | |
| 4 | |
| 5 | |
| **Average** | |

---

### 5. Security Testing

**Tests:**
- [ ] SQL injection blocked by SentinelAgent
- [ ] XSS attempt blocked
- [ ] Path traversal blocked
- [ ] Honeytoken access triggers alert (if honeytokens seeded)
- [ ] Failed login attempts logged
- [ ] Audit log captures all PHI access

**Procedure:**
```powershell
# Test SQL injection detection
$token = "YOUR_TOKEN_HERE"
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/agents/sentinel/analyze-input" `
  -Headers @{"Authorization"="Bearer $token"} `
  -ContentType "application/json" `
  -Body '{"user_input":"''; DROP TABLE users;--"}'
# Should return: threat_detected: true

# Test XSS detection
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/agents/sentinel/analyze-input" `
  -Headers @{"Authorization"="Bearer $token"} `
  -ContentType "application/json" `
  -Body '{"user_input":"<script>alert(''xss'')</script>"}'
# Should return: threat_detected: true

# Test safe input
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/agents/sentinel/analyze-input" `
  -Headers @{"Authorization"="Bearer $token"} `
  -ContentType "application/json" `
  -Body '{"user_input":"Patient reports chest pain for 3 days"}'
# Should return: threat_detected: false
```

**Results:**
| Test | Expected | Actual | Pass? |
|------|----------|--------|-------|
| SQL Injection | threat_detected: true | | |
| XSS | threat_detected: true | | |
| Path Traversal | threat_detected: true | | |
| Safe Input | threat_detected: false | | |

---

### 6. Documentation Accuracy Test

**Verify:**
- [ ] README commands work as written
- [ ] Demo credentials work (dr.smith@phoenixguardian.health / Doctor123!)
- [ ] API endpoints match documentation
- [ ] All required environment variables documented
- [ ] Setup steps are complete and accurate
- [ ] Demo script is accurate (DEMO_SCRIPT.md)
- [ ] Model card metrics match actual files:
  - [ ] Threat detector: AUC 1.0 (check models/threat_detector_metrics.json)
  - [ ] Readmission: AUC 0.6899 (check models/readmission_xgb_metrics.json)

**Verification Commands:**
```powershell
# Verify model metrics match documentation
Get-Content "models/threat_detector_metrics.json" | ConvertFrom-Json | Select-Object auc, accuracy
# Expected: auc=1.0, accuracy=1.0

Get-Content "models/readmission_xgb_metrics.json" | ConvertFrom-Json | Select-Object auc, accuracy
# Expected: auc=0.6899, accuracy=0.5975
```

**Issues Found:**
| Document | Issue | Fixed? |
|----------|-------|--------|
| | | |

---

### 7. Error Handling Test

**Test Scenarios:**
- [ ] Invalid ANTHROPIC_API_KEY → Clear error message
- [ ] Database connection failure → Graceful error
- [ ] Invalid JWT token → 401 Unauthorized
- [ ] Missing required fields in API calls → 422 Validation Error
- [ ] Malformed JSON → 400 Bad Request

**Expected:**
- Clear error messages (not stack traces)
- No crashes
- Graceful degradation

**Results:**
| Scenario | Expected Response | Actual | Pass? |
|----------|-------------------|--------|-------|
| Invalid API Key | Error message | | |
| Invalid JWT | 401 | | |
| Missing fields | 422 | | |
| Malformed JSON | 400 | | |

---

### 8. ML Model Validation

**Verify Models Load Correctly:**
```python
# Run in Python shell
import xgboost as xgb
import pickle

# Threat detector
with open('models/threat_detector/model.pkl', 'rb') as f:
    threat_model = pickle.load(f)
print(f"Threat model loaded: {type(threat_model)}")

# Readmission model
readmission_model = xgb.Booster()
readmission_model.load_model('models/readmission_xgb.json')
print(f"Readmission model loaded: {type(readmission_model)}")
```

**Verify Predictions Work:**
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
print(result)
# Should have: risk_score, risk_level, probability, factors, recommendations
```

**Results:**
- [ ] Threat model loads successfully
- [ ] Readmission model loads successfully
- [ ] Predictions return expected format
- [ ] Risk scores within valid range (0-100)

---

## Bug Fix Priority

### P0 (Critical - Demo Blockers)
- System won't start
- Login doesn't work
- SOAP generation fails
- Frontend crashes

### P1 (High - Major Features)
- API endpoints error
- Database issues
- Security features broken
- Model predictions fail

### P2 (Medium - Polish)
- UI bugs (cosmetic)
- Error messages unclear
- Documentation inaccuracies

### P3 (Low - Nice to Have)
- Minor UI improvements
- Performance optimizations
- Additional features

---

## Test Results Template

### Test Execution Log

| Test | Status | Date | Tester | Issues Found | Fixed? |
|------|--------|------|--------|--------------|--------|
| Fresh System | ⏳ | | | | |
| End-to-End Demo | ⏳ | | | | |
| Cross-Browser | ⏳ | | | | |
| Performance | ⏳ | | | | |
| Security | ⏳ | | | | |
| Documentation | ⏳ | | | | |
| Error Handling | ⏳ | | | | |
| ML Models | ⏳ | | | | |

**Legend:**
- ✅ Passed
- ⚠️ Passed with issues
- ❌ Failed
- ⏳ Not started

---

## Final Sign-Off Checklist

Before declaring "ready for demo":

### Critical
- [ ] All P0 bugs fixed
- [ ] All P1 bugs fixed or documented with workaround
- [ ] Fresh clone test passes
- [ ] Demo rehearsed 3+ times without issues

### Team Readiness
- [ ] All team members can run system locally
- [ ] All team members can give demo
- [ ] Backup plan exists for common failures
- [ ] Demo credentials verified working

### Environment
- [ ] All services tested together
- [ ] API key verified valid
- [ ] Database has seed data
- [ ] Honeytokens seeded (optional)

---

## Backup Plans

### If Backend Won't Start
1. Check PostgreSQL is running
2. Verify .env file exists with valid DATABASE_URL
3. Run migrations: `python scripts/migrate.py`
4. Check port 8000 is not in use

### If Frontend Won't Start
1. Delete node_modules and package-lock.json
2. Run `npm install --legacy-peer-deps`
3. Check port 3000 is not in use

### If API Key Invalid
1. Verify ANTHROPIC_API_KEY in .env
2. Check key has not expired
3. Test key directly: `curl -X POST https://api.anthropic.com/...`

### If Database Issues
1. Check PostgreSQL service is running
2. Verify database exists: `psql -l | grep phoenix`
3. Reset database: `python scripts/reset_db.py` (if available)

### If Demo Fails Live
1. Have backup video ready
2. Switch to screenshots/slides
3. Explain what would happen
4. Offer post-demo live demo

---

## Quick Smoke Test (5 minutes before demo)

```powershell
# 1. Backend health check
Invoke-RestMethod http://localhost:8000/health

# 2. Frontend loads
Start-Process "http://localhost:3000"

# 3. Login works
$response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"dr.smith@phoenixguardian.health","password":"Doctor123!"}'
Write-Host "Token received: $($response.access_token.Substring(0,20))..."

# 4. SOAP endpoint responds
Write-Host "All systems operational!"
```

---

**Test Plan Created:** February 2025  
**Last Updated:** [Date]  
**Approved By:** [Team Lead]
