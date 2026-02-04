#!/bin/bash
# =============================================================================
# PHOENIX GUARDIAN - HEALTH CHECK SCRIPT
# =============================================================================
# Comprehensive health verification for deployed services
# Usage: ./health_check.sh [staging|production]
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }

# Configuration
ENV=${1:-production}
TIMEOUT=${TIMEOUT:-30}
RETRY_COUNT=${RETRY_COUNT:-5}
RETRY_DELAY=${RETRY_DELAY:-5}

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║           PHOENIX GUARDIAN - HEALTH CHECK                         ║"
echo "║                                                                    ║"
echo "║  Environment: $ENV                                           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

HEALTH_CHECKS_PASSED=0
HEALTH_CHECKS_FAILED=0

check_pass() {
  log_success "$1"
  ((HEALTH_CHECKS_PASSED++))
}

check_fail() {
  log_error "$1"
  ((HEALTH_CHECKS_FAILED++))
}

# =============================================================================
# KUBERNETES CLUSTER HEALTH
# =============================================================================

log_info "Checking Kubernetes cluster health..."

# Check node status
NODES_NOT_READY=$(kubectl get nodes --no-headers | grep -v " Ready" | wc -l)
if [[ "$NODES_NOT_READY" -eq 0 ]]; then
  TOTAL_NODES=$(kubectl get nodes --no-headers | wc -l)
  check_pass "All $TOTAL_NODES nodes are Ready"
else
  check_fail "$NODES_NOT_READY node(s) not Ready"
fi

# Check critical pods in kube-system
CRITICAL_PODS=("coredns" "kube-proxy" "aws-node" "cluster-autoscaler")
for pod_prefix in "${CRITICAL_PODS[@]}"; do
  POD_STATUS=$(kubectl get pods -n kube-system -l k8s-app="$pod_prefix" --no-headers 2>/dev/null | grep -v "Running" | wc -l || echo "0")
  if [[ "$POD_STATUS" -eq 0 ]]; then
    check_pass "kube-system/$pod_prefix pods healthy"
  else
    check_fail "kube-system/$pod_prefix has unhealthy pods"
  fi
done

# =============================================================================
# PHOENIX GUARDIAN PODS
# =============================================================================

log_info "Checking Phoenix Guardian pods..."

