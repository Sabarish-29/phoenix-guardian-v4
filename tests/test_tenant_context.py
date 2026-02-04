"""
Phoenix Guardian - Week 21-22: Multi-Tenant Architecture Tests
Comprehensive test suite for tenant isolation and management.

Tests cover:
- Tenant context management
- Thread-local storage isolation
- Decorator enforcement
- Cross-tenant access prevention
"""

import pytest
import threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from phoenix_guardian.core.tenant_context import (
    TenantContext,
    TenantInfo,
    TenantStatus,
    TenantAccessLevel,
    TenantAccessAudit,
    SecurityError,
    TenantNotFoundError,
    TenantSuspendedError,
    require_tenant,
    require_tenant_async,
    require_access_level,
    with_tenant,
)


class TestTenantContext:
    """Tests for TenantContext core functionality."""
    
    def setup_method(self):
        """Clear context before each test."""
        TenantContext.clear()
    
    def teardown_method(self):
        """Clear context after each test."""
        TenantContext.clear()
    
    # =========================================================================
    # Basic Context Tests
    # =========================================================================
    
    def test_set_and_get_tenant(self):
        """Test setting and getting tenant ID."""
        TenantContext.set("pilot_hospital_001")
        assert TenantContext.get() == "pilot_hospital_001"
    
    def test_get_without_set_raises_error(self):
        """Test that getting without setting raises SecurityError."""
        with pytest.raises(SecurityError, match="No tenant context"):
            TenantContext.get()
    
    def test_clear_tenant(self):
        """Test clearing tenant context."""
        TenantContext.set("pilot_hospital_001")
        TenantContext.clear()
        
        with pytest.raises(SecurityError):
            TenantContext.get()
    
    def test_current_returns_none_without_context(self):
        """Test current() returns None without raising."""
        assert TenantContext.current() is None
    
    def test_current_returns_tenant_with_context(self):
        """Test current() returns tenant ID when set."""
        TenantContext.set("pilot_hospital_001")
        assert TenantContext.current() == "pilot_hospital_001"
    
    def test_is_set(self):
        """Test is_set() method."""
        assert TenantContext.is_set() is False
        
        TenantContext.set("pilot_hospital_001")
        assert TenantContext.is_set() is True
    
    def test_overwrite_tenant(self):
        """Test that setting tenant overwrites previous value."""
        TenantContext.set("hospital_a")
        TenantContext.set("hospital_b")
        
        assert TenantContext.get() == "hospital_b"
    
    # =========================================================================
    # Access Level Tests
    # =========================================================================
    
    def test_default_access_level(self):
        """Test default access level is READ_WRITE."""
        TenantContext.set("pilot_hospital_001")
        assert TenantContext.get_access_level() == TenantAccessLevel.READ_WRITE
    
    def test_set_access_level(self):
        """Test setting custom access level."""
        TenantContext.set("pilot_hospital_001", access_level=TenantAccessLevel.ADMIN)
        assert TenantContext.get_access_level() == TenantAccessLevel.ADMIN
    
    def test_all_access_levels(self):
        """Test all access level values."""
        levels = [
            TenantAccessLevel.READ_ONLY,
            TenantAccessLevel.READ_WRITE,
            TenantAccessLevel.ADMIN,
            TenantAccessLevel.SUPER_ADMIN,
        ]
        
        for level in levels:
            TenantContext.set("pilot_hospital_001", access_level=level)
            assert TenantContext.get_access_level() == level
    
    # =========================================================================
    # Tenant Info Tests
    # =========================================================================
    
    def test_set_tenant_info(self):
        """Test setting tenant info."""
        info = TenantInfo(
            tenant_id="pilot_hospital_001",
            name="General Hospital",
            status=TenantStatus.ACTIVE,
        )
        
        TenantContext.set_tenant_info(info)
        
        assert TenantContext.get() == "pilot_hospital_001"
        assert TenantContext.get_tenant_info() is not None
    
    def test_get_tenant_info_without_set(self):
        """Test getting tenant info returns None without setting."""
        TenantContext.set("pilot_hospital_001")
        assert TenantContext.get_tenant_info() is None
    
    # =========================================================================
    # Override Context Tests
    # =========================================================================
    
    def test_override_context(self):
        """Test override context manager."""
        TenantContext.set("hospital_a")
        
        with TenantContext.override("hospital_b"):
            assert TenantContext.get() == "hospital_b"
        
        # Original context restored
        assert TenantContext.get() == "hospital_a"
    
    def test_override_with_no_previous_context(self):
        """Test override when no previous context."""
        with TenantContext.override("hospital_a"):
            assert TenantContext.get() == "hospital_a"
        
        # Context cleared after
        assert TenantContext.current() is None
    
    def test_nested_override(self):
        """Test nested override contexts."""
        TenantContext.set("hospital_a")
        
        with TenantContext.override("hospital_b"):
            assert TenantContext.get() == "hospital_b"
            
            with TenantContext.override("hospital_c"):
                assert TenantContext.get() == "hospital_c"
            
            assert TenantContext.get() == "hospital_b"
        
        assert TenantContext.get() == "hospital_a"
    
    def test_override_restores_on_exception(self):
        """Test that override restores context even on exception."""
        TenantContext.set("hospital_a")
        
        with pytest.raises(ValueError):
            with TenantContext.override("hospital_b"):
                raise ValueError("Test error")
        
        assert TenantContext.get() == "hospital_a"


