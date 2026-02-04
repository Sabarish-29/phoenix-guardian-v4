#!/bin/bash
# =============================================================================
# PHOENIX GUARDIAN - PRODUCTION DEPLOYMENT SCRIPT
# =============================================================================
# One-command deployment to AWS EKS
# Usage: ./deploy.sh [staging|production]
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}ℹ${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }

# Configuration
ENV=${1:-production}
AWS_REGION=${AWS_REGION:-us-east-1}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRASTRUCTURE_DIR="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$INFRASTRUCTURE_DIR/terraform"
K8S_DIR="$INFRASTRUCTURE_DIR/k8s"

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         PHOENIX GUARDIAN - PRODUCTION DEPLOYMENT                  ║"
echo "║                                                                    ║"
echo "║  Environment: $ENV                                           ║"
echo "║  Region:      $AWS_REGION                                         ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# VALIDATION
# =============================================================================

log_info "Validating environment..."

# Validate environment parameter
if [[ ! "$ENV" =~ ^(staging|production)$ ]]; then
  log_error "Invalid environment. Use: staging or production"
  exit 1
fi

# Production requires confirmation
if [[ "$ENV" == "production" ]]; then
  log_warning "You are about to deploy to PRODUCTION!"
  read -p "Type 'yes' to confirm: " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    log_error "Deployment cancelled."
    exit 1
  fi
fi

# Check prerequisites
log_info "Checking prerequisites..."

PREREQS=("terraform" "kubectl" "aws" "helm" "jq")
for cmd in "${PREREQS[@]}"; do
  if ! command -v "$cmd" &> /dev/null; then
    log_error "$cmd is not installed. Please install it first."
    exit 1
  fi
  log_success "$cmd found"
done

# Verify AWS credentials
log_info "Verifying AWS credentials..."
AWS_IDENTITY=$(aws sts get-caller-identity --output json 2>/dev/null || echo "")
if [[ -z "$AWS_IDENTITY" ]]; then
  log_error "AWS credentials not configured. Run 'aws configure' first."
  exit 1
fi
AWS_ACCOUNT=$(echo "$AWS_IDENTITY" | jq -r '.Account')
log_success "AWS Account: $AWS_ACCOUNT"

# =============================================================================
# TERRAFORM DEPLOYMENT
# =============================================================================

log_info "Deploying infrastructure with Terraform..."
cd "$TERRAFORM_DIR"

# Initialize Terraform
log_info "Initializing Terraform..."
terraform init -backend-config="key=$ENV/terraform.tfstate" -reconfigure

# Plan changes
log_info "Planning Terraform changes..."
terraform plan \
  -var="environment=$ENV" \
  -var="aws_region=$AWS_REGION" \
  -out=tfplan \
  -detailed-exitcode || PLAN_EXIT=$?

# Exit code 2 means changes detected
if [[ "${PLAN_EXIT:-0}" == "1" ]]; then
  log_error "Terraform plan failed!"
  exit 1
fi

# Apply changes
log_info "Applying Terraform changes..."
terraform apply tfplan

# Get outputs
log_info "Retrieving Terraform outputs..."
EKS_CLUSTER=$(terraform output -raw eks_cluster_id)
ECR_REGISTRY=$(terraform output -raw ecr_registry)
RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
REDIS_ENDPOINT=$(terraform output -raw redis_endpoint)

log_success "EKS Cluster: $EKS_CLUSTER"
log_success "ECR Registry: $ECR_REGISTRY"
log_success "RDS Endpoint: $RDS_ENDPOINT"
log_success "Redis Endpoint: $REDIS_ENDPOINT"

# =============================================================================
# KUBERNETES CONFIGURATION
# =============================================================================

log_info "Configuring kubectl..."
aws eks update-kubeconfig --name "$EKS_CLUSTER" --region "$AWS_REGION"

# Verify cluster access
log_info "Verifying cluster access..."
if ! kubectl cluster-info &> /dev/null; then
  log_error "Cannot connect to Kubernetes cluster!"
  exit 1
fi
log_success "Connected to Kubernetes cluster"

# Display node status
log_info "Cluster nodes:"
kubectl get nodes -o wide

