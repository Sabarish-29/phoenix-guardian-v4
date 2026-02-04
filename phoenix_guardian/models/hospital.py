"""
Hospital/Organization model for multi-tenant support.

Represents healthcare organizations using Phoenix Guardian.
"""

from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Column, Enum as SQLEnum, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .user import User


class HospitalType(str, Enum):
    """Types of healthcare organizations."""
    
    HOSPITAL = "hospital"
    CLINIC = "clinic"
    URGENT_CARE = "urgent_care"
    ACADEMIC_MEDICAL_CENTER = "academic_medical_center"
    COMMUNITY_HEALTH_CENTER = "community_health_center"
    SPECIALTY_PRACTICE = "specialty_practice"


class Hospital(BaseModel):
    """
    Hospital/Healthcare Organization model.
    
    Represents a tenant/organization in the multi-tenant system.
    
    Attributes:
        name: Organization name
        code: Unique organization code (tenant identifier)
        hospital_type: Type of healthcare organization
        address: Street address
        city: City
        state: State/Province
        zip_code: Postal code
        phone: Main phone number
        npi: Organization NPI number
        is_active: Whether organization is active
    """
    
    __tablename__ = "hospitals"
    
    name = Column(String(255), nullable=False, index=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    hospital_type = Column(SQLEnum(HospitalType), default=HospitalType.HOSPITAL)
    
    # Address
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    country = Column(String(100), default="USA")
    
    # Contact
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    
    # Identifiers
    npi = Column(String(20), nullable=True, unique=True)
    tax_id = Column(String(20), nullable=True)
    
    # Configuration
    is_active = Column(Boolean, default=True)
    settings = Column(Text, nullable=True)  # JSON config
    
    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="hospital")
    
    def __repr__(self) -> str:
        return f"<Hospital(id={self.id}, code='{self.code}', name='{self.name}')>"
