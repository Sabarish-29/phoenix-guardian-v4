"""
Phoenix Guardian - Tenant Context System
Thread-local storage for current tenant ID.

This is the FOUNDATION of multi-tenant isolation. Every database query,
cache access, and API call must check this context.

SECURITY GUARANTEE: No code can access data from another tenant
unless it explicitly sets the tenant context (which is audited).
"""

import threading
import logging
import inspect
from typing import Optional, Any, Callable
from contextlib import contextmanager
from functools import wraps
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


# ==============================================================================
# Exceptions
# ==============================================================================

class SecurityError(Exception):
    """Raised when tenant isolation is violated."""
    pass


class TenantNotFoundError(Exception):
    """Raised when a tenant does not exist."""
    pass


class TenantSuspendedError(Exception):
    """Raised when a tenant is suspended."""
    pass


# ==============================================================================
# Enumerations
# ==============================================================================

class TenantStatus(Enum):
    """Tenant lifecycle status."""
    PENDING = "pending"              # Being provisioned
    ACTIVE = "active"                # Normal operation
    SUSPENDED = "suspended"          # Temporarily disabled
    DEACTIVATING = "deactivating"    # Being offboarded
    ARCHIVED = "archived"            # Data archived, tenant gone


class TenantAccessLevel(Enum):
    """Access levels for tenant operations."""
    READ_ONLY = "read_only"          # Can read tenant data
    READ_WRITE = "read_write"        # Normal operations
    ADMIN = "admin"                  # Tenant admin
    SUPER_ADMIN = "super_admin"      # Platform admin (cross-tenant)


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class TenantInfo:
    """
    Information about a tenant.
    """
    tenant_id: str
    name: str
    status: TenantStatus = TenantStatus.ACTIVE
    access_level: TenantAccessLevel = TenantAccessLevel.READ_WRITE
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    settings: dict = field(default_factory=dict)
    
    # Limits
    max_users: int = 100
    max_encounters_per_day: int = 10000
    
    def is_active(self) -> bool:
        """Check if tenant is active."""
        return self.status == TenantStatus.ACTIVE
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "status": self.status.value,
            "access_level": self.access_level.value,
            "created_at": self.created_at.isoformat(),
            "settings": self.settings,
            "max_users": self.max_users,
            "max_encounters_per_day": self.max_encounters_per_day,
        }


@dataclass
class TenantAccessAudit:
    """
    Audit record for tenant context access.
    """
    timestamp: datetime
    tenant_id: str
    action: str                      # set, get, override, clear
    caller_file: str
    caller_line: int
    caller_function: str
    user_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "tenant_id": self.tenant_id,
            "action": self.action,
            "caller": f"{self.caller_file}:{self.caller_line}:{self.caller_function}",
            "user_id": self.user_id,
        }


# ==============================================================================
# Tenant Context (Thread-Local Storage)
# ==============================================================================

