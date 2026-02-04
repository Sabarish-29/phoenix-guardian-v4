# Phoenix Guardian - Windows Setup Script
# Run this with: .\setup.ps1

param(
    [switch]$SkipFrontend,
    [switch]$SkipPrompt
)

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "Phoenix Guardian - One-Command Setup (Windows)" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# --- Check Prerequisites ---
Write-Host ""
Write-Host "[1/8] Checking prerequisites..." -ForegroundColor Yellow

try {
    $pythonOutput = python --version 2>&1
    if ($pythonOutput -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
            Write-Host "ERROR: Python 3.11+ required. Found: $pythonOutput" -ForegroundColor Red
            exit 1
        }
        Write-Host "   [OK] $pythonOutput" -ForegroundColor Green
    }
} catch {
    Write-Host "ERROR: Python not found. Install from python.org" -ForegroundColor Red
    exit 1
}

# Check Node.js
try {
    $nodeVersion = node --version 2>&1
    Write-Host "   [OK] Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "   [WARN] Node.js not found (optional for frontend)" -ForegroundColor Yellow
}

# --- Create .env from template ---
Write-Host ""
Write-Host "[2/8] Setting up environment..." -ForegroundColor Yellow

if (!(Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "   [OK] Created .env from template" -ForegroundColor Green
    
    if (-not $SkipPrompt) {
        Write-Host ""
        Write-Host "   IMPORTANT: Edit .env and configure your settings:" -ForegroundColor Red
        Write-Host "      - Set DB_PASSWORD to your PostgreSQL password" -ForegroundColor Yellow
        Write-Host "      - Set JWT_SECRET_KEY (or leave default for dev)" -ForegroundColor Yellow
        Write-Host ""
        Read-Host "   Press Enter after you have configured .env"
    }
} else {
    Write-Host "   [OK] .env already exists" -ForegroundColor Green
}

# --- Create Python Virtual Environment ---
Write-Host ""
Write-Host "[3/8] Creating Python virtual environment..." -ForegroundColor Yellow

if (!(Test-Path ".venv")) {
    python -m venv .venv
    Write-Host "   [OK] Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "   [OK] Virtual environment already exists" -ForegroundColor Green
}

# Activate virtual environment
& ".\.venv\Scripts\Activate.ps1"
Write-Host "   [OK] Virtual environment activated" -ForegroundColor Green

# --- Install Python Dependencies ---
Write-Host ""
Write-Host "[4/8] Installing Python dependencies..." -ForegroundColor Yellow

pip install --upgrade pip setuptools wheel -q 2>$null
pip install -r requirements.txt -q 2>$null
pip install python-dotenv faker -q 2>$null
Write-Host "   [OK] All Python packages installed" -ForegroundColor Green

# --- Load Environment Variables ---
Write-Host ""
Write-Host "[5/8] Loading environment variables..." -ForegroundColor Yellow

$envContent = Get-Content ".env" -ErrorAction SilentlyContinue
if ($envContent) {
    foreach ($line in $envContent) {
        $line = $line.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $eqIndex = $line.IndexOf("=")
            $key = $line.Substring(0, $eqIndex).Trim()
            $value = $line.Substring($eqIndex + 1).Trim()
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
    Write-Host "   [OK] Environment variables loaded" -ForegroundColor Green
}

# --- Setup Database ---
Write-Host ""
Write-Host "[6/8] Setting up database..." -ForegroundColor Yellow

try {
    python scripts/migrate.py
    Write-Host "   [OK] Database schema created" -ForegroundColor Green
} catch {
    Write-Host "   [WARN] Database setup issue: $_" -ForegroundColor Yellow
}

# --- Create Required Directories ---
Write-Host ""
Write-Host "[7/8] Creating required directories..." -ForegroundColor Yellow

$dirs = @("models", "logs", "reports", "data/uploads", "data/outputs")
foreach ($dir in $dirs) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "   [OK] Directory structure created" -ForegroundColor Green

# --- Install Frontend Dependencies ---
Write-Host ""
Write-Host "[8/8] Setting up frontend..." -ForegroundColor Yellow

if (-not $SkipFrontend -and (Test-Path "phoenix-ui")) {
    Push-Location "phoenix-ui"
    if (!(Test-Path "node_modules")) {
        npm install --legacy-peer-deps 2>$null
        Write-Host "   [OK] Frontend dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "   [OK] Frontend dependencies already installed" -ForegroundColor Green
    }
    Pop-Location
} else {
    Write-Host "   [SKIP] Frontend setup skipped" -ForegroundColor Yellow
}

# --- Success ---
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "[SUCCESS] Phoenix Guardian setup complete!" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Start backend:  .\.venv\Scripts\Activate.ps1; python -m uvicorn phoenix_guardian.api.main:app --reload --port 8000"
Write-Host "  2. Start frontend: cd phoenix-ui; npm start"
Write-Host "  3. API docs:       http://localhost:8000/api/docs"
Write-Host "  4. Frontend:       http://localhost:3000"
Write-Host ""
Write-Host "Demo credentials:" -ForegroundColor Yellow
Write-Host "  Admin:     admin@phoenixguardian.health / Admin123!"
Write-Host "  Physician: dr.smith@phoenixguardian.health / Doctor123!"
Write-Host ""
