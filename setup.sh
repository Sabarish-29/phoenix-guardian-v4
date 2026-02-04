#!/bin/bash
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phoenix Guardian — One-Command Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── Check Prerequisites ────────────────────────────────────────────────────
echo ""
echo "1️⃣  Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3.11+ required. Install from python.org"; exit 1; }

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo "❌ Python 3.11+ required. Found: $PYTHON_VERSION"
    exit 1
fi

echo "   ✓ Python $(python3 --version | cut -d' ' -f2)"

# Check for PostgreSQL
if command -v psql >/dev/null 2>&1; then
    echo "   ✓ PostgreSQL client found"
else
    echo "   ⚠️  PostgreSQL client not found (optional if using Docker)"
fi

# ─── Create .env from template ──────────────────────────────────────────────
echo ""
echo "2️⃣  Setting up environment..."

if [ ! -f .env ]; then
    cp .env.example .env
    echo "   ✓ Created .env from template"
    echo ""
    echo "   ⚠️  IMPORTANT: Edit .env and configure your settings:"
    echo "      - Set DB_PASSWORD to your PostgreSQL password"
    echo "      - Set JWT_SECRET_KEY (generate with: python3 -c 'import secrets; print(secrets.token_hex(32))')"
    echo "      - Optionally set ANTHROPIC_API_KEY for AI features"
    echo ""
    read -p "   Press Enter after you've configured .env..."
else
    echo "   ✓ .env already exists"
fi

# ─── Create Python Virtual Environment ─────────────────────────────────────
echo ""
echo "3️⃣  Creating Python virtual environment..."

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "   ✓ Virtual environment created"
else
    echo "   ✓ Virtual environment already exists"
fi

source .venv/bin/activate
echo "   ✓ Virtual environment activated"

# ─── Install Python Dependencies ────────────────────────────────────────────
echo ""
echo "4️⃣  Installing Python dependencies..."

pip install --upgrade pip setuptools wheel --quiet
pip install -r requirements.txt --quiet
echo "   ✓ All Python packages installed"

# ─── Setup Database ─────────────────────────────────────────────────────────
echo ""
echo "5️⃣  Setting up database..."

# Source .env to get DB settings
export $(grep -v '^#' .env | xargs)

# Check if PostgreSQL is running
if command -v pg_isready >/dev/null 2>&1; then
    if pg_isready -h ${DB_HOST:-localhost} -p ${DB_PORT:-5432} > /dev/null 2>&1; then
        echo "   ✓ PostgreSQL is running"
    else
        echo "   ⚠️  PostgreSQL is not running. Please start PostgreSQL first."
        echo "      On macOS: brew services start postgresql"
        echo "      On Ubuntu: sudo systemctl start postgresql"
        exit 1
    fi
fi

# Run migrations
python scripts/migrate.py
echo "   ✓ Database schema created"

# ─── Create Required Directories ────────────────────────────────────────────
echo ""
echo "6️⃣  Creating required directories..."

mkdir -p models logs reports benchmarks data/{uploads,outputs}
touch models/.gitkeep logs/.gitkeep reports/.gitkeep 2>/dev/null || true

echo "   ✓ Directory structure created"

# ─── Install Frontend Dependencies ──────────────────────────────────────────
echo ""
echo "7️⃣  Setting up frontend..."

if [ -d "phoenix-ui" ]; then
    cd phoenix-ui
    if [ ! -d "node_modules" ]; then
        npm install --legacy-peer-deps
        echo "   ✓ Frontend dependencies installed"
    else
        echo "   ✓ Frontend dependencies already installed"
    fi
    cd ..
fi

# ─── Run Validator ──────────────────────────────────────────────────────────
echo ""
echo "8️⃣  Running installation validator..."

python scripts/validate_installation.py

# ─── Success ────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Phoenix Guardian setup complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  1. Start the backend:    source .venv/bin/activate && python -m uvicorn phoenix_guardian.api.main:app --reload"
echo "  2. Start the frontend:   cd phoenix-ui && npm start"
echo "  3. View API docs:        http://localhost:8000/api/docs"
echo "  4. View frontend:        http://localhost:3000"
echo ""
echo "Demo credentials:"
echo "  Admin:     admin@phoenixguardian.health / Admin123!"
echo "  Physician: dr.smith@phoenixguardian.health / Doctor123!"
echo ""
echo "To deactivate virtual environment: deactivate"
echo ""
