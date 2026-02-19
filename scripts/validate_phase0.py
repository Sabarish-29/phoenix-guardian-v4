#!/usr/bin/env python3
"""
Phoenix Guardian V5 — Phase 0 Validation Script

Validates that all Phase 0 infrastructure is correctly set up:
  1. Python packages (aiofiles, httpx, numpy, scipy, redis, scikit-learn)
  2. Environment variables (.env V5 block)
  3. V5 config module loads without error
  4. Database tables (6 new V5 tables)
  5. Redis connectivity (warns if unavailable)
  6. External API reachability (OpenFDA, Orphadata)
  7. Existing tests still pass (non-blocking)

Usage:
    python scripts/validate_phase0.py
"""

import os
import sys
import importlib
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

errors: list[str] = []
warnings: list[str] = []

print("━" * 72)
print("Phoenix Guardian V5 — Phase 0 Validation")
print("━" * 72)


# ── 1. Python packages ────────────────────────────────────────────────────
print("\n1️⃣  Checking required Python packages …")

REQUIRED_PACKAGES = {
    "aiofiles":      "aiofiles",
    "httpx":         "httpx",
    "numpy":         "numpy",
    "scipy":         "scipy",
    "redis":         "redis",
    "scikit-learn":  "sklearn",
}

for display_name, import_name in REQUIRED_PACKAGES.items():
    try:
        mod = importlib.import_module(import_name)
        version = getattr(mod, "__version__", "?")
        print(f"   {PASS} {display_name} ({version})")
    except ImportError:
        errors.append(f"Missing package: {display_name}")
        print(f"   {FAIL} {display_name} — NOT INSTALLED")


# ── 2. Environment variables ──────────────────────────────────────────────
print("\n2️⃣  Checking V5 environment variables …")

V5_REQUIRED_VARS = [
    "ORPHADATA_BASE_URL",
    "OPENFDA_BASE_URL",
    "SHADOW_TREND_THRESHOLD_PCT",
    "SHADOW_MIN_LAB_RESULTS",
    "SILENT_VOICE_ZSCORE_THRESHOLD",
    "SILENT_VOICE_BASELINE_WINDOW_MINUTES",
    "GHOST_PROTOCOL_MIN_CLUSTER",
    "GHOST_PROTOCOL_TTL_DAYS",
]

V5_OPTIONAL_VARS = [
    "ORPHADATA_API_KEY",
    "OPENFDA_API_KEY",
    "SILENT_VOICE_MONITOR_INTERVAL_SECONDS",
    "DEMO_MODE",
    "DEMO_CACHE_TTL_SECONDS",
]

for var in V5_REQUIRED_VARS:
    val = os.getenv(var)
    if val:
        # Truncate long values for display
        display = val if len(val) <= 40 else val[:37] + "…"
        print(f"   {PASS} {var} = {display}")
    else:
        errors.append(f"Missing env var: {var}")
        print(f"   {FAIL} {var} — NOT SET")

for var in V5_OPTIONAL_VARS:
    val = os.getenv(var)
    if val:
        display = val if len(val) <= 40 else val[:37] + "…"
        print(f"   {PASS} {var} = {display}")
    else:
        warnings.append(f"Optional env var not set: {var}")
        print(f"   {WARN} {var} — not set (optional)")


# ── 3. V5 Config module ──────────────────────────────────────────────────
print("\n3️⃣  Loading V5 agent config module …")

try:
    from phoenix_guardian.config.v5_agent_config import v5_settings  # noqa: E402
    print(f"   {PASS} v5_agent_config loaded successfully")
    print(f"       orphadata url  = {v5_settings.orphadata.base_url}")
    print(f"       openfda url    = {v5_settings.openfda.base_url}")
    print(f"       zscore thresh  = {v5_settings.silent_voice.zscore_threshold}")
    print(f"       ghost min_clust= {v5_settings.ghost_protocol.min_cluster}")
except Exception as exc:
    errors.append(f"V5 config import failed: {exc}")
    print(f"   {FAIL} Could not import v5_agent_config: {exc}")


# ── 4. Database tables ───────────────────────────────────────────────────
print("\n4️⃣  Checking V5 database tables …")

V5_TABLES = [
    "zebra_analyses",
    "zebra_missed_clues",
    "ghost_cases",
    "patient_baselines",
    "silent_voice_alerts",
    "treatment_shadows",
]

try:
    from sqlalchemy import create_engine, text

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "phoenix_guardian")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    DATABASE_URL = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        )
        existing = {row[0] for row in result}

    for tbl in V5_TABLES:
        if tbl in existing:
            print(f"   {PASS} {tbl}")
        else:
            errors.append(f"Missing table: {tbl}")
            print(f"   {FAIL} {tbl} — NOT FOUND")

