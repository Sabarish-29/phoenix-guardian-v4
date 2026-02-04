"""
Phoenix Guardian - Row-Level Security (RLS) Policies
Database-enforced tenant isolation for PostgreSQL.

This module provides the CRITICAL last line of defense for data isolation.
Even if application-level checks fail, RLS prevents cross-tenant access.

SECURITY GUARANTEE: No tenant can EVER access another tenant's data
when RLS is properly configured.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Type
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import text, event
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import Pool

logger = logging.getLogger(__name__)


# ==============================================================================
# RLS Configuration
# ==============================================================================

class RLSPolicyType(Enum):
    """Types of RLS policies."""
    PERMISSIVE = "PERMISSIVE"  # Default - combines with OR
    RESTRICTIVE = "RESTRICTIVE"  # Combines with AND


class RLSCommand(Enum):
    """SQL commands that RLS applies to."""
    ALL = "ALL"
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass
class RLSPolicy:
    """
    Definition of a Row-Level Security policy.
    
    Attributes:
        name: Unique policy name
        table_name: Table this policy applies to
        policy_type: PERMISSIVE or RESTRICTIVE
        command: Which SQL commands this applies to
        using_expr: Expression for SELECT/UPDATE/DELETE
        check_expr: Expression for INSERT/UPDATE
        roles: List of roles this policy applies to
    """
    name: str
    table_name: str
    policy_type: RLSPolicyType = RLSPolicyType.PERMISSIVE
    command: RLSCommand = RLSCommand.ALL
    using_expr: Optional[str] = None
    check_expr: Optional[str] = None
    roles: List[str] = field(default_factory=list)
    
    def to_create_sql(self, schema: str = "public") -> str:
        """Generate CREATE POLICY SQL statement."""
        parts = [
            f"CREATE POLICY {self.name}",
            f"ON {schema}.{self.table_name}",
            f"AS {self.policy_type.value}",
            f"FOR {self.command.value}",
        ]
        
        if self.roles:
            roles_str = ", ".join(self.roles)
            parts.append(f"TO {roles_str}")
        
        if self.using_expr:
            parts.append(f"USING ({self.using_expr})")
        
        if self.check_expr:
            parts.append(f"WITH CHECK ({self.check_expr})")
        
        return "\n".join(parts) + ";"
    
    def to_drop_sql(self, schema: str = "public") -> str:
        """Generate DROP POLICY SQL statement."""
        return f"DROP POLICY IF EXISTS {self.name} ON {schema}.{self.table_name};"


# ==============================================================================
# RLS Manager
# ==============================================================================

class RLSManager:
    """
    Manages Row-Level Security policies for tenant isolation.
    
    This is the CRITICAL component for database-level security.
    
    Architecture:
    1. Each multi-tenant table has a tenant_id column
    2. RLS policies restrict access to rows matching current_setting('app.tenant_id')
    3. Connection setup MUST set this variable before any queries
    
    Example:
        manager = RLSManager(engine)
        
        # Enable RLS on a table
        manager.enable_rls("predictions")
        
        # Create isolation policy
        manager.create_tenant_isolation_policy("predictions")
        
        # In each request, set the tenant
        manager.set_tenant_for_connection(connection, "pilot_hospital_001")
    """
    
    # Application setting for tenant ID
    TENANT_SETTING = "app.tenant_id"
    
    # Tables that should have RLS
    MULTI_TENANT_TABLES = [
        "predictions",
        "alerts",
        "patient_data",
        "model_versions",
        "feature_cache",
        "audit_logs",
        "user_feedback",
        "system_events",
        "performance_metrics",
        "hospital_config",
    ]
    
    def __init__(
        self,
        engine: Engine,
        schema: str = "public",
    ):
        """
        Initialize RLS manager.
        
        Args:
            engine: SQLAlchemy engine
            schema: Database schema (default: public)
        """
        self.engine = engine
        self.schema = schema
        self._policies: Dict[str, List[RLSPolicy]] = {}
    
    # =========================================================================
    # RLS Enable/Disable
    # =========================================================================
    
    def enable_rls(self, table_name: str) -> None:
        """
        Enable Row-Level Security on a table.
        
        Args:
            table_name: Name of the table
        """
        sql = f"""
        ALTER TABLE {self.schema}.{table_name}
        ENABLE ROW LEVEL SECURITY;
        """
        
        with self.engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        logger.info(f"Enabled RLS on {self.schema}.{table_name}")
    
    def disable_rls(self, table_name: str) -> None:
        """
        Disable Row-Level Security on a table.
        
        WARNING: This removes ALL tenant isolation for the table!
        """
        sql = f"""
        ALTER TABLE {self.schema}.{table_name}
        DISABLE ROW LEVEL SECURITY;
        """
        
        with self.engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        logger.warning(f"DISABLED RLS on {self.schema}.{table_name}")
    
    def force_rls_for_owner(self, table_name: str, force: bool = True) -> None:
        """
        Force RLS even for table owner.
        
        By default, RLS is bypassed for the table owner.
        This forces RLS to apply to everyone.
        
        SECURITY: Enable this in production!
        """
        action = "FORCE" if force else "NO FORCE"
        
        sql = f"""
        ALTER TABLE {self.schema}.{table_name}
        {action} ROW LEVEL SECURITY;
        """
        
        with self.engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        logger.info(f"Set {action} RLS on {self.schema}.{table_name}")
    
    # =========================================================================
    # Policy Management
    # =========================================================================
    
    def create_policy(self, policy: RLSPolicy) -> None:
        """
        Create an RLS policy.
        
        Args:
            policy: RLSPolicy definition
        """
        sql = policy.to_create_sql(self.schema)
        
        with self.engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        # Track policy
        if policy.table_name not in self._policies:
            self._policies[policy.table_name] = []
        self._policies[policy.table_name].append(policy)
        
        logger.info(f"Created RLS policy {policy.name} on {policy.table_name}")
    
    def drop_policy(self, policy_name: str, table_name: str) -> None:
        """
        Drop an RLS policy.
        
        Args:
            policy_name: Name of the policy
            table_name: Table the policy is on
        """
        sql = f"""
        DROP POLICY IF EXISTS {policy_name} ON {self.schema}.{table_name};
        """
        
        with self.engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        # Remove from tracking
        if table_name in self._policies:
            self._policies[table_name] = [
                p for p in self._policies[table_name]
                if p.name != policy_name
            ]
        
        logger.info(f"Dropped RLS policy {policy_name} from {table_name}")
    
    def create_tenant_isolation_policy(
        self,
        table_name: str,
        tenant_column: str = "tenant_id",
        policy_name: Optional[str] = None,
    ) -> RLSPolicy:
        """
        Create standard tenant isolation policy.
        
        This is the PRIMARY isolation policy that:
        - Filters SELECT to only tenant's rows
        - Validates INSERT has correct tenant_id
        - Filters UPDATE/DELETE to only tenant's rows
        
        Args:
            table_name: Name of the table
            tenant_column: Column containing tenant ID
            policy_name: Optional custom policy name
        
        Returns:
            Created RLSPolicy
        """
        if policy_name is None:
            policy_name = f"tenant_isolation_{table_name}"
        
        # The isolation expression
        isolation_expr = f"{tenant_column} = current_setting('{self.TENANT_SETTING}')"
        
        policy = RLSPolicy(
            name=policy_name,
            table_name=table_name,
            policy_type=RLSPolicyType.PERMISSIVE,
            command=RLSCommand.ALL,
            using_expr=isolation_expr,
            check_expr=isolation_expr,
        )
        
        self.create_policy(policy)
        
        return policy
    
    def create_admin_bypass_policy(
        self,
        table_name: str,
        admin_role: str = "phoenix_admin",
        policy_name: Optional[str] = None,
    ) -> RLSPolicy:
        """
        Create admin bypass policy.
        
        Allows admin role to access all rows regardless of tenant.
        Use carefully - this is for system-level operations only.
        
        Args:
            table_name: Name of the table
            admin_role: Role that can bypass RLS
            policy_name: Optional custom policy name
        
        Returns:
            Created RLSPolicy
        """
        if policy_name is None:
            policy_name = f"admin_bypass_{table_name}"
        
        policy = RLSPolicy(
            name=policy_name,
            table_name=table_name,
            policy_type=RLSPolicyType.PERMISSIVE,
            command=RLSCommand.ALL,
            using_expr="true",
            check_expr="true",
            roles=[admin_role],
        )
        
        self.create_policy(policy)
        
        return policy
    
    # =========================================================================
    # Connection Setup
    # =========================================================================
    
    def set_tenant_for_connection(
        self,
        connection: Connection,
        tenant_id: str,
    ) -> None:
        """
        Set tenant context for a database connection.
        
        CRITICAL: This MUST be called before any queries on the connection.
        
        Args:
            connection: SQLAlchemy connection
            tenant_id: Current tenant ID
        """
        # Use SET LOCAL to limit to current transaction
        sql = f"SET LOCAL {self.TENANT_SETTING} = :tenant_id"
        
        connection.execute(text(sql), {"tenant_id": tenant_id})
        
        logger.debug(f"Set connection tenant to {tenant_id}")
    
    def clear_tenant_for_connection(self, connection: Connection) -> None:
        """
        Clear tenant context from a connection.
        
        Call this when returning connection to pool.
        """
        sql = f"RESET {self.TENANT_SETTING}"
        
        connection.execute(text(sql))
        
        logger.debug("Cleared connection tenant")
    
    # =========================================================================
    # Bulk Operations
    # =========================================================================
    
    def setup_all_tables(self) -> None:
        """
        Enable RLS and create isolation policies for all multi-tenant tables.
        
        This is the main setup method for production deployment.
        """
        logger.info("Setting up RLS for all multi-tenant tables...")
        
        for table_name in self.MULTI_TENANT_TABLES:
            try:
                # Check if table exists
                if not self._table_exists(table_name):
                    logger.warning(f"Table {table_name} does not exist, skipping")
                    continue
                
                # Enable RLS
                self.enable_rls(table_name)
                
                # Force RLS for table owner
                self.force_rls_for_owner(table_name, force=True)
                
                # Create tenant isolation policy
                self.create_tenant_isolation_policy(table_name)
                
            except Exception as e:
                logger.error(f"Failed to setup RLS for {table_name}: {e}")
                raise
        
        logger.info("RLS setup complete for all tables")
    
    def verify_rls_enabled(self) -> Dict[str, bool]:
        """
        Verify RLS is enabled on all multi-tenant tables.
        
        Returns:
            Dictionary mapping table name to RLS status
        """
        results = {}
        
        for table_name in self.MULTI_TENANT_TABLES:
            if not self._table_exists(table_name):
                results[table_name] = False
                continue
            
            sql = """
            SELECT relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = :table_name
            AND relnamespace = (
                SELECT oid FROM pg_namespace WHERE nspname = :schema
            );
            """
            
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(sql),
                    {"table_name": table_name, "schema": self.schema}
                ).fetchone()
                
                if result:
                    # Both RLS enabled and forced
                    results[table_name] = result[0] and result[1]
                else:
                    results[table_name] = False
        
        return results
    
    def list_policies(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all RLS policies from the database.
        
        Args:
            table_name: Optional filter by table name
        
        Returns:
            List of policy information dictionaries
        """
        sql = """
        SELECT
            pol.polname as policy_name,
            tab.relname as table_name,
            CASE pol.polpermissive WHEN true THEN 'PERMISSIVE' ELSE 'RESTRICTIVE' END as policy_type,
            CASE pol.polcmd
                WHEN 'r' THEN 'SELECT'
                WHEN 'a' THEN 'INSERT'
                WHEN 'w' THEN 'UPDATE'
                WHEN 'd' THEN 'DELETE'
                WHEN '*' THEN 'ALL'
            END as command,
            pg_get_expr(pol.polqual, pol.polrelid) as using_expr,
            pg_get_expr(pol.polwithcheck, pol.polrelid) as check_expr
        FROM pg_policy pol
        JOIN pg_class tab ON pol.polrelid = tab.oid
        JOIN pg_namespace ns ON tab.relnamespace = ns.oid
        WHERE ns.nspname = :schema
        """
        
        params = {"schema": self.schema}
        
        if table_name:
            sql += " AND tab.relname = :table_name"
            params["table_name"] = table_name
        
        with self.engine.connect() as conn:
            results = conn.execute(text(sql), params).fetchall()
        
        return [
            {
                "policy_name": r[0],
                "table_name": r[1],
                "policy_type": r[2],
                "command": r[3],
                "using_expr": r[4],
                "check_expr": r[5],
            }
            for r in results
        ]
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        sql = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = :schema
            AND table_name = :table_name
        );
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(
                text(sql),
                {"schema": self.schema, "table_name": table_name}
            ).scalar()
        
        return bool(result)


