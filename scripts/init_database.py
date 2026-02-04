"""
Database initialization script for Phoenix Guardian.

Creates all tables and seeds sample data for development/testing.

Usage:
    python scripts/init_database.py
    python scripts/init_database.py --seed
    python scripts/init_database.py --drop --seed
"""

import argparse
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phoenix_guardian.database import Database, get_test_db_url
from phoenix_guardian.models import (
    AuditAction,
    AuditLog,
    Encounter,
    EncounterStatus,
    EncounterType,
    SOAPNote,
    User,
    UserRole,
)


def create_sample_users(session) -> dict:
    """
    Create sample users for development.

    Returns:
        Dictionary of created users
    """
    users = {}

    # Admin user
    admin = User(
        email="admin@phoenixguardian.health",
        password_hash="$2b$12$hashed_password_here",  # bcrypt hash
        first_name="System",
        last_name="Administrator",
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(admin)
    users["admin"] = admin

    # Physician
    physician = User(
        email="dr.smith@phoenixguardian.health",
        password_hash="$2b$12$hashed_password_here",
        first_name="John",
        last_name="Smith",
        role=UserRole.PHYSICIAN,
        is_active=True,
        npi_number="1234567890",
        license_number="MD12345",
        license_state="CA",
    )
    session.add(physician)
    users["physician"] = physician

    # Nurse
    nurse = User(
        email="nurse.jones@phoenixguardian.health",
        password_hash="$2b$12$hashed_password_here",
        first_name="Mary",
        last_name="Jones",
        role=UserRole.NURSE,
        is_active=True,
        license_number="RN54321",
        license_state="CA",
    )
    session.add(nurse)
    users["nurse"] = nurse

    # Scribe
    scribe = User(
        email="scribe.wilson@phoenixguardian.health",
        password_hash="$2b$12$hashed_password_here",
        first_name="Alex",
        last_name="Wilson",
        role=UserRole.SCRIBE,
        is_active=True,
    )
    session.add(scribe)
    users["scribe"] = scribe

    # Auditor
    auditor = User(
        email="auditor@phoenixguardian.health",
        password_hash="$2b$12$hashed_password_here",
        first_name="Compliance",
        last_name="Officer",
        role=UserRole.AUDITOR,
        is_active=True,
    )
    session.add(auditor)
    users["auditor"] = auditor

    session.flush()  # Get IDs
    print(f"Created {len(users)} sample users")

    return users


def create_sample_encounter(session, physician: User) -> Encounter:
    """
    Create a sample encounter with SOAP note.

    Args:
        session: Database session
        physician: Provider for encounter

    Returns:
        Created encounter
    """
    transcript = """
    Patient: Hi doctor, I've been having this persistent cough for about two weeks now.
    Doctor: I see. Is the cough dry or productive?
    Patient: It's been productive, with some yellowish mucus.
    Doctor: Any fever, shortness of breath, or chest pain?
    Patient: I had a low-grade fever last week, but it's gone now. No chest pain.
    Doctor: Let me listen to your lungs. Take a deep breath.
    Doctor: I hear some slight wheezing. Have you had any allergies or asthma history?
    Patient: I have seasonal allergies, but no asthma.
    Doctor: Based on the exam, this looks like acute bronchitis. I'll prescribe
    some medication and recommend rest.
    """

    encounter = Encounter(
        patient_mrn="MRN-12345",
        encounter_type=EncounterType.OFFICE_VISIT,
        status=EncounterStatus.SIGNED,
        provider_id=physician.id,
        transcript=transcript.strip(),
        transcript_length=len(transcript),
        processing_time_ms=2500.0,
        safety_check_passed=True,
        threat_score=0.0,
    )
    session.add(encounter)
    session.flush()

    # Create SOAP note
    soap_note = SOAPNote(
        encounter_id=encounter.id,
        subjective="""
        Chief Complaint: Persistent productive cough x 2 weeks
        HPI: 45-year-old presents with 2-week history of productive cough
        with yellowish sputum. Reports low-grade fever last week, now resolved.
        Denies chest pain or significant shortness of breath.
        PMH: Seasonal allergies, no asthma history
        """.strip(),
        objective="""
        Vitals: T 98.6°F, BP 120/80, HR 72, RR 16, SpO2 98% RA
        General: Alert, in no acute distress
        HEENT: Oropharynx without erythema
        Lungs: Bilateral mild wheezing, no rales/rhonchi
        CV: RRR, no murmurs
        """.strip(),
        assessment="""
        1. Acute bronchitis (J20.9)
        - Likely viral etiology given symptom duration and resolution of fever
        - Mild wheezing noted, may benefit from bronchodilator
        """.strip(),
        plan="""
        1. Albuterol inhaler PRN for wheezing
        2. Guaifenesin 400mg q4h PRN for cough
        3. Increase fluid intake, rest
        4. Return in 1 week if not improving or sooner if worsening
        5. Patient education provided on bronchitis and warning signs
        """.strip(),
        full_note="",  # Will be set below
        generated_by_model="claude-sonnet-4-20250514",
        token_count=850,
        was_edited=True,
        edit_count=1,
        reviewed_by=physician.id,
        is_signed=True,
        physician_rating=4,
    )
    session.add(soap_note)
    session.flush()

    # Generate full note
    soap_note.full_note = f"""
SOAP NOTE
=========
Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
Provider: {physician.full_name}
Patient MRN: {encounter.patient_mrn}

SUBJECTIVE
----------
{soap_note.subjective}

OBJECTIVE
---------
{soap_note.objective}

ASSESSMENT
----------
{soap_note.assessment}

PLAN
----
{soap_note.plan}

Electronically signed by {physician.full_name}, MD
    """.strip()

    print(f"Created sample encounter (ID: {encounter.id})")
    return encounter


def create_sample_audit_logs(session, users: dict, encounter: Encounter) -> None:
    """
    Create sample audit log entries.

    Args:
        session: Database session
        users: Dictionary of users
        encounter: Sample encounter
    """
    admin = users["admin"]
    physician = users["physician"]
    
    # Admin login
    AuditLog.log_action(
        session=session,
        action=AuditAction.LOGIN,
        user_id=admin.id,
        user_email=admin.email,
        description="Admin logged in",
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 Chrome/120.0",
        commit=False,
    )
    
    # Physician creates encounter
    AuditLog.log_action(
        session=session,
        action=AuditAction.CREATE_ENCOUNTER,
        user_id=physician.id,
        user_email=physician.email,
        description="Created patient encounter",
        resource_type="encounter",
        resource_id=encounter.id,
        encounter_id=encounter.id,
        patient_mrn=encounter.patient_mrn,
        ip_address="192.168.1.101",
        commit=False,
    )
    
    # System generates SOAP note
    AuditLog.log_action(
        session=session,
        action=AuditAction.CREATE_SOAP_NOTE,
        user_id=physician.id,
        user_email=physician.email,
        description="AI generated SOAP note",
        resource_type="soap_note",
        resource_id=encounter.soap_note.id if encounter.soap_note else None,
        encounter_id=encounter.id,
        patient_mrn=encounter.patient_mrn,
        ip_address="192.168.1.101",
        metadata={"model": "claude-sonnet-4-20250514", "token_count": 850},
        commit=False,
    )
    
    # Physician signs note
    AuditLog.log_action(
        session=session,
        action=AuditAction.SIGN_SOAP_NOTE,
        user_id=physician.id,
        user_email=physician.email,
        description="Physician signed SOAP note",
        resource_type="soap_note",
        resource_id=encounter.soap_note.id if encounter.soap_note else None,
        encounter_id=encounter.id,
        patient_mrn=encounter.patient_mrn,
        ip_address="192.168.1.101",
        commit=False,
    )

    session.flush()
    print("Created 4 sample audit log entries")


def init_database(
    db_url: str | None = None,
    drop_existing: bool = False,
    seed_data: bool = False,
) -> None:
    """
    Initialize the database.

    Args:
        db_url: Database URL (uses env config if None)
        drop_existing: Drop existing tables first
        seed_data: Seed sample data
    """
    print("=" * 60)
    print("Phoenix Guardian Database Initialization")
    print("=" * 60)

    # Create database instance
    db = Database()

    # Use test URL if not provided
    url = db_url or get_test_db_url()

    print(f"\nConnecting to database...")
    db.connect(url)
    print("Connected successfully!")

    # Drop existing tables if requested
    if drop_existing:
        print("\nDropping existing tables...")
        db.drop_tables()
        print("Tables dropped.")

    # Create tables
    print("\nCreating tables...")
    db.create_tables()
    print("Tables created successfully!")

    # Seed data if requested
    if seed_data:
        print("\nSeeding sample data...")
        with db.session_scope() as session:
            users = create_sample_users(session)
            encounter = create_sample_encounter(session, users["physician"])
            create_sample_audit_logs(session, users, encounter)
        print("Sample data seeded successfully!")

    # Health check
    print("\nRunning health check...")
    if db.health_check():
        print("Database health check passed!")
    else:
        print("WARNING: Database health check failed!")

    print("\n" + "=" * 60)
    print("Database initialization complete!")
    print("=" * 60)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Initialize Phoenix Guardian database"
    )
    parser.add_argument(
        "--url",
        type=str,
        help="Database URL (uses env config if not provided)",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop existing tables before creating",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed sample data for development",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use in-memory SQLite for testing",
    )

    args = parser.parse_args()

    # Use test URL if --test flag
    url = get_test_db_url() if args.test else args.url

    init_database(
        db_url=url,
        drop_existing=args.drop,
        seed_data=args.seed,
    )


if __name__ == "__main__":
    main()
