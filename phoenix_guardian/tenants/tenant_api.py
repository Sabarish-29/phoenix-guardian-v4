"""
Phoenix Guardian - Tenant REST API
FastAPI endpoints for tenant management.

Provides administrative API for tenant lifecycle operations
including creation, updates, suspension, and archival.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Depends, Query, Header, status
from pydantic import BaseModel, ConfigDict, Field, validator

from phoenix_guardian.core.tenant_context import (
    TenantContext,
    TenantInfo,
    TenantStatus,
    TenantAccessLevel,
    SecurityError,
    TenantNotFoundError,
)
from phoenix_guardian.tenants.tenant_manager import TenantManager, InMemoryTenantStorage
from phoenix_guardian.tenants.tenant_provisioner import (
    TenantProvisioner,
    TenantOnboardingRequest,
    ProvisioningConfig,
)
from phoenix_guardian.tenants.tenant_archiver import TenantArchiver, ArchiveConfig

logger = logging.getLogger(__name__)


# ==============================================================================
# Pydantic Models
# ==============================================================================

class TenantCreate(BaseModel):
    """Request to create a new tenant."""
    
    tenant_id: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern="^[a-z][a-z0-9_-]*$",
        description="Unique tenant identifier",
    )
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    config: Dict[str, Any] = Field(default_factory=dict)
    limits: Dict[str, Any] = Field(default_factory=dict)
    
    # Contact info
    admin_email: Optional[str] = None
    admin_name: Optional[str] = None
    
    # Customization
    timezone: str = "UTC"
    locale: str = "en-US"
    enabled_features: List[str] = Field(default_factory=list)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tenant_id": "general_hospital_001",
                "name": "General Hospital",
                "display_name": "General Hospital - Main Campus",
                "config": {"timezone": "America/New_York"},
                "limits": {"max_users": 200, "max_requests_per_minute": 2000},
                "admin_email": "admin@general-hospital.com",
            }
        }
    )


class TenantUpdate(BaseModel):
    """Request to update tenant information."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)


class TenantConfigUpdate(BaseModel):
    """Request to update tenant configuration."""
    
    config: Dict[str, Any]
    merge: bool = Field(True, description="Merge with existing config if True")


class TenantLimitsUpdate(BaseModel):
    """Request to update tenant limits."""
    
    max_users: Optional[int] = Field(None, ge=1)
    max_requests_per_minute: Optional[int] = Field(None, ge=1)


class TenantSuspend(BaseModel):
    """Request to suspend a tenant."""
    
    reason: Optional[str] = Field(None, max_length=500)


class TenantResponse(BaseModel):
    """Tenant information response."""
    
    tenant_id: str
    name: str
    display_name: Optional[str]
    status: str
    config: Dict[str, Any]
    max_users: int
    max_requests_per_minute: int
    created_at: Optional[datetime]
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tenant_id": "general_hospital_001",
                "name": "General Hospital",
                "display_name": "General Hospital - Main Campus",
                "status": "active",
                "config": {"timezone": "America/New_York"},
                "max_users": 200,
                "max_requests_per_minute": 2000,
                "created_at": "2024-01-01T00:00:00Z",
            }
        }
    )


class TenantListResponse(BaseModel):
    """Response for listing tenants."""
    
    tenants: List[TenantResponse]
    total: int
    limit: int
    offset: int


class ProvisioningResponse(BaseModel):
    """Response for provisioning operations."""
    
    tenant_id: str
    success: bool
    duration_ms: Optional[float]
    error: Optional[str]
    steps: List[Dict[str, Any]]


class ArchiveResponse(BaseModel):
    """Response for archive operations."""
    
    tenant_id: str
    success: bool
    archive_path: Optional[str]
    records_exported: int
    archive_size_bytes: int
    error: Optional[str]


class HealthCheckResponse(BaseModel):
    """Response for tenant health check."""
    
    tenant_id: str
    status: str
    is_active: bool
    checks: Dict[str, bool]


# ==============================================================================
# Dependencies
# ==============================================================================