class TenantContext:
    """
    Thread-local storage for current tenant ID.
    
    This is the FOUNDATION of multi-tenant isolation.
    Every database query, cache access, and API call must
    check this context.
    
    Usage:
        # Set by middleware on each request
        TenantContext.set("pilot_hospital_001", user_id="user123")
        
        # Get current tenant (raises if not set)
        tenant_id = TenantContext.get()
        
        # Check if set
        if TenantContext.is_set():
            ...
        
        # Clear after request
        TenantContext.clear()
        
        # Override for admin operations (AUDITED)
        with TenantContext.override("other_tenant"):
            # Temporarily access other tenant's data
            pass
    """
    
    _local = threading.local()
    _audit_log: list = []            # In-memory audit (for testing)
    _tenant_registry: dict = {}      # Registered tenants
    
    # =========================================================================
    # Core Operations
    # =========================================================================
    
    @classmethod
    def set(
        cls,
        tenant_id: str,
        user_id: Optional[str] = None,
        access_level: TenantAccessLevel = TenantAccessLevel.READ_WRITE,
    ) -> None:
        """
        Set the current tenant for this thread.
        
        IMPORTANT: This is called by tenant_middleware on every request.
        Manual calls to this method are AUDITED.
        
        Args:
            tenant_id: Tenant identifier (e.g., "pilot_hospital_001")
            user_id: User making the request
            access_level: Access level for this session
        
        Raises:
            ValueError: If tenant_id is invalid
            TenantNotFoundError: If tenant doesn't exist
            TenantSuspendedError: If tenant is suspended
        """
        if not tenant_id:
            raise ValueError("tenant_id cannot be empty")
        
        if not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a string")
        
        # Validate tenant exists (if registry is populated)
        if cls._tenant_registry and tenant_id not in cls._tenant_registry:
            raise TenantNotFoundError(f"Tenant '{tenant_id}' not found")
        
        # Check tenant status
        if tenant_id in cls._tenant_registry:
            tenant_info = cls._tenant_registry[tenant_id]
            if tenant_info.status == TenantStatus.SUSPENDED:
                raise TenantSuspendedError(f"Tenant '{tenant_id}' is suspended")
            if tenant_info.status == TenantStatus.ARCHIVED:
                raise TenantNotFoundError(f"Tenant '{tenant_id}' is archived")
        
        # Audit the context change
        cls._audit_access(tenant_id, "set", user_id)
        
        # Set thread-local storage
        cls._local.tenant_id = tenant_id
        cls._local.user_id = user_id
        cls._local.access_level = access_level
        cls._local.set_at = datetime.now(timezone.utc)
    
    @classmethod
    def get(cls) -> str:
        """
        Get the current tenant ID.
        
        Returns:
            Tenant ID string
        
        Raises:
            SecurityError: If no tenant context is set
        """
        tenant_id = getattr(cls._local, 'tenant_id', None)
        
        if tenant_id is None:
            raise SecurityError(
                "No tenant context set. All API requests must be authenticated."
            )
        
        return tenant_id
    
    @classmethod
    def get_or_none(cls) -> Optional[str]:
        """
        Get the current tenant ID or None if not set.
        
        Use this for code paths where tenant context is optional.
        """
        return getattr(cls._local, 'tenant_id', None)
    
    @classmethod
    def get_user_id(cls) -> Optional[str]:
        """Get the current user ID."""
        return getattr(cls._local, 'user_id', None)
    
    @classmethod
    def get_access_level(cls) -> TenantAccessLevel:
        """Get the current access level."""
        return getattr(cls._local, 'access_level', TenantAccessLevel.READ_ONLY)
    
    @classmethod
    def clear(cls) -> None:
        """
        Clear the tenant context (called after request completes).
        """
        tenant_id = getattr(cls._local, 'tenant_id', None)
        if tenant_id:
            cls._audit_access(tenant_id, "clear")
        
        for attr in ['tenant_id', 'user_id', 'access_level', 'set_at']:
            if hasattr(cls._local, attr):
                delattr(cls._local, attr)
    
    @classmethod
    def is_set(cls) -> bool:
        """Check if tenant context is currently set."""
        return hasattr(cls._local, 'tenant_id') and cls._local.tenant_id is not None
    
    # =========================================================================
    # Override Context (Admin Operations)
    # =========================================================================
    
    @classmethod
    @contextmanager
    def override(cls, tenant_id: str, user_id: Optional[str] = None):
        """
        Temporarily override tenant context (for admin operations).
        
        USE WITH EXTREME CAUTION. This allows cross-tenant access.
        All uses are CRITICALLY AUDITED.
        
        Example:
            with TenantContext.override("pilot_hospital_002"):
                # Can now access hospital 002's data
                pass
        """
        # Critical audit for override
        cls._audit_access(tenant_id, "override_start", user_id)
        
        # Save original context
        original_tenant = getattr(cls._local, 'tenant_id', None)
        original_user = getattr(cls._local, 'user_id', None)
        original_access = getattr(cls._local, 'access_level', None)
        
        try:
            cls._local.tenant_id = tenant_id
            cls._local.user_id = user_id or original_user
            cls._local.access_level = TenantAccessLevel.SUPER_ADMIN
            cls._local.set_at = datetime.now(timezone.utc)
            
            yield
            
        finally:
            # Restore original context
            cls._audit_access(tenant_id, "override_end", user_id)
            
            if original_tenant is None:
                cls.clear()
            else:
                cls._local.tenant_id = original_tenant
                cls._local.user_id = original_user
                cls._local.access_level = original_access
    
    # =========================================================================
    # Tenant Registry
    # =========================================================================
    
    @classmethod
    def register_tenant(cls, tenant_info: TenantInfo) -> None:
        """
        Register a tenant in the context registry.
        
        Called during tenant provisioning.
        """
        cls._tenant_registry[tenant_info.tenant_id] = tenant_info
        logger.info(f"Registered tenant: {tenant_info.tenant_id}")
    
    @classmethod
    def unregister_tenant(cls, tenant_id: str) -> None:
        """
        Remove a tenant from the registry.
        
        Called during tenant offboarding.
        """
        if tenant_id in cls._tenant_registry:
            del cls._tenant_registry[tenant_id]
            logger.info(f"Unregistered tenant: {tenant_id}")
    
    @classmethod
    def get_tenant_info(cls, tenant_id: str) -> Optional[TenantInfo]:
        """Get tenant info from registry."""
        return cls._tenant_registry.get(tenant_id)
    
    @classmethod
    def get_all_tenants(cls) -> list:
        """Get all registered tenants."""
        return list(cls._tenant_registry.values())
    
    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered tenants (for testing)."""
        cls._tenant_registry.clear()
    
    # =========================================================================
    # Audit Logging
    # =========================================================================
    
    @classmethod
    def _audit_access(
        cls,
        tenant_id: str,
        action: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Log tenant context access for audit trail.
        """
        # Get caller information
        frame = inspect.currentframe()
        try:
            # Go up the call stack to find the actual caller
            for _ in range(3):  # Skip internal frames
                if frame.f_back:
                    frame = frame.f_back
            
            caller_info = inspect.getframeinfo(frame)
            
            audit = TenantAccessAudit(
                timestamp=datetime.now(timezone.utc),
                tenant_id=tenant_id,
                action=action,
                caller_file=caller_info.filename,
                caller_line=caller_info.lineno,
                caller_function=caller_info.function,
                user_id=user_id or getattr(cls._local, 'user_id', None),
            )
            
            # Store in memory (for testing)
            cls._audit_log.append(audit)
            
            # Log based on action severity
            if action.startswith("override"):
                logger.critical(
                    f"TENANT_CONTEXT_{action.upper()}: {tenant_id} by "
                    f"{caller_info.filename}:{caller_info.lineno}"
                )
            else:
                logger.debug(
                    f"TENANT_CONTEXT_{action.upper()}: {tenant_id}"
                )
                
        finally:
            del frame
    
    @classmethod
    def get_audit_log(cls) -> list:
        """Get the audit log."""
        return [a.to_dict() for a in cls._audit_log]
    
    @classmethod
    def clear_audit_log(cls) -> None:
        """Clear the audit log (for testing)."""
        cls._audit_log.clear()


