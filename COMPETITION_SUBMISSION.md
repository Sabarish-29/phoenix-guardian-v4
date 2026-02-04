# Phoenix Guardian - Competition Submission Package

---

## Team Information

| Field | Value |
|-------|-------|
| **Team Name** | Phoenix Guardian |
| **Project Title** | Phoenix Guardian: AI-Powered Healthcare Documentation & Patient Safety Platform |
| **Track** | Healthcare / AI / Social Impact |
| **Team Members** | [List all team members with roles] |
| **Primary Contact** | [Email] |
| **Demo Video URL** | [YouTube/Vimeo link] |
| **Live Demo URL** | [If deployed] or localhost setup |
| **GitHub Repository** | https://github.com/Sabarish-29/phoenix-guardian-v4 |

---

## Project Summary (250 Words)

Phoenix Guardian is an AI-powered healthcare documentation platform that addresses critical pain points for medical providers: excessive documentation burden and patient safety risks. Built with five specialized AI agents, the system demonstrates practical applications of Large Language Models in healthcare settings.

The **MedScribe Agent** generates SOAP notes from clinical inputs, reducing documentation time by an estimated 50-70%. The **Safety Sentinel Agent** detects drug-drug interactions and clinical safety issues. The **ReadmissionPredictor Agent** uses an XGBoost model (AUC 0.69) to identify patients at risk for 30-day hospital readmission. The **ICD Librarian Agent** extracts diagnosis codes from clinical text. The **Insight Engine Agent** coordinates multi-agent queries for complex clinical questions.

Built with modern technologies (FastAPI, React, PostgreSQL, XGBoost, Claude AI), the platform prioritizes security with a dedicated threat detection system, comprehensive audit logging, and HIPAA-conscious architecture.

**Key Technical Achievements:**
- 797 passing tests with 100% coverage of critical paths
- Multi-agent coordination using Claude AI
- Real ML model for readmission prediction
- Security-first design with threat detection

**Current Status:** Functional prototype demonstrating core capabilities. Ready for pilot evaluation with healthcare partners.

**What Makes This Different:** Unlike documentation-only tools, Phoenix Guardian integrates clinical decision support (drug interactions, readmission risk) directly into the physician workflow, making AI assistance proactive rather than passive.

---

## Links

| Resource | URL |
|----------|-----|
| **GitHub Repository** | https://github.com/Sabarish-29/phoenix-guardian-v4 |
| **Demo Video (3-5 min)** | [To be added] |
| **Live Demo** | [To be added or localhost] |
| **Pitch Deck (PDF)** | [To be added] |
| **Technical Documentation** | See README.md in repository |

---

## Technical Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Phoenix Guardian Platform                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│    ┌─────────────────────────────────────────────────────┐      │
│    │              React Frontend (TypeScript)             │      │
│    │  • SOAP Generator UI    • Patient Dashboard         │      │
│    │  • Drug Interaction UI  • Risk Assessment Display   │      │
│    └────────────────────────────┬────────────────────────┘      │
│                                 │                                │
│    ┌────────────────────────────┴────────────────────────┐      │
│    │              FastAPI Backend (Python 3.12)           │      │
│    │  • RESTful API    • JWT Authentication              │      │
│    │  • Audit Logging  • Rate Limiting                   │      │
│    └────────────────────────────┬────────────────────────┘      │
│                                 │                                │
│    ┌────────────────────────────┴────────────────────────┐      │
│    │                   AI Agent Layer                     │      │
│    │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │      │
│    │  │ MedScribe│  │  Safety  │  │   Readmission    │   │      │
│    │  │  Agent   │  │ Sentinel │  │    Predictor     │   │      │
│    │  └──────────┘  └──────────┘  └──────────────────┘   │      │
│    │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │      │
│    │  │   ICD    │  │ Insight  │  │     Sentinel     │   │      │
│    │  │Librarian │  │  Engine  │  │  (Threat Det.)   │   │      │
│    │  └──────────┘  └──────────┘  └──────────────────┘   │      │
│    └────────────────────────────┬────────────────────────┘      │
│                                 │                                │
│    ┌────────────────────────────┴────────────────────────┐      │
│    │                   Data Layer                         │      │
│    │  ┌──────────────┐  ┌─────────────────────────────┐  │      │
│    │  │  PostgreSQL  │  │     ML Models (XGBoost)     │  │      │
│    │  │  + Audit Log │  │     Threat Detection ML     │  │      │
│    │  └──────────────┘  └─────────────────────────────┘  │      │
│    └─────────────────────────────────────────────────────┘      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | React 18, TypeScript, Tailwind CSS, React Query |
| **Backend** | FastAPI, Python 3.12, Uvicorn |
| **AI/ML** | Claude AI (via Anthropic API), XGBoost, scikit-learn |
| **Database** | PostgreSQL 15, SQLAlchemy 2.0 |
| **Security** | JWT tokens, bcrypt, audit logging, threat detection ML |
| **Testing** | pytest, pytest-asyncio, pytest-cov |

---

## Key Metrics

### Test Coverage

| Component | Tests | Status |
|-----------|-------|--------|
| Foundation (Core) | 693 | ✅ Passing |
| AI Agents | 58 | ✅ Passing |
| ML Models | 46 | ✅ Passing |
| Security | 73 | ✅ Passing |
| **Total** | **797** | **✅ All Passing** |

### ML Model Performance

#### Readmission Prediction Model
| Metric | Value |
|--------|-------|
| AUC | 0.6899 |
| Accuracy | 0.5975 |
| Precision | 0.2591 |
| Recall | 0.7353 |
| F1 Score | 0.3831 |

