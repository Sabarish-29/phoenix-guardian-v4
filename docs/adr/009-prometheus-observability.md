# ADR-009: Prometheus Stack for Observability

## Status
Accepted

## Date
Day 150 (Phase 3)

## Context

Phoenix Guardian requires comprehensive observability for:
1. Real-time system health monitoring
2. SLA compliance tracking (latency, availability)
3. Security anomaly detection
4. Capacity planning
5. Incident response and debugging

We need metrics collection, visualization, and alerting that integrates with our Kubernetes infrastructure.

## Decision

We will deploy the Prometheus stack (Prometheus, Alertmanager, Grafana) using the kube-prometheus-stack Helm chart.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Prometheus Stack                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      Grafana                                 │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │ │
│  │  │ Dashboards  │  │   Alerts    │  │  Explore    │          │ │
│  │  │  (custom)   │  │   (visual)  │  │   (debug)   │          │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Prometheus                                │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │ │
│  │  │   Scraper    │  │     TSDB     │  │  Recording   │       │ │
│  │  │   (pull)     │  │   (storage)  │  │    Rules     │       │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │ │
│  │                           │                                   │ │
│  │         ┌─────────────────┼─────────────────┐                │ │
│  │         ▼                 ▼                 ▼                │ │
│  │  ┌────────────┐   ┌────────────┐   ┌────────────┐           │ │
│  │  │   Thanos   │   │   Thanos   │   │   Thanos   │           │ │
│  │  │  Sidecar   │   │   Query    │   │   Store    │           │ │
│  │  └────────────┘   └────────────┘   └────────────┘           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   Alertmanager                               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │ │
│  │  │   Routing    │  │  Inhibition  │  │  Silencing   │       │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │ │
│  │         │                                                     │ │
│  │         └──────────────────────────────────────────────────┐ │ │
│  │                                                            │ │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │ │ │
│  │  │   Slack      │  │  PagerDuty   │  │    Email     │◄────┘ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Prometheus Configuration

```yaml
# prometheus-values.yaml (kube-prometheus-stack)
prometheus:
  prometheusSpec:
    retention: 15d
    retentionSize: 50GB
    
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: gp3-encrypted
          resources:
            requests:
              storage: 100Gi
              
    resources:
      requests:
        memory: 4Gi
        cpu: 2
      limits:
        memory: 8Gi
        cpu: 4
        
    # Service discovery
    serviceMonitorSelector:
      matchLabels:
        release: prometheus
        
    # Additional scrape configs
    additionalScrapeConfigs:
      - job_name: 'phoenix-guardian-services'
        kubernetes_sd_configs:
          - role: pod
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
            action: replace
            target_label: __metrics_path__
            regex: (.+)
          - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
            action: replace
            target_label: __address__
            regex: ([^:]+)(?::\d+)?;(\d+)
            replacement: $1:$2

# Thanos sidecar for long-term storage
thanos:
  enabled: true
  objectStorageConfig:
    secretName: thanos-objstore-config
    secretKey: objstore.yml
```

### Custom Metrics

```python
from prometheus_client import Counter, Histogram, Gauge, Info
import time

# Request metrics
REQUEST_COUNT = Counter(
    'phoenix_guardian_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status', 'tenant_id']
)

REQUEST_LATENCY = Histogram(
    'phoenix_guardian_request_latency_seconds',
    'Request latency in seconds',
    ['method', 'endpoint', 'tenant_id'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Threat detection metrics
THREATS_DETECTED = Counter(
    'phoenix_guardian_threats_detected_total',
    'Total threats detected',
    ['threat_type', 'severity', 'tenant_id']
)

THREAT_DETECTION_LATENCY = Histogram(
    'phoenix_guardian_threat_detection_seconds',
    'Threat detection latency',
    ['threat_type'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

# Encounter metrics
ACTIVE_ENCOUNTERS = Gauge(
    'phoenix_guardian_active_encounters',
    'Currently active encounters',
    ['tenant_id']
)

TRANSCRIPTION_DURATION = Histogram(
    'phoenix_guardian_transcription_duration_seconds',
    'Transcription processing duration',
    ['language'],
    buckets=[1, 2, 5, 10, 30, 60, 120, 300]
)

SOAP_GENERATION_DURATION = Histogram(
    'phoenix_guardian_soap_generation_seconds',
    'SOAP note generation duration',
    ['language'],
    buckets=[0.5, 1, 2, 5, 10, 20, 30]
)

# System metrics
WEBSOCKET_CONNECTIONS = Gauge(
    'phoenix_guardian_websocket_connections',
    'Active WebSocket connections',
    ['tenant_id']
)

DATABASE_CONNECTIONS = Gauge(
    'phoenix_guardian_db_connections',
    'Database connection pool status',
    ['pool', 'state']
)

# Build info
BUILD_INFO = Info(
    'phoenix_guardian_build',
    'Build information'
)


def record_request(method: str, endpoint: str, status: int, 
                   tenant_id: str, duration: float):
    """Record HTTP request metrics."""
    REQUEST_COUNT.labels(
        method=method,
        endpoint=endpoint,
        status=status,
        tenant_id=tenant_id
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=method,
        endpoint=endpoint,
        tenant_id=tenant_id
    ).observe(duration)


def record_threat(threat_type: str, severity: str, tenant_id: str,
                  detection_time: float):
    """Record threat detection metrics."""
    THREATS_DETECTED.labels(
        threat_type=threat_type,
        severity=severity,
        tenant_id=tenant_id
    ).inc()
    
    THREAT_DETECTION_LATENCY.labels(
        threat_type=threat_type
    ).observe(detection_time)
```

