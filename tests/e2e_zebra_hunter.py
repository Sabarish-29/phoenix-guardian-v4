"""E2E test for Zebra Hunter — Patient A and Patient B."""
import requests, json, time

BASE = "http://localhost:8000/api/v1"

# Login
r = requests.post(f"{BASE}/auth/login", json={"email": "admin@phoenixguardian.health", "password": "Admin123!"})
tok = r.json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}
print("Login OK")

# Analyze Patient A
patient_a = "a1b2c3d4-0001-4000-8000-000000000001"
print("\n=== Analyzing Patient A (Priya Sharma) ===")
start = time.time()
r = requests.post(f"{BASE}/zebra-hunter/analyze/{patient_a}", headers=h, timeout=120)
elapsed = time.time() - start
print(f"Status: {r.status_code} ({elapsed:.1f}s)")
if r.status_code == 200:
    d = r.json()
    status = d["status"]
    print(f"  status: {status}")
    print(f"  patient_name: {d['patient_name']}")
    print(f"  total_visits: {d['total_visits']}")
    syms = d["symptoms_found"]
    print(f"  symptoms_found: {len(syms)} -> {syms[:5]}")
    if d.get("top_matches"):
        m = d["top_matches"][0]
        disease = m["disease"]
        conf = m["confidence"]
        print(f"  top_match: {disease} ({conf}%)")
    tl = d["missed_clue_timeline"]
    print(f"  timeline_entries: {len(tl)}")
    print(f"  years_lost: {d['years_lost']}")
    print(f"  analysis_time: {d['analysis_time_seconds']}s")
    gp = d.get("ghost_protocol")
    if gp:
        print(f"  ghost_protocol: activated={gp['activated']}")
    rec = d.get("recommendation", "")
    print(f"  recommendation: {rec[:120]}...")
    # Assertions
    assert status == "zebra_found", f"Expected zebra_found, got {status}"
    assert conf >= 70, f"Expected EDS confidence >= 70, got {conf}"
    assert len(tl) >= 5, f"Expected >= 5 timeline entries, got {len(tl)}"
    assert d["years_lost"] > 0, "Expected years_lost > 0"
    print("  ✅ Patient A PASSED")
else:
    print(f"ERROR: {r.text[:500]}")

# Analyze Patient B
patient_b = "a1b2c3d4-0002-4000-8000-000000000002"
print("\n=== Analyzing Patient B (Arjun Nair) — first call ===")
start = time.time()
r = requests.post(f"{BASE}/zebra-hunter/analyze/{patient_b}", headers=h, timeout=120)
elapsed = time.time() - start
print(f"Status: {r.status_code} ({elapsed:.1f}s)")
if r.status_code == 200:
    d = r.json()
    status = d["status"]
    print(f"  status: {status}")
    print(f"  patient_name: {d['patient_name']}")
    syms = d["symptoms_found"]
    print(f"  symptoms_found: {len(syms)} -> {syms[:5]}")
    gp = d.get("ghost_protocol")
    if gp:
        act = gp["activated"]
        gid = gp.get("ghost_id")
        cnt = gp.get("patient_count", 0)
        print(f"  ghost_protocol: activated={act}, ghost_id={gid}, count={cnt}")
    else:
        print("  ghost_protocol: None")
    print(f"  ✅ Patient B call 1 complete (status={status})")
else:
    print(f"ERROR: {r.text[:500]}")

# Second call for Patient B to trigger ghost cluster
print("\n=== Analyzing Patient B — second call (trigger cluster) ===")
start = time.time()
r = requests.post(f"{BASE}/zebra-hunter/analyze/{patient_b}", headers=h, timeout=120)
elapsed = time.time() - start
print(f"Status: {r.status_code} ({elapsed:.1f}s)")
if r.status_code == 200:
    d = r.json()
    status = d["status"]
    gp = d.get("ghost_protocol")
    if gp:
        act = gp["activated"]
        gid = gp.get("ghost_id")
        cnt = gp.get("patient_count", 0)
        print(f"  ghost_protocol: activated={act}, ghost_id={gid}, count={cnt}")
    print(f"  ✅ Patient B call 2 complete (status={status})")

# Ghost cases
print("\n=== Ghost Cases ===")
r = requests.get(f"{BASE}/zebra-hunter/ghost-cases", headers=h, timeout=10)
if r.status_code == 200:
    gc = r.json()
    total = gc["total_ghost_cases"]
    fired = gc["alert_fired_count"]
    print(f"  total_ghost_cases: {total}")
    print(f"  alert_fired_count: {fired}")
    for c in gc["cases"]:
        print(f"    {c['ghost_id']}: status={c['status']}, patients={c['patient_count']}")
else:
    print(f"  Error: {r.status_code}")

# Fetch stored result
print("\n=== Stored Result (Patient A) ===")
r = requests.get(f"{BASE}/zebra-hunter/result/{patient_a}", headers=h, timeout=10)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    print("  ✅ Stored result retrieved")

print("\n=== ALL E2E TESTS COMPLETE ===")
