# Demo Day Checklist

> **Purpose:** Ensure all systems are ready for a successful demo  
> **Time Required:** 45-60 minutes before demo  
> **Last Updated:** February 2026

---

## ⏰ 1 Hour Before Demo

### Environment Setup

- [ ] **Fresh terminal sessions** - Close all old terminals, open new ones
- [ ] **Pull latest code:**
  ```powershell
  cd "D:\phoenix guardian v4"
  git pull origin main
  ```
- [ ] **Activate virtual environment:**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```

### Configuration Check

- [ ] **Verify .env file exists and has required keys:**
  ```powershell
  Get-Content .env | Select-String "ANTHROPIC_API_KEY|ENCRYPTION_KEY|DATABASE_URL"
  ```
  - [ ] `ANTHROPIC_API_KEY` is set (not empty)
  - [ ] `ENCRYPTION_KEY` is set
  - [ ] `DATABASE_URL` is set

### Database

- [ ] **Database is running:**
  ```powershell
  # Check PostgreSQL service
  Get-Service -Name "postgresql*"
  ```
- [ ] **Run migrations (if needed):**
  ```powershell
  python scripts/migrate.py
  ```
- [ ] **Seed test data:**
  ```powershell
  python scripts/seed_data.py
  ```
- [ ] **Seed honeytokens:**
  ```powershell
  python scripts/seed_honeytokens.py --count 50
  ```

---

## ⏰ 30 Minutes Before Demo

### Start Backend

- [ ] **Start API server:**
  ```powershell
  cd "D:\phoenix guardian v4"
  .\.venv\Scripts\Activate.ps1
  uvicorn phoenix_guardian.api.main:app --reload --port 8000
  ```
- [ ] **Verify backend is healthy:**
  ```powershell
  curl http://localhost:8000/health
  # Or open in browser: http://localhost:8000/health
  ```
  - [ ] Response shows `"status": "healthy"`

### Start Frontend

- [ ] **Open new terminal and start frontend:**
  ```powershell
  cd "D:\phoenix guardian v4\phoenix-ui"
  npm start
  ```
- [ ] **Wait for compilation** (may take 30-60 seconds)
- [ ] **Verify frontend loads:**
  - Open http://localhost:3000
  - [ ] Login page displays correctly
  - [ ] No console errors (F12 → Console tab)

### Optional: Start Mock FHIR Server

- [ ] **If demonstrating FHIR integration:**
  ```powershell
  cd "D:\phoenix guardian v4"
  python scripts/mock_fhir_server.py
  ```
  - [ ] Server running at http://localhost:8001

---

## ⏰ 15 Minutes Before Demo - Quick Test

### Authentication Test

- [ ] **Test login:**
  - Navigate to http://localhost:3000
  - Email: `dr.smith@phoenixguardian.health`
  - Password: `Doctor123!`
  - [ ] Login successful
  - [ ] Dashboard loads

### SOAP Generator Test (Critical!)

- [ ] Navigate to **SOAP Generator** page
- [ ] Click "**Load Sample Data**"
- [ ] Click "**Generate SOAP Note**"
- [ ] **Wait 5-10 seconds...**
  - [ ] ✅ SOAP note appears
  - [ ] ✅ All 4 sections present (S/O/A/P)
  - [ ] ✅ ICD codes displayed

### API Endpoint Tests

- [ ] **Get authentication token:**
  ```powershell
  $response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" `
    -Method POST `
    -ContentType "application/json" `
    -Body '{"email":"dr.smith@phoenixguardian.health","password":"Doctor123!"}'
  $TOKEN = $response.access_token
  Write-Host "Token: $TOKEN"
  ```

- [ ] **Test drug interaction endpoint:**
  ```powershell
  Invoke-RestMethod -Uri "http://localhost:8000/api/v1/agents/safety/check-interactions" `
    -Method POST `
    -Headers @{"Authorization"="Bearer $TOKEN"} `
    -ContentType "application/json" `
    -Body '{"medications":["lisinopril","potassium"]}'
  ```
  - [ ] Returns interaction with severity

- [ ] **Test readmission prediction:**
  ```powershell
  $body = @{
    age = 75
    has_heart_failure = $true
    has_diabetes = $true
    has_copd = $false
    comorbidity_count = 2
    length_of_stay = 8
    visits_30d = 1
    visits_90d = 3
    discharge_disposition = "snf"
  } | ConvertTo-Json

  Invoke-RestMethod -Uri "http://localhost:8000/api/v1/agents/readmission/predict-risk" `
    -Method POST `
    -Headers @{"Authorization"="Bearer $TOKEN"} `
    -ContentType "application/json" `
    -Body $body
  ```
  - [ ] Returns risk score and recommendations

---

## ⏰ 5 Minutes Before Demo

### Final Readiness

- [ ] **Demo materials ready:**
  - [ ] DEMO_SCRIPT.md open or printed
  - [ ] This checklist open for reference
  
- [ ] **Browser prepared:**
  - [ ] Login page loaded (http://localhost:3000)
  - [ ] Other tabs closed
  - [ ] Bookmarks bar hidden (clean view)
  
- [ ] **Screen sharing ready:**
  - [ ] Tested screen share in meeting tool
  - [ ] Correct screen/window selected
  - [ ] Resolution appropriate for viewers

- [ ] **Notifications silenced:**
  - [ ] System notifications off
  - [ ] Slack/Teams on DND
  - [ ] Phone silenced

- [ ] **Backup ready:**
  - [ ] Second browser ready if needed
  - [ ] Terminal commands in clipboard
  - [ ] Mobile hotspot available (if internet issues)

---

## 🚨 Quick Fixes for Common Issues

### Backend won't start

**Error:** `Address already in use`
```powershell
# Find process on port 8000
netstat -ano | findstr :8000
# Kill it (replace PID)
taskkill /PID <PID> /F
```

**Error:** `ModuleNotFoundError`
```powershell
# Reinstall dependencies
pip install -r requirements.txt
```

---

### Frontend issues

**Blank page:**
```powershell
# Clear node modules and reinstall
cd phoenix-ui
Remove-Item -Recurse -Force node_modules
npm install --legacy-peer-deps
npm start
```

**Port 3000 in use:**
```powershell
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```

---

### SOAP generation fails

**Check 1:** API key valid?
```powershell
# Verify key is set
$env:ANTHROPIC_API_KEY
# Or check .env file
Get-Content .env | Select-String "ANTHROPIC"
```

**Check 2:** Network connectivity?
```powershell
# Test Anthropic API
Invoke-WebRequest -Uri "https://api.anthropic.com" -Method HEAD
```

---

### Database connection error

**Check PostgreSQL:**
```powershell
# Windows Service
Get-Service -Name "postgresql*" | Start-Service

