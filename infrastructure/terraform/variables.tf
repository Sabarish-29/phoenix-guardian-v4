# =============================================================================
# PHOENIX GUARDIAN - TERRAFORM VARIABLES
# =============================================================================

# =============================================================================
# GENERAL
# =============================================================================

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (staging, production)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be 'staging' or 'production'."
  }
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access EKS API endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"]  # Restrict in production!
}

# =============================================================================
# VPC
# =============================================================================

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# =============================================================================
# RDS
# =============================================================================

variable "db_username" {
  description = "Master username for RDS PostgreSQL"
  type        = string
  default     = "phoenix_admin"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.r6g.xlarge"  # 4 vCPU, 32 GB RAM
}

variable "db_allocated_storage" {
  description = "Allocated storage for RDS in GB"
  type        = number
  default     = 500
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for RDS autoscaling in GB"
  type        = number
  default     = 2000
}

variable "db_iops" {
  description = "Provisioned IOPS for RDS storage"
  type        = number
  default     = 3000
}

variable "db_storage_throughput" {
  description = "Storage throughput in MiBps for gp3"
  type        = number
  default     = 125
}

variable "create_read_replica" {
  description = "Create a read replica for RDS"
  type        = bool
  default     = true
}

variable "db_replica_instance_class" {
  description = "Instance class for RDS read replica"
  type        = string
  default     = "db.r6g.large"
}

# =============================================================================
# ELASTICACHE REDIS
# =============================================================================

variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.r6g.large"  # 2 vCPU, 13 GB RAM
}

variable "redis_num_cache_clusters" {
  description = "Number of Redis cache clusters (nodes)"
  type        = number
  default     = 3

  validation {
    condition     = var.redis_num_cache_clusters >= 2
    error_message = "Must have at least 2 cache clusters for high availability."
  }
}

# =============================================================================
# GITHUB ACTIONS
# =============================================================================

variable "enable_github_actions_oidc" {
  description = "Enable GitHub Actions OIDC provider for CI/CD"
  type        = bool
  default     = true
}

variable "github_org" {
  description = "GitHub organization name"
  type        = string
  default     = "yourorg"
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "phoenix-guardian"
}