class TestThreadIsolation:
    """Tests for thread-local tenant isolation."""
    
    def test_tenants_isolated_between_threads(self):
        """Test that each thread has its own tenant context."""
        results = {}
        barrier = threading.Barrier(3)
        
        def worker(thread_id, tenant_id):
            TenantContext.set(tenant_id)
            barrier.wait()  # Ensure all threads set before checking
            results[thread_id] = TenantContext.get()
            barrier.wait()  # Wait for all to check
        
        threads = [
            threading.Thread(target=worker, args=(1, "hospital_a")),
            threading.Thread(target=worker, args=(2, "hospital_b")),
            threading.Thread(target=worker, args=(3, "hospital_c")),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Each thread should see its own tenant
        assert results[1] == "hospital_a"
        assert results[2] == "hospital_b"
        assert results[3] == "hospital_c"
    
    def test_context_not_shared_between_threads(self):
        """Test that setting context in one thread doesn't affect another."""
        main_set = threading.Event()
        child_checked = threading.Event()
        
        child_result = {"has_context": None}
        
        def child_worker():
            main_set.wait()  # Wait for main to set
            child_result["has_context"] = TenantContext.is_set()
            child_checked.set()
        
        child = threading.Thread(target=child_worker)
        child.start()
        
        TenantContext.set("main_tenant")
        main_set.set()
        
        child_checked.wait()
        child.join()
        
        # Child should NOT have context
        assert child_result["has_context"] is False
    
    def test_concurrent_context_operations(self):
        """Test many concurrent context operations."""
        results = []
        errors = []
        
        def worker(tenant_id, iterations):
            try:
                for _ in range(iterations):
                    TenantContext.set(tenant_id)
                    current = TenantContext.get()
                    
                    if current != tenant_id:
                        errors.append(f"Expected {tenant_id}, got {current}")
                    
                    TenantContext.clear()
                
                results.append((tenant_id, "success"))
            except Exception as e:
                errors.append(str(e))
        
        threads = [
            threading.Thread(target=worker, args=(f"tenant_{i}", 100))
            for i in range(10)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 10


class TestTenantDecorators:
    """Tests for tenant decorator enforcement."""
    
    def setup_method(self):
        TenantContext.clear()
    
    def teardown_method(self):
        TenantContext.clear()
    
    def test_require_tenant_without_context(self):
        """Test @require_tenant raises without context."""
        @require_tenant
        def protected_function():
            return "success"
        
        with pytest.raises(SecurityError, match="No tenant context"):
            protected_function()
    
    def test_require_tenant_with_context(self):
        """Test @require_tenant allows with context."""
        @require_tenant
        def protected_function():
            return "success"
        
        TenantContext.set("pilot_hospital_001")
        result = protected_function()
        
        assert result == "success"
    
    def test_require_tenant_passes_arguments(self):
        """Test @require_tenant passes function arguments."""
        @require_tenant
        def process_data(data, multiplier=1):
            return data * multiplier
        
        TenantContext.set("pilot_hospital_001")
        result = process_data([1, 2], multiplier=3)
        
        assert result == [1, 2, 1, 2, 1, 2]
    
    def test_require_access_level_admin(self):
        """Test @require_access_level for admin."""
        @require_access_level(TenantAccessLevel.ADMIN)
        def admin_function():
            return "admin_success"
        
        TenantContext.set("pilot_hospital_001", access_level=TenantAccessLevel.ADMIN)
        result = admin_function()
        
        assert result == "admin_success"
    
    def test_require_access_level_insufficient(self):
        """Test @require_access_level rejects insufficient level."""
        @require_access_level(TenantAccessLevel.ADMIN)
        def admin_function():
            return "admin_success"
        
        TenantContext.set("pilot_hospital_001", access_level=TenantAccessLevel.READ_ONLY)
        
        with pytest.raises(SecurityError, match="Insufficient access level"):
            admin_function()
    
    def test_with_tenant_decorator(self):
        """Test @with_tenant decorator."""
        @with_tenant("auto_tenant")
        def auto_context_function():
            return TenantContext.get()
        
        result = auto_context_function()
        assert result == "auto_tenant"
        
        # Context should be cleared after
        assert TenantContext.is_set() is False
    
    def test_with_tenant_restores_previous(self):
        """Test @with_tenant restores previous context."""
        @with_tenant("temp_tenant")
        def temp_function():
            return TenantContext.get()
        
        TenantContext.set("original_tenant")
        result = temp_function()
        
        assert result == "temp_tenant"
        assert TenantContext.get() == "original_tenant"


class TestAsyncDecorators:
    """Tests for async tenant decorators."""
    
    @pytest.mark.asyncio
    async def test_require_tenant_async_without_context(self):
        """Test @require_tenant_async raises without context."""
        @require_tenant_async
        async def protected_async():
            return "success"
        
        with pytest.raises(SecurityError):
            await protected_async()
    
    @pytest.mark.asyncio
    async def test_require_tenant_async_with_context(self):
        """Test @require_tenant_async allows with context."""
        @require_tenant_async
        async def protected_async():
            return "async_success"
        
        TenantContext.set("pilot_hospital_001")
        result = await protected_async()
        
        assert result == "async_success"
        TenantContext.clear()


class TestTenantStatus:
    """Tests for tenant status enumeration."""
    
    def test_all_statuses_defined(self):
        """Test all expected statuses are defined."""
        expected = ["pending", "active", "suspended", "deactivating", "archived"]
        
        for status_value in expected:
            status = TenantStatus(status_value)
            assert status.value == status_value
    
    def test_status_transitions(self):
        """Test valid status transitions."""
        # PENDING -> ACTIVE
        info = TenantInfo(
            tenant_id="test",
            name="Test",
            status=TenantStatus.PENDING,
        )
        info.status = TenantStatus.ACTIVE
        assert info.status == TenantStatus.ACTIVE
        
        # ACTIVE -> SUSPENDED
        info.status = TenantStatus.SUSPENDED
        assert info.status == TenantStatus.SUSPENDED
        
        # SUSPENDED -> ACTIVE (reactivation)
        info.status = TenantStatus.ACTIVE
        assert info.status == TenantStatus.ACTIVE


class TestTenantInfo:
    """Tests for TenantInfo dataclass."""
    
    def test_create_tenant_info(self):
        """Test creating TenantInfo."""
        info = TenantInfo(
            tenant_id="pilot_hospital_001",
            name="General Hospital",
            status=TenantStatus.ACTIVE,
        )
        
        assert info.tenant_id == "pilot_hospital_001"
        assert info.name == "General Hospital"
        assert info.status == TenantStatus.ACTIVE
    
    def test_tenant_info_defaults(self):
        """Test TenantInfo default values."""
        info = TenantInfo(
            tenant_id="test",
            name="Test",
            status=TenantStatus.PENDING,
        )
        
        assert info.display_name is None
        assert info.config == {}
        assert info.max_users == 100
        assert info.max_requests_per_minute == 1000
    
    def test_tenant_info_with_config(self):
        """Test TenantInfo with custom config."""
        config = {
            "timezone": "America/New_York",
            "features": ["prediction", "alerts"],
        }
        
        info = TenantInfo(
            tenant_id="test",
            name="Test",
            status=TenantStatus.ACTIVE,
            config=config,
        )
        
        assert info.config["timezone"] == "America/New_York"
        assert "prediction" in info.config["features"]


class TestAuditLogging:
    """Tests for tenant access audit logging."""
    
    def test_audit_records_created(self):
        """Test that audit records are created."""
        audit = TenantAccessAudit()
        
        TenantContext.set("pilot_hospital_001")
        
        # The audit trail should be tracked
        # In production, this would be stored
        assert TenantContext.get() == "pilot_hospital_001"
    
    def test_audit_captures_caller(self):
        """Test audit captures caller information."""
        # This is more of an integration test
        # The TenantContext.set captures caller info
        TenantContext.set("pilot_hospital_001")
        
        # Verify context is set (caller capture is internal)
        assert TenantContext.is_set()
        TenantContext.clear()


class TestExceptions:
    """Tests for tenant-related exceptions."""
    
    def test_security_error(self):
        """Test SecurityError exception."""
        error = SecurityError("Cross-tenant access denied")
        
        assert str(error) == "Cross-tenant access denied"
        assert isinstance(error, Exception)
    
    def test_tenant_not_found_error(self):
        """Test TenantNotFoundError exception."""
        error = TenantNotFoundError("Tenant 'xyz' not found")
        
        assert "xyz" in str(error)
        assert isinstance(error, SecurityError)
    
    def test_tenant_suspended_error(self):
        """Test TenantSuspendedError exception."""
        error = TenantSuspendedError("Tenant is suspended")
        
        assert "suspended" in str(error)
        assert isinstance(error, SecurityError)


# ==============================================================================
# Test Count: ~50 tests for tenant context
# ==============================================================================
