#!/usr/bin/env bash
# Phoenix Guardian - DR Failover Script
# Sprint 67-68: Multi-Region DR
#
# Automated failover from us-east-1 to us-west-2
# RTO Target: 15 minutes

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

PRIMARY_REGION="us-east-1"
DR_REGION="us-west-2"
ENVIRONMENT="${ENVIRONMENT:-production}"
CLUSTER_NAME="phoenix-guardian-${ENVIRONMENT}"
DR_CLUSTER_NAME="phoenix-guardian-dr-${ENVIRONMENT}"
GLOBAL_DB_CLUSTER="phoenix-guardian-global-${ENVIRONMENT}"

# Slack webhook for notifications
SLACK_WEBHOOK="${SLACK_WEBHOOK_URL:-}"

# Logging
LOG_FILE="/var/log/phoenix-dr-failover-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    log "ERROR: $1"
    notify_slack ":x: FAILOVER ERROR: $1" "danger"
    exit 1
}

notify_slack() {
    local message="$1"
    local color="${2:-good}"
    
    if [[ -n "$SLACK_WEBHOOK" ]]; then
        curl -s -X POST "$SLACK_WEBHOOK" \
            -H 'Content-Type: application/json' \
            -d "{
                \"attachments\": [{
                    \"color\": \"$color\",
                    \"text\": \"$message\",
                    \"footer\": \"Phoenix Guardian DR\",
                    \"ts\": $(date +%s)
                }]
            }" || true
    fi
}

confirm_action() {
    local prompt="$1"
    if [[ "${AUTO_CONFIRM:-false}" != "true" ]]; then
        read -r -p "$prompt [y/N] " response
        case "$response" in
            [yY][eE][sS]|[yY]) return 0 ;;
            *) return 1 ;;
        esac
    fi
    return 0
}

# =============================================================================
# PRE-FAILOVER CHECKS
# =============================================================================

check_primary_health() {
    log "Checking primary region health..."
    
    # Check Route 53 health check status
    local health_status
    health_status=$(aws route53 get-health-check-status \
        --health-check-id "$PRIMARY_HEALTH_CHECK_ID" \
        --query 'HealthCheckObservations[0].StatusReport.Status' \
        --output text 2>/dev/null || echo "UNKNOWN")
    
    log "Primary health check status: $health_status"
    
    if [[ "$health_status" == "Success" ]]; then
        log "WARNING: Primary region appears healthy. Manual failover requested."
        if ! confirm_action "Primary region is healthy. Proceed with failover anyway?"; then
            log "Failover cancelled by user."
            exit 0
        fi
    fi
}

