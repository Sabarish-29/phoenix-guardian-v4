# Phoenix Guardian - Multi-Region Disaster Recovery
# Sprint 67-68: Multi-Region DR Infrastructure
#
# Secondary region: us-west-2 (Oregon)
# Primary region: us-east-1 (Virginia)
# RTO: 15 minutes | RPO: 5 minutes

terraform {
  required_version = ">= 1.6"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket         = "phoenix-guardian-terraform-state"
    key            = "dr/us-west-2/terraform.tfstate"
    region         = "us-east-1"  # State always in primary
    encrypt        = true
    dynamodb_table = "phoenix-terraform-locks"
  }
}

# =============================================================================
# PROVIDERS - Multi-Region Configuration
# =============================================================================

provider "aws" {
  region = "us-west-2"
  alias  = "dr"
  
  default_tags {
    tags = {
      Project             = "PhoenixGuardian"
      Environment         = var.environment
      ManagedBy           = "Terraform"
      DisasterRecovery    = "secondary"
      PrimaryRegion       = "us-east-1"
    }
  }
}

provider "aws" {
  region = "us-east-1"
  alias  = "primary"
}

# =============================================================================
# DATA SOURCES - Primary Region Resources
# =============================================================================

data "aws_kms_key" "primary_key" {
  provider = aws.primary
  key_id   = "alias/phoenix-guardian-${var.environment}"
}

data "aws_rds_cluster" "primary_db" {
  provider           = aws.primary
  cluster_identifier = "phoenix-guardian-${var.environment}"
}

data "aws_elasticache_replication_group" "primary_redis" {
  provider             = aws.primary
  replication_group_id = "phoenix-guardian-${var.environment}"
}

# =============================================================================
# DR VPC - Secondary Region
# =============================================================================

module "dr_vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
  
  providers = {
    aws = aws.dr
  }
  
  name = "phoenix-guardian-dr-${var.environment}"
  cidr = var.dr_vpc_cidr  # Different CIDR for peering
  
  azs             = ["us-west-2a", "us-west-2b", "us-west-2c"]
  private_subnets = var.dr_private_subnets
  public_subnets  = var.dr_public_subnets
  
  enable_nat_gateway     = true
  single_nat_gateway     = false  # HA NAT
  enable_dns_hostnames   = true
  enable_dns_support     = true
  
  # VPC Flow Logs
  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true
  flow_log_max_aggregation_interval    = 60
  
  tags = {
    Region = "us-west-2"
    Role   = "disaster-recovery"
  }
}

# =============================================================================
# VPC PEERING - Cross-Region Connectivity
# =============================================================================

resource "aws_vpc_peering_connection" "primary_to_dr" {
  provider    = aws.primary
  vpc_id      = data.aws_vpc.primary.id
  peer_vpc_id = module.dr_vpc.vpc_id
  peer_region = "us-west-2"
  
  tags = {
    Name = "phoenix-primary-to-dr"
  }
}

resource "aws_vpc_peering_connection_accepter" "dr_accepter" {
  provider                  = aws.dr
  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_dr.id
  auto_accept               = true
  
  tags = {
    Name = "phoenix-dr-accepter"
  }
}

data "aws_vpc" "primary" {
  provider = aws.primary
  
  filter {
    name   = "tag:Name"
    values = ["phoenix-guardian-${var.environment}"]
  }
}

# =============================================================================
# KMS - DR Region Key (for encryption)
# =============================================================================

resource "aws_kms_key" "dr_key" {
  provider                = aws.dr
  description             = "Phoenix Guardian DR encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  multi_region            = true
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow RDS Access"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey*"
        ]
        Resource = "*"
      }
    ]
  })
  
  tags = {
    Name = "phoenix-guardian-dr-key"
  }
}

resource "aws_kms_alias" "dr_key_alias" {
  provider      = aws.dr
  name          = "alias/phoenix-guardian-${var.environment}"
  target_key_id = aws_kms_key.dr_key.key_id
}

data "aws_caller_identity" "current" {}

# =============================================================================
# RDS - Global Database (Cross-Region Replication)
# =============================================================================

