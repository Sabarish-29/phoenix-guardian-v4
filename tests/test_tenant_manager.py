"""
Phoenix Guardian - Week 21-22: Tenant Manager Tests
Tests for tenant lifecycle management.

Tests cover:
- Tenant creation
- Status transitions
- Configuration updates
- Limits management
- Event handling
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from phoenix_guardian.tenants.tenant_manager import (
    TenantManager,
    TenantStorage,
    InMemoryTenantStorage,
    TenantEvent,
    TenantEventData,
)
from phoenix_guardian.core.tenant_context import (
    TenantContext,
    TenantInfo,
    TenantStatus,
    TenantNotFoundError,
)


class TestInMemoryStorage:
    """Tests for in-memory tenant storage."""
    
    def test_save_and_get(self):
        """Test saving and retrieving tenant."""
        storage = InMemoryTenantStorage()
        
        tenant = TenantInfo(
            tenant_id="test_tenant",
            name="Test Tenant",
            status=TenantStatus.PENDING,
        )
        
        storage.save(tenant)
        retrieved = storage.get("test_tenant")
        
        assert retrieved is not None
        assert retrieved.tenant_id == "test_tenant"
        assert retrieved.name == "Test Tenant"
    
    def test_get_nonexistent(self):
        """Test getting non-existent tenant returns None."""
        storage = InMemoryTenantStorage()
        
        result = storage.get("nonexistent")
        
        assert result is None
    
    def test_exists(self):
        """Test exists check."""
        storage = InMemoryTenantStorage()
        
        assert storage.exists("test") is False
        
        storage.save(TenantInfo(
            tenant_id="test",
            name="Test",
            status=TenantStatus.PENDING,
        ))
        
        assert storage.exists("test") is True
    
    def test_delete(self):
        """Test deleting tenant."""
        storage = InMemoryTenantStorage()
        
        storage.save(TenantInfo(
            tenant_id="test",
            name="Test",
            status=TenantStatus.PENDING,
        ))
        
        result = storage.delete("test")
        
        assert result is True
        assert storage.exists("test") is False
    
    def test_delete_nonexistent(self):
        """Test deleting non-existent tenant."""
        storage = InMemoryTenantStorage()
        
        result = storage.delete("nonexistent")
        
        assert result is False
    
    def test_list_all(self):
        """Test listing all tenants."""
        storage = InMemoryTenantStorage()
        
        for i in range(5):
            storage.save(TenantInfo(
                tenant_id=f"tenant_{i}",
                name=f"Tenant {i}",
                status=TenantStatus.ACTIVE,
            ))
        
        tenants = storage.list_all()
        
        assert len(tenants) == 5


class TestTenantManager:
    """Tests for TenantManager."""
    
    def setup_method(self):
        """Setup manager for tests."""
        self.storage = InMemoryTenantStorage()
        self.manager = TenantManager(self.storage)
    
    # =========================================================================
    # Creation Tests
    # =========================================================================
    
    def test_create_tenant(self):
        """Test creating a new tenant."""
        tenant = self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        
        assert tenant.tenant_id == "pilot_hospital_001"
        assert tenant.name == "Pilot Hospital"
        assert tenant.status == TenantStatus.PENDING
    
    def test_create_tenant_with_config(self):
        """Test creating tenant with config."""
        tenant = self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
            config={"timezone": "America/New_York"},
        )
        
        assert tenant.config["timezone"] == "America/New_York"
    
    def test_create_tenant_with_limits(self):
        """Test creating tenant with limits."""
        tenant = self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
            limits={"max_users": 500},
        )
        
        assert tenant.max_users == 500
    
    def test_create_duplicate_tenant_fails(self):
        """Test creating duplicate tenant fails."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        
        with pytest.raises(ValueError, match="already exists"):
            self.manager.create_tenant(
                tenant_id="pilot_hospital_001",
                name="Another Hospital",
            )
    
    def test_create_tenant_invalid_id(self):
        """Test creating tenant with invalid ID."""
        with pytest.raises(ValueError):
            self.manager.create_tenant(
                tenant_id="AB",  # Too short
                name="Test",
            )
        
        with pytest.raises(ValueError):
            self.manager.create_tenant(
                tenant_id="Invalid-ID",  # Uppercase
                name="Test",
            )
    
    # =========================================================================
    # Get/List Tests
    # =========================================================================
    
    def test_get_tenant(self):
        """Test getting a tenant."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        
        tenant = self.manager.get_tenant("pilot_hospital_001")
        
        assert tenant.name == "Pilot Hospital"
    
    def test_get_nonexistent_tenant(self):
        """Test getting non-existent tenant raises error."""
        with pytest.raises(TenantNotFoundError):
            self.manager.get_tenant("nonexistent")
    
    def test_list_tenants(self):
        """Test listing tenants."""
        for i in range(5):
            self.manager.create_tenant(
                tenant_id=f"hospital_{i}",
                name=f"Hospital {i}",
            )
        
        tenants = self.manager.list_tenants()
        
        assert len(tenants) == 5
    
    def test_list_tenants_by_status(self):
        """Test listing tenants by status."""
        for i in range(3):
            self.manager.create_tenant(
                tenant_id=f"hospital_{i}",
                name=f"Hospital {i}",
            )
        
        # Activate one
        self.manager.activate_tenant("hospital_0")
        
        active = self.manager.list_tenants(status=TenantStatus.ACTIVE)
        pending = self.manager.list_tenants(status=TenantStatus.PENDING)
        
        assert len(active) == 1
        assert len(pending) == 2
    
    def test_list_tenants_pagination(self):
        """Test listing tenants with pagination."""
        for i in range(10):
            self.manager.create_tenant(
                tenant_id=f"hospital_{i:02d}",
                name=f"Hospital {i}",
            )
        
        page1 = self.manager.list_tenants(limit=5, offset=0)
        page2 = self.manager.list_tenants(limit=5, offset=5)
        
        assert len(page1) == 5
        assert len(page2) == 5
        assert page1[0].tenant_id != page2[0].tenant_id
    
    # =========================================================================
    # Update Tests
    # =========================================================================
    
    def test_update_tenant(self):
        """Test updating tenant."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        
        tenant = self.manager.update_tenant(
            "pilot_hospital_001",
            name="General Hospital",
            display_name="General Hospital - Main Campus",
        )
        
        assert tenant.name == "General Hospital"
        assert tenant.display_name == "General Hospital - Main Campus"
    
    def test_update_nonexistent_tenant(self):
        """Test updating non-existent tenant raises error."""
        with pytest.raises(TenantNotFoundError):
            self.manager.update_tenant(
                "nonexistent",
                name="New Name",
            )
    
    # =========================================================================
    # Status Transition Tests
    # =========================================================================
    
    def test_activate_tenant(self):
        """Test activating a tenant."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        
        tenant = self.manager.activate_tenant("pilot_hospital_001")
        
        assert tenant.status == TenantStatus.ACTIVE
    
    def test_activate_already_active(self):
        """Test activating already active tenant."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        self.manager.activate_tenant("pilot_hospital_001")
        
        # Should not raise, just return
        tenant = self.manager.activate_tenant("pilot_hospital_001")
        assert tenant.status == TenantStatus.ACTIVE
    
    def test_suspend_tenant(self):
        """Test suspending a tenant."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        self.manager.activate_tenant("pilot_hospital_001")
        
        tenant = self.manager.suspend_tenant(
            "pilot_hospital_001",
            reason="Scheduled maintenance",
        )
        
        assert tenant.status == TenantStatus.SUSPENDED
    
    def test_reactivate_suspended_tenant(self):
        """Test reactivating a suspended tenant."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        self.manager.activate_tenant("pilot_hospital_001")
        self.manager.suspend_tenant("pilot_hospital_001")
        
        tenant = self.manager.activate_tenant("pilot_hospital_001")
        
        assert tenant.status == TenantStatus.ACTIVE
    
    def test_archive_tenant(self):
        """Test archiving a tenant."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        self.manager.activate_tenant("pilot_hospital_001")
        
        tenant = self.manager.archive_tenant("pilot_hospital_001")
        
        assert tenant.status == TenantStatus.ARCHIVED
    
    def test_cannot_activate_archived_tenant(self):
        """Test cannot activate archived tenant."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        self.manager.archive_tenant("pilot_hospital_001")
        
        with pytest.raises(ValueError, match="Cannot activate"):
            self.manager.activate_tenant("pilot_hospital_001")
    
    # =========================================================================
    # Configuration Tests
    # =========================================================================
    
    def test_update_config_merge(self):
        """Test updating config with merge."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
            config={"key1": "value1"},
        )
        
        tenant = self.manager.update_config(
            "pilot_hospital_001",
            config={"key2": "value2"},
            merge=True,
        )
        
        assert tenant.config["key1"] == "value1"
        assert tenant.config["key2"] == "value2"
    
    def test_update_config_replace(self):
        """Test updating config with replace."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
            config={"key1": "value1"},
        )
        
        tenant = self.manager.update_config(
            "pilot_hospital_001",
            config={"key2": "value2"},
            merge=False,
        )
        
        assert "key1" not in tenant.config
        assert tenant.config["key2"] == "value2"
    
    def test_get_config(self):
        """Test getting config."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
            config={"timezone": "America/New_York"},
        )
        
        config = self.manager.get_config("pilot_hospital_001")
        assert config["timezone"] == "America/New_York"
        
        timezone = self.manager.get_config("pilot_hospital_001", key="timezone")
        assert timezone == "America/New_York"
    
    # =========================================================================
    # Limits Tests
    # =========================================================================
    
    def test_update_limits(self):
        """Test updating limits."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        
        tenant = self.manager.update_limits(
            "pilot_hospital_001",
            max_users=500,
            max_requests_per_minute=5000,
        )
        
        assert tenant.max_users == 500
        assert tenant.max_requests_per_minute == 5000
    
    # =========================================================================
    # Delete Tests
    # =========================================================================
    
    def test_delete_tenant_soft(self):
        """Test soft deleting (archiving) tenant."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        
        result = self.manager.delete_tenant("pilot_hospital_001")
        
        assert result is True
        
        # Tenant should be archived, not deleted
        tenant = self.manager.get_tenant("pilot_hospital_001")
        assert tenant.status == TenantStatus.ARCHIVED
    
    def test_delete_tenant_hard(self):
        """Test hard deleting tenant."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        
        result = self.manager.delete_tenant("pilot_hospital_001", hard_delete=True)
        
        assert result is True
        
        with pytest.raises(TenantNotFoundError):
            self.manager.get_tenant("pilot_hospital_001")
    
    # =========================================================================
    # Event Handler Tests
    # =========================================================================
    
    def test_event_handler_called(self):
        """Test event handlers are called."""
        events = []
        
        def handler(event_data):
            events.append(event_data)
        
        self.manager.add_event_handler(handler)
        
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        
        assert len(events) == 1
        assert events[0].event == TenantEvent.CREATED
        assert events[0].tenant_id == "pilot_hospital_001"
    
    def test_multiple_event_handlers(self):
        """Test multiple event handlers."""
        events1 = []
        events2 = []
        
        self.manager.add_event_handler(lambda e: events1.append(e))
        self.manager.add_event_handler(lambda e: events2.append(e))
        
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        
        assert len(events1) == 1
        assert len(events2) == 1
    
    def test_status_change_events(self):
        """Test events are emitted for status changes."""
        events = []
        self.manager.add_event_handler(lambda e: events.append(e))
        
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        self.manager.activate_tenant("pilot_hospital_001")
        self.manager.suspend_tenant("pilot_hospital_001")
        
        event_types = [e.event for e in events]
        
        assert TenantEvent.CREATED in event_types
        assert TenantEvent.ACTIVATED in event_types
        assert TenantEvent.SUSPENDED in event_types
    
    # =========================================================================
    # Utility Tests
    # =========================================================================
    
    def test_is_active(self):
        """Test is_active helper."""
        self.manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="Pilot Hospital",
        )
        
        assert self.manager.is_active("pilot_hospital_001") is False
        
        self.manager.activate_tenant("pilot_hospital_001")
        
        assert self.manager.is_active("pilot_hospital_001") is True
    
    def test_is_active_nonexistent(self):
        """Test is_active returns False for non-existent."""
        assert self.manager.is_active("nonexistent") is False


# ==============================================================================
# Test Count: ~45 tests for tenant manager
# ==============================================================================