except Exception as exc:
    errors.append(f"Database check failed: {exc}")
    print(f"   {FAIL} Could not connect to database: {exc}")


# ── 5. Redis connectivity ────────────────────────────────────────────────
print("\n5️⃣  Checking Redis connectivity …")

try:
    import redis as _redis

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    r = _redis.from_url(REDIS_URL, socket_connect_timeout=3)
    pong = r.ping()
    if pong:
        r.set("v5_phase0_test", "ok", ex=60)
        print(f"   {PASS} Redis reachable at {REDIS_URL}")
    else:
        warnings.append("Redis ping returned False")
        print(f"   {WARN} Redis ping returned False")
except _redis.ConnectionError:
    warnings.append("Redis not running (non-blocking for dev)")
    print(f"   {WARN} Redis not running at {REDIS_URL} — OK for local dev")
except Exception as exc:
    warnings.append(f"Redis error: {exc}")
    print(f"   {WARN} Redis error: {exc}")


# ── 6. External API reachability ──────────────────────────────────────────
print("\n6️⃣  Checking external API reachability …")

try:
    import httpx

    # OpenFDA — base URL alone returns 404; test the drug label endpoint
    openfda_base = os.getenv(
        "OPENFDA_BASE_URL", "https://api.fda.gov"
    )
    openfda_test_url = f"{openfda_base}/drug/label.json"
    try:
        resp = httpx.get(openfda_test_url, params={"limit": 1}, timeout=10)
        if resp.status_code == 200:
            print(f"   {PASS} OpenFDA API — reachable (HTTP {resp.status_code})")
        else:
            warnings.append(f"OpenFDA returned HTTP {resp.status_code}")
            print(f"   {WARN} OpenFDA API — HTTP {resp.status_code}")
    except httpx.RequestError as exc:
        warnings.append(f"OpenFDA unreachable: {exc}")
        print(f"   {WARN} OpenFDA API — unreachable: {exc}")

    # Orphadata
    orphadata_url = os.getenv(
        "ORPHADATA_BASE_URL", "https://api.orphadata.com/rd-cross-referencing"
    )
    try:
        resp = httpx.get(orphadata_url, timeout=10)
        # 200 or 401 (needs API key) both prove the host is up
        if resp.status_code in (200, 401, 403):
            print(
                f"   {PASS} Orphadata API — reachable (HTTP {resp.status_code})"
            )
        else:
            warnings.append(f"Orphadata returned HTTP {resp.status_code}")
            print(f"   {WARN} Orphadata API — HTTP {resp.status_code}")
    except httpx.RequestError as exc:
        warnings.append(f"Orphadata unreachable: {exc}")
        print(f"   {WARN} Orphadata API — unreachable: {exc}")

except ImportError:
    errors.append("httpx not installed — cannot check APIs")
    print(f"   {FAIL} httpx not installed")


# ── 7. Existing tests (quick smoke) ──────────────────────────────────────
print("\n7️⃣  Running existing test smoke check …")

import subprocess

test_result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-x", "-q", "--tb=line", "--timeout=30"],
    capture_output=True,
    text=True,
    cwd=str(project_root),
    timeout=120,
)

if test_result.returncode == 0:
    # Count passed tests from output
    lines = test_result.stdout.strip().split("\n")
    summary = lines[-1] if lines else "done"
    print(f"   {PASS} Tests passed — {summary}")
elif test_result.returncode == 5:
    # pytest exit code 5 = no tests collected
    print(f"   {WARN} No tests collected (exit code 5)")
    warnings.append("No tests collected by pytest")
else:
    last_lines = test_result.stdout.strip().split("\n")[-3:]
    summary = " | ".join(last_lines)
    warnings.append(f"Some tests failed (exit {test_result.returncode}): {summary}")
    print(f"   {WARN} Tests exited with code {test_result.returncode}")
    for line in last_lines:
        print(f"       {line}")


# ── Summary ──────────────────────────────────────────────────────────────
print("\n" + "━" * 72)
print("SUMMARY")
print("━" * 72)

if errors:
    print(f"\n{FAIL} {len(errors)} ERROR(S):")
    for e in errors:
        print(f"   • {e}")

if warnings:
    print(f"\n{WARN} {len(warnings)} WARNING(S):")
    for w in warnings:
        print(f"   • {w}")

if not errors and not warnings:
    print(f"\n{PASS} All Phase 0 checks passed with zero issues!")
elif not errors:
    print(f"\n{PASS} Phase 0 PASSED (with {len(warnings)} non-blocking warnings)")
else:
    print(f"\n{FAIL} Phase 0 has {len(errors)} blocking issue(s). Fix before proceeding.")

print()
sys.exit(1 if errors else 0)
