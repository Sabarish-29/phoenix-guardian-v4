#!/usr/bin/env python3
"""
Seed data script for Phoenix Guardian.

Creates realistic test data for development and testing:
- 3 hospitals with realistic healthcare organization data
- 10 test users (5 physicians, 3 nurses, 2 admins)
- 100 test encounters with varied patient data

Usage:
    python scripts/seed_data.py
    python scripts/seed_data.py --clear  # Clear existing data first
"""

import os
import sys
import random
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from faker import Faker

# Initialize Faker with medical-friendly seed
fake = Faker()
Faker.seed(42)  # Reproducible data
random.seed(42)


def get_database_url() -> str:
    """Build database URL from environment variables."""
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "phoenix_guardian")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    
    if not DB_PASSWORD:
        print("ERROR: DB_PASSWORD not set in .env file")
        sys.exit(1)
    
    return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def seed_hospitals(session) -> list:
    """
    Create 3 test hospitals with realistic data.
    
    Returns:
        List of created Hospital objects
    """
    from phoenix_guardian.models import Hospital, HospitalType
    
    hospitals_data = [
        {
            "name": "Phoenix Memorial Hospital",
            "code": "PMH001",
            "hospital_type": HospitalType.HOSPITAL,
            "address": "1200 Healthcare Boulevard",
            "city": "Phoenix",
            "state": "AZ",
            "zip_code": "85001",
            "phone": "(602) 555-0100",
            "email": "info@phoenixmemorial.health",
            "website": "https://phoenixmemorial.health",
            "npi": "1234567890",
            "tax_id": "86-1234567",
            "is_active": True,
        },
        {
            "name": "Valley View Medical Center",
            "code": "VVM002",
            "hospital_type": HospitalType.ACADEMIC_MEDICAL_CENTER,
            "address": "500 University Drive",
            "city": "Tempe",
            "state": "AZ",
            "zip_code": "85281",
            "phone": "(480) 555-0200",
            "email": "contact@valleyviewmed.edu",
            "website": "https://valleyviewmed.edu",
            "npi": "2345678901",
            "tax_id": "86-2345678",
            "is_active": True,
        },
        {
            "name": "Desert Springs Community Clinic",
            "code": "DSC003",
            "hospital_type": HospitalType.COMMUNITY_HEALTH_CENTER,
            "address": "789 Community Way",
            "city": "Mesa",
            "state": "AZ",
            "zip_code": "85201",
            "phone": "(480) 555-0300",
            "email": "hello@desertspringsclinic.org",
            "website": "https://desertspringsclinic.org",
            "npi": "3456789012",
            "tax_id": "86-3456789",
            "is_active": True,
        },
    ]
    
    hospitals = []
    for data in hospitals_data:
        existing = session.query(Hospital).filter(Hospital.code == data["code"]).first()
        if existing:
            print(f"   - Hospital '{data['name']}' already exists")
            hospitals.append(existing)
        else:
            hospital = Hospital(**data)
            session.add(hospital)
            hospitals.append(hospital)
            print(f"   + Created hospital: {data['name']}")
    
    session.flush()
    return hospitals