resource "aws_rds_global_cluster" "phoenix_global" {
  provider                  = aws.primary
  global_cluster_identifier = "phoenix-guardian-global-${var.environment}"
  source_db_cluster_identifier = data.aws_rds_cluster.primary_db.arn
  force_destroy             = false
  deletion_protection       = true
}

resource "aws_rds_cluster" "dr_cluster" {
  provider              = aws.dr
  cluster_identifier    = "phoenix-guardian-dr-${var.environment}"
  engine                = "aurora-postgresql"
  engine_version        = "15.4"
  global_cluster_identifier = aws_rds_global_cluster.phoenix_global.id
  
  db_subnet_group_name   = aws_db_subnet_group.dr.name
  vpc_security_group_ids = [aws_security_group.dr_rds.id]
  
  kms_key_id            = aws_kms_key.dr_key.arn
  storage_encrypted     = true
  
  # DR cluster settings
  enable_global_write_forwarding = true
  
  # Backup
  backup_retention_period = 35
  preferred_backup_window = "03:00-04:00"
  
  # Enhanced monitoring
  enabled_cloudwatch_logs_exports = ["postgresql"]
  
  tags = {
    Name = "phoenix-guardian-dr-cluster"
    Role = "read-replica"
  }
  
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_rds_cluster_instance" "dr_instances" {
  provider           = aws.dr
  count              = var.dr_db_instance_count
  
  identifier         = "phoenix-guardian-dr-${count.index}"
  cluster_identifier = aws_rds_cluster.dr_cluster.id
  instance_class     = var.dr_db_instance_class
  engine             = "aurora-postgresql"
  
  performance_insights_enabled    = true
  performance_insights_kms_key_id = aws_kms_key.dr_key.arn
  
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn
  
  tags = {
    Name = "phoenix-guardian-dr-instance-${count.index}"
  }
}

resource "aws_db_subnet_group" "dr" {
  provider   = aws.dr
  name       = "phoenix-guardian-dr-${var.environment}"
  subnet_ids = module.dr_vpc.private_subnets
  
  tags = {
    Name = "phoenix-guardian-dr-subnet-group"
  }
}

resource "aws_security_group" "dr_rds" {
  provider    = aws.dr
  name_prefix = "phoenix-dr-rds-"
  description = "DR RDS security group"
  vpc_id      = module.dr_vpc.vpc_id
  
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = module.dr_vpc.private_subnets_cidr_blocks
  }
  
  # Allow from primary region (for replication)
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.primary.cidr_block]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = {
    Name = "phoenix-dr-rds-sg"
  }
}

