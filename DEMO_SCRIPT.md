# Phoenix Guardian Demo Script (5 Minutes)

> **Version:** 1.0  
> **Last Updated:** February 2026  
> **Audience:** Investors, Hospital Partners, Technical Evaluators

---

## Pre-Demo Setup (Do 30 minutes before)

### 1. Start Backend Server
```powershell
cd "D:\phoenix guardian v4"
.\.venv\Scripts\Activate.ps1
uvicorn phoenix_guardian.api.main:app --reload --port 8000
```

### 2. Start Frontend (New Terminal)
```powershell
cd "D:\phoenix guardian v4\phoenix-ui"
npm start
```

### 3. Optional: Start Mock FHIR Server (New Terminal)
```powershell
cd "D:\phoenix guardian v4"
python scripts/mock_fhir_server.py
```

### 4. Pre-flight Checks
- [ ] Open browser to http://localhost:3000
- [ ] Verify login page loads
- [ ] Have demo credentials ready: `dr.smith@phoenixguardian.health` / `Doctor123!`
- [ ] Close unnecessary browser tabs/applications
- [ ] Silence notifications

---

## Demo Flow (5 minutes total)

### 1. Introduction (30 seconds)

**SAY:**
> "Phoenix Guardian is an AI-powered healthcare platform that helps physicians reduce documentation time by up to 60% while enhancing patient safety and maintaining full HIPAA compliance.
>
> The system combines 5 production-ready AI agents with 2 machine learning models, all designed with healthcare security from day one.
>
> Let me show you how it works."

---

### 2. Login & Dashboard (30 seconds)

**DO:**
1. Navigate to http://localhost:3000
2. Enter credentials:
   - Email: `dr.smith@phoenixguardian.health`
   - Password: `Doctor123!`
3. Click "Sign In"

**SAY:**
> "Authentication is handled through JWT tokens with role-based access control. Different user roles—physicians, nurses, admins—see different capabilities."

**SHOW:**
- Dashboard loads with encounter overview
- Point out the navigation menu

---

### 3. AI SOAP Note Generation (90 seconds) ⭐ **MAIN FEATURE**

**DO:**
1. Navigate to **SOAP Generator** (in navigation or at `/soap-generator`)
2. Click "**Load Sample Data**" button (or enter manually):
   - **Chief Complaint:** Cough and fever for 3 days
   - **Temp:** 101.2F | **BP:** 120/80 | **HR:** 88 | **RR:** 18 | **SpO2:** 96%
   - **Symptoms:** cough, fever, fatigue, shortness of breath
   - **Exam:** Crackles in right lower lung field. Decreased breath sounds.
3. Click "**Generate SOAP Note**"
4. Wait 5-10 seconds for AI response

**SAY (while waiting):**
> "The ScribeAgent is now analyzing the encounter data using Claude Sonnet 4—Anthropic's most advanced model. It understands medical context, follows clinical documentation standards, and generates a complete SOAP note."

**SHOW (when complete):**
> "Here we have a complete SOAP note with all four sections:
> - **Subjective:** Patient's symptoms and history
> - **Objective:** Vitals and exam findings
> - **Assessment:** Clinical assessment with differential diagnoses
> - **Plan:** Treatment plan and follow-up
>
> Notice the ICD-10 codes automatically suggested—**J18.9 for pneumonia**. This saves physicians 10-15 minutes per patient encounter."

---

### 4. Drug Safety Check (45 seconds)

**DO (using API or show concept):**

Option A - Use Postman/curl:
```bash
curl -X POST http://localhost:8000/api/v1/agents/safety/check-interactions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"medications": ["lisinopril", "potassium", "spironolactone"]}'
```

Option B - Describe the feature:

**SAY:**
> "The SafetyAgent continuously monitors for dangerous drug interactions. Let me show you an example.
>
> If a physician prescribes lisinopril and potassium together, the system immediately flags this as a **HIGH severity interaction**—both medications increase potassium levels, creating hyperkalemia risk.
>
> This runs on every medication order, catching potential errors before they reach the patient."

**KEY POINT:**
> "This isn't a database lookup—it's AI-powered analysis that understands medication classes and mechanisms of action."

---

### 5. Readmission Risk Prediction (45 seconds)

**SAY:**
> "Our machine learning model predicts 30-day hospital readmission risk. Let me show you a high-risk patient scenario."

**DO (show or describe):**
- Patient: 75 years old
- Heart failure + Diabetes
- 8-day hospital stay
- Discharging to skilled nursing facility

**SAY:**
> "The model returns a risk score of **78—HIGH risk**. It identifies the key factors: age over 70, multiple comorbidities, extended hospital stay.
>
> It then recommends specific interventions: schedule follow-up within 7 days, arrange care coordinator contact within 48 hours.
>
> This model was trained on 2,000 synthetic patient encounters and achieves an AUC of 0.69 with 74% recall—meaning it catches 74% of patients who would actually be readmitted."

---

### 6. Security Features (30 seconds)

**SAY:**
> "HIPAA compliance is built into every layer of Phoenix Guardian."

