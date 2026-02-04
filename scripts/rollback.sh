#!/bin/bash
# ==============================================================================
# Phoenix Guardian - Emergency Rollback Script
# Instantly revert to previous deployment
# Version: 1.0.0
#
# Usage:
#   ./rollback.sh                  # Rollback all components
#   ./rollback.sh app              # Rollback only app deployment
#   ./rollback.sh --to-revision 3  # Rollback to specific revision
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

NAMESPACE="${NAMESPACE:-phoenix-guardian}"
COMPONENT="${1:-all}"
REVISION=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --to-revision)
            REVISION="$2"
            shift 2
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        *)
            COMPONENT="$1"
            shift
            ;;
    esac
done

# ==============================================================================
# Helper Functions
# ==============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

show_banner() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║           Phoenix Guardian - Emergency Rollback                   ║"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    echo "║  Namespace: ${NAMESPACE}                                          ║"
    echo "║  Component: ${COMPONENT}                                                ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
}

# ==============================================================================
# Rollback Functions
# ==============================================================================

show_revision_history() {
    local deployment=$1
    
    log_info "Revision history for ${deployment}:"
    kubectl rollout history deployment/"$deployment" -n "$NAMESPACE" 2>/dev/null || true
    echo ""
}

rollback_deployment() {
    local deployment=$1
    
    log_info "Rolling back ${deployment}..."
    
    if [[ -n "$REVISION" ]]; then
        kubectl rollout undo deployment/"$deployment" -n "$NAMESPACE" --to-revision="$REVISION"
    else
        kubectl rollout undo deployment/"$deployment" -n "$NAMESPACE"
    fi
    
    # Wait for rollback to complete
    log_info "Waiting for rollback to complete..."
    kubectl rollout status deployment/"$deployment" -n "$NAMESPACE" --timeout=300s
    
    log_success "${deployment} rolled back successfully"
}

rollback_statefulset() {
    local statefulset=$1
    
    log_warn "StatefulSet rollback for ${statefulset} - use with caution!"
    log_info "Current pods:"
    kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component="$statefulset"
    
    read -p "Continue with StatefulSet rollback? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        log_info "StatefulSet rollback cancelled"
        return
    fi
    
    kubectl rollout undo statefulset/"$statefulset" -n "$NAMESPACE"
    kubectl rollout status statefulset/"$statefulset" -n "$NAMESPACE" --timeout=600s
    
    log_success "${statefulset} rolled back"
}

rollback_all() {
    log_info "Rolling back all deployments..."
    
    # Rollback in reverse order of deployment
    local deployments=(
        "phoenix-guardian-beacon"
        "phoenix-guardian-worker"
        "phoenix-guardian-app"
    )
    
    for deployment in "${deployments[@]}"; do
        if kubectl get deployment "$deployment" -n "$NAMESPACE" &> /dev/null; then
            rollback_deployment "$deployment"
        else
            log_warn "Deployment ${deployment} not found, skipping"
        fi
    done
    
    log_success "All deployments rolled back"
}

verify_rollback() {
    log_info "Verifying rollback..."
    
    # Check pod status
    local unhealthy_pods=$(kubectl get pods -n "$NAMESPACE" \
        --field-selector=status.phase!=Running,status.phase!=Succeeded \
        -o name 2>/dev/null | wc -l)
    
    if [[ "$unhealthy_pods" -gt 0 ]]; then
        log_error "Found ${unhealthy_pods} unhealthy pods after rollback"
        kubectl get pods -n "$NAMESPACE"
        return 1
    fi
    
    # Quick health check
    local app_pod=$(kubectl get pods -n "$NAMESPACE" \
        -l app.kubernetes.io/component=app \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [[ -n "$app_pod" ]]; then
        if kubectl exec -n "$NAMESPACE" "$app_pod" -- curl -sf http://localhost:8000/health &> /dev/null; then
            log_success "Application health check passed"
        else
            log_error "Application health check failed"
            return 1
        fi
    fi
    
    log_success "Rollback verification complete"
}

show_current_state() {
    log_info "Current deployment state:"
    echo ""
    
    kubectl get deployments -n "$NAMESPACE" \
        -o custom-columns='NAME:.metadata.name,READY:.status.readyReplicas,IMAGE:.spec.template.spec.containers[0].image'
    
    echo ""
    log_info "Pod status:"
    kubectl get pods -n "$NAMESPACE" -o wide
}

# ==============================================================================
# Main Execution
# ==============================================================================

main() {
    show_banner
    
    # Verify namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_error "Namespace ${NAMESPACE} not found"
        exit 1
    fi
    
    case "$COMPONENT" in
        all)
            show_revision_history "phoenix-guardian-app"
            rollback_all
            ;;
        app)
            show_revision_history "phoenix-guardian-app"
            rollback_deployment "phoenix-guardian-app"
            ;;
        worker)
            show_revision_history "phoenix-guardian-worker"
            rollback_deployment "phoenix-guardian-worker"
            ;;
        beacon)
            show_revision_history "phoenix-guardian-beacon"
            rollback_deployment "phoenix-guardian-beacon"
            ;;
        postgres)
            rollback_statefulset "postgres"
            ;;
        redis)
            rollback_statefulset "redis"
            ;;
        *)
            log_error "Unknown component: ${COMPONENT}"
            echo "Valid components: all, app, worker, beacon, postgres, redis"
            exit 1
            ;;
    esac
    
    verify_rollback
    show_current_state
    
    log_success "Rollback completed successfully"
}

main "$@"
