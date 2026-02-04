#!/usr/bin/env python3
"""
Validates that Phoenix Guardian is correctly installed and configured.

Usage:
    python scripts/validate_installation.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("Phoenix Guardian — Installation Validator")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

errors = []
warnings = []

# Check 1: Python version
print("\n1️⃣  Checking Python version...")
version = sys.version_info
if version.major == 3 and version.minor >= 11:
    print(f"   ✓ Python {version.major}.{version.minor}.{version.micro}")
else:
    errors.append(f"Python 3.11+ required, found {version.major}.{version.minor}")
    print(f"   ❌ Python {version.major}.{version.minor} (3.11+ required)")

# Check 2: Environment variables
print("\n2️⃣  Checking environment variables...")
required_vars = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
optional_vars = ["JWT_SECRET_KEY", "ANTHROPIC_API_KEY", "REDIS_URL"]

for var in required_vars:
    if os.getenv(var):
        print(f"   ✓ {var} is set")
    else:
        errors.append(f"{var} not set in .env")
        print(f"   ❌ {var} is NOT set")

for var in optional_vars:
    if os.getenv(var):
        print(f"   ✓ {var} is set")
    else:
        warnings.append(f"{var} not set (optional)")
        print(f"   ⚠️  {var} not set (optional)")

# Check 3: Required directories
print("\n3️⃣  Checking directory structure...")
required_dirs = ["phoenix_guardian", "phoenix-ui", "scripts", "tests"]
for dir_name in required_dirs:
    dir_path = project_root / dir_name
    if dir_path.exists():
        print(f"   ✓ {dir_name}/")
    else:
        errors.append(f"Missing directory: {dir_name}")
        print(f"   ❌ {dir_name}/ NOT FOUND")

# Check 4: Database connection
print("\n4️⃣  Checking database connection...")
try:
    from sqlalchemy import create_engine, text
    
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "phoenix_guardian")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("   ✓ PostgreSQL connection successful")
        
        # Check if tables exist
        result = conn.execute(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """))
        tables = [row[0] for row in result]
        if tables:
            print(f"   ✓ Found {len(tables)} tables: {', '.join(tables[:5])}{'...' if len(tables) > 5 else ''}")
        else:
            warnings.append("No tables found - run migrations")
            print("   ⚠️  No tables found - run: python scripts/migrate.py")
    
    engine.dispose()
except Exception as e:
    errors.append(f"Database connection failed: {e}")
    print(f"   ❌ Database connection failed: {e}")

# Check 5: Core imports
print("\n5️⃣  Checking core module imports...")
critical_modules = [
    ("phoenix_guardian.models", "Models"),
    ("phoenix_guardian.api.main", "API"),
    ("phoenix_guardian.database.connection", "Database"),
    ("phoenix_guardian.api.auth.utils", "Authentication"),
]
for module_path, module_name in critical_modules:
    try:
        __import__(module_path)
        print(f"   ✓ {module_name}")
    except ImportError as e:
        errors.append(f"Failed to import {module_path}: {e}")
        print(f"   ❌ {module_name}: {e}")

# Check 6: Frontend
print("\n6️⃣  Checking frontend...")
frontend_path = project_root / "phoenix-ui"
if frontend_path.exists():
    package_json = frontend_path / "package.json"
    node_modules = frontend_path / "node_modules"
    
    if package_json.exists():
        print("   ✓ package.json exists")
    else:
        errors.append("phoenix-ui/package.json not found")
        print("   ❌ package.json NOT FOUND")
    
    if node_modules.exists():
        print("   ✓ node_modules installed")
    else:
        warnings.append("node_modules not installed - run: cd phoenix-ui && npm install")
        print("   ⚠️  node_modules not installed - run: cd phoenix-ui && npm install --legacy-peer-deps")
else:
    errors.append("phoenix-ui directory not found")
    print("   ❌ phoenix-ui/ NOT FOUND")

# Results
print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
if errors:
    print("❌ VALIDATION FAILED")
    print("\nErrors:")
    for err in errors:
        print(f"   • {err}")
    if warnings:
        print("\nWarnings:")
        for warn in warnings:
            print(f"   • {warn}")
    sys.exit(1)
elif warnings:
    print("⚠️  VALIDATION PASSED WITH WARNINGS")
    print("\nWarnings:")
    for warn in warnings:
        print(f"   • {warn}")
    print("\nPhoenix Guardian is installed but some optional features are missing.")
else:
    print("✅ VALIDATION PASSED")
    print("\nPhoenix Guardian is correctly installed and ready to use!")

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
