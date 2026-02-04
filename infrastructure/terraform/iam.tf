# =============================================================================
# PHOENIX GUARDIAN - IAM ROLES AND POLICIES
# =============================================================================
# HIPAA-compliant IAM configuration with least privilege principle
# Includes IRSA (IAM Roles for Service Accounts) for K8s workloads
# =============================================================================

# =============================================================================
# EKS ADMIN ROLE
# =============================================================================

resource "aws_iam_role" "eks_admin" {
  name = "${local.name}-eks-admin"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Condition = {
          Bool = {
            "aws:MultiFactorAuthPresent" = "true"
          }
        }
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "eks_admin" {
  role       = aws_iam_role.eks_admin.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# =============================================================================
# PHOENIX API SERVICE ACCOUNT (IRSA)
# =============================================================================

module "phoenix_api_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${local.name}-phoenix-api"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["production:phoenix-api", "staging:phoenix-api"]
    }
  }

  role_policy_arns = {
    secrets_manager = aws_iam_policy.phoenix_api_secrets.arn
    s3_access       = aws_iam_policy.phoenix_api_s3.arn
    kms_access      = aws_iam_policy.phoenix_api_kms.arn
    cloudwatch      = aws_iam_policy.phoenix_api_cloudwatch.arn
  }

  tags = local.tags
}

# Policy: Access to Secrets Manager
resource "aws_iam_policy" "phoenix_api_secrets" {
  name        = "${local.name}-api-secrets"
  description = "Allow Phoenix API to read secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.db_credentials.arn,
          aws_secretsmanager_secret.redis_credentials.arn,
          "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${local.name}/*"
        ]
      }
    ]
  })

  tags = local.tags
}

# Policy: S3 access for PHI storage
resource "aws_iam_policy" "phoenix_api_s3" {
  name        = "${local.name}-api-s3"
  description = "Allow Phoenix API to access S3 buckets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.phoenix_data.arn,
          "${aws_s3_bucket.phoenix_data.arn}/*"
        ]
      },
      # Deny access to other tenants' data (defense in depth)
      {
        Effect = "Deny"
        Action = "s3:*"
        Resource = [
          "${aws_s3_bucket.phoenix_data.arn}/*"
        ]
        Condition = {
          StringNotLike = {
            "s3:prefix" = "$${aws:PrincipalTag/tenant_id}/*"
          }
        }
      }
    ]
  })

  tags = local.tags
}

# Policy: KMS for encryption
resource "aws_iam_policy" "phoenix_api_kms" {
  name        = "${local.name}-api-kms"
  description = "Allow Phoenix API to use KMS keys"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = [
          aws_kms_key.rds.arn,
          aws_kms_key.redis.arn,
          aws_kms_key.s3.arn,
          aws_kms_key.secrets.arn
        ]
      }
    ]
  })

  tags = local.tags
}

# Policy: CloudWatch for logging and metrics
resource "aws_iam_policy" "phoenix_api_cloudwatch" {
  name        = "${local.name}-api-cloudwatch"
  description = "Allow Phoenix API to write to CloudWatch"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/phoenix-guardian/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "PhoenixGuardian"
          }
        }
      }
    ]
  })

  tags = local.tags
}

# =============================================================================
# ML WORKER SERVICE ACCOUNT (IRSA)
# =============================================================================

module "phoenix_ml_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${local.name}-phoenix-ml"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["production:phoenix-ml", "staging:phoenix-ml"]
    }
  }

  role_policy_arns = {
    secrets_manager = aws_iam_policy.phoenix_api_secrets.arn
    s3_access       = aws_iam_policy.phoenix_ml_s3.arn
    kms_access      = aws_iam_policy.phoenix_api_kms.arn
    sagemaker       = aws_iam_policy.phoenix_ml_sagemaker.arn
  }

  tags = local.tags
}

# Policy: S3 for ML models and training data
resource "aws_iam_policy" "phoenix_ml_s3" {
  name        = "${local.name}-ml-s3"
  description = "Allow Phoenix ML to access S3 for models and data"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.phoenix_data.arn,
          "${aws_s3_bucket.phoenix_data.arn}/*",
          aws_s3_bucket.ml_models.arn,
          "${aws_s3_bucket.ml_models.arn}/*"
        ]
      }
    ]
  })

  tags = local.tags
}

# Policy: SageMaker for ML inference
resource "aws_iam_policy" "phoenix_ml_sagemaker" {
  name        = "${local.name}-ml-sagemaker"
  description = "Allow Phoenix ML to use SageMaker for inference"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sagemaker:InvokeEndpoint"
        ]
        Resource = [
          "arn:aws:sagemaker:${var.aws_region}:${data.aws_caller_identity.current.account_id}:endpoint/${local.name}-*"
        ]
      }
    ]
  })

  tags = local.tags
}

# =============================================================================
# GITHUB ACTIONS OIDC ROLE (for CI/CD)
# =============================================================================

data "aws_iam_openid_connect_provider" "github" {
  count = var.enable_github_actions_oidc ? 1 : 0
  url   = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.enable_github_actions_oidc && length(data.aws_iam_openid_connect_provider.github) == 0 ? 1 : 0

  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = local.tags
}

resource "aws_iam_role" "github_actions" {
  count = var.enable_github_actions_oidc ? 1 : 0

  name = "${local.name}-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.enable_github_actions_oidc ? (
            length(data.aws_iam_openid_connect_provider.github) > 0 
            ? data.aws_iam_openid_connect_provider.github[0].arn 
            : aws_iam_openid_connect_provider.github[0].arn
          ) : null
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_org}/${var.github_repo}:*"
          }
        }
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "github_actions" {
  count = var.enable_github_actions_oidc ? 1 : 0

  name = "${local.name}-github-actions-policy"
  role = aws_iam_role.github_actions[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:ListClusters"
        ]
        Resource = [
          module.eks.cluster_arn
        ]
      }
    ]
  })
}