resource "aws_iam_role" "rds_monitoring" {
  provider = aws.dr
  name     = "phoenix-dr-rds-monitoring"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "monitoring.rds.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  provider   = aws.dr
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# =============================================================================
# ELASTICACHE - Global Datastore
# =============================================================================

resource "aws_elasticache_global_replication_group" "phoenix_global" {
  provider                           = aws.primary
  global_replication_group_id_suffix = "phoenix-guardian"
  primary_replication_group_id       = data.aws_elasticache_replication_group.primary_redis.id
  
  global_replication_group_description = "Phoenix Guardian Global Redis"
}

resource "aws_elasticache_replication_group" "dr_redis" {
  provider                   = aws.dr
  replication_group_id       = "phoenix-guardian-dr-${var.environment}"
  description                = "Phoenix Guardian DR Redis cluster"
  global_replication_group_id = aws_elasticache_global_replication_group.phoenix_global.global_replication_group_id
  
  # Node configuration (inherited from global)
  automatic_failover_enabled = true
  multi_az_enabled           = true
  
  subnet_group_name  = aws_elasticache_subnet_group.dr.name
  security_group_ids = [aws_security_group.dr_redis.id]
  
  # Snapshots
  snapshot_retention_limit = 7
  snapshot_window          = "05:00-06:00"
  
  tags = {
    Name = "phoenix-guardian-dr-redis"
    Role = "read-replica"
  }
}

resource "aws_elasticache_subnet_group" "dr" {
  provider   = aws.dr
  name       = "phoenix-guardian-dr-${var.environment}"
  subnet_ids = module.dr_vpc.private_subnets
  
  tags = {
    Name = "phoenix-guardian-dr-redis-subnet-group"
  }
}

resource "aws_security_group" "dr_redis" {
  provider    = aws.dr
  name_prefix = "phoenix-dr-redis-"
  description = "DR Redis security group"
  vpc_id      = module.dr_vpc.vpc_id
  
  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = module.dr_vpc.private_subnets_cidr_blocks
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = {
    Name = "phoenix-dr-redis-sg"
  }
}

# =============================================================================
# EKS - DR Cluster
# =============================================================================

module "dr_eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"
  
  providers = {
    aws = aws.dr
  }
  
  cluster_name    = "phoenix-guardian-dr-${var.environment}"
  cluster_version = "1.28"
  
  vpc_id     = module.dr_vpc.vpc_id
  subnet_ids = module.dr_vpc.private_subnets
  
  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true
  
  # Encryption
  cluster_encryption_config = {
    provider_key_arn = aws_kms_key.dr_key.arn
    resources        = ["secrets"]
  }
  
  # Add-ons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent = true
    }
  }
  
  # Node groups - scaled down for DR (hot standby)
  eks_managed_node_groups = {
    dr_system = {
      name           = "dr-system-nodes"
      instance_types = ["m6i.large"]  # Smaller than primary
      
      min_size     = 1
      max_size     = 3
      desired_size = 2
      
      labels = {
        role = "system"
        tier = "dr"
      }
      
      taints = []
    }
    
    dr_api = {
      name           = "dr-api-nodes"
      instance_types = ["m6i.xlarge"]
      
      min_size     = 1
      max_size     = 5
      desired_size = 2  # Scaled down for DR
      
      labels = {
        role = "api"
        tier = "dr"
      }
    }
    
    dr_ml = {
      name           = "dr-ml-nodes"
      instance_types = ["g5.xlarge"]
      ami_type       = "AL2_x86_64_GPU"
      
      min_size     = 0  # Scale to 0 when not active
      max_size     = 3
      desired_size = 0
      
      labels = {
        role         = "ml"
        tier         = "dr"
        "nvidia.com/gpu" = "true"
      }
      
      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
  }
  
  # IRSA
  enable_irsa = true
  
  tags = {
    Name = "phoenix-guardian-dr-eks"
    Role = "disaster-recovery"
  }
}

# =============================================================================
# S3 - Cross-Region Replication
# =============================================================================

resource "aws_s3_bucket" "dr_data" {
  provider = aws.dr
  bucket   = "phoenix-guardian-dr-data-${var.environment}-${data.aws_caller_identity.current.account_id}"
  
  tags = {
    Name = "phoenix-guardian-dr-data"
    Role = "disaster-recovery"
  }
}

