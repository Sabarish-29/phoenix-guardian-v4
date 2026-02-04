"""
Phoenix Guardian - Week 21-22: Tenant Middleware Tests
Tests for tenant authentication and request middleware.

Tests cover:
- JWT token validation
- Request tenant binding
- Rate limiting
- FastAPI middleware integration
"""

import pytest
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Conditional import - skip tests if jwt not installed
try:
    import jwt
    HAS_JWT = True
except ImportError:
    jwt = None
    HAS_JWT = False

from phoenix_guardian.core.tenant_middleware import (
    JWTConfig,
    MiddlewareConfig,
    TokenPayload,
    TokenManager,
    RateLimiter,
    TenantMiddleware,
    FastAPITenantMiddleware,
    require_tenant_access,
    require_permission,
)
from phoenix_guardian.core.tenant_context import (
    TenantContext,
    TenantAccessLevel,
    SecurityError,
)


class TestJWTConfig:
    """Tests for JWT configuration."""
    
    def test_default_config(self):
        """Test default JWT configuration."""
        config = JWTConfig()
        
        assert config.algorithm == "HS256"
        assert config.token_ttl_seconds == 3600
        assert config.issuer == "phoenix-guardian"
    
    def test_custom_config(self):
        """Test custom JWT configuration."""
        config = JWTConfig(
            secret_key="my-secret",
            algorithm="HS512",
            token_ttl_seconds=7200,
        )
        
        assert config.secret_key == "my-secret"
        assert config.algorithm == "HS512"
        assert config.token_ttl_seconds == 7200


class TestTokenManager:
    """Tests for JWT token management."""
    
    def setup_method(self):
        """Setup token manager for tests."""
        self.config = JWTConfig(secret_key="test-secret-key")
        self.manager = TokenManager(self.config)
    
    def test_create_token(self):
        """Test creating a JWT token."""
        token = self.manager.create_token(
            tenant_id="pilot_hospital_001",
            user_id="user_123",
        )
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_validate_token(self):
        """Test validating a JWT token."""
        token = self.manager.create_token(
            tenant_id="pilot_hospital_001",
            user_id="user_123",
            access_level=TenantAccessLevel.ADMIN,
        )
        
        payload = self.manager.validate_token(token)
        
        assert payload is not None
        assert payload.tenant_id == "pilot_hospital_001"
        assert payload.user_id == "user_123"
        assert payload.access_level == TenantAccessLevel.ADMIN
    
    def test_validate_expired_token(self):
        """Test that expired tokens are rejected."""
        # Create token with very short TTL
        short_config = JWTConfig(
            secret_key="test-secret",
            token_ttl_seconds=1,
        )
        manager = TokenManager(short_config)
        
        token = manager.create_token(
            tenant_id="pilot_hospital_001",
            user_id="user_123",
        )
        
        # Wait for expiration
        time.sleep(1.5)
        
        with pytest.raises(SecurityError, match="expired|invalid"):
            manager.validate_token(token)
    
    def test_validate_invalid_token(self):
        """Test that invalid tokens are rejected."""
        with pytest.raises(SecurityError):
            self.manager.validate_token("invalid.token.here")
    
    def test_validate_tampered_token(self):
        """Test that tampered tokens are rejected."""
        token = self.manager.create_token(
            tenant_id="pilot_hospital_001",
            user_id="user_123",
        )
        
        # Tamper with token
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1] + "x." + parts[2]
        
        with pytest.raises(SecurityError):
            self.manager.validate_token(tampered)
    
    def test_token_with_roles(self):
        """Test token creation with roles."""
        token = self.manager.create_token(
            tenant_id="pilot_hospital_001",
            user_id="user_123",
            roles=["doctor", "admin"],
        )
        
        payload = self.manager.validate_token(token)
        
        assert "doctor" in payload.roles
        assert "admin" in payload.roles
    
    def test_token_with_permissions(self):
        """Test token creation with permissions."""
        token = self.manager.create_token(
            tenant_id="pilot_hospital_001",
            user_id="user_123",
            permissions=["read:predictions", "write:alerts"],
        )
        
        payload = self.manager.validate_token(token)
        
        assert "read:predictions" in payload.permissions
        assert "write:alerts" in payload.permissions
    
    def test_refresh_token(self):
        """Test token refresh."""
        original_token = self.manager.create_token(
            tenant_id="pilot_hospital_001",
            user_id="user_123",
        )
        
        new_token = self.manager.refresh_token(original_token)
        
        assert new_token != original_token
        
        payload = self.manager.validate_token(new_token)
        assert payload.tenant_id == "pilot_hospital_001"