def seed_users(session, hospitals: list) -> list:
    """
    Create 10 test users (5 physicians, 3 nurses, 2 admins).
    
    Args:
        session: Database session
        hospitals: List of Hospital objects to assign users to
        
    Returns:
        List of created User objects
    """
    from phoenix_guardian.models import User, UserRole
    from phoenix_guardian.api.auth.utils import hash_password
    
    # Medical specialties for physicians
    specialties = ["Internal Medicine", "Family Medicine", "Emergency Medicine", 
                   "Cardiology", "Pediatrics"]
    
    users_data = [
        # 2 Admins
        {
            "email": "admin@phoenixguardian.health",
            "password": "Admin123!",
            "first_name": "System",
            "last_name": "Administrator",
            "role": UserRole.ADMIN,
            "hospital_id": hospitals[0].id,
            "npi_number": None,
        },
        {
            "email": "admin2@phoenixguardian.health",
            "password": "Admin123!",
            "first_name": "Backup",
            "last_name": "Admin",
            "role": UserRole.ADMIN,
            "hospital_id": hospitals[1].id,
            "npi_number": None,
        },
        # 5 Physicians
        {
            "email": "dr.smith@phoenixguardian.health",
            "password": "Doctor123!",
            "first_name": "John",
            "last_name": "Smith",
            "role": UserRole.PHYSICIAN,
            "hospital_id": hospitals[0].id,
            "npi_number": "1111111111",
            "license_number": "MD-12345",
            "license_state": "AZ",
        },
        {
            "email": "dr.johnson@phoenixguardian.health",
            "password": "Doctor123!",
            "first_name": "Sarah",
            "last_name": "Johnson",
            "role": UserRole.PHYSICIAN,
            "hospital_id": hospitals[0].id,
            "npi_number": "2222222222",
            "license_number": "MD-23456",
            "license_state": "AZ",
        },
        {
            "email": "dr.williams@phoenixguardian.health",
            "password": "Doctor123!",
            "first_name": "Michael",
            "last_name": "Williams",
            "role": UserRole.PHYSICIAN,
            "hospital_id": hospitals[1].id,
            "npi_number": "3333333333",
            "license_number": "MD-34567",
            "license_state": "AZ",
        },
        {
            "email": "dr.brown@phoenixguardian.health",
            "password": "Doctor123!",
            "first_name": "Emily",
            "last_name": "Brown",
            "role": UserRole.PHYSICIAN,
            "hospital_id": hospitals[1].id,
            "npi_number": "4444444444",
            "license_number": "MD-45678",
            "license_state": "AZ",
        },
        {
            "email": "dr.davis@phoenixguardian.health",
            "password": "Doctor123!",
            "first_name": "Robert",
            "last_name": "Davis",
            "role": UserRole.PHYSICIAN,
            "hospital_id": hospitals[2].id,
            "npi_number": "5555555555",
            "license_number": "MD-56789",
            "license_state": "AZ",
        },
        # 3 Nurses
        {
            "email": "nurse.jones@phoenixguardian.health",
            "password": "Nurse123!",
            "first_name": "Sarah",
            "last_name": "Jones",
            "role": UserRole.NURSE,
            "hospital_id": hospitals[0].id,
            "npi_number": None,
            "license_number": "RN-11111",
            "license_state": "AZ",
        },
        {
            "email": "nurse.wilson@phoenixguardian.health",
            "password": "Nurse123!",
            "first_name": "Jennifer",
            "last_name": "Wilson",
            "role": UserRole.NURSE,
            "hospital_id": hospitals[1].id,
            "npi_number": None,
            "license_number": "RN-22222",
            "license_state": "AZ",
        },
        {
            "email": "nurse.taylor@phoenixguardian.health",
            "password": "Nurse123!",
            "first_name": "Amanda",
            "last_name": "Taylor",
            "role": UserRole.NURSE,
            "hospital_id": hospitals[2].id,
            "npi_number": None,
            "license_number": "RN-33333",
            "license_state": "AZ",
        },
    ]
    
    users = []
    for data in users_data:
        existing = session.query(User).filter(User.email == data["email"]).first()
        if existing:
            print(f"   - User '{data['email']}' already exists")
            users.append(existing)
        else:
            password = data.pop("password")
            user = User(
                password_hash=hash_password(password),
                is_active=True,
                **data
            )
            session.add(user)
            users.append(user)
            print(f"   + Created user: {data['first_name']} {data['last_name']} ({data['role'].value})")
    
    session.flush()
    return users


