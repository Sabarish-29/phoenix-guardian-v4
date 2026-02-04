"""
Authentication and authorization module.

Provides JWT-based authentication, password hashing,
and role-based access control for HIPAA compliance.
"""

from .utils import (
    # Password utilities
    hash_password,
    verify_password,
    # Token utilities
    create_access_token,
    create_refresh_token,
    decode_token,
    # Dependencies
    get_current_user,
    get_current_active_user,
    RoleChecker,
    require_physician,
    require_admin,
    # Authentication
    authenticate_user,
    create_tokens_for_user,
    # Exceptions
    AuthenticationError,
    AuthorizationError,
    # Security
    security,
)

__all__ = [
    # Password utilities
    "hash_password",
    "verify_password",
    # Token utilities
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    # Dependencies
    "get_current_user",
    "get_current_active_user",
    "RoleChecker",
    "require_physician",
    "require_admin",
    # Authentication
    "authenticate_user",
    "create_tokens_for_user",
    # Exceptions
    "AuthenticationError",
    "AuthorizationError",
    # Security
    "security",
]