# Global instances (in production, use proper DI)
_storage = InMemoryTenantStorage()
_manager = TenantManager(_storage)
_provisioner = TenantProvisioner(_manager)
_archiver = TenantArchiver(_manager)


def get_tenant_manager() -> TenantManager:
    """Dependency for tenant manager."""
    return _manager


def get_provisioner() -> TenantProvisioner:
    """Dependency for provisioner."""
    return _provisioner


def get_archiver() -> TenantArchiver:
    """Dependency for archiver."""
    return _archiver


def get_current_user_id(
    x_user_id: Optional[str] = Header(None),
) -> Optional[str]:
    """Extract user ID from headers."""
    return x_user_id


def require_admin_access(
    x_access_level: str = Header(..., alias="X-Access-Level"),
) -> None:
    """Require admin or super_admin access level."""
    allowed = ["admin", "super_admin"]
    if x_access_level not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin access required. Current: {x_access_level}",
        )


def require_super_admin_access(
    x_access_level: str = Header(..., alias="X-Access-Level"),
) -> None:
    """Require super_admin access level."""
    if x_access_level != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )


# ==============================================================================
# Router
# ==============================================================================

router = APIRouter(prefix="/tenants", tags=["Tenants"])


# ==============================================================================
# Tenant CRUD Endpoints
# ==============================================================================

@router.post(
    "",
    response_model=ProvisioningResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tenant",
)
async def create_tenant(
    request: TenantCreate,
    manager: TenantManager = Depends(get_tenant_manager),
    provisioner: TenantProvisioner = Depends(get_provisioner),
    user_id: Optional[str] = Depends(get_current_user_id),
    _: None = Depends(require_admin_access),
):
    """
    Create and provision a new tenant.
    
    This will:
    1. Validate the tenant ID and configuration
    2. Create the tenant record
    3. Set up database resources
    4. Seed default data
    5. Deploy models
    6. Run health checks
    7. Activate the tenant
    """
    try:
        # Build onboarding request
        onboarding_request = TenantOnboardingRequest(
            tenant_id=request.tenant_id,
            name=request.name,
            display_name=request.display_name,
            config=request.config,
            limits=request.limits,
            admin_email=request.admin_email,
            admin_name=request.admin_name,
            timezone=request.timezone,
            locale=request.locale,
            enabled_features=request.enabled_features,
        )
        
        # Provision tenant
        result = provisioner.provision(onboarding_request, actor_id=user_id)
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error or "Provisioning failed",
            )
        
        return ProvisioningResponse(
            tenant_id=result.tenant_id,
            success=result.success,
            duration_ms=result.duration_ms,
            error=result.error,
            steps=[
                {
                    "step": s.step.value,
                    "status": s.status.value,
                    "duration_ms": s.duration_ms,
                    "error": s.error,
                }
                for s in result.steps
            ],
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=TenantListResponse,
    summary="List all tenants",
)
async def list_tenants(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    manager: TenantManager = Depends(get_tenant_manager),
    _: None = Depends(require_admin_access),
):
    """
    List tenants with optional filtering.
    """
    # Convert status string to enum
    tenant_status = None
    if status_filter:
        try:
            tenant_status = TenantStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )
    
    tenants = manager.list_tenants(status=tenant_status, limit=limit, offset=offset)
    
    return TenantListResponse(
        tenants=[
            TenantResponse(
                tenant_id=t.tenant_id,
                name=t.name,
                display_name=t.display_name,
                status=t.status.value,
                config=t.config,
                max_users=t.max_users,
                max_requests_per_minute=t.max_requests_per_minute,
                created_at=t.created_at,
            )
            for t in tenants
        ],
        total=len(tenants),  # In production, get actual total count
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Get tenant details",
)
async def get_tenant(
    tenant_id: str,
    manager: TenantManager = Depends(get_tenant_manager),
    _: None = Depends(require_admin_access),
):
    """
    Get detailed information about a tenant.
    """
    try:
        tenant = manager.get_tenant(tenant_id)
        
        return TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            display_name=tenant.display_name,
            status=tenant.status.value,
            config=tenant.config,
            max_users=tenant.max_users,
            max_requests_per_minute=tenant.max_requests_per_minute,
            created_at=tenant.created_at,
        )
        
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found",
        )


