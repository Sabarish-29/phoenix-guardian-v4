#!/bin/bash
# ==============================================================================
# Phoenix Guardian - Deployment Script
# Single-command deployment to Kubernetes
# Version: 1.0.0
#
# Usage:
#   ./deploy.sh                    # Deploy with latest tag
#   ./deploy.sh v1.2.3             # Deploy specific version
#   ./deploy.sh latest staging     # Deploy to staging namespace
#   ./deploy.sh latest production  # Deploy to production (requires confirmation)
# ==============================================================================

set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Script configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
readonly K8S_DIR="${PROJECT_ROOT}/k8s"
readonly DOCKER_DIR="${PROJECT_ROOT}/docker"

# Deployment configuration
IMAGE_TAG="${1:-latest}"
ENVIRONMENT="${2:-staging}"
REGISTRY="${DOCKER_REGISTRY:-ghcr.io/phoenix-guardian}"
NAMESPACE="phoenix-guardian-${ENVIRONMENT}"
TIMEOUT="600s"

# Deployment tracking
DEPLOY_START_TIME=$(date +%s)
DEPLOY_STEPS_TOTAL=10
DEPLOY_STEPS_COMPLETED=0

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

log_step() {
    DEPLOY_STEPS_COMPLETED=$((DEPLOY_STEPS_COMPLETED + 1))
    echo -e "${YELLOW}[${DEPLOY_STEPS_COMPLETED}/${DEPLOY_STEPS_TOTAL}]${NC} $1"
}

show_banner() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║           Phoenix Guardian - Kubernetes Deployment               ║"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    echo "║  Environment: ${ENVIRONMENT}                                            ║"
    echo "║  Image Tag:   ${IMAGE_TAG}                                              ║"
    echo "║  Namespace:   ${NAMESPACE}                                    ║"
    echo "║  Registry:    ${REGISTRY}                          ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
}

confirm_production() {
    if [[ "$ENVIRONMENT" == "production" ]]; then
        echo ""
        log_warn "You are about to deploy to PRODUCTION!"
        echo ""
        read -p "Type 'yes-deploy-production' to confirm: " confirmation
        if [[ "$confirmation" != "yes-deploy-production" ]]; then
            log_error "Production deployment cancelled."
            exit 1
        fi
        echo ""
    fi
}

calculate_duration() {
    local end_time=$(date +%s)
    local duration=$((end_time - DEPLOY_START_TIME))
    echo "${duration}s"
}

# ==============================================================================
# Pre-flight Checks
# ==============================================================================

