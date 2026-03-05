<div align="center">

# Phoenix Guardian 🛡️

**AI-Powered Clinical Documentation & Decision-Support Platform**

[![Python 3.11](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.3-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Tests](https://img.shields.io/badge/tests-915%2B%20passing-brightgreen?logo=pytest&logoColor=white)]()
[![AI Agents](https://img.shields.io/badge/AI%20Agents-35-FF6F00?logo=openai&logoColor=white)]()
[![License](https://img.shields.io/badge/license-Proprietary-red)]()
[![CI](https://img.shields.io/github/actions/workflow/status/Sabarish-29/phoenix-guardian-v4/test.yml?branch=main&label=CI&logo=github)](https://github.com/Sabarish-29/phoenix-guardian-v4/actions)

Phoenix Guardian is a full-stack healthcare platform that combines AI agents, ML models, and post-quantum encryption to assist physicians with clinical documentation, decision support, and security monitoring — all built with HIPAA compliance in mind.

> **⚠️ Not production-ready.** Proof-of-concept built by a college team. ML models trained on synthetic data only. No clinical validation performed.

</div>

---

## 📋 Table of Contents

- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Getting Started](#-getting-started)
- [Usage](#-usage)
- [API Reference](#-api-reference)
- [Configuration](#-configuration)
- [Testing](#-testing)
- [Docker](#-docker)
- [Deployment](#-deployment)
- [Security](#-security)
- [Contributing](#-contributing)
- [Documentation](#-documentation)
- [License](#-license)
- [Authors](#-authors)
- [Project Status](#-project-status)

---

## ✨ Features

### AI Agents (35 agents)

| Category | Agent | Description |
|----------|-------|-------------|
| **Clinical Documentation** | ScribeAgent | Generates SOAP notes from encounter data |
| **Drug Safety** | SafetyAgent | Checks drug interactions, allergies, dosage |
| **Clinical Navigation** | NavigatorAgent | Suggests clinical workflow next steps |
| **Medical Coding** | CodingAgent | Recommends ICD-10 and CPT codes |
| **Security Monitoring** | SentinelQ Agent | Detects SQL injection, XSS, anomalous access |
| **Readmission Risk** | ReadmissionAgent | 30-day readmission prediction (XGBoost) |
| **Fraud Detection** | FraudAgent | NCCI unbundling, upcoding, billing fraud |
| **Clinical Decision** | ClinicalDecisionAgent | Treatment recommendations, risk scores, differential diagnosis |
| **Pharmacy** | PharmacyAgent | Formulary lookup, prior auth, e-prescribing, DUR |
| **Deception Detection** | DeceptionAgent | Consistency analysis, drug-seeking detection |
| **Order Management** | OrdersAgent | Lab, imaging, and prescription suggestions |
| **Rare Disease** | ZebraHunterAgent | Rare/orphan disease detection via OrphaData |
| **Treatment Validation** | TreatmentShadowAgent | Evidence-based treatment validation via OpenFDA |
| **Patient Monitoring** | SilentVoiceAgent | Non-verbal patient vitals monitoring (ICU) |
| **Population Health** | PopulationHealthAgent | Population-level analytics and reporting |
| **Quality Metrics** | QualityAgent | Clinical quality metrics computation |
| **Telehealth** | TelehealthAgent | Telehealth session management, consent, follow-up |
| **Risk Stratification** | RiskStratifier | Patient risk stratification engine |
| **Care Gap Analysis** | CareGapAnalyzer | Identifies gaps in care plans |
| **Prior Authorization** | PriorAuthAgent | Prior authorization workflow automation |
| **Cross-Agent Correlation** | CrossAgentCorrelator | Correlates findings across multiple agents |
| **Agent Orchestration** | AgentOrchestrator | 4-phase parallel orchestrator with circuit breakers |

### ML Models

| Model | Type | Training Data | AUC | Notes |
|-------|------|---------------|-----|-------|
| Threat Detection | TF-IDF + Logistic Regression | 2,000 synthetic samples | 1.0000 | Integrated into SentinelQ |
| Readmission Risk | XGBoost | 2,000 synthetic encounters | 0.6899 | 30-day readmission prediction |

> **Note:** Models trained on synthetic data only. Clinical validation required before patient use.

### Security & Compliance

- **Post-Quantum Cryptography:** Kyber-1024 + AES-256-GCM hybrid encryption
- **PHI Encryption:** 18 HIPAA PHI fields auto-encrypted at field level
- **Honeytoken System:** Fake patient records detect unauthorized access
- **Audit Logging:** Complete HIPAA-compliant audit trail (7-year retention)
- **Role-Based Access Control (RBAC):** Physician, Nurse, Admin, Readonly roles
- **ML Threat Detection:** Real-time anomaly scoring and attack detection
- **Attacker Intelligence:** Fingerprinting and threat intelligence feeds
- **Keystroke Dynamics:** Behavioral biometric detection
- **Security Console:** Real-time threat feed, PQC status, system health dashboard

### Voice & Transcription

- **Groq Whisper:** Primary transcription via Groq Cloud API
- **Live Preview:** Periodic 5-second Whisper transcription during recording
- **Medical Term Enrichment:** Automatic medical terminology detection and normalization
- **Multi-Provider Support:** Groq, OpenAI Whisper, Azure Speech, Google Speech, local Whisper

### Integration & Infrastructure

- **FHIR R4:** Client library + mock server for EHR integration
- **Temporal.io:** SAGA workflow orchestration with 12 activities and compensation rollback
- **Federated Learning:** Privacy-preserving distributed model training
- **WebSocket:** Real-time encounter updates
- **Docker:** Full containerized stack (10 services) with Nginx, Grafana, Prometheus
- **OpenTelemetry:** Distributed tracing and observability

---

## 🛠️ Tech Stack

### Backend

| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11 | Runtime |
| FastAPI | 0.115.0 | REST API framework |
| SQLAlchemy | 2.0.35 | ORM |
| Alembic | 1.13.2 | Database migrations |
| PostgreSQL | 15 / 16 | Primary database |
| Redis | 7.x | Caching & pub/sub |
| Pydantic | 2.9.2 | Data validation |
| PyJWT | 2.9.0 | JWT authentication |
| passlib + bcrypt | 1.7.4 / 4.0.1 | Password hashing |
| Anthropic SDK | 0.34.0 | Claude AI (legacy) |
| Groq SDK | via httpx | LLM inference (primary) |
| XGBoost | 2.1.1 | ML readmission model |
| scikit-learn | 1.5.2 | ML pipelines |
| NumPy / SciPy | 2.0.2 / 1.14.1 | Numerical computing |
| structlog | 24.4.0 | Structured logging |
| cryptography | 43.0.1 | Encryption (PQC, PHI) |
| Gunicorn | 21.2.0 | Production WSGI server |
| Uvicorn | 0.30.6 | ASGI server |

### Frontend

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 18.2 | UI framework |
| TypeScript | 5.3 | Type-safe JavaScript |
| React Router | 6.21 | Client-side routing |
| TanStack React Query | 5.17 | Server state management |
| Zustand | 4.4.7 | Client state management |
| Axios | 1.6.5 | HTTP client |
| Recharts | 3.7.0 | Data visualization |
| TailwindCSS | 3.4.1 | Utility-first CSS |
| Playwright | 1.41 | E2E testing |
| react-scripts | 5.0.1 | Build toolchain (CRA) |

### Infrastructure

| Technology | Purpose |
|-----------|---------|
| Docker + Docker Compose | Containerization |
| Nginx | Reverse proxy & SSL termination |
| Grafana + Prometheus | Monitoring & dashboards |
| Celery + Flower | Background task processing |
| GitHub Actions | CI/CD |
| Render | Backend hosting (free tier) |
| Netlify | Frontend hosting |
| OpenTelemetry | Distributed tracing |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│         React 18 Frontend           │  TypeScript, TailwindCSS, Zustand
│  (Netlify / localhost:3000)         │  Voice Recording, Dark Theme
└──────────────┬──────────────────────┘
               │ REST API + WebSocket
               ▼
┌─────────────────────────────────────┐
│         FastAPI Backend             │  Python 3.11, 17 route modules
│  (Render / localhost:8000)          │  JWT Auth, RBAC, CORS
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────────────────────────────┐
    │          │                                   │
    ▼          ▼                                   ▼
┌────────┐ ┌──────────────────────┐  ┌───────────────────────┐
│ Agents │ │   ML Models          │  │   Security Layer      │
│ (35)   │ │ • Threat Detection   │  │ • PQC Encryption      │
│        │ │ • Readmission Risk   │  │ • PHI Field Encrypt   │
│ 4-phase│ │                      │  │ • Honeytokens         │
│parallel│ │                      │  │ • Audit Logging       │
│orchestr│ │                      │  │ • ML Threat Detection │
└────────┘ └──────────────────────┘  └───────────────────────┘
    │               │                         │
    └───────────────┼─────────────────────────┘
                    ▼
    ┌───────────────────────────────┐
    │  PostgreSQL 16  │  Redis 7.x │
    │  (Data Store)   │  (Cache)   │
    └───────────────────────────────┘
```

### Agent Orchestration Pipeline

```
Phase 1 (Parallel): Scribe + Sentinel + Safety
Phase 2 (Parallel): Coding + ClinicalDecision + Deception
Phase 3 (Parallel): Fraud + Orders + Pharmacy
Phase 4 (Sequential): Navigator (uses results from phases 1-3)
```

---

## 📁 Project Structure

```
phoenix-guardian-v4/
├── phoenix_guardian/              # Backend Python package
│   ├── api/
│   │   ├── main.py               # FastAPI app entry point (17 routers)
│   │   ├── auth/
│   │   │   └── utils.py          # JWT, password hashing, RBAC
│   │   └── routes/               # 17 route modules
│   │       ├── agents.py         # AI agent invocation endpoints
│   │       ├── auth.py           # Login, register, token refresh
│   │       ├── correlations.py   # Cross-agent correlation
│   │       ├── encounters.py     # Encounter CRUD + WebSocket
│   │       ├── feedback.py       # Clinician feedback collection
│   │       ├── health.py         # Health check probes
│   │       ├── learning.py       # ML learning pipeline
│   │       ├── orchestration.py  # Multi-agent orchestration
│   │       ├── patients.py       # Patient record management
│   │       ├── pqc.py            # Post-quantum cryptography
│   │       ├── security_console.py  # Admin security dashboard
│   │       ├── silent_voice.py   # ICU patient monitoring
│   │       ├── transcription.py  # Voice-to-text transcription
│   │       ├── treatment_shadow.py  # Treatment validation
│   │       ├── v5_dashboard.py   # V5 unified dashboard
│   │       └── zebra_hunter.py   # Rare disease detection
│   ├── agents/                   # 35 AI agents
│   │   ├── base_agent.py         # Abstract base agent class
│   │   ├── scribe_agent.py       # SOAP note generation
│   │   ├── safety_agent.py       # Drug interaction checks
│   │   ├── navigator_agent.py    # Clinical workflow navigation
│   │   ├── coding_agent.py       # ICD-10/CPT code suggestion
│   │   ├── sentinel_q_agent.py   # Security threat analysis
│   │   ├── zebra_hunter_agent.py # Rare disease detection
│   │   ├── treatment_shadow_agent.py  # Evidence-based validation
│   │   ├── silent_voice_agent.py # Non-verbal patient monitoring
│   │   ├── fraud.py              # Billing fraud detection
│   │   ├── clinical_decision.py  # Clinical decision support
│   │   ├── pharmacy.py           # Pharmacy management
│   │   ├── deception_detection.py # Security deception detection
│   │   ├── order_management.py   # Clinical order management
│   │   ├── population_health_agent.py  # Population analytics
│   │   ├── quality_agent.py      # Quality metrics
│   │   ├── telehealth_agent.py   # Telehealth sessions
│   │   └── ...                   # + more specialized agents
│   ├── services/                 # External service integrations
│   │   ├── ai_service.py         # LLM calls (Groq / Ollama / Anthropic)
│   │   ├── voice_transcription.py # Multi-provider ASR
│   │   ├── medical_terminology.py # Medical term normalization
│   │   └── security_event_service.py # Security event management
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── user.py               # User / clinician accounts
│   │   ├── encounter.py          # Patient encounters
│   │   ├── soap_note.py          # SOAP notes
│   │   ├── audit_log.py          # HIPAA audit trail
│   │   ├── security_event.py     # Security events
│   │   └── ...                   # hospital, agent_metrics, etc.
│   ├── security/                 # Security subsystem (15 modules)
│   │   ├── pqc_encryption.py     # Kyber-1024 post-quantum crypto
│   │   ├── phi_encryption.py     # PHI field-level encryption
│   │   ├── encryption.py         # Standard AES encryption
│   │   ├── honeytoken_generator.py # Honeytoken creation
│   │   ├── ml_detector.py        # ML-based threat detection
│   │   ├── anomaly_scorer.py     # Access anomaly scoring
│   │   ├── audit_logger.py       # HIPAA audit log writer
│   │   └── ...                   # alerting, intelligence, forensics
│   ├── database/
│   │   └── connection.py         # DB connection with pool management
│   ├── workflows/                # Temporal.io SAGA orchestration
│   ├── learning/                 # Bidirectional ML pipeline
│   ├── orchestration/            # Agent coordination engine
│   └── config/                   # Application configuration
│
├── phoenix-ui/                   # React frontend
│   ├── src/
│   │   ├── pages/                # 17 page components
│   │   │   ├── LoginPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── CreateEncounterPage.tsx
│   │   │   ├── SOAPGeneratorPage.tsx
│   │   │   ├── AdminHomePage.tsx
│   │   │   ├── AdminSecurityConsolePage.tsx
│   │   │   ├── ZebraHunterPage.tsx
│   │   │   ├── TreatmentShadowPage.tsx
│   │   │   ├── SilentVoicePage.tsx
│   │   │   ├── V5DashboardPage.tsx
│   │   │   └── ...
│   │   ├── components/           # 20+ reusable components
│   │   │   ├── VoiceRecorder.tsx
│   │   │   ├── TranscriptEditor.tsx
│   │   │   ├── Header.tsx / Layout.tsx
│   │   │   ├── ImpactCalculator.tsx
│   │   │   └── security/        # Security dashboard components
│   │   ├── hooks/                # Custom React hooks
│   │   │   ├── useMedicalTranscription.ts
│   │   │   ├── useConnectivity.ts
│   │   │   └── useSilentVoiceStream.ts
│   │   ├── stores/
│   │   │   └── authStore.ts      # Zustand auth state
│   │   └── api/
│   │       ├── client.ts         # Axios client with JWT interceptors
│   │       └── services/         # API service layer
│   ├── e2e/                      # Playwright E2E tests
│   └── public/
│
├── tests/                        # 915+ tests (27 subdirectories)
│   ├── agents/                   # Agent unit tests
│   ├── security/                 # Security tests
│   ├── integration/              # Cross-module integration tests
│   ├── workflows/                # Temporal workflow tests
│   ├── ml/                       # ML model tests
│   ├── compliance/               # Compliance validation
│   ├── performance/              # Performance benchmarks
│   └── ...
│
├── scripts/                      # 34 utility scripts
├── models/                       # Trained ML model artifacts
├── data/                         # Training datasets (synthetic)
├── docs/                         # 26 docs + 20 ADRs + OpenAPI spec
├── docker/                       # Production Docker configs (10 services)
├── config/                       # Prometheus, Grafana, alerting configs
├── k8s/                          # Kubernetes manifests
├── migrations/                   # Alembic DB migrations
├── .github/workflows/test.yml    # CI/CD pipeline
├── docker-compose.yml            # Quick local dev (Postgres + Redis)
├── Dockerfile                    # Render production image
├── render.yaml                   # Render deployment blueprint
├── netlify.toml                  # Netlify frontend config
├── Makefile                      # Dev automation targets
├── pyproject.toml                # Python tooling config
├── requirements.txt              # Full Python dependencies (39 packages)
├── requirements-prod.txt         # Production dependencies (24 packages)
└── requirements-dev.txt          # Dev-only dependencies (10 packages)
```

---

## 📋 Prerequisites

| Requirement | Minimum Version | Notes |
|------------|----------------|-------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| PostgreSQL | 15+ | Primary database |
| Redis | 7.0+ | Caching (optional for dev) |
| Docker | 20.10+ | For containerized setup (optional) |
| Groq API Key | — | Required for AI agent functionality |

---

## 🚀 Getting Started

### Installation

```bash
# Clone the repository
git clone https://github.com/Sabarish-29/phoenix-guardian-v4.git
cd phoenix-guardian-v4

# Option A: Automated setup (Unix)
chmod +x setup.sh && ./setup.sh

# Option A: Automated setup (Windows PowerShell)
.\setup.ps1

# Option B: Manual setup
python -m venv .venv
# Unix:
source .venv/bin/activate
# Windows:
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### Environment Setup

Copy the example environment file and configure:

```bash
cp .env.example .env
```

#### Required Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | **Yes** | — | Groq Cloud API key for AI agents |
| `DB_HOST` | **Yes** | `localhost` | PostgreSQL host |
| `DB_PORT` | **Yes** | `5432` | PostgreSQL port |
| `DB_NAME` | **Yes** | `phoenix_guardian` | Database name |
| `DB_USER` | **Yes** | `postgres` | Database user |
| `DB_PASSWORD` | **Yes** | — | Database password |
| `JWT_SECRET_KEY` | **Yes** | dev fallback | JWT signing secret (`python -c "import secrets; print(secrets.token_hex(32))"`) |
| `DATABASE_URL` | Alt | — | Full connection string (alternative to individual DB_* vars) |
| `CORS_ORIGIN` | No | — | Additional allowed CORS origin |
| `DEMO_MODE` | No | `false` | Use cached responses for demo |
| `ENVIRONMENT` | No | `development` | `development` / `production` |

<details>
<summary><b>All Environment Variables (103 total)</b></summary>

#### AI Providers

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model name |
| `AI_PROVIDER` | auto-detect | Force provider: `groq` or `ollama` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2:1b` | Ollama model name |
| `ANTHROPIC_API_KEY` | — | Anthropic Claude API key (legacy) |
| `OPENAI_API_KEY` | — | OpenAI Whisper API key |
| `AZURE_SPEECH_KEY` | — | Azure Speech Services key |
| `AZURE_SPEECH_REGION` | `eastus` | Azure Speech region |

#### Database Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_POOL_SIZE` | `10` | Connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Max overflow connections |
| `DB_POOL_TIMEOUT` | `30` | Pool timeout (seconds) |
| `DB_ECHO` | `false` | SQLAlchemy SQL echo logging |

#### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `PHOENIX_DEV_MODE` | `false` | Enable dev-mode login without database |
| `ENCRYPTION_KEY` | auto-generated | Fernet encryption key |
| `PHI_ENCRYPTION_ENABLED` | `false` | Enable PHI field-level encryption |
| `PHI_ADDITIONAL_FIELDS` | — | Comma-separated additional PHI fields |
| `PHI_ENCRYPTION_AUDIT` | `true` | Audit PHI encryption events |
| `TLS_CERT_FILE` | — | TLS certificate path |
| `TLS_KEY_FILE` | — | TLS private key path |

#### Redis / Caching

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |

#### V5 Agent Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ORPHADATA_API_KEY` | — | OrphaData API key (Zebra Hunter) |
| `ORPHADATA_BASE_URL` | `https://api.orphadata.com` | OrphaData API URL |
| `OPENFDA_BASE_URL` | `https://api.fda.gov` | OpenFDA API URL |
| `GHOST_PROTOCOL_MIN_CLUSTER` | `2` | Min patients for ghost protocol alert |
| `GHOST_PROTOCOL_TTL_DAYS` | `30` | Ghost case Redis TTL |
| `SHADOW_TREND_THRESHOLD_PCT` | `-20` | Treatment decline threshold |
| `SHADOW_MIN_LAB_RESULTS` | `2` | Min lab results for trend analysis |
| `SILENT_VOICE_BASELINE_WINDOW_MINUTES` | `120` | Vitals baseline window |
| `SILENT_VOICE_ZSCORE_THRESHOLD` | `2.5` | Abnormal vitals z-score threshold |

#### Monitoring

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Application log level |
| `SENTRY_DSN` | — | Sentry error tracking |
| `METRICS_ENABLED` | `true` | Prometheus metrics |
| `OTEL_SERVICE_NAME` | `phoenix-guardian` | OpenTelemetry service name |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | OTLP endpoint |

#### Alerting (Production)

| Variable | Default | Description |
|----------|---------|-------------|
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SLACK_WEBHOOK_URL` | — | Slack incoming webhook |
| `DATADOG_API_KEY` | — | Datadog API key |
| `PAGERDUTY_API_KEY` | — | PagerDuty API key |

#### Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_PQC_ENCRYPTION` | `true` | Post-quantum cryptography |
| `ENABLE_HONEYTOKEN_SYSTEM` | `true` | Honeytoken intrusion detection |
| `ENABLE_REAL_TIME_ALERTS` | `true` | Real-time security alerts |
| `ENABLE_ML_DETECTION` | `true` | ML-based threat detection |
| `ENABLE_AUDIT_LOGGING` | `true` | Audit logging |

#### Frontend (React)

| Variable | Default | Description |
|----------|---------|-------------|
| `REACT_APP_API_URL` | `/api/v1` | Backend API URL |
| `REACT_APP_ENV` | — | Frontend environment |

</details>

### Database Setup

```bash
# Option A: Docker (recommended for local dev)
docker-compose up -d   # Starts PostgreSQL 15 + Redis 7

# Option B: Manual PostgreSQL
createdb phoenix_guardian

# Run migrations
python scripts/migrate.py

# Seed demo data
python scripts/seed_data.py
python scripts/seed_honeytokens.py
```

### Running the Application

#### Development

```bash
# Terminal 1: Start backend
uvicorn phoenix_guardian.api.main:app --reload --port 8000

# Terminal 2: Start frontend
cd phoenix-ui
npm install --legacy-peer-deps
npm start

# Access the application
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/api/docs
# ReDoc:    http://localhost:8000/api/redoc
```

#### Using Make

```bash
make setup      # One-command project setup
make backend    # Start backend API server
make frontend   # Start frontend dev server
make test       # Run test suite
make lint       # Run code quality checks
make migrate    # Run database migrations
make validate   # Validate installation
make clean      # Remove generated files
```

### Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| Physician | `dr.smith@phoenixguardian.health` | `Doctor123!` |
| Admin | `admin@phoenixguardian.health` | `Admin123!` |
| Nurse | `nurse.jones@phoenixguardian.health` | `Nurse123!` |

---

## 📖 Usage

### Creating an Encounter

1. Login with demo credentials
2. Click **"New Encounter"** from the dashboard
3. Fill in patient information
4. Use the **Voice Recorder** to dictate clinical notes (uses Groq Whisper)
5. The transcription appears in real-time with live preview updates every 5 seconds
6. Submit to generate an AI-powered SOAP note

### SOAP Note Generation

Navigate to the **SOAP Generator** page and provide encounter details. The ScribeAgent generates structured SOAP notes with:
- Subjective findings
- Objective data
- Assessment & differential diagnoses
- Plan with follow-up recommendations

### Security Console (Admin)

Admin users can access the **Security Console** which provides:
- Live threat feed with real-time security events
- Honeytoken monitoring panel
- PQC encryption status
- System health dashboard
- Attacker fingerprinting

### V5 Agents Dashboard

The unified V5 Dashboard showcases three specialized agents:
- **Zebra Hunter:** Scans for rare/orphan diseases based on symptom patterns
- **Treatment Shadow:** Validates treatment plans against OpenFDA evidence
- **Silent Voice:** Monitors ICU patient vitals for non-verbal deterioration detection

---

## 🔌 API Reference

All endpoints are under the base path `/api/v1`. Interactive documentation is available at `/api/docs` (Swagger UI) and `/api/redoc`.

### Authentication

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/auth/login` | Login with email/password → JWT tokens | No |
| `POST` | `/auth/register` | Register new user (admin only) | Admin |
| `POST` | `/auth/refresh` | Refresh access token | No |
| `POST` | `/auth/logout` | Logout (audit trail) | Yes |
| `GET` | `/auth/me` | Get current user profile | Yes |
| `POST` | `/auth/change-password` | Change password | Yes |

### Health & System

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/health` | Health check with agent status | No |
| `GET` | `/system/connectivity` | Check Groq/OrphaData/OpenFDA connectivity | No |

### Patients

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/patients` | List patients | Yes |
| `POST` | `/patients` | Create patient | Yes |
| `GET` | `/patients/{id}` | Get patient details | Yes |
| `PUT` | `/patients/{id}` | Update patient | Yes |

### Encounters

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/encounters` | List encounters | Yes |
| `POST` | `/encounters` | Create encounter | Yes |
| `GET` | `/encounters/{id}` | Get encounter details | Yes |
| `POST` | `/encounters/workflow` | Start SAGA workflow | Yes |
| `GET` | `/encounters/workflow/{id}/status` | Workflow status | Yes |

### AI Agents

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/agents/scribe/generate-soap` | Generate SOAP note | Yes |
| `POST` | `/agents/safety/check-interactions` | Check drug interactions | Yes |
| `POST` | `/agents/navigator/suggest-workflow` | Suggest next steps | Yes |
| `POST` | `/agents/coding/suggest-codes` | ICD-10/CPT suggestions | Yes |
| `POST` | `/agents/sentinel/analyze-input` | Security threat analysis | Yes |
| `POST` | `/agents/readmission/predict-risk` | Readmission risk prediction | Yes |
| `POST` | `/agents/fraud/detect` | Full fraud analysis | Yes |
| `POST` | `/agents/clinical-decision/recommend-treatment` | Treatment recommendations | Yes |
| `POST` | `/agents/clinical-decision/differential` | Differential diagnosis | Yes |
| `POST` | `/agents/pharmacy/check-formulary` | Formulary lookup | Yes |
| `POST` | `/agents/pharmacy/send-prescription` | e-Prescribing | Yes |
| `POST` | `/agents/deception/analyze-consistency` | Consistency analysis | Yes |
| `POST` | `/agents/orders/suggest-labs` | Lab order suggestions | Yes |
| `POST` | `/agents/orders/suggest-imaging` | Imaging suggestions | Yes |

### Orchestration

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/orchestration/process` | Process encounter through all agents | Yes |
| `GET` | `/orchestration/health` | All agent health status | Yes |
| `GET` | `/orchestration/agents` | List registered agents | Yes |

### Post-Quantum Cryptography

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/pqc/encrypt` | Encrypt data with Kyber-1024 | Yes |
| `POST` | `/pqc/encrypt-phi` | Encrypt PHI fields | Yes |
| `POST` | `/pqc/decrypt-phi` | Decrypt PHI fields | Yes |
| `POST` | `/pqc/rotate-keys` | Rotate encryption keys | Admin |
| `GET` | `/pqc/health` | PQC subsystem health | Yes |

### Voice Transcription

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/transcription/upload-audio` | Upload audio for transcription | Yes |
| `POST` | `/transcription/process` | Process text for medical terms | Yes |
| `POST` | `/transcription/verify-terms` | Verify medical terminology | Yes |
| `GET` | `/transcription/providers` | List available ASR providers | Yes |

### V5 Agents

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/zebra-hunter/analyze` | Rare disease detection | Yes |
| `POST` | `/treatment-shadow/validate` | Treatment validation | Yes |
| `GET` | `/silent-voice/monitor/{patient_id}` | Patient vitals monitoring | Yes |
| `GET` | `/v5-dashboard/summary` | V5 aggregate dashboard | Yes |

### Learning Pipeline

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/learning/feedback` | Record physician feedback | Yes |
| `POST` | `/learning/run-cycle` | Trigger training cycle | Admin |
| `GET` | `/learning/status` | Pipeline overview | Yes |

---

## ⚙️ Configuration

### Code Quality Tools (pyproject.toml)

| Tool | Setting | Value |
|------|---------|-------|
| **Black** | Line length | 88 |
| **isort** | Profile | black |
| **mypy** | Python version | 3.11, strict mode |
| **pylint** | Max line length | 88 |
| **pytest** | Min version | 7.0, asyncio_mode=auto |
| **coverage** | Fail under | 5% |

### Frontend Build Configuration

| Setting | Value |
|---------|-------|
| Build tool | react-scripts (CRA) |
| Dev proxy | `http://localhost:8000` |
| ESLint | `react-app` + `react-app/jest` |
| PostCSS | autoprefixer + tailwindcss |

---

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v --no-cov

# Run specific test categories
pytest tests/agents/ -v                    # AI agent tests
pytest tests/security/ -v                  # Security tests
pytest tests/ml/ -v                        # ML model tests
pytest tests/integration/ -v              # Integration tests
pytest tests/compliance/ -v               # Compliance tests
pytest tests/workflows/ -v                # Temporal workflow tests
pytest tests/performance/ -v              # Performance benchmarks

# Run with coverage report
pytest tests/ --cov=phoenix_guardian --cov-report=html
open htmlcov/index.html

# Run sprint test suites
pytest tests/agents/test_all_10_agents.py tests/security/test_pqc_enhancement.py \
       tests/workflows/test_temporal_workflow.py tests/integration/test_full_integration.py \
       -v --no-cov
```

### Frontend Tests

```bash
cd phoenix-ui

# Unit tests
npm test

# E2E tests (Playwright)
npm run test:e2e
npm run test:e2e:headed     # With browser UI
npm run test:e2e:debug      # Debug mode
npm run test:e2e:chromium   # Chromium only
npm run test:e2e:firefox    # Firefox only
npm run test:e2e:webkit     # WebKit only
npm run test:e2e:report     # View test report
```

### Test Coverage Summary

| Category | Tests | Status |
|----------|-------|--------|
| Foundation | 693 | ✅ Passing |
| AI Agents | 113 | ✅ Passing |
| ML Models | 46 | ✅ Passing |
| Security | 95 | ✅ Passing |
| Integration | 41+ | ✅ Passing |
| Sprint Tests | 118 | ✅ Passing |
| **Total** | **915+** | ✅ |

---

## 🐳 Docker

### Quick Local Development

Start database and cache services only:

```bash
docker-compose up -d
# Starts:
#   PostgreSQL 15 on port 5432
#   Redis 7 on port 6379
```

### Full Production Stack

```bash
cd docker
docker-compose up -d
```

This starts 10 services:

| Service | Port | Description |
|---------|------|-------------|
| **app** | 8000 | FastAPI backend (Gunicorn + Uvicorn) |
| **worker** | — | Celery background worker |
| **beacon** | 8080 | Honeytoken beacon server |
| **postgres** | 5432 | PostgreSQL 16 (tuned: shared_buffers=512MB, max_connections=200) |
| **redis** | 6379 | Redis 7.2 (password-protected, AOF, 512MB maxmemory) |
| **nginx** | 80, 443 | Reverse proxy + SSL termination |
| **monitor** | 3000, 9090 | Grafana + Prometheus dashboards |
| **flower** | 5555 | Celery worker monitoring UI |
| **redis-exporter** | — | Prometheus Redis metrics exporter |
| **postgres-exporter** | — | Prometheus PostgreSQL metrics exporter |

### Building the Production Image

```bash
docker build -t phoenix-guardian -f Dockerfile .
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:pass@host/db" \
  -e GROQ_API_KEY="your-key" \
  -e JWT_SECRET_KEY="your-secret" \
  phoenix-guardian
```

---

## 🚢 Deployment

### Render (Backend)

The project includes a `render.yaml` blueprint for one-click deployment:

1. Connect your GitHub repo to [Render](https://render.com)
2. Create a new **Web Service** from the Dockerfile
3. Set environment variables:
   - `DATABASE_URL` — from Render PostgreSQL
   - `GROQ_API_KEY` — your Groq Cloud API key
   - `JWT_SECRET_KEY` — auto-generated
   - `CORS_ORIGIN` — your Netlify frontend URL
   - `DEMO_MODE` — `true`
4. Deploy

> **Note:** Render free tier services sleep after 15 minutes of inactivity. First request may take 30–60 seconds for cold start.

**Live Backend:** `https://phoenix-guardian-api-fuq0.onrender.com`

### Netlify (Frontend)

The `netlify.toml` configures automatic builds:

1. Connect GitHub repo to [Netlify](https://netlify.com)
2. Build settings are auto-detected from `netlify.toml`:
   - Base directory: `phoenix-ui`
   - Build command: `npm install --legacy-peer-deps && npm run build`
   - Publish directory: `phoenix-ui/build`
3. `REACT_APP_API_URL` is configured in `netlify.toml` build environment

**Live Frontend:** `https://phoenixguardianv41.netlify.app`

### CI/CD (GitHub Actions)

The `.github/workflows/test.yml` workflow runs on every push/PR to `main`/`develop`:

1. **Backend job:** Python 3.11 + PostgreSQL 16 service → import verification + core tests
2. **Frontend job:** Node 18 → `npm ci --legacy-peer-deps` → production build

---

## 🔐 Security

### Authentication & Authorization

- **JWT-based authentication** with access tokens (1 hour) and refresh tokens (7 days)
- **bcrypt password hashing** via passlib
- **Role-based access control (RBAC):** Physician, Nurse, Admin, Readonly
- **Protected routes** on frontend with auth-gated components

### Encryption

- **Post-Quantum Cryptography:** Kyber-1024 + AES-256-GCM hybrid encryption
- **PHI Field-Level Encryption:** 18 HIPAA-defined PHI fields auto-encrypted
- **Key Rotation:** Zero-downtime encryption key migration
- **TLS 1.3** for data in transit

### Intrusion Detection

- **Honeytokens:** 50+ fake patient records detect unauthorized data access
- **ML Threat Detection:** TF-IDF + Logistic Regression model for real-time threat classification
- **Anomaly Scoring:** Behavioral analysis of access patterns
- **Keystroke Dynamics:** Biometric behavioral detection
- **Attacker Intelligence Database:** Fingerprinting and threat feed integration

### Compliance

- **HIPAA:** Complete audit trail, PHI encryption, access controls, breach notification procedures
- **FDA CDS:** Classification documentation for clinical decision support
- **Security Policies:** Incident response, risk analysis, on-call runbooks

### Reporting Vulnerabilities

This is a proof-of-concept project. For security concerns, open an issue on the GitHub repository or contact the team directly.

---

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/your-feature`
3. **Install** dev dependencies: `pip install -r requirements-dev.txt`
4. **Code** your changes following the project style:
   - Python: Black (88 chars), isort, mypy strict mode
   - TypeScript: ESLint with `react-app` config
5. **Test** your changes: `pytest tests/ -v`
6. **Lint** your code: `make lint`
7. **Commit** with a descriptive message
8. **Push** and open a Pull Request

---

## 📚 Documentation

### Compliance & Security

| Document | Description |
|----------|-------------|
| [HIPAA Compliance](docs/HIPAA_COMPLIANCE.md) | HIPAA compliance framework |
| [FDA CDS Classification](docs/FDA_CDS_CLASSIFICATION.md) | FDA clinical decision support classification |
| [Security Policies](docs/SECURITY_POLICIES.md) | Security policy documentation |
| [Incident Response](docs/INCIDENT_RESPONSE.md) | Incident response playbook |
| [Risk Analysis](docs/RISK_ANALYSIS.md) | Risk analysis document |

### Operations

| Document | Description |
|----------|-------------|
| [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) | Deployment instructions |
| [Production Deployment](docs/PRODUCTION_DEPLOYMENT_GUIDE.md) | Production deployment guide |
| [Production Runbook](docs/PRODUCTION_RUNBOOK.md) | Operations runbook |
| [On-Call Runbook](docs/ON_CALL_RUNBOOK.md) | On-call procedures |

### API & Architecture

| Document | Description |
|----------|-------------|
| [API Reference](docs/API.md) | Full API documentation |
| [OpenAPI Spec](docs/api/openapi.yaml) | OpenAPI 3.0 specification |
| [ADRs](docs/adr/) | 20 Architecture Decision Records |

### Project Reports

| Document | Description |
|----------|-------------|
| [Sprint Report](SPRINT_REPORT.md) | Detailed 7-sprint development report |
| [Demo Script](DEMO_SCRIPT.md) | 5-minute demo walkthrough |
| [Demo Checklist](DEMO_CHECKLIST.md) | Pre-demo verification checklist |
| [Phase 5 Report](docs/PHASE5_IMPLEMENTATION_REPORT.md) | V5 agents implementation report |

---

## 📜 License

**Proprietary** — Demo/Educational Use Only

Not licensed for clinical use. Contact the team for licensing inquiries.

---

## 👥 Authors

**Sabarish S** — Full-stack development, AI agents, security, infrastructure

- GitHub: [@Sabarish-29](https://github.com/Sabarish-29)

---

## 📊 Project Status

**Active Development** — Proof of Concept

### What's Complete ✅

- 35 AI agents with LLM integration (Groq / Ollama / Anthropic failover)
- 2 trained ML models (synthetic data)
- Post-quantum encryption (Kyber-1024 + AES-256-GCM)
- Full HIPAA compliance framework
- 915+ passing tests across 27 test categories
- Voice transcription with live Groq Whisper preview
- Dark theme UI with CSS design system
- Docker containerized deployment (10 services)
- CI/CD pipeline with GitHub Actions
- Live deployment on Render (backend) + Netlify (frontend)

### What's NOT Production-Ready ❌

- ML models trained on **synthetic data only** — no clinical validation
- No IRB approval or clinical studies
- No external penetration testing or SOC 2 certification
- No multi-factor authentication
- Not load tested at scale
- No Business Associate Agreements executed
- No malpractice insurance or formal HIPAA audit

---

## 🙏 Acknowledgments

- **Groq** — Fast LLM inference API
- **Anthropic** — Claude API (legacy agent support)
- **HL7 FHIR** — Healthcare interoperability standard
- **FastAPI** — Modern Python web framework
- **React** — UI component library
- **PostgreSQL** — Reliable open-source database

---

<div align="center">

**Last Updated:** March 2026 · **Version:** 5.0.0

</div>
