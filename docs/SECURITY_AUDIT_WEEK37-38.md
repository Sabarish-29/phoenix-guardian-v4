# Phoenix Guardian Security Audit Report
## Phase 4 Week 37-38: Foundation Hardening

**Generated:** 2026-02-01
**Scanner Tools:** pip-audit 2.7.3, bandit 1.7.9
**Python Version:** 3.11.9
**Codebase Size:** 63,187 lines of code

---

## Executive Summary

| Category | Count | Severity |
|----------|-------|----------|
| **Dependency Vulnerabilities** | 29 | Mixed |
| **Code Security Issues** | 108 | 9 High, 21 Medium, 78 Low |
| **Critical Fixes Required** | 12 | Immediate |

---

## 1. Dependency Vulnerabilities (pip-audit)

### Critical/High Severity (Immediate Fix Required)

| Package | Version | CVE | Fix Version | Priority |
|---------|---------|-----|-------------|----------|
| aiohttp | 3.12.15 | CVE-2025-69223-69230 | 3.13.3 | HIGH |
| langchain | 0.1.20 | PYSEC-2024-115, CVE-2024-7774 | 0.2.0+ | CRITICAL |
| urllib3 | 2.5.0 | CVE-2025-66418, CVE-2026-21441 | 2.6.3 | HIGH |
| setuptools | 65.5.0 | CVE-2024-6345, PYSEC-2025-49 | 78.1.1 | HIGH |
| pip | 24.0 | CVE-2025-8869 | 25.3 | MEDIUM |
| python-multipart | 0.0.21 | CVE-2026-24486 | 0.0.22 | MEDIUM |

### Medium Severity

| Package | Version | CVE | Fix Version |
|---------|---------|-----|-------------|
| azure-core | 1.37.0 | CVE-2026-21226 | 1.38.0 |
| fonttools | 4.60.1 | CVE-2025-66034 | 4.60.2 |
| marshmallow | 3.26.1 | CVE-2025-68480 | 3.26.2 |
| mcp | 1.16.0 | CVE-2025-66416 | 1.23.0 |
| pymongo | 4.5.0 | CVE-2024-5629 | 4.6.3 |
| unstructured | 0.9.2 | CVE-2024-46455 | 0.14.3 |

### Low/Unfixable

| Package | Issue |
|---------|-------|
| ecdsa | CVE-2024-23342 - No fix available |
| orjson | CVE-2025-67221 - No fix available |
| protobuf | CVE-2026-0994 - No fix available |
| pyasn1 | CVE-2026-23490 - Fix: 0.6.2 |

---

## 2. Code Security Issues (bandit)

### HIGH Severity (9 issues)

All HIGH severity issues are **MD5 hash usage** (CWE-327):

| File | Line | Issue | Remediation |
|------|------|-------|-------------|
| `config/ehr_connectors.py` | 496 | MD5 for doc_id | Use secrets.token_hex(8) |
| `config/ehr_connectors.py` | 566 | MD5 for token | Use secrets.token_urlsafe(16) |
| `config/ehr_connectors.py` | 584 | MD5 for jti | Use uuid.uuid4() |
| `config/ehr_connectors.py` | 763 | MD5 for token | Use secrets.token_urlsafe(16) |
| `config/ehr_connectors.py` | 943 | MD5 for token | Use secrets.token_urlsafe(16) |
| `federated/privacy_validator.py` | 615 | MD5 for hash | Use hashlib.sha256() |
| `learning/ab_tester.py` | 527 | MD5 for hashing | Use hashlib.sha256() |
| `security/forensics.py` | Multiple | MD5 usage | Use SHA-256 |
| `security/ml_detector.py` | Multiple | MD5 usage | Use SHA-256 |

### MEDIUM Severity (21 issues)

| Category | Count | Files | Remediation |
|----------|-------|-------|-------------|
| pickle.loads (B301) | 8 | cache/tenant_redis.py, security/ml_detector.py | Use JSON or msgpack |
| Binding 0.0.0.0 (B104) | 1 | api/main.py | Use 127.0.0.1 in dev |
| HuggingFace unsafe download (B615) | 5 | learning/active_learner.py | Pin model revision |
| subprocess with shell=True (B602) | 4 | Various | Avoid shell=True |
| Hardcoded temp directory (B108) | 3 | Various | Use tempfile module |

### LOW Severity (78 issues)

Mostly B101 (assert usage) - acceptable in test context but should use proper exceptions in production.

---

## 3. Policy Violations

### ⚠️ CRITICAL: OpenAI Dependency Found

The environment has **crewai 1.8.0** installed which requires **openai~=1.83.0**.

**This violates the Anthropic-only policy.**

**Action Required:**
```bash
pip uninstall crewai openai
```

Phoenix Guardian must use **anthropic>=0.34.0** exclusively.

---

## 4. Immediate Remediation Actions

### Priority 1 (Security-Critical)

1. **Upgrade langchain to 0.2.5+**
   ```bash
   pip install langchain>=0.2.5
   ```

2. **Replace MD5 with SHA-256**
   ```python
   # Before (INSECURE)
   hashlib.md5(data.encode()).hexdigest()
   
   # After (SECURE)
   hashlib.sha256(data.encode()).hexdigest()
   ```

3. **Remove pickle usage for untrusted data**
   ```python
   # Before (INSECURE)
   data = pickle.loads(bytes.fromhex(stored))
   
   # After (SECURE)
   import json
   data = json.loads(stored)
   ```

### Priority 2 (Security-Important)

4. **Upgrade urllib3 to 2.6.3+**
5. **Upgrade aiohttp to 3.13.3+**
6. **Upgrade setuptools to 78.1.1+**
7. **Upgrade pip to 25.3**

### Priority 3 (Best Practice)

8. **Pin HuggingFace model revisions**
   ```python
   AutoTokenizer.from_pretrained(model_path, revision="v1.0.0")
   ```

9. **Add subprocess hardening**
   ```python
   subprocess.run(["cmd", "arg"], shell=False, check=True)
   ```

10. **Remove 0.0.0.0 binding in development**
    ```python
    uvicorn.run(app, host="127.0.0.1", port=8000)
    ```

---

## 5. Recommended requirements.txt Updates

```txt
# Update these packages in requirements.txt:
langchain==0.3.0
urllib3==2.6.3
aiohttp==3.13.3
setuptools==78.1.1
python-multipart==0.0.22
marshmallow==3.26.2
fonttools==4.60.2
pymongo==4.6.3
mcp==1.23.0
pyasn1==0.6.2
```

---

## 6. Security Baseline Metrics

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| High Severity Issues | 9 | 0 | ❌ |
| Medium Severity Issues | 21 | <5 | ❌ |
| Dependency CVEs | 29 | 0 | ❌ |
| OpenAI Dependencies | 1 | 0 | ❌ |
| Code Coverage | ~75% | 85% | 🟡 |
| Pre-commit Hooks | ✅ | ✅ | ✅ |
| Type Coverage | ~60% | 90% | 🟡 |

---

## 7. Next Steps for Week 39-40

1. Apply all Priority 1 fixes
2. Upgrade vulnerable dependencies
3. Remove crewai/openai from environment
4. Run full regression test suite
5. Achieve 0 HIGH severity issues
6. Begin FDA CDS Classification work

---

**Report Generated By:** Phoenix Guardian Hardening Agent
**Compliance Standards:** HIPAA, SOC 2, FDA 21 CFR Part 11