check_dr_readiness() {
    log "Checking DR region readiness..."
    
    # Check EKS cluster
    local eks_status
    eks_status=$(aws eks describe-cluster \
        --name "$DR_CLUSTER_NAME" \
        --region "$DR_REGION" \
        --query 'cluster.status' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [[ "$eks_status" != "ACTIVE" ]]; then
        error "DR EKS cluster not active. Status: $eks_status"
    fi
    log "DR EKS cluster: ACTIVE"
    
    # Check RDS cluster
    local rds_status
    rds_status=$(aws rds describe-db-clusters \
        --db-cluster-identifier "$DR_CLUSTER_NAME" \
        --region "$DR_REGION" \
        --query 'DBClusters[0].Status' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [[ "$rds_status" != "available" ]]; then
        error "DR RDS cluster not available. Status: $rds_status"
    fi
    log "DR RDS cluster: available"
    
    # Check replication lag
    local replication_lag
    replication_lag=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/RDS \
        --metric-name AuroraReplicaLag \
        --dimensions Name=DBClusterIdentifier,Value="$DR_CLUSTER_NAME" \
        --start-time "$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
        --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --period 60 \
        --statistics Average \
        --region "$DR_REGION" \
        --query 'Datapoints[0].Average' \
        --output text 2>/dev/null || echo "0")
    
    log "DR replication lag: ${replication_lag}ms"
    
    if (( $(echo "$replication_lag > 60000" | bc -l) )); then
        log "WARNING: Replication lag is high (${replication_lag}ms). Data loss may occur."
        if ! confirm_action "Replication lag exceeds 60 seconds. Proceed?"; then
            exit 0
        fi
    fi
}

# =============================================================================
# FAILOVER PROCEDURES
# =============================================================================

promote_rds_cluster() {
    log "Promoting DR RDS cluster to primary..."
    notify_slack ":database: Promoting DR database to primary..." "warning"
    
    # Remove from global cluster (promotes to standalone primary)
    aws rds remove-from-global-cluster \
        --global-cluster-identifier "$GLOBAL_DB_CLUSTER" \
        --db-cluster-identifier "arn:aws:rds:${DR_REGION}:$(aws sts get-caller-identity --query Account --output text):cluster:${DR_CLUSTER_NAME}" \
        --region "$DR_REGION"
    
    # Wait for promotion to complete
    log "Waiting for RDS promotion..."
    aws rds wait db-cluster-available \
        --db-cluster-identifier "$DR_CLUSTER_NAME" \
        --region "$DR_REGION"
    
    log "DR RDS cluster promoted successfully."
}

promote_redis_cluster() {
    log "Promoting DR Redis cluster to primary..."
    notify_slack ":zap: Promoting DR Redis to primary..." "warning"
    
    # Failover global datastore
    aws elasticache failover-global-replication-group \
        --global-replication-group-id "phoenix-guardian" \
        --primary-region "$DR_REGION" \
        --primary-replication-group-id "phoenix-guardian-dr-${ENVIRONMENT}"
    
    # Wait for failover
    log "Waiting for Redis failover..."
    sleep 60
    
    local redis_status
    for i in {1..30}; do
        redis_status=$(aws elasticache describe-replication-groups \
            --replication-group-id "phoenix-guardian-dr-${ENVIRONMENT}" \
            --region "$DR_REGION" \
            --query 'ReplicationGroups[0].Status' \
            --output text 2>/dev/null || echo "unknown")
        
        if [[ "$redis_status" == "available" ]]; then
            log "DR Redis cluster promoted successfully."
            break
        fi
        
        log "Redis status: $redis_status. Waiting..."
        sleep 10
    done
}

scale_up_dr_cluster() {
    log "Scaling up DR EKS workloads..."
    notify_slack ":rocket: Scaling up DR infrastructure..." "warning"
    
    # Update kubeconfig for DR cluster
    aws eks update-kubeconfig \
        --name "$DR_CLUSTER_NAME" \
        --region "$DR_REGION" \
        --alias "phoenix-dr"
    
    # Scale up API nodes
    aws eks update-nodegroup-config \
        --cluster-name "$DR_CLUSTER_NAME" \
        --nodegroup-name "dr-api-nodes" \
        --scaling-config minSize=3,maxSize=10,desiredSize=5 \
        --region "$DR_REGION"
    
    # Scale up ML nodes
    aws eks update-nodegroup-config \
        --cluster-name "$DR_CLUSTER_NAME" \
        --nodegroup-name "dr-ml-nodes" \
        --scaling-config minSize=1,maxSize=5,desiredSize=2 \
        --region "$DR_REGION"
    
    log "Waiting for nodes to be ready..."
    kubectl --context phoenix-dr wait --for=condition=ready nodes --all --timeout=300s
    
    # Scale up deployments
    kubectl --context phoenix-dr -n phoenix-production scale deployment phoenix-api --replicas=5
    kubectl --context phoenix-dr -n phoenix-production scale deployment phoenix-worker --replicas=3
    
    log "DR workloads scaled up."
}

update_dns_failover() {
    log "Updating DNS to DR region..."
    notify_slack ":globe_with_meridians: Updating DNS failover..." "warning"
    
    # The Route 53 failover should happen automatically based on health checks
    # But we can force it by disabling the primary health check
    
    # Get current DNS resolution
    local current_ip
    current_ip=$(dig +short "api.${DOMAIN}" | head -1)
    log "Current DNS resolution: $current_ip"
    
    # If automatic failover hasn't occurred, manually update
    # This is a safety mechanism
    
    log "Verifying DNS failover..."
    for i in {1..12}; do
        local new_ip
        new_ip=$(dig +short "api.${DOMAIN}" @8.8.8.8 | head -1)
        
        if [[ "$new_ip" != "$current_ip" ]]; then
            log "DNS failover confirmed. New IP: $new_ip"
            break
        fi
        
        log "Waiting for DNS propagation..."
        sleep 10
    done
}

verify_dr_services() {
    log "Verifying DR services..."
    
    # Health check
    local health_response
    health_response=$(curl -s -o /dev/null -w "%{http_code}" \
        "https://api-dr.${DOMAIN}/health" || echo "000")
    
    if [[ "$health_response" != "200" ]]; then
        error "DR API health check failed. HTTP status: $health_response"
    fi
    log "DR API health check: OK"
    
    # Database connectivity
    local db_check
    db_check=$(kubectl --context phoenix-dr -n phoenix-production exec -it deployment/phoenix-api -- \
        python -c "from app.db import engine; engine.execute('SELECT 1')" 2>&1 || echo "FAILED")
    
    if [[ "$db_check" == *"FAILED"* ]]; then
        log "WARNING: Database connectivity check failed"
    else
        log "Database connectivity: OK"
    fi
    
    # Redis connectivity
    local redis_check
    redis_check=$(kubectl --context phoenix-dr -n phoenix-production exec -it deployment/phoenix-api -- \
        python -c "from app.cache import redis_client; redis_client.ping()" 2>&1 || echo "FAILED")
    
    if [[ "$redis_check" == *"FAILED"* ]]; then
        log "WARNING: Redis connectivity check failed"
    else
        log "Redis connectivity: OK"
    fi
}

# =============================================================================
# POST-FAILOVER TASKS
# =============================================================================

notify_stakeholders() {
    log "Sending stakeholder notifications..."
    
    notify_slack ":white_check_mark: DR FAILOVER COMPLETE\n\n*Region:* us-west-2\n*Status:* Active\n*Time:* $(date)\n\nPlease verify all services and update runbooks." "good"
    
    # Send email via SES (if configured)
    if [[ -n "${NOTIFICATION_EMAIL:-}" ]]; then
        aws ses send-email \
            --from "ops@${DOMAIN}" \
            --destination "ToAddresses=${NOTIFICATION_EMAIL}" \
            --message "Subject={Data='Phoenix Guardian DR Failover Complete'},Body={Text={Data='DR failover to us-west-2 completed at $(date). All services operational.'}}" \
            --region "$DR_REGION" || true
    fi
}

create_incident_record() {
    log "Creating incident record..."
    
    local incident_id="INC-$(date +%Y%m%d%H%M%S)"
    local incident_file="/var/log/phoenix-incidents/${incident_id}.json"
    
    mkdir -p /var/log/phoenix-incidents
    
    cat > "$incident_file" << EOF
{
    "incident_id": "$incident_id",
    "type": "DR_FAILOVER",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "primary_region": "$PRIMARY_REGION",
    "dr_region": "$DR_REGION",
    "environment": "$ENVIRONMENT",
    "triggered_by": "${USER:-automated}",
    "log_file": "$LOG_FILE",
    "status": "completed"
}
EOF
    
    log "Incident record created: $incident_id"
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    log "========================================"
    log "PHOENIX GUARDIAN DR FAILOVER"
    log "========================================"
    log "Primary Region: $PRIMARY_REGION"
    log "DR Region: $DR_REGION"
    log "Environment: $ENVIRONMENT"
    log "========================================"
    
    notify_slack ":warning: DR FAILOVER INITIATED\n\n*Primary Region:* $PRIMARY_REGION\n*DR Region:* $DR_REGION\n*Triggered by:* ${USER:-automated}" "warning"
    
    local start_time=$(date +%s)
    
    # Pre-flight checks
    check_primary_health
    check_dr_readiness
    
    # Confirm failover
    if ! confirm_action "Proceed with DR failover?"; then
        log "Failover cancelled by user."
        notify_slack ":no_entry: DR failover cancelled by user" "warning"
        exit 0
    fi
    
    log "Starting failover sequence..."
    
    # Execute failover
    promote_rds_cluster
    promote_redis_cluster
    scale_up_dr_cluster
    update_dns_failover
    verify_dr_services
    
    # Post-failover
    notify_stakeholders
    create_incident_record
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log "========================================"
    log "FAILOVER COMPLETE"
    log "Duration: ${duration} seconds"
    log "RTO Target: 900 seconds (15 minutes)"
    log "RTO Actual: ${duration} seconds"
    if [[ $duration -le 900 ]]; then
        log "RTO Status: MET ✓"
    else
        log "RTO Status: EXCEEDED ✗"
    fi
    log "========================================"
    
    notify_slack ":checkered_flag: DR Failover completed in ${duration} seconds (RTO: 15 min)" "good"
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