# ==============================================================================
# Connection Event Handlers
# ==============================================================================

def setup_rls_connection_events(
    engine: Engine,
    get_tenant_id: callable,
) -> None:
    """
    Setup SQLAlchemy event handlers for automatic tenant setting.
    
    This automatically sets the tenant ID when a connection is checked
    out from the pool, and clears it when returned.
    
    Args:
        engine: SQLAlchemy engine
        get_tenant_id: Callable that returns current tenant ID or None
    """
    manager = RLSManager(engine)
    
    @event.listens_for(Pool, "checkout")
    def on_checkout(dbapi_connection, connection_record, connection_proxy):
        """Set tenant when connection is checked out."""
        tenant_id = get_tenant_id()
        
        if tenant_id:
            cursor = dbapi_connection.cursor()
            cursor.execute(
                f"SET LOCAL {RLSManager.TENANT_SETTING} = %s",
                (tenant_id,)
            )
            cursor.close()
    
    @event.listens_for(Pool, "checkin")
    def on_checkin(dbapi_connection, connection_record):
        """Clear tenant when connection is returned."""
        cursor = dbapi_connection.cursor()
        cursor.execute(f"RESET {RLSManager.TENANT_SETTING}")
        cursor.close()
    
    logger.info("Setup RLS connection event handlers")


