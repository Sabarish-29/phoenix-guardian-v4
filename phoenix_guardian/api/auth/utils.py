"""
Authentication and authorization utilities.

Implements:
- Password hashing with bcrypt
- JWT token generation and validation
- Role-based permission checking
- FastAPI dependencies for protected routes
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from phoenix_guardian.database.connection import get_db
from phoenix_guardian.models import AuditAction, AuditLog, User, UserRole


# =============================================================================
# Configuration
# =============================================================================

SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    "CHANGE-THIS-IN-PRODUCTION-USE-STRONG-RANDOM-KEY-256-BITS"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 days

# DEV MODE - allows login without database (set PHOENIX_DEV_MODE=true)
DEV_MODE = os.getenv("PHOENIX_DEV_MODE", "false").lower() == "true"

# Dev mode users (only used when PHOENIX_DEV_MODE=true)
DEV_USERS = {
    "admin@phoenix.local": {
        "id": 1,
        "password": "Admin123!",
        "first_name": "System",
        "last_name": "Admin",
        "role": "admin",
        "is_active": True,
    },
    "dr.smith@phoenix.local": {
        "id": 2,
        "password": "Doctor123!",
        "first_name": "John",
        "last_name": "Smith",
        "role": "physician",
        "npi_number": "1234567890",
        "license_number": "MD12345",
        "license_state": "CA",
        "is_active": True,
    },
    "nurse.jones@phoenix.local": {
        "id": 3,
        "password": "Nurse123!",
        "first_name": "Sarah",
        "last_name": "Jones",
        "role": "nurse",
        "is_active": True,
    },
}

# Password hashing context (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


# =============================================================================
# Custom Exceptions
# =============================================================================


class AuthenticationError(HTTPException):
    """Raised when authentication fails.
    
    Returns 401 Unauthorized with WWW-Authenticate header.
    """

    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(HTTPException):
    """Raised when user lacks required permissions.
    
    Returns 403 Forbidden.
    """

    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


# =============================================================================
# Password Utilities
# =============================================================================


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
    
    Returns:
        Bcrypt hashed password
    
    Example:
        hashed = hash_password("mysecretpassword")
        # Returns: "$2b$12$..."
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its bcrypt hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hash to compare against
    
    Returns:
        True if password matches, False otherwise
    
    Example:
        is_valid = verify_password("mysecretpassword", stored_hash)
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


# =============================================================================
# JWT Token Utilities
# =============================================================================


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Payload to encode in token (usually user info)
        expires_delta: Custom expiration time (default: 1 hour)
    
    Returns:
        Encoded JWT token string
    
    Token payload includes:
        - sub: User ID
        - email: User email
        - role: User role
        - exp: Expiration timestamp
        - iat: Issued at timestamp
        - jti: Unique token ID
        - type: "access"
    
    Example:
        token = create_access_token({"sub": 123, "email": "user@example.com"})
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),  # Unique token ID for tracking
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.
    
    Refresh tokens have longer expiration (7 days by default)
    and are used to obtain new access tokens.
    
    Args:
        data: Payload to encode (minimal - just user ID)
        expires_delta: Custom expiration time (default: 7 days)
    
    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload as dictionary
    
    Raises:
        AuthenticationError: If token is invalid, expired, or malformed
    
    Example:
        payload = decode_token(token)
        user_id = payload["sub"]
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError(detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(detail=f"Invalid token: {str(e)}")


# =============================================================================
# FastAPI Dependencies
# =============================================================================


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.
    
    This is a FastAPI dependency that:
    1. Extracts JWT token from Authorization header
    2. Validates and decodes token
    3. Retrieves user from database
    4. Verifies user is active
    
    Args:
        credentials: HTTP Bearer token from request header
        db: Database session
    
    Returns:
        Authenticated User object
    
    Raises:
        AuthenticationError: If token invalid, missing, or user not found
    
    Usage:
        @app.get("/protected")
        def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.id}
    """
    if credentials is None:
        raise AuthenticationError(detail="Missing authentication token")
    
    token = credentials.credentials
    
    # Decode and validate token
    payload = decode_token(token)
    
    # Extract user ID (sub is stored as string per JWT standard)
    sub = payload.get("sub")
    if sub is None:
        raise AuthenticationError(detail="Token missing user ID")
    
    try:
        user_id = int(sub)
    except (ValueError, TypeError):
        raise AuthenticationError(detail="Invalid user ID in token")
    
    # Verify token type is access (not refresh)
    token_type = payload.get("type")
    if token_type != "access":
        raise AuthenticationError(detail="Invalid token type - use access token")
    
    # Retrieve user from database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise AuthenticationError(detail="User not found")
    
    # Check if user is active
    if not user.is_active:
        raise AuthenticationError(detail="User account is disabled")
    
    # Check if user is deleted
    if user.is_deleted:
        raise AuthenticationError(detail="User account has been deleted")
    
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Verify user is active (additional security layer).
    
    This is a wrapper around get_current_user that provides
    an explicit check for active status.
    
    Args:
        current_user: User from get_current_user dependency
    
    Returns:
        Active user
    
    Raises:
        AuthenticationError: If user is inactive
    """
    if not current_user.is_active:
        raise AuthenticationError(detail="Inactive user account")
    return current_user


class RoleChecker:
    """
    Dependency class for role-based access control.
    
    Creates a callable dependency that checks if the current
    user has the required role (or higher in the hierarchy).
    
    Usage:
        @app.get("/admin-only")
        def admin_route(user: User = Depends(RoleChecker(UserRole.ADMIN))):
            return {"message": "Admin access granted"}
        
        @app.get("/physician-or-higher")
        def physician_route(user: User = Depends(RoleChecker(UserRole.PHYSICIAN))):
            return {"message": "Physician access granted"}
    """

    def __init__(self, required_role: UserRole):
        """
        Initialize role checker with required role.
        
        Args:
            required_role: Minimum role required for access
        """
        self.required_role = required_role

    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        """
        Check if user has required role.
        
        Args:
            current_user: Authenticated active user
        
        Returns:
            User if authorized
        
        Raises:
            AuthorizationError: If user lacks required permission
        """
        if not current_user.has_permission(self.required_role):
            raise AuthorizationError(
                detail=f"Access denied. Requires {self.required_role.value} role or higher"
            )
        return current_user


def require_physician(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Dependency that requires PHYSICIAN role or higher.
    
    Physicians can:
    - Create encounters
    - Generate SOAP notes
    - Sign SOAP notes
    - View all patient data
    
    Usage:
        @app.post("/encounters")
        def create_encounter(user: User = Depends(require_physician)):
            ...
    """
    if not current_user.has_permission(UserRole.PHYSICIAN):
        raise AuthorizationError(
            detail="Physician access required for this operation"
        )
    return current_user


