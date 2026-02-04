# =============================================================================
# PHOENIX GUARDIAN - SECURITY RESOURCES
# =============================================================================
# KMS keys, S3 buckets, WAF, and security configurations
# HIPAA-compliant with encryption and audit logging
# =============================================================================

# =============================================================================
# KMS KEYS
# =============================================================================

# KMS Key for EKS cluster secrets
resource "aws_kms_key" "eks" {
  description             = "KMS key for Phoenix Guardian EKS secrets encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  
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
        Sid    = "Allow EKS to use the key"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.tags, {
    Name    = "${local.name}-eks-kms"
    Purpose = "EKS secrets encryption"
  })
}

resource "aws_kms_alias" "eks" {
  name          = "alias/${local.name}-eks"
  target_key_id = aws_kms_key.eks.key_id
}

# KMS Key for RDS encryption
resource "aws_kms_key" "rds" {
  description             = "KMS key for Phoenix Guardian RDS encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(local.tags, {
    Name    = "${local.name}-rds-kms"
    Purpose = "RDS encryption"
    HIPAA   = "true"
  })
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${local.name}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

# KMS Key for Redis encryption
resource "aws_kms_key" "redis" {
  description             = "KMS key for Phoenix Guardian Redis encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(local.tags, {
    Name    = "${local.name}-redis-kms"
    Purpose = "ElastiCache encryption"
    HIPAA   = "true"
  })
}

resource "aws_kms_alias" "redis" {
  name          = "alias/${local.name}-redis"
  target_key_id = aws_kms_key.redis.key_id
}

# KMS Key for S3 encryption
resource "aws_kms_key" "s3" {
  description             = "KMS key for Phoenix Guardian S3 encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(local.tags, {
    Name    = "${local.name}-s3-kms"
    Purpose = "S3 encryption"
    HIPAA   = "true"
  })
}

resource "aws_kms_alias" "s3" {
  name          = "alias/${local.name}-s3"
  target_key_id = aws_kms_key.s3.key_id
}

# KMS Key for Secrets Manager
resource "aws_kms_key" "secrets" {
  description             = "KMS key for Phoenix Guardian Secrets Manager"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(local.tags, {
    Name    = "${local.name}-secrets-kms"
    Purpose = "Secrets Manager encryption"
    HIPAA   = "true"
  })
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${local.name}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# KMS Key for SNS
resource "aws_kms_key" "sns" {
  description             = "KMS key for Phoenix Guardian SNS topics"
  deletion_window_in_days = 30
  enable_key_rotation     = true

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
        Sid    = "Allow SNS to use the key"
        Effect = "Allow"
        Principal = {
          Service = "sns.amazonaws.com"
        }
        Action = [
          "kms:GenerateDataKey*",
          "kms:Decrypt"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow CloudWatch to use the key"
        Effect = "Allow"
        Principal = {
          Service = "cloudwatch.amazonaws.com"
        }
        Action = [
          "kms:GenerateDataKey*",
          "kms:Decrypt"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.tags, {
    Name    = "${local.name}-sns-kms"
    Purpose = "SNS encryption"
  })
}

resource "aws_kms_alias" "sns" {
  name          = "alias/${local.name}-sns"
  target_key_id = aws_kms_key.sns.key_id
}

# =============================================================================
# S3 BUCKETS
# =============================================================================

# Main data bucket (PHI storage)
resource "aws_s3_bucket" "phoenix_data" {
  bucket = "${local.name}-data-${data.aws_caller_identity.current.account_id}"

  tags = merge(local.tags, {
    Name = "${local.name}-data"
    HIPAA = "true"
    DataClassification = "PHI"
  })
}

resource "aws_s3_bucket_versioning" "phoenix_data" {
  bucket = aws_s3_bucket.phoenix_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "phoenix_data" {
  bucket = aws_s3_bucket.phoenix_data.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.s3.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "phoenix_data" {
  bucket = aws_s3_bucket.phoenix_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_logging" "phoenix_data" {
  bucket = aws_s3_bucket.phoenix_data.id

  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "phoenix-data-logs/"
}

resource "aws_s3_bucket_lifecycle_configuration" "phoenix_data" {
  bucket = aws_s3_bucket.phoenix_data.id

  rule {
    id     = "transition-to-glacier"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 2555  # 7 years (HIPAA retention)
    }

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}

# ML Models bucket
resource "aws_s3_bucket" "ml_models" {
  bucket = "${local.name}-ml-models-${data.aws_caller_identity.current.account_id}"

  tags = merge(local.tags, {
    Name = "${local.name}-ml-models"
  })
}

resource "aws_s3_bucket_versioning" "ml_models" {
  bucket = aws_s3_bucket.ml_models.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ml_models" {
  bucket = aws_s3_bucket.ml_models.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.s3.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "ml_models" {
  bucket = aws_s3_bucket.ml_models.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Access logs bucket
resource "aws_s3_bucket" "access_logs" {
  bucket = "${local.name}-access-logs-${data.aws_caller_identity.current.account_id}"

  tags = merge(local.tags, {
    Name = "${local.name}-access-logs"
  })
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}

# =============================================================================
# ECR REPOSITORY
# =============================================================================

resource "aws_ecr_repository" "phoenix" {
  name                 = "phoenix-guardian"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.s3.arn
  }

  tags = local.tags
}

resource "aws_ecr_lifecycle_policy" "phoenix" {
  repository = aws_ecr_repository.phoenix.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 30 images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v", "release"]
          countType     = "imageCountMoreThan"
          countNumber   = 30
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Expire untagged images older than 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# =============================================================================
# WAF (Web Application Firewall)
# =============================================================================

resource "aws_wafv2_web_acl" "phoenix" {
  name        = "${local.name}-waf"
  description = "WAF for Phoenix Guardian API"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # AWS Managed Rules - Common Rule Set
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name}-common-rules"
      sampled_requests_enabled   = true
    }
  }

  # AWS Managed Rules - SQL Injection
  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name}-sqli-rules"
      sampled_requests_enabled   = true
    }
  }

  # Rate limiting
  rule {
    name     = "RateLimitRule"
    priority = 3

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name}-waf"
    sampled_requests_enabled   = true
  }

  tags = local.tags
}

# =============================================================================
# SECURITY HUB
# =============================================================================

resource "aws_securityhub_account" "main" {
  enable_default_standards = true

  control_finding_generator = "SECURITY_CONTROL"
  auto_enable_controls      = true
}

resource "aws_securityhub_standards_subscription" "hipaa" {
  depends_on    = [aws_securityhub_account.main]
  standards_arn = "arn:aws:securityhub:${var.aws_region}::standards/hipaa-baseline/v/1.0.0"
}
