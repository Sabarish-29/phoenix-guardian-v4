"""
Phoenix Guardian - Multi-Tenant Database Models
SQLAlchemy models with built-in tenant isolation.

All models in this module include tenant_id and automatically
integrate with RLS policies for database-level isolation.
"""

import logging
from typing import Any, Dict, List, Optional, Type, TypeVar
from datetime import datetime, timezone
from dataclasses import dataclass

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    Index,
    UniqueConstraint,
    CheckConstraint,
    event,
    inspect,
)
from sqlalchemy.ext.declarative import declared_attr, declarative_base
from sqlalchemy.orm import relationship, validates

from phoenix_guardian.core.tenant_context import TenantContext, SecurityError

logger = logging.getLogger(__name__)

Base = declarative_base()
T = TypeVar('T', bound='TenantMixin')


# ==============================================================================
# Tenant Mixin
# ==============================================================================

class TenantMixin:
    """
    Mixin that adds tenant isolation to SQLAlchemy models.
    
    All multi-tenant models should inherit from this mixin.
    It provides:
    - tenant_id column with proper indexing
    - Automatic tenant_id validation
    - Cross-tenant access prevention
    
    Example:
        class Prediction(Base, TenantMixin):
            __tablename__ = 'predictions'
            
            id = Column(Integer, primary_key=True)
            patient_id = Column(String(50), nullable=False)
            risk_score = Column(Float, nullable=False)
    """
    
    @declared_attr
    def tenant_id(cls) -> Column:
        """Tenant ID column - REQUIRED for all multi-tenant tables."""
        return Column(
            String(64),
            nullable=False,
            index=True,
            comment="Tenant identifier for RLS isolation"
        )
    
    @declared_attr
    def __table_args__(cls):
        """Add tenant-scoped indexes."""
        args = getattr(super(), '__table_args__', ())
        
        if isinstance(args, dict):
            args = (args,)
        elif not isinstance(args, tuple):
            args = ()
        
        # Add tenant_id index
        new_args = args + (
            Index(f'ix_{cls.__tablename__}_tenant', 'tenant_id'),
        )
        
        return new_args
    
    @validates('tenant_id')
    def validate_tenant_id(self, key: str, tenant_id: str) -> str:
        """
        Validate tenant_id on assignment.
        
        CRITICAL: Prevents cross-tenant data creation.
        """
        if tenant_id is None:
            raise ValueError("tenant_id cannot be None")
        
        # During normal operations, validate against context
        try:
            context_tenant = TenantContext.get()
            
            if tenant_id != context_tenant:
                raise SecurityError(
                    f"Cannot set tenant_id to '{tenant_id}' when context "
                    f"is '{context_tenant}'"
                )
        except SecurityError as e:
            # If "No tenant context", we're in admin mode - allow
            if "No tenant context" not in str(e):
                raise
        
        return tenant_id
    
    @classmethod
    def get_for_tenant(
        cls: Type[T],
        session,
        tenant_id: Optional[str] = None,
        **filters,
    ) -> List[T]:
        """
        Get all instances for a tenant.
        
        Args:
            session: Database session
            tenant_id: Tenant ID (uses context if not provided)
            **filters: Additional filter criteria
        
        Returns:
            List of matching instances
        """
        if tenant_id is None:
            tenant_id = TenantContext.get()
        
        query = session.query(cls).filter(cls.tenant_id == tenant_id)
        
        for key, value in filters.items():
            if hasattr(cls, key):
                query = query.filter(getattr(cls, key) == value)
        
        return query.all()
    
    @classmethod
    def count_for_tenant(
        cls: Type[T],
        session,
        tenant_id: Optional[str] = None,
    ) -> int:
        """Count instances for a tenant."""
        if tenant_id is None:
            tenant_id = TenantContext.get()
        
        return session.query(cls).filter(cls.tenant_id == tenant_id).count()


# ==============================================================================
# Audit Mixin
# ==============================================================================

class AuditMixin:
    """
    Mixin for audit tracking (created_at, updated_at, etc.).
    """
    
    @declared_attr
    def created_at(cls) -> Column:
        return Column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            nullable=False,
        )
    
    @declared_attr
    def updated_at(cls) -> Column:
        return Column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        )
    
    @declared_attr
    def created_by(cls) -> Column:
        return Column(String(64), nullable=True)
    
    @declared_attr
    def updated_by(cls) -> Column:
        return Column(String(64), nullable=True)


# ==============================================================================
# Core Multi-Tenant Models
# ==============================================================================

