"""
Phoenix Guardian - Tenant Validator
Validates tenant access and permissions.

Provides validation logic for tenant operations including
existence checks, status validation, and permission verification.
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
# Validation Rules
# ==============================================================================

class ValidationResult:
    """Result of a validation check."""
    
    def __init__(
        self,
        is_valid: bool,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
    ):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
    
    def __bool__(self) -> bool:
        return self.is_valid
    
    def add_error(self, error: str) -> None:
        """Add an error and mark invalid."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a warning (doesn't affect validity)."""
        self.warnings.append(warning)
    
    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge another validation result."""
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ==============================================================================
# Tenant Validator
# ==============================================================================

class TenantValidator:
    """
    Validates tenant operations and access.
    
    Provides comprehensive validation including:
    - Tenant ID format validation
    - Tenant existence checks
    - Status validation
    - Permission checks
    - Cross-tenant access prevention
    
    Example:
        validator = TenantValidator()
        
        # Validate tenant ID format
        result = validator.validate_tenant_id("pilot_hospital_001")
        
        # Validate tenant exists and is active
        result = validator.validate_tenant_active("pilot_hospital_001")
        
        # Validate cross-tenant access
        validator.validate_same_tenant("pilot_hospital_001", "pilot_hospital_001")
    """
    
    # Tenant ID format rules
    TENANT_ID_MIN_LENGTH = 3
    TENANT_ID_MAX_LENGTH = 64
    TENANT_ID_PATTERN = re.compile(r'^[a-z][a-z0-9_-]*$')
    
    # Reserved tenant IDs
    RESERVED_TENANT_IDS = {
        "admin",
        "system",
        "root",
        "phoenix",
        "default",
        "public",
        "internal",
        "test",
    }
    
    def __init__(
        self,
        tenant_lookup: Optional[Callable[[str], Optional[TenantInfo]]] = None,
    ):
        """
        Initialize validator.
        
        Args:
            tenant_lookup: Custom function to look up tenant info
        """
        self._tenant_lookup = tenant_lookup or TenantContext.get_tenant_info
    
    # =========================================================================
    # ID Validation
    # =========================================================================
    
    def validate_tenant_id_format(self, tenant_id: str) -> ValidationResult:
        """
        Validate tenant ID format.
        
        Rules:
        - Must be 3-64 characters
        - Must start with lowercase letter
        - Can contain lowercase letters, numbers, underscores, hyphens
        - Cannot be a reserved ID
        """
        result = ValidationResult(is_valid=True)
        
        # Check type
        if not isinstance(tenant_id, str):
            result.add_error("Tenant ID must be a string")
            return result
        
        # Check length
        if len(tenant_id) < self.TENANT_ID_MIN_LENGTH:
            result.add_error(
                f"Tenant ID must be at least {self.TENANT_ID_MIN_LENGTH} characters"
            )
        
        if len(tenant_id) > self.TENANT_ID_MAX_LENGTH:
            result.add_error(
                f"Tenant ID must be at most {self.TENANT_ID_MAX_LENGTH} characters"
            )
        
        # Check pattern
        if not self.TENANT_ID_PATTERN.match(tenant_id):
            result.add_error(
                "Tenant ID must start with lowercase letter and contain only "
                "lowercase letters, numbers, underscores, or hyphens"
            )
        
        # Check reserved
        if tenant_id.lower() in self.RESERVED_TENANT_IDS:
            result.add_error(f"Tenant ID '{tenant_id}' is reserved")
        
        return result
    
    # =========================================================================
    # Existence Validation
    # =========================================================================
    
    def validate_tenant_exists(self, tenant_id: str) -> ValidationResult:
        """
        Validate that a tenant exists.
        """
        result = ValidationResult(is_valid=True)
        
        tenant_info = self._tenant_lookup(tenant_id)
        
        if not tenant_info:
            result.add_error(f"Tenant '{tenant_id}' does not exist")
        
        return result
    
    def validate_tenant_active(self, tenant_id: str) -> ValidationResult:
        """
        Validate that a tenant exists and is active.
        """
        result = self.validate_tenant_exists(tenant_id)
        
        if not result.is_valid:
            return result
        
        tenant_info = self._tenant_lookup(tenant_id)
        
        if tenant_info.status == TenantStatus.PENDING:
            result.add_warning(f"Tenant '{tenant_id}' is pending activation")
        elif tenant_info.status == TenantStatus.SUSPENDED:
            result.add_error(f"Tenant '{tenant_id}' is suspended")
        elif tenant_info.status == TenantStatus.DEACTIVATING:
            result.add_error(f"Tenant '{tenant_id}' is being deactivated")
        elif tenant_info.status == TenantStatus.ARCHIVED:
            result.add_error(f"Tenant '{tenant_id}' is archived")
        
        return result
    
    # =========================================================================
    # Cross-Tenant Validation
    # =========================================================================
    
    def validate_same_tenant(
        self,
        requested_tenant: str,
        context_tenant: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate that requested tenant matches context tenant.
        
        CRITICAL: Prevents cross-tenant data access.
        
        Args:
            requested_tenant: Tenant ID being accessed
            context_tenant: Current context tenant (uses TenantContext if None)
        
        Raises:
            SecurityError: If cross-tenant access is attempted
        """
        result = ValidationResult(is_valid=True)
        
        if context_tenant is None:
            try:
                context_tenant = TenantContext.get()
            except SecurityError:
                result.add_error("No tenant context set")
                return result
        
        if requested_tenant != context_tenant:
            result.add_error(
                f"Cross-tenant access denied: requested={requested_tenant}, "
                f"context={context_tenant}"
            )
            
            # Log this as a security event
            logger.warning(
                f"CROSS_TENANT_ACCESS_ATTEMPT: requested={requested_tenant}, "
                f"context={context_tenant}"
            )
        
        return result
    
    def validate_tenant_data_access(
        self,
        resource_tenant_id: str,
        operation: str = "read",
    ) -> None:
        """
        Validate access to tenant-scoped data.
        
        CRITICAL: Call this before any data access.
        
        Args:
            resource_tenant_id: Tenant that owns the resource
            operation: Type of operation (read, write, delete)
        
        Raises:
            SecurityError: If access is not allowed
        """
        result = self.validate_same_tenant(resource_tenant_id)
        
        if not result.is_valid:
            raise SecurityError(result.errors[0])
        
        # Check access level for write operations
        if operation in ["write", "delete"]:
            access_level = TenantContext.get_access_level()
            
            if access_level == TenantAccessLevel.READ_ONLY:
                raise SecurityError(
                    f"Read-only access cannot perform '{operation}' operation"
                )
    
    # =========================================================================
    # Permission Validation
    # =========================================================================
    
    def validate_access_level(
        self,
        required_level: TenantAccessLevel,
    ) -> ValidationResult:
        """
        Validate current access level meets requirement.
        """
        result = ValidationResult(is_valid=True)
        
        current_level = TenantContext.get_access_level()
        
        level_hierarchy = [
            TenantAccessLevel.READ_ONLY,
            TenantAccessLevel.READ_WRITE,
            TenantAccessLevel.ADMIN,
            TenantAccessLevel.SUPER_ADMIN,
        ]
        
        current_idx = level_hierarchy.index(current_level)
        required_idx = level_hierarchy.index(required_level)
        
        if current_idx < required_idx:
            result.add_error(
                f"Insufficient access level. Required: {required_level.value}, "
                f"Current: {current_level.value}"
            )
        
        return result
    
    # =========================================================================
    # Bulk Validation
    # =========================================================================
    
    def validate_tenant_ids(self, tenant_ids: List[str]) -> Dict[str, ValidationResult]:
        """
        Validate multiple tenant IDs.
        
        Returns:
            Dictionary mapping tenant_id to validation result
        """
        return {
            tenant_id: self.validate_tenant_id_format(tenant_id)
            for tenant_id in tenant_ids
        }
    
    def validate_data_batch(
        self,
        records: List[Dict[str, Any]],
        tenant_id_field: str = "tenant_id",
    ) -> ValidationResult:
        """
        Validate a batch of records all belong to current tenant.
        
        CRITICAL: Use this when processing bulk data imports.
        
        Args:
            records: List of dictionaries containing data
            tenant_id_field: Field name containing tenant ID
        
        Returns:
            ValidationResult with any cross-tenant violations
        """
        result = ValidationResult(is_valid=True)
        
        try:
            context_tenant = TenantContext.get()
        except SecurityError:
            result.add_error("No tenant context set")
            return result
        
        for i, record in enumerate(records):
            record_tenant = record.get(tenant_id_field)
            
            if record_tenant is None:
                result.add_error(f"Record {i}: missing {tenant_id_field}")
            elif record_tenant != context_tenant:
                result.add_error(
                    f"Record {i}: cross-tenant data (record={record_tenant}, "
                    f"context={context_tenant})"
                )
        
        return result


# ==============================================================================
# Validation Decorators
# ==============================================================================

def validate_tenant_id(param_name: str = "tenant_id"):
    """
    Decorator to validate tenant_id parameter format.
    
    Example:
        @validate_tenant_id("tenant_id")
        def create_resource(tenant_id: str, data: dict):
            pass
    """
    validator = TenantValidator()
    
    def decorator(func: Callable) -> Callable:
        from functools import wraps
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            tenant_id = kwargs.get(param_name)
            
            if tenant_id:
                result = validator.validate_tenant_id_format(tenant_id)
                if not result.is_valid:
                    raise ValueError(", ".join(result.errors))
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def validate_same_tenant_access(resource_param: str = "tenant_id"):
    """
    Decorator to validate resource belongs to current tenant.
    
    Example:
        @validate_same_tenant_access("resource_tenant_id")
        def get_resource(resource_id: str, resource_tenant_id: str):
            pass
    """
    validator = TenantValidator()
    
    def decorator(func: Callable) -> Callable:
        from functools import wraps
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            resource_tenant = kwargs.get(resource_param)
            
            if resource_tenant:
                validator.validate_tenant_data_access(resource_tenant, "read")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator
