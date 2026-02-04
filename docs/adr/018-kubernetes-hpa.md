# ADR-018: Kubernetes HPA Configuration

## Status
Accepted

## Date
Day 142 (Phase 3)

## Context

Phoenix Guardian services experience variable load:
1. Peak hours: 8 AM - 6 PM with 3x baseline traffic
2. Transcription jobs can spike unpredictably
3. Different services have different scaling characteristics
4. Cost optimization requires scaling down during off-hours

## Decision

We will use Kubernetes Horizontal Pod Autoscaler (HPA) with custom metrics from Prometheus.

### Scaling Configuration

```yaml
# API Gateway - scale on requests per second
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: phoenix-guardian
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 3
  maxReplicas: 20
  metrics:
    # Primary: Request rate
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "100"
    # Secondary: CPU
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 4
          periodSeconds: 60
        - type: Percent
          value: 100
          periodSeconds: 60
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
      selectPolicy: Min

---
# Transcription Service - scale on queue depth
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: transcription-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: transcription-service
  minReplicas: 2
  maxReplicas: 15
  metrics:
    # Queue depth from Redis
    - type: External
      external:
        metric:
          name: transcription_queue_depth
        target:
          type: AverageValue
          averageValue: "5"
    # GPU utilization
    - type: Pods
      pods:
        metric:
          name: gpu_utilization
        target:
          type: AverageValue
          averageValue: "70"

---
# WebSocket Gateway - scale on connection count
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: websocket-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: websocket-gateway
  minReplicas: 3
  maxReplicas: 15
  metrics:
    - type: Pods
      pods:
        metric:
          name: websocket_connections
        target:
          type: AverageValue
          averageValue: "500"
```

### Pod Disruption Budgets

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: api-gateway

---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: database-pdb
spec:
  maxUnavailable: 1
  selector:
    matchLabels:
      app: postgres
```

### Custom Metrics Adapter

```yaml
# Prometheus Adapter config
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-adapter-config
data:
  config.yaml: |
    rules:
      - seriesQuery: 'phoenix_guardian_requests_total{namespace="phoenix-guardian"}'
        resources:
          overrides:
            namespace: {resource: "namespace"}
            pod: {resource: "pod"}
        name:
          matches: "^(.*)_total$"
          as: "${1}_per_second"
        metricsQuery: 'sum(rate(<<.Series>>{<<.LabelMatchers>>}[2m])) by (<<.GroupBy>>)'
      
      - seriesQuery: 'transcription_queue_depth'
        resources:
          template: <<.Resource>>
        name:
          matches: "^(.*)$"
          as: "${1}"
        metricsQuery: '<<.Series>>{<<.LabelMatchers>>}'
```

## Consequences

### Positive
- Automatic response to traffic changes
- Cost savings during low traffic
- Prevents overload during peaks
- Custom metrics enable precise scaling

### Negative
- Cold start latency during scale-up
- Complexity in tuning thresholds
- Resource overhead for metrics collection

## References
- Kubernetes HPA: https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- Prometheus Adapter: https://github.com/kubernetes-sigs/prometheus-adapter