@router.patch(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Update tenant information",
)
async def update_tenant(
    tenant_id: str,
    request: TenantUpdate,
    manager: TenantManager = Depends(get_tenant_manager),
    user_id: Optional[str] = Depends(get_current_user_id),
    _: None = Depends(require_admin_access),
):
    """
    Update tenant name or display name.
    """
    try:
        tenant = manager.update_tenant(
            tenant_id,
            name=request.name,
            display_name=request.display_name,
            actor_id=user_id,
        )
        
        return TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            display_name=tenant.display_name,
            status=tenant.status.value,
            config=tenant.config,
            max_users=tenant.max_users,
            max_requests_per_minute=tenant.max_requests_per_minute,
            created_at=tenant.created_at,
        )
        
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found",
        )


@router.delete(
    "/{tenant_id}",
    response_model=ArchiveResponse,
    summary="Archive or delete a tenant",
)
async def delete_tenant(
    tenant_id: str,
    hard_delete: bool = Query(False),
    manager: TenantManager = Depends(get_tenant_manager),
    archiver: TenantArchiver = Depends(get_archiver),
    user_id: Optional[str] = Depends(get_current_user_id),
    _: None = Depends(require_super_admin_access),
):
    """
    Archive or permanently delete a tenant.
    
    By default, this archives the tenant (soft delete).
    Set `hard_delete=true` to permanently remove all data.
    
    **Warning:** Hard delete is irreversible!
    """
    try:
        if hard_delete:
            # Permanent deletion
            manager.delete_tenant(tenant_id, hard_delete=True, actor_id=user_id)
            
            return ArchiveResponse(
                tenant_id=tenant_id,
                success=True,
                archive_path=None,
                records_exported=0,
                archive_size_bytes=0,
                error=None,
            )
        else:
            # Archive
            result = archiver.archive_tenant(tenant_id, actor_id=user_id)
            
            return ArchiveResponse(
                tenant_id=result.tenant_id,
                success=result.success,
                archive_path=result.archive_path,
                records_exported=result.records_exported,
                archive_size_bytes=result.archive_size_bytes,
                error=result.error,
            )
        
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found",
        )


# ==============================================================================
# Configuration Endpoints
# ==============================================================================

@router.get(
    "/{tenant_id}/config",
    response_model=Dict[str, Any],
    summary="Get tenant configuration",
)
async def get_tenant_config(
    tenant_id: str,
    key: Optional[str] = Query(None),
    manager: TenantManager = Depends(get_tenant_manager),
    _: None = Depends(require_admin_access),
):
    """
    Get tenant configuration, optionally filtered by key.
    """
    try:
        config = manager.get_config(tenant_id, key)
        
        if key:
            return {"key": key, "value": config}
        return config
        
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found",
        )


@router.put(
    "/{tenant_id}/config",
    response_model=TenantResponse,
    summary="Update tenant configuration",
)
async def update_tenant_config(
    tenant_id: str,
    request: TenantConfigUpdate,
    manager: TenantManager = Depends(get_tenant_manager),
    user_id: Optional[str] = Depends(get_current_user_id),
    _: None = Depends(require_admin_access),
):
    """
    Update tenant configuration.
    """
    try:
        tenant = manager.update_config(
            tenant_id,
            config=request.config,
            merge=request.merge,
            actor_id=user_id,
        )
        
        return TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            display_name=tenant.display_name,
            status=tenant.status.value,
            config=tenant.config,
            max_users=tenant.max_users,
            max_requests_per_minute=tenant.max_requests_per_minute,
            created_at=tenant.created_at,
        )
        
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found",
        )


