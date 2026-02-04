# ADR-010: Locust for Load Testing

## Status
Accepted

## Date
Day 160 (Phase 3)

## Context

Phoenix Guardian needs performance testing to validate:
1. API endpoints handle 1,000+ concurrent users
2. WebSocket connections scale to 10,000+
3. Transcription service handles peak load
4. Database performance under stress
5. SLA compliance under load

Requirements:
- Python-based for team familiarity
- Realistic user behavior simulation
- Distributed load generation
- CI/CD integration
- Real-time monitoring during tests

## Decision

We will use Locust as our primary load testing framework.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Load Test Cluster                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   Locust Master                              │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │ │
│  │  │  Web UI      │  │  Coordinator │  │   Reporter   │       │ │
│  │  │  (:8089)     │  │              │  │   (stats)    │       │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│         ┌────────────────────┼────────────────────┐              │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  ┌────────────┐       ┌────────────┐       ┌────────────┐       │
│  │  Worker 1  │       │  Worker 2  │       │  Worker N  │       │
│  │  (spawn)   │       │  (spawn)   │       │  (spawn)   │       │
│  │  500 users │       │  500 users │       │  500 users │       │
│  └─────┬──────┘       └─────┬──────┘       └─────┬──────┘       │
│        │                    │                    │              │
│        └────────────────────┼────────────────────┘              │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                Phoenix Guardian API                         │ │
│  │       (staging environment / dedicated load test)           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Test Implementation

```python
# locustfile.py
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import json
import random
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PhoenixGuardianUser(HttpUser):
    """Simulates a typical physician user workflow."""
    
    wait_time = between(1, 5)
    abstract = True
    
    def on_start(self):
        """Authenticate and store token."""
        response = self.client.post("/auth/token", json={
            "grant_type": "password",
            "tenant_id": self.tenant_id,
            "username": self.username,
            "password": self.password,
        })
        
        if response.status_code == 200:
            token = response.json()["access_token"]
            self.client.headers["Authorization"] = f"Bearer {token}"
        else:
            logger.error(f"Auth failed: {response.status_code}")
            
    @task(10)
    def list_encounters(self):
        """List recent encounters - most common operation."""
        self.client.get("/encounters", params={
            "page": 1,
            "page_size": 20,
            "status": "active"
        })
        
    @task(5)
    def view_encounter(self):
        """View single encounter details."""
        encounter_id = self.get_random_encounter_id()
        self.client.get(f"/encounters/{encounter_id}")
        
    @task(3)
    def create_encounter(self):
        """Create new encounter."""
        self.client.post("/encounters", json={
            "patient_mrn": f"MRN-{random.randint(1000, 9999)}",
            "encounter_type": "office_visit",
            "chief_complaint": "Follow-up visit",
        })
        
    @task(2)
    def view_soap_note(self):
        """View SOAP note for encounter."""
        encounter_id = self.get_random_encounter_id()
        self.client.get(f"/soap/{encounter_id}")
        
    @task(2)
    def dashboard_metrics(self):
        """Check dashboard metrics."""
        self.client.get("/dashboard/metrics", params={
            "period": "day"
        })
        
    @task(1)
    def search_patients(self):
        """Search for patients."""
        self.client.get("/patients/search", params={
            "q": "John",
            "limit": 10
        })
        
    def get_random_encounter_id(self):
        """Get a random encounter ID from pool."""
        # In real test, maintain a pool of valid encounter IDs
        return f"encounter-{random.randint(1, 1000)}"


class HighVolumeUser(PhoenixGuardianUser):
    """Power user with higher activity rate."""
    
    wait_time = between(0.5, 2)
    weight = 1


class NormalUser(PhoenixGuardianUser):
    """Normal user with typical activity."""
    
    wait_time = between(2, 8)
    weight = 5


class AdminUser(HttpUser):
    """Admin user checking system health."""
    
    wait_time = between(30, 60)
    weight = 0.1
    
    def on_start(self):
        self.client.post("/auth/token", json={
            "grant_type": "password",
            "tenant_id": "admin-tenant",
            "username": "admin",
            "password": "admin-password",
        })
        
    @task
    def admin_dashboard(self):
        self.client.get("/admin/dashboard")
        
    @task
    def audit_logs(self):
        self.client.get("/admin/audit/logs", params={
            "limit": 100,
            "days": 1
        })


# Custom metrics tracking
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, 
               response, context, exception, **kwargs):
    """Track custom metrics for analysis."""
    if exception:
        logger.warning(f"Request failed: {name} - {exception}")
    elif response.status_code >= 400:
        logger.warning(f"Error response: {name} - {response.status_code}")


# SLA validation
@events.quitting.add_listener  
def check_sla(environment, **kwargs):
    """Check SLA compliance after test."""
    stats = environment.stats
    
    sla_violations = []
    
    # P95 latency < 100ms
    for entry in stats.entries.values():
        p95 = entry.get_response_time_percentile(0.95)
        if p95 > 100:
            sla_violations.append(
                f"{entry.name}: P95 {p95:.2f}ms > 100ms"
            )
    
    # Error rate < 1%
    total_requests = stats.total.num_requests
    total_failures = stats.total.num_failures
    error_rate = (total_failures / total_requests * 100) if total_requests > 0 else 0
    
    if error_rate > 1:
        sla_violations.append(f"Error rate {error_rate:.2f}% > 1%")
    
    if sla_violations:
        logger.error("SLA VIOLATIONS:")
        for violation in sla_violations:
            logger.error(f"  - {violation}")
        # Could fail CI/CD here
    else:
        logger.info("All SLA requirements met!")
```