# =============================================================================
# ARGOCD INSTALLATION
# =============================================================================

if ! kubectl get namespace argocd &> /dev/null; then
  log_info "Installing ArgoCD..."
  kubectl create namespace argocd
  kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
  
  log_info "Waiting for ArgoCD to be ready..."
  kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd
  log_success "ArgoCD installed"
else
  log_success "ArgoCD already installed"
fi

# =============================================================================
# NAMESPACE CREATION
# =============================================================================

log_info "Creating Kubernetes namespaces..."
kubectl apply -f "$K8S_DIR/namespaces/"
log_success "Namespaces created"

# =============================================================================
# SECRETS CONFIGURATION
# =============================================================================

log_info "Configuring secrets..."

# Get secrets from Secrets Manager
DB_CREDS=$(aws secretsmanager get-secret-value \
  --secret-id "phoenix-$ENV/database/credentials" \
  --query SecretString --output text)

REDIS_CREDS=$(aws secretsmanager get-secret-value \
  --secret-id "phoenix-$ENV/redis/credentials" \
  --query SecretString --output text)

# Create Kubernetes secrets
kubectl create secret generic phoenix-db-credentials \
  --namespace="$ENV" \
  --from-literal=username=$(echo "$DB_CREDS" | jq -r '.username') \
  --from-literal=password=$(echo "$DB_CREDS" | jq -r '.password') \
  --from-literal=host=$(echo "$DB_CREDS" | jq -r '.host') \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic phoenix-redis-credentials \
  --namespace="$ENV" \
  --from-literal=auth_token=$(echo "$REDIS_CREDS" | jq -r '.auth_token') \
  --from-literal=host=$(echo "$REDIS_CREDS" | jq -r '.primary_endpoint') \
  --dry-run=client -o yaml | kubectl apply -f -

log_success "Secrets configured"

# =============================================================================
# APPLICATION DEPLOYMENT
# =============================================================================

log_info "Deploying Phoenix Guardian applications..."

# Update image references in manifests
IMAGE_TAG=${IMAGE_TAG:-latest}
IMAGE="$ECR_REGISTRY/phoenix-guardian:$IMAGE_TAG"

# Apply manifests with substitutions
for manifest in "$K8S_DIR/apps/"*.yaml; do
  log_info "Applying $(basename "$manifest")..."
  sed -e "s|IMAGE_PLACEHOLDER|$IMAGE|g" \
      -e "s|REGION|$AWS_REGION|g" \
      -e "s|ACCOUNT_ID|$AWS_ACCOUNT|g" \
      "$manifest" | kubectl apply -n "$ENV" -f -
done

log_success "Applications deployed"

# =============================================================================
# WAIT FOR PODS
# =============================================================================

log_info "Waiting for pods to be ready..."

# Wait for deployments
DEPLOYMENTS=("phoenix-api" "phoenix-worker" "phoenix-beacon")
for deploy in "${DEPLOYMENTS[@]}"; do
  log_info "Waiting for $deploy..."
  kubectl rollout status deployment/"$deploy" -n "$ENV" --timeout=600s
  log_success "$deploy is ready"
done

# =============================================================================
# HEALTH CHECK
# =============================================================================

log_info "Running health check..."
"$SCRIPT_DIR/health_check.sh" "$ENV"

# =============================================================================
# DEPLOYMENT SUMMARY
# =============================================================================

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    DEPLOYMENT COMPLETE                            ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Get endpoints
API_ENDPOINT=$(kubectl get service phoenix-api -n "$ENV" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "pending")
ARGOCD_ENDPOINT=$(kubectl get service argocd-server -n argocd -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "pending")

echo "📍 Endpoints:"
echo "   API:     https://$API_ENDPOINT"
echo "   ArgoCD:  https://$ARGOCD_ENDPOINT"
echo ""
echo "📊 Resource Summary:"
kubectl get pods -n "$ENV" --no-headers | wc -l | xargs echo "   Pods:"
kubectl get services -n "$ENV" --no-headers | wc -l | xargs echo "   Services:"
echo ""
echo "🔑 ArgoCD Admin Password:"
echo "   kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
echo ""
log_success "Deployment to $ENV complete!"
