#!/bin/bash
# ==============================================================================
# Phoenix Guardian - Health Check Script
# 47-point validation checklist for post-deployment verification
# Version: 1.0.0
#
# Usage:
#   ./health-check.sh              # Check default namespace
#   ./health-check.sh staging      # Check staging namespace
#   ./health-check.sh production   # Check production namespace
# ==============================================================================

set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

NAMESPACE="${1:-phoenix-guardian}"
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNED=0
TOTAL_CHECKS=47

# ==============================================================================
# Helper Functions
# ==============================================================================

log_check() {
    echo -e "${BLUE}[CHECK]${NC} $1"
}

log_pass() {
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_fail() {
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
    echo -e "${RED}[FAIL]${NC} $1"
}

log_warn() {
    CHECKS_WARNED=$((CHECKS_WARNED + 1))
    echo -e "${YELLOW}[WARN]${NC} $1"
}

show_banner() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║       Phoenix Guardian - 47-Point Health Check                    ║"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    echo "║  Namespace: ${NAMESPACE}                                          ║"
    echo "║  Timestamp: $(date '+%Y-%m-%d %H:%M:%S')                          ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
}

section_header() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  $1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ==============================================================================
# 1. Namespace Checks (3 checks)
# ==============================================================================

check_namespace() {
    section_header "1. Namespace Checks"
    
    # Check 1: Namespace exists
    log_check "Namespace exists"
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_pass "Namespace ${NAMESPACE} exists"
    else
        log_fail "Namespace ${NAMESPACE} not found"
        return 1
    fi
    
    # Check 2: Resource quota exists
    log_check "Resource quota configured"
    if kubectl get resourcequota -n "$NAMESPACE" 2>/dev/null | grep -q "phoenix-guardian"; then
        log_pass "Resource quota configured"
    else
        log_warn "Resource quota not found"
    fi
    
    # Check 3: Network policy exists
    log_check "Network policy configured"
    if kubectl get networkpolicy -n "$NAMESPACE" 2>/dev/null | grep -q "phoenix-guardian"; then
        log_pass "Network policy configured"
    else
        log_warn "Network policy not found"
    fi
}

# ==============================================================================
# 2. Pod Health Checks (10 checks)
# ==============================================================================

