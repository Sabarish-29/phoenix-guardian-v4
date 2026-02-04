"""
Phoenix Guardian - Database Migration: Tenant-Scoped Indexes
Creates composite indexes for efficient tenant-scoped queries.

Revision ID: 003_tenant_scoped_indexes
Create Date: 2024-01-01
Depends On: 002_create_rls_policies
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = '003_tenant_scoped_indexes'
down_revision = '002_create_rls_policies'
branch_labels = None
depends_on = None


def upgrade():
    """Create tenant-scoped composite indexes for performance."""
    
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    # Predictions indexes
    if 'predictions' in tables:
        # Tenant + patient for patient lookup
        op.create_index(
            'ix_predictions_tenant_patient',
            'predictions',
            ['tenant_id', 'patient_id'],
            if_not_exists=True,
        )
        
        # Tenant + timestamp for time-based queries
        op.create_index(
            'ix_predictions_tenant_timestamp',
            'predictions',
            ['tenant_id', 'prediction_timestamp'],
            if_not_exists=True,
        )
        
        # Tenant + risk category for risk filtering
        op.create_index(
            'ix_predictions_tenant_risk',
            'predictions',
            ['tenant_id', 'risk_category'],
            if_not_exists=True,
        )
        
        # Tenant + model version for model analysis
        op.create_index(
            'ix_predictions_tenant_model',
            'predictions',
            ['tenant_id', 'model_version'],
            if_not_exists=True,
        )
    
    # Alerts indexes
    if 'alerts' in tables:
        # Tenant + patient for patient alerts
        op.create_index(
            'ix_alerts_tenant_patient',
            'alerts',
            ['tenant_id', 'patient_id'],
            if_not_exists=True,
        )
        
        # Tenant + status for active alert queries
        op.create_index(
            'ix_alerts_tenant_status',
            'alerts',
            ['tenant_id', 'status'],
            if_not_exists=True,
        )
        
        # Tenant + severity for priority filtering
        op.create_index(
            'ix_alerts_tenant_severity',
            'alerts',
            ['tenant_id', 'severity'],
            if_not_exists=True,
        )
        
        # Tenant + created_at for time-based queries
        op.create_index(
            'ix_alerts_tenant_created',
            'alerts',
            ['tenant_id', 'created_at'],
            if_not_exists=True,
        )
    
    # Patient data indexes
    if 'patient_data' in tables:
        # Tenant + patient (unique constraint)
        op.create_index(
            'ix_patient_data_tenant_patient',
            'patient_data',
            ['tenant_id', 'patient_id'],
            unique=True,
            if_not_exists=True,
        )
        
        # Tenant + data timestamp for freshness queries
        op.create_index(
            'ix_patient_data_tenant_timestamp',
            'patient_data',
            ['tenant_id', 'data_timestamp'],
            if_not_exists=True,
        )
    
    # Model versions indexes
    if 'model_versions' in tables:
        # Tenant + model name for version lookup
        op.create_index(
            'ix_model_versions_tenant_model',
            'model_versions',
            ['tenant_id', 'model_name'],
            if_not_exists=True,
        )
        
        # Tenant + active for finding active models
        op.create_index(
            'ix_model_versions_tenant_active',
            'model_versions',
            ['tenant_id', 'is_active'],
            if_not_exists=True,
        )
    
    # Audit logs indexes
    if 'audit_logs' in tables:
        # Tenant + timestamp for log queries
        op.create_index(
            'ix_audit_logs_tenant_timestamp',
            'audit_logs',
            ['tenant_id', 'timestamp'],
            if_not_exists=True,
        )
        
        # Tenant + user for user activity
        op.create_index(
            'ix_audit_logs_tenant_user',
            'audit_logs',
            ['tenant_id', 'user_id'],
            if_not_exists=True,
        )
        
        # Tenant + event type for event filtering
        op.create_index(
            'ix_audit_logs_tenant_event',
            'audit_logs',
            ['tenant_id', 'event_type'],
            if_not_exists=True,
        )
        
        # Tenant + resource for resource tracking
        op.create_index(
            'ix_audit_logs_tenant_resource',
            'audit_logs',
            ['tenant_id', 'resource_type', 'resource_id'],
            if_not_exists=True,
        )
    
    # User feedback indexes
    if 'user_feedback' in tables:
        # Tenant + prediction for feedback lookup
        op.create_index(
            'ix_feedback_tenant_prediction',
            'user_feedback',
            ['tenant_id', 'prediction_id'],
            if_not_exists=True,
        )
        
        # Tenant + type for feedback analysis
        op.create_index(
            'ix_feedback_tenant_type',
            'user_feedback',
            ['tenant_id', 'feedback_type'],
            if_not_exists=True,
        )
        
        # Tenant + submitted_at for time-based queries
        op.create_index(
            'ix_feedback_tenant_submitted',
            'user_feedback',
            ['tenant_id', 'submitted_at'],
            if_not_exists=True,
        )
    
    # Performance metrics indexes
    if 'performance_metrics' in tables:
        # Tenant + metric name + timestamp for metric queries
        op.create_index(
            'ix_metrics_tenant_name_time',
            'performance_metrics',
            ['tenant_id', 'metric_name', 'timestamp'],
            if_not_exists=True,
        )
        
        # Tenant + metric type for aggregations
        op.create_index(
            'ix_metrics_tenant_type',
            'performance_metrics',
            ['tenant_id', 'metric_type'],
            if_not_exists=True,
        )
    
    # Hospital config indexes
    if 'hospital_config' in tables:
        # Tenant + config key (unique)
        op.create_index(
            'ix_hospital_config_tenant_key',
            'hospital_config',
            ['tenant_id', 'config_key'],
            unique=True,
            if_not_exists=True,
        )
        
        # Tenant + category for category lookup
        op.create_index(
            'ix_hospital_config_tenant_category',
            'hospital_config',
            ['tenant_id', 'config_category'],
            if_not_exists=True,
        )
    
    print("Created tenant-scoped composite indexes")


def downgrade():
    """Drop tenant-scoped indexes."""
    
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # List of all indexes to drop
    indexes_to_drop = [
        ('predictions', 'ix_predictions_tenant_patient'),
        ('predictions', 'ix_predictions_tenant_timestamp'),
        ('predictions', 'ix_predictions_tenant_risk'),
        ('predictions', 'ix_predictions_tenant_model'),
        ('alerts', 'ix_alerts_tenant_patient'),
        ('alerts', 'ix_alerts_tenant_status'),
        ('alerts', 'ix_alerts_tenant_severity'),
        ('alerts', 'ix_alerts_tenant_created'),
        ('patient_data', 'ix_patient_data_tenant_patient'),
        ('patient_data', 'ix_patient_data_tenant_timestamp'),
        ('model_versions', 'ix_model_versions_tenant_model'),
        ('model_versions', 'ix_model_versions_tenant_active'),
        ('audit_logs', 'ix_audit_logs_tenant_timestamp'),
        ('audit_logs', 'ix_audit_logs_tenant_user'),
        ('audit_logs', 'ix_audit_logs_tenant_event'),
        ('audit_logs', 'ix_audit_logs_tenant_resource'),
        ('user_feedback', 'ix_feedback_tenant_prediction'),
        ('user_feedback', 'ix_feedback_tenant_type'),
        ('user_feedback', 'ix_feedback_tenant_submitted'),
        ('performance_metrics', 'ix_metrics_tenant_name_time'),
        ('performance_metrics', 'ix_metrics_tenant_type'),
        ('hospital_config', 'ix_hospital_config_tenant_key'),
        ('hospital_config', 'ix_hospital_config_tenant_category'),
    ]
    
    for table_name, index_name in indexes_to_drop:
        try:
            op.drop_index(index_name, table_name)
        except Exception as e:
            print(f"Could not drop index {index_name}: {e}")
    
    print("Dropped tenant-scoped indexes")
