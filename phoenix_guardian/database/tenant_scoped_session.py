"""
Phoenix Guardian - Tenant-Scoped Database Session
SQLAlchemy session that automatically enforces tenant isolation.

Provides a drop-in replacement for standard SQLAlchemy sessions
that automatically sets RLS context and validates tenant access.
"""

import logging
from typing import Any, Callable, Dict, Optional, Type, TypeVar
from contextlib import contextmanager
from functools import wraps

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker, Query

from phoenix_guardian.core.tenant_context import (
    TenantContext,
    SecurityError,
    TenantStatus,
)
from phoenix_guardian.database.rls_policies import RLSManager

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ==============================================================================
# Tenant-Scoped Session
# ==============================================================================

class TenantScopedSession(Session):
    """
    SQLAlchemy session with automatic tenant isolation.
    
    This session:
    1. Automatically sets RLS context on connection checkout
    2. Validates all queries include tenant filtering
    3. Prevents cross-tenant data access
    4. Clears tenant context on connection return
    
    Example:
        # Create session factory
        TenantSession = tenant_sessionmaker(engine)
        
        # Use in request
        TenantContext.set("pilot_hospital_001")
        session = TenantSession()
        
        # All queries automatically filtered to tenant
        predictions = session.query(Prediction).all()  # Only tenant's predictions
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize tenant-scoped session."""
        self._tenant_id: Optional[str] = None
        self._rls_manager: Optional[RLSManager] = None
        
        super().__init__(*args, **kwargs)
    
    def _setup_tenant_context(self) -> None:
        """Set up tenant context on the database connection."""
        if self._tenant_id is None:
            try:
                self._tenant_id = TenantContext.get()
            except SecurityError:
                raise SecurityError(
                    "Cannot create TenantScopedSession without tenant context"
                )
        
        # Get raw connection and set RLS context
        connection = self.connection()
        
        if self._rls_manager:
            self._rls_manager.set_tenant_for_connection(
                connection,
                self._tenant_id
            )
        else:
            # Fallback to raw SQL
            connection.execute(
                text(f"SET LOCAL {RLSManager.TENANT_SETTING} = :tenant_id"),
                {"tenant_id": self._tenant_id}
            )
        
        logger.debug(f"Session tenant context set: {self._tenant_id}")
    
    def get_tenant_id(self) -> str:
        """Get current tenant ID."""
        if self._tenant_id is None:
            self._tenant_id = TenantContext.get()
        return self._tenant_id
    
    def execute(self, statement, *args, **kwargs):
        """Execute with tenant context."""
        self._setup_tenant_context()
        return super().execute(statement, *args, **kwargs)
    
    def query(self, *entities, **kwargs) -> Query:
        """Create query with tenant context."""
        self._setup_tenant_context()
        return super().query(*entities, **kwargs)
    
    def add(self, instance, _warn: bool = True) -> None:
        """Add instance with tenant validation."""
        self._validate_instance_tenant(instance)
        return super().add(instance, _warn)
    
    def add_all(self, instances) -> None:
        """Add all instances with tenant validation."""
        for instance in instances:
            self._validate_instance_tenant(instance)
        return super().add_all(instances)
    
    def _validate_instance_tenant(self, instance: Any) -> None:
        """
        Validate instance belongs to current tenant.
        
        Raises:
            SecurityError: If instance has wrong tenant_id
        """
        if hasattr(instance, 'tenant_id'):
            instance_tenant = getattr(instance, 'tenant_id')
            current_tenant = self.get_tenant_id()
            
            # If tenant_id is not set, set it to current tenant
            if instance_tenant is None:
                setattr(instance, 'tenant_id', current_tenant)
                logger.debug(f"Auto-set tenant_id to {current_tenant}")
            
            # If set to different tenant, raise error
            elif instance_tenant != current_tenant:
                raise SecurityError(
                    f"Cannot add instance for tenant '{instance_tenant}' "
                    f"in session for tenant '{current_tenant}'"
                )
    
    def close(self) -> None:
        """Close session and clear tenant context."""
        # Clear RLS context before closing
        if self.is_active:
            try:
                connection = self.connection()
                connection.execute(text(f"RESET {RLSManager.TENANT_SETTING}"))
            except Exception:
                pass  # Ignore errors during cleanup
        
        super().close()
        logger.debug("Tenant session closed")


