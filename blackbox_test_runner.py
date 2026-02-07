"""Blackbox Test Runner for Phoenix Guardian v4 — All Sprints + Groq/Ollama AI Agents
Updated: Feb 7, 2026
AI Backend: Groq Cloud API (primary) + Ollama llama3.2:1b (fallback)
"""
import requests
import json
import sys
import time
from datetime import datetime

BASE = "http://localhost:8000/api/v1"
PASS_COUNT = 0
FAIL_COUNT = 0
ERROR_COUNT = 0
RESULTS = []


def login():
    r = requests.post(f"{BASE}/auth/login", json={
        "email": "dr.smith@phoenixguardian.health",
        "password": "Doctor123!"
    })
    return r.json()["access_token"]


def test(name, method, path, token, json_body=None, expected_status=200, timeout=30):
    global PASS_COUNT, FAIL_COUNT, ERROR_COUNT
    headers = {"Authorization": f"Bearer {token}"}
    start = time.time()
    try:
        if method == "GET":
            r = requests.get(f"{BASE}{path}", headers=headers, timeout=timeout)
        else:
            r = requests.post(f"{BASE}{path}", headers=headers, json=json_body, timeout=timeout)

        elapsed = int((time.time() - start) * 1000)
        passed = r.status_code == expected_status
        status = "PASS" if passed else "FAIL"
        if passed:
            PASS_COUNT += 1
        else:
            FAIL_COUNT += 1
        RESULTS.append({"name": name, "status": status, "code": r.status_code, "ms": elapsed})
        print(f"  [{status}] {name} -> {r.status_code} ({elapsed}ms)")
        if passed:
            try:
                data = r.json()
                if isinstance(data, dict):
                    keys = list(data.keys())[:6]
                    print(f"         Keys: {keys}")
                elif isinstance(data, list):
                    print(f"         Items: {len(data)}")
                return data
            except Exception:
                print(f"         Body: {r.text[:100]}")
                return r.text
        else:
            print(f"         Error: {r.text[:250]}")
            return None
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        ERROR_COUNT += 1
        RESULTS.append({"name": name, "status": "ERROR", "code": 0, "ms": elapsed})
        print(f"  [ERROR] {name} -> {e}")
        return None