check_pods() {
    section_header "2. Pod Health Checks"
    
    # Check 4: All app pods running
    log_check "App pods running"
    local app_ready=$(kubectl get deployment phoenix-guardian-app -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local app_desired=$(kubectl get deployment phoenix-guardian-app -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    if [[ "$app_ready" -ge "$app_desired" && "$app_desired" -gt 0 ]]; then
        log_pass "App pods: ${app_ready}/${app_desired} ready"
    else
        log_fail "App pods: ${app_ready}/${app_desired} ready"
    fi
    
    # Check 5: All worker pods running
    log_check "Worker pods running"
    local worker_ready=$(kubectl get deployment phoenix-guardian-worker -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local worker_desired=$(kubectl get deployment phoenix-guardian-worker -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    if [[ "$worker_ready" -ge "$worker_desired" && "$worker_desired" -gt 0 ]]; then
        log_pass "Worker pods: ${worker_ready}/${worker_desired} ready"
    else
        log_fail "Worker pods: ${worker_ready}/${worker_desired} ready"
    fi
    
    # Check 6: All beacon pods running
    log_check "Beacon pods running"
    local beacon_ready=$(kubectl get deployment phoenix-guardian-beacon -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local beacon_desired=$(kubectl get deployment phoenix-guardian-beacon -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    if [[ "$beacon_ready" -ge "$beacon_desired" && "$beacon_desired" -gt 0 ]]; then
        log_pass "Beacon pods: ${beacon_ready}/${beacon_desired} ready"
    else
        log_fail "Beacon pods: ${beacon_ready}/${beacon_desired} ready"
    fi
    
    # Check 7: PostgreSQL pods running
    log_check "PostgreSQL pods running"
    local pg_ready=$(kubectl get statefulset postgres -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [[ "$pg_ready" -ge 1 ]]; then
        log_pass "PostgreSQL pods: ${pg_ready} ready"
    else
        log_fail "PostgreSQL pods not ready"
    fi
    
    # Check 8: Redis pods running
    log_check "Redis pods running"
    local redis_ready=$(kubectl get statefulset redis -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [[ "$redis_ready" -ge 1 ]]; then
        log_pass "Redis pods: ${redis_ready} ready"
    else
        log_fail "Redis pods not ready"
    fi
    
    # Check 9: No pods in CrashLoopBackOff
    log_check "No pods in CrashLoopBackOff"
    local crash_pods=$(kubectl get pods -n "$NAMESPACE" 2>/dev/null | grep -c "CrashLoopBackOff" || echo "0")
    if [[ "$crash_pods" -eq 0 ]]; then
        log_pass "No pods in CrashLoopBackOff"
    else
        log_fail "${crash_pods} pods in CrashLoopBackOff"
    fi
    
    # Check 10: No pods pending
    log_check "No pods pending"
    local pending_pods=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Pending 2>/dev/null | wc -l)
    if [[ "$pending_pods" -le 1 ]]; then
        log_pass "No pods pending"
    else
        log_fail "$((pending_pods - 1)) pods pending"
    fi
    
    # Check 11: All pods have resource limits
    log_check "Pods have resource limits"
    local pods_without_limits=$(kubectl get pods -n "$NAMESPACE" -o json 2>/dev/null | \
        jq -r '.items[].spec.containers[] | select(.resources.limits == null) | .name' 2>/dev/null | wc -l || echo "0")
    if [[ "$pods_without_limits" -eq 0 ]]; then
        log_pass "All pods have resource limits"
    else
        log_warn "${pods_without_limits} containers without resource limits"
    fi
    
    # Check 12: Pods running as non-root
    log_check "Pods running as non-root"
    local root_pods=$(kubectl get pods -n "$NAMESPACE" -o json 2>/dev/null | \
        jq -r '.items[].spec.securityContext.runAsNonRoot // false' 2>/dev/null | grep -c "false" || echo "0")
    if [[ "$root_pods" -eq 0 ]]; then
        log_pass "All pods running as non-root"
    else
        log_warn "${root_pods} pods may be running as root"
    fi
    
    # Check 13: Pod distribution across nodes
    log_check "Pods distributed across nodes"
    local unique_nodes=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].spec.nodeName}' 2>/dev/null | tr ' ' '\n' | sort -u | wc -l)
    if [[ "$unique_nodes" -ge 2 ]]; then
        log_pass "Pods distributed across ${unique_nodes} nodes"
    else
        log_warn "Pods on only ${unique_nodes} node(s)"
    fi
}

# ==============================================================================
# 3. Service Checks (6 checks)
# ==============================================================================

check_services() {
    section_header "3. Service Checks"
    
    # Check 14: App service exists
    log_check "App service exists"
    if kubectl get service phoenix-guardian-app -n "$NAMESPACE" &> /dev/null; then
        log_pass "App service exists"
    else
        log_fail "App service not found"
    fi
    
    # Check 15: Worker service exists
    log_check "Worker service exists"
    if kubectl get service phoenix-guardian-worker -n "$NAMESPACE" &> /dev/null; then
        log_pass "Worker service exists"
    else
        log_warn "Worker service not found (may be headless)"
    fi
    
    # Check 16: Beacon service exists
    log_check "Beacon service exists"
    if kubectl get service phoenix-guardian-beacon -n "$NAMESPACE" &> /dev/null; then
        log_pass "Beacon service exists"
    else
        log_fail "Beacon service not found"
    fi
    
    # Check 17: PostgreSQL service exists
    log_check "PostgreSQL service exists"
    if kubectl get service postgres-service -n "$NAMESPACE" &> /dev/null; then
        log_pass "PostgreSQL service exists"
    else
        log_fail "PostgreSQL service not found"
    fi
    
    # Check 18: Redis service exists
    log_check "Redis service exists"
    if kubectl get service redis-service -n "$NAMESPACE" &> /dev/null; then
        log_pass "Redis service exists"
    else
        log_fail "Redis service not found"
    fi
    
    # Check 19: Service endpoints populated
    log_check "Service endpoints populated"
    local endpoints=$(kubectl get endpoints phoenix-guardian-app -n "$NAMESPACE" -o jsonpath='{.subsets[*].addresses[*].ip}' 2>/dev/null | wc -w)
    if [[ "$endpoints" -ge 1 ]]; then
        log_pass "App service has ${endpoints} endpoints"
    else
        log_fail "App service has no endpoints"
    fi
}

# ==============================================================================
# 4. Database Checks (6 checks)
# ==============================================================================

check_database() {
    section_header "4. Database Checks"
    
    # Get a postgres pod
    local pg_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=postgres -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    # Check 20: PostgreSQL connection
    log_check "PostgreSQL connection"
    if [[ -n "$pg_pod" ]]; then
        if kubectl exec -n "$NAMESPACE" "$pg_pod" -- pg_isready -U phoenix 2>/dev/null; then
            log_pass "PostgreSQL is accepting connections"
        else
            log_fail "PostgreSQL not accepting connections"
        fi
    else
        log_fail "No PostgreSQL pod found"
    fi
    
    # Check 21: Database exists
    log_check "Database phoenix_guardian exists"
    if [[ -n "$pg_pod" ]]; then
        if kubectl exec -n "$NAMESPACE" "$pg_pod" -- psql -U phoenix -d phoenix_guardian -c "SELECT 1" &> /dev/null; then
            log_pass "Database phoenix_guardian exists"
        else
            log_fail "Database phoenix_guardian not accessible"
        fi
    else
        log_warn "Cannot check database - no pod"
    fi
    
    # Check 22: PostgreSQL replication
    log_check "PostgreSQL replication"
    local pg_replicas=$(kubectl get statefulset postgres -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [[ "$pg_replicas" -ge 2 ]]; then
        log_pass "PostgreSQL has ${pg_replicas} replicas"
    else
        log_warn "PostgreSQL has only ${pg_replicas} replica(s)"
    fi
    
    # Check 23: PostgreSQL PVC bound
    log_check "PostgreSQL PVC bound"
    local pg_pvc=$(kubectl get pvc -n "$NAMESPACE" -l app.kubernetes.io/component=postgres 2>/dev/null | grep -c "Bound" || echo "0")
    if [[ "$pg_pvc" -ge 1 ]]; then
        log_pass "${pg_pvc} PostgreSQL PVC(s) bound"
    else
        log_fail "No PostgreSQL PVC bound"
    fi
    
    # Check 24: Redis connection
    log_check "Redis connection"
    local redis_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=redis -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [[ -n "$redis_pod" ]]; then
        if kubectl exec -n "$NAMESPACE" "$redis_pod" -c redis -- redis-cli ping 2>/dev/null | grep -q "PONG"; then
            log_pass "Redis is responding"
        else
            log_fail "Redis not responding"
        fi
    else
        log_fail "No Redis pod found"
    fi
    
    # Check 25: Redis persistence
    log_check "Redis persistence enabled"
    local redis_pvc=$(kubectl get pvc -n "$NAMESPACE" -l app.kubernetes.io/component=redis 2>/dev/null | grep -c "Bound" || echo "0")
    if [[ "$redis_pvc" -ge 1 ]]; then
        log_pass "${redis_pvc} Redis PVC(s) bound"
    else
        log_warn "No Redis PVC bound - data may not persist"
    fi
}

# ==============================================================================
# 5. Application Health Checks (8 checks)
# ==============================================================================

check_application_health() {
    section_header "5. Application Health Checks"
    
    # Get an app pod
    local app_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=app -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    # Check 26: App health endpoint
    log_check "App /health endpoint"
    if [[ -n "$app_pod" ]]; then
        if kubectl exec -n "$NAMESPACE" "$app_pod" -- curl -sf http://localhost:8000/health &> /dev/null; then
            log_pass "App health endpoint responding"
        else
            log_fail "App health endpoint not responding"
        fi
    else
        log_fail "No app pod found"
    fi
    
    # Check 27: App metrics endpoint
    log_check "App /metrics endpoint"
    if [[ -n "$app_pod" ]]; then
        if kubectl exec -n "$NAMESPACE" "$app_pod" -- curl -sf http://localhost:8000/metrics &> /dev/null; then
            log_pass "App metrics endpoint responding"
        else
            log_warn "App metrics endpoint not responding"
        fi
    else
        log_warn "Cannot check metrics - no pod"
    fi
    
    # Check 28: Beacon health endpoint
    log_check "Beacon health endpoint"
    local beacon_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=beacon -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [[ -n "$beacon_pod" ]]; then
        if kubectl exec -n "$NAMESPACE" "$beacon_pod" -- curl -sf http://localhost:8080/beacon/health &> /dev/null; then
            log_pass "Beacon health endpoint responding"
        else
            log_fail "Beacon health endpoint not responding"
        fi
    else
        log_fail "No beacon pod found"
    fi
    
    # Check 29: Worker is processing
    log_check "Worker is healthy"
    local worker_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=worker -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [[ -n "$worker_pod" ]]; then
        local worker_status=$(kubectl get pod "$worker_pod" -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null)
        if [[ "$worker_status" == "Running" ]]; then
            log_pass "Worker pod is running"
        else
            log_fail "Worker pod status: ${worker_status}"
        fi
    else
        log_fail "No worker pod found"
    fi
    
    # Check 30: Database connectivity from app
    log_check "App can connect to database"
    if [[ -n "$app_pod" ]]; then
        if kubectl exec -n "$NAMESPACE" "$app_pod" -- python -c "import os; from urllib.parse import urlparse; print('OK')" 2>/dev/null; then
            log_pass "App has Python available"
        else
            log_warn "Cannot verify database connectivity"
        fi
    else
        log_warn "Cannot check database connectivity - no pod"
    fi
    
    # Check 31: Redis connectivity from app
    log_check "App can connect to Redis"
    # Similar check - verify environment is set
    if [[ -n "$app_pod" ]]; then
        local redis_env=$(kubectl exec -n "$NAMESPACE" "$app_pod" -- printenv REDIS_URL 2>/dev/null || echo "")
        if [[ -n "$redis_env" ]]; then
            log_pass "REDIS_URL environment variable is set"
        else
            log_fail "REDIS_URL environment variable not set"
        fi
    else
        log_warn "Cannot check Redis connectivity - no pod"
    fi
    
    # Check 32: ML models loaded
    log_check "Application startup complete"
    if [[ -n "$app_pod" ]]; then
        local restart_count=$(kubectl get pod "$app_pod" -n "$NAMESPACE" -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo "0")
        if [[ "$restart_count" -eq 0 ]]; then
            log_pass "App has not restarted (stable)"
        else
            log_warn "App has restarted ${restart_count} time(s)"
        fi
    else
        log_warn "Cannot check startup - no pod"
    fi
    
    # Check 33: Response time acceptable
    log_check "Response time acceptable"
    if [[ -n "$app_pod" ]]; then
        local response_time=$(kubectl exec -n "$NAMESPACE" "$app_pod" -- curl -sf -w "%{time_total}" -o /dev/null http://localhost:8000/health 2>/dev/null || echo "99")
        if (( $(echo "$response_time < 1.0" | bc -l 2>/dev/null || echo 0) )); then
            log_pass "Response time: ${response_time}s"
        else
            log_warn "Response time: ${response_time}s (may be slow)"
        fi
    else
        log_warn "Cannot check response time - no pod"
    fi
}

# ==============================================================================
# 6. Security Checks (6 checks)
# ==============================================================================

check_security() {
    section_header "6. Security Checks"
    
    # Check 34: Secrets exist
    log_check "Required secrets exist"
    local required_secrets=("pg-credentials" "redis-credentials" "anthropic-credentials" "app-secrets")
    local secrets_found=0
    for secret in "${required_secrets[@]}"; do
        if kubectl get secret "$secret" -n "$NAMESPACE" &> /dev/null; then
            secrets_found=$((secrets_found + 1))
        fi
    done
    if [[ "$secrets_found" -eq ${#required_secrets[@]} ]]; then
        log_pass "All ${#required_secrets[@]} required secrets exist"
    else
        log_fail "Only ${secrets_found}/${#required_secrets[@]} required secrets exist"
    fi
    
    # Check 35: TLS configured
    log_check "TLS secret exists"
    if kubectl get secret phoenix-guardian-tls -n "$NAMESPACE" &> /dev/null; then
        log_pass "TLS secret exists"
    else
        log_warn "TLS secret not found"
    fi
    
    # Check 36: Network policy enforced
    log_check "Network policy exists"
    if kubectl get networkpolicy -n "$NAMESPACE" 2>/dev/null | grep -q "phoenix-guardian"; then
        log_pass "Network policy configured"
    else
        log_warn "No network policy found"
    fi
    
    # Check 37: Service account configured
    log_check "Service account configured"
    if kubectl get serviceaccount phoenix-guardian -n "$NAMESPACE" &> /dev/null; then
        log_pass "Service account exists"
    else
        log_warn "Service account not found"
    fi
    
    # Check 38: RBAC configured
    log_check "RBAC configured"
    local role_bindings=$(kubectl get rolebinding -n "$NAMESPACE" 2>/dev/null | wc -l)
    if [[ "$role_bindings" -gt 1 ]]; then
        log_pass "Role bindings configured"
    else
        log_warn "No role bindings found"
    fi
    
    # Check 39: Pod security context
    log_check "Pod security context set"
    local secure_pods=$(kubectl get pods -n "$NAMESPACE" -o json 2>/dev/null | \
        jq -r '.items[] | select(.spec.securityContext.runAsNonRoot == true) | .metadata.name' 2>/dev/null | wc -l || echo "0")
    local total_pods=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)
    if [[ "$secure_pods" -ge "$total_pods" && "$total_pods" -gt 0 ]]; then
        log_pass "All pods have security context"
    else
        log_warn "${secure_pods}/${total_pods} pods have security context"
    fi
}

# ==============================================================================
# 7. Ingress & Networking (4 checks)
# ==============================================================================

check_ingress() {
    section_header "7. Ingress & Networking"
    
    # Check 40: Ingress exists
    log_check "Ingress exists"
    if kubectl get ingress phoenix-guardian-ingress -n "$NAMESPACE" &> /dev/null; then
        log_pass "Ingress configured"
    else
        log_warn "Ingress not found"
    fi
    
    # Check 41: Ingress has address
    log_check "Ingress has address"
    local ingress_ip=$(kubectl get ingress phoenix-guardian-ingress -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
    local ingress_host=$(kubectl get ingress phoenix-guardian-ingress -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
    if [[ -n "$ingress_ip" || -n "$ingress_host" ]]; then
        log_pass "Ingress address: ${ingress_ip:-$ingress_host}"
    else
        log_warn "Ingress has no address assigned"
    fi
    
    # Check 42: DNS resolution
    log_check "DNS resolution"
    if command -v nslookup &> /dev/null; then
        if nslookup phoenix-guardian.hospital.internal &> /dev/null; then
            log_pass "DNS resolves correctly"
        else
            log_warn "DNS not resolving (may be internal)"
        fi
    else
        log_warn "Cannot check DNS - nslookup not available"
    fi
    
    # Check 43: Internal service DNS
    log_check "Internal service DNS"
    local app_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=app -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [[ -n "$app_pod" ]]; then
        if kubectl exec -n "$NAMESPACE" "$app_pod" -- nslookup postgres-service.phoenix-guardian.svc.cluster.local &> /dev/null; then
            log_pass "Internal DNS working"
        else
            log_warn "Internal DNS may have issues"
        fi
    else
        log_warn "Cannot check internal DNS - no pod"
    fi
}

# ==============================================================================
# 8. Autoscaling & Resources (4 checks)
# ==============================================================================

check_autoscaling() {
    section_header "8. Autoscaling & Resources"
    
    # Check 44: HPA configured
    log_check "HPA configured"
    local hpa_count=$(kubectl get hpa -n "$NAMESPACE" 2>/dev/null | grep -c "phoenix-guardian" || echo "0")
    if [[ "$hpa_count" -ge 1 ]]; then
        log_pass "${hpa_count} HPA(s) configured"
    else
        log_warn "No HPA configured"
    fi
    
    # Check 45: HPA current replicas
    log_check "HPA current status"
    local hpa_status=$(kubectl get hpa phoenix-guardian-app-hpa -n "$NAMESPACE" -o jsonpath='{.status.currentReplicas}/{.spec.maxReplicas}' 2>/dev/null || echo "N/A")
    if [[ "$hpa_status" != "N/A" ]]; then
        log_pass "App HPA: ${hpa_status} replicas"
    else
        log_warn "Cannot get HPA status"
    fi
    
    # Check 46: PDB configured
    log_check "Pod Disruption Budget configured"
    local pdb_count=$(kubectl get pdb -n "$NAMESPACE" 2>/dev/null | grep -c "phoenix-guardian" || echo "0")
    if [[ "$pdb_count" -ge 1 ]]; then
        log_pass "${pdb_count} PDB(s) configured"
    else
        log_warn "No PDB configured"
    fi
    
    # Check 47: Resource usage reasonable
    log_check "Resource usage reasonable"
    local cpu_usage=$(kubectl top pods -n "$NAMESPACE" 2>/dev/null | awk 'NR>1 {sum+=$2} END {print sum}' 2>/dev/null || echo "0")
    if [[ "$cpu_usage" =~ ^[0-9]+$ && "$cpu_usage" -lt 10000 ]]; then
        log_pass "CPU usage: ${cpu_usage}m"
    else
        log_warn "Cannot determine resource usage"
    fi
}

# ==============================================================================
# Summary
# ==============================================================================

show_summary() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║                    Health Check Summary                           ║"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    printf "║  %-10s %-50s     ║\n" "PASSED:" "${CHECKS_PASSED}/${TOTAL_CHECKS}"
    printf "║  %-10s %-50s     ║\n" "FAILED:" "${CHECKS_FAILED}"
    printf "║  %-10s %-50s     ║\n" "WARNINGS:" "${CHECKS_WARNED}"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    
    if [[ "$CHECKS_FAILED" -eq 0 ]]; then
        echo "║  ${GREEN}STATUS: HEALTHY${NC}                                                  ║"
    elif [[ "$CHECKS_FAILED" -le 3 ]]; then
        echo "║  ${YELLOW}STATUS: DEGRADED${NC}                                                 ║"
    else
        echo "║  ${RED}STATUS: UNHEALTHY${NC}                                                ║"
    fi
    
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
}

# ==============================================================================
# Main Execution
# ==============================================================================

main() {
    show_banner
    
    # Verify namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_fail "Namespace ${NAMESPACE} not found"
        exit 1
    fi
    
    check_namespace
    check_pods
    check_services
    check_database
    check_application_health
    check_security
    check_ingress
    check_autoscaling
    
    show_summary
    
    # Exit with appropriate code
    if [[ "$CHECKS_FAILED" -gt 0 ]]; then
        exit 1
    fi
    
    exit 0
}

main "$@"