# ==============================================================================
# RLS Testing Utilities
# ==============================================================================

class RLSTestHelper:
    """
    Helper for testing RLS policies.
    
    Provides utilities to verify tenant isolation is working correctly.
    """
    
    def __init__(self, engine: Engine, manager: RLSManager):
        self.engine = engine
        self.manager = manager
    
    def verify_tenant_isolation(
        self,
        table_name: str,
        tenant_a: str,
        tenant_b: str,
    ) -> bool:
        """
        Verify that tenants cannot see each other's data.
        
        Args:
            table_name: Table to test
            tenant_a: First tenant
            tenant_b: Second tenant
        
        Returns:
            True if isolation is working correctly
        """
        with self.engine.connect() as conn:
            # Insert test data for tenant_a
            self.manager.set_tenant_for_connection(conn, tenant_a)
            conn.execute(text(f"""
                INSERT INTO {table_name} (tenant_id, test_data)
                VALUES (:tenant_id, 'test_data_a')
            """), {"tenant_id": tenant_a})
            
            # Insert test data for tenant_b
            self.manager.set_tenant_for_connection(conn, tenant_b)
            conn.execute(text(f"""
                INSERT INTO {table_name} (tenant_id, test_data)
                VALUES (:tenant_id, 'test_data_b')
            """), {"tenant_id": tenant_b})
            
            # Verify tenant_a can only see their data
            self.manager.set_tenant_for_connection(conn, tenant_a)
            result_a = conn.execute(text(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE test_data IN ('test_data_a', 'test_data_b')
            """)).scalar()
            
            # Should only see 1 row (their own)
            if result_a != 1:
                logger.error(f"Tenant isolation FAILED: {tenant_a} sees {result_a} rows")
                return False
            
            # Verify tenant_b can only see their data
            self.manager.set_tenant_for_connection(conn, tenant_b)
            result_b = conn.execute(text(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE test_data IN ('test_data_a', 'test_data_b')
            """)).scalar()
            
            if result_b != 1:
                logger.error(f"Tenant isolation FAILED: {tenant_b} sees {result_b} rows")
                return False
            
            # Cleanup
            conn.execute(text(f"""
                DELETE FROM {table_name}
                WHERE test_data IN ('test_data_a', 'test_data_b')
            """))
            conn.commit()
        
        logger.info(f"Tenant isolation VERIFIED for {table_name}")
        return True
    
    def test_cross_tenant_insert(
        self,
        table_name: str,
        attacker_tenant: str,
        victim_tenant: str,
    ) -> bool:
        """
        Test that a tenant cannot insert data for another tenant.
        
        Returns:
            True if the attack was BLOCKED (good)
        """
        with self.engine.connect() as conn:
            self.manager.set_tenant_for_connection(conn, attacker_tenant)
            
            try:
                # Attempt to insert with victim's tenant_id
                conn.execute(text(f"""
                    INSERT INTO {table_name} (tenant_id, test_data)
                    VALUES (:tenant_id, 'malicious_data')
                """), {"tenant_id": victim_tenant})
                conn.commit()
                
                # If we get here, the attack succeeded (BAD)
                logger.error(
                    f"SECURITY BREACH: {attacker_tenant} inserted data for {victim_tenant}"
                )
                return False
                
            except Exception as e:
                # Expected - RLS should block this
                logger.info(f"Cross-tenant insert correctly blocked: {e}")
                conn.rollback()
                return True