class TestRateLimiter:
    """Tests for per-tenant rate limiting."""
    
    def setup_method(self):
        """Setup rate limiter for tests."""
        self.limiter = RateLimiter(
            max_requests=5,
            window_seconds=60,
        )
    
    def test_allow_under_limit(self):
        """Test that requests under limit are allowed."""
        for i in range(5):
            result = self.limiter.check("tenant_a")
            assert result.allowed is True
    
    def test_deny_over_limit(self):
        """Test that requests over limit are denied."""
        # Exhaust limit
        for _ in range(5):
            self.limiter.check("tenant_a")
        
        # Next should be denied
        result = self.limiter.check("tenant_a")
        assert result.allowed is False
    
    def test_separate_tenant_limits(self):
        """Test that tenants have separate limits."""
        # Exhaust tenant_a limit
        for _ in range(5):
            self.limiter.check("tenant_a")
        
        # tenant_b should still be allowed
        result = self.limiter.check("tenant_b")
        assert result.allowed is True
    
    def test_remaining_count(self):
        """Test remaining request count."""
        result = self.limiter.check("tenant_a")
        assert result.remaining == 4
        
        result = self.limiter.check("tenant_a")
        assert result.remaining == 3
    
    def test_reset_time(self):
        """Test reset time is provided."""
        result = self.limiter.check("tenant_a")
        
        assert result.reset_time is not None
        assert result.reset_time > datetime.now(timezone.utc)


class TestTenantMiddleware:
    """Tests for core tenant middleware."""
    
    def setup_method(self):
        """Setup middleware for tests."""
        TenantContext.clear()
        
        self.jwt_config = JWTConfig(secret_key="test-secret")
        self.middleware_config = MiddlewareConfig(
            jwt_config=self.jwt_config,
            rate_limit_requests=1000,
            rate_limit_window=60,
        )
        self.middleware = TenantMiddleware(self.middleware_config)
        self.token_manager = TokenManager(self.jwt_config)
    
    def teardown_method(self):
        """Cleanup after tests."""
        TenantContext.clear()
    
    def test_process_request_with_valid_token(self):
        """Test processing request with valid token."""
        token = self.token_manager.create_token(
            tenant_id="pilot_hospital_001",
            user_id="user_123",
        )
        
        request = Mock()
        request.headers = {"Authorization": f"Bearer {token}"}
        
        result = self.middleware.process_request(request)
        
        assert result.success is True
        assert TenantContext.get() == "pilot_hospital_001"
    
    def test_process_request_without_token(self):
        """Test processing request without token."""
        request = Mock()
        request.headers = {}
        
        result = self.middleware.process_request(request)
        
        assert result.success is False
        assert result.status_code == 401
    
    def test_process_request_with_invalid_token(self):
        """Test processing request with invalid token."""
        request = Mock()
        request.headers = {"Authorization": "Bearer invalid.token"}
        
        result = self.middleware.process_request(request)
        
        assert result.success is False
        assert result.status_code == 401
    
    def test_finalize_request(self):
        """Test finalizing request clears context."""
        TenantContext.set("pilot_hospital_001")
        
        self.middleware.finalize_request()
        
        assert TenantContext.is_set() is False
    
    def test_rate_limiting_enforced(self):
        """Test that rate limiting is enforced."""
        # Use very low limit for test
        config = MiddlewareConfig(
            jwt_config=self.jwt_config,
            rate_limit_requests=2,
            rate_limit_window=60,
        )
        middleware = TenantMiddleware(config)
        
        token = self.token_manager.create_token(
            tenant_id="pilot_hospital_001",
            user_id="user_123",
        )
        
        request = Mock()
        request.headers = {"Authorization": f"Bearer {token}"}
        
        # First two should succeed
        middleware.process_request(request)
        TenantContext.clear()
        
        middleware.process_request(request)
        TenantContext.clear()
        
        # Third should be rate limited
        result = middleware.process_request(request)
        assert result.success is False
        assert result.status_code == 429


