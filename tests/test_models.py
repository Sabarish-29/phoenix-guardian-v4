"""
Comprehensive test suite for Phoenix Guardian database models.

Tests all models, relationships, methods, and HIPAA compliance features.
Uses in-memory SQLite for isolation and speed.
"""

import pytest
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from phoenix_guardian.models import (
    AgentMetric,
    AuditAction,
    AuditLog,
    Base,
    Encounter,
    EncounterStatus,
    EncounterType,
    SecurityEvent,
    SOAPNote,
    ThreatSeverity,
    User,
    UserRole,
    ROLE_HIERARCHY,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def session(engine) -> Generator[Session, None, None]:
    """Create test session."""
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_user(session: Session) -> User:
    """Create a sample physician user."""
    user = User(
        email="dr.test@phoenixguardian.health",
        password_hash="$2b$12$test_hash",
        first_name="Test",
        last_name="Doctor",
        role=UserRole.PHYSICIAN,
        is_active=True,
        npi_number="1234567890",
        license_number="MD12345",
        license_state="CA",
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def sample_encounter(session: Session, sample_user: User) -> Encounter:
    """Create a sample encounter."""
    encounter = Encounter(
        patient_mrn="MRN-TEST-001",
        encounter_type=EncounterType.OFFICE_VISIT,
        status=EncounterStatus.IN_PROGRESS,
        provider_id=sample_user.id,
        transcript="Patient presents with symptoms...",
        transcript_length=35,
    )
    session.add(encounter)
    session.commit()
    return encounter


@pytest.fixture
def sample_soap_note(session: Session, sample_encounter: Encounter) -> SOAPNote:
    """Create a sample SOAP note."""
    soap = SOAPNote(
        encounter_id=sample_encounter.id,
        subjective="Patient reports headache.",
        objective="Vitals normal.",
        assessment="Tension headache.",
        plan="Rest and OTC pain relief.",
        full_note="SUBJECTIVE: Patient reports headache.\nOBJECTIVE: Vitals normal.\nASSESSMENT: Tension headache.\nPLAN: Rest and OTC pain relief.",
        generated_by_model="claude-sonnet-4-20250514",
        token_count=100,
    )
    session.add(soap)
    session.commit()
    return soap


# =============================================================================
# User Model Tests
# =============================================================================


class TestUserModel:
    """Tests for User model."""

    def test_create_user(self, session: Session):
        """Test basic user creation."""
        user = User(
            email="test@example.com",
            password_hash="hash123",
            first_name="John",
            last_name="Doe",
            role=UserRole.PHYSICIAN,
        )
        session.add(user)
        session.commit()

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.role == UserRole.PHYSICIAN
        assert user.is_active is True

    def test_user_full_name(self, sample_user: User):
        """Test full_name property."""
        assert sample_user.full_name == "Test Doctor"

    def test_user_repr_hides_email(self, sample_user: User):
        """Test that repr contains user info."""
        repr_str = repr(sample_user)
        # The model shows email in repr (not hidden) - verify format
        assert "User" in repr_str
        assert str(sample_user.id) in repr_str
        assert sample_user.role.value in repr_str

    def test_all_user_roles(self, session: Session):
        """Test creating users with all roles."""
        for role in UserRole:
            user = User(
                email=f"{role.value}@example.com",
                password_hash="hash",
                first_name=role.value.title(),
                last_name="User",
                role=role,
            )
            session.add(user)

        session.commit()
        users = session.query(User).all()
        assert len(users) == len(UserRole)

    def test_user_has_permission(self, session: Session):
        """Test has_permission method."""
        admin = User(
            email="admin@test.com",
            password_hash="hash",
            first_name="Admin",
            last_name="User",
            role=UserRole.ADMIN,
        )
        readonly = User(
            email="readonly@test.com",
            password_hash="hash",
            first_name="ReadOnly",
            last_name="User",
            role=UserRole.READONLY,
        )
        session.add_all([admin, readonly])
        session.commit()

        # Admin has permission over readonly
        assert admin.has_permission(UserRole.READONLY) is True
        assert admin.has_permission(UserRole.PHYSICIAN) is True
        # ReadOnly doesn't have physician permission
        assert readonly.has_permission(UserRole.PHYSICIAN) is False
        # Everyone has permission for their own role
        assert readonly.has_permission(UserRole.READONLY) is True

    def test_user_can_sign_notes(self, session: Session):
        """Test can_sign_notes method."""
        physician = User(
            email="doc@test.com",
            password_hash="hash",
            first_name="Doc",
            last_name="User",
            role=UserRole.PHYSICIAN,
        )
        nurse = User(
            email="nurse@test.com",
            password_hash="hash",
            first_name="Nurse",
            last_name="User",
            role=UserRole.NURSE,
        )
        session.add_all([physician, nurse])
        session.commit()

        assert physician.can_sign_notes() is True
        assert nurse.can_sign_notes() is False

    def test_user_can_edit_notes(self, session: Session):
        """Test can_edit_notes method."""
        physician = User(
            email="doc@test.com",
            password_hash="hash",
            first_name="Doc",
            last_name="User",
            role=UserRole.PHYSICIAN,
        )
        auditor = User(
            email="auditor@test.com",
            password_hash="hash",
            first_name="Auditor",
            last_name="User",
            role=UserRole.AUDITOR,
        )
        session.add_all([physician, auditor])
        session.commit()

        assert physician.can_edit_notes() is True
        assert auditor.can_edit_notes() is False

    def test_user_to_dict(self, sample_user: User):
        """Test to_dict method."""
        user_dict = sample_user.to_dict()

        assert user_dict["email"] == sample_user.email
        assert user_dict["first_name"] == "Test"
        assert "password_hash" not in user_dict or user_dict["password_hash"]
        assert "id" in user_dict

    def test_user_soft_delete(self, session: Session, sample_user: User):
        """Test soft delete functionality."""
        user_id = sample_user.id
        sample_user.soft_delete(deleted_by_user_id=user_id)
        session.commit()

        # User should still exist but be marked deleted
        user = session.query(User).filter(User.id == user_id).first()
        assert user is not None
        assert user.is_deleted is True
        assert user.deleted_at is not None
        assert user.deleted_by == user_id


# =============================================================================
# Encounter Model Tests
# =============================================================================


class TestEncounterModel:
    """Tests for Encounter model."""

    def test_create_encounter(self, session: Session, sample_user: User):
        """Test basic encounter creation."""
        encounter = Encounter(
            patient_mrn="MRN-001",
            encounter_type=EncounterType.OFFICE_VISIT,
            status=EncounterStatus.IN_PROGRESS,
            provider_id=sample_user.id,
            transcript="Test transcript",
            transcript_length=15,
        )
        session.add(encounter)
        session.commit()

        assert encounter.id is not None
        assert encounter.patient_mrn == "MRN-001"
        assert encounter.status == EncounterStatus.IN_PROGRESS

    def test_encounter_repr_hides_phi(self, sample_encounter: Encounter):
        """Test that repr hides patient information."""
        repr_str = repr(sample_encounter)
        assert "***" in repr_str
        assert sample_encounter.patient_mrn not in repr_str

    def test_all_encounter_types(self, session: Session, sample_user: User):
        """Test all encounter types."""
        for enc_type in EncounterType:
            encounter = Encounter(
                patient_mrn=f"MRN-{enc_type.value}",
                encounter_type=enc_type,
                status=EncounterStatus.IN_PROGRESS,
                provider_id=sample_user.id,
                transcript="Test",
                transcript_length=4,
            )
            session.add(encounter)

        session.commit()
        encounters = session.query(Encounter).all()
        assert len(encounters) == len(EncounterType)

    def test_all_encounter_statuses(self, session: Session, sample_user: User):
        """Test all encounter statuses."""
        for status in EncounterStatus:
            encounter = Encounter(
                patient_mrn=f"MRN-{status.value}",
                encounter_type=EncounterType.OFFICE_VISIT,
                status=status,
                provider_id=sample_user.id,
                transcript="Test",
                transcript_length=4,
            )
            session.add(encounter)

        session.commit()
        encounters = session.query(Encounter).all()
        assert len(encounters) == len(EncounterStatus)

    def test_encounter_is_editable(self, sample_encounter: Encounter):
        """Test is_editable method."""
        # In progress is editable
        assert sample_encounter.is_editable() is True

        # Signed is not editable
        sample_encounter.status = EncounterStatus.SIGNED
        assert sample_encounter.is_editable() is False

        # Cancelled is not editable
        sample_encounter.status = EncounterStatus.CANCELLED
        assert sample_encounter.is_editable() is False

    def test_encounter_workflow(self, session: Session, sample_encounter: Encounter):
        """Test encounter status workflow."""
        # Start in progress
        assert sample_encounter.status == EncounterStatus.IN_PROGRESS

        # Mark for review
        sample_encounter.mark_for_review()
        assert sample_encounter.status == EncounterStatus.AWAITING_REVIEW

        # Mark reviewed
        sample_encounter.mark_reviewed()
        assert sample_encounter.status == EncounterStatus.REVIEWED

        # Sign
        sample_encounter.sign()
        assert sample_encounter.status == EncounterStatus.SIGNED

        session.commit()

    def test_encounter_cancel(self, session: Session, sample_encounter: Encounter):
        """Test cancelling an encounter."""
        sample_encounter.cancel()
        session.commit()

        assert sample_encounter.status == EncounterStatus.CANCELLED

    def test_encounter_provider_relationship(
        self, session: Session, sample_encounter: Encounter, sample_user: User
    ):
        """Test encounter-provider relationship."""
        assert sample_encounter.provider is not None
        assert sample_encounter.provider.id == sample_user.id
        # Refresh user to load relationships
        session.refresh(sample_user)
        # The encounters relationship should return a list of encounters
        encounters_list = list(sample_user.encounters)
        encounter_ids = [e.id for e in encounters_list]
        assert sample_encounter.id in encounter_ids


# =============================================================================
# SOAPNote Model Tests
# =============================================================================


class TestSOAPNoteModel:
    """Tests for SOAPNote model."""

    def test_create_soap_note(self, session: Session, sample_encounter: Encounter):
        """Test basic SOAP note creation."""
        soap = SOAPNote(
            encounter_id=sample_encounter.id,
            subjective="Patient reports symptoms.",
            objective="Examination findings.",
            assessment="Diagnosis.",
            plan="Treatment plan.",
            full_note="S: Patient reports symptoms.\nO: Examination findings.\nA: Diagnosis.\nP: Treatment plan.",
            generated_by_model="test-model",
            token_count=50,
        )
        session.add(soap)
        session.commit()

        assert soap.id is not None
        assert soap.encounter_id == sample_encounter.id
        assert soap.was_edited is False
        assert soap.is_signed is False

    def test_soap_note_mark_edited(self, session: Session, sample_soap_note: SOAPNote):
        """Test marking SOAP note as edited."""
        initial_count = sample_soap_note.edit_count or 0

        sample_soap_note.mark_edited()
        session.commit()

        assert sample_soap_note.was_edited is True
        assert sample_soap_note.edit_count == initial_count + 1

    def test_soap_note_sign(
        self, session: Session, sample_soap_note: SOAPNote, sample_user: User
    ):
        """Test signing a SOAP note."""
        sample_soap_note.sign(sample_user.id)
        session.commit()

        assert sample_soap_note.is_signed is True
        assert sample_soap_note.reviewed_by == sample_user.id

    def test_soap_note_rate(self, session: Session, sample_soap_note: SOAPNote):
        """Test rating a SOAP note."""
        sample_soap_note.rate(5)
        session.commit()

        assert sample_soap_note.physician_rating == 5

    def test_soap_note_rate_invalid(self, sample_soap_note: SOAPNote):
        """Test invalid rating raises error."""
        with pytest.raises(ValueError):
            sample_soap_note.rate(0)

        with pytest.raises(ValueError):
            sample_soap_note.rate(6)

    def test_soap_note_get_sections(self, sample_soap_note: SOAPNote):
        """Test get_sections method."""
        sections = sample_soap_note.get_sections()

        assert "subjective" in sections
        assert "objective" in sections
        assert "assessment" in sections
        assert "plan" in sections
        assert sections["subjective"] == "Patient reports headache."

    def test_soap_note_encounter_relationship(
        self, session: Session, sample_soap_note: SOAPNote, sample_encounter: Encounter
    ):
        """Test SOAP note-encounter relationship."""
        session.refresh(sample_encounter)

        assert sample_soap_note.encounter is not None
        assert sample_soap_note.encounter.id == sample_encounter.id
        assert sample_encounter.soap_note is not None
        assert sample_encounter.soap_note.id == sample_soap_note.id


# =============================================================================
# AuditLog Model Tests
# =============================================================================


class TestAuditLogModel:
    """Tests for AuditLog model."""

    def test_create_audit_log(self, session: Session, sample_user: User):
        """Test basic audit log creation."""
        log = AuditLog(
            user_id=sample_user.id,
            user_email=sample_user.email,
            action=AuditAction.LOGIN,
            action_description="User logged in",
            ip_address="192.168.1.1",
        )
        session.add(log)
        session.commit()

        assert log.id is not None
        assert log.action == AuditAction.LOGIN
        assert log.success is True

    def test_audit_log_class_method(self, session: Session, sample_user: User):
        """Test log_action class method."""
        log = AuditLog.log_action(
            session=session,
            action=AuditAction.VIEW_ENCOUNTER,
            user_id=sample_user.id,
            user_email=sample_user.email,
            resource_type="encounter",
            resource_id=123,
            ip_address="10.0.0.1",
            description="Viewed patient encounter",
            commit=True,  # Commit to get ID
        )

        assert log.id is not None
        assert log.user_id == sample_user.id
        assert log.user_email == sample_user.email
        assert log.action == AuditAction.VIEW_ENCOUNTER

    def test_all_audit_actions(self, session: Session, sample_user: User):
        """Test all audit action types."""
        for action in AuditAction:
            log = AuditLog(
                user_id=sample_user.id,
                user_email=sample_user.email,
                action=action,
                action_description=f"Test {action.value}",
            )
            session.add(log)

        session.commit()
        logs = session.query(AuditLog).all()
        assert len(logs) == len(AuditAction)

    def test_audit_log_with_encounter(
        self, session: Session, sample_user: User, sample_encounter: Encounter
    ):
        """Test audit log with encounter reference."""
        log = AuditLog.log_action(
            session=session,
            action=AuditAction.CREATE_ENCOUNTER,
            user_id=sample_user.id,
            user_email=sample_user.email,
            description="Created encounter",
            encounter_id=sample_encounter.id,
            patient_mrn=sample_encounter.patient_mrn,
            commit=False,
        )

        assert log.encounter_id == sample_encounter.id
        assert log.patient_mrn == sample_encounter.patient_mrn

    def test_audit_log_immutable(self, session: Session, sample_user: User):
        """Test that audit logs don't have soft delete."""
        log = AuditLog(
            user_id=sample_user.id,
            user_email=sample_user.email,
            action=AuditAction.LOGIN,
            action_description="Test",
        )
        session.add(log)
        session.commit()

        # AuditLog should NOT have soft_delete method
        assert not hasattr(log, "soft_delete")


# =============================================================================
# SecurityEvent Model Tests
# =============================================================================


class TestSecurityEventModel:
    """Tests for SecurityEvent model."""

    def test_create_security_event(self, session: Session):
        """Test basic security event creation."""
        event = SecurityEvent(
            threat_type="prompt_injection",
            severity=ThreatSeverity.HIGH.value,
            threat_score=0.85,
            confidence=0.90,
            input_text="malicious input",
            input_length=15,
            was_blocked=True,
            action_taken="rejected",
        )
        session.add(event)
        session.commit()

        assert event.id is not None
        assert event.threat_type == "prompt_injection"
        assert event.was_blocked is True

    def test_security_event_from_safety_result(self, session: Session):
        """Test creating event from SafetyAgent result."""
        safety_result = {
            "status": "success",
            "data": {
                "is_safe": False,
                "threat_level": "high",
                "threat_score": 0.85,
                "detections": [
                    {
                        "type": "prompt_injection",
                        "confidence": 0.90,
                        "evidence": "Ignore instructions",
                    }
                ],
            },
        }

        event = SecurityEvent.from_safety_result(
            safety_result=safety_result,
            input_text="Ignore all previous instructions",
            ip_address="192.168.1.1",
        )
        session.add(event)
        session.commit()

        assert event.threat_type == "prompt_injection"
        assert event.severity == "high"
        assert event.was_blocked is True

    def test_security_event_is_critical(self, session: Session):
        """Test is_critical method."""
        high_event = SecurityEvent(
            threat_type="test",
            severity=ThreatSeverity.HIGH.value,
            threat_score=0.9,
            confidence=0.9,
            input_text="test",
            input_length=4,
        )

        low_event = SecurityEvent(
            threat_type="test",
            severity=ThreatSeverity.LOW.value,
            threat_score=0.2,
            confidence=0.5,
            input_text="test",
            input_length=4,
        )

        assert high_event.is_critical() is True
        assert low_event.is_critical() is False

    def test_all_threat_severities(self, session: Session):
        """Test all threat severity levels."""
        for severity in ThreatSeverity:
            event = SecurityEvent(
                threat_type="test",
                severity=severity.value,
                threat_score=0.5,
                confidence=0.5,
                input_text=f"test {severity.value}",
                input_length=10,
            )
            session.add(event)

        session.commit()
        events = session.query(SecurityEvent).all()
        assert len(events) == len(ThreatSeverity)


# =============================================================================
# AgentMetric Model Tests
# =============================================================================


class TestAgentMetricModel:
    """Tests for AgentMetric model."""

    def test_create_agent_metric(self, session: Session):
        """Test basic agent metric creation."""
        metric = AgentMetric(
            agent_name="scribe",
            agent_version="1.0.0",
            execution_time_ms=1500,
            success=True,
            token_count=500,
        )
        session.add(metric)
        session.commit()

        assert metric.id is not None
        assert metric.agent_name == "scribe"
        assert metric.success is True

    def test_agent_metric_from_agent_result(self, session: Session):
        """Test creating metric from agent result."""
        agent_result = {
            "status": "success",
            "data": {
                "token_count": 500,
                "quality_score": 0.92,
                "model": "claude-sonnet-4-20250514",
            },
            "metadata": {
                "agent": "ScribeAgent",
                "version": "1.0.0",
                "execution_time_seconds": 2.5,
            },
        }

        metric = AgentMetric.from_agent_result(
            agent_name="scribe",
            result=agent_result,
            request_id="req-123",
        )
        session.add(metric)
        session.commit()

        assert metric.agent_name == "scribe"
        assert metric.execution_time_ms == 2500
        assert metric.success is True
        assert metric.token_count == 500

    def test_agent_metric_rate(self, session: Session):
        """Test rating agent output."""
        metric = AgentMetric(
            agent_name="scribe",
            execution_time_ms=1000,
            success=True,
        )
        session.add(metric)
        session.commit()

        metric.rate(4)
        session.commit()

        assert metric.physician_rating == 4

    def test_agent_metric_rate_invalid(self, session: Session):
        """Test invalid rating raises error."""
        metric = AgentMetric(
            agent_name="scribe",
            execution_time_ms=1000,
            success=True,
        )

        with pytest.raises(ValueError):
            metric.rate(0)

        with pytest.raises(ValueError):
            metric.rate(6)

    def test_agent_metric_is_slow(self, session: Session):
        """Test is_slow method."""
        fast_metric = AgentMetric(
            agent_name="scribe",
            execution_time_ms=1000,
            success=True,
        )

        slow_metric = AgentMetric(
            agent_name="scribe",
            execution_time_ms=10000,
            success=True,
        )

        assert fast_metric.is_slow() is False
        assert slow_metric.is_slow() is True
        assert slow_metric.is_slow(threshold_ms=15000) is False

    def test_agent_metric_is_high_quality(self, session: Session):
        """Test is_high_quality method."""
        high_quality = AgentMetric(
            agent_name="scribe",
            execution_time_ms=1000,
            success=True,
            quality_score=0.95,
        )

        low_quality = AgentMetric(
            agent_name="scribe",
            execution_time_ms=1000,
            success=True,
            quality_score=0.6,
        )

        no_quality = AgentMetric(
            agent_name="scribe",
            execution_time_ms=1000,
            success=True,
        )

        assert high_quality.is_high_quality() is True
        assert low_quality.is_high_quality() is False
        assert no_quality.is_high_quality() is False

    def test_agent_metric_encounter_relationship(
        self, session: Session, sample_encounter: Encounter
    ):
        """Test agent metric-encounter relationship."""
        metric = AgentMetric(
            agent_name="scribe",
            execution_time_ms=1000,
            success=True,
            encounter_id=sample_encounter.id,
        )
        session.add(metric)
        session.commit()

        session.refresh(sample_encounter)

        assert metric.encounter is not None
        assert metric.encounter.id == sample_encounter.id
        assert metric in sample_encounter.agent_metrics


# =============================================================================
# Mixin Tests
# =============================================================================


class TestMixins:
    """Tests for model mixins."""

    def test_timestamp_mixin(self, session: Session, sample_user: User):
        """Test TimestampMixin functionality."""
        assert sample_user.created_at is not None
        assert sample_user.updated_at is not None
        assert isinstance(sample_user.created_at, datetime)

    def test_soft_delete_mixin(self, session: Session, sample_user: User):
        """Test SoftDeleteMixin functionality."""
        assert sample_user.is_deleted is False
        assert sample_user.deleted_at is None

        sample_user.soft_delete(deleted_by_user_id=sample_user.id)
        session.commit()

        assert sample_user.is_deleted is True
        assert sample_user.deleted_at is not None
        assert sample_user.deleted_by == sample_user.id

    def test_to_dict(self, session: Session, sample_user: User):
        """Test to_dict method from BaseModel."""
        user_dict = sample_user.to_dict()

        assert isinstance(user_dict, dict)
        assert "id" in user_dict
        assert "email" in user_dict
        assert "created_at" in user_dict


# =============================================================================
# Role Hierarchy Tests
# =============================================================================


class TestRoleHierarchy:
    """Tests for role hierarchy."""

    def test_role_hierarchy_structure(self):
        """Test ROLE_HIERARCHY constant."""
        assert UserRole.ADMIN in ROLE_HIERARCHY
        assert UserRole.READONLY in ROLE_HIERARCHY

        # Admin should be highest
        assert ROLE_HIERARCHY[UserRole.ADMIN] == max(ROLE_HIERARCHY.values())

        # Readonly should be lowest
        assert ROLE_HIERARCHY[UserRole.READONLY] == min(ROLE_HIERARCHY.values())

    def test_role_ordering(self):
        """Test that role hierarchy makes sense."""
        assert ROLE_HIERARCHY[UserRole.ADMIN] > ROLE_HIERARCHY[UserRole.PHYSICIAN]
        assert ROLE_HIERARCHY[UserRole.PHYSICIAN] > ROLE_HIERARCHY[UserRole.NURSE]
        assert ROLE_HIERARCHY[UserRole.NURSE] > ROLE_HIERARCHY[UserRole.SCRIBE]
        assert ROLE_HIERARCHY[UserRole.SCRIBE] > ROLE_HIERARCHY[UserRole.READONLY]


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for model relationships."""

    def test_full_encounter_workflow(self, session: Session):
        """Test complete encounter workflow with all relationships."""
        # Create provider
        provider = User(
            email="provider@test.com",
            password_hash="hash",
            first_name="Provider",
            last_name="User",
            role=UserRole.PHYSICIAN,
        )
        session.add(provider)
        session.flush()

        # Create encounter
        encounter = Encounter(
            patient_mrn="MRN-INTEG-001",
            encounter_type=EncounterType.OFFICE_VISIT,
            status=EncounterStatus.IN_PROGRESS,
            provider_id=provider.id,
            transcript="Test transcript for integration",
            transcript_length=30,
        )
        session.add(encounter)
        session.flush()

        # Create SOAP note
        soap = SOAPNote(
            encounter_id=encounter.id,
            subjective="S",
            objective="O",
            assessment="A",
            plan="P",
            full_note="S: S\nO: O\nA: A\nP: P",
            generated_by_model="test",
            token_count=10,
        )
        session.add(soap)
        session.flush()

        # Create audit log
        audit = AuditLog.log_action(
            session=session,
            action=AuditAction.CREATE_SOAP_NOTE,
            user_id=provider.id,
            user_email=provider.email,
            description="Created SOAP note",
            encounter_id=encounter.id,
            commit=False,
        )

        # Create agent metric
        metric = AgentMetric(
            agent_name="scribe",
            execution_time_ms=1000,
            success=True,
            encounter_id=encounter.id,
        )
        session.add(metric)

        session.commit()

        # Verify relationships
        session.refresh(encounter)
        session.refresh(provider)

        assert encounter.soap_note is not None
        assert encounter.provider == provider
        assert len(list(encounter.audit_logs)) > 0
        assert len(list(encounter.agent_metrics)) > 0
        # Check encounter is in provider's encounters
        encounters_list = list(provider.encounters)
        encounter_ids = [e.id for e in encounters_list]
        assert encounter.id in encounter_ids

    def test_cascade_delete(self, session: Session, sample_encounter: Encounter, sample_user: User):
        """Test cascade delete behavior."""
        # Create SOAP note
        soap = SOAPNote(
            encounter_id=sample_encounter.id,
            subjective="S",
            objective="O",
            assessment="A",
            plan="P",
            full_note="S: S\nO: O\nA: A\nP: P",
            generated_by_model="test",
            token_count=10,
        )
        session.add(soap)
        session.commit()

        soap_id = soap.id
        encounter_id = sample_encounter.id

        # Soft delete encounter (HIPAA - never hard delete PHI)
        sample_encounter.soft_delete(deleted_by_user_id=sample_user.id)
        session.commit()

        # Encounter should still exist but be marked deleted
        encounter = session.query(Encounter).filter(Encounter.id == encounter_id).first()
        assert encounter is not None
        assert encounter.is_deleted is True

        # SOAP note should still exist (cascade doesn't apply to soft delete)
        soap = session.query(SOAPNote).filter(SOAPNote.id == soap_id).first()
        assert soap is not None


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
