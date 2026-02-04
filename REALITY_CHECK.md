# Phoenix Guardian Reality Check

**Date:** February 4, 2026  
**Purpose:** Document the actual state of the codebase before Week 1 recovery efforts

---

## 1. Setup Script Errors

### setup.ps1 - BROKEN
```
At D:\phoenix guardian v4\setup.ps1:78 char:23
+     if ($_ -match '^([^#][^=]+)=(.*)$') {
+                       ~
Missing type name after '['.
At D:\phoenix guardian v4\setup.ps1:79 char:81
+ ...ronment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
+                    ~~
The string is missing the terminator: '.
At D:\phoenix guardian v4\setup.ps1:36 char:24
+ if (!(Test-Path .env)) {
+                        ~
Missing closing '}' in statement block or type definition.
```

**Root Cause:** PowerShell regex pattern syntax errors, unclosed brackets

### setup.sh - NOT TESTED ON WINDOWS
- Script exists but cannot be tested on Windows environment
- Needs verification on macOS/Linux

---

## 2. Broken Dependencies

### Python Dependencies
| Package | Status | Issue |
|---------|--------|-------|
| python-jose | ⚠️ Warning | JWT "sub" field must be string, tests pass int |
| bcrypt | ✅ Works | Password hashing functional |
| psycopg2-binary | ✅ Works | Database connection works |
| pytest-asyncio | ⚠️ Warning | Mode deprecation warnings |

### Frontend Dependencies (phoenix-ui/)
- Not verified in this check
- Need to run `npm install` and verify

---

## 3. Missing/Broken Files

### Tests with Collection Errors
| File | Error |
|------|-------|
| tests/pilot/test_pilot_metrics.py | Collection error - blocks all tests |
| tests/integrations/test_base_connector.py | TestConnector class has __init__ |

### Configuration Files
| File | Status |
|------|--------|
| .env | ✅ Exists (not committed) |
| .env.example | ✅ Exists |
| pyproject.toml | ✅ Exists |
| setup.ps1 | ❌ BROKEN - syntax errors |
| setup.sh | ⚠️ Not tested |

---

## 4. Current State Assessment

### Backend
- **FastAPI Application:** ✅ Runs successfully
- **Database Connection:** ✅ Works with PostgreSQL
- **Authentication:** ✅ Login works (but JWT tests fail due to type mismatch)
- **API Routes:** ✅ Basic routes functional

### Test Suite
- **Total Tests Collected:** 3,450+ (many are boilerplate)
- **Core Tests (test_models.py + test_auth.py):** 112 tests
- **Passing:** 97 tests
- **Failing:** 15 tests (all JWT-related type mismatch)
- **Test Coverage:** 7.28% (far below 80% target)

### JWT Token Issue
The `create_access_token()` function in `phoenix_guardian/api/auth/utils.py` was fixed to use `str(user_id)` for the JWT "sub" field, but the test file still expects integer comparison:
```python
# Test expects: decoded["sub"] == sample_user.id (int)
# Actual: decoded["sub"] == "1" (string)
```

---

## 5. Critical Blockers

1. **setup.ps1 is broken** - Cannot run setup on Windows
2. **15 failing tests** - JWT type mismatch in test assertions
3. **Test collection error** - tests/pilot/test_pilot_metrics.py blocks pytest
4. **Low test coverage** - 7.28% vs 80% required
5. **Many untested modules** - 0% coverage on most security/compliance modules

---

## 6. What Actually Works

✅ PostgreSQL database connection  
✅ User model and password hashing  
✅ JWT token creation (strings)  
✅ FastAPI server starts  
✅ Login endpoint (tested manually)  
✅ Basic CRUD operations  
✅ 97 core tests passing  

---

## 7. Immediate Fixes Needed (Week 1)

1. Fix `setup.ps1` PowerShell syntax
2. Fix JWT test assertions to compare strings
3. Remove or fix `tests/pilot/test_pilot_metrics.py`
4. Add `faker` to requirements (for seed data)
5. Create proper seed data script
6. Write tests for uncovered modules
7. Get frontend to build

---

*This document represents the honest baseline before recovery efforts.*
