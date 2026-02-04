# ADR-001: PostgreSQL Row-Level Security for Tenant Isolation

## Status
Accepted

## Date
Day 95 (Phase 3)

## Context

Phoenix Guardian is transitioning to a multi-tenant SaaS platform serving 500+ hospital systems. Each tenant's data (patient records, encounters, SOAP notes, threat logs) must be completely isolated from other tenants to meet HIPAA requirements and customer contractual obligations.

We needed to choose an isolation strategy that:
1. Guarantees data isolation at the database level
2. Scales to 500+ tenants without performance degradation
3. Simplifies application code by not requiring tenant filtering in every query
4. Provides auditable isolation for SOC 2 compliance
5. Minimizes infrastructure overhead

### Options Evaluated

1. **Separate databases per tenant** - Complete isolation but high operational overhead
2. **Separate schemas per tenant** - Good isolation but migration complexity
3. **Shared schema with application-level filtering** - Simple but error-prone
4. **Shared schema with Row-Level Security (RLS)** - Database-enforced, auditable

## Decision

We will implement PostgreSQL Row-Level Security (RLS) for tenant isolation.

All tables containing tenant-specific data will:
1. Include a `tenant_id` column as part of the primary key or with NOT NULL constraint
2. Have RLS policies enabled that filter rows based on `current_setting('app.tenant_id')`
3. Use composite indexes starting with `tenant_id` for query performance
4. Be tested with cross-tenant access prevention tests

### Implementation Details

```sql
-- Example RLS policy for encounters table
ALTER TABLE encounters ENABLE ROW LEVEL SECURITY;
ALTER TABLE encounters FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON encounters
    USING (tenant_id = current_setting('app.tenant_id')::uuid);

CREATE POLICY tenant_insert ON encounters
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
```

Application connection setup:
```python
async def set_tenant_context(connection, tenant_id: str):
    await connection.execute(
        "SET LOCAL app.tenant_id = $1",
        tenant_id
    )
```

## Consequences

### Positive

1. **Guaranteed isolation** - Database enforces isolation, cannot be bypassed by application bugs
2. **Simplified application code** - No tenant filtering needed in queries
3. **Auditable** - Policies can be reviewed by security auditors
4. **Performance** - Minimal overhead (<2%) with proper indexing
5. **Scalability** - Single database scales to 1000+ tenants
6. **Compliance** - Meets HIPAA and SOC 2 isolation requirements

### Negative

1. **Connection setup overhead** - Must set tenant context on each connection
2. **Migration complexity** - Adding RLS to existing tables requires careful planning
3. **Debugging complexity** - Queries may behave unexpectedly without tenant context
4. **Superuser bypass** - PostgreSQL superusers bypass RLS by default
5. **Join complexity** - All joined tables must have matching tenant_id

### Risks

1. **Performance with complex queries** - Mitigated by composite indexes
2. **Forgot to set context** - Mitigated by connection wrapper enforcement
3. **Superuser data exposure** - Mitigated by restricted superuser access

## Alternatives Considered

### Separate Databases per Tenant

**Pros:**
- Complete isolation
- Independent scaling
- Simple migrations

**Cons:**
- 500+ databases to manage
- Connection pool per database
- High operational overhead
- Expensive infrastructure

**Rejected because:** Operational complexity at scale is prohibitive.

### Separate Schemas per Tenant

**Pros:**
- Good isolation within single database
- Easier migrations than separate databases

**Cons:**
- Schema proliferation
- Complex cross-tenant queries
- Migration coordination

**Rejected because:** Schema management complexity at 500+ tenants.

### Application-Level Filtering

**Pros:**
- Simplest implementation
- No database changes needed

**Cons:**
- Error-prone (forget WHERE clause)
- Not auditable
- Security depends on developer discipline
- Harder to verify isolation

**Rejected because:** Insufficient security guarantees for healthcare data.

## Validation

1. **Unit tests** - RLS policies tested with pytest
2. **Integration tests** - Cross-tenant access prevented in E2E tests
3. **Penetration testing** - Third-party validation of isolation
4. **Audit queries** - All queries verified to include RLS filtering

## References

- PostgreSQL RLS Documentation: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- HIPAA Technical Safeguards: 45 CFR § 164.312
- Phase 3 Multi-Tenant Architecture Design Document
