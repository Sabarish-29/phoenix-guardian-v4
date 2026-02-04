# =============================================================================
# PHOENIX GUARDIAN - EKS CLUSTER
# =============================================================================
# Production EKS cluster with 3 node groups:
# - system: CoreDNS, kube-proxy, cluster add-ons
# - api: FastAPI application pods
# - ml: GPU-enabled nodes for ML workloads
# =============================================================================

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.21"

  cluster_name    = local.name
  cluster_version = local.cluster_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Cluster endpoint access
  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  # Restrict public access to specific CIDR blocks (add your office IPs)
  cluster_endpoint_public_access_cidrs = var.allowed_cidr_blocks

  # Cluster add-ons
  cluster_addons = {
    coredns = {
      most_recent = true
      configuration_values = jsonencode({
        computeType = "Fargate"
        resources = {
          limits = {
            cpu    = "0.25"
            memory = "256M"
          }
          requests = {
            cpu    = "0.25"
            memory = "256M"
          }
        }
      })
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
      configuration_values = jsonencode({
        env = {
          ENABLE_PREFIX_DELEGATION = "true"
          WARM_PREFIX_TARGET       = "1"
        }
      })
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    }
  }

  # Encryption for Kubernetes secrets
  cluster_encryption_config = {
    provider_key_arn = aws_kms_key.eks.arn
    resources        = ["secrets"]
  }

  # Enable IRSA (IAM Roles for Service Accounts)
  enable_irsa = true

  # Cluster security group additional rules
  cluster_security_group_additional_rules = {
    ingress_nodes_ephemeral_ports_tcp = {
      description                = "Nodes on ephemeral ports"
      protocol                   = "tcp"
      from_port                  = 1025
      to_port                    = 65535
      type                       = "ingress"
      source_node_security_group = true
    }
  }

  # Node security group additional rules
  node_security_group_additional_rules = {
    ingress_self_all = {
      description = "Node to node all ports/protocols"
      protocol    = "-1"
      from_port   = 0
      to_port     = 0
      type        = "ingress"
      self        = true
    }
  }

  # ==========================================================================
  # MANAGED NODE GROUPS
  # ==========================================================================

  eks_managed_node_groups = {
    # -------------------------------------------------------------------------
    # SYSTEM NODE GROUP - Cluster add-ons and critical workloads
    # -------------------------------------------------------------------------
    system = {
      name            = "${local.name}-system"
      use_name_prefix = true

      instance_types = ["t3.medium"]
      capacity_type  = "ON_DEMAND"

      min_size     = 2
      max_size     = 4
      desired_size = 2

      # Use Amazon Linux 2023
      ami_type = "AL2023_x86_64_STANDARD"

      labels = {
        role = "system"
        environment = var.environment
      }

      taints = [{
        key    = "CriticalAddonsOnly"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]

      # EBS configuration
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 50
            volume_type           = "gp3"
            encrypted             = true
            kms_key_id            = aws_kms_key.eks.arn
            delete_on_termination = true
          }
        }
      }

      tags = merge(local.tags, {
        NodeGroup = "system"
      })
    }

    # -------------------------------------------------------------------------
    # API NODE GROUP - FastAPI application pods
    # -------------------------------------------------------------------------
    api = {
      name            = "${local.name}-api"
      use_name_prefix = true

      instance_types = ["c6i.2xlarge"]  # 8 vCPU, 16 GB RAM - CPU optimized
      capacity_type  = "ON_DEMAND"

      min_size     = 3
      max_size     = 12
      desired_size = 6

      ami_type = "AL2023_x86_64_STANDARD"

      labels = {
        role = "api"
        environment = var.environment
        workload = "web"
      }

      # EBS configuration
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 100
            volume_type           = "gp3"
            iops                  = 3000
            throughput            = 125
            encrypted             = true
            kms_key_id            = aws_kms_key.eks.arn
            delete_on_termination = true
          }
        }
      }

      tags = merge(local.tags, {
        NodeGroup = "api"
      })
    }

    # -------------------------------------------------------------------------
    # ML NODE GROUP - GPU-enabled for ML workloads
    # -------------------------------------------------------------------------
    ml = {
      name            = "${local.name}-ml"
      use_name_prefix = true

      instance_types = ["g4dn.xlarge"]  # NVIDIA T4 GPU, 4 vCPU, 16 GB RAM
      capacity_type  = "ON_DEMAND"

      min_size     = 1
      max_size     = 4
      desired_size = 2

      # GPU-optimized AMI
      ami_type = "AL2_x86_64_GPU"

      labels = {
        role = "ml"
        environment = var.environment
        gpu = "nvidia-t4"
        workload = "ml"
      }

      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]

      # Larger EBS for ML models and datasets
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 200
            volume_type           = "gp3"
            iops                  = 4000
            throughput            = 250
            encrypted             = true
            kms_key_id            = aws_kms_key.eks.arn
            delete_on_termination = true
          }
        }
      }

      tags = merge(local.tags, {
        NodeGroup = "ml"
        GPU       = "nvidia-t4"
      })
    }
  }

  # Manage aws-auth ConfigMap
  manage_aws_auth_configmap = true

  aws_auth_roles = [
    {
      rolearn  = aws_iam_role.eks_admin.arn
      username = "admin"
      groups   = ["system:masters"]
    }
  ]

  tags = local.tags
}