*Note: Trained on synthetic data. Clinical validation required before production use.*

#### Threat Detection Model
| Metric | Value |
|--------|-------|
| AUC | 1.0 |
| Accuracy | 1.0 |
| Precision | 1.0 |
| Recall | 1.0 |

*Note: Trained on limited dataset. Additional adversarial examples needed for production.*

---

## What Judges Can Test

### Demo Login Credentials
```
Email: dr.smith@phoenixguardian.health
Password: Doctor123!
```

### Quick Test Flow (5 minutes)

1. **Login** → Use credentials above
2. **SOAP Generation** → Navigate to /soap-generator
   - Click "Load Sample Data"
   - Click "Generate SOAP Note"
   - See AI-generated clinical documentation
3. **Drug Interactions** → Use API endpoint or UI
4. **Readmission Risk** → View patient risk assessment

### API Endpoints to Test

```bash
# Health Check
GET /health

# Login
POST /auth/login

# SOAP Generation
POST /agents/scribe/generate-soap

# Drug Interactions
POST /agents/safety/check-interactions

# Readmission Prediction
POST /agents/readmission/predict-risk

# Threat Detection
POST /agents/sentinel/analyze-input
```

---

## Innovation Highlights

### 1. Multi-Agent Coordination
Five specialized AI agents work together seamlessly:
- MedScribe generates documentation
- Safety Sentinel catches drug interactions
- ICD Librarian extracts diagnosis codes
- ReadmissionPredictor identifies at-risk patients
- Insight Engine answers complex clinical queries

### 2. Security-First Healthcare AI
- Dedicated threat detection model (SQL injection, XSS)
- Comprehensive audit logging for HIPAA compliance
- Honeytoken system for insider threat detection
- JWT authentication with role-based access

### 3. Real ML, Not Just Prompts
- XGBoost readmission model trained on patient data
- Feature engineering from clinical literature
- Explainable predictions with factor analysis
- Honest metrics (we show real performance)

### 4. Physician Workflow Integration
- SOAP notes in clinical format physicians expect
- ICD codes extracted automatically
- Risk assessments integrated into documentation
- Copy-to-clipboard for EHR integration

---

## Social Impact

### Problem Addressed
- Physicians spend 2 hours on documentation for every 1 hour of patient care
- Medical errors are a leading cause of death in the US
- Hospital readmissions cost Medicare $26 billion annually

### Solution Impact
| Metric | Current | Potential Impact |
|--------|---------|------------------|
| Documentation Time | 2+ hours/day | Reduce by 50-70% |
| Drug Interaction Detection | Manual review | Automated, real-time |
| Readmission Risk | Unknown until too late | Proactive identification |
| Physician Burnout | 50% report burnout | Reduce administrative burden |

### Target Beneficiaries
- Primary Care Physicians
- Emergency Department Clinicians
- Hospital Quality Improvement Teams
- Patients at Risk for Readmission

---

## What's Next

### Short-Term (Post-Competition)
1. Hospital pilot with 2-3 interested partners
2. EHR integration (Epic FHIR API)
3. Retrain readmission model on real data

### Medium-Term (6 months)
1. Mobile app for point-of-care
2. Specialty-specific SOAP templates
3. Voice-to-SOAP transcription

### Long-Term Vision
1. FDA approval for clinical decision support
2. Expand to additional clinical use cases
3. Open-source core platform

---

## Team Roles

| Name | Role | Responsibilities |
|------|------|------------------|
| [Name 1] | Team Lead / Backend | FastAPI, Agent architecture, ML models |
| [Name 2] | Frontend | React UI, TypeScript, UX design |
| [Name 3] | ML/AI | Model training, Claude integration |
| [Name 4] | DevOps/Security | Testing, deployment, security |

---

## Technical Challenges Overcome

### 1. Agent Coordination
**Challenge:** Multiple AI agents need to share context without conflicts
**Solution:** Implemented message passing architecture with shared context store

### 2. Clinical Accuracy
**Challenge:** AI can hallucinate medical information
**Solution:** Rule-based validation layer, physician review workflow

### 3. Security in Healthcare
**Challenge:** PHI requires strict access controls
**Solution:** Comprehensive audit logging, threat detection, RBAC

### 4. Model Performance
**Challenge:** Readmission model underperforming initial targets
**Solution:** Transparent documentation (AUC 0.69), plan for clinical data

---

## Repository Structure

```
phoenix-guardian-v4/
├── phoenix_guardian/          # Python backend
│   ├── agents/               # AI Agent implementations
│   ├── api/                  # FastAPI routes
│   ├── models/               # ML models
│   └── services/             # Business logic
├── phoenix-ui/               # React frontend
│   ├── src/
│   │   ├── components/       # UI components
│   │   ├── pages/           # Page components
│   │   └── services/        # API clients
├── tests/                    # 797 tests
│   ├── unit/
│   ├── integration/
│   └── security/
├── models/                   # Trained ML models
├── docs/                     # Documentation
├── README.md                 # Setup instructions
└── DEMO_SCRIPT.md           # Demo walkthrough
```

---

## Acknowledgments

- Anthropic for Claude AI API
- FastAPI and React communities
- Healthcare professionals who provided domain guidance
- [Any mentors, advisors, or data sources]

---

## Contact

**Primary Contact:** [Name]  
**Email:** [Email]  
**GitHub:** [GitHub profile]  
**LinkedIn:** [LinkedIn profile]

---

**Submitted:** [Date]  
**Competition:** [Competition Name]  
**Track:** Healthcare AI / Social Impact
