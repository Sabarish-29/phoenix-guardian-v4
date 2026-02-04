# =============================================================================
# PHOENIX GUARDIAN - ELASTICACHE REDIS
# =============================================================================
# HIPAA-compliant Redis cluster with:
# - Multi-AZ replication for high availability
# - Encryption at rest and in transit
# - AUTH token for authentication
# - Automatic failover
# =============================================================================

resource "aws_elasticache_subnet_group" "redis" {
  name        = "${local.name}-redis"
  description = "Subnet group for Phoenix Guardian Redis"
  subnet_ids  = module.vpc.private_subnets

  tags = merge(local.tags, {
    Name = "${local.name}-redis-subnet-group"
  })
}

resource "aws_elasticache_parameter_group" "redis" {
  name        = "${local.name}-redis7"
  family      = "redis7"
  description = "Custom parameter group for Phoenix Guardian Redis"

  # Memory management
  parameter {
    name  = "maxmemory-policy"
    value = "volatile-lru"
  }

  # Persistence (AOF for durability)
  parameter {
    name  = "appendonly"
    value = "yes"
  }

  parameter {
    name  = "appendfsync"
    value = "everysec"
  }

  # Timeout settings
  parameter {
    name  = "timeout"
    value = "300"
  }

  # Slow log for debugging
  parameter {
    name  = "slowlog-log-slower-than"
    value = "10000"  # 10ms
  }

  parameter {
    name  = "slowlog-max-len"
    value = "128"
  }

  tags = local.tags
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${local.name}-redis"
  description          = "Phoenix Guardian Redis Cluster"

  # Engine configuration
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = var.redis_node_type
  num_cache_clusters   = var.redis_num_cache_clusters
  parameter_group_name = aws_elasticache_parameter_group.redis.name
  port                 = 6379

  # Network configuration
  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]

  # High availability
  automatic_failover_enabled = true
  multi_az_enabled           = true

  # Encryption at rest (HIPAA requirement)
  at_rest_encryption_enabled = true
  kms_key_id                 = aws_kms_key.redis.arn

  # Encryption in transit (HIPAA requirement)
  transit_encryption_enabled = true
  auth_token                 = random_password.redis_token.result

  # Backup configuration
  snapshot_retention_limit = 7
  snapshot_window          = "03:00-05:00"

  # Maintenance window
  maintenance_window = "sun:05:00-sun:06:00"

  # Auto minor version upgrades
  auto_minor_version_upgrade = true

  # Notifications
  notification_topic_arn = aws_sns_topic.redis_notifications.arn

  # Apply changes immediately in non-prod, during window in prod
  apply_immediately = var.environment != "production"

  tags = merge(local.tags, {
    Name = "Phoenix Guardian Redis"
    HIPAA = "true"
  })

  lifecycle {
    ignore_changes = [
      num_cache_clusters,  # Managed by autoscaling
    ]
  }
}

# =============================================================================
# SECURITY GROUP FOR REDIS
# =============================================================================

resource "aws_security_group" "redis" {
  name        = "${local.name}-redis"
  description = "Security group for Phoenix Guardian ElastiCache Redis"
  vpc_id      = module.vpc.vpc_id

  # Allow Redis from EKS nodes only
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
    description     = "Redis from EKS nodes"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = merge(local.tags, {
    Name = "${local.name}-redis-sg"
  })
}

# =============================================================================
# SNS TOPIC FOR REDIS NOTIFICATIONS
# =============================================================================

resource "aws_sns_topic" "redis_notifications" {
  name              = "${local.name}-redis-notifications"
  kms_master_key_id = aws_kms_key.sns.id

  tags = local.tags
}

# =============================================================================
# SECRETS MANAGER FOR REDIS AUTH TOKEN
# =============================================================================

resource "aws_secretsmanager_secret" "redis_credentials" {
  name        = "${local.name}/redis/credentials"
  description = "Redis credentials for Phoenix Guardian"
  kms_key_id  = aws_kms_key.secrets.arn

  recovery_window_in_days = 30

  tags = merge(local.tags, {
    Name = "${local.name}-redis-credentials"
  })
}

resource "aws_secretsmanager_secret_version" "redis_credentials" {
  secret_id = aws_secretsmanager_secret.redis_credentials.id
  secret_string = jsonencode({
    auth_token       = random_password.redis_token.result
    primary_endpoint = aws_elasticache_replication_group.redis.primary_endpoint_address
    reader_endpoint  = aws_elasticache_replication_group.redis.reader_endpoint_address
    port             = 6379
  })
}

# =============================================================================
# CLOUDWATCH ALARMS FOR REDIS
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "redis_cpu" {
  alarm_name          = "${local.name}-redis-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Redis CPU utilization is high"
  alarm_actions       = [aws_sns_topic.redis_notifications.arn]
  ok_actions          = [aws_sns_topic.redis_notifications.arn]

  dimensions = {
    CacheClusterId = "${local.name}-redis-001"
  }

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "redis_memory" {
  alarm_name          = "${local.name}-redis-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Redis memory utilization is high"
  alarm_actions       = [aws_sns_topic.redis_notifications.arn]
  ok_actions          = [aws_sns_topic.redis_notifications.arn]

  dimensions = {
    CacheClusterId = "${local.name}-redis-001"
  }

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "redis_evictions" {
  alarm_name          = "${local.name}-redis-evictions"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Evictions"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Sum"
  threshold           = 100
  alarm_description   = "Redis is evicting keys - may need larger instance"
  alarm_actions       = [aws_sns_topic.redis_notifications.arn]

  dimensions = {
    CacheClusterId = "${local.name}-redis-001"
  }

  tags = local.tags
}

resource "aws_cloudwatch_metric_alarm" "redis_replication_lag" {
  alarm_name          = "${local.name}-redis-replication-lag"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ReplicationLag"
  namespace           = "AWS/ElastiCache"
  period              = 60
  statistic           = "Maximum"
  threshold           = 30
  alarm_description   = "Redis replication lag is high"
  alarm_actions       = [aws_sns_topic.redis_notifications.arn]

  dimensions = {
    CacheClusterId = "${local.name}-redis-002"  # Replica
  }

  tags = local.tags
}
