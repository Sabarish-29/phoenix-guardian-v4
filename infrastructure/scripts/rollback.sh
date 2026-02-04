#!/bin/bash
# =============================================================================
# PHOENIX GUARDIAN - ROLLBACK SCRIPT
# =============================================================================
# Rollback to previous deployment version
# Usage: ./rollback.sh [staging|production] [revision]
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
REVISION=${2:-}
AWS_REGION=${AWS_REGION:-us-east-1}

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║            PHOENIX GUARDIAN - ROLLBACK                            ║"
echo "║                                                                    ║"
echo "║  Environment: $ENV                                           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Validate environment
if [[ ! "$ENV" =~ ^(staging|production)$ ]]; then
  log_error "Invalid environment. Use: staging or production"
  exit 1
fi

# Production requires confirmation
if [[ "$ENV" == "production" ]]; then
  log_warning "You are about to ROLLBACK PRODUCTION!"
  read -p "Type 'yes' to confirm: " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    log_error "Rollback cancelled."
    exit 1
  fi
fi

# =============================================================================
# CURRENT STATE
# =============================================================================

log_info "Current deployment state:"
echo ""

DEPLOYMENTS=("phoenix-api" "phoenix-worker" "phoenix-beacon")
for deploy in "${DEPLOYMENTS[@]}"; do
  echo "📦 $deploy:"
  kubectl rollout history deployment/"$deploy" -n "$ENV" --revision=0 2>/dev/null | tail -3 || echo "   No history available"
  echo ""
done

# =============================================================================
# ROLLBACK OPTIONS
# =============================================================================

if [[ -z "$REVISION" ]]; then
  log_info "Available revisions for phoenix-api:"
  kubectl rollout history deployment/phoenix-api -n "$ENV"
  echo ""
  read -p "Enter revision number to rollback to (or press Enter for previous): " REVISION
fi

# =============================================================================
# EXECUTE ROLLBACK
# =============================================================================

log_info "Starting rollback..."

for deploy in "${DEPLOYMENTS[@]}"; do
  log_info "Rolling back $deploy..."
  
  if [[ -n "$REVISION" ]]; then
    kubectl rollout undo deployment/"$deploy" -n "$ENV" --to-revision="$REVISION"
  else
    kubectl rollout undo deployment/"$deploy" -n "$ENV"
  fi
  
  log_info "Waiting for $deploy rollback to complete..."
  kubectl rollout status deployment/"$deploy" -n "$ENV" --timeout=300s
  log_success "$deploy rolled back successfully"
done

# =============================================================================
# VERIFY ROLLBACK
# =============================================================================

log_info "Verifying rollback..."

# Check pod status
log_info "Pod status:"
kubectl get pods -n "$ENV" -l app.kubernetes.io/part-of=phoenix-guardian

# Run health check
log_info "Running health check..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/health_check.sh" "$ENV"

# =============================================================================
# ARGOCD SYNC (if using ArgoCD)
# =============================================================================

if kubectl get namespace argocd &> /dev/null; then
  log_info "Syncing ArgoCD application..."
  
  # Check if argocd CLI is available
  if command -v argocd &> /dev/null; then
    argocd app sync "phoenix-$ENV" --grpc-web 2>/dev/null || log_warning "ArgoCD sync skipped (not logged in)"
  else
    log_warning "ArgoCD CLI not found. Manual sync may be required."
  fi
fi

# =============================================================================
# SUMMARY
# =============================================================================

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    ROLLBACK COMPLETE                              ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_info "New deployment state:"
for deploy in "${DEPLOYMENTS[@]}"; do
  CURRENT_IMAGE=$(kubectl get deployment "$deploy" -n "$ENV" -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "unknown")
  echo "   $deploy: $CURRENT_IMAGE"
done
echo ""

log_success "Rollback to $ENV complete!"

# =============================================================================
# POST-ROLLBACK CHECKLIST
# =============================================================================

echo ""
log_warning "Post-rollback checklist:"
echo "   [ ] Verify all endpoints responding correctly"
echo "   [ ] Check error rates in monitoring dashboard"
echo "   [ ] Review application logs for errors"
echo "   [ ] Notify team of rollback completion"
echo "   [ ] Create incident report if production issue"
echo ""
