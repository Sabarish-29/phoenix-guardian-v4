# Phoenix Guardian 🛡️

Enterprise Healthcare AI Platform with Advanced Security & Clinical Decision Support

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://reactjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791.svg)](https://www.postgresql.org/)

---

## 🚀 Quick Start (One Command)

### Prerequisites

Before running setup, ensure you have:

1. **Python 3.11+** — [Download](https://www.python.org/downloads/)
2. **Node.js 18+** — [Download](https://nodejs.org/)
3. **PostgreSQL 15+** — [Download](https://www.postgresql.org/download/)
4. **Git** — [Download](https://git-scm.com/downloads)

### macOS / Linux

```bash
git clone https://github.com/Sabarish-29/phoenix-guardian-v4.git
cd phoenix-guardian-v4
chmod +x setup.sh
./setup.sh
```

### Windows (PowerShell as Administrator)

```powershell
git clone https://github.com/Sabarish-29/phoenix-guardian-v4.git
cd phoenix-guardian-v4
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```

**That's it!** The setup script will:
- ✅ Check prerequisites
- ✅ Create Python virtual environment
- ✅ Install all dependencies
- ✅ Setup database and run migrations
- ✅ Seed initial test data
- ✅ Setup frontend
- ✅ Validate installation

---

## 🔑 Configuration

After cloning, configure your environment:

1. The setup script creates `.env` from `.env.example`
2. Edit `.env` with your settings:
   - **Required:** `DB_PASSWORD` - Your PostgreSQL password
   - **Required:** `JWT_SECRET_KEY` - Generate with: `python -c "import secrets; print(secrets.token_hex(32))"`
   - **Optional:** `ANTHROPIC_API_KEY` - For AI-powered SOAP generation

**⚠️ Never commit your `.env` file to git!**

---

## 🖥️ Running the Application

### Start Backend API

```bash
# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# OR
.\.venv\Scripts\Activate.ps1  # Windows

# Start API server (auto-reload enabled)
python -m uvicorn phoenix_guardian.api.main:app --reload --port 8000
```

### Start Frontend

```bash
cd phoenix-ui
npm start
```

### Access Points

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API Docs | http://localhost:8000/api/docs |
| Health Check | http://localhost:8000/api/v1/health |

### Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@phoenixguardian.health | Admin123! |
| Physician | dr.smith@phoenixguardian.health | Doctor123! |
| Nurse | nurse.jones@phoenixguardian.health | Nurse123! |

---

## 🏗️ Project Structure

```
phoenix-guardian-v4/
├── phoenix_guardian/        # Backend Python package
│   ├── api/                 # FastAPI routes and middleware
│   │   ├── routes/          # API endpoints (auth, encounters, etc.)
│   │   └── auth/            # Authentication utilities
│   ├── models/              # SQLAlchemy ORM models
│   ├── database/            # Database connection management
│   ├── agents/              # AI agents (Scribe, Navigator, Safety)
│   ├── security/            # Security modules
│   └── integrations/        # EHR connectors (Epic, Cerner, etc.)
├── phoenix-ui/              # React frontend
│   ├── src/
│   │   ├── pages/           # Page components
│   │   ├── components/      # Reusable UI components
│   │   ├── api/             # API client and services
│   │   └── stores/          # Zustand state management
├── tests/                   # Test suite
├── scripts/                 # Setup and utility scripts
├── docker/                  # Docker configurations
└── docs/                    # Documentation
```

---

## 🧪 Running Tests

```bash
# Activate virtual environment first
source .venv/bin/activate  # macOS/Linux

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=phoenix_guardian --cov-report=html

# Run specific module
pytest tests/api/test_auth.py -v
```

---

## 🐳 Docker Development (Optional)

If you prefer Docker for PostgreSQL and Redis:

```bash
# Start databases
docker-compose up -d

# Stop databases
docker-compose down

# Stop and remove data
docker-compose down -v
```

---

## 📊 Key Features

### Clinical Documentation
- **AI-Powered SOAP Notes** — Generates structured clinical notes from encounter data
- **Real-time Transcription** — Voice-to-text for clinical encounters
- **Template Library** — Customizable note templates by specialty

### Security & Compliance
- **HIPAA Compliant** — Full audit logging, encryption at rest and in transit
- **Role-Based Access Control** — Physician, Nurse, Admin, Scribe roles
- **JWT Authentication** — Secure token-based auth with refresh tokens

### EHR Integration
- **Epic** — FHIR R4 integration
- **Cerner** — FHIR R4 integration
- **Allscripts** — HL7v2 and FHIR support
- **Meditech** — HL7v2 integration
- **athenahealth** — REST API integration

---

## 🛠️ Development

### Code Quality

```bash
# Format code
black phoenix_guardian/ tests/

# Type checking
mypy phoenix_guardian/ --ignore-missing-imports

# Linting
pylint phoenix_guardian/
```

### Database Migrations

```bash
# Run migrations
python scripts/migrate.py

# Validate installation
python scripts/validate_installation.py
```

---

## 📖 API Documentation

When the server is running, view the interactive API documentation at:
- **Swagger UI:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc

---

## 🤝 Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Run tests: `pytest tests/ -v`
4. Format code: `black phoenix_guardian/ tests/`
5. Commit: `git commit -m "Add your feature"`
6. Push: `git push origin feature/your-feature`
7. Create a Pull Request

---

## 🐛 Troubleshooting

### "PostgreSQL connection failed"

1. Ensure PostgreSQL is running:
   - macOS: `brew services start postgresql`
   - Windows: Check Services → PostgreSQL
   - Linux: `sudo systemctl start postgresql`

2. Verify credentials in `.env` file

3. Check database exists:
   ```bash
   psql -U postgres -c "SELECT datname FROM pg_database WHERE datname = 'phoenix_guardian';"
   ```

### "Module not found"

1. Ensure virtual environment is activated:
   ```bash
   source .venv/bin/activate  # macOS/Linux
   .\.venv\Scripts\Activate.ps1  # Windows
   ```

2. Reinstall dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### "Frontend build errors"

1. Clear node modules and reinstall:
   ```bash
   cd phoenix-ui
   rm -rf node_modules
   npm install --legacy-peer-deps
   ```

### "Port already in use"

```bash
# Find process using port
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows
```

---

## 📞 Support

For questions or issues:
- Create a GitHub Issue
- Email: team@phoenix-guardian.ai

---

## 📜 License

Proprietary. © 2026 Phoenix Guardian Team. All rights reserved.

---

**Built with ❤️ by the Phoenix Guardian Team**