preflight_checks() {
    log_step "Running pre-flight checks..."
    
    local checks_passed=true
    
    # Check kubectl is installed and configured
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        checks_passed=false
    elif ! kubectl cluster-info &> /dev/null; then
        log_error "kubectl is not configured or cluster is unreachable"
        checks_passed=false
    else
        log_success "kubectl configured and cluster reachable"
    fi
    
    # Check docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "docker is not installed"
        checks_passed=false
    else
        log_success "docker is installed"
    fi
    
    # Check required files exist
    local required_files=(
        "${K8S_DIR}/namespaces.yaml"
        "${K8S_DIR}/secrets.yaml"
        "${K8S_DIR}/postgres-statefulset.yaml"
        "${K8S_DIR}/redis-deployment.yaml"
        "${K8S_DIR}/app-deployment.yaml"
        "${K8S_DIR}/worker-deployment.yaml"
        "${K8S_DIR}/beacon-deployment.yaml"
        "${K8S_DIR}/ingress.yaml"
        "${K8S_DIR}/hpa.yaml"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Required file not found: $file"
            checks_passed=false
        fi
    done
    log_success "All required Kubernetes manifests found"
    
    # Check Dockerfiles exist
    local dockerfiles=(
        "${DOCKER_DIR}/Dockerfile.app"
        "${DOCKER_DIR}/Dockerfile.worker"
        "${DOCKER_DIR}/Dockerfile.beacon"
    )
    
    for dockerfile in "${dockerfiles[@]}"; do
        if [[ ! -f "$dockerfile" ]]; then
            log_error "Required Dockerfile not found: $dockerfile"
            checks_passed=false
        fi
    done
    log_success "All Dockerfiles found"
    
    if [[ "$checks_passed" == "false" ]]; then
        log_error "Pre-flight checks failed. Aborting deployment."
        exit 1
    fi
    
    log_success "All pre-flight checks passed"
}

# ==============================================================================
# Docker Image Build
# ==============================================================================

build_docker_images() {
    log_step "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Build app image
    log_info "Building app image..."
    docker build \
        -t "${REGISTRY}/app:${IMAGE_TAG}" \
        -t "${REGISTRY}/app:latest" \
        -f docker/Dockerfile.app \
        --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --build-arg VERSION="${IMAGE_TAG}" \
        --build-arg VCS_REF="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
        .
    log_success "App image built: ${REGISTRY}/app:${IMAGE_TAG}"
    
    # Build worker image
    log_info "Building worker image..."
    docker build \
        -t "${REGISTRY}/worker:${IMAGE_TAG}" \
        -t "${REGISTRY}/worker:latest" \
        -f docker/Dockerfile.worker \
        .
    log_success "Worker image built: ${REGISTRY}/worker:${IMAGE_TAG}"
    
    # Build beacon image
    log_info "Building beacon image..."
    docker build \
        -t "${REGISTRY}/beacon:${IMAGE_TAG}" \
        -t "${REGISTRY}/beacon:latest" \
        -f docker/Dockerfile.beacon \
        .
    log_success "Beacon image built: ${REGISTRY}/beacon:${IMAGE_TAG}"
    
    log_success "All Docker images built successfully"
}

# ==============================================================================
# Docker Image Push
# ==============================================================================

push_docker_images() {
    log_step "Pushing Docker images to registry..."
    
    # Push app image
    log_info "Pushing app image..."
    docker push "${REGISTRY}/app:${IMAGE_TAG}"
    docker push "${REGISTRY}/app:latest"
    
    # Push worker image
    log_info "Pushing worker image..."
    docker push "${REGISTRY}/worker:${IMAGE_TAG}"
    docker push "${REGISTRY}/worker:latest"
    
    # Push beacon image
    log_info "Pushing beacon image..."
    docker push "${REGISTRY}/beacon:${IMAGE_TAG}"
    docker push "${REGISTRY}/beacon:latest"
    
    log_success "All images pushed to ${REGISTRY}"
}

# ==============================================================================
# Namespace Setup
# ==============================================================================

setup_namespace() {
    log_step "Setting up Kubernetes namespace..."
    
    # Create or update namespace
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "Namespace ${NAMESPACE} already exists"
    else
        log_info "Creating namespace ${NAMESPACE}..."
        # Modify namespace name in YAML and apply
        sed "s/phoenix-guardian/${NAMESPACE}/g" "${K8S_DIR}/namespaces.yaml" | kubectl apply -f -
    fi
    
    log_success "Namespace ${NAMESPACE} ready"
}

# ==============================================================================
# Secrets Deployment
# ==============================================================================

deploy_secrets() {
    log_step "Deploying secrets..."
    
    # Check if sealed-secrets controller is installed
    if kubectl get deployment sealed-secrets-controller -n kube-system &> /dev/null; then
        log_info "Deploying sealed secrets..."
        kubectl apply -f "${K8S_DIR}/secrets.yaml" -n "$NAMESPACE"
    else
        log_warn "Sealed Secrets controller not found. Using regular secrets."
        log_warn "Ensure secrets are created manually or via external secrets manager."
    fi
    
    # Wait for secrets to be unsealed
    sleep 5
    
    log_success "Secrets deployed"
}

# ==============================================================================
# Database Deployment
# ==============================================================================

deploy_database() {
    log_step "Deploying PostgreSQL StatefulSet..."
    
    # Apply PostgreSQL StatefulSet
    kubectl apply -f "${K8S_DIR}/postgres-statefulset.yaml" -n "$NAMESPACE"
    
    # Wait for PostgreSQL to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    kubectl rollout status statefulset/postgres -n "$NAMESPACE" --timeout="${TIMEOUT}"
    
    log_success "PostgreSQL StatefulSet deployed and ready"
}

# ==============================================================================
# Redis Deployment
# ==============================================================================

deploy_redis() {
    log_step "Deploying Redis..."
    
    # Apply Redis deployment
    kubectl apply -f "${K8S_DIR}/redis-deployment.yaml" -n "$NAMESPACE"
    
    # Wait for Redis to be ready
    log_info "Waiting for Redis to be ready..."
    kubectl rollout status statefulset/redis -n "$NAMESPACE" --timeout="${TIMEOUT}"
    
    log_success "Redis deployed and ready"
}

# ==============================================================================
# Application Deployment
# ==============================================================================

deploy_applications() {
    log_step "Deploying Phoenix Guardian applications..."
    
    # Update image tags in deployments
    log_info "Deploying app (3 replicas)..."
    kubectl apply -f "${K8S_DIR}/app-deployment.yaml" -n "$NAMESPACE"
    kubectl set image deployment/phoenix-guardian-app \
        app="${REGISTRY}/app:${IMAGE_TAG}" \
        -n "$NAMESPACE"
    
    log_info "Deploying worker (2 replicas)..."
    kubectl apply -f "${K8S_DIR}/worker-deployment.yaml" -n "$NAMESPACE"
    kubectl set image deployment/phoenix-guardian-worker \
        worker="${REGISTRY}/worker:${IMAGE_TAG}" \
        -n "$NAMESPACE"
    
    log_info "Deploying beacon (5 replicas)..."
    kubectl apply -f "${K8S_DIR}/beacon-deployment.yaml" -n "$NAMESPACE"
    kubectl set image deployment/phoenix-guardian-beacon \
        beacon="${REGISTRY}/beacon:${IMAGE_TAG}" \
        -n "$NAMESPACE"
    
    # Wait for all deployments
    log_info "Waiting for deployments to complete..."
    kubectl rollout status deployment/phoenix-guardian-app -n "$NAMESPACE" --timeout="${TIMEOUT}"
    kubectl rollout status deployment/phoenix-guardian-worker -n "$NAMESPACE" --timeout="${TIMEOUT}"
    kubectl rollout status deployment/phoenix-guardian-beacon -n "$NAMESPACE" --timeout="${TIMEOUT}"
    
    log_success "All applications deployed successfully"
}

# ==============================================================================
# Ingress and HPA Deployment
# ==============================================================================

deploy_infrastructure() {
    log_step "Deploying Ingress and HPA..."
    
    # Apply Ingress
    log_info "Deploying Ingress..."
    kubectl apply -f "${K8S_DIR}/ingress.yaml" -n "$NAMESPACE"
    
    # Apply HPA
    log_info "Deploying Horizontal Pod Autoscaler..."
    kubectl apply -f "${K8S_DIR}/hpa.yaml" -n "$NAMESPACE"
    
    log_success "Ingress and HPA deployed"
}

# ==============================================================================
# Health Checks
# ==============================================================================

run_health_checks() {
    log_step "Running post-deployment health checks..."
    
    local health_script="${SCRIPT_DIR}/health-check.sh"
    
    if [[ -f "$health_script" ]]; then
        bash "$health_script" "$NAMESPACE"
    else
        log_warn "Health check script not found, running basic checks..."
        
        # Basic pod health check
        local unhealthy_pods=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase!=Running,status.phase!=Succeeded -o name 2>/dev/null | wc -l)
        
        if [[ "$unhealthy_pods" -gt 0 ]]; then
            log_error "Found ${unhealthy_pods} unhealthy pods"
            kubectl get pods -n "$NAMESPACE" --field-selector=status.phase!=Running,status.phase!=Succeeded
            exit 1
        fi
        
        # Check app endpoint
        log_info "Checking application health endpoint..."
        local app_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/component=app -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        
        if [[ -n "$app_pod" ]]; then
            kubectl exec -n "$NAMESPACE" "$app_pod" -- curl -sf http://localhost:8000/health || {
                log_error "Health check failed for app"
                exit 1
            }
        fi
    fi
    
    log_success "All health checks passed"
}

