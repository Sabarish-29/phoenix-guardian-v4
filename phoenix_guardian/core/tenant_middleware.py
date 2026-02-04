"""
Phoenix Guardian - Tenant Middleware
FastAPI/Flask middleware for tenant isolation.

CRITICAL SECURITY: This middleware runs on EVERY request.
It extracts the tenant_id from the JWT token and sets TenantContext.

If tenant extraction fails, the request is REJECTED.
"""

import logging
import time
import jwt
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from functools import wraps
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
# Configuration
# ==============================================================================

@dataclass
class JWTConfig:
    """JWT configuration for tenant middleware."""
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    token_expiry_hours: int = 24
    issuer: str = "phoenix-guardian"
    audience: str = "phoenix-api"


@dataclass
class MiddlewareConfig:
    """Middleware configuration."""
    jwt: JWTConfig = field(default_factory=JWTConfig)
    
    # Paths that don't require authentication
    public_paths: List[str] = field(default_factory=lambda: [
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
    ])
    
    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 1000
    rate_limit_window_seconds: int = 60
    
    # Logging
    log_all_requests: bool = True
    log_sensitive_headers: bool = False


# ==============================================================================
# Token Management
# ==============================================================================

@dataclass
class TokenPayload:
    """
    JWT token payload for tenant authentication.
    """
    tenant_id: str
    user_id: str
    access_level: TenantAccessLevel = TenantAccessLevel.READ_WRITE
    
    # Standard JWT claims
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    issuer: str = "phoenix-guardian"
    
    # Additional claims
    roles: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    
    def to_jwt_claims(self) -> Dict[str, Any]:
        """Convert to JWT claims dictionary."""
        exp = self.expires_at or (self.issued_at + timedelta(hours=24))
        
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "access_level": self.access_level.value,
            "iat": int(self.issued_at.timestamp()),
            "exp": int(exp.timestamp()),
            "iss": self.issuer,
            "roles": self.roles,
            "permissions": self.permissions,
        }
    
    @classmethod
    def from_jwt_claims(cls, claims: Dict[str, Any]) -> "TokenPayload":
        """Create from JWT claims dictionary."""
        return cls(
            tenant_id=claims["tenant_id"],
            user_id=claims["user_id"],
            access_level=TenantAccessLevel(claims.get("access_level", "read_write")),
            issued_at=datetime.fromtimestamp(claims["iat"], tz=timezone.utc),
            expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc),
            issuer=claims.get("iss", "phoenix-guardian"),
            roles=claims.get("roles", []),
            permissions=claims.get("permissions", []),
        )


class TokenManager:
    """
    Manages JWT token creation and validation.
    """
    
    def __init__(self, config: JWTConfig):
        self.config = config
    
    def create_token(self, payload: TokenPayload) -> str:
        """
        Create a signed JWT token.
        
        Args:
            payload: Token payload with tenant and user info
        
        Returns:
            Signed JWT token string
        """
        claims = payload.to_jwt_claims()
        claims["aud"] = self.config.audience
        
        token = jwt.encode(
            claims,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )
        
        logger.info(
            f"Token created for tenant={payload.tenant_id} user={payload.user_id}"
        )
        
        return token
    
    def validate_token(self, token: str) -> TokenPayload:
        """
        Validate and decode a JWT token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded token payload
        
        Raises:
            SecurityError: If token is invalid, expired, or malformed
        """
        try:
            claims = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
                audience=self.config.audience,
            )
            
            return TokenPayload.from_jwt_claims(claims)
            
        except jwt.ExpiredSignatureError:
            raise SecurityError("Token has expired")
        except jwt.InvalidAudienceError:
            raise SecurityError("Invalid token audience")
        except jwt.InvalidIssuerError:
            raise SecurityError("Invalid token issuer")
        except jwt.InvalidTokenError as e:
            raise SecurityError(f"Invalid token: {str(e)}")
    
    def refresh_token(
        self,
        old_token: str,
        extend_hours: int = 24,
    ) -> str:
        """
        Refresh an existing token with new expiry.
        
        Args:
            old_token: Current valid token
            extend_hours: Hours to extend expiry
        
        Returns:
            New token with extended expiry
        """
        payload = self.validate_token(old_token)
        payload.issued_at = datetime.now(timezone.utc)
        payload.expires_at = payload.issued_at + timedelta(hours=extend_hours)
        
        return self.create_token(payload)


# ==============================================================================
# Rate Limiting
# ==============================================================================