# =============================================================================
# EBS CSI DRIVER IRSA
# =============================================================================

module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "${local.name}-ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }

  tags = local.tags
}

# =============================================================================
# CLUSTER AUTOSCALER IRSA
# =============================================================================

module "cluster_autoscaler_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name                        = "${local.name}-cluster-autoscaler"
  attach_cluster_autoscaler_policy = true
  cluster_autoscaler_cluster_names = [module.eks.cluster_name]

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:cluster-autoscaler"]
    }
  }

  tags = local.tags
}

# =============================================================================
# LOAD BALANCER CONTROLLER IRSA
# =============================================================================

module "load_balancer_controller_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name                              = "${local.name}-lb-controller"
  attach_load_balancer_controller_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }

  tags = local.tags
}

# =============================================================================
# NVIDIA DEVICE PLUGIN (for GPU nodes)
# =============================================================================

resource "helm_release" "nvidia_device_plugin" {
  name       = "nvidia-device-plugin"
  repository = "https://nvidia.github.io/k8s-device-plugin"
  chart      = "nvidia-device-plugin"
  namespace  = "kube-system"
  version    = "0.14.3"

  set {
    name  = "tolerations[0].key"
    value = "nvidia.com/gpu"
  }

  set {
    name  = "tolerations[0].operator"
    value = "Exists"
  }

  set {
    name  = "tolerations[0].effect"
    value = "NoSchedule"
  }

  depends_on = [module.eks]
}

# =============================================================================
# CLUSTER AUTOSCALER
# =============================================================================

resource "helm_release" "cluster_autoscaler" {
  name       = "cluster-autoscaler"
  repository = "https://kubernetes.github.io/autoscaler"
  chart      = "cluster-autoscaler"
  namespace  = "kube-system"
  version    = "9.34.0"

  set {
    name  = "autoDiscovery.clusterName"
    value = module.eks.cluster_name
  }

  set {
    name  = "awsRegion"
    value = var.aws_region
  }

  set {
    name  = "rbac.serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.cluster_autoscaler_irsa.iam_role_arn
  }

  set {
    name  = "extraArgs.balance-similar-node-groups"
    value = "true"
  }

  set {
    name  = "extraArgs.skip-nodes-with-system-pods"
    value = "false"
  }

  depends_on = [module.eks]
}

# =============================================================================
# AWS LOAD BALANCER CONTROLLER
# =============================================================================

resource "helm_release" "aws_load_balancer_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"
  version    = "1.6.2"

  set {
    name  = "clusterName"
    value = module.eks.cluster_name
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.load_balancer_controller_irsa.iam_role_arn
  }

  set {
    name  = "vpcId"
    value = module.vpc.vpc_id
  }

  set {
    name  = "region"
    value = var.aws_region
  }

  depends_on = [module.eks]
}