### Alert Rules

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: phoenix-guardian-alerts
spec:
  groups:
    - name: phoenix-guardian.sla
      interval: 30s
      rules:
        # API latency SLA
        - alert: HighAPILatency
          expr: |
            histogram_quantile(0.95, 
              sum(rate(phoenix_guardian_request_latency_seconds_bucket[5m])) 
              by (le, endpoint)
            ) > 0.1
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "API latency P95 above 100ms"
            description: "Endpoint {{ $labels.endpoint }} has P95 latency of {{ $value | humanizeDuration }}"
            
        # Error rate
        - alert: HighErrorRate
          expr: |
            sum(rate(phoenix_guardian_requests_total{status=~"5.."}[5m])) 
            / sum(rate(phoenix_guardian_requests_total[5m])) > 0.01
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Error rate above 1%"
            description: "Error rate is {{ $value | humanizePercentage }}"
            
    - name: phoenix-guardian.threats
      rules:
        # High threat volume
        - alert: ThreatDetectionHigh
          expr: |
            sum(rate(phoenix_guardian_threats_detected_total{severity="critical"}[5m])) > 0.1
          for: 2m
          labels:
            severity: critical
          annotations:
            summary: "High rate of critical threats"
            description: "{{ $value | humanize }} critical threats/sec detected"
            
        # Threat detection slow
        - alert: ThreatDetectionSlow
          expr: |
            histogram_quantile(0.95, 
              sum(rate(phoenix_guardian_threat_detection_seconds_bucket[5m])) 
              by (le)
            ) > 0.5
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Threat detection latency high"
            
    - name: phoenix-guardian.infrastructure
      rules:
        # Database connections
        - alert: DatabaseConnectionPoolExhausted
          expr: |
            phoenix_guardian_db_connections{state="available"} 
            / phoenix_guardian_db_connections{state="total"} < 0.1
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Database connection pool nearly exhausted"
            
        # WebSocket connections
        - alert: WebSocketConnectionsHigh
          expr: |
            sum(phoenix_guardian_websocket_connections) > 10000
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High WebSocket connection count"
```

### Grafana Dashboards

```json
{
  "dashboard": {
    "title": "Phoenix Guardian Overview",
    "panels": [
      {
        "title": "Request Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(rate(phoenix_guardian_requests_total[5m]))",
            "legendFormat": "requests/sec"
          }
        ]
      },
      {
        "title": "API Latency P95",
        "type": "gauge",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate(phoenix_guardian_request_latency_seconds_bucket[5m])) by (le))",
            "legendFormat": "P95"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 0.05, "color": "yellow"},
                {"value": 0.1, "color": "red"}
              ]
            },
            "unit": "s"
          }
        }
      },
      {
        "title": "Active Encounters",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(phoenix_guardian_active_encounters)",
            "legendFormat": "encounters"
          }
        ]
      },
      {
        "title": "Threats by Severity",
        "type": "piechart",
        "targets": [
          {
            "expr": "sum(increase(phoenix_guardian_threats_detected_total[24h])) by (severity)",
            "legendFormat": "{{ severity }}"
          }
        ]
      }
    ]
  }
}
```

## Consequences

### Positive

1. **Pull-based model** - Reliable metrics collection
2. **PromQL** - Powerful query language
3. **Kubernetes-native** - ServiceMonitor/PodMonitor CRDs
4. **Ecosystem** - Huge library of exporters and integrations
5. **Grafana integration** - Rich visualization
6. **Long-term storage** - Thanos for unlimited retention
7. **Open source** - No vendor lock-in

### Negative

1. **Resource intensive** - Prometheus can consume significant memory
2. **Cardinality issues** - High cardinality labels cause problems
3. **Pull limitations** - Short-lived jobs need pushgateway
4. **Alert complexity** - PromQL learning curve
5. **Storage management** - Need to manage retention carefully

### Risks

1. **Prometheus OOM** - Mitigated by resource limits and cardinality monitoring
2. **Alert fatigue** - Mitigated by careful threshold tuning
3. **Data loss** - Mitigated by Thanos for long-term storage

## Alternatives Considered

### Datadog

**Pros:**
- Managed service
- All-in-one solution
- APM included

**Cons:**
- Per-host pricing
- Vendor lock-in
- Data residency concerns

**Rejected because:** Cost at scale and preference for open-source.

### New Relic

**Pros:**
- Strong APM
- Good UI
- ML-based anomaly detection

**Cons:**
- Expensive
- Complex pricing
- Vendor lock-in

**Rejected because:** Cost and vendor lock-in concerns.

### Elastic Observability

**Pros:**
- Unified logs and metrics
- Strong search
- Elastic ecosystem

**Cons:**
- Resource heavy
- Complex setup
- Licensing changes

**Rejected because:** Prometheus better suited for Kubernetes metrics.

### Victoria Metrics

**Pros:**
- PromQL compatible
- Better performance
- Lower resource usage

**Cons:**
- Smaller community
- Less mature
- Fewer integrations

**Rejected because:** Prometheus ecosystem is more mature and widely supported.

## Validation

1. **SLA monitoring** - All SLA metrics accurately tracked
2. **Alert testing** - Alerts fire correctly for all scenarios
3. **Dashboard usability** - Teams can self-serve troubleshooting
4. **Long-term storage** - Thanos queries work for 90+ days

## References

- Prometheus Documentation: https://prometheus.io/docs/
- kube-prometheus-stack: https://github.com/prometheus-community/helm-charts
- Thanos Documentation: https://thanos.io/tip/thanos/quick-tutorial.md/
- Grafana Dashboards: https://grafana.com/grafana/dashboards/
