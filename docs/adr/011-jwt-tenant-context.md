# ADR-011: JWT-based Tenant Context Propagation

## Status
Accepted

## Date
Day 96 (Phase 3)

## Context

In a multi-tenant environment, every request must be associated with a tenant context for:
1. Database RLS policy enforcement
2. Audit logging
3. Rate limiting per tenant
4. Authorization decisions
5. Analytics and metrics segmentation

## Decision

We will embed tenant context in JWT claims and propagate it through all service layers.

### JWT Structure

```json
{
  "sub": "user-uuid",
  "iss": "phoenix-guardian",
  "aud": "phoenix-guardian-api",
  "exp": 1699999999,
  "iat": 1699996399,
  "tenant_id": "hospital-uuid",
  "tenant_slug": "general-hospital",
  "roles": ["physician", "admin"],
  "permissions": [
    "encounter:read",
    "encounter:write",
    "soap:read",
    "soap:write"
  ],
  "department": "cardiology",
  "session_id": "session-uuid"
}
```

### Implementation

```python
from pydantic import BaseModel
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
import jwt

class TenantContext(BaseModel):
    tenant_id: str
    tenant_slug: str
    user_id: str
    roles: list[str]
    permissions: list[str]
    session_id: str

async def get_tenant_context(
    token: str = Depends(HTTPBearer())
) -> TenantContext:
    """Extract and validate tenant context from JWT."""
    try:
        payload = jwt.decode(
            token.credentials,
            key=settings.JWT_PUBLIC_KEY,
            algorithms=["RS256"],
            audience="phoenix-guardian-api"
        )
        return TenantContext(
            tenant_id=payload["tenant_id"],
            tenant_slug=payload["tenant_slug"],
            user_id=payload["sub"],
            roles=payload.get("roles", []),
            permissions=payload.get("permissions", []),
            session_id=payload["session_id"]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"Invalid token: {e}")
```

## Consequences

### Positive
- Stateless tenant identification
- Self-contained authorization data
- Works across service boundaries
- Audit trail with user and tenant context

### Negative
- Token size increases with permissions
- Cannot revoke individual tokens immediately
- Refresh needed for permission updates

## References
- RFC 7519 (JWT): https://tools.ietf.org/html/rfc7519
- ADR-001: RLS Tenant Isolation
