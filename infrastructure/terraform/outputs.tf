# =============================================================================
# PHOENIX GUARDIAN - TERRAFORM OUTPUTS
# =============================================================================

# =============================================================================
# VPC
# =============================================================================

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = module.vpc.vpc_cidr_block
}

output "private_subnets" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnets
}

output "database_subnets" {
  description = "Database subnet IDs"
  value       = module.vpc.database_subnets
}

# =============================================================================
# EKS
# =============================================================================

output "eks_cluster_id" {
  description = "EKS cluster ID"
  value       = module.eks.cluster_name
}

output "eks_cluster_arn" {
  description = "EKS cluster ARN"
  value       = module.eks.cluster_arn
}

output "eks_cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "eks_node_security_group_id" {
  description = "Security group ID attached to the EKS nodes"
  value       = module.eks.node_security_group_id
}

output "eks_node_groups" {
  description = "EKS managed node groups"
  value       = keys(module.eks.eks_managed_node_groups)
}

output "eks_oidc_provider_arn" {
  description = "ARN of the OIDC Provider for IRSA"
  value       = module.eks.oidc_provider_arn
}

output "cluster_autoscaler_role_arn" {
  description = "IAM role ARN for Cluster Autoscaler"
  value       = module.cluster_autoscaler_irsa.iam_role_arn
}

output "load_balancer_controller_role_arn" {
  description = "IAM role ARN for AWS Load Balancer Controller"
  value       = module.load_balancer_controller_irsa.iam_role_arn
}

# =============================================================================
# RDS
# =============================================================================

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "rds_address" {
  description = "RDS PostgreSQL address (hostname)"
  value       = aws_db_instance.postgres.address
}

output "rds_port" {
  description = "RDS PostgreSQL port"
  value       = aws_db_instance.postgres.port
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.postgres.db_name
}

output "rds_multi_az" {
  description = "RDS Multi-AZ enabled"
  value       = aws_db_instance.postgres.multi_az
}

output "rds_storage_encrypted" {
  description = "RDS storage encryption enabled"
  value       = aws_db_instance.postgres.storage_encrypted
}

output "rds_replica_endpoint" {
  description = "RDS read replica endpoint"
  value       = var.create_read_replica ? aws_db_instance.postgres_replica[0].endpoint : null
}

# =============================================================================
# ELASTICACHE REDIS
# =============================================================================

output "redis_endpoint" {
  description = "Redis primary endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_reader_endpoint" {
  description = "Redis reader endpoint"
  value       = aws_elasticache_replication_group.redis.reader_endpoint_address
}

output "redis_port" {
  description = "Redis port"
  value       = aws_elasticache_replication_group.redis.port
}

output "redis_at_rest_encryption_enabled" {
  description = "Redis at-rest encryption enabled"
  value       = aws_elasticache_replication_group.redis.at_rest_encryption_enabled
}

output "redis_transit_encryption_enabled" {
  description = "Redis in-transit encryption enabled"
  value       = aws_elasticache_replication_group.redis.transit_encryption_enabled
}

# =============================================================================
# SECRETS
# =============================================================================

output "db_credentials_secret_arn" {
  description = "ARN of the Secrets Manager secret for DB credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "redis_credentials_secret_arn" {
  description = "ARN of the Secrets Manager secret for Redis credentials"
  value       = aws_secretsmanager_secret.redis_credentials.arn
}

# =============================================================================
# S3
# =============================================================================

output "data_bucket_name" {
  description = "S3 bucket for PHI data"
  value       = aws_s3_bucket.phoenix_data.bucket
}

output "data_bucket_arn" {
  description = "S3 bucket ARN for PHI data"
  value       = aws_s3_bucket.phoenix_data.arn
}

output "ml_models_bucket_name" {
  description = "S3 bucket for ML models"
  value       = aws_s3_bucket.ml_models.bucket
}

output "access_logs_bucket_name" {
  description = "S3 bucket for access logs"
  value       = aws_s3_bucket.access_logs.bucket
}

# =============================================================================
# ECR
# =============================================================================

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.phoenix.repository_url
}

output "ecr_registry" {
  description = "ECR registry URL"
  value       = split("/", aws_ecr_repository.phoenix.repository_url)[0]
}

# =============================================================================
# KMS
# =============================================================================

output "eks_kms_key_arn" {
  description = "KMS key ARN for EKS secrets"
  value       = aws_kms_key.eks.arn
}

output "rds_kms_key_arn" {
  description = "KMS key ARN for RDS encryption"
  value       = aws_kms_key.rds.arn
}

output "redis_kms_key_arn" {
  description = "KMS key ARN for Redis encryption"
  value       = aws_kms_key.redis.arn
}

output "s3_kms_key_arn" {
  description = "KMS key ARN for S3 encryption"
  value       = aws_kms_key.s3.arn
}

# =============================================================================
# IAM
# =============================================================================

output "phoenix_api_role_arn" {
  description = "IAM role ARN for Phoenix API service account"
  value       = module.phoenix_api_irsa.iam_role_arn
}

output "phoenix_ml_role_arn" {
  description = "IAM role ARN for Phoenix ML service account"
  value       = module.phoenix_ml_irsa.iam_role_arn
}

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions"
  value       = var.enable_github_actions_oidc ? aws_iam_role.github_actions[0].arn : null
}

# =============================================================================
# WAF
# =============================================================================

output "waf_web_acl_arn" {
  description = "WAF Web ACL ARN"
  value       = aws_wafv2_web_acl.phoenix.arn
}

# =============================================================================
# KUBECTL CONFIGURATION COMMAND
# =============================================================================

output "configure_kubectl" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.aws_region}"
}
