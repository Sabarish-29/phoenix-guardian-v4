"""
User model for authentication and authorization.

Provides role-based access control (RBAC) for HIPAA compliance.
"""

from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Column, Enum as SQLEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, Relationship, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .audit_log import AuditLog
    from .encounter import Encounter
    from .hospital import Hospital


class UserRole(str, Enum):
    """User roles for RBAC (Role-Based Access Control).

    Role hierarchy (highest to lowest):
    - ADMIN: Full system access
    - PHYSICIAN: Can create/edit/sign notes
    - NURSE: Can view and assist with encounters
    - SCRIBE: Can create/edit notes (not sign)
    - AUDITOR: Read-only access to audit logs
    - READONLY: View-only access
    """

    ADMIN = "admin"
    PHYSICIAN = "physician"
    NURSE = "nurse"
    SCRIBE = "scribe"
    AUDITOR = "auditor"
    READONLY = "readonly"


# Role hierarchy for permission checking
ROLE_HIERARCHY = {
    UserRole.ADMIN: 6,
    UserRole.PHYSICIAN: 5,
    UserRole.NURSE: 4,
    UserRole.SCRIBE: 3,
    UserRole.AUDITOR: 2,
    UserRole.READONLY: 1,
}


class User(BaseModel):
    """
    User account model.

    Stores authentication and authorization data.
    Passwords are hashed using bcrypt.

    Attributes:
        email: User email address (login)
        password_hash: Bcrypt password hash
        first_name: User first name
        last_name: User last name
        role: User role for RBAC
        is_active: Account active status
        npi_number: National Provider Identifier (physicians)
        license_number: Medical license number
        license_state: State of medical licensure
    """

    __tablename__ = "users"

    # Authentication
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User email address (login)",
    )

    password_hash = Column(
        String(255),
        nullable=False,
        comment="Bcrypt password hash",
    )

    # Profile
    first_name = Column(
        String(100),
        nullable=False,
        comment="User first name",
    )

    last_name = Column(
        String(100),
        nullable=False,
        comment="User last name",
    )

    # Authorization
    role = Column(
        SQLEnum(UserRole),
        nullable=False,
        default=UserRole.READONLY,
        comment="User role for RBAC",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Account active status",
    )

    # Medical credentials (for physicians)
    npi_number = Column(
        String(10),
        nullable=True,
        unique=True,
        comment="National Provider Identifier (physicians only)",
    )

    license_number = Column(
        String(50),
        nullable=True,
        comment="Medical license number",
    )

    license_state = Column(
        String(2),
        nullable=True,
        comment="State of medical licensure",
    )

    # Hospital/Tenant association
    hospital_id = Column(
        Integer,
        ForeignKey("hospitals.id"),
        nullable=True,
        comment="Associated hospital/organization",
    )

    # Relationships
    hospital: Mapped[Optional["Hospital"]] = relationship(
        "Hospital",
        back_populates="users",
    )

    encounters: Mapped[List["Encounter"]] = relationship(
        "Encounter",
        back_populates="provider",
        foreign_keys="Encounter.provider_id",
    )

    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        foreign_keys="AuditLog.user_id",
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<User(id={self.id}, email='{self.email}', "
            f"role='{self.role.value}')>"
        )

    @property
    def full_name(self) -> str:
        """Get user's full name.

        Returns:
            Full name as 'First Last'
        """
        return f"{self.first_name} {self.last_name}"

    def has_permission(self, required_role: UserRole) -> bool:
        """
        Check if user has required permission level.

        Role hierarchy: ADMIN > PHYSICIAN > NURSE > SCRIBE > AUDITOR > READONLY

        Args:
            required_role: Minimum required role

        Returns:
            True if user has sufficient permissions
        """
        return ROLE_HIERARCHY[self.role] >= ROLE_HIERARCHY[required_role]

    def can_sign_notes(self) -> bool:
        """Check if user can sign SOAP notes.

        Returns:
            True if user is a physician or admin
        """
        return self.role in [UserRole.ADMIN, UserRole.PHYSICIAN]

    def can_edit_notes(self) -> bool:
        """Check if user can edit SOAP notes.

        Returns:
            True if user can edit notes
        """
        return self.role in [
            UserRole.ADMIN,
            UserRole.PHYSICIAN,
            UserRole.NURSE,
            UserRole.SCRIBE,
        ]
