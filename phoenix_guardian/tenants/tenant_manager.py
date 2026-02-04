"""
Phoenix Guardian - Tenant Manager
Central management of tenant lifecycle and operations.

Provides high-level API for tenant administration including
creation, updates, suspension, and deletion.
"""

import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from phoenix_guardian.core.tenant_context import (
    TenantContext,
    TenantInfo,
    TenantStatus,
    TenantAccessLevel,
    SecurityError,
    TenantNotFoundError,
    TenantSuspendedError,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# Events
# ==============================================================================

class TenantEvent(Enum):
    """Tenant lifecycle events."""
    CREATED = "created"
    ACTIVATED = "activated"
    SUSPENDED = "suspended"
    REACTIVATED = "reactivated"
    DEACTIVATING = "deactivating"
    ARCHIVED = "archived"
    DELETED = "deleted"
    CONFIG_UPDATED = "config_updated"
    LIMITS_UPDATED = "limits_updated"


@dataclass
class TenantEventData:
    """Data for a tenant event."""
    event: TenantEvent
    tenant_id: str
    timestamp: datetime
    actor_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    previous_state: Optional[TenantStatus] = None
    new_state: Optional[TenantStatus] = None


# ==============================================================================
# Tenant Manager
# ==============================================================================

class TenantManager:
    """
    Manages tenant lifecycle and operations.
    
    This is the central hub for all tenant administration:
    - Creating new tenants
    - Updating tenant configuration
    - Suspending/reactivating tenants
    - Managing tenant limits
    - Archiving/deleting tenants
    
    Example:
        manager = TenantManager(storage)
        
        # Create a new tenant
        tenant = manager.create_tenant(
            tenant_id="pilot_hospital_001",
            name="General Hospital",
            config={"timezone": "America/New_York"}
        )
        
        # Activate the tenant
        manager.activate_tenant("pilot_hospital_001")
        
        # Update configuration
        manager.update_config("pilot_hospital_001", {"feature_flags": {...}})
        
        # Suspend for maintenance
        manager.suspend_tenant("pilot_hospital_001", reason="scheduled maintenance")
    """
    
    def __init__(
        self,
        storage: "TenantStorage",
        event_handlers: Optional[List[Callable[[TenantEventData], None]]] = None,
    ):
        """
        Initialize tenant manager.
        
        Args:
            storage: Tenant storage backend
            event_handlers: Optional list of event handler callbacks
        """
        self._storage = storage
        self._event_handlers = event_handlers or []
        self._validators: List[Callable[[str, Dict], bool]] = []
    
    # =========================================================================
    # Event Handling
    # =========================================================================
    
    def add_event_handler(
        self,
        handler: Callable[[TenantEventData], None],
    ) -> None:
        """Register an event handler."""
        self._event_handlers.append(handler)
    
    def _emit_event(
        self,
        event: TenantEvent,
        tenant_id: str,
        actor_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        previous_state: Optional[TenantStatus] = None,
        new_state: Optional[TenantStatus] = None,
    ) -> None:
        """Emit a tenant event to all handlers."""
        event_data = TenantEventData(
            event=event,
            tenant_id=tenant_id,
            timestamp=datetime.now(timezone.utc),
            actor_id=actor_id,
            details=details or {},
            previous_state=previous_state,
            new_state=new_state,
        )
        
        for handler in self._event_handlers:
            try:
                handler(event_data)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
    
    # =========================================================================
    # Tenant CRUD
    # =========================================================================
    
    def create_tenant(
        self,
        tenant_id: str,
        name: str,
        config: Optional[Dict[str, Any]] = None,
        limits: Optional[Dict[str, Any]] = None,
        actor_id: Optional[str] = None,
    ) -> TenantInfo:
        """
        Create a new tenant.
        
        The tenant is created in PENDING status and must be
        activated before use.
        
        Args:
            tenant_id: Unique tenant identifier
            name: Human-readable tenant name
            config: Initial configuration
            limits: Resource limits
            actor_id: ID of user creating the tenant
        
        Returns:
            Created TenantInfo
        
        Raises:
            ValueError: If tenant_id already exists or is invalid
        """
        # Validate tenant_id format
        self._validate_tenant_id(tenant_id)
        
        # Check for duplicates
        if self._storage.exists(tenant_id):
            raise ValueError(f"Tenant '{tenant_id}' already exists")
        
        # Create tenant info
        now = datetime.now(timezone.utc)
        
        tenant_info = TenantInfo(
            tenant_id=tenant_id,
            name=name,
            status=TenantStatus.PENDING,
            config=config or {},
            created_at=now,
        )
        
        # Apply limits
        if limits:
            tenant_info.max_users = limits.get('max_users', 100)
            tenant_info.max_requests_per_minute = limits.get('max_requests_per_minute', 1000)
        
        # Save to storage
        self._storage.save(tenant_info)
        
        # Emit event
        self._emit_event(
            TenantEvent.CREATED,
            tenant_id,
            actor_id=actor_id,
            details={"name": name, "config": config},
            new_state=TenantStatus.PENDING,
        )
        
        logger.info(f"Created tenant: {tenant_id}")
        
        return tenant_info
    
    def get_tenant(self, tenant_id: str) -> TenantInfo:
        """
        Get tenant information.
        
        Args:
            tenant_id: Tenant identifier
        
        Returns:
            TenantInfo
        
        Raises:
            TenantNotFoundError: If tenant doesn't exist
        """
        tenant_info = self._storage.get(tenant_id)
        
        if tenant_info is None:
            raise TenantNotFoundError(f"Tenant '{tenant_id}' not found")
        
        return tenant_info
    
    def list_tenants(
        self,
        status: Optional[TenantStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TenantInfo]:
        """
        List tenants with optional filtering.
        
        Args:
            status: Filter by status
            limit: Maximum results
            offset: Pagination offset
        
        Returns:
            List of TenantInfo
        """
        tenants = self._storage.list_all()
        
        # Filter by status
        if status:
            tenants = [t for t in tenants if t.status == status]
        
        # Paginate
        return tenants[offset:offset + limit]
    
    def update_tenant(
        self,
        tenant_id: str,
        name: Optional[str] = None,
        display_name: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> TenantInfo:
        """
        Update basic tenant information.
        
        Args:
            tenant_id: Tenant identifier
            name: New name
            display_name: New display name
            actor_id: ID of user making update
        
        Returns:
            Updated TenantInfo
        """
        tenant = self.get_tenant(tenant_id)
        
        if name:
            tenant.name = name
        
        if display_name:
            tenant.display_name = display_name
        
        self._storage.save(tenant)
        
        logger.info(f"Updated tenant: {tenant_id}")
        
        return tenant
    
    def delete_tenant(
        self,
        tenant_id: str,
        hard_delete: bool = False,
        actor_id: Optional[str] = None,
    ) -> bool:
        """
        Delete a tenant.
        
        By default, this archives the tenant. Use hard_delete=True
        to permanently remove all data.
        
        Args:
            tenant_id: Tenant identifier
            hard_delete: Whether to permanently delete
            actor_id: ID of user deleting
        
        Returns:
            True if successful
        """
        tenant = self.get_tenant(tenant_id)
        
        if hard_delete:
            # Permanent deletion
            self._storage.delete(tenant_id)
            
            self._emit_event(
                TenantEvent.DELETED,
                tenant_id,
                actor_id=actor_id,
                details={"hard_delete": True},
            )
            
            logger.warning(f"HARD DELETED tenant: {tenant_id}")
        else:
            # Archive instead
            self.archive_tenant(tenant_id, actor_id=actor_id)
        
        return True
    
    # =========================================================================
    # Status Management
    # =========================================================================
    
    def activate_tenant(
        self,
        tenant_id: str,
        actor_id: Optional[str] = None,
    ) -> TenantInfo:
        """
        Activate a pending tenant.
        
        Args:
            tenant_id: Tenant identifier
            actor_id: ID of user activating
        
        Returns:
            Updated TenantInfo
        """
        tenant = self.get_tenant(tenant_id)
        previous_status = tenant.status
        
        if tenant.status == TenantStatus.ACTIVE:
            return tenant  # Already active
        
        if tenant.status not in [TenantStatus.PENDING, TenantStatus.SUSPENDED]:
            raise ValueError(
                f"Cannot activate tenant in status '{tenant.status.value}'"
            )
        
        tenant.status = TenantStatus.ACTIVE
        self._storage.save(tenant)
        
        event = (
            TenantEvent.ACTIVATED
            if previous_status == TenantStatus.PENDING
            else TenantEvent.REACTIVATED
        )
        
        self._emit_event(
            event,
            tenant_id,
            actor_id=actor_id,
            previous_state=previous_status,
            new_state=TenantStatus.ACTIVE,
        )
        
        logger.info(f"Activated tenant: {tenant_id}")
        
        return tenant
    
    def suspend_tenant(
        self,
        tenant_id: str,
        reason: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> TenantInfo:
        """
        Suspend a tenant.
        
        Suspended tenants cannot access the system but data is preserved.
        
        Args:
            tenant_id: Tenant identifier
            reason: Reason for suspension
            actor_id: ID of user suspending
        
        Returns:
            Updated TenantInfo
        """
        tenant = self.get_tenant(tenant_id)
        previous_status = tenant.status
        
        if tenant.status == TenantStatus.SUSPENDED:
            return tenant  # Already suspended
        
        if tenant.status in [TenantStatus.ARCHIVED, TenantStatus.DEACTIVATING]:
            raise ValueError(
                f"Cannot suspend tenant in status '{tenant.status.value}'"
            )
        
        tenant.status = TenantStatus.SUSPENDED
        self._storage.save(tenant)
        
        self._emit_event(
            TenantEvent.SUSPENDED,
            tenant_id,
            actor_id=actor_id,
            details={"reason": reason},
            previous_state=previous_status,
            new_state=TenantStatus.SUSPENDED,
        )
        
        logger.warning(f"Suspended tenant: {tenant_id}, reason: {reason}")
        
        return tenant
    
    def archive_tenant(
        self,
        tenant_id: str,
        actor_id: Optional[str] = None,
    ) -> TenantInfo:
        """
        Archive a tenant.
        
        Archived tenants are read-only and cannot be accessed normally.
        Data is preserved for compliance.
        
        Args:
            tenant_id: Tenant identifier
            actor_id: ID of user archiving
        
        Returns:
            Updated TenantInfo
        """
        tenant = self.get_tenant(tenant_id)
        previous_status = tenant.status
        
        # First transition to DEACTIVATING
        tenant.status = TenantStatus.DEACTIVATING
        self._storage.save(tenant)
        
        self._emit_event(
            TenantEvent.DEACTIVATING,
            tenant_id,
            actor_id=actor_id,
            previous_state=previous_status,
            new_state=TenantStatus.DEACTIVATING,
        )
        
        # Then to ARCHIVED
        tenant.status = TenantStatus.ARCHIVED
        self._storage.save(tenant)
        
        self._emit_event(
            TenantEvent.ARCHIVED,
            tenant_id,
            actor_id=actor_id,
            previous_state=TenantStatus.DEACTIVATING,
            new_state=TenantStatus.ARCHIVED,
        )
        
        logger.info(f"Archived tenant: {tenant_id}")
        
        return tenant
    
    # =========================================================================
    # Configuration Management
    # =========================================================================
    
    def update_config(
        self,
        tenant_id: str,
        config: Dict[str, Any],
        merge: bool = True,
        actor_id: Optional[str] = None,
    ) -> TenantInfo:
        """
        Update tenant configuration.
        
        Args:
            tenant_id: Tenant identifier
            config: Configuration to apply
            merge: If True, merge with existing. If False, replace.
            actor_id: ID of user updating
        
        Returns:
            Updated TenantInfo
        """
        tenant = self.get_tenant(tenant_id)
        
        if merge:
            tenant.config.update(config)
        else:
            tenant.config = config
        
        self._storage.save(tenant)
        
        self._emit_event(
            TenantEvent.CONFIG_UPDATED,
            tenant_id,
            actor_id=actor_id,
            details={"config": config, "merge": merge},
        )
        
        logger.info(f"Updated config for tenant: {tenant_id}")
        
        return tenant
    
    def get_config(
        self,
        tenant_id: str,
        key: Optional[str] = None,
    ) -> Any:
        """
        Get tenant configuration.
        
        Args:
            tenant_id: Tenant identifier
            key: Optional specific key to get
        
        Returns:
            Configuration value or dict
        """
        tenant = self.get_tenant(tenant_id)
        
        if key:
            return tenant.config.get(key)
        
        return tenant.config
    
    # =========================================================================
    # Limits Management
    # =========================================================================
    
    def update_limits(
        self,
        tenant_id: str,
        max_users: Optional[int] = None,
        max_requests_per_minute: Optional[int] = None,
        actor_id: Optional[str] = None,
    ) -> TenantInfo:
        """
        Update tenant resource limits.
        
        Args:
            tenant_id: Tenant identifier
            max_users: Maximum users
            max_requests_per_minute: Rate limit
            actor_id: ID of user updating
        
        Returns:
            Updated TenantInfo
        """
        tenant = self.get_tenant(tenant_id)
        
        if max_users is not None:
            tenant.max_users = max_users
        
        if max_requests_per_minute is not None:
            tenant.max_requests_per_minute = max_requests_per_minute
        
        self._storage.save(tenant)
        
        self._emit_event(
            TenantEvent.LIMITS_UPDATED,
            tenant_id,
            actor_id=actor_id,
            details={
                "max_users": max_users,
                "max_requests_per_minute": max_requests_per_minute,
            },
        )
        
        logger.info(f"Updated limits for tenant: {tenant_id}")
        
        return tenant
    
    # =========================================================================
    # Validation
    # =========================================================================
    
    def _validate_tenant_id(self, tenant_id: str) -> None:
        """Validate tenant ID format."""
        import re
        
        if not tenant_id:
            raise ValueError("Tenant ID cannot be empty")
        
        if len(tenant_id) < 3:
            raise ValueError("Tenant ID must be at least 3 characters")
        
        if len(tenant_id) > 64:
            raise ValueError("Tenant ID must be at most 64 characters")
        
        if not re.match(r'^[a-z][a-z0-9_-]*$', tenant_id):
            raise ValueError(
                "Tenant ID must start with lowercase letter and contain only "
                "lowercase letters, numbers, underscores, or hyphens"
            )
    
    def is_active(self, tenant_id: str) -> bool:
        """Check if tenant is active."""
        try:
            tenant = self.get_tenant(tenant_id)
            return tenant.status == TenantStatus.ACTIVE
        except TenantNotFoundError:
            return False


# ==============================================================================
# Tenant Storage
# ==============================================================================

class TenantStorage:
    """
    Abstract storage interface for tenants.
    
    Implementations can use database, file system, or other backends.
    """
    
    def save(self, tenant: TenantInfo) -> None:
        """Save tenant info."""
        raise NotImplementedError
    
    def get(self, tenant_id: str) -> Optional[TenantInfo]:
        """Get tenant info."""
        raise NotImplementedError
    
    def delete(self, tenant_id: str) -> bool:
        """Delete tenant."""
        raise NotImplementedError
    
    def exists(self, tenant_id: str) -> bool:
        """Check if tenant exists."""
        raise NotImplementedError
    
    def list_all(self) -> List[TenantInfo]:
        """List all tenants."""
        raise NotImplementedError


class InMemoryTenantStorage(TenantStorage):
    """
    In-memory tenant storage for testing.
    """
    
    def __init__(self):
        self._tenants: Dict[str, TenantInfo] = {}
    
    def save(self, tenant: TenantInfo) -> None:
        self._tenants[tenant.tenant_id] = tenant
    
    def get(self, tenant_id: str) -> Optional[TenantInfo]:
        return self._tenants.get(tenant_id)
    
    def delete(self, tenant_id: str) -> bool:
        if tenant_id in self._tenants:
            del self._tenants[tenant_id]
            return True
        return False
    
    def exists(self, tenant_id: str) -> bool:
        return tenant_id in self._tenants
    
    def list_all(self) -> List[TenantInfo]:
        return list(self._tenants.values())


class DatabaseTenantStorage(TenantStorage):
    """
    Database-backed tenant storage.
    
    Uses SQLAlchemy session to persist tenant data.
    """
    
    def __init__(self, session_factory):
        self._session_factory = session_factory
    
    def save(self, tenant: TenantInfo) -> None:
        from phoenix_guardian.database.multi_tenant_models import Tenant
        
        session = self._session_factory()
        try:
            db_tenant = session.query(Tenant).get(tenant.tenant_id)
            
            if db_tenant is None:
                db_tenant = Tenant(id=tenant.tenant_id)
                session.add(db_tenant)
            
            db_tenant.name = tenant.name
            db_tenant.display_name = tenant.display_name
            db_tenant.status = tenant.status.value
            db_tenant.is_active = tenant.status == TenantStatus.ACTIVE
            db_tenant.config = tenant.config
            db_tenant.max_users = tenant.max_users
            db_tenant.updated_at = datetime.now(timezone.utc)
            
            session.commit()
        finally:
            session.close()
    
    def get(self, tenant_id: str) -> Optional[TenantInfo]:
        from phoenix_guardian.database.multi_tenant_models import Tenant
        
        session = self._session_factory()
        try:
            db_tenant = session.query(Tenant).get(tenant_id)
            
            if db_tenant is None:
                return None
            
            return TenantInfo(
                tenant_id=db_tenant.id,
                name=db_tenant.name,
                display_name=db_tenant.display_name,
                status=TenantStatus(db_tenant.status),
                config=db_tenant.config or {},
                max_users=db_tenant.max_users,
                max_requests_per_minute=1000,
                created_at=db_tenant.created_at,
            )
        finally:
            session.close()
    
    def delete(self, tenant_id: str) -> bool:
        from phoenix_guardian.database.multi_tenant_models import Tenant
        
        session = self._session_factory()
        try:
            db_tenant = session.query(Tenant).get(tenant_id)
            
            if db_tenant:
                session.delete(db_tenant)
                session.commit()
                return True
            
            return False
        finally:
            session.close()
    
    def exists(self, tenant_id: str) -> bool:
        from phoenix_guardian.database.multi_tenant_models import Tenant
        
        session = self._session_factory()
        try:
            return session.query(Tenant).get(tenant_id) is not None
        finally:
            session.close()
    
    def list_all(self) -> List[TenantInfo]:
        from phoenix_guardian.database.multi_tenant_models import Tenant
        
        session = self._session_factory()
        try:
            db_tenants = session.query(Tenant).all()
            
            return [
                TenantInfo(
                    tenant_id=t.id,
                    name=t.name,
                    display_name=t.display_name,
                    status=TenantStatus(t.status),
                    config=t.config or {},
                    max_users=t.max_users,
                    max_requests_per_minute=1000,
                    created_at=t.created_at,
                )
                for t in db_tenants
            ]
        finally:
            session.close()