class Tenant(Base):
    """
    Tenant master table.
    
    Stores information about each tenant (hospital).
    This table is NOT tenant-scoped (it's the source of truth for tenants).
    """
    __tablename__ = 'tenants'
    
    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    
    # Status
    status = Column(String(20), nullable=False, default='pending')
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Configuration
    config = Column(JSON, default=dict, nullable=False)
    settings = Column(JSON, default=dict, nullable=False)
    
    # Limits
    max_users = Column(Integer, default=100)
    max_predictions_per_day = Column(Integer, default=10000)
    max_storage_gb = Column(Float, default=100.0)
    
    # Dates
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))
    activated_at = Column(DateTime(timezone=True), nullable=True)
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    predictions = relationship("Prediction", back_populates="tenant", lazy="dynamic")
    alerts = relationship("Alert", back_populates="tenant", lazy="dynamic")
    
    def __repr__(self):
        return f"<Tenant(id='{self.id}', name='{self.name}', status='{self.status}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "status": self.status,
            "is_active": self.is_active,
            "max_users": self.max_users,
            "max_predictions_per_day": self.max_predictions_per_day,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Prediction(Base, TenantMixin, AuditMixin):
    """
    Sepsis risk predictions.
    
    Multi-tenant table with RLS protection.
    """
    __tablename__ = 'predictions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id = Column(String(36), unique=True, nullable=False)
    
    # Patient info
    patient_id = Column(String(50), nullable=False, index=True)
    encounter_id = Column(String(50), nullable=True)
    
    # Prediction results
    risk_score = Column(Float, nullable=False)
    risk_category = Column(String(20), nullable=False)  # low, moderate, high, critical
    confidence = Column(Float, nullable=True)
    
    # Model info
    model_version = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=True)
    
    # Features used
    feature_snapshot = Column(JSON, default=dict)
    explanation = Column(JSON, default=dict)
    
    # Timestamps
    prediction_timestamp = Column(DateTime(timezone=True), nullable=False)
    
    # Foreign keys
    tenant_fk = Column(String(64), ForeignKey('tenants.id'), nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="predictions")
    
    # Indexes
    __table_args__ = (
        Index('ix_predictions_tenant_patient', 'tenant_id', 'patient_id'),
        Index('ix_predictions_tenant_timestamp', 'tenant_id', 'prediction_timestamp'),
        Index('ix_predictions_tenant_risk', 'tenant_id', 'risk_category'),
    )
    
    def __repr__(self):
        return (
            f"<Prediction(id={self.id}, patient='{self.patient_id}', "
            f"risk={self.risk_score:.2f})>"
        )


class Alert(Base, TenantMixin, AuditMixin):
    """
    Clinical alerts generated from predictions.
    
    Multi-tenant with RLS protection.
    """
    __tablename__ = 'alerts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String(36), unique=True, nullable=False)
    
    # Source
    prediction_id = Column(String(36), ForeignKey('predictions.prediction_id'))
    patient_id = Column(String(50), nullable=False, index=True)
    
    # Alert details
    severity = Column(String(20), nullable=False)  # info, warning, critical
    alert_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    
    # Status
    status = Column(String(20), default='active')  # active, acknowledged, resolved
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(64), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(64), nullable=True)
    
    # Metadata
    metadata = Column(JSON, default=dict)
    
    # Foreign keys
    tenant_fk = Column(String(64), ForeignKey('tenants.id'), nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="alerts")
    
    # Indexes
    __table_args__ = (
        Index('ix_alerts_tenant_patient', 'tenant_id', 'patient_id'),
        Index('ix_alerts_tenant_status', 'tenant_id', 'status'),
        Index('ix_alerts_tenant_severity', 'tenant_id', 'severity'),
    )


class PatientData(Base, TenantMixin, AuditMixin):
    """
    Patient clinical data cache.
    
    Stores the latest patient features for quick prediction.
    Multi-tenant with RLS protection.
    """
    __tablename__ = 'patient_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Patient identification
    patient_id = Column(String(50), nullable=False)
    encounter_id = Column(String(50), nullable=True)
    
    # Demographics
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)
    
    # Latest vitals
    vitals = Column(JSON, default=dict)
    
    # Latest labs
    labs = Column(JSON, default=dict)
    
    # Medications
    medications = Column(JSON, default=list)
    
    # Risk factors
    risk_factors = Column(JSON, default=dict)
    
    # Last update
    data_timestamp = Column(DateTime(timezone=True), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('ix_patient_data_tenant_patient', 'tenant_id', 'patient_id'),
        UniqueConstraint('tenant_id', 'patient_id', name='uq_patient_data_tenant_patient'),
    )


class ModelVersion(Base, TenantMixin, AuditMixin):
    """
    ML model versions deployed per tenant.
    
    Tracks which model versions are active for each tenant.
    """
    __tablename__ = 'model_versions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Model identification
    model_name = Column(String(100), nullable=False)
    version = Column(String(50), nullable=False)
    
    # Status
    is_active = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    
    # Metadata
    description = Column(Text, nullable=True)
    metrics = Column(JSON, default=dict)  # Training metrics
    config = Column(JSON, default=dict)  # Model configuration
    
    # Deployment
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    deployed_by = Column(String(64), nullable=True)
    
    # Artifact location
    artifact_path = Column(String(500), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('ix_model_versions_tenant_model', 'tenant_id', 'model_name'),
        UniqueConstraint('tenant_id', 'model_name', 'version', name='uq_model_version'),
    )


