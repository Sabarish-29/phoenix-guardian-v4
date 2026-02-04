# =============================================================================
# PHOENIX GUARDIAN - RDS POSTGRESQL
# =============================================================================
# HIPAA-compliant PostgreSQL RDS with:
# - Multi-AZ deployment for high availability
# - Encryption at rest with KMS
# - Performance Insights for monitoring
# - Automated backups with 30-day retention
# =============================================================================

resource "aws_db_subnet_group" "postgres" {
  name        = "${local.name}-postgres"
  description = "Database subnet group for Phoenix Guardian PostgreSQL"
  subnet_ids  = module.vpc.database_subnets

  tags = merge(local.tags, {
    Name = "${local.name}-postgres-subnet-group"
  })
}

resource "aws_db_parameter_group" "postgres" {
  name        = "${local.name}-postgres15"
  family      = "postgres15"
  description = "Custom parameter group for Phoenix Guardian PostgreSQL"

  # Force SSL connections (HIPAA requirement)
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  # Logging for audit trail
  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_statement"
    value = "ddl"  # Log DDL statements only (not data)
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # Log queries taking >1 second
  }

  # Performance tuning
  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  parameter {
    name  = "pg_stat_statements.track"
    value = "all"
  }

  tags = local.tags
}

resource "aws_db_instance" "postgres" {
  identifier = "${local.name}-postgres"

  # Engine configuration
  engine               = "postgres"
  engine_version       = "15.4"
  instance_class       = var.db_instance_class
  parameter_group_name = aws_db_parameter_group.postgres.name

  # Storage configuration
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  iops                  = var.db_iops
  storage_throughput    = var.db_storage_throughput

  # Encryption (HIPAA requirement)
  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn

  # Database configuration
  db_name  = "phoenix"
  username = var.db_username
  password = random_password.db_password.result
  port     = 5432

  # Network configuration
  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  # High availability
  multi_az = true

  # Backup configuration
  backup_retention_period   = 30
  backup_window             = "03:00-04:00"
  maintenance_window        = "sun:04:00-sun:05:00"
  copy_tags_to_snapshot     = true
  delete_automated_backups  = false

  # Monitoring
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  performance_insights_enabled    = true
  performance_insights_retention_period = 7
  performance_insights_kms_key_id = aws_kms_key.rds.arn
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn

  # Deletion protection (HIPAA requirement - prevent accidental deletion)
  deletion_protection      = true
  skip_final_snapshot      = false
  final_snapshot_identifier = "${local.name}-final-${formatdate("YYYYMMDD-HHmmss", timestamp())}"

  # Automatic minor version upgrades
  auto_minor_version_upgrade  = true
  allow_major_version_upgrade = false

  # Enable IAM authentication
  iam_database_authentication_enabled = true

  tags = merge(local.tags, {
    Name = "Phoenix Guardian PostgreSQL"
    HIPAA = "true"
    DataClassification = "PHI"
  })

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      final_snapshot_identifier,
    ]
  }
}

# =============================================================================
# READ REPLICA (for read-heavy workloads)
# =============================================================================

resource "aws_db_instance" "postgres_replica" {
  count = var.create_read_replica ? 1 : 0

  identifier = "${local.name}-postgres-replica"

  # Replica configuration
  replicate_source_db = aws_db_instance.postgres.identifier
  instance_class      = var.db_replica_instance_class

  # Storage (inherited from primary, but can specify IOPS)
  storage_type       = "gp3"
  iops               = var.db_iops
  storage_throughput = var.db_storage_throughput

  # Encryption (inherited from primary)
  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn

  # Network
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  # No Multi-AZ for replica (it IS the DR)
  multi_az = false

  # Backup (handled by primary)
  backup_retention_period = 0
  skip_final_snapshot     = true

  # Monitoring
  performance_insights_enabled    = true
  performance_insights_retention_period = 7
  performance_insights_kms_key_id = aws_kms_key.rds.arn
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn

  # Auto upgrades follow primary
  auto_minor_version_upgrade = true

  tags = merge(local.tags, {
    Name = "Phoenix Guardian PostgreSQL Replica"
    Role = "read-replica"
  })
}

# =============================================================================
# SECURITY GROUP FOR RDS
# =============================================================================

resource "aws_security_group" "rds" {
  name        = "${local.name}-rds"
  description = "Security group for Phoenix Guardian RDS PostgreSQL"
  vpc_id      = module.vpc.vpc_id

  # Allow PostgreSQL from EKS nodes only
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
    description     = "PostgreSQL from EKS nodes"
  }

  # Allow PostgreSQL from VPC (for management)
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "PostgreSQL from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = merge(local.tags, {
    Name = "${local.name}-rds-sg"
  })
}

# =============================================================================
# IAM ROLE FOR RDS ENHANCED MONITORING
# =============================================================================

resource "aws_iam_role" "rds_monitoring" {
  name = "${local.name}-rds-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# =============================================================================
# SECRETS MANAGER FOR DATABASE CREDENTIALS
# =============================================================================

resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${local.name}/database/credentials"
  description = "Database credentials for Phoenix Guardian"
  kms_key_id  = aws_kms_key.secrets.arn

  recovery_window_in_days = 30

  tags = merge(local.tags, {
    Name = "${local.name}-db-credentials"
  })
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db_password.result
    host     = aws_db_instance.postgres.address
    port     = 5432
    dbname   = "phoenix"
    engine   = "postgres"
  })
}