# Check pod status
DEPLOYMENTS=("phoenix-api" "phoenix-worker" "phoenix-beacon")
for deploy in "${DEPLOYMENTS[@]}"; do
  # Check deployment exists and is available
  AVAILABLE=$(kubectl get deployment "$deploy" -n "$ENV" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")
  DESIRED=$(kubectl get deployment "$deploy" -n "$ENV" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
  
  if [[ "$AVAILABLE" -ge 1 ]] && [[ "$AVAILABLE" -eq "$DESIRED" ]]; then
    check_pass "$deploy: $AVAILABLE/$DESIRED replicas available"
  elif [[ "$AVAILABLE" -ge 1 ]]; then
    log_warning "$deploy: $AVAILABLE/$DESIRED replicas available (degraded)"
    ((HEALTH_CHECKS_PASSED++))  # Degraded but still functional
  else
    check_fail "$deploy: $AVAILABLE/$DESIRED replicas available"
  fi
  
  # Check for pod restarts
  RESTART_COUNT=$(kubectl get pods -n "$ENV" -l app.kubernetes.io/name="$deploy" -o jsonpath='{.items[*].status.containerStatuses[*].restartCount}' 2>/dev/null | tr ' ' '\n' | awk '{sum+=$1} END {print sum}' || echo "0")
  if [[ "${RESTART_COUNT:-0}" -lt 5 ]]; then
    check_pass "$deploy: low restart count ($RESTART_COUNT)"
  else
    check_fail "$deploy: high restart count ($RESTART_COUNT)"
  fi
done

# =============================================================================
# API ENDPOINT HEALTH
# =============================================================================

log_info "Checking API endpoint health..."

# Get API endpoint
API_ENDPOINT=$(kubectl get service phoenix-api -n "$ENV" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")

if [[ -z "$API_ENDPOINT" ]]; then
  log_warning "API endpoint not yet available (LoadBalancer pending)"
  
  # Fallback to port-forward check
  log_info "Using port-forward for internal check..."
  kubectl port-forward -n "$ENV" service/phoenix-api 8080:80 &>/dev/null &
  PF_PID=$!
  sleep 3
  
  API_ENDPOINT="localhost:8080"
  CLEANUP_PF=true
else
  CLEANUP_PF=false
fi

# Wait for DNS propagation
log_info "Waiting for endpoint availability..."
for ((i=1; i<=RETRY_COUNT; i++)); do
  if curl -sf --connect-timeout 5 "http://$API_ENDPOINT/health" &>/dev/null; then
    break
  fi
  if [[ $i -eq $RETRY_COUNT ]]; then
    check_fail "API endpoint not responding after $RETRY_COUNT attempts"
    [[ "$CLEANUP_PF" == "true" ]] && kill $PF_PID 2>/dev/null
    exit 1
  fi
  log_info "Attempt $i/$RETRY_COUNT - waiting ${RETRY_DELAY}s..."
  sleep $RETRY_DELAY
done

# Health endpoint
HEALTH_RESPONSE=$(curl -sf --connect-timeout "$TIMEOUT" "http://$API_ENDPOINT/health" 2>/dev/null || echo "")
if echo "$HEALTH_RESPONSE" | grep -q '"status":"healthy"'; then
  check_pass "API /health endpoint healthy"
else
  check_fail "API /health endpoint unhealthy: $HEALTH_RESPONSE"
fi

# Ready endpoint
READY_RESPONSE=$(curl -sf --connect-timeout "$TIMEOUT" "http://$API_ENDPOINT/health/ready" 2>/dev/null || echo "")
if echo "$READY_RESPONSE" | grep -q '"ready":true'; then
  check_pass "API /health/ready endpoint ready"
else
  check_fail "API /health/ready endpoint not ready: $READY_RESPONSE"
fi

# Cleanup port-forward if used
[[ "$CLEANUP_PF" == "true" ]] && kill $PF_PID 2>/dev/null

# =============================================================================
# DATABASE CONNECTIVITY
# =============================================================================

log_info "Checking database connectivity..."

# Use a pod to test database connection
DB_CHECK=$(kubectl exec -n "$ENV" deployment/phoenix-api -- python -c "
import os
import sys
try:
    import psycopg2
    conn = psycopg2.connect(
        host=os.environ['DB_HOST'],
        port=os.environ['DB_PORT'],
        dbname=os.environ['DB_NAME'],
        user=os.environ['DB_USERNAME'],
        password=os.environ['DB_PASSWORD'],
        sslmode='require',
        connect_timeout=10
    )
    cursor = conn.cursor()
    cursor.execute('SELECT 1')
    result = cursor.fetchone()
    conn.close()
    print('OK' if result[0] == 1 else 'FAILED')
except Exception as e:
    print(f'FAILED: {e}')
    sys.exit(1)
" 2>&1 || echo "FAILED: Could not execute")

if [[ "$DB_CHECK" == "OK" ]]; then
  check_pass "PostgreSQL database connection healthy"
else
  check_fail "PostgreSQL database connection failed: $DB_CHECK"
fi

# =============================================================================
# REDIS CONNECTIVITY
# =============================================================================

log_info "Checking Redis connectivity..."

REDIS_CHECK=$(kubectl exec -n "$ENV" deployment/phoenix-api -- python -c "
import os
import sys
try:
    import redis
    r = redis.Redis(
        host=os.environ['REDIS_HOST'],
        port=int(os.environ['REDIS_PORT']),
        password=os.environ.get('REDIS_AUTH_TOKEN'),
        ssl=os.environ.get('REDIS_SSL', 'true').lower() == 'true',
        socket_timeout=10
    )
    r.ping()
    print('OK')
except Exception as e:
    print(f'FAILED: {e}')
    sys.exit(1)
" 2>&1 || echo "FAILED: Could not execute")

if [[ "$REDIS_CHECK" == "OK" ]]; then
  check_pass "Redis connection healthy"
else
  check_fail "Redis connection failed: $REDIS_CHECK"
fi

# =============================================================================
# ML SERVICE HEALTH
# =============================================================================

log_info "Checking ML service (Beacon) health..."

BEACON_HEALTH=$(kubectl exec -n "$ENV" deployment/phoenix-api -- curl -sf --connect-timeout 5 "http://phoenix-beacon:8080/health" 2>/dev/null || echo "")
if echo "$BEACON_HEALTH" | grep -q '"status":"healthy"'; then
  check_pass "Phoenix Beacon (ML) service healthy"
else
  check_fail "Phoenix Beacon (ML) service unhealthy: $BEACON_HEALTH"
fi

# =============================================================================
# HORIZONTAL POD AUTOSCALER
# =============================================================================

log_info "Checking Horizontal Pod Autoscalers..."

for deploy in "${DEPLOYMENTS[@]}"; do
  HPA_STATUS=$(kubectl get hpa "$deploy" -n "$ENV" -o jsonpath='{.status.currentReplicas}/{.spec.maxReplicas}' 2>/dev/null || echo "N/A")
  if [[ "$HPA_STATUS" != "N/A" ]]; then
    check_pass "HPA $deploy: $HPA_STATUS replicas"
  else
    log_warning "HPA $deploy: not found"
  fi
done

# =============================================================================
# PERSISTENT VOLUME CLAIMS
# =============================================================================

log_info "Checking Persistent Volume Claims..."

PVC_PENDING=$(kubectl get pvc -n "$ENV" --no-headers 2>/dev/null | grep -v "Bound" | wc -l || echo "0")
if [[ "$PVC_PENDING" -eq 0 ]]; then
  PVC_TOTAL=$(kubectl get pvc -n "$ENV" --no-headers 2>/dev/null | wc -l || echo "0")
  if [[ "$PVC_TOTAL" -gt 0 ]]; then
    check_pass "All $PVC_TOTAL PVCs are Bound"
  else
    log_info "No PVCs in namespace"
  fi
else
  check_fail "$PVC_PENDING PVC(s) not Bound"
fi

# =============================================================================
# RECENT EVENTS CHECK
# =============================================================================

log_info "Checking for warning events..."

WARNING_EVENTS=$(kubectl get events -n "$ENV" --field-selector type=Warning --sort-by='.lastTimestamp' 2>/dev/null | tail -5 || echo "")
if [[ -z "$WARNING_EVENTS" ]] || [[ $(echo "$WARNING_EVENTS" | wc -l) -le 1 ]]; then
  check_pass "No recent warning events"
else
  log_warning "Recent warning events detected:"
  echo "$WARNING_EVENTS" | head -5
fi

# =============================================================================
# SUMMARY
# =============================================================================

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    HEALTH CHECK SUMMARY                           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "   Passed: $HEALTH_CHECKS_PASSED"
echo "   Failed: $HEALTH_CHECKS_FAILED"
echo ""

if [[ "$HEALTH_CHECKS_FAILED" -eq 0 ]]; then
  log_success "All health checks PASSED"
  exit 0
else
  log_error "$HEALTH_CHECKS_FAILED health check(s) FAILED"
  exit 1
fi