resource "aws_s3_bucket_versioning" "dr_data" {
  provider = aws.dr
  bucket   = aws_s3_bucket.dr_data.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "dr_data" {
  provider = aws.dr
  bucket   = aws_s3_bucket.dr_data.id
  
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.dr_key.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# Cross-region replication from primary
resource "aws_s3_bucket_replication_configuration" "primary_to_dr" {
  provider = aws.primary
  
  # Assumes primary bucket exists
  bucket = "phoenix-guardian-data-${var.environment}-${data.aws_caller_identity.current.account_id}"
  role   = aws_iam_role.s3_replication.arn
  
  rule {
    id     = "replicate-all"
    status = "Enabled"
    
    filter {
      prefix = ""
    }
    
    destination {
      bucket        = aws_s3_bucket.dr_data.arn
      storage_class = "STANDARD"
      
      encryption_configuration {
        replica_kms_key_id = aws_kms_key.dr_key.arn
      }
      
      metrics {
        status = "Enabled"
        event_threshold {
          minutes = 15
        }
      }
      
      replication_time {
        status = "Enabled"
        time {
          minutes = 15
        }
      }
    }
    
    delete_marker_replication {
      status = "Enabled"
    }
  }
}

resource "aws_iam_role" "s3_replication" {
  provider = aws.primary
  name     = "phoenix-s3-replication-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "s3.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "s3_replication" {
  provider = aws.primary
  name     = "s3-replication-policy"
  role     = aws_iam_role.s3_replication.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:s3:::phoenix-guardian-data-${var.environment}-${data.aws_caller_identity.current.account_id}"
      },
      {
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:s3:::phoenix-guardian-data-${var.environment}-${data.aws_caller_identity.current.account_id}/*"
      },
      {
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Effect   = "Allow"
        Resource = "${aws_s3_bucket.dr_data.arn}/*"
      },
      {
        Action = [
          "kms:Decrypt"
        ]
        Effect   = "Allow"
        Resource = data.aws_kms_key.primary_key.arn
      },
      {
        Action = [
          "kms:Encrypt"
        ]
        Effect   = "Allow"
        Resource = aws_kms_key.dr_key.arn
      }
    ]
  })
}

# =============================================================================
# ROUTE 53 - Health Checks and Failover
# =============================================================================

resource "aws_route53_health_check" "primary" {
  provider          = aws.primary
  fqdn              = var.primary_api_endpoint
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 10
  
  regions = ["us-east-1", "us-west-2", "eu-west-1"]
  
  tags = {
    Name = "phoenix-primary-health-check"
  }
}

resource "aws_route53_health_check" "dr" {
  provider          = aws.dr
  fqdn              = var.dr_api_endpoint
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 10
  
  regions = ["us-east-1", "us-west-2", "eu-west-1"]
  
  tags = {
    Name = "phoenix-dr-health-check"
  }
}

resource "aws_route53_record" "failover_primary" {
  provider = aws.primary
  zone_id  = var.route53_zone_id
  name     = "api.${var.domain}"
  type     = "A"
  
  failover_routing_policy {
    type = "PRIMARY"
  }
  
  set_identifier  = "primary"
  health_check_id = aws_route53_health_check.primary.id
  
  alias {
    name                   = var.primary_alb_dns_name
    zone_id                = var.primary_alb_zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "failover_dr" {
  provider = aws.dr
  zone_id  = var.route53_zone_id
  name     = "api.${var.domain}"
  type     = "A"
  
  failover_routing_policy {
    type = "SECONDARY"
  }
  
  set_identifier = "dr"
  
  alias {
    name                   = module.dr_alb.dns_name
    zone_id                = module.dr_alb.zone_id
    evaluate_target_health = true
  }
}

# =============================================================================
# DR ALB - Application Load Balancer
# =============================================================================

module "dr_alb" {
  source  = "terraform-aws-modules/alb/aws"
  version = "~> 8.0"
  
  providers = {
    aws = aws.dr
  }
  
  name               = "phoenix-guardian-dr-${var.environment}"
  load_balancer_type = "application"
  
  vpc_id  = module.dr_vpc.vpc_id
  subnets = module.dr_vpc.public_subnets
  
  security_group_rules = {
    ingress_https = {
      type        = "ingress"
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
    egress_all = {
      type        = "egress"
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }
  
  https_listeners = [{
    port               = 443
    protocol           = "HTTPS"
    certificate_arn    = var.dr_certificate_arn
    ssl_policy         = "ELBSecurityPolicy-TLS13-1-2-2021-06"
    target_group_index = 0
  }]
  
  target_groups = [{
    name             = "phoenix-api-dr"
    backend_protocol = "HTTP"
    backend_port     = 8000
    target_type      = "ip"
    
    health_check = {
      enabled             = true
      interval            = 15
      path                = "/health"
      port                = "traffic-port"
      healthy_threshold   = 2
      unhealthy_threshold = 3
      timeout             = 5
      protocol            = "HTTP"
      matcher             = "200"
    }
  }]
  
  tags = {
    Name = "phoenix-guardian-dr-alb"
  }
}

# =============================================================================
# CLOUDWATCH - DR Monitoring
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "dr_replication_lag" {
  provider            = aws.dr
  alarm_name          = "phoenix-dr-replication-lag"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "AuroraReplicaLag"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 60000  # 60 seconds
  alarm_description   = "DR database replication lag exceeds 60 seconds"
  
  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.dr_cluster.cluster_identifier
  }
  
  alarm_actions = [var.sns_alarm_topic_arn]
  ok_actions    = [var.sns_alarm_topic_arn]
  
  tags = {
    Name = "phoenix-dr-replication-lag-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "dr_s3_replication_latency" {
  provider            = aws.primary
  alarm_name          = "phoenix-s3-replication-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ReplicationLatency"
  namespace           = "AWS/S3"
  period              = 300
  statistic           = "Average"
  threshold           = 900  # 15 minutes
  alarm_description   = "S3 replication latency exceeds 15 minutes"
  
  dimensions = {
    SourceBucket      = "phoenix-guardian-data-${var.environment}-${data.aws_caller_identity.current.account_id}"
    DestinationBucket = aws_s3_bucket.dr_data.id
    RuleId            = "replicate-all"
  }
  
  alarm_actions = [var.sns_alarm_topic_arn]
  
  tags = {
    Name = "phoenix-s3-replication-latency-alarm"
  }
}

# =============================================================================
# VARIABLES
# =============================================================================

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "dr_vpc_cidr" {
  description = "CIDR for DR VPC"
  type        = string
  default     = "10.1.0.0/16"  # Different from primary 10.0.0.0/16
}

variable "dr_private_subnets" {
  description = "Private subnet CIDRs for DR"
  type        = list(string)
  default     = ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24"]
}

variable "dr_public_subnets" {
  description = "Public subnet CIDRs for DR"
  type        = list(string)
  default     = ["10.1.101.0/24", "10.1.102.0/24", "10.1.103.0/24"]
}

variable "dr_db_instance_count" {
  description = "Number of DB instances in DR"
  type        = number
  default     = 2
}

variable "dr_db_instance_class" {
  description = "Instance class for DR database"
  type        = string
  default     = "db.r6g.large"  # Smaller than primary
}

variable "primary_api_endpoint" {
  description = "Primary region API endpoint"
  type        = string
}

variable "dr_api_endpoint" {
  description = "DR region API endpoint"
  type        = string
}

variable "route53_zone_id" {
  description = "Route 53 hosted zone ID"
  type        = string
}

variable "domain" {
  description = "Domain name"
  type        = string
}

variable "primary_alb_dns_name" {
  description = "Primary ALB DNS name"
  type        = string
}

variable "primary_alb_zone_id" {
  description = "Primary ALB zone ID"
  type        = string
}

variable "dr_certificate_arn" {
  description = "ACM certificate ARN for DR region"
  type        = string
}

variable "sns_alarm_topic_arn" {
  description = "SNS topic for alarms"
  type        = string
}

# =============================================================================
# OUTPUTS
# =============================================================================

output "dr_vpc_id" {
  description = "DR VPC ID"
  value       = module.dr_vpc.vpc_id
}

output "dr_eks_cluster_endpoint" {
  description = "DR EKS cluster endpoint"
  value       = module.dr_eks.cluster_endpoint
}

output "dr_rds_cluster_endpoint" {
  description = "DR RDS cluster endpoint"
  value       = aws_rds_cluster.dr_cluster.endpoint
}

output "dr_redis_endpoint" {
  description = "DR Redis endpoint"
  value       = aws_elasticache_replication_group.dr_redis.primary_endpoint_address
}

output "dr_alb_dns_name" {
  description = "DR ALB DNS name"
  value       = module.dr_alb.lb_dns_name
}

output "dr_s3_bucket" {
  description = "DR S3 bucket name"
  value       = aws_s3_bucket.dr_data.id
}

output "replication_status" {
  description = "Replication configuration status"
  value = {
    rds_global_cluster     = aws_rds_global_cluster.phoenix_global.id
    redis_global_datastore = aws_elasticache_global_replication_group.phoenix_global.id
    s3_replication         = "enabled"
    route53_failover       = "configured"
  }
}