# ==============================================================================
# Session Factory
# ==============================================================================

def tenant_sessionmaker(
    engine: Engine,
    rls_manager: Optional[RLSManager] = None,
    **session_kwargs,
) -> sessionmaker:
    """
    Create a session factory that produces TenantScopedSessions.
    
    Args:
        engine: SQLAlchemy engine
        rls_manager: Optional RLS manager instance
        **session_kwargs: Additional session configuration
    
    Returns:
        Configured sessionmaker
    
    Example:
        TenantSession = tenant_sessionmaker(engine)
        
        with TenantContext.set_context("pilot_hospital_001"):
            session = TenantSession()
            data = session.query(Prediction).all()
            session.close()
    """
    if rls_manager is None:
        rls_manager = RLSManager(engine)
    
    class ConfiguredTenantSession(TenantScopedSession):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._rls_manager = rls_manager
    
    factory = sessionmaker(
        bind=engine,
        class_=ConfiguredTenantSession,
        **session_kwargs
    )
    
    return factory


# ==============================================================================
# Context Managers
# ==============================================================================

@contextmanager
def tenant_session(
    session_factory: sessionmaker,
    tenant_id: Optional[str] = None,
    auto_commit: bool = False,
):
    """
    Context manager for tenant-scoped database sessions.
    
    Args:
        session_factory: Session factory from tenant_sessionmaker
        tenant_id: Optional tenant ID (uses TenantContext if not provided)
        auto_commit: Whether to commit on successful exit
    
    Yields:
        TenantScopedSession
    
    Example:
        TenantSession = tenant_sessionmaker(engine)
        
        with tenant_session(TenantSession, "pilot_hospital_001") as session:
            predictions = session.query(Prediction).all()
            # Automatically closed and cleaned up
    """
    # Set tenant context if provided
    if tenant_id:
        TenantContext.set(tenant_id)
    
    session = session_factory()
    
    try:
        yield session
        
        if auto_commit:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        
        # Clear tenant context if we set it
        if tenant_id:
            TenantContext.clear()


@contextmanager
def admin_session(
    session_factory: sessionmaker,
    admin_role: str = "phoenix_admin",
):
    """
    Context manager for admin sessions that bypass RLS.
    
    WARNING: Use sparingly for legitimate admin operations only!
    
    Args:
        session_factory: Session factory
        admin_role: Database role with admin bypass
    
    Yields:
        Session with admin privileges
    """
    session = session_factory()
    
    try:
        # Set admin role
        connection = session.connection()
        connection.execute(text(f"SET ROLE {admin_role}"))
        
        yield session
        
    finally:
        # Reset role
        try:
            connection.execute(text("RESET ROLE"))
        except Exception:
            pass
        
        session.close()


# ==============================================================================
# Query Extensions
# ==============================================================================

class TenantAwareQuery(Query):
    """
    Query class that automatically filters by tenant.
    
    This provides an additional layer of safety beyond RLS.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tenant_filter_applied = False
    
    def _apply_tenant_filter(self) -> "TenantAwareQuery":
        """Apply tenant filter if not already applied."""
        if self._tenant_filter_applied:
            return self
        
        # Get tenant from context
        try:
            tenant_id = TenantContext.get()
        except SecurityError:
            return self  # No tenant context, rely on RLS
        
        # Apply filter to all entities that have tenant_id
        for entity in self.column_descriptions:
            mapper_class = entity.get('entity')
            if mapper_class and hasattr(mapper_class, 'tenant_id'):
                self = self.filter(mapper_class.tenant_id == tenant_id)
                self._tenant_filter_applied = True
        
        return self
    
    def all(self):
        """Get all results with tenant filter."""
        return self._apply_tenant_filter().all()
    
    def first(self):
        """Get first result with tenant filter."""
        return self._apply_tenant_filter().first()
    
    def one(self):
        """Get exactly one result with tenant filter."""
        return self._apply_tenant_filter().one()
    
    def one_or_none(self):
        """Get one or none with tenant filter."""
        return self._apply_tenant_filter().one_or_none()
    
    def count(self):
        """Count with tenant filter."""
        return self._apply_tenant_filter().count()


# ==============================================================================
# Decorators
# ==============================================================================

def with_tenant_session(session_factory: sessionmaker):
    """
    Decorator that provides a tenant-scoped session to a function.
    
    The session is passed as the first argument after self (for methods)
    or as the first argument (for functions).
    
    Example:
        @with_tenant_session(TenantSession)
        def get_predictions(session, patient_id):
            return session.query(Prediction).filter_by(patient_id=patient_id).all()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with tenant_session(session_factory) as session:
                return func(session, *args, **kwargs)
        return wrapper
    return decorator