class AuditLog(Base, TenantMixin):
    """
    Audit log for all tenant operations.
    
    Records all significant actions for compliance and debugging.
    """
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Event identification
    event_id = Column(String(36), unique=True, nullable=False)
    event_type = Column(String(50), nullable=False)
    
    # Actor
    user_id = Column(String(64), nullable=True)
    user_role = Column(String(50), nullable=True)
    
    # Resource
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    
    # Action details
    action = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)  # success, failure
    
    # Details
    request_data = Column(JSON, default=dict)
    response_data = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)
    
    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Indexes
    __table_args__ = (
        Index('ix_audit_logs_tenant_timestamp', 'tenant_id', 'timestamp'),
        Index('ix_audit_logs_tenant_user', 'tenant_id', 'user_id'),
        Index('ix_audit_logs_tenant_event', 'tenant_id', 'event_type'),
    )


class UserFeedback(Base, TenantMixin, AuditMixin):
    """
    User feedback on predictions.
    
    Captures clinician feedback for model improvement.
    """
    __tablename__ = 'user_feedback'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    feedback_id = Column(String(36), unique=True, nullable=False)
    
    # Source
    prediction_id = Column(String(36), ForeignKey('predictions.prediction_id'))
    alert_id = Column(String(36), ForeignKey('alerts.alert_id'), nullable=True)
    
    # Feedback
    feedback_type = Column(String(50), nullable=False)  # accuracy, usefulness, etc.
    rating = Column(Integer, nullable=True)  # 1-5
    was_helpful = Column(Boolean, nullable=True)
    was_accurate = Column(Boolean, nullable=True)
    
    # Details
    comment = Column(Text, nullable=True)
    suggested_outcome = Column(String(50), nullable=True)
    
    # Submitter
    submitted_by = Column(String(64), nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Indexes
    __table_args__ = (
        Index('ix_feedback_tenant_prediction', 'tenant_id', 'prediction_id'),
        Index('ix_feedback_tenant_type', 'tenant_id', 'feedback_type'),
    )


class PerformanceMetric(Base, TenantMixin):
    """
    System performance metrics per tenant.
    
    Tracks prediction latency, throughput, etc.
    """
    __tablename__ = 'performance_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Metric identification
    metric_name = Column(String(100), nullable=False)
    metric_type = Column(String(50), nullable=False)  # gauge, counter, histogram
    
    # Values
    value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=True)
    
    # Dimensions
    dimensions = Column(JSON, default=dict)
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('ix_metrics_tenant_name_time', 'tenant_id', 'metric_name', 'timestamp'),
    )


class HospitalConfig(Base, TenantMixin, AuditMixin):
    """
    Hospital-specific configuration.
    
    Stores thresholds, display settings, integration config, etc.
    """
    __tablename__ = 'hospital_config'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Config identification
    config_key = Column(String(100), nullable=False)
    config_category = Column(String(50), nullable=False)
    
    # Value
    config_value = Column(JSON, nullable=False)
    
    # Metadata
    description = Column(Text, nullable=True)
    is_secret = Column(Boolean, default=False)
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('tenant_id', 'config_key', name='uq_hospital_config'),
        Index('ix_hospital_config_tenant_category', 'tenant_id', 'config_category'),
    )


# ==============================================================================
# Model Events
# ==============================================================================

@event.listens_for(TenantMixin, 'before_insert', propagate=True)
def set_tenant_before_insert(mapper, connection, target):
    """
    Automatically set tenant_id before insert if not set.
    """
    if hasattr(target, 'tenant_id') and target.tenant_id is None:
        try:
            target.tenant_id = TenantContext.get()
        except SecurityError:
            pass  # Let it fail at DB level if no tenant


@event.listens_for(TenantMixin, 'before_update', propagate=True)
def validate_tenant_before_update(mapper, connection, target):
    """
    Prevent tenant_id changes during update.
    """
    if hasattr(target, 'tenant_id'):
        state = inspect(target)
        history = state.attrs.tenant_id.history
        
        if history.has_changes() and history.deleted:
            old_tenant = history.deleted[0]
            new_tenant = target.tenant_id
            
            if old_tenant != new_tenant:
                raise SecurityError(
                    f"Cannot change tenant_id from '{old_tenant}' to '{new_tenant}'"
                )


# ==============================================================================
# Helper Functions
# ==============================================================================

def get_all_tenant_models() -> List[Type]:
    """Get all model classes that use TenantMixin."""
    return [
        cls for cls in Base.__subclasses__()
        if issubclass(cls, TenantMixin) and cls is not TenantMixin
    ]


def get_multi_tenant_table_names() -> List[str]:
    """Get table names that require RLS."""
    return [
        cls.__tablename__
        for cls in get_all_tenant_models()
    ]


def create_all_tables(engine) -> None:
    """Create all tables in the database."""
    Base.metadata.create_all(engine)
    logger.info("Created all database tables")


def drop_all_tables(engine) -> None:
    """Drop all tables from the database."""
    Base.metadata.drop_all(engine)
    logger.warning("Dropped all database tables")