def seed_encounters(session, users: list) -> list:
    """
    Create 100 test encounters with realistic patient data.
    
    Args:
        session: Database session
        users: List of User objects (physicians will be providers)
        
    Returns:
        List of created Encounter objects
    """
    from phoenix_guardian.models import Encounter, EncounterStatus, EncounterType
    
    # Get physicians only
    physicians = [u for u in users if u.role.value == "physician"]
    
    # Common chief complaints for medical encounters
    chief_complaints = [
        "chest pain",
        "shortness of breath",
        "abdominal pain",
        "headache",
        "back pain",
        "fever",
        "cough",
        "fatigue",
        "dizziness",
        "nausea and vomiting",
        "joint pain",
        "skin rash",
        "sore throat",
        "anxiety",
        "depression",
        "follow-up visit",
        "medication refill",
        "annual physical",
        "diabetes management",
        "hypertension follow-up",
    ]
    
    encounter_types = list(EncounterType)
    statuses = list(EncounterStatus)
    
    encounters = []
    base_date = datetime.now() - timedelta(days=90)
    
    for i in range(100):
        # Generate realistic patient data
        patient_gender = random.choice(["M", "F"])
        if patient_gender == "M":
            patient_first = fake.first_name_male()
        else:
            patient_first = fake.first_name_female()
        
        patient_last = fake.last_name()
        patient_dob = fake.date_of_birth(minimum_age=18, maximum_age=90).strftime("%Y-%m-%d")
        
        # Generate encounter data
        encounter_date = base_date + timedelta(days=random.randint(0, 90))
        provider = random.choice(physicians)
        
        # Weight status towards completed encounters
        status_weights = [0.05, 0.1, 0.15, 0.65, 0.05]  # IN_PROGRESS, AWAITING, REVIEWED, SIGNED, CANCELLED
        status = random.choices(statuses, weights=status_weights)[0]
        
        # Generate MRN (Medical Record Number)
        mrn = f"MRN{100000 + i:06d}"
        
        # Check if encounter with this MRN exists
        existing = session.query(Encounter).filter(Encounter.patient_mrn == mrn).first()
        if existing:
            encounters.append(existing)
            continue
        
        encounter = Encounter(
            patient_mrn=mrn,
            patient_first_name=patient_first,
            patient_last_name=patient_last,
            patient_dob=patient_dob,
            encounter_type=random.choice(encounter_types),
            status=status,
            provider_id=provider.id,
            chief_complaint=random.choice(chief_complaints),
            transcript=generate_sample_transcript(patient_first, random.choice(chief_complaints)),
            transcript_length=random.randint(500, 3000),
            processing_time_ms=random.randint(1000, 5000),
            safety_check_passed=random.random() > 0.05,  # 95% pass rate
            threat_score=random.uniform(0, 0.3),
        )
        
        # Set timestamps based on encounter date
        encounter.created_at = encounter_date
        encounter.updated_at = encounter_date + timedelta(hours=random.randint(1, 24))
        
        session.add(encounter)
        encounters.append(encounter)
    
    session.flush()
    print(f"   + Created {len(encounters)} encounters")
    return encounters


def generate_sample_transcript(patient_name: str, complaint: str) -> str:
    """Generate a sample medical transcript."""
    return f"""
Doctor: Good morning, {patient_name}. How are you feeling today?

Patient: Not great, doctor. I've been experiencing {complaint} for the past few days.

Doctor: I'm sorry to hear that. Can you tell me more about when it started and how severe it is?

Patient: It started about three days ago. It's been getting progressively worse.

Doctor: Have you tried any medications or treatments at home?

Patient: Just some over-the-counter pain relief, but it hasn't helped much.

Doctor: I see. Let me examine you and we'll run some tests to determine the cause.

[Physical examination performed]

Doctor: Based on my examination, I'd like to order some additional tests. In the meantime, I'm going to prescribe some medication to help with your symptoms.

Patient: Thank you, doctor.

Doctor: You're welcome. Please follow up if symptoms worsen or don't improve within a week.
""".strip()


def clear_data(session):
    """Clear all seeded data (for fresh start)."""
    from phoenix_guardian.models import Encounter, User, Hospital, SOAPNote, AuditLog
    
    print("   Clearing existing data...")
    session.query(SOAPNote).delete()
    session.query(AuditLog).delete()
    session.query(Encounter).delete()
    session.query(User).delete()
    session.query(Hospital).delete()
    session.commit()
    print("   + Data cleared")


def main():
    parser = argparse.ArgumentParser(description="Seed Phoenix Guardian database")
    parser.add_argument("--clear", action="store_true", help="Clear existing data first")
    args = parser.parse_args()
    
    print("=" * 70)
    print("Phoenix Guardian - Database Seeding")
    print("=" * 70)
    
    # Get database connection
    database_url = get_database_url()
    
    from phoenix_guardian.database.connection import db
    
    try:
        db.connect(database_url)
        db.create_tables()
        
        with db.session_scope() as session:
            if args.clear:
                clear_data(session)
            
            print("\n[1/3] Seeding hospitals...")
            hospitals = seed_hospitals(session)
            
            print("\n[2/3] Seeding users...")
            users = seed_users(session, hospitals)
            
            print("\n[3/3] Seeding encounters...")
            encounters = seed_encounters(session, users)
            
            session.commit()
        
        print("\n" + "=" * 70)
        print("[SUCCESS] Database seeding complete!")
        print("=" * 70)
        print(f"\nCreated:")
        print(f"  - {len(hospitals)} hospitals")
        print(f"  - {len(users)} users")
        print(f"  - {len(encounters)} encounters")
        print("\nTest credentials:")
        print("  Admin:     admin@phoenixguardian.health / Admin123!")
        print("  Physician: dr.smith@phoenixguardian.health / Doctor123!")
        print("  Nurse:     nurse.jones@phoenixguardian.health / Nurse123!")
        print("")
        
    except Exception as e:
        print(f"\nERROR: Seeding failed - {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.disconnect()


if __name__ == "__main__":
    main()