@router.put(
    "/{tenant_id}/limits",
    response_model=TenantResponse,
    summary="Update tenant limits",
)
async def update_tenant_limits(
    tenant_id: str,
    request: TenantLimitsUpdate,
    manager: TenantManager = Depends(get_tenant_manager),
    user_id: Optional[str] = Depends(get_current_user_id),
    _: None = Depends(require_admin_access),
):
    """
    Update tenant resource limits.
    """
    try:
        tenant = manager.update_limits(
            tenant_id,
            max_users=request.max_users,
            max_requests_per_minute=request.max_requests_per_minute,
            actor_id=user_id,
        )
        
        return TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            display_name=tenant.display_name,
            status=tenant.status.value,
            config=tenant.config,
            max_users=tenant.max_users,
            max_requests_per_minute=tenant.max_requests_per_minute,
            created_at=tenant.created_at,
        )
        
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found",
        )


# ==============================================================================
# Status Management Endpoints
# ==============================================================================

@router.post(
    "/{tenant_id}/activate",
    response_model=TenantResponse,
    summary="Activate a tenant",
)
async def activate_tenant(
    tenant_id: str,
    manager: TenantManager = Depends(get_tenant_manager),
    user_id: Optional[str] = Depends(get_current_user_id),
    _: None = Depends(require_admin_access),
):
    """
    Activate a pending or suspended tenant.
    """
    try:
        tenant = manager.activate_tenant(tenant_id, actor_id=user_id)
        
        return TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            display_name=tenant.display_name,
            status=tenant.status.value,
            config=tenant.config,
            max_users=tenant.max_users,
            max_requests_per_minute=tenant.max_requests_per_minute,
            created_at=tenant.created_at,
        )
        
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{tenant_id}/suspend",
    response_model=TenantResponse,
    summary="Suspend a tenant",
)
async def suspend_tenant(
    tenant_id: str,
    request: TenantSuspend,
    manager: TenantManager = Depends(get_tenant_manager),
    user_id: Optional[str] = Depends(get_current_user_id),
    _: None = Depends(require_admin_access),
):
    """
    Suspend an active tenant.
    """
    try:
        tenant = manager.suspend_tenant(
            tenant_id,
            reason=request.reason,
            actor_id=user_id,
        )
        
        return TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            display_name=tenant.display_name,
            status=tenant.status.value,
            config=tenant.config,
            max_users=tenant.max_users,
            max_requests_per_minute=tenant.max_requests_per_minute,
            created_at=tenant.created_at,
        )
        
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ==============================================================================
# Health Check Endpoints
# ==============================================================================

@router.get(
    "/{tenant_id}/health",
    response_model=HealthCheckResponse,
    summary="Check tenant health",
)
async def check_tenant_health(
    tenant_id: str,
    manager: TenantManager = Depends(get_tenant_manager),
    _: None = Depends(require_admin_access),
):
    """
    Run health checks for a tenant.
    """
    checks = {
        "tenant_exists": False,
        "tenant_active": False,
        "context_accessible": False,
    }
    
    try:
        tenant = manager.get_tenant(tenant_id)
        checks["tenant_exists"] = True
        checks["tenant_active"] = tenant.status == TenantStatus.ACTIVE
        
        # Try to set context
        try:
            TenantContext.set(tenant_id)
            checks["context_accessible"] = True
        finally:
            TenantContext.clear()
        
        return HealthCheckResponse(
            tenant_id=tenant_id,
            status=tenant.status.value,
            is_active=tenant.status == TenantStatus.ACTIVE,
            checks=checks,
        )
        
    except TenantNotFoundError:
        return HealthCheckResponse(
            tenant_id=tenant_id,
            status="not_found",
            is_active=False,
            checks=checks,
        )


# ==============================================================================
# Factory Function
# ==============================================================================

def create_tenant_router(
    manager: TenantManager,
    provisioner: TenantProvisioner,
    archiver: TenantArchiver,
) -> APIRouter:
    """
    Create a tenant router with custom dependencies.
    
    Args:
        manager: Tenant manager instance
        provisioner: Provisioner instance
        archiver: Archiver instance
    
    Returns:
        Configured APIRouter
    """
    # Override dependencies
    def get_manager():
        return manager
    
    def get_prov():
        return provisioner
    
    def get_arch():
        return archiver
    
    # Create new router with overridden dependencies
    custom_router = APIRouter(prefix="/tenants", tags=["Tenants"])
    
    # Re-register all routes with new dependencies
    # This is simplified - in production, use proper DI framework
    
    return router  # Return default for now