if __name__ == "__main__":
    run_start = time.time()
    print("=" * 70)
    print("PHOENIX GUARDIAN v4 — BLACKBOX TEST SUITE v3")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("AI Backend: Groq Cloud API + Ollama llama3.2:1b")
    print("=" * 70)

    # ═══════════════════════════════════════════════════════════════════════
    # 1. AUTH
    # ═══════════════════════════════════════════════════════════════════════
    print("\n--- 1. AUTH ---")
    token = login()
    print(f"  [PASS] Login -> Token: {token[:20]}...")
    PASS_COUNT += 1
    RESULTS.append({"name": "Login", "status": "PASS", "code": 200, "ms": 0})

    # ═══════════════════════════════════════════════════════════════════════
    # 2. PQC ENDPOINTS (Sprint 4)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n--- 2. PQC ENDPOINTS (Sprint 4: Post-Quantum Cryptography) ---")

    test("PQC Health", "GET", "/pqc/health", token)
    test("PQC Algorithms", "GET", "/pqc/algorithms", token)
    test("PQC Encrypt", "POST", "/pqc/encrypt", token, {"plaintext": "Hello HIPAA"})
    test("PQC Encrypt PHI", "POST", "/pqc/encrypt-phi", token, {
        "data": {"patient_name": "John Doe", "ssn": "123-45-6789"},
        "context": "test"
    })
    test("PQC Key Rotation", "POST", "/pqc/rotate-keys", token)
    test("PQC Benchmark", "GET", "/pqc/benchmark", token)

    # ═══════════════════════════════════════════════════════════════════════
    # 3. LEARNING PIPELINE (Sprint 6)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n--- 3. LEARNING PIPELINE (Sprint 6: Bidirectional Learning) ---")

    test("Submit Feedback", "POST", "/learning/feedback", token, {
        "agent": "fraud",
        "action": "modify",
        "original_output": "flagged as fraud",
        "corrected_output": "legitimate claim",
        "encounter_id": "ENC-001",
        "metadata": {}
    }, timeout=60)

    test("Pipeline Status (fraud)", "GET", "/learning/status/fraud_detection", token, timeout=60)
    test("Feedback Stats (fraud)", "GET", "/learning/feedback-stats/fraud_detection", token, timeout=60)

    test("Batch Feedback", "POST", "/learning/feedback/batch", token, {
        "feedback": [
            {"agent": "scribe", "action": "accept", "original_output": "SOAP note generated"},
            {"agent": "fraud", "action": "reject", "original_output": "false positive"},
            {"agent": "fraud", "action": "modify", "original_output": "flagged", "corrected_output": "ok"},
        ]
    })

    test("Run Learning Cycle (insufficient data)", "POST", "/learning/run-cycle", token, {
        "domain": "fraud_detection",
        "force": True
    }, expected_status=500)

    # ═══════════════════════════════════════════════════════════════════════
    # 4. ORCHESTRATION (Sprint 7)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n--- 4. ORCHESTRATION (Sprint 7: Agent Orchestration) ---")

    test("Orchestration Health", "GET", "/orchestration/health", token)
    test("List Agents", "GET", "/orchestration/agents", token)

    test("Process Encounter", "POST", "/orchestration/process", token, {
        "patient_mrn": "MRN-001",
        "transcript": "Patient presents with headache and fever for 3 days. Blood pressure 140/90.",
        "chief_complaint": "headache and fever",
        "symptoms": ["headache", "fever"],
        "vitals": {"bp": "140/90", "temp": "101.2F"},
        "patient_age": 45,
        "duration": 15
    }, timeout=60)

    # ═══════════════════════════════════════════════════════════════════════
    # 5. TRANSCRIPTION (Sprint 5)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n--- 5. TRANSCRIPTION (Sprint 5: Voice Transcription) ---")

    test("List Providers", "GET", "/transcription/providers", token)
    test("Supported Languages", "GET", "/transcription/supported-languages", token)
    test("List Transcriptions", "GET", "/transcription/list", token)

    test("Process Transcription", "POST", "/transcription/process", token, {
        "transcript": "Patient reports chest pain radiating to left arm for 2 hours",
        "segments": [],
        "metadata": {"provider": "phoenix"}
    })

    test("Detect Medical Terms", "POST", "/transcription/detect-terms", token, {
        "text": "Patient has hypertension and type 2 diabetes mellitus"
    })

    test("Get Suggestions", "POST", "/transcription/suggestions", token, {
        "partial": "hypert",
        "limit": 5
    })

    # ═══════════════════════════════════════════════════════════════════════
    # 6. CORE ENDPOINTS (Sanity Check)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n--- 6. CORE ENDPOINTS (Sanity Check) ---")

    test("Health Check", "GET", "/health", token)
    test("Encounters List", "GET", "/encounters", token)

    # ═══════════════════════════════════════════════════════════════════════
    # 7. AI AGENT ENDPOINTS (Groq Cloud API — All 10 Agents)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n--- 7. AI AGENT ENDPOINTS (via Groq Cloud API) ---")

    # TC-AGT-001: ScribeAgent
    test("ScribeAgent — SOAP Note", "POST", "/agents/scribe/generate-soap", token, {
        "chief_complaint": "headache and fever for 3 days",
        "vitals": {"bp": "140/90", "temp": "101.2F"},
        "symptoms": ["headache", "fever", "fatigue"]
    }, timeout=60)

    # TC-AGT-002: SafetyAgent
    test("SafetyAgent — Drug Interactions", "POST", "/agents/safety/check-interactions", token, {
        "medications": ["aspirin", "warfarin", "ibuprofen"]
    }, timeout=60)

    # TC-AGT-003: NavigatorAgent
    test("NavigatorAgent — Workflow", "POST", "/agents/navigator/suggest-workflow", token, {
        "current_status": "patient checked in",
        "encounter_type": "Office Visit",
        "pending_items": ["vitals", "labs"]
    }, timeout=60)

    # TC-AGT-004: CodingAgent
    test("CodingAgent — ICD/CPT Codes", "POST", "/agents/coding/suggest-codes", token, {
        "clinical_note": "Patient presents with acute upper respiratory infection with productive cough",
        "procedures": ["chest x-ray"]
    }, timeout=60)

    # TC-AGT-005: SentinelAgent
    test("SentinelAgent — Threat Detection", "POST", "/agents/sentinel/analyze-input", token, {
        "user_input": "SELECT * FROM patients WHERE 1=1; DROP TABLE users;",
        "context": "search field"
    }, timeout=60)

    # TC-AGT-006: FraudAgent — detect
    test("FraudAgent — Detect Fraud", "POST", "/agents/fraud/detect", token, {
        "procedure_codes": ["99213"],
        "billed_cpt_code": "99215",
        "encounter_complexity": "low",
        "encounter_duration": 15,
        "documented_elements": 6
    }, timeout=60)

    # TC-AGT-014: FraudAgent — unbundling (expects raw list, not object)
    test("FraudAgent — Unbundling", "POST", "/agents/fraud/detect-unbundling", token,
        ["99213", "99214", "36415", "85025"]
    , timeout=60)

    # TC-AGT-007: ClinicalDecisionAgent — treatment
    test("ClinicalDecision — Treatment", "POST", "/agents/clinical-decision/recommend-treatment", token, {
        "diagnosis": "Type 2 Diabetes",
        "patient_factors": {"age": 55, "sex": "M"},
        "current_medications": ["metformin"]
    }, timeout=60)

    # TC-AGT-008: ClinicalDecisionAgent — risk
    test("ClinicalDecision — Risk Score", "POST", "/agents/clinical-decision/calculate-risk", token, {
        "condition": "chest pain",
        "clinical_data": {"age": 65, "sex": "M", "troponin": 0.04}
    }, timeout=60)

    # TC-AGT-013: ClinicalDecisionAgent — differential
    test("ClinicalDecision — Differential Dx", "POST", "/agents/clinical-decision/differential", token, {
        "symptoms": ["chest pain", "shortness of breath", "diaphoresis"],
        "patient_factors": {"age": 60, "sex": "M"}
    }, timeout=60)

    # TC-AGT-009: PharmacyAgent — formulary
    test("PharmacyAgent — Formulary", "POST", "/agents/pharmacy/check-formulary", token, {
        "medication": "lisinopril 10mg",
        "insurance_plan": "Blue Cross PPO"
    }, timeout=60)

    # TC-AGT-010: DeceptionDetectionAgent — consistency
    test("DeceptionAgent — Consistency", "POST", "/agents/deception/analyze-consistency", token, {
        "patient_history": ["I never smoke", "I quit smoking 5 years ago"],
        "current_statement": "I have been smoking a pack a day for 20 years"
    }, timeout=60)

    # TC-AGT-015: DeceptionDetectionAgent — drug-seeking
    test("DeceptionAgent — Drug Seeking", "POST", "/agents/deception/detect-drug-seeking", token, {
        "patient_request": "I need oxycodone 80mg, nothing else works",
        "medical_history": "No documented chronic pain condition",
        "current_medications": []
    }, timeout=60)

    # TC-AGT-011: OrderManagementAgent — labs
    test("OrderAgent — Suggest Labs", "POST", "/agents/orders/suggest-labs", token, {
        "clinical_note": "Patient presents with fatigue, weight gain, and cold intolerance",
        "diagnosis": "Suspected thyroid disorder",
        "patient_age": 45
    }, timeout=60)

    # TC-AGT-012: ReadmissionAgent
    test("ReadmissionAgent — Predict Risk", "POST", "/agents/readmission/predict-risk", token, {
        "age": 72,
        "has_heart_failure": True,
        "has_diabetes": True,
        "has_copd": False,
        "comorbidity_count": 3,
        "length_of_stay": 7,
        "visits_30d": 2,
        "visits_90d": 4,
        "discharge_disposition": "home"
    }, timeout=60)

    # ═══════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════════════
    total_time = int((time.time() - run_start) * 1000)
    print("\n" + "=" * 70)
    total = PASS_COUNT + FAIL_COUNT + ERROR_COUNT
    print(f"RESULTS: {PASS_COUNT} PASS / {FAIL_COUNT} FAIL / {ERROR_COUNT} ERROR  (Total: {total})")
    print(f"Total Time: {total_time}ms ({total_time / 1000:.1f}s)")
    print("=" * 70)

    print("\nAI Backend: Groq Cloud API (llama-3.3-70b-versatile) + Ollama (llama3.2:1b fallback)")
    print("All agent endpoints now use Groq — no Anthropic/Claude dependency.")

    if FAIL_COUNT > 0 or ERROR_COUNT > 0:
        print("\n--- FAILURES / ERRORS ---")
        for r in RESULTS:
            if r["status"] != "PASS":
                print(f"  [{r['status']}] {r['name']} -> HTTP {r['code']} ({r['ms']}ms)")

    sys.exit(0 if FAIL_COUNT == 0 and ERROR_COUNT == 0 else 1)