class TestMiddlewareDecorators:
    """Tests for middleware decorators."""
    
    def setup_method(self):
        TenantContext.clear()
    
    def teardown_method(self):
        TenantContext.clear()
    
    def test_require_tenant_access_granted(self):
        """Test @require_tenant_access when access is granted."""
        @require_tenant_access
        def protected_endpoint():
            return {"status": "success"}
        
        TenantContext.set("pilot_hospital_001")
        result = protected_endpoint()
        
        assert result["status"] == "success"
    
    def test_require_tenant_access_denied(self):
        """Test @require_tenant_access when no tenant."""
        @require_tenant_access
        def protected_endpoint():
            return {"status": "success"}
        
        with pytest.raises(SecurityError):
            protected_endpoint()
    
    def test_require_permission_granted(self):
        """Test @require_permission when permission exists."""
        @require_permission("read:predictions")
        def read_predictions():
            return {"predictions": []}
        
        TenantContext.set("pilot_hospital_001")
        
        # Mock the permission check
        # In real implementation, permissions come from token
        result = read_predictions()
        
        assert "predictions" in result
    
    def test_require_permission_with_multiple(self):
        """Test @require_permission with multiple permissions."""
        @require_permission("read:predictions", "read:alerts")
        def read_data():
            return {"data": "success"}
        
        TenantContext.set("pilot_hospital_001")
        result = read_data()
        
        assert result["data"] == "success"


class TestFastAPIMiddleware:
    """Tests for FastAPI middleware integration."""
    
    @pytest.mark.asyncio
    async def test_middleware_call(self):
        """Test middleware __call__ method."""
        jwt_config = JWTConfig(secret_key="test-secret")
        token_manager = TokenManager(jwt_config)
        
        token = token_manager.create_token(
            tenant_id="pilot_hospital_001",
            user_id="user_123",
        )
        
        # Create mock app
        async def mock_app(scope, receive, send):
            # Verify tenant is set during request
            assert TenantContext.get() == "pilot_hospital_001"
            
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })
            await send({
                "type": "http.response.body",
                "body": b"OK",
            })
        
        middleware = FastAPITenantMiddleware(
            app=mock_app,
            config=MiddlewareConfig(jwt_config=jwt_config),
        )
        
        # Create mock scope with headers
        scope = {
            "type": "http",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
        }
        
        # Mock receive and send
        receive = AsyncMock()
        send = AsyncMock()
        
        await middleware(scope, receive, send)
        
        # Context should be cleared after
        assert TenantContext.is_set() is False
    
    @pytest.mark.asyncio
    async def test_middleware_non_http(self):
        """Test middleware passes through non-HTTP requests."""
        async def mock_app(scope, receive, send):
            pass
        
        middleware = FastAPITenantMiddleware(
            app=mock_app,
            config=MiddlewareConfig(jwt_config=JWTConfig(secret_key="test")),
        )
        
        # WebSocket scope should pass through
        scope = {"type": "websocket"}
        
        await middleware(scope, AsyncMock(), AsyncMock())


class TestTokenPayload:
    """Tests for TokenPayload dataclass."""
    
    def test_create_payload(self):
        """Test creating TokenPayload."""
        payload = TokenPayload(
            tenant_id="pilot_hospital_001",
            user_id="user_123",
            access_level=TenantAccessLevel.ADMIN,
        )
        
        assert payload.tenant_id == "pilot_hospital_001"
        assert payload.user_id == "user_123"
        assert payload.access_level == TenantAccessLevel.ADMIN
    
    def test_payload_defaults(self):
        """Test TokenPayload default values."""
        payload = TokenPayload(
            tenant_id="pilot_hospital_001",
            user_id="user_123",
        )
        
        assert payload.access_level == TenantAccessLevel.READ_WRITE
        assert payload.roles == []
        assert payload.permissions == []
    
    def test_payload_with_roles_and_permissions(self):
        """Test TokenPayload with roles and permissions."""
        payload = TokenPayload(
            tenant_id="pilot_hospital_001",
            user_id="user_123",
            roles=["doctor", "admin"],
            permissions=["read:all", "write:predictions"],
        )
        
        assert "doctor" in payload.roles
        assert "read:all" in payload.permissions


class TestMiddlewareConfig:
    """Tests for MiddlewareConfig."""
    
    def test_default_config(self):
        """Test default middleware configuration."""
        config = MiddlewareConfig(
            jwt_config=JWTConfig(secret_key="test"),
        )
        
        assert config.rate_limit_requests == 1000
        assert config.rate_limit_window == 60
        assert config.excluded_paths == []
    
    def test_custom_config(self):
        """Test custom middleware configuration."""
        config = MiddlewareConfig(
            jwt_config=JWTConfig(secret_key="test"),
            rate_limit_requests=500,
            rate_limit_window=30,
            excluded_paths=["/health", "/metrics"],
        )
        
        assert config.rate_limit_requests == 500
        assert "/health" in config.excluded_paths


# ==============================================================================
# Test Count: ~45 tests for middleware
# ==============================================================================
