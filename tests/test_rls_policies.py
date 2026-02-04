"""
Phoenix Guardian - Week 21-22: RLS Policies Tests
Tests for PostgreSQL Row-Level Security policies.

These tests validate:
- RLS policies are correctly created
- Tenant isolation at database level
- Admin bypass functionality
- Policy management operations
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timezone

from phoenix_guardian.database.rls_policies import (
    RLSPolicy,
    RLSPolicyType,
    RLSCommand,
    RLSManager,
    RLSTestHelper,
)


class TestRLSPolicy:
    """Tests for RLSPolicy dataclass."""
    
    def test_create_policy(self):
        """Test creating an RLS policy."""
        policy = RLSPolicy(
            name="tenant_isolation",
            table_name="predictions",
            policy_type=RLSPolicyType.PERMISSIVE,
            command=RLSCommand.ALL,
            using_expression="tenant_id = current_setting('app.tenant_id')",
        )
        
        assert policy.name == "tenant_isolation"
        assert policy.table_name == "predictions"
        assert policy.policy_type == RLSPolicyType.PERMISSIVE
        assert policy.command == RLSCommand.ALL
    
    def test_policy_with_check_expression(self):
        """Test policy with WITH CHECK expression."""
        policy = RLSPolicy(
            name="tenant_write",
            table_name="alerts",
            policy_type=RLSPolicyType.PERMISSIVE,
            command=RLSCommand.INSERT,
            using_expression="true",
            check_expression="tenant_id = current_setting('app.tenant_id')",
        )
        
        assert policy.check_expression is not None
    
    def test_policy_for_specific_roles(self):
        """Test policy targeting specific roles."""
        policy = RLSPolicy(
            name="admin_bypass",
            table_name="predictions",
            policy_type=RLSPolicyType.PERMISSIVE,
            command=RLSCommand.ALL,
            using_expression="true",
            roles=["phoenix_admin"],
        )
        
        assert "phoenix_admin" in policy.roles
    
    def test_restrictive_policy(self):
        """Test restrictive policy type."""
        policy = RLSPolicy(
            name="deny_deleted",
            table_name="predictions",
            policy_type=RLSPolicyType.RESTRICTIVE,
            command=RLSCommand.SELECT,
            using_expression="deleted = false",
        )
        
        assert policy.policy_type == RLSPolicyType.RESTRICTIVE


class TestRLSCommand:
    """Tests for RLSCommand enum."""
    
    def test_all_commands(self):
        """Test all RLS commands exist."""
        assert RLSCommand.ALL.value == "ALL"
        assert RLSCommand.SELECT.value == "SELECT"
        assert RLSCommand.INSERT.value == "INSERT"
        assert RLSCommand.UPDATE.value == "UPDATE"
        assert RLSCommand.DELETE.value == "DELETE"


class TestRLSPolicyType:
    """Tests for RLSPolicyType enum."""
    
    def test_policy_types(self):
        """Test policy types."""
        assert RLSPolicyType.PERMISSIVE.value == "PERMISSIVE"
        assert RLSPolicyType.RESTRICTIVE.value == "RESTRICTIVE"


class TestRLSManager:
    """Tests for RLSManager class."""
    
    def setup_method(self):
        """Set up mock database connection."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__ = Mock(return_value=self.mock_cursor)
        self.mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        self.manager = RLSManager(self.mock_conn)
    
    # =========================================================================
    # Enable RLS
    # =========================================================================
    
    def test_enable_rls(self):
        """Test enabling RLS on a table."""
        self.manager.enable_rls("predictions")
        
        self.mock_cursor.execute.assert_called()
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "ALTER TABLE" in sql
        assert "ENABLE ROW LEVEL SECURITY" in sql
    
    def test_enable_rls_force(self):
        """Test enabling RLS with FORCE."""
        self.manager.enable_rls("predictions", force=True)
        
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "FORCE ROW LEVEL SECURITY" in sql
    
    def test_disable_rls(self):
        """Test disabling RLS on a table."""
        self.manager.disable_rls("predictions")
        
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "DISABLE ROW LEVEL SECURITY" in sql
    
    # =========================================================================
    # Create Policies
    # =========================================================================
    
    def test_create_tenant_isolation_policy(self):
        """Test creating tenant isolation policy."""
        self.manager.create_tenant_isolation_policy("predictions")
        
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "CREATE POLICY" in sql
        assert "tenant_isolation_predictions" in sql
        assert "current_setting('app.tenant_id')" in sql
    
    def test_create_admin_bypass_policy(self):
        """Test creating admin bypass policy."""
        self.manager.create_admin_bypass_policy("predictions")
        
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "CREATE POLICY" in sql
        assert "admin_bypass_predictions" in sql
        assert "phoenix_admin" in sql
    
    def test_create_custom_policy(self):
        """Test creating custom policy."""
        policy = RLSPolicy(
            name="custom_policy",
            table_name="alerts",
            policy_type=RLSPolicyType.PERMISSIVE,
            command=RLSCommand.SELECT,
            using_expression="severity >= 3",
        )
        
        self.manager.create_policy(policy)
        
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "CREATE POLICY" in sql
        assert "custom_policy" in sql
        assert "severity >= 3" in sql
    
    def test_create_policy_with_check(self):
        """Test creating policy with WITH CHECK."""
        policy = RLSPolicy(
            name="insert_policy",
            table_name="alerts",
            policy_type=RLSPolicyType.PERMISSIVE,
            command=RLSCommand.INSERT,
            using_expression="true",
            check_expression="tenant_id = current_setting('app.tenant_id')",
        )
        
        self.manager.create_policy(policy)
        
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "WITH CHECK" in sql
    
    def test_create_policy_for_roles(self):
        """Test creating policy for specific roles."""
        policy = RLSPolicy(
            name="role_policy",
            table_name="predictions",
            policy_type=RLSPolicyType.PERMISSIVE,
            command=RLSCommand.ALL,
            using_expression="true",
            roles=["app_user", "app_admin"],
        )
        
        self.manager.create_policy(policy)
        
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "TO app_user, app_admin" in sql
    
    # =========================================================================
    # Drop Policies
    # =========================================================================
    
    def test_drop_policy(self):
        """Test dropping a policy."""
        self.manager.drop_policy("tenant_isolation_predictions", "predictions")
        
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "DROP POLICY" in sql
        assert "tenant_isolation_predictions" in sql
    
    def test_drop_policy_if_exists(self):
        """Test dropping policy with IF EXISTS."""
        self.manager.drop_policy(
            "tenant_isolation_predictions",
            "predictions",
            if_exists=True,
        )
        
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "IF EXISTS" in sql
    
    def test_drop_all_policies(self):
        """Test dropping all policies on a table."""
        self.mock_cursor.fetchall.return_value = [
            ("policy1",),
            ("policy2",),
        ]
        
        self.manager.drop_all_policies("predictions")
        
        # Should have called DROP POLICY for each
        assert self.mock_cursor.execute.call_count >= 2
    
    # =========================================================================
    # List Policies
    # =========================================================================
    
    def test_list_policies(self):
        """Test listing policies."""
        self.mock_cursor.fetchall.return_value = [
            ("tenant_isolation_predictions", "predictions", "PERMISSIVE", "ALL"),
            ("admin_bypass_predictions", "predictions", "PERMISSIVE", "ALL"),
        ]
        
        policies = self.manager.list_policies("predictions")
        
        assert len(policies) == 2
        assert policies[0][0] == "tenant_isolation_predictions"
    
    def test_policy_exists(self):
        """Test checking if policy exists."""
        self.mock_cursor.fetchone.return_value = (True,)
        
        exists = self.manager.policy_exists(
            "tenant_isolation_predictions",
            "predictions",
        )
        
        assert exists is True
    
    def test_policy_not_exists(self):
        """Test policy doesn't exist."""
        self.mock_cursor.fetchone.return_value = None
        
        exists = self.manager.policy_exists("nonexistent", "predictions")
        
        assert exists is False
    
    # =========================================================================
    # Bulk Operations
    # =========================================================================
    
    def test_setup_all_tables(self):
        """Test setting up RLS on all tables."""
        tables = ["predictions", "alerts", "patient_data"]
        
        self.manager.setup_all_tables(tables)
        
        # Should enable RLS and create policies for each
        assert self.mock_cursor.execute.call_count >= len(tables) * 2
    
    def test_teardown_all_tables(self):
        """Test tearing down RLS on all tables."""
        tables = ["predictions", "alerts"]
        self.mock_cursor.fetchall.return_value = []
        
        self.manager.teardown_all_tables(tables)
        
        # Should have disabled RLS
        assert self.mock_cursor.execute.call_count >= len(tables)


