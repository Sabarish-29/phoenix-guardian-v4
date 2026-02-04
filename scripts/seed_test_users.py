"""
Seed test users for E2E testing.

This script creates test users with known credentials for E2E tests.
Run this before running E2E tests.

Usage:
    python scripts/seed_test_users.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from phoenix_guardian.core.database import SessionLocal, engine, Base
from phoenix_guardian.models.user import User, UserRole
from phoenix_guardian.auth.utils import get_password_hash


# Test users for E2E tests
TEST_USERS = [
    {
        "email": "admin@phoenix.local",
        "password": "Admin123!",
        "first_name": "System",
        "last_name": "Admin",
        "role": UserRole.ADMIN,
        "is_active": True,
    },
    {
        "email": "dr.smith@phoenix.local",
        "password": "Doctor123!",
        "first_name": "John",
        "last_name": "Smith",
        "role": UserRole.PHYSICIAN,
        "npi_number": "1234567890",
        "license_number": "MD12345",
        "license_state": "CA",
        "is_active": True,
    },
    {
        "email": "nurse.jones@phoenix.local",
        "password": "Nurse123!",
        "first_name": "Sarah",
        "last_name": "Jones",
        "role": UserRole.NURSE,
        "is_active": True,
    },
    {
        "email": "scribe@phoenix.local",
        "password": "Scribe123!",
        "first_name": "Mike",
        "last_name": "Scribe",
        "role": UserRole.SCRIBE,
        "is_active": True,
    },
    {
        "email": "auditor@phoenix.local",
        "password": "Auditor123!",
        "first_name": "Jane",
        "last_name": "Auditor",
        "role": UserRole.AUDITOR,
        "is_active": True,
    },
    {
        "email": "readonly@phoenix.local",
        "password": "Readonly123!",
        "first_name": "View",
        "last_name": "Only",
        "role": UserRole.READONLY,
        "is_active": True,
    },
]


def seed_test_users():
    """Create test users in the database."""
    print("🌱 Seeding test users for E2E tests...")
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        created_count = 0
        updated_count = 0
        
        for user_data in TEST_USERS:
            password = user_data.pop("password")
            email = user_data["email"]
            
            # Check if user exists
            existing_user = db.query(User).filter(User.email == email).first()
            
            if existing_user:
                # Update existing user
                for key, value in user_data.items():
                    setattr(existing_user, key, value)
                existing_user.hashed_password = get_password_hash(password)
                updated_count += 1
                print(f"  ✓ Updated user: {email}")
            else:
                # Create new user
                user = User(
                    **user_data,
                    hashed_password=get_password_hash(password)
                )
                db.add(user)
                created_count += 1
                print(f"  ✓ Created user: {email}")
        
        db.commit()
        
        print(f"\n✅ Seeding complete!")
        print(f"   Created: {created_count} users")
        print(f"   Updated: {updated_count} users")
        print(f"   Total:   {len(TEST_USERS)} test users")
        
        # Print credentials for reference
        print("\n📋 Test User Credentials:")
        print("-" * 50)
        for user_data in TEST_USERS:
            # Restore password for display
            user_data["password"] = next(
                u["password"] for u in [
                    {"email": "admin@phoenix.local", "password": "Admin123!"},
                    {"email": "dr.smith@phoenix.local", "password": "Doctor123!"},
                    {"email": "nurse.jones@phoenix.local", "password": "Nurse123!"},
                    {"email": "scribe@phoenix.local", "password": "Scribe123!"},
                    {"email": "auditor@phoenix.local", "password": "Auditor123!"},
                    {"email": "readonly@phoenix.local", "password": "Readonly123!"},
                ] if u["email"] == user_data.get("email", "")
            )
            print(f"   {user_data.get('role', 'unknown'):12} | {user_data.get('email', 'N/A')}")
        print("-" * 50)
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error seeding users: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_test_users()
