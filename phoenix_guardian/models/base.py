"""
Base model class with common fields and HIPAA compliance utilities.

Provides:
- TimestampMixin: created_at and updated_at timestamps
- SoftDeleteMixin: soft delete support (never hard delete PHI)
- AuditableMixin: who created/modified tracking
- BaseModel: combined base class for all models
"""

import re
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import Boolean, Column, DateTime, Integer
from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation timestamp (UTC)",
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Record last update timestamp (UTC)",
    )


class SoftDeleteMixin:
    """
    Mixin for soft deletes (HIPAA compliance).

    Never hard delete PHI - instead mark as deleted and
    schedule for secure deletion after retention period.
    """

    is_deleted = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Soft delete flag",
    )

    deleted_at = Column(
        DateTime,
        nullable=True,
        comment="Soft deletion timestamp",
    )

    deleted_by = Column(
        Integer,
        nullable=True,
        comment="User ID who deleted this record",
    )

    def soft_delete(self, deleted_by_user_id: int) -> None:
        """Mark record as deleted.

        Args:
            deleted_by_user_id: ID of user performing deletion
        """
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by_user_id


class AuditableMixin:
    """
    Mixin for audit trail fields.

    Tracks who created/modified records for HIPAA compliance.
    """

    created_by = Column(
        Integer,
        nullable=True,
        comment="User ID who created this record",
    )

    modified_by = Column(
        Integer,
        nullable=True,
        comment="User ID who last modified this record",
    )


class BaseModel(Base, TimestampMixin, SoftDeleteMixin, AuditableMixin):
    """
    Base model with all common fields and HIPAA compliance features.

    All models should inherit from this to ensure:
    - Automatic timestamps
    - Soft delete support
    - Audit trail tracking

    Attributes:
        id: Primary key
        created_at: Creation timestamp
        updated_at: Last update timestamp
        is_deleted: Soft delete flag
        deleted_at: Deletion timestamp
        deleted_by: User who deleted
        created_by: User who created
        modified_by: User who last modified
    """

    __abstract__ = True

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Primary key",
    )

    @declared_attr
    def __tablename__(cls) -> str:  # noqa: N805
        """Generate table name from class name.

        Converts CamelCase to snake_case.

        Returns:
            Table name in snake_case
        """
        name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", cls.__name__)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()

    def to_dict(self, exclude_deleted: bool = True) -> Dict[str, Any]:
        """
        Convert model to dictionary.

        Args:
            exclude_deleted: Skip if soft deleted

        Returns:
            Dictionary representation of the model
        """
        if exclude_deleted and self.is_deleted:
            return {}

        result: Dict[str, Any] = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value

        return result

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<{self.__class__.__name__}(id={self.id})>"