class RateLimiter:
    """
    Simple in-memory rate limiter per tenant.
    
    In production, use Redis for distributed rate limiting.
    """
    
    def __init__(
        self,
        max_requests: int = 1000,
        window_seconds: int = 60,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, tenant_id: str) -> Tuple[bool, int]:
        """
        Check if a request is allowed for this tenant.
        
        Returns:
            Tuple of (allowed, remaining_requests)
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests
        if tenant_id in self._requests:
            self._requests[tenant_id] = [
                ts for ts in self._requests[tenant_id]
                if ts > window_start
            ]
        else:
            self._requests[tenant_id] = []
        
        # Check limit
        current_count = len(self._requests[tenant_id])
        remaining = max(0, self.max_requests - current_count)
        
        if current_count >= self.max_requests:
            return False, 0
        
        # Record this request
        self._requests[tenant_id].append(now)
        
        return True, remaining - 1
    
    def reset(self, tenant_id: str) -> None:
        """Reset rate limit for a tenant."""
        if tenant_id in self._requests:
            del self._requests[tenant_id]


# ==============================================================================
# Tenant Middleware (Core)
# ==============================================================================

class TenantMiddleware:
    """
    Core tenant middleware for request processing.
    
    Workflow:
    1. Check if path is public
    2. Extract Authorization header
    3. Decode JWT token
    4. Extract tenant_id claim
    5. Validate tenant exists and is active
    6. Check rate limits
    7. Set TenantContext for this request
    8. Process request
    9. Clear TenantContext after request
    
    Example usage with FastAPI:
        app = FastAPI()
        middleware = TenantMiddleware(config)
        app.add_middleware(middleware.as_fastapi_middleware())
    """
    
    def __init__(
        self,
        config: Optional[MiddlewareConfig] = None,
        tenant_validator: Optional[Callable[[str], TenantInfo]] = None,
    ):
        self.config = config or MiddlewareConfig()
        self.token_manager = TokenManager(self.config.jwt)
        self.rate_limiter = RateLimiter(
            max_requests=self.config.rate_limit_requests,
            window_seconds=self.config.rate_limit_window_seconds,
        )
        self._tenant_validator = tenant_validator
    
    def is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        for public_path in self.config.public_paths:
            if path.startswith(public_path):
                return True
        return False
    
    def extract_token(self, authorization: Optional[str]) -> str:
        """
        Extract token from Authorization header.
        
        Raises:
            SecurityError: If header is missing or malformed
        """
        if not authorization:
            raise SecurityError("Missing Authorization header")
        
        if not authorization.startswith("Bearer "):
            raise SecurityError("Invalid Authorization header format. Expected: Bearer <token>")
        
        return authorization.split(" ", 1)[1]
    
    def validate_tenant(self, tenant_id: str) -> TenantInfo:
        """
        Validate that tenant exists and is active.
        
        Returns:
            TenantInfo if valid
        
        Raises:
            TenantNotFoundError: If tenant doesn't exist
            TenantSuspendedError: If tenant is suspended
        """
        # Try custom validator first
        if self._tenant_validator:
            return self._tenant_validator(tenant_id)
        
        # Fall back to context registry
        tenant_info = TenantContext.get_tenant_info(tenant_id)
        
        if not tenant_info:
            raise TenantNotFoundError(f"Tenant '{tenant_id}' not found")
        
        if tenant_info.status == TenantStatus.SUSPENDED:
            raise TenantSuspendedError(f"Tenant '{tenant_id}' is suspended")
        
        if tenant_info.status == TenantStatus.ARCHIVED:
            raise TenantNotFoundError(f"Tenant '{tenant_id}' is archived")
        
        return tenant_info
    
    def process_request(
        self,
        path: str,
        method: str,
        authorization: Optional[str],
        request_id: Optional[str] = None,
    ) -> TokenPayload:
        """
        Process an incoming request and set tenant context.
        
        Args:
            path: Request path
            method: HTTP method
            authorization: Authorization header value
            request_id: Optional request ID for tracing
        
        Returns:
            Decoded token payload
        
        Raises:
            SecurityError: If authentication fails
            TenantNotFoundError: If tenant doesn't exist
            TenantSuspendedError: If tenant is suspended
        """
        start_time = time.time()
        
        try:
            # Step 1: Extract token
            token = self.extract_token(authorization)
            
            # Step 2: Validate token
            payload = self.token_manager.validate_token(token)
            
            # Step 3: Validate tenant
            tenant_info = self.validate_tenant(payload.tenant_id)
            
            # Step 4: Check rate limits
            if self.config.rate_limit_enabled:
                allowed, remaining = self.rate_limiter.is_allowed(payload.tenant_id)
                if not allowed:
                    raise SecurityError(
                        f"Rate limit exceeded for tenant '{payload.tenant_id}'"
                    )
            
            # Step 5: Set tenant context
            TenantContext.set(
                tenant_id=payload.tenant_id,
                user_id=payload.user_id,
                access_level=payload.access_level,
            )
            
            # Log successful authentication
            if self.config.log_all_requests:
                elapsed = (time.time() - start_time) * 1000
                logger.info(
                    f"AUTH_SUCCESS: tenant={payload.tenant_id} user={payload.user_id} "
                    f"path={path} method={method} request_id={request_id} "
                    f"auth_ms={elapsed:.2f}"
                )
            
            return payload
            
        except (SecurityError, TenantNotFoundError, TenantSuspendedError) as e:
            elapsed = (time.time() - start_time) * 1000
            logger.warning(
                f"AUTH_FAILURE: error={str(e)} path={path} method={method} "
                f"request_id={request_id} auth_ms={elapsed:.2f}"
            )
            raise
    
    def finalize_request(self) -> None:
        """
        Clean up after request processing.
        
        Called after request is complete (in finally block).
        """
        TenantContext.clear()


# ==============================================================================
# FastAPI Integration
# ==============================================================================

class FastAPITenantMiddleware:
    """
    FastAPI middleware wrapper for TenantMiddleware.
    
    Usage:
        from fastapi import FastAPI
        
        app = FastAPI()
        
        middleware = TenantMiddleware()
        app.add_middleware(FastAPITenantMiddleware, core=middleware)
    """
    
    def __init__(self, app, core: TenantMiddleware):
        self.app = app
        self.core = core
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract request info
        path = scope.get("path", "/")
        method = scope.get("method", "GET")
        headers = dict(scope.get("headers", []))
        
        # Get authorization header (headers are bytes)
        authorization = headers.get(b"authorization", b"").decode()
        request_id = headers.get(b"x-request-id", b"").decode()
        
        # Check if public path
        if self.core.is_public_path(path):
            await self.app(scope, receive, send)
            return
        
        try:
            # Process authentication
            self.core.process_request(path, method, authorization, request_id)
            
            # Process request
            await self.app(scope, receive, send)
            
        except SecurityError as e:
            await self._send_error(send, 401, "Unauthorized", str(e))
        except TenantNotFoundError as e:
            await self._send_error(send, 404, "Tenant Not Found", str(e))
        except TenantSuspendedError as e:
            await self._send_error(send, 403, "Tenant Suspended", str(e))
        finally:
            self.core.finalize_request()
    
    async def _send_error(
        self,
        send,
        status_code: int,
        error: str,
        message: str,
    ):
        """Send error response."""
        import json
        
        body = json.dumps({
            "error": error,
            "message": message,
        }).encode()
        
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                [b"content-type", b"application/json"],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })


# ==============================================================================
# Route Decorators
# ==============================================================================

def require_tenant_access(
    allowed_tenants: Optional[List[str]] = None,
    denied_tenants: Optional[List[str]] = None,
):
    """
    Decorator to restrict route access to specific tenants.
    
    Example:
        @app.get("/admin/reports")
        @require_tenant_access(allowed_tenants=["pilot_hospital_003"])
        async def get_admin_reports():
            # Only pilot_hospital_003 can access this
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_tenant = TenantContext.get()
            
            if allowed_tenants and current_tenant not in allowed_tenants:
                raise SecurityError(
                    f"Tenant {current_tenant} not authorized for this resource"
                )
            
            if denied_tenants and current_tenant in denied_tenants:
                raise SecurityError(
                    f"Tenant {current_tenant} is blocked from this resource"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_permission(permission: str):
    """
    Decorator to require a specific permission.
    
    Example:
        @app.delete("/patients/{id}")
        @require_permission("patients:delete")
        async def delete_patient(id: str):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # In production, check permissions from token payload
            # This is a simplified version
            access_level = TenantContext.get_access_level()
            
            if access_level not in [TenantAccessLevel.ADMIN, TenantAccessLevel.SUPER_ADMIN]:
                raise SecurityError(
                    f"Permission '{permission}' required"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