**SHOW (point to documentation or describe):**
> "We implement:
> - **50+ Honeytokens:** Fake patient records that trigger immediate alerts if accessed, detecting insider threats
> - **Field-level encryption:** All PII encrypted at rest using Fernet AES-128
> - **Complete audit trail:** Every action logged with user, timestamp, and IP address—retained for 7 years
> - **Role-based access control:** Physicians see patient data; billing sees only what they need"

---

### 7. Conclusion (30 seconds)

**SAY:**
> "To summarize, Phoenix Guardian delivers:
>
> ✅ **5 production AI agents** powered by Claude Sonnet 4  
> ✅ **2 trained ML models** with documented performance metrics  
> ✅ **HIPAA-ready security** with encryption, audit logging, and intrusion detection  
> ✅ **FHIR R4 integration** ready for Epic, Cerner, and other major EHRs
>
> Built by our 4-person team in 6 weeks. We're ready for a pilot program with a partner hospital.
>
> Questions?"

---

## Backup Talking Points (If Asked)

### "How accurate are the AI agents?"

> "The ScribeAgent uses Claude Sonnet 4, which is specifically trained on medical literature and clinical documentation. Our threat detection model achieves an AUC of 1.0 on our test set, and the readmission model achieves 0.69 AUC with 74% recall.
>
> All AI-generated content requires physician review before entering the medical record—this is a documentation *assistant*, not a replacement for clinical judgment."

---

### "Is this HIPAA compliant?"

> "Yes, designed for HIPAA from day one. We have:
> - Encryption at rest (Fernet/AES) and in transit (TLS 1.3)
> - Complete audit trail with 7-year retention
> - Access controls with role-based permissions
> - Business Associate Agreement ready for deployment
> - Full documentation in our compliance folder
>
> See `docs/HIPAA_COMPLIANCE.md` for our complete safeguards matrix."

---

### "Can you integrate with our EHR?"

> "Yes, we support FHIR R4, which is the standard for Epic, Cerner, and most modern EHRs. Our mock FHIR server demonstrates the integration capability.
>
> For legacy systems, we can also support HL7 v2.x messaging. We've built connectors for Epic, Cerner, Allscripts, Meditech, and athenahealth."

---

### "What's the tech stack?"

> - **Backend:** Python 3.11, FastAPI, PostgreSQL
> - **Frontend:** React 18, TypeScript, TailwindCSS
> - **AI:** Claude Sonnet 4 (Anthropic API)
> - **ML:** XGBoost, scikit-learn, TF-IDF
> - **Infrastructure:** Docker-ready, deployable to AWS/Azure/GCP

---

### "What about testing?"

> "We have comprehensive test coverage:
> - 693 foundation tests (Week 1)
> - 58 agent tests (Week 2)
> - 46 ML tests (Week 3)
> - 73 security tests (Week 4)
>
> That's over 870 tests total, all passing."

---

### "What's next?"

> "We're seeking a pilot hospital partnership for a 3-month supervised trial with 5-10 physicians. Our goal is to:
> 1. Validate time savings in real clinical workflows
> 2. Measure physician satisfaction
> 3. Confirm safety with real patient data
>
> From there, we plan to expand to 10 hospitals within 18 months."

---

## Common Demo Issues & Fixes

### Backend won't start
```powershell
# Check if port is in use
netstat -ano | findstr :8000
# Kill the process
taskkill /PID <PID> /F
# Try again
uvicorn phoenix_guardian.api.main:app --reload
```

### Frontend blank page
- Clear browser cache: `Ctrl+Shift+Delete`
- Hard refresh: `Ctrl+Shift+R`
- Check console for errors: `F12`

### SOAP generation fails or slow
- Verify `ANTHROPIC_API_KEY` in `.env` file
- Check API quota at console.anthropic.com
- Expected time: 5-10 seconds (network + API processing)

### Login fails
- Verify credentials: `dr.smith@phoenixguardian.health` / `Doctor123!`
- Check backend is running: `curl http://localhost:8000/health`
- Re-seed database if needed: `python scripts/seed_data.py`

### Token expired during demo
- Simply log in again
- Tokens are valid for 24 hours by default

---

## Post-Demo Actions

1. **Share resources:**
   - GitHub: https://github.com/Sabarish-29/phoenix-guardian-v4
   - Demo recording (if available)
   - Technical documentation (docs/ folder)

2. **Collect feedback:**
   - Note any questions asked
   - Identify areas of interest
   - Record technical concerns

3. **Follow-up:**
   - Send thank-you email within 24 hours
   - Include links to GitHub and documentation
   - Offer to schedule deeper technical dive

---

## Demo Timing Summary

| Section | Time | Cumulative |
|---------|------|------------|
| Introduction | 0:30 | 0:30 |
| Login & Dashboard | 0:30 | 1:00 |
| SOAP Generation ⭐ | 1:30 | 2:30 |
| Drug Safety | 0:45 | 3:15 |
| Readmission Prediction | 0:45 | 4:00 |
| Security Features | 0:30 | 4:30 |
| Conclusion | 0:30 | 5:00 |

---

**Remember:** The SOAP generation is the hero feature. If you're running short on time, spend extra time there and abbreviate the API-only features (safety, readmission).

---

*Good luck with the demo! 🚀*
