# =============================================================================
# PHOENIX GUARDIAN - PRODUCTION INFRASTRUCTURE
# =============================================================================
# Terraform configuration for AWS EKS production deployment
# HIPAA-compliant infrastructure with encryption at rest and in transit
# =============================================================================

terraform {
  required_version = ">= 1.6"

  backend "s3" {
    bucket         = "phoenix-guardian-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "phoenix-terraform-locks"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project           = "PhoenixGuardian"
      Environment       = var.environment
      ManagedBy         = "Terraform"
      HIPAA             = "true"
      DataClassification = "PHI"
      CostCenter        = "healthcare-ai"
    }
  }
}

provider "aws" {
  alias  = "us_west_2"
  region = "us-west-2"

  default_tags {
    tags = {
      Project           = "PhoenixGuardian"
      Environment       = var.environment
      ManagedBy         = "Terraform"
      HIPAA             = "true"
      DataClassification = "PHI"
      CostCenter        = "healthcare-ai"
    }
  }
}

# Configure Kubernetes provider after EKS is created
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}

# =============================================================================
# DATA SOURCES
# =============================================================================

data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

# =============================================================================
# LOCAL VALUES
# =============================================================================

locals {
  name            = "phoenix-${var.environment}"
  cluster_version = "1.28"
  
  azs = slice(data.aws_availability_zones.available.names, 0, 3)

  tags = {
    Project     = "PhoenixGuardian"
    Environment = var.environment
    Terraform   = "true"
  }
}

# =============================================================================
# RANDOM RESOURCES
# =============================================================================

resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "random_password" "redis_token" {
  length           = 64
  special          = false
}
