#!/usr/bin/env python3
"""
Database migration script - creates schema and seeds initial data.

Usage:
    python scripts/migrate.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("Phoenix Guardian — Database Migration")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

# Get database connection info
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "phoenix_guardian")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

if not DB_PASSWORD:
    print("❌ DB_PASSWORD not set in .env file")
    sys.exit(1)

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"   Connecting to: {DB_HOST}:{DB_PORT}/{DB_NAME}")

try:
    from sqlalchemy import create_engine, text
    
    # First, try to create the database if it doesn't exist
    try:
        admin_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'"))
            if not result.fetchone():
                conn.execute(text(f"CREATE DATABASE {DB_NAME}"))
                print(f"   ✓ Created database: {DB_NAME}")
            else:
                print(f"   ✓ Database exists: {DB_NAME}")
        admin_engine.dispose()
    except Exception as e:
        print(f"   ⚠️  Could not check/create database: {e}")
    
    # Now connect to the actual database and create tables
    engine = create_engine(DATABASE_URL)
    
    # Import models and create tables
    from phoenix_guardian.models import Base
    from phoenix_guardian.database.connection import db
    
    # Connect and create all tables
    db.connect(DATABASE_URL)
    db.create_tables()
    print("   ✓ All tables created")
    
    # Add missing columns if they don't exist (for existing databases)
    with engine.connect() as conn:
        # Create hospitals table if not exists (check first)
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'hospitals'
            )
        """))
        if not result.fetchone()[0]:
            from phoenix_guardian.models import Hospital
            Hospital.__table__.create(engine, checkfirst=True)
            print("   ✓ Created hospitals table")
        
        # Check and add hospital_id to users table
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'hospital_id'
        """))
        if not result.fetchone():
            conn.execute(text("ALTER TABLE users ADD COLUMN hospital_id INTEGER REFERENCES hospitals(id)"))
            conn.commit()
            print("   ✓ Added hospital_id column to users")
        
        # Check and add new columns to encounters table
        for col in ['patient_first_name', 'patient_last_name', 'patient_dob', 'chief_complaint']:
            result = conn.execute(text(f"""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'encounters' AND column_name = '{col}'
            """))
            if not result.fetchone():
                if col == 'chief_complaint':
                    conn.execute(text(f"ALTER TABLE encounters ADD COLUMN {col} VARCHAR(500)"))
                else:
                    conn.execute(text(f"ALTER TABLE encounters ADD COLUMN {col} VARCHAR(100)"))
                conn.commit()
                print(f"   ✓ Added {col} column to encounters")
    
    # Seed test users if they don't exist
    from phoenix_guardian.models import User, UserRole
    from phoenix_guardian.api.auth.utils import hash_password
    
    with db.session_scope() as session:
        # Check if users already exist
        existing = session.query(User).filter(User.email == "admin@phoenixguardian.health").first()
        if not existing:
            # Create test users
            test_users = [
                User(
                    email="admin@phoenixguardian.health",
                    password_hash=hash_password("Admin123!"),
                    first_name="System",
                    last_name="Admin",
                    role=UserRole.ADMIN,
                    is_active=True,
                ),
                User(
                    email="dr.smith@phoenixguardian.health",
                    password_hash=hash_password("Doctor123!"),
                    first_name="John",
                    last_name="Smith",
                    role=UserRole.PHYSICIAN,
                    npi_number="1234567890",
                    is_active=True,
                ),
                User(
                    email="nurse.jones@phoenixguardian.health",
                    password_hash=hash_password("Nurse123!"),
                    first_name="Sarah",
                    last_name="Jones",
                    role=UserRole.NURSE,
                    is_active=True,
                ),
            ]
            for user in test_users:
                session.add(user)
            print("   ✓ Test users created")
        else:
            print("   ✓ Test users already exist")
    
    db.disconnect()
    
    print("")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ Migration complete!")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
except Exception as e:
    print(f"❌ Migration failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
