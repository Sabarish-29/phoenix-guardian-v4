"""Security utilities for authentication and authorization.

Implements:
- JWT token generation and validation
- Password hashing (bcrypt)
- Role-based access control
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

# JWT Configuration
SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY", "your-secret-key-change-in-production"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored password hash

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token.

    Args:
        data: Token payload data (user_id, username, role, etc.)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return payload

    except JWTError as exc:
        raise credentials_exception from exc


# Mock user database (replace with real database in production)
# Passwords are pre-hashed for the mock users
_MOCK_USERS_DB: Optional[Dict[str, Dict[str, Any]]] = None


def _get_mock_users_db() -> Dict[str, Dict[str, Any]]:
    """Get or initialize mock users database.

    Returns:
        Dictionary of mock users
    """
    global _MOCK_USERS_DB  # pylint: disable=global-statement

    if _MOCK_USERS_DB is None:
        _MOCK_USERS_DB = {
            "dr_smith": {
                "user_id": "user_001",
                "username": "dr_smith",
                "hashed_password": hash_password("SecurePassword123!"),
                "role": "physician",
                "full_name": "Dr. John Smith",
            },
            "admin": {
                "user_id": "user_002",
                "username": "admin",
                "hashed_password": hash_password("AdminPass456!"),
                "role": "admin",
                "full_name": "System Administrator",
            },
            "nurse_jones": {
                "user_id": "user_003",
                "username": "nurse_jones",
                "hashed_password": hash_password("NursePass789!"),
                "role": "nurse",
                "full_name": "Nurse Sarah Jones",
            },
        }

    return _MOCK_USERS_DB


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user by username and password.

    Args:
        username: Username
        password: Plain text password

    Returns:
        User dictionary if authenticated, None otherwise
    """
    users_db = _get_mock_users_db()
    user = users_db.get(username)

    if not user:
        return None

    if not verify_password(password, user["hashed_password"]):
        return None

    return user


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID.

    Args:
        user_id: User ID

    Returns:
        User dictionary if found, None otherwise
    """
    users_db = _get_mock_users_db()

    for user in users_db.values():
        if user["user_id"] == user_id:
            return user

    return None
