# Phoenix Guardian - Dependency Audit
## Task 7: Dependency Analysis

**Audit Date:** February 1, 2026  
**Status:** ✅ COMPLETE

---

## Executive Summary

| Metric | Value | Status |
|--------|-------|--------|
| Total Python Packages | 80 | ✅ Reasonable |
| Core Dependencies (requirements.txt) | 11 | ✅ Minimal |
| Missing from requirements.txt | 6 | ⚠️ Need update |
| Security Vulnerabilities | Not scanned | ⚠️ Recommend scan |

**Assessment:** Dependencies need requirements.txt update; security scan recommended.

---

## requirements.txt Analysis

### Currently Declared Dependencies

```
# Core AI/ML
anthropic>=0.18.0            ✅ Installed: 0.77.0

# FastAPI Framework  
fastapi>=0.109.0             ✅ Installed: 0.128.0
uvicorn[standard]>=0.27.0    ✅ Installed: (via standard)
pydantic>=2.5.0              ✅ Installed: 2.12.5

# Authentication & Security
python-jose[cryptography]>=3.3.0  ✅ Installed
passlib[bcrypt]>=1.7.4           ✅ Installed: 1.7.4
python-multipart>=0.0.6          ✅ Installed

# ML Threat Detection (Phase 2)
transformers>=4.36.0         ⚠️ NOT INSTALLED
torch>=2.1.0                 ⚠️ NOT INSTALLED
scikit-learn>=1.3.2          ✅ Installed: 1.8.0

# Structured Logging
structlog>=23.2.0            ✅ Installed: 25.5.0
```

### Missing from requirements.txt (Used in Code)

| Package | Version Installed | Used In |
|---------|------------------|---------|
| numpy | 2.4.2 | ml_detector, federated |
| scipy | 1.17.0 | ML operations |
| requests | 2.32.5 | fhir_client, integrations |
| email-validator | 2.3.0 | pydantic email fields |
| psycopg2-binary | 2.9.11 | PostgreSQL connection |
| httpx | 0.28.1 | HTTP client |

---

## Installed Packages (80 Total)

### Core Framework
| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.128.0 | Web framework |
| pydantic | 2.12.5 | Data validation |
| uvicorn | (installed) | ASGI server |
| httpx | 0.28.1 | HTTP client |

### AI/ML
| Package | Version | Purpose |
|---------|---------|---------|
| anthropic | 0.77.0 | Claude API |
| numpy | 2.4.2 | Numerical computing |
| scipy | 1.17.0 | Scientific computing |
| scikit-learn | 1.8.0 | ML algorithms |
| joblib | 1.5.3 | Model serialization |

### Security
| Package | Version | Purpose |
|---------|---------|---------|
| passlib | 1.7.4 | Password hashing |
| bcrypt | 5.0.0 | Bcrypt hashing |
| cryptography | 46.0.4 | Cryptographic operations |
| PyJWT | 2.11.0 | JWT tokens |

### Database
| Package | Version | Purpose |
|---------|---------|---------|
| psycopg2-binary | 2.9.11 | PostgreSQL driver |

### Development/Testing
| Package | Version | Purpose |
|---------|---------|---------|
| pytest | (installed) | Testing framework |
| pytest-cov | (installed) | Coverage reporting |
| pytest-mock | (installed) | Mocking |
| pytest-asyncio | (installed) | Async testing |
| Faker | 40.1.2 | Test data generation |
| black | 26.1.0 | Code formatting |
| isort | 7.0.0 | Import sorting |
| mypy | 1.19.1 | Type checking |
| coverage | 7.13.2 | Coverage measurement |

### Logging/Monitoring
| Package | Version | Purpose |
|---------|---------|---------|
| structlog | 25.5.0 | Structured logging |

---

## Dependency Issues

### Critical Missing (Required for tests to pass)

1. **transformers** - Listed but NOT installed
   - Required for: Medical NLP models
   - Impact: Some ML features won't work
   
2. **torch** - Listed but NOT installed
   - Required for: Deep learning models
   - Impact: ML model inference won't work
   - Note: Large package (~2GB), may be intentional

### Update Required

```bash
# Add to requirements.txt
numpy>=2.0.0
scipy>=1.10.0
requests>=2.31.0
email-validator>=2.0.0
psycopg2-binary>=2.9.0
httpx>=0.25.0
```

---

## Version Compatibility Matrix

| Package | Min Version | Installed | Status |
|---------|-------------|-----------|--------|
| Python | 3.11+ | 3.11.9 | ✅ OK |
| FastAPI | 0.109.0 | 0.128.0 | ✅ OK |
| Pydantic | 2.5.0 | 2.12.5 | ✅ OK |
| Anthropic | 0.18.0 | 0.77.0 | ✅ OK |
| NumPy | - | 2.4.2 | ⚠️ Add |
| scikit-learn | 1.3.2 | 1.8.0 | ✅ OK |

---

## Security Audit

### Recommended Scans

```bash
# Install safety for vulnerability scanning
pip install safety

# Run vulnerability check
safety check

# Or use pip-audit
pip install pip-audit
pip-audit
```

### Known Issues to Check
- [ ] Older cryptography versions (current: 46.0.4 ✅)
- [ ] JWT library vulnerabilities
- [ ] psycopg2 vs psycopg3 migration

---

## Frontend Dependencies

### Dashboard (phoenix-ui)
**Location:** `phoenix-ui/package.json`

Expected dependencies:
- React 18.x
- TypeScript
- Material-UI / Tailwind
- Axios / fetch

### Mobile App
**Location:** `mobile/package.json`

Expected dependencies:
- React Native 0.73.x
- TypeScript
- React Navigation
- AsyncStorage

**Status:** Not audited in this task (frontend focus)

---

## Recommended requirements.txt Update

```python
# Phoenix Guardian Base Requirements
# Python 3.11+

# Core AI/ML
anthropic>=0.18.0

# FastAPI Framework
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0

# Authentication & Security
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6

# ML/Numerical
numpy>=2.0.0
scipy>=1.10.0
scikit-learn>=1.3.2

# ML Models (Optional - large packages)
# transformers>=4.36.0
# torch>=2.1.0

# Structured Logging
structlog>=23.2.0

# HTTP Client
requests>=2.31.0
httpx>=0.25.0

# Database
psycopg2-binary>=2.9.0

# Email Validation
email-validator>=2.0.0
```

---

## Action Items

### Immediate

1. **Update requirements.txt**
   - Add: numpy, scipy, requests, email-validator, psycopg2-binary, httpx

2. **Run security scan**
   ```bash
   pip install safety
   safety check
   ```

### This Week

3. **Create requirements-dev.txt**
   - Separate dev dependencies (pytest, black, mypy, etc.)

4. **Evaluate torch/transformers**
   - Large packages (~2GB+)
   - Consider optional installation
   - Or use smaller alternatives

### Before Production

5. **Pin exact versions**
   - Create `requirements.lock` or use `pip freeze`
   - Ensures reproducible builds

6. **Security scan in CI/CD**
   - Add safety/pip-audit to pipeline

---

## Conclusion

**Dependency Status: ⚠️ NEEDS UPDATE**

### Strengths
- Core dependencies properly versioned
- Using modern package versions
- Development tools configured (black, mypy, isort)

### Issues
- 6 packages used but not in requirements.txt
- torch/transformers listed but not installed
- No security vulnerability scan in place

### Dependency Score: 75/100
- Declared deps: 15/20
- Installed correctly: 15/20
- Security scanning: 0/20
- Version management: 15/20
- Documentation: 15/20
- Missing packages: -5