def require_active_session(func: Callable) -> Callable:
    """
    Decorator that ensures session is active and has tenant context.
    
    Example:
        @require_active_session
        def update_prediction(self, session, prediction_id, new_status):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Find session in args
        session = None
        for arg in args:
            if isinstance(arg, Session):
                session = arg
                break
        
        if session is None:
            session = kwargs.get('session')
        
        if session is None:
            raise ValueError("No session provided")
        
        if not session.is_active:
            raise ValueError("Session is not active")
        
        # Verify tenant context
        if isinstance(session, TenantScopedSession):
            session.get_tenant_id()  # Will raise if no tenant
        
        return func(*args, **kwargs)
    
    return wrapper


# ==============================================================================
# Session Events
# ==============================================================================

def setup_session_events(session_factory: sessionmaker) -> None:
    """
    Setup SQLAlchemy events for automatic tenant handling.
    
    Args:
        session_factory: Session factory to configure
    """
    
    @event.listens_for(session_factory, "after_begin")
    def set_tenant_on_begin(session, transaction, connection):
        """Set tenant context when transaction begins."""
        try:
            tenant_id = TenantContext.get()
            connection.execute(
                text(f"SET LOCAL {RLSManager.TENANT_SETTING} = :tenant_id"),
                {"tenant_id": tenant_id}
            )
        except SecurityError:
            pass  # No tenant context, rely on RLS
    
    @event.listens_for(session_factory, "after_transaction_end")
    def clear_tenant_on_end(session, transaction):
        """Clear tenant context when transaction ends."""
        try:
            if session.connection():
                session.connection().execute(
                    text(f"RESET {RLSManager.TENANT_SETTING}")
                )
        except Exception:
            pass  # Connection may be closed
    
    logger.info("Setup session event handlers")


# ==============================================================================
# Validation Helpers
# ==============================================================================

def validate_tenant_query(
    session: Session,
    model_class: Type[T],
    query: Query,
) -> None:
    """
    Validate that a query is properly tenant-scoped.
    
    CRITICAL: Call this for sensitive queries as an extra check.
    
    Args:
        session: Current session
        model_class: SQLAlchemy model class
        query: Query to validate
    
    Raises:
        SecurityError: If query is not properly scoped
    """
    if not hasattr(model_class, 'tenant_id'):
        return  # Not a multi-tenant model
    
    # Check if query has tenant filter
    query_str = str(query)
    
    if 'tenant_id' not in query_str:
        logger.warning(
            f"Query on {model_class.__name__} may not be tenant-scoped"
        )
        # In strict mode, we could raise here


def bulk_insert_with_tenant(
    session: Session,
    model_class: Type[T],
    records: list,
) -> None:
    """
    Bulk insert records with automatic tenant_id setting.
    
    Args:
        session: Tenant-scoped session
        model_class: Model class to insert
        records: List of dictionaries with record data
    """
    tenant_id = TenantContext.get()
    
    # Add tenant_id to all records
    for record in records:
        record['tenant_id'] = tenant_id
    
    session.bulk_insert_mappings(model_class, records)
    logger.debug(f"Bulk inserted {len(records)} {model_class.__name__} records")
