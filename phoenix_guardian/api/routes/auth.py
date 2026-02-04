"""
Authentication API endpoints.

Provides secure authentication and session management:
- POST /auth/login - User login with email/password
- POST /auth/refresh - Token refresh using refresh token
- POST /auth/logout - User logout (audit trail)
- GET /auth/me - Get current user profile
- POST /auth/change-password - Change user password
- POST /auth/register - Admin-only user registration
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from phoenix_guardian.api.auth.utils import (
    AuthenticationError,
    authenticate_user,
    create_tokens_for_user,
    decode_token,
    get_current_active_user,
    hash_password,
    refresh_access_token,
    require_admin,
    verify_password,
)
from phoenix_guardian.database.connection import get_db
from phoenix_guardian.models import AuditAction, AuditLog, User, UserRole


router = APIRouter(tags=["Authentication"])


# =============================================================================
# Request/Response Models
# =============================================================================


class LoginRequest(BaseModel):
    """Login request payload."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "dr.smith@phoenixguardian.health",
                "password": "securepassword123"
            }
        }
    )


class TokenResponse(BaseModel):
    """Token response payload returned after successful login."""
    access_token: str = Field(..., description="JWT access token (1 hour expiry)")
    refresh_token: str = Field(..., description="JWT refresh token (7 days expiry)")
    token_type: str = Field(default="bearer", description="Token type")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        }
    )


