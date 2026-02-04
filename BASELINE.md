# Phoenix Guardian Baseline Metrics

**Date:** February 4, 2026  
**Purpose:** Honest starting metrics before Week 1 recovery

---

## Test Results

### Actual Test Execution
```
pytest tests/test_models.py tests/test_auth.py -v
```

| Metric | Value |
|--------|-------|
| Total Tests Run | 112 |
| Passed | 97 |
| Failed | 15 |
| Pass Rate | 86.6% |
| Test Coverage | 7.28% |

### Test Breakdown by Module
| Module | Tests | Pass | Fail |
|--------|-------|------|------|
| test_models.py | 27 | 27 | 0 |
| test_auth.py | 85 | 70 | 15 |

### Failing Tests (All JWT-Related)
1. `test_create_access_token_contains_required_fields` - Subject must be string
2. `test_create_access_token_default_expiry` - Subject must be string
3. `test_create_access_token_custom_expiry` - Subject must be string
4. `test_create_refresh_token_type` - Subject must be string
5. `test_create_refresh_token_longer_expiry` - Subject must be string
6. `test_decode_token_success` - Subject must be string
7. `test_token_jti_unique` - Subject must be string
8. `test_create_tokens_for_user` - assert '1' == 1
9. `test_refresh_access_token_success` - Subject must be string
10. `test_refresh_for_inactive_user_fails` - Wrong error message
11. `test_refresh_for_deleted_user_fails` - Wrong error message
12. `test_unicode_in_token_data` - Subject must be string
13. `test_very_long_token_data` - Subject must be string
14. `test_full_auth_flow` - assert '1' == 1
15. `test_token_decode_performance` - Subject must be string

---

## Code Coverage

### Overall Coverage: 7.28%
```
TOTAL: 26,948 statements, 24,985 missed
```

### Coverage by Module Type
| Category | Coverage |
|----------|----------|
| Models | ~95% |
| API Auth | ~72% |
| API Main | ~72% |
| Agents | 0-30% |
| Security | 14-39% |
| Integrations | 0% |
| Federated | 0% |
| Compliance | 0% |

### Well-Covered Files (>90%)
- `phoenix_guardian/models/audit_log.py` - 100%
- `phoenix_guardian/models/encounter.py` - 100%
- `phoenix_guardian/models/security_event.py` - 100%
- `phoenix_guardian/models/soap_note.py` - 100%
- `phoenix_guardian/models/user.py` - 100%
- `phoenix_guardian/api/models.py` - 98%

### Zero Coverage Files (0%)
- All compliance modules
- All federated learning modules
- All integration connectors
- All language/localization modules
- Most security modules
- All telemetry modules
- All tenant management modules

---

## What Actually Exists vs. Documentation

### Documented Features
| Feature | Code Exists | Tests Exist | Works |
|---------|-------------|-------------|-------|
| User Authentication | ✅ | ✅ | ✅ |
| JWT Tokens | ✅ | ✅ | ⚠️ Test mismatch |
| Database Models | ✅ | ✅ | ✅ |
| SOAP Notes | ✅ | ✅ | ✅ |
| Encounters | ✅ | ✅ | ✅ |
| EHR Integrations | ✅ | ⚠️ | ❓ |
| Federated Learning | ✅ | ⚠️ | ❓ |
| Security Scanning | ✅ | ⚠️ | ❓ |
| Multi-tenancy | ✅ | ⚠️ | ❓ |

### Files Count
| Category | Count |
|----------|-------|
| Total Python files | 200+ |
| Total test files | 100+ |
| Tests that actually run | ~112 |
| Modules with 0% coverage | 60+ |

---

## Setup Script Status

| Script | Status | Details |
|--------|--------|---------|
| setup.ps1 | ❌ BROKEN | PowerShell syntax errors |
| setup.sh | ⚠️ UNKNOWN | Not tested on Windows |
| scripts/migrate.py | ✅ Works | Creates tables |
| scripts/seed_data.py | ❌ Missing | Needs to be created |

---

## Frontend Status

| Check | Status |
|-------|--------|
| package.json exists | ✅ |
| node_modules installed | ⚠️ Outdated |
| npm install succeeds | ⚠️ Needs --legacy-peer-deps |
| npm build succeeds | ⚠️ Not verified |
| npm start works | ⚠️ Not verified |

---

## Week 1 Targets

| Metric | Current | Target |
|--------|---------|--------|
| Passing Tests | 97 | 100+ |
| Test Coverage | 7.28% | 30%+ |
| Setup Script Works | ❌ | ✅ |
| Frontend Builds | ❓ | ✅ |
| Seed Data Script | ❌ | ✅ |

---

## GitHub CI Status

| Workflow | Status |
|----------|--------|
| test.yml | ⚠️ Simplified |
| deploy.yml | ❌ Removed |
| e2e-tests.yml | ❌ Removed |
| deploy-production.yml | ❌ Removed |

---

*This baseline will be updated at end of Week 1 to show progress.*