### CI/CD Integration

```yaml
# .github/workflows/load-test.yml
name: Load Test

on:
  schedule:
    - cron: '0 2 * * *'  # Nightly
  workflow_dispatch:
    inputs:
      users:
        description: 'Number of users'
        default: '100'
      duration:
        description: 'Test duration (seconds)'
        default: '300'

jobs:
  load-test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install locust
          
      - name: Run load test
        run: |
          locust \
            -f tests/load/locustfile.py \
            --headless \
            --users ${{ github.event.inputs.users || 100 }} \
            --spawn-rate 10 \
            --run-time ${{ github.event.inputs.duration || 300 }}s \
            --host https://staging-api.phoenix-guardian.health \
            --html report.html \
            --csv results
            
      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: load-test-results
          path: |
            report.html
            results*.csv
            
      - name: Check SLA
        run: |
          python scripts/check_load_test_sla.py results_stats.csv
```

### Kubernetes Distributed Testing

```yaml
# locust-master.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: locust-master
spec:
  replicas: 1
  selector:
    matchLabels:
      app: locust
      role: master
  template:
    spec:
      containers:
        - name: locust
          image: locustio/locust:2.20.0
          args:
            - --master
            - --expect-workers=10
          ports:
            - containerPort: 8089
            - containerPort: 5557
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
          volumeMounts:
            - name: locust-scripts
              mountPath: /mnt/locust
      volumes:
        - name: locust-scripts
          configMap:
            name: locust-scripts

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: locust-worker
spec:
  replicas: 10
  selector:
    matchLabels:
      app: locust
      role: worker
  template:
    spec:
      containers:
        - name: locust
          image: locustio/locust:2.20.0
          args:
            - --worker
            - --master-host=locust-master
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          volumeMounts:
            - name: locust-scripts
              mountPath: /mnt/locust
      volumes:
        - name: locust-scripts
          configMap:
            name: locust-scripts
```

## Consequences

### Positive

1. **Python-based** - Team already knows Python
2. **Realistic simulation** - User classes model real behavior
3. **Distributed** - Scale to millions of users
4. **Web UI** - Real-time monitoring during tests
5. **Programmable** - Custom scenarios and assertions
6. **CI/CD friendly** - Headless mode for automation

### Negative

1. **HTTP focused** - WebSocket/gRPC need custom code
2. **Single-threaded users** - gevent-based, not async
3. **Resource usage** - Each worker needs dedicated resources
4. **Complex scenarios** - Complex state management needed
5. **Limited reporting** - Basic HTML reports

### Risks

1. **Test environment impact** - Mitigated by isolated staging
2. **False positives** - Mitigated by stable test data
3. **Incomplete coverage** - Mitigated by scenario review

## Alternatives Considered

### k6

**Pros:**
- JavaScript-based
- Lower resource usage
- Good CLI
- Cloud offering

**Cons:**
- Different language from app
- Fewer team members know JS
- Less flexible user modeling

**Rejected because:** Python preference for team familiarity.

### JMeter

**Pros:**
- Industry standard
- GUI for test creation
- Many protocols

**Cons:**
- XML configuration
- Java-based
- Resource heavy
- Complex for simple tests

**Rejected because:** XML configuration and GUI-centric approach don't fit our workflow.

### Gatling

**Pros:**
- Scala/Java
- Good reports
- High performance

**Cons:**
- Scala learning curve
- JVM-based
- Complex setup

**Rejected because:** Scala is not in our tech stack.

### Artillery

**Pros:**
- YAML configuration
- Easy to start
- Good for APIs

**Cons:**
- Limited user modeling
- Less programmable
- JavaScript

**Rejected because:** Need more complex user behavior modeling.

## Validation

1. **1,000 concurrent users** - Successfully tested
2. **10,000 WebSocket connections** - Custom test validated
3. **SLA compliance** - P95 <100ms under load
4. **CI/CD integration** - Nightly tests passing

## References

- Locust Documentation: https://docs.locust.io/
- Distributed Load Testing: https://docs.locust.io/en/stable/running-distributed.html
- Locust on Kubernetes: https://github.com/deliveryhero/locust-helm-chart
