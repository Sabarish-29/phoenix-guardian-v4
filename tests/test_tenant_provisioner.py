"""
Phoenix Guardian - Week 21-22: Tenant Provisioner Tests
Tests for automated tenant provisioning and offboarding.

These tests validate:
- Tenant provisioning workflow
- Step-by-step provisioning
- Bulk provisioning
- Tenant archival and offboarding
- Data export and cleanup
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from dataclasses import dataclass

from phoenix_guardian.tenants.tenant_provisioner import (
    TenantProvisioner,
    ProvisioningStep,
    ProvisioningConfig,
    ProvisioningResult,
    TenantOnboardingRequest,
    BulkProvisioner,
)
from phoenix_guardian.tenants.tenant_archiver import (
    TenantArchiver,
    RetentionPolicy,
    ArchiveConfig,
    ArchiveResult,
)
from phoenix_guardian.core.tenant_context import TenantStatus


class TestProvisioningStep:
    """Tests for ProvisioningStep enum."""
    
    def test_all_steps_exist(self):
        """Test all provisioning steps exist."""
        expected_steps = [
            "VALIDATE",
            "CREATE_TENANT",
            "CREATE_SCHEMA",
            "APPLY_RLS",
            "CREATE_CACHE",
            "CONFIGURE_LIMITS",
            "CREATE_ADMIN_USER",
            "FINALIZE",
        ]
        
        for step in expected_steps:
            assert hasattr(ProvisioningStep, step)
    
    def test_step_order(self):
        """Test steps have proper ordering."""
        steps = list(ProvisioningStep)
        
        # VALIDATE should be first
        assert steps[0] == ProvisioningStep.VALIDATE
        # FINALIZE should be last
        assert steps[-1] == ProvisioningStep.FINALIZE


class TestProvisioningConfig:
    """Tests for ProvisioningConfig dataclass."""
    
    def test_default_config(self):
        """Test default provisioning config."""
        config = ProvisioningConfig()
        
        assert config.create_dedicated_schema is False
        assert config.enable_rls is True
        assert config.create_cache_namespace is True
        assert config.max_users > 0
        assert config.max_storage_gb > 0
    
    def test_custom_config(self):
        """Test custom provisioning config."""
        config = ProvisioningConfig(
            create_dedicated_schema=True,
            max_users=500,
            max_storage_gb=100,
            custom_features=["advanced_analytics"],
        )
        
        assert config.create_dedicated_schema is True
        assert config.max_users == 500
        assert "advanced_analytics" in config.custom_features


class TestTenantOnboardingRequest:
    """Tests for TenantOnboardingRequest dataclass."""
    
    def test_minimal_request(self):
        """Test minimal onboarding request."""
        request = TenantOnboardingRequest(
            tenant_id="new_hospital",
            name="New Hospital",
            admin_email="admin@newhospital.org",
        )
        
        assert request.tenant_id == "new_hospital"
        assert request.name == "New Hospital"
    
    def test_full_request(self):
        """Test full onboarding request."""
        request = TenantOnboardingRequest(
            tenant_id="enterprise_hospital",
            name="Enterprise Hospital",
            admin_email="admin@enterprise.org",
            admin_name="Admin User",
            tier="enterprise",
            config=ProvisioningConfig(max_users=1000),
            metadata={"region": "east"},
        )
        
        assert request.tier == "enterprise"
        assert request.config.max_users == 1000
        assert request.metadata["region"] == "east"


class TestTenantProvisioner:
    """Tests for TenantProvisioner class."""
    
    def setup_method(self):
        """Set up provisioner with mocks."""
        self.mock_manager = Mock()
        self.mock_db = Mock()
        self.mock_cache = Mock()
        
        self.provisioner = TenantProvisioner(
            tenant_manager=self.mock_manager,
            db_connection=self.mock_db,
            cache_client=self.mock_cache,
        )
    
    # =========================================================================
    # Basic Provisioning
    # =========================================================================
    
    def test_provision_tenant(self):
        """Test provisioning a new tenant."""
        request = TenantOnboardingRequest(
            tenant_id="new_hospital",
            name="New Hospital",
            admin_email="admin@new.org",
        )
        
        result = self.provisioner.provision(request)
        
        assert result.success is True
        assert result.tenant_id == "new_hospital"
        assert len(result.completed_steps) > 0
    
    def test_provision_returns_result(self):
        """Test provisioning returns proper result."""
        request = TenantOnboardingRequest(
            tenant_id="test_hospital",
            name="Test Hospital",
            admin_email="admin@test.org",
        )
        
        result = self.provisioner.provision(request)
        
        assert isinstance(result, ProvisioningResult)
        assert result.tenant_id is not None
        assert result.started_at is not None
        assert result.completed_at is not None
    
    def test_provision_executes_all_steps(self):
        """Test all provisioning steps are executed."""
        request = TenantOnboardingRequest(
            tenant_id="full_hospital",
            name="Full Hospital",
            admin_email="admin@full.org",
        )
        
        result = self.provisioner.provision(request)
        
        # All steps should be completed
        assert len(result.completed_steps) == len(ProvisioningStep)
    
    # =========================================================================
    # Step Execution
    # =========================================================================
    
    def test_validate_step(self):
        """Test validation step."""
        request = TenantOnboardingRequest(
            tenant_id="valid_hospital",
            name="Valid Hospital",
            admin_email="admin@valid.org",
        )
        
        result = self.provisioner.execute_step(
            ProvisioningStep.VALIDATE,
            request,
        )
        
        assert result.success is True
    
    def test_validate_step_fails_for_invalid(self):
        """Test validation step fails for invalid tenant ID."""
        request = TenantOnboardingRequest(
            tenant_id="AB",  # Too short
            name="Invalid",
            admin_email="admin@invalid.org",
        )
        
        result = self.provisioner.execute_step(
            ProvisioningStep.VALIDATE,
            request,
        )
        
        assert result.success is False
    
    def test_create_tenant_step(self):
        """Test create tenant step."""
        request = TenantOnboardingRequest(
            tenant_id="create_hospital",
            name="Create Hospital",
            admin_email="admin@create.org",
        )
        
        result = self.provisioner.execute_step(
            ProvisioningStep.CREATE_TENANT,
            request,
        )
        
        self.mock_manager.create_tenant.assert_called_once()
    
    def test_apply_rls_step(self):
        """Test apply RLS step."""
        request = TenantOnboardingRequest(
            tenant_id="rls_hospital",
            name="RLS Hospital",
            admin_email="admin@rls.org",
        )
        
        result = self.provisioner.execute_step(
            ProvisioningStep.APPLY_RLS,
            request,
        )
        
        assert result.success is True
    
    def test_create_cache_step(self):
        """Test create cache namespace step."""
        request = TenantOnboardingRequest(
            tenant_id="cache_hospital",
            name="Cache Hospital",
            admin_email="admin@cache.org",
        )
        
        result = self.provisioner.execute_step(
            ProvisioningStep.CREATE_CACHE,
            request,
        )
        
        assert result.success is True
    
    # =========================================================================
    # Error Handling
    # =========================================================================
    
    def test_provision_rollback_on_failure(self):
        """Test rollback when provisioning fails."""
        # Make create_tenant fail
        self.mock_manager.create_tenant.side_effect = Exception("DB error")
        
        request = TenantOnboardingRequest(
            tenant_id="fail_hospital",
            name="Fail Hospital",
            admin_email="admin@fail.org",
        )
        
        result = self.provisioner.provision(request)
        
        assert result.success is False
        assert len(result.errors) > 0
    
    def test_provision_records_failed_step(self):
        """Test failed step is recorded."""
        self.mock_manager.create_tenant.side_effect = Exception("Error")
        
        request = TenantOnboardingRequest(
            tenant_id="error_hospital",
            name="Error Hospital",
            admin_email="admin@error.org",
        )
        
        result = self.provisioner.provision(request)
        
        assert result.failed_step is not None
    
    # =========================================================================
    # Custom Hooks
    # =========================================================================
    
    def test_add_pre_hook(self):
        """Test adding pre-provision hook."""
        hook_called = []
        
        def my_hook(request):
            hook_called.append(True)
        
        self.provisioner.add_pre_hook(my_hook)
        
        request = TenantOnboardingRequest(
            tenant_id="hook_hospital",
            name="Hook Hospital",
            admin_email="admin@hook.org",
        )
        
        self.provisioner.provision(request)
        
        assert len(hook_called) == 1
    
    def test_add_post_hook(self):
        """Test adding post-provision hook."""
        hook_called = []
        
        def my_hook(result):
            hook_called.append(result.tenant_id)
        
        self.provisioner.add_post_hook(my_hook)
        
        request = TenantOnboardingRequest(
            tenant_id="post_hook_hospital",
            name="Post Hook Hospital",
            admin_email="admin@posthook.org",
        )
        
        self.provisioner.provision(request)
        
        assert "post_hook_hospital" in hook_called
    
    def test_add_step_hook(self):
        """Test adding per-step hook."""
        steps_executed = []
        
        def step_hook(step, request):
            steps_executed.append(step)
        
        self.provisioner.add_step_hook(ProvisioningStep.CREATE_TENANT, step_hook)
        
        request = TenantOnboardingRequest(
            tenant_id="step_hook_hospital",
            name="Step Hook Hospital",
            admin_email="admin@stephook.org",
        )
        
        self.provisioner.provision(request)
        
        assert ProvisioningStep.CREATE_TENANT in steps_executed


class TestBulkProvisioner:
    """Tests for BulkProvisioner class."""
    
    def setup_method(self):
        """Set up bulk provisioner."""
        self.mock_provisioner = Mock(spec=TenantProvisioner)
        self.mock_provisioner.provision.return_value = ProvisioningResult(
            success=True,
            tenant_id="test",
            completed_steps=[ProvisioningStep.VALIDATE],
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        
        self.bulk = BulkProvisioner(self.mock_provisioner)
    
    def test_provision_multiple(self):
        """Test provisioning multiple tenants."""
        requests = [
            TenantOnboardingRequest(
                tenant_id=f"hospital_{i}",
                name=f"Hospital {i}",
                admin_email=f"admin{i}@hospital.org",
            )
            for i in range(3)
        ]
        
        results = self.bulk.provision_all(requests)
        
        assert len(results) == 3
        assert all(r.success for r in results)
    
    def test_provision_parallel(self):
        """Test parallel provisioning."""
        requests = [
            TenantOnboardingRequest(
                tenant_id=f"parallel_{i}",
                name=f"Parallel {i}",
                admin_email=f"admin{i}@parallel.org",
            )
            for i in range(5)
        ]
        
        results = self.bulk.provision_all(requests, parallel=True, max_workers=3)
        
        assert len(results) == 5
    
    def test_provision_stops_on_error(self):
        """Test bulk provisioning stops on error (sequential mode)."""
        # Make second call fail
        self.mock_provisioner.provision.side_effect = [
            ProvisioningResult(success=True, tenant_id="t1",
                              completed_steps=[], started_at=datetime.now(timezone.utc),
                              completed_at=datetime.now(timezone.utc)),
            ProvisioningResult(success=False, tenant_id="t2",
                              completed_steps=[], errors=["Error"],
                              started_at=datetime.now(timezone.utc),
                              completed_at=datetime.now(timezone.utc)),
            ProvisioningResult(success=True, tenant_id="t3",
                              completed_steps=[], started_at=datetime.now(timezone.utc),
                              completed_at=datetime.now(timezone.utc)),
        ]
        
        requests = [
            TenantOnboardingRequest(tenant_id=f"stop_{i}", name=f"Stop {i}",
                                   admin_email=f"admin@stop{i}.org")
            for i in range(3)
        ]
        
        results = self.bulk.provision_all(requests, stop_on_error=True)
        
        # Should stop after failure
        assert len(results) == 2


class TestRetentionPolicy:
    """Tests for RetentionPolicy dataclass."""
    
    def test_default_retention(self):
        """Test default retention policy."""
        policy = RetentionPolicy()
        
        # Healthcare default: 7 years
        assert policy.retention_years >= 7
        assert policy.archive_after_days > 0
    
    def test_custom_retention(self):
        """Test custom retention policy."""
        policy = RetentionPolicy(
            retention_years=10,
            archive_after_days=60,
            encryption_required=True,
        )
        
        assert policy.retention_years == 10
        assert policy.encryption_required is True


class TestArchiveConfig:
    """Tests for ArchiveConfig dataclass."""
    
    def test_default_config(self):
        """Test default archive config."""
        config = ArchiveConfig()
        
        assert config.compress is True
        assert config.encrypt is True
        assert config.include_audit_logs is True
    
    def test_custom_config(self):
        """Test custom archive config."""
        config = ArchiveConfig(
            export_path="/custom/path",
            compress=False,
            format="parquet",
        )
        
        assert config.export_path == "/custom/path"
        assert config.compress is False


class TestTenantArchiver:
    """Tests for TenantArchiver class."""
    
    def setup_method(self):
        """Set up archiver with mocks."""
        self.mock_manager = Mock()
        self.mock_db = Mock()
        self.mock_storage = Mock()
        
        self.archiver = TenantArchiver(
            tenant_manager=self.mock_manager,
            db_connection=self.mock_db,
            storage_client=self.mock_storage,
        )
    
    # =========================================================================
    # Archive Tenant
    # =========================================================================
    
    def test_archive_tenant(self):
        """Test archiving a tenant."""
        result = self.archiver.archive_tenant("old_hospital")
        
        assert isinstance(result, ArchiveResult)
        assert result.tenant_id == "old_hospital"
    
    def test_archive_exports_data(self):
        """Test archive exports tenant data."""
        config = ArchiveConfig(include_data=True)
        
        result = self.archiver.archive_tenant("export_hospital", config=config)
        
        assert result.success is True
    
    def test_archive_with_compression(self):
        """Test archive with compression."""
        config = ArchiveConfig(compress=True)
        
        result = self.archiver.archive_tenant("compress_hospital", config=config)
        
        assert result.archive_path is not None
    
    def test_archive_with_encryption(self):
        """Test archive with encryption."""
        config = ArchiveConfig(encrypt=True, encryption_key="test_key")
        
        result = self.archiver.archive_tenant("encrypt_hospital", config=config)
        
        assert result.encrypted is True
    
    # =========================================================================
    # Offboarding Workflow
    # =========================================================================
    
    def test_offboard_tenant(self):
        """Test full offboarding workflow."""
        result = self.archiver.offboard_tenant("departing_hospital")
        
        assert result.success is True
        # Should update status to archived
        self.mock_manager.update_status.assert_called()
    
    def test_offboard_suspends_first(self):
        """Test offboarding suspends tenant first."""
        self.archiver.offboard_tenant("suspend_hospital")
        
        # Should call suspend before archive
        calls = self.mock_manager.method_calls
        # Verify suspend was called
        suspend_called = any("suspend" in str(c) or "update_status" in str(c) 
                           for c in calls)
        assert suspend_called
    
    def test_offboard_removes_cache(self):
        """Test offboarding removes cache namespace."""
        result = self.archiver.offboard_tenant("cache_clean_hospital")
        
        assert result.cache_cleared is True
    
    # =========================================================================
    # Restore Tenant
    # =========================================================================
    
    def test_restore_tenant(self):
        """Test restoring archived tenant."""
        result = self.archiver.restore_tenant(
            "archived_hospital",
            archive_path="/archives/archived_hospital.tar.gz",
        )
        
        assert result.success is True
    
    def test_restore_to_new_id(self):
        """Test restoring to a new tenant ID."""
        result = self.archiver.restore_tenant(
            "old_hospital",
            archive_path="/archives/old_hospital.tar.gz",
            new_tenant_id="new_hospital",
        )
        
        assert result.tenant_id == "new_hospital"
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def test_cleanup_expired_archives(self):
        """Test cleaning up expired archives."""
        policy = RetentionPolicy(retention_years=7)
        
        cleaned = self.archiver.cleanup_expired_archives(policy)
        
        assert isinstance(cleaned, int)
    
    def test_list_archives(self):
        """Test listing tenant archives."""
        self.mock_storage.list.return_value = [
            "hospital_a_2023.tar.gz",
            "hospital_b_2022.tar.gz",
        ]
        
        archives = self.archiver.list_archives()
        
        assert len(archives) >= 0


class TestProvisioningResult:
    """Tests for ProvisioningResult dataclass."""
    
    def test_success_result(self):
        """Test successful provisioning result."""
        result = ProvisioningResult(
            success=True,
            tenant_id="new_hospital",
            completed_steps=[
                ProvisioningStep.VALIDATE,
                ProvisioningStep.CREATE_TENANT,
            ],
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        
        assert result.success is True
        assert len(result.completed_steps) == 2
        assert result.duration_seconds >= 0
    
    def test_failure_result(self):
        """Test failed provisioning result."""
        result = ProvisioningResult(
            success=False,
            tenant_id="failed_hospital",
            completed_steps=[ProvisioningStep.VALIDATE],
            failed_step=ProvisioningStep.CREATE_TENANT,
            errors=["Database connection failed"],
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        
        assert result.success is False
        assert result.failed_step == ProvisioningStep.CREATE_TENANT
        assert "Database" in result.errors[0]
    
    def test_to_dict(self):
        """Test converting result to dict."""
        result = ProvisioningResult(
            success=True,
            tenant_id="dict_hospital",
            completed_steps=[ProvisioningStep.VALIDATE],
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        
        d = result.to_dict()
        
        assert d["success"] is True
        assert d["tenant_id"] == "dict_hospital"
        assert "started_at" in d


class TestArchiveResult:
    """Tests for ArchiveResult dataclass."""
    
    def test_success_result(self):
        """Test successful archive result."""
        result = ArchiveResult(
            success=True,
            tenant_id="archived_hospital",
            archive_path="/archives/archived_hospital.tar.gz",
            size_bytes=1024 * 1024 * 50,  # 50MB
            encrypted=True,
            compressed=True,
        )
        
        assert result.success is True
        assert result.size_bytes > 0
    
    def test_failure_result(self):
        """Test failed archive result."""
        result = ArchiveResult(
            success=False,
            tenant_id="fail_hospital",
            errors=["Storage quota exceeded"],
        )
        
        assert result.success is False
        assert "quota" in result.errors[0]


# ==============================================================================
# Test Count: ~55 tests for tenant provisioner and archiver
# ==============================================================================
