# Phoenix Guardian — Windows Setup Script
# Run this with: .\setup.ps1

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "Phoenix Guardian — One-Command Setup (Windows)" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# ─── Check Prerequisites ────────────────────────────────────────────────────
Write-Host ""
Write-Host "1️⃣  Checking prerequisites..." -ForegroundColor Yellow

try {
    $pythonVersion = python --version 2>&1 | Select-String -Pattern "(\d+\.\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }
    if ([version]$pythonVersion -lt [version]"3.11") {
        Write-Host "❌ Python 3.11+ required. Found: $pythonVersion" -ForegroundColor Red
        exit 1
    }
    Write-Host "   ✓ Python $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found. Install from python.org" -ForegroundColor Red
    exit 1
}

# Check Node.js
try {
    $nodeVersion = node --version 2>&1
    Write-Host "   ✓ Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "   ⚠️  Node.js not found (optional, needed for frontend)" -ForegroundColor Yellow
}

# ─── Create .env from template ──────────────────────────────────────────────
Write-Host ""
Write-Host "2️⃣  Setting up environment..." -ForegroundColor Yellow

if (!(Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "   ✓ Created .env from template" -ForegroundColor Green
    Write-Host ""
    Write-Host "   ⚠️  IMPORTANT: Edit .env and configure your settings:" -ForegroundColor Red
    Write-Host "      - Set DB_PASSWORD to your PostgreSQL password" -ForegroundColor Yellow
    Write-Host "      - Set JWT_SECRET_KEY" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "   Press Enter after you've configured .env"
} else {
    Write-Host "   ✓ .env already exists" -ForegroundColor Green
}

# ─── Create Python Virtual Environment ─────────────────────────────────────
Write-Host ""
Write-Host "3️⃣  Creating Python virtual environment..." -ForegroundColor Yellow

if (!(Test-Path .venv)) {
    python -m venv .venv
    Write-Host "   ✓ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "   ✓ Virtual environment already exists" -ForegroundColor Green
}

# Activate virtual environment
.\.venv\Scripts\Activate.ps1
Write-Host "   ✓ Virtual environment activated" -ForegroundColor Green

# ─── Install Python Dependencies ────────────────────────────────────────────
Write-Host ""
Write-Host "4️⃣  Installing Python dependencies..." -ForegroundColor Yellow

pip install --upgrade pip setuptools wheel --quiet 2>$null
pip install -r requirements.txt --quiet 2>$null
Write-Host "   ✓ All Python packages installed" -ForegroundColor Green

# ─── Setup Database ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "5️⃣  Setting up database..." -ForegroundColor Yellow

# Load .env file
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#][^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}

# Run migrations
python scripts/migrate.py
Write-Host "   ✓ Database schema created" -ForegroundColor Green

# ─── Create Required Directories ────────────────────────────────────────────
Write-Host ""
Write-Host "6️⃣  Creating required directories..." -ForegroundColor Yellow

$dirs = @("models", "logs", "reports", "benchmarks", "data\uploads", "data\outputs")
foreach ($dir in $dirs) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "   ✓ Directory structure created" -ForegroundColor Green

# ─── Install Frontend Dependencies ──────────────────────────────────────────
Write-Host ""
Write-Host "7️⃣  Setting up frontend..." -ForegroundColor Yellow

if (Test-Path "phoenix-ui") {
    Push-Location phoenix-ui
    if (!(Test-Path "node_modules")) {
        npm install --legacy-peer-deps 2>$null
        Write-Host "   ✓ Frontend dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "   ✓ Frontend dependencies already installed" -ForegroundColor Green
    }
    Pop-Location
}

# ─── Run Validator ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "8️⃣  Running installation validator..." -ForegroundColor Yellow

python scripts/validate_installation.py

# ─── Success ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✅ Phoenix Guardian setup complete!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Start the backend:    .\.venv\Scripts\Activate.ps1; python -m uvicorn phoenix_guardian.api.main:app --reload --port 8000"
Write-Host "  2. Start the frontend:   cd phoenix-ui; npm start"
Write-Host "  3. View API docs:        http://localhost:8000/api/docs"
Write-Host "  4. View frontend:        http://localhost:3000"
Write-Host ""
Write-Host "Demo credentials:" -ForegroundColor Yellow
Write-Host "  Admin:     admin@phoenixguardian.health / Admin123!"
Write-Host "  Physician: dr.smith@phoenixguardian.health / Doctor123!"
Write-Host ""
Write-Host "To deactivate virtual environment: deactivate"
Write-Host ""