class LoginResponse(BaseModel):
    """Login response with tokens and user data."""
    access_token: str = Field(..., description="JWT access token (1 hour expiry)")
    refresh_token: str = Field(..., description="JWT refresh token (7 days expiry)")
    token_type: str = Field(default="bearer", description="Token type")
    user: Optional["UserResponse"] = Field(None, description="User profile data")

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    """User profile response."""
    id: int
    email: str
    first_name: str
    last_name: str
    role: str
    npi_number: Optional[str] = None
    license_number: Optional[str] = None
    license_state: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "email": "dr.smith@phoenixguardian.health",
                "first_name": "John",
                "last_name": "Smith",
                "role": "physician",
                "npi_number": "1234567890",
                "license_number": "MD12345",
                "license_state": "CA",
                "is_active": True,
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    )


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    current_password: str = Field(..., min_length=8, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")

    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str = Field(..., description="Valid refresh token")


class RegisterUserRequest(BaseModel):
    """Register new user request (admin only)."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="readonly")
    npi_number: Optional[str] = Field(None, max_length=10)
    license_number: Optional[str] = Field(None, max_length=50)
    license_state: Optional[str] = Field(None, max_length=2)


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
) -> LoginResponse:
    """
    Authenticate user and return JWT tokens.
    
    This endpoint validates user credentials and returns access and refresh tokens.
    Failed login attempts are logged for security auditing.
    
    **Request Body:**
    - `email`: User email address
    - `password`: User password (min 8 characters)
    
    **Returns:**
    - `access_token`: JWT access token (expires in 1 hour)
    - `refresh_token`: JWT refresh token (expires in 7 days)
    - `token_type`: "bearer"
    
    **Errors:**
    - `401 Unauthorized`: Invalid credentials
    """
    # Authenticate user
    user = authenticate_user(
        email=login_data.email,
        password=login_data.password,
        db=db,
        request=request
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    tokens = create_tokens_for_user(user)
    
    # Build user response
    user_response = UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        npi_number=user.npi_number,
        license_number=user.license_number,
        license_state=user.license_state,
        is_active=user.is_active,
        created_at=user.created_at,
    )
    
    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        user=user_response,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    Refresh access token using a valid refresh token.
    
    Use this endpoint to get a new access token when the current one expires.
    The refresh token is also rotated for security.
    
    **Request Body:**
    - `refresh_token`: Valid JWT refresh token
    
    **Returns:**
    - New `access_token` and `refresh_token`
    
    **Errors:**
    - `401 Unauthorized`: Invalid or expired refresh token
    """
    try:
        tokens = refresh_access_token(
            refresh_token=refresh_data.refresh_token,
            db=db
        )
        return TokenResponse(**tokens)
    except AuthenticationError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    Get current authenticated user's profile.
    
    Returns the profile information for the currently authenticated user.
    
    **Requires:** Valid JWT access token in Authorization header
    
    **Returns:**
    - User profile including id, email, name, role, and credentials
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        role=current_user.role.value,
        npi_number=current_user.npi_number,
        license_number=current_user.license_number,
        license_state=current_user.license_state,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Logout current user.
    
    Note: With stateless JWT tokens, server-side invalidation is not possible.
    This endpoint:
    1. Logs the logout action for audit trail (HIPAA compliance)
    2. Client should discard stored tokens
    
    **Requires:** Valid JWT access token
    
    **Returns:**
    - Success message
    """
    # Get client info for audit log
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # Log logout action for audit trail
    AuditLog.log_action(
        session=db,
        action=AuditAction.LOGOUT,
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=ip_address,
        user_agent=user_agent,
        success=True,
        description=f"User {current_user.email} logged out"
    )
    
    return MessageResponse(message="Logged out successfully")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Change the current user's password.
    
    Requires the current password for verification before setting a new one.
    Password must meet security requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    
    **Request Body:**
    - `current_password`: Current password for verification
    - `new_password`: New password (must meet security requirements)
    
    **Requires:** Valid JWT access token
    
    **Returns:**
    - Success message
    
    **Errors:**
    - `400 Bad Request`: Current password incorrect or new password invalid
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Check new password is different from current
    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    # Update password
    current_user.password_hash = hash_password(password_data.new_password)
    current_user.modified_by = current_user.id
    db.commit()
    
    # Get client info for audit log
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # Log password change for audit trail
    AuditLog.log_action(
        session=db,
        action=AuditAction.PASSWORD_CHANGED,
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=ip_address,
        user_agent=user_agent,
        success=True,
        description=f"Password changed for user {current_user.email}"
    )
    
    return MessageResponse(message="Password changed successfully")


@router.post("/register", response_model=UserResponse)
async def register_user(
    request: Request,
    user_data: RegisterUserRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    Register a new user (Admin only).
    
    This endpoint allows administrators to create new user accounts.
    New users will need to login to obtain their tokens.
    
    **Request Body:**
    - `email`: User email (must be unique)
    - `password`: Initial password (min 8 characters)
    - `first_name`: User's first name
    - `last_name`: User's last name
    - `role`: User role (admin, physician, nurse, scribe, auditor, readonly)
    - `npi_number`: National Provider Identifier (for physicians)
    - `license_number`: Medical license number
    - `license_state`: State of licensure (2-letter code)
    
    **Requires:** ADMIN role
    
    **Returns:**
    - Created user profile
    
    **Errors:**
    - `400 Bad Request`: Email already exists
    - `403 Forbidden`: Not an admin
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate role
    try:
        role = UserRole(user_data.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {[r.value for r in UserRole]}"
        )
    
    # Create new user
    new_user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        role=role,
        is_active=True,
        npi_number=user_data.npi_number,
        license_number=user_data.license_number,
        license_state=user_data.license_state,
        created_by=admin_user.id
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Get client info for audit log
    ip_address = request.client.host if request.client else None
    
    # Log user creation
    AuditLog.log_action(
        session=db,
        action=AuditAction.USER_CREATED,
        user_id=admin_user.id,
        user_email=admin_user.email,
        resource_type="user",
        resource_id=new_user.id,
        ip_address=ip_address,
        success=True,
        description=f"Admin {admin_user.email} created user {new_user.email}",
        metadata={"new_user_role": role.value}
    )
    
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        role=new_user.role.value,
        npi_number=new_user.npi_number,
        license_number=new_user.license_number,
        license_state=new_user.license_state,
        is_active=new_user.is_active,
        created_at=new_user.created_at
    )


@router.get("/validate")
async def validate_token(
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Validate current access token.
    
    Simple endpoint to check if the current token is valid.
    Useful for frontend applications to verify session status.
    
    **Requires:** Valid JWT access token
    
    **Returns:**
    - `valid`: True
    - `user_id`: Current user ID
    - `role`: Current user role
    """
    return {
        "valid": True,
        "user_id": current_user.id,
        "role": current_user.role.value
    }
