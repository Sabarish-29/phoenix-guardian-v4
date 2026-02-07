"""Environment Verification Script for Black Box Testing"""
import requests
import json
import sys

BASE = "http://localhost:8000"
FRONT = "http://localhost:3000"
FHIR = "http://localhost:8001"

results = {}

# 1. Backend Health
print("=" * 60)
print("  PHOENIX GUARDIAN v4 - ENVIRONMENT VERIFICATION")
print("=" * 60)

print("\n1. BACKEND SERVER (port 8000)")
print("-" * 40)
try:
    r = requests.get(f"{BASE}/api/v1/health", timeout=5)
    data = r.json()
    status = data.get("status", "unknown")
    version = data.get("version", "N/A")
    db = data.get("database_connected", "N/A")
    agents = data.get("agents", [])
    print(f"   Status Code: {r.status_code}")
    print(f"   Health: {status}")
    print(f"   Version: {version}")
    print(f"   Database Connected: {db}")
    if agents:
        print(f"   Agents: {len(agents)} loaded")
        for a in agents:
            name = a.get("name", "?")
            a_status = a.get("status", "?")
            print(f"     - {name}: {a_status}")
    results["backend"] = "PASS" if status == "healthy" else "WARN"
except Exception as e:
    print(f"   FAILED: {e}")
    results["backend"] = "FAIL"

# 2. Frontend
print("\n2. FRONTEND SERVER (port 3000)")
print("-" * 40)
try:
    r = requests.get(FRONT, timeout=5)
    ct = r.headers.get("content-type", "N/A")
    print(f"   Status Code: {r.status_code}")
    print(f"   Content-Type: {ct}")
    results["frontend"] = "PASS" if r.status_code == 200 else "FAIL"
except Exception as e:
    print(f"   FAILED: {e}")
    results["frontend"] = "FAIL"

# 3. Database (test via login)
print("\n3. DATABASE CONNECTION (via auth)")
print("-" * 40)
try:
    r = requests.post(f"{BASE}/api/v1/auth/login", json={
        "email": "dr.smith@phoenixguardian.health",
        "password": "Doctor123!"
    }, timeout=10)
    print(f"   Login Status: {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        user = d.get("user", {})
        print(f"   User: {user.get('first_name', '?')} {user.get('last_name', '?')}")
        print(f"   Role: {user.get('role', '?')}")
        print(f"   Token: {d.get('access_token', '')[:30]}...")
        results["database"] = "PASS"
        results["_token"] = d.get("access_token", "")
    else:
        print(f"   Response: {r.text[:200]}")
        results["database"] = "FAIL"
except Exception as e:
    print(f"   FAILED: {e}")
    results["database"] = "FAIL"

# 4. Test all 3 users
print("\n4. TEST USER VERIFICATION")
print("-" * 40)
users = [
    ("admin@phoenixguardian.health", "Admin123!", "admin"),
    ("dr.smith@phoenixguardian.health", "Doctor123!", "physician"),
    ("nurse.jones@phoenixguardian.health", "Nurse123!", "nurse"),
]
all_users_ok = True
for email, pwd, expected_role in users:
    try:
        r = requests.post(f"{BASE}/api/v1/auth/login", json={"email": email, "password": pwd}, timeout=10)
        if r.status_code == 200:
            role = r.json().get("user", {}).get("role", "?")
            match = "OK" if role == expected_role else f"MISMATCH (got {role})"
            print(f"   {expected_role:10s} ({email}): {r.status_code} - Role: {match}")
        else:
            print(f"   {expected_role:10s} ({email}): {r.status_code} FAILED")
            all_users_ok = False
    except Exception as e:
        print(f"   {expected_role:10s}: FAILED - {e}")
        all_users_ok = False
results["users"] = "PASS" if all_users_ok else "FAIL"

# 5. API Docs
print("\n5. API DOCUMENTATION")
print("-" * 40)
try:
    r = requests.get(f"{BASE}/api/docs", timeout=5)
    print(f"   Swagger UI: {r.status_code}")
    results["docs"] = "PASS" if r.status_code == 200 else "FAIL"
except Exception as e:
    print(f"   FAILED: {e}")
    results["docs"] = "FAIL"

# 6. ML Models (check via agent endpoints)
print("\n6. ML MODELS / AI AGENTS")
print("-" * 40)
token = results.get("_token", "")
headers = {"Authorization": f"Bearer {token}"} if token else {}

# Test readmission model
try:
    r = requests.post(f"{BASE}/api/v1/agents/readmission/predict-risk", headers=headers, json={
        "age": 65, "has_heart_failure": True, "has_diabetes": False, "has_copd": False,
        "comorbidity_count": 2, "length_of_stay": 3, "visits_30d": 1, "visits_90d": 2,
        "discharge_disposition": "home"
    }, timeout=10)
    print(f"   Readmission Model: {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        print(f"     Risk Level: {d.get('risk_level', '?')}")
        print(f"     Model AUC: {d.get('model_auc', '?')}")
        results["readmission_model"] = "PASS"
    else:
        print(f"     Response: {r.text[:150]}")
        results["readmission_model"] = "WARN"
except Exception as e:
    print(f"   Readmission Model FAILED: {e}")
    results["readmission_model"] = "FAIL"

# Test sentinel agent
try:
    r = requests.post(f"{BASE}/api/v1/agents/sentinel/analyze-input", headers=headers, json={
        "user_input": "Patient reports headache",
        "context": "transcript"
    }, timeout=10)
    print(f"   Sentinel Agent: {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        print(f"     Threat Detected: {d.get('threat_detected', '?')}")
        results["sentinel"] = "PASS"
    else:
        print(f"     Response: {r.text[:150]}")
        results["sentinel"] = "WARN"
except Exception as e:
    print(f"   Sentinel Agent FAILED: {e}")
    results["sentinel"] = "FAIL"

# 7. FHIR Server (optional)
print("\n7. MOCK FHIR SERVER (port 8001) - Optional")
print("-" * 40)
try:
    r = requests.get(f"{FHIR}/Patient/patient-001", timeout=3)
    print(f"   Status: {r.status_code}")
    results["fhir"] = "PASS"
except requests.exceptions.ConnectionError:
    print(f"   Not running (optional - EHR tests will be skipped)")
    results["fhir"] = "SKIP"
except Exception as e:
    print(f"   Error: {e}")
    results["fhir"] = "SKIP"

# 8. X-Process-Time header
print("\n8. RESPONSE HEADERS CHECK")
print("-" * 40)
try:
    r = requests.get(f"{BASE}/api/v1/health", timeout=5)
    xpt = r.headers.get("x-process-time", None)
    print(f"   X-Process-Time: {xpt}")
    results["headers"] = "PASS" if xpt else "WARN"
except:
    results["headers"] = "FAIL"

# Summary
print("\n" + "=" * 60)
print("  VERIFICATION SUMMARY")
print("=" * 60)
icons = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN", "SKIP": "SKIP"}
critical_pass = True
for key, val in results.items():
    if key.startswith("_"):
        continue
    icon = icons.get(val, "?")
    print(f"   [{icon}] {key}")
    if val == "FAIL" and key in ("backend", "frontend", "database"):
        critical_pass = False

print("\n" + "-" * 60)
if critical_pass:
    print("   ENVIRONMENT READY FOR BLACK BOX TESTING")
else:
    print("   ENVIRONMENT NOT READY - Fix FAIL items above")
print("=" * 60)
