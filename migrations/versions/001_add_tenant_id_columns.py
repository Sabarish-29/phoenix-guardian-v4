"""
Phoenix Guardian - Database Migration: Add Tenant ID Columns
Adds tenant_id column to all multi-tenant tables.

Revision ID: 001_add_tenant_id_columns
Create Date: 2024-01-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision = '001_add_tenant_id_columns'
down_revision = None
branch_labels = None
depends_on = None

# Tables that need tenant_id column
MULTI_TENANT_TABLES = [
    'predictions',
    'alerts',
    'patient_data',
    'model_versions',
    'feature_cache',
    'audit_logs',
    'user_feedback',
    'system_events',
    'performance_metrics',
    'hospital_config',
]


def upgrade():
    """Add tenant_id column to all multi-tenant tables."""
    
    # First, create the tenants table if it doesn't exist
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('config', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('settings', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('max_users', sa.Integer(), server_default='100'),
        sa.Column('max_predictions_per_day', sa.Integer(), server_default='10000'),
        sa.Column('max_storage_gb', sa.Float(), server_default='100.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('suspended_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Add tenant_id column to each table
    for table_name in MULTI_TENANT_TABLES:
        # Check if table exists
        connection = op.get_bind()
        inspector = sa.inspect(connection)
        
        if table_name in inspector.get_table_names():
            # Check if column already exists
            columns = [c['name'] for c in inspector.get_columns(table_name)]
            
            if 'tenant_id' not in columns:
                # Add tenant_id column
                op.add_column(
                    table_name,
                    sa.Column(
                        'tenant_id',
                        sa.String(64),
                        nullable=True,  # Initially nullable for existing data
                    )
                )
                
                # Add index on tenant_id
                op.create_index(
                    f'ix_{table_name}_tenant_id',
                    table_name,
                    ['tenant_id'],
                )
                
                # Add foreign key to tenants table
                op.create_foreign_key(
                    f'fk_{table_name}_tenant',
                    table_name,
                    'tenants',
                    ['tenant_id'],
                    ['id'],
                    ondelete='CASCADE',
                )
    
    print(f"Added tenant_id column to {len(MULTI_TENANT_TABLES)} tables")


def downgrade():
    """Remove tenant_id column from all multi-tenant tables."""
    
    for table_name in MULTI_TENANT_TABLES:
        connection = op.get_bind()
        inspector = sa.inspect(connection)
        
        if table_name in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns(table_name)]
            
            if 'tenant_id' in columns:
                # Drop foreign key
                op.drop_constraint(
                    f'fk_{table_name}_tenant',
                    table_name,
                    type_='foreignkey',
                )
                
                # Drop index
                op.drop_index(f'ix_{table_name}_tenant_id', table_name)
                
                # Drop column
                op.drop_column(table_name, 'tenant_id')
    
    # Drop tenants table
    op.drop_table('tenants')
    
    print(f"Removed tenant_id column from {len(MULTI_TENANT_TABLES)} tables")
