"""
Phoenix Guardian - Database Migration: Create RLS Policies
Sets up Row-Level Security for tenant isolation.

Revision ID: 002_create_rls_policies
Create Date: 2024-01-01
Depends On: 001_add_tenant_id_columns
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = '002_create_rls_policies'
down_revision = '001_add_tenant_id_columns'
branch_labels = None
depends_on = None

# Tables that need RLS
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

# Application tenant ID setting
TENANT_SETTING = 'app.tenant_id'


def upgrade():
    """Enable RLS and create tenant isolation policies."""
    
    connection = op.get_bind()
    
    # Create the application role for RLS bypass
    connection.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'phoenix_admin') THEN
                CREATE ROLE phoenix_admin;
            END IF;
        END
        $$;
    """))
    
    # Create the application user role
    connection.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'phoenix_app') THEN
                CREATE ROLE phoenix_app;
            END IF;
        END
        $$;
    """))
    
    for table_name in MULTI_TENANT_TABLES:
        inspector = sa.inspect(connection)
        
        if table_name not in inspector.get_table_names():
            print(f"Table {table_name} does not exist, skipping")
            continue
        
        # Enable Row-Level Security on the table
        connection.execute(sa.text(f"""
            ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;
        """))
        
        # Force RLS for table owner (critical for security)
        connection.execute(sa.text(f"""
            ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;
        """))
        
        # Create tenant isolation policy
        # This policy:
        # - Allows SELECT only for rows where tenant_id matches current setting
        # - Allows INSERT only if tenant_id matches current setting
        # - Allows UPDATE only for rows where tenant_id matches
        # - Allows DELETE only for rows where tenant_id matches
        policy_name = f'tenant_isolation_{table_name}'
        
        connection.execute(sa.text(f"""
            DROP POLICY IF EXISTS {policy_name} ON {table_name};
        """))
        
        connection.execute(sa.text(f"""
            CREATE POLICY {policy_name} ON {table_name}
            AS PERMISSIVE
            FOR ALL
            TO phoenix_app
            USING (tenant_id = current_setting('{TENANT_SETTING}', true))
            WITH CHECK (tenant_id = current_setting('{TENANT_SETTING}', true));
        """))
        
        # Create admin bypass policy
        # Allows admin role to access all rows
        admin_policy_name = f'admin_bypass_{table_name}'
        
        connection.execute(sa.text(f"""
            DROP POLICY IF EXISTS {admin_policy_name} ON {table_name};
        """))
        
        connection.execute(sa.text(f"""
            CREATE POLICY {admin_policy_name} ON {table_name}
            AS PERMISSIVE
            FOR ALL
            TO phoenix_admin
            USING (true)
            WITH CHECK (true);
        """))
        
        print(f"Created RLS policies for {table_name}")
    
    print(f"RLS enabled on {len(MULTI_TENANT_TABLES)} tables")


def downgrade():
    """Disable RLS and drop policies."""
    
    connection = op.get_bind()
    
    for table_name in MULTI_TENANT_TABLES:
        inspector = sa.inspect(connection)
        
        if table_name not in inspector.get_table_names():
            continue
        
        # Drop policies
        connection.execute(sa.text(f"""
            DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name};
        """))
        
        connection.execute(sa.text(f"""
            DROP POLICY IF EXISTS admin_bypass_{table_name} ON {table_name};
        """))
        
        # Disable RLS
        connection.execute(sa.text(f"""
            ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;
        """))
        
        connection.execute(sa.text(f"""
            ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY;
        """))
    
    # Drop roles (may fail if in use)
    try:
        connection.execute(sa.text("DROP ROLE IF EXISTS phoenix_app;"))
        connection.execute(sa.text("DROP ROLE IF EXISTS phoenix_admin;"))
    except Exception as e:
        print(f"Could not drop roles: {e}")
    
    print("RLS disabled on all tables")