# ==============================================================================
# Deployment Summary
# ==============================================================================

show_summary() {
    local duration=$(calculate_duration)
    
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║           Deployment Complete!                                    ║"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    echo "║  Environment: ${ENVIRONMENT}                                            ║"
    echo "║  Image Tag:   ${IMAGE_TAG}                                              ║"
    echo "║  Duration:    ${duration}                                              ║"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    echo "║  Endpoints:                                                       ║"
    echo "║    App:     https://phoenix-guardian.hospital.internal            ║"
    echo "║    Beacon:  https://beacon.phoenix-guardian.hospital.internal     ║"
    echo "║    Monitor: https://monitoring.phoenix-guardian.hospital.internal ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Show pod status
    log_info "Pod Status:"
    kubectl get pods -n "$NAMESPACE" -o wide
    
    echo ""
    log_info "Services:"
    kubectl get services -n "$NAMESPACE"
}

# ==============================================================================
# Main Execution
# ==============================================================================

main() {
    show_banner
    confirm_production
    
    preflight_checks
    build_docker_images
    push_docker_images
    setup_namespace
    deploy_secrets
    deploy_database
    deploy_redis
    deploy_applications
    deploy_infrastructure
    run_health_checks
    
    show_summary
    
    log_success "Deployment completed successfully in $(calculate_duration)"
}

# Run main function
main "$@"