def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Dependency that requires ADMIN role (exactly, not hierarchy).
    
    Admins can:
    - Manage users
    - View audit logs
    - Configure system settings
    
    Usage:
        @app.delete("/users/{user_id}")
        def delete_user(user: User = Depends(require_admin)):
            ...
    """
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError(
            detail="Administrator access required for this operation"
        )
    return current_user


def require_can_sign(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Dependency that requires ability to sign SOAP notes.
    
    Only physicians and admins can sign notes (legally binding).
    """
    if not current_user.can_sign_notes():
        raise AuthorizationError(
            detail="Only physicians can sign SOAP notes"
        )
    return current_user


def require_can_edit(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Dependency that requires ability to edit SOAP notes.
    
    Physicians, nurses, and scribes can edit notes before signing.
    """
    if not current_user.can_edit_notes():
        raise AuthorizationError(
            detail="You do not have permission to edit SOAP notes"
        )
    return current_user


# =============================================================================
# Authentication Functions
# =============================================================================


def authenticate_user(
    email: str,
    password: str,
    db: Session,
    request: Optional[Request] = None
) -> Optional[User]:
    """
    Authenticate user with email and password.
    
    This function:
    1. Looks up user by email
    2. Verifies password
    3. Checks if user is active
    4. Logs the attempt (success or failure) for audit trail
    
    Args:
        email: User email address
        password: Plain text password
        db: Database session
        request: Optional FastAPI request (for IP logging)
    
    Returns:
        User if authenticated successfully, None otherwise
    
    Side Effects:
        Creates audit log entries for login attempts
    
    Example:
        user = authenticate_user("dr.smith@hospital.com", "password123", db)
        if user:
            tokens = create_tokens_for_user(user)
    """
    # Get client IP if request available
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
    
    # Look up user by email
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # Log failed login - user not found
        AuditLog.log_action(
            session=db,
            action=AuditAction.LOGIN_FAILED,
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            error_message="User not found",
            description=f"Failed login attempt for email: {email}"
        )
        return None
    
    # Verify password
    if not verify_password(password, user.password_hash):
        # Log failed login - invalid password
        AuditLog.log_action(
            session=db,
            action=AuditAction.LOGIN_FAILED,
            user_id=user.id,
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            error_message="Invalid password",
            description=f"Failed login attempt - invalid password"
        )
        return None
    
    # Check if user is active
    if not user.is_active:
        # Log failed login - inactive account
        AuditLog.log_action(
            session=db,
            action=AuditAction.LOGIN_FAILED,
            user_id=user.id,
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            error_message="Account disabled",
            description=f"Failed login attempt - account disabled"
        )
        return None
    
    # Check if user is deleted
    if user.is_deleted:
        AuditLog.log_action(
            session=db,
            action=AuditAction.LOGIN_FAILED,
            user_id=user.id,
            user_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            error_message="Account deleted",
            description=f"Failed login attempt - account deleted"
        )
        return None
    
    # Success! Log successful login
    AuditLog.log_action(
        session=db,
        action=AuditAction.LOGIN,
        user_id=user.id,
        user_email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        success=True,
        description=f"User {email} logged in successfully"
    )
    
    return user


def create_tokens_for_user(user: User) -> Dict[str, str]:
    """
    Create access and refresh tokens for an authenticated user.
    
    Args:
        user: Authenticated User object
    
    Returns:
        Dictionary containing:
        - access_token: JWT access token (1 hour expiry)
        - refresh_token: JWT refresh token (7 days expiry)
        - token_type: "bearer"
    
    Example:
        tokens = create_tokens_for_user(user)
        return TokenResponse(**tokens)
    """
    # Build token payload
    token_data = {
        "sub": str(user.id),  # JWT standard expects sub to be a string
        "email": user.email,
        "role": user.role.value,
    }
    
    # Add NPI number for physicians (useful for EHR integration)
    if user.npi_number:
        token_data["npi"] = user.npi_number
    
    # Create tokens
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


def refresh_access_token(
    refresh_token: str,
    db: Session
) -> Dict[str, str]:
    """
    Create new tokens using a valid refresh token.
    
    Args:
        refresh_token: Valid JWT refresh token
        db: Database session
    
    Returns:
        New token pair (access + refresh)
    
    Raises:
        AuthenticationError: If refresh token invalid or user not found
    """
    # Decode refresh token
    payload = decode_token(refresh_token)
    
    # Verify token type
    if payload.get("type") != "refresh":
        raise AuthenticationError(detail="Invalid token type - expected refresh token")
    
    # Get user (sub is stored as string per JWT standard)
    sub = payload.get("sub")
    try:
        user_id = int(sub) if sub else None
    except (ValueError, TypeError):
        raise AuthenticationError(detail="Invalid user ID in token")
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise AuthenticationError(detail="User not found")
    
    if not user.is_active:
        raise AuthenticationError(detail="User account is disabled")
    
    if user.is_deleted:
        raise AuthenticationError(detail="User account has been deleted")
    
    # Create new tokens
    return create_tokens_for_user(user)