# ==============================================================================
# Decorators
# ==============================================================================

def require_tenant(func: Callable) -> Callable:
    """
    Decorator that enforces tenant context on any function.
    
    If a function tries to run without valid tenant context,
    it raises SecurityError. This prevents any code path from
    accidentally accessing cross-tenant data.
    
    Usage:
        @require_tenant
        def get_patient_records(patient_id: str):
            tenant_id = TenantContext.get()
            return db.query(Patient).filter_by(
                tenant_id=tenant_id,
                patient_id=patient_id
            ).all()
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        tenant_id = TenantContext.get()  # Raises if not set
        
        # Log the access for audit trail
        logger.debug(
            f"TENANT_ACCESS: {tenant_id} → {func.__module__}.{func.__name__}"
        )
        
        return func(*args, **kwargs)
    
    return wrapper


def require_tenant_async(func: Callable) -> Callable:
    """
    Async version of require_tenant decorator.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        tenant_id = TenantContext.get()  # Raises if not set
        
        logger.debug(
            f"TENANT_ACCESS: {tenant_id} → {func.__module__}.{func.__name__}"
        )
        
        return await func(*args, **kwargs)
    
    return wrapper


def require_access_level(level: TenantAccessLevel) -> Callable:
    """
    Decorator that enforces minimum access level.
    
    Usage:
        @require_access_level(TenantAccessLevel.ADMIN)
        def delete_all_records():
            # Only admins can do this
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_level = TenantContext.get_access_level()
            
            # Check access level hierarchy
            level_hierarchy = [
                TenantAccessLevel.READ_ONLY,
                TenantAccessLevel.READ_WRITE,
                TenantAccessLevel.ADMIN,
                TenantAccessLevel.SUPER_ADMIN,
            ]
            
            current_idx = level_hierarchy.index(current_level)
            required_idx = level_hierarchy.index(level)
            
            if current_idx < required_idx:
                raise SecurityError(
                    f"Insufficient access level. Required: {level.value}, "
                    f"Current: {current_level.value}"
                )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def with_tenant(tenant_id: str, user_id: Optional[str] = None) -> Callable:
    """
    Decorator that sets tenant context for a function.
    
    Useful for background tasks that need tenant context.
    
    Usage:
        @with_tenant("pilot_hospital_001")
        def process_background_job():
            # Has tenant context set
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                TenantContext.set(tenant_id, user_id)
                return func(*args, **kwargs)
            finally:
                TenantContext.clear()
        
        return wrapper
    return decorator