class TestSetTenantForConnection:
    """Tests for RLSManager.set_tenant_for_connection method."""
    
    def test_set_tenant(self):
        """Test setting tenant for connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        manager = RLSManager(mock_conn)
        manager.set_tenant_for_connection(mock_conn, "hospital_a")
        
        mock_cursor.execute.assert_called()
        sql = mock_cursor.execute.call_args[0][0]
        assert "app.tenant_id" in str(sql)
    
    def test_clear_tenant(self):
        """Test clearing tenant from connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        manager = RLSManager(mock_conn)
        manager.set_tenant_for_connection(mock_conn, None)
        
        mock_cursor.execute.assert_called()


class TestRLSTestHelper:
    """Tests for RLSTestHelper class."""
    
    def setup_method(self):
        """Set up mock connection."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__ = Mock(return_value=self.mock_cursor)
        self.mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        self.helper = RLSTestHelper(self.mock_conn)
    
    def test_verify_isolation_success(self):
        """Test verification of tenant isolation."""
        # Setup mock to return no cross-tenant data
        self.mock_cursor.fetchall.return_value = []
        
        result = self.helper.verify_isolation(
            table="predictions",
            tenant_id="hospital_a",
        )
        
        assert result is True
    
    def test_verify_isolation_failure(self):
        """Test detection of isolation violation."""
        # Setup mock to return cross-tenant data
        self.mock_cursor.fetchall.return_value = [("hospital_b", 5)]
        
        result = self.helper.verify_isolation(
            table="predictions",
            tenant_id="hospital_a",
        )
        
        assert result is False
    
    def test_insert_test_data(self):
        """Test inserting test data."""
        self.helper.insert_test_data(
            table="predictions",
            tenant_id="hospital_a",
            data={"patient_id": "P001", "score": 0.85},
        )
        
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO" in sql
    
    def test_verify_cannot_read_other_tenant(self):
        """Test verification of cross-tenant read block."""
        self.mock_cursor.fetchone.return_value = (0,)
        
        result = self.helper.verify_cannot_read_other_tenant(
            table="predictions",
            own_tenant="hospital_a",
            other_tenant="hospital_b",
        )
        
        assert result is True
    
    def test_cleanup_test_data(self):
        """Test cleanup of test data."""
        self.helper.cleanup_test_data(
            table="predictions",
            tenant_id="hospital_a",
        )
        
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "DELETE FROM" in sql


class TestRLSPolicySQLGeneration:
    """Tests for SQL generation in RLS policies."""
    
    def setup_method(self):
        """Set up mock connection."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__ = Mock(return_value=self.mock_cursor)
        self.mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        self.manager = RLSManager(self.mock_conn)
    
    def test_sql_injection_prevention(self):
        """Test SQL injection is prevented."""
        # Attempt SQL injection in table name
        with pytest.raises(ValueError):
            self.manager.enable_rls("predictions; DROP TABLE users;--")
    
    def test_valid_table_names_only(self):
        """Test only valid table names allowed."""
        valid_tables = ["predictions", "alerts", "patient_data"]
        
        for table in valid_tables:
            # Should not raise
            self.manager.validate_table_name(table)
    
    def test_invalid_table_names_rejected(self):
        """Test invalid table names rejected."""
        invalid_tables = [
            "drop table",
            "predictions--",
            "table';",
            "../etc/passwd",
        ]
        
        for table in invalid_tables:
            with pytest.raises(ValueError):
                self.manager.validate_table_name(table)


class TestRLSIntegration:
    """Integration tests for RLS setup."""
    
    def setup_method(self):
        """Set up mock connection."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__ = Mock(return_value=self.mock_cursor)
        self.mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        self.manager = RLSManager(self.mock_conn)
    
    def test_full_table_setup(self):
        """Test complete table setup with RLS."""
        self.manager.setup_table_with_rls("predictions")
        
        calls = [str(c) for c in self.mock_cursor.execute.call_args_list]
        sql_statements = " ".join(calls)
        
        # Should enable RLS
        assert "ENABLE ROW LEVEL SECURITY" in sql_statements
        # Should create tenant isolation policy
        assert "tenant_isolation" in sql_statements
    
    def test_role_creation(self):
        """Test role creation for RLS."""
        self.manager.create_rls_roles()
        
        calls = [str(c) for c in self.mock_cursor.execute.call_args_list]
        sql_statements = " ".join(calls)
        
        assert "phoenix_admin" in sql_statements
        assert "phoenix_app" in sql_statements


# ==============================================================================
# Test Count: ~50 tests for RLS policies
# ==============================================================================
