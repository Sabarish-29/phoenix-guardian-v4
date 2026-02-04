"""
Phoenix Guardian Tenants Module.

Multi-tenant management for healthcare organizations.
"""

from phoenix_guardian.tenants.tenant_manager import (
    TenantManager,
    InMemoryTenantStorage,
)

__all__ = [
    "TenantManager",
    "InMemoryTenantStorage",
]