# Or if using Docker
docker start phoenix-postgres
```

**Check connection string:**
```powershell
Get-Content .env | Select-String "DATABASE"
```

---

### Token expired during demo

- Simply **log in again** at http://localhost:3000
- Get new token and update `$TOKEN` variable if using curl/PowerShell

---

## ✅ Demo Readiness Confirmation

Before starting the demo, confirm all items:

| Check | Status |
|-------|--------|
| Backend running on :8000 | ⬜ |
| Frontend running on :3000 | ⬜ |
| Login works | ⬜ |
| SOAP generation works | ⬜ |
| Demo script accessible | ⬜ |
| Screen share tested | ⬜ |
| Notifications silenced | ⬜ |

**All green? You're ready! 🚀**

---

## Post-Demo Cleanup

After the demo:

- [ ] Stop all services gracefully (Ctrl+C in each terminal)
- [ ] Note any issues encountered for future improvement
- [ ] Commit any last-minute fixes
- [ ] Send follow-up email with:
  - GitHub link
  - Demo recording (if available)
  - Compliance documentation
  - Contact information

---

## Demo Credentials Quick Reference

| Role | Email | Password |
|------|-------|----------|
| Physician | dr.smith@phoenixguardian.health | Doctor123! |
| Nurse | nurse.jones@phoenixguardian.health | Nurse123! |
| Admin | admin@phoenixguardian.health | Admin123! |

---

## Service URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/api/docs |
| Health Check | http://localhost:8000/health |
| Mock FHIR Server | http://localhost:8001 |
| FHIR Docs | http://localhost:8001/docs |

---

*Last verified: February 2026*
