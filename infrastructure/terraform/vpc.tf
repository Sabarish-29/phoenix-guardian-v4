# =============================================================================
# PHOENIX GUARDIAN - VPC CONFIGURATION
# =============================================================================
# HIPAA-compliant VPC with 3 AZs, public/private/database subnets
# Flow logs enabled for audit trail
# =============================================================================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = local.name
  cidr = var.vpc_cidr

  azs              = local.azs
  private_subnets  = [for k, v in local.azs : cidrsubnet(var.vpc_cidr, 4, k)]
  public_subnets   = [for k, v in local.azs : cidrsubnet(var.vpc_cidr, 4, k + 4)]
  database_subnets = [for k, v in local.azs : cidrsubnet(var.vpc_cidr, 4, k + 8)]

  # NAT Gateway for private subnets (HA with one per AZ)
  enable_nat_gateway     = true
  single_nat_gateway     = false
  one_nat_gateway_per_az = true

  # DNS settings for private endpoints
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Database subnet group
  create_database_subnet_group       = true
  create_database_subnet_route_table = true
  database_subnet_group_name         = "${local.name}-db"

  # VPC Flow Logs (HIPAA requirement - audit trail)
  enable_flow_log                      = true
  create_flow_log_cloudwatch_iam_role  = true
  create_flow_log_cloudwatch_log_group = true
  flow_log_max_aggregation_interval    = 60
  flow_log_cloudwatch_log_group_retention_in_days = 365

  # Tags for Kubernetes
  public_subnet_tags = {
    "kubernetes.io/role/elb"                      = 1
    "kubernetes.io/cluster/${local.name}"         = "shared"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"             = 1
    "kubernetes.io/cluster/${local.name}"         = "shared"
  }

  tags = local.tags
}

# =============================================================================
# VPC ENDPOINTS - Private connectivity to AWS services
# =============================================================================

module "vpc_endpoints" {
  source  = "terraform-aws-modules/vpc/aws//modules/vpc-endpoints"
  version = "~> 5.0"

  vpc_id = module.vpc.vpc_id

  endpoints = {
    # S3 Gateway endpoint (free)
    s3 = {
      service         = "s3"
      service_type    = "Gateway"
      route_table_ids = module.vpc.private_route_table_ids
      tags            = { Name = "${local.name}-s3-endpoint" }
    }

    # DynamoDB Gateway endpoint (free)
    dynamodb = {
      service         = "dynamodb"
      service_type    = "Gateway"
      route_table_ids = module.vpc.private_route_table_ids
      tags            = { Name = "${local.name}-dynamodb-endpoint" }
    }

    # ECR API (for pulling Docker images)
    ecr_api = {
      service             = "ecr.api"
      private_dns_enabled = true
      subnet_ids          = module.vpc.private_subnets
      security_group_ids  = [aws_security_group.vpc_endpoints.id]
      tags                = { Name = "${local.name}-ecr-api-endpoint" }
    }

    # ECR DKR (for Docker registry)
    ecr_dkr = {
      service             = "ecr.dkr"
      private_dns_enabled = true
      subnet_ids          = module.vpc.private_subnets
      security_group_ids  = [aws_security_group.vpc_endpoints.id]
      tags                = { Name = "${local.name}-ecr-dkr-endpoint" }
    }

    # CloudWatch Logs
    logs = {
      service             = "logs"
      private_dns_enabled = true
      subnet_ids          = module.vpc.private_subnets
      security_group_ids  = [aws_security_group.vpc_endpoints.id]
      tags                = { Name = "${local.name}-logs-endpoint" }
    }

    # Secrets Manager
    secretsmanager = {
      service             = "secretsmanager"
      private_dns_enabled = true
      subnet_ids          = module.vpc.private_subnets
      security_group_ids  = [aws_security_group.vpc_endpoints.id]
      tags                = { Name = "${local.name}-sm-endpoint" }
    }

    # SSM for Parameter Store
    ssm = {
      service             = "ssm"
      private_dns_enabled = true
      subnet_ids          = module.vpc.private_subnets
      security_group_ids  = [aws_security_group.vpc_endpoints.id]
      tags                = { Name = "${local.name}-ssm-endpoint" }
    }

    # STS for IAM roles
    sts = {
      service             = "sts"
      private_dns_enabled = true
      subnet_ids          = module.vpc.private_subnets
      security_group_ids  = [aws_security_group.vpc_endpoints.id]
      tags                = { Name = "${local.name}-sts-endpoint" }
    }

    # KMS for encryption
    kms = {
      service             = "kms"
      private_dns_enabled = true
      subnet_ids          = module.vpc.private_subnets
      security_group_ids  = [aws_security_group.vpc_endpoints.id]
      tags                = { Name = "${local.name}-kms-endpoint" }
    }
  }

  tags = local.tags
}

# Security group for VPC endpoints
resource "aws_security_group" "vpc_endpoints" {
  name        = "${local.name}-vpc-endpoints"
  description = "Security group for VPC endpoints"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "HTTPS from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = merge(local.tags, {
    Name = "${local.name}-vpc-endpoints-sg"
  })
}
