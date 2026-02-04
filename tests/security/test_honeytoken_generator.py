"""
Tests for the Legal Honeytoken Generator.

This test suite verifies:
1. Legal compliance (CRITICAL - no SSNs, proper ranges)
2. Honeytoken generation functionality
3. ForensicBeacon operations
4. AttackerFingerprint report generation

Test Categories:
- Legal Compliance Tests (6): Verify strict legal requirements
- Functionality Tests (6): Test generation and validation
- ForensicBeacon Tests (3): Test beacon payload and tracking
- AttackerFingerprint Tests (2): Test fingerprint and reports
- Integration Tests (3): End-to-end scenarios
- Edge Case Tests (3): Error handling and boundaries
- Batch Generation Tests (3): Multi-honeytoken operations
- Export/Report Tests (2): Data export functionality
- Status Management Tests (2): Honeytoken lifecycle
- Configuration Tests (2): System configuration
"""

import pytest
import re
import json
import base64
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from phoenix_guardian.security.honeytoken_generator import (
    # Main classes
    HoneytokenGenerator,
    ForensicBeacon,
    LegalHoneytoken,
    AttackerFingerprint,
    # Enums
    AttackType,
    HoneytokenStatus,
    ComplianceCheck,
    # Exceptions
    HoneytokenError,
    LegalComplianceError,
    InvalidMRNError,
    BeaconError,
    FingerprintError,
    # Constants
    FCC_FICTION_PHONE_PREFIX,
    NON_ROUTABLE_EMAIL_DOMAIN,
    MRN_HONEYTOKEN_PREFIX,
    MRN_RANGE_MIN,
    MRN_RANGE_MAX,
    BEACON_TRACKING_ENDPOINT,
    SSN_PATTERN,
    # Predefined lists
    FIRST_NAMES_MALE,
    FIRST_NAMES_FEMALE,
    LAST_NAMES,
    VACANT_COMMERCIAL_ADDRESSES,
    COMMON_MEDICAL_CONDITIONS,
    COMMON_MEDICATIONS,
    COMMON_ALLERGIES
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def generator():
    """Create a HoneytokenGenerator instance."""
    return HoneytokenGenerator()


@pytest.fixture
def beacon():
    """Create a ForensicBeacon instance."""
    return ForensicBeacon()


@pytest.fixture
def sample_honeytoken(generator):
    """Generate a sample honeytoken for testing."""
    return generator.generate(attack_type="test")


@pytest.fixture
def sample_attacker_data():
    """Sample attacker data from beacon trigger."""
    return {
        "ip_address": "192.168.1.100",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0",
        "platform": "Win32",
        "language": "en-US",
        "screen_resolution": "1920x1080",
        "color_depth": 24,
        "timezone": "America/New_York",
        "canvas_fingerprint": "data:image/png;base64,abc123...",
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA GeForce GTX 1080)",
        "installed_fonts": "Arial,Verdana,Times New Roman",
        "cookies_enabled": True,
        "local_storage": True,
        "session_storage": True,
        "do_not_track": "false",
        "geolocation": {
            "city": "New York",
            "country": "US",
            "lat": 40.7128,
            "lon": -74.0060
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LEGAL COMPLIANCE TESTS (CRITICAL)
# ═══════════════════════════════════════════════════════════════════════════════

class TestLegalCompliance:
    """
    CRITICAL: Legal compliance tests.
    
    These tests verify that honeytokens NEVER contain illegal data.
    """
    
    def test_no_ssn_in_100_honeytokens(self, generator):
        """
        CRITICAL: Verify NO SSN patterns in 100 generated honeytokens.
        
        Reference: 42 USC §408(a)(7)(B) - SSN usage violations
        """
        for i in range(100):
            honeytoken = generator.generate()
            
            # Check all fields for SSN patterns
            all_text = (
                f"{honeytoken.mrn} {honeytoken.name} {honeytoken.address} "
                f"{honeytoken.city} {honeytoken.state} {honeytoken.zip_code} "
                f"{honeytoken.phone} {honeytoken.email} "
                f"{' '.join(honeytoken.conditions)} "
                f"{' '.join(honeytoken.medications)} "
                f"{' '.join(honeytoken.allergies)}"
            )
            
            # SSN pattern: XXX-XX-XXXX or XXXXXXXXX
            assert not SSN_PATTERN.search(all_text), (
                f"Honeytoken {i+1} contains SSN pattern! CRITICAL LEGAL VIOLATION!"
            )
    
    def test_mrn_always_in_honeytoken_range(self, generator):
        """
        Verify MRN is always in the reserved honeytoken range.
        
        Range: MRN-900000 to MRN-999999
        """
        for _ in range(50):
            honeytoken = generator.generate()
            
            # Check prefix
            assert honeytoken.mrn.startswith(MRN_HONEYTOKEN_PREFIX), (
                f"MRN missing required prefix: {honeytoken.mrn}"
            )
            
            # Check number range
            mrn_number = int(honeytoken.mrn[len(MRN_HONEYTOKEN_PREFIX):])
            assert MRN_RANGE_MIN <= mrn_number <= MRN_RANGE_MAX, (
                f"MRN out of legal range: {mrn_number}"
            )
    
    def test_phone_always_fcc_reserved(self, generator):
        """
        CRITICAL: Verify phone is always in FCC-reserved 555-01XX range.
        
        Reference: 47 CFR §52.21 - FCC number reservation
        """
        for _ in range(50):
            honeytoken = generator.generate()
            
            assert honeytoken.phone.startswith(FCC_FICTION_PHONE_PREFIX), (
                f"Phone not in FCC reserved range: {honeytoken.phone}"
            )
            
            # Verify full format: 555-01XX
            assert re.match(r'^555-01\d{2}$', honeytoken.phone), (
                f"Invalid phone format: {honeytoken.phone}"
            )
    
    def test_email_always_non_routable(self, generator):
        """
        Verify email always uses non-routable .internal domain.
        
        Reference: RFC 2606 - Reserved TLDs
        """
        for _ in range(50):
            honeytoken = generator.generate()
            
            assert ".internal" in honeytoken.email.lower(), (
                f"Email uses routable domain: {honeytoken.email}"
            )
            
            assert honeytoken.email.endswith(f"@{NON_ROUTABLE_EMAIL_DOMAIN}"), (
                f"Email domain mismatch: {honeytoken.email}"
            )
    
    def test_address_always_from_vacant_list(self, generator):
        """
        Verify address is always from predefined vacant commercial list.
        """
        for _ in range(50):
            honeytoken = generator.generate()
            
            # Check if address matches any in the vacant list
            address_valid = False
            for vacant in VACANT_COMMERCIAL_ADDRESSES:
                if (honeytoken.address == vacant["street"] and
                    honeytoken.city == vacant["city"] and
                    honeytoken.state == vacant["state"] and
                    honeytoken.zip_code == vacant["zip_code"]):
                    address_valid = True
                    break
            
            assert address_valid, (
                f"Address not in vacant list: {honeytoken.address}, "
                f"{honeytoken.city}, {honeytoken.state} {honeytoken.zip_code}"
            )
    
    def test_validate_legal_compliance_passes(self, generator, sample_honeytoken):
        """
        Verify validate_legal_compliance returns all True for valid honeytokens.
        """
        compliance = generator.validate_legal_compliance(sample_honeytoken)
        
        assert compliance[ComplianceCheck.NO_SSN.value] is True
        assert compliance[ComplianceCheck.MRN_HOSPITAL_INTERNAL.value] is True
        assert compliance[ComplianceCheck.PHONE_FCC_RESERVED.value] is True
        assert compliance[ComplianceCheck.EMAIL_NON_ROUTABLE.value] is True
        assert compliance[ComplianceCheck.ADDRESS_VACANT.value] is True
        assert compliance[ComplianceCheck.FULLY_COMPLIANT.value] is True


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONALITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHoneytokenGeneration:
    """Tests for honeytoken generation functionality."""
    
    def test_generate_creates_valid_honeytoken(self, generator):
        """Test basic honeytoken generation."""
        honeytoken = generator.generate(attack_type="prompt_injection")
        
        assert honeytoken is not None
        assert honeytoken.honeytoken_id.startswith("ht_")
        assert honeytoken.attack_type == "prompt_injection"
        assert honeytoken.status == HoneytokenStatus.ACTIVE.value
    
    def test_generate_assigns_unique_ids(self, generator):
        """Test that each honeytoken gets a unique ID."""
        honeytokens = [generator.generate() for _ in range(10)]
        ids = [ht.honeytoken_id for ht in honeytokens]
        
        # All IDs should be unique
        assert len(ids) == len(set(ids))
    
    def test_generate_includes_medical_data(self, generator):
        """Test that honeytokens include medical data."""
        honeytoken = generator.generate()
        
        assert len(honeytoken.conditions) >= 1
        assert len(honeytoken.medications) >= 1
        # Allergies can be empty (0-3 range)
        assert isinstance(honeytoken.allergies, list)
    
    def test_generate_with_metadata(self, generator):
        """Test honeytoken generation with custom metadata."""
        metadata = {"source": "test", "priority": "high"}
        honeytoken = generator.generate(metadata=metadata)
        
        assert honeytoken.metadata == metadata
    
    def test_generate_stores_in_tracking_dict(self, generator):
        """Test that generated honeytokens are stored for tracking."""
        honeytoken = generator.generate()
        
        assert honeytoken.honeytoken_id in generator.generated_honeytokens
        assert generator.get_honeytoken(honeytoken.honeytoken_id) == honeytoken
    
    def test_generate_all_attack_types(self, generator):
        """Test generation with all defined attack types."""
        for attack_type in AttackType:
            honeytoken = generator.generate(attack_type=attack_type.value)
            assert honeytoken.attack_type == attack_type.value


# ═══════════════════════════════════════════════════════════════════════════════
# FORENSIC BEACON TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestForensicBeacon:
    """Tests for ForensicBeacon functionality."""
    
    def test_generate_beacon_payload(self, beacon):
        """Test beacon payload generation."""
        honeytoken_id = "ht_test12345"
        payload = beacon.generate_beacon_payload(honeytoken_id)
        
        # Payload should be Base64 encoded
        assert isinstance(payload, str)
        
        # Should be decodable
        decoded = base64.b64decode(payload.encode()).decode()
        
        # Should contain honeytoken ID
        assert honeytoken_id in decoded
        
        # Should contain tracking endpoint
        assert BEACON_TRACKING_ENDPOINT in decoded
        
        # Should be valid JavaScript
        assert "function" in decoded or "(function()" in decoded
    
    def test_decode_beacon_payload(self, beacon):
        """Test beacon payload decoding."""
        honeytoken_id = "ht_decode_test"
        encoded = beacon.generate_beacon_payload(honeytoken_id)
        decoded = beacon.decode_beacon_payload(encoded)
        
        assert honeytoken_id in decoded
        assert "fingerprint" in decoded.lower()
    
    def test_record_beacon_trigger(self, beacon, sample_attacker_data):
        """Test recording beacon trigger with attacker data."""
        honeytoken_id = "ht_trigger_test"
        
        fingerprint = beacon.record_beacon_trigger(honeytoken_id, sample_attacker_data)
        
        assert fingerprint.fingerprint_id.startswith("fp_")
        assert fingerprint.honeytoken_id == honeytoken_id
        assert fingerprint.ip_address == sample_attacker_data["ip_address"]
        assert fingerprint.user_agent == sample_attacker_data["user_agent"]
        assert fingerprint.platform == sample_attacker_data["platform"]
        
        # Should be stored in triggers
        assert beacon.get_trigger(honeytoken_id) == fingerprint


# ═══════════════════════════════════════════════════════════════════════════════
# ATTACKER FINGERPRINT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAttackerFingerprint:
    """Tests for AttackerFingerprint functionality."""
    
    def test_compute_fingerprint_hash(self, sample_attacker_data):
        """Test fingerprint hash computation."""
        fingerprint = AttackerFingerprint(
            fingerprint_id="fp_test",
            honeytoken_id="ht_test",
            ip_address=sample_attacker_data["ip_address"],
            user_agent=sample_attacker_data["user_agent"],
            platform=sample_attacker_data["platform"],
            language=sample_attacker_data["language"],
            screen_resolution=sample_attacker_data["screen_resolution"],
            color_depth=sample_attacker_data["color_depth"],
            timezone=sample_attacker_data["timezone"],
            canvas_fingerprint=sample_attacker_data["canvas_fingerprint"],
            webgl_vendor=sample_attacker_data["webgl_vendor"],
            webgl_renderer=sample_attacker_data["webgl_renderer"]
        )
        
        hash_value = fingerprint.compute_hash()
        
        # Should be SHA-256 (64 hex characters)
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)
        
        # Same data should produce same hash
        hash_value2 = fingerprint.compute_hash()
        assert hash_value == hash_value2
    
    def test_generate_law_enforcement_report(self, sample_attacker_data):
        """Test law enforcement report generation."""
        fingerprint = AttackerFingerprint(
            fingerprint_id="fp_report_test",
            honeytoken_id="ht_report_test",
            ip_address=sample_attacker_data["ip_address"],
            ip_geolocation=sample_attacker_data["geolocation"],
            user_agent=sample_attacker_data["user_agent"],
            platform=sample_attacker_data["platform"],
            language=sample_attacker_data["language"],
            screen_resolution=sample_attacker_data["screen_resolution"],
            color_depth=sample_attacker_data["color_depth"],
            timezone=sample_attacker_data["timezone"],
            canvas_fingerprint=sample_attacker_data["canvas_fingerprint"],
            webgl_vendor=sample_attacker_data["webgl_vendor"],
            webgl_renderer=sample_attacker_data["webgl_renderer"]
        )
        
        report = fingerprint.generate_law_enforcement_report()
        
        # Should be ASCII art report
        assert "PHOENIX GUARDIAN SECURITY REPORT" in report
        assert "ATTACKER ATTRIBUTION" in report
        assert "ATTACK TIMELINE" in report
        assert "TECHNICAL EVIDENCE" in report
        assert "CHAIN OF CUSTODY" in report
        assert "LEGAL NOTICE" in report
        
        # Should contain attacker data
        assert sample_attacker_data["ip_address"] in report
        assert "CFAA" in report or "Computer Fraud" in report
        assert "HIPAA" in report


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """End-to-end integration tests."""
    
    def test_full_honeytoken_lifecycle(self, generator, sample_attacker_data):
        """Test complete honeytoken lifecycle: generate -> trigger -> report."""
        # Generate honeytoken
        honeytoken = generator.generate(attack_type="data_exfiltration")
        assert honeytoken.status == HoneytokenStatus.ACTIVE.value
        
        # Simulate trigger
        honeytoken.mark_triggered(
            attacker_ip=sample_attacker_data["ip_address"],
            user_agent=sample_attacker_data["user_agent"],
            fingerprint="abc123hash",
            geolocation=sample_attacker_data["geolocation"]
        )
        
        assert honeytoken.status == HoneytokenStatus.TRIGGERED.value
        assert honeytoken.attacker_ip == sample_attacker_data["ip_address"]
        assert honeytoken.trigger_count == 1
        
        # Verify in triggered list
        triggered = generator.get_triggered_honeytokens()
        assert honeytoken in triggered
    
    def test_beacon_to_fingerprint_flow(self, generator, beacon, sample_attacker_data):
        """Test flow from beacon generation to fingerprint recording."""
        # Generate honeytoken
        honeytoken = generator.generate()
        
        # Generate beacon payload
        payload = beacon.generate_beacon_payload(honeytoken.honeytoken_id)
        assert payload is not None
        
        # Simulate beacon trigger (attacker accessed honeytoken)
        fingerprint = beacon.record_beacon_trigger(
            honeytoken.honeytoken_id,
            sample_attacker_data
        )
        
        # Generate report
        report = fingerprint.generate_law_enforcement_report()
        
        assert honeytoken.honeytoken_id in report
        assert sample_attacker_data["ip_address"] in report
    
    def test_multiple_triggers_same_honeytoken(self, generator, sample_attacker_data):
        """Test multiple triggers on the same honeytoken."""
        honeytoken = generator.generate()
        
        # First trigger
        honeytoken.mark_triggered(
            attacker_ip="192.168.1.100",
            user_agent="Agent1"
        )
        assert honeytoken.trigger_count == 1
        
        # Second trigger (different attacker)
        honeytoken.mark_triggered(
            attacker_ip="10.0.0.50",
            user_agent="Agent2"
        )
        assert honeytoken.trigger_count == 2
        
        # Should retain last attacker info
        assert honeytoken.attacker_ip == "10.0.0.50"


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_invalid_mrn_format_raises_error(self):
        """Test that invalid MRN format raises InvalidMRNError."""
        with pytest.raises(InvalidMRNError):
            LegalHoneytoken(
                honeytoken_id="ht_test",
                mrn="INVALID-123456",  # Wrong prefix
                name="Test Patient",
                age=50,
                gender="M",
                address="1000 Industrial Parkway",
                city="Newark",
                state="NJ",
                zip_code="07114",
                phone="555-0123",
                email="test@honeytoken-tracker.internal",
                conditions=["Hypertension"],
                medications=["Lisinopril"],
                allergies=[],
                beacon_url="https://example.com/beacon",
                session_id="session_test",
                deployment_timestamp=datetime.now(timezone.utc)
            )
    
    def test_mrn_out_of_range_raises_error(self):
        """Test that MRN out of range raises InvalidMRNError."""
        with pytest.raises(InvalidMRNError):
            LegalHoneytoken(
                honeytoken_id="ht_test",
                mrn="MRN-100000",  # Below 900000
                name="Test Patient",
                age=50,
                gender="M",
                address="1000 Industrial Parkway",
                city="Newark",
                state="NJ",
                zip_code="07114",
                phone="555-0123",
                email="test@honeytoken-tracker.internal",
                conditions=["Hypertension"],
                medications=["Lisinopril"],
                allergies=[],
                beacon_url="https://example.com/beacon",
                session_id="session_test",
                deployment_timestamp=datetime.now(timezone.utc)
            )
    
    def test_invalid_phone_raises_compliance_error(self):
        """Test that non-FCC phone raises LegalComplianceError."""
        with pytest.raises(LegalComplianceError):
            LegalHoneytoken(
                honeytoken_id="ht_test",
                mrn="MRN-950000",
                name="Test Patient",
                age=50,
                gender="M",
                address="1000 Industrial Parkway",
                city="Newark",
                state="NJ",
                zip_code="07114",
                phone="123-456-7890",  # Not FCC reserved!
                email="test@honeytoken-tracker.internal",
                conditions=["Hypertension"],
                medications=["Lisinopril"],
                allergies=[],
                beacon_url="https://example.com/beacon",
                session_id="session_test",
                deployment_timestamp=datetime.now(timezone.utc)
            )


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH GENERATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchGeneration:
    """Tests for batch honeytoken generation."""
    
    def test_generate_batch_creates_correct_count(self, generator):
        """Test batch generation creates requested number."""
        count = 10
        honeytokens = generator.generate_batch(count)
        
        assert len(honeytokens) == count
    
    def test_generate_batch_all_unique(self, generator):
        """Test batch generation creates unique honeytokens."""
        honeytokens = generator.generate_batch(20)
        ids = [ht.honeytoken_id for ht in honeytokens]
        mrns = [ht.mrn for ht in honeytokens]
        
        assert len(ids) == len(set(ids))
        assert len(mrns) == len(set(mrns))
    
    def test_generate_batch_all_compliant(self, generator):
        """Test batch generation produces all compliant honeytokens."""
        honeytokens = generator.generate_batch(25)
        
        for ht in honeytokens:
            compliance = generator.validate_legal_compliance(ht)
            assert compliance[ComplianceCheck.FULLY_COMPLIANT.value] is True


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT AND REPORT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestExportAndReports:
    """Tests for data export and report generation."""
    
    def test_export_honeytokens_json_serializable(self, generator):
        """Test that exported honeytokens are JSON serializable."""
        generator.generate_batch(5)
        
        exported = generator.export_honeytokens()
        
        # Should be serializable to JSON
        json_str = json.dumps(exported)
        assert json_str is not None
        
        # Should round-trip
        parsed = json.loads(json_str)
        assert len(parsed) == 5
    
    def test_deployment_report_content(self, generator, sample_attacker_data):
        """Test deployment report contains required information."""
        # Generate some honeytokens
        ht1 = generator.generate()
        ht2 = generator.generate()
        ht3 = generator.generate()
        
        # Trigger one
        ht2.mark_triggered(
            attacker_ip=sample_attacker_data["ip_address"],
            user_agent=sample_attacker_data["user_agent"]
        )
        
        report = generator.generate_deployment_report()
        
        assert "DEPLOYMENT REPORT" in report
        assert "Total Honeytokens Deployed: 3" in report
        assert "Active Honeytokens: 2" in report
        assert "Triggered Honeytokens: 1" in report
        assert sample_attacker_data["ip_address"] in report


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS MANAGEMENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestStatusManagement:
    """Tests for honeytoken status management."""
    
    def test_honeytoken_status_transitions(self, generator, sample_attacker_data):
        """Test honeytoken status transitions."""
        honeytoken = generator.generate()
        
        # Initial state
        assert honeytoken.status == HoneytokenStatus.ACTIVE.value
        
        # Trigger
        honeytoken.mark_triggered(
            attacker_ip=sample_attacker_data["ip_address"],
            user_agent=sample_attacker_data["user_agent"]
        )
        assert honeytoken.status == HoneytokenStatus.TRIGGERED.value
    
    def test_get_triggered_vs_active(self, generator, sample_attacker_data):
        """Test filtering triggered vs active honeytokens."""
        # Generate 5 honeytokens
        honeytokens = generator.generate_batch(5)
        
        # Trigger 2
        honeytokens[0].mark_triggered(
            attacker_ip="1.1.1.1",
            user_agent="Agent1"
        )
        honeytokens[2].mark_triggered(
            attacker_ip="2.2.2.2",
            user_agent="Agent2"
        )
        
        triggered = generator.get_triggered_honeytokens()
        
        assert len(triggered) == 2
        assert honeytokens[0] in triggered
        assert honeytokens[2] in triggered
        assert honeytokens[1] not in triggered


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfiguration:
    """Tests for system configuration and constants."""
    
    def test_predefined_lists_populated(self):
        """Test that predefined lists are properly populated."""
        assert len(FIRST_NAMES_MALE) >= 10
        assert len(FIRST_NAMES_FEMALE) >= 10
        assert len(LAST_NAMES) >= 10
        assert len(VACANT_COMMERCIAL_ADDRESSES) == 5
        assert len(COMMON_MEDICAL_CONDITIONS) == 10
        assert len(COMMON_MEDICATIONS) == 10
        assert len(COMMON_ALLERGIES) == 7
    
    def test_constants_correct_values(self):
        """Test that critical constants have correct values."""
        assert FCC_FICTION_PHONE_PREFIX == "555-01"
        assert NON_ROUTABLE_EMAIL_DOMAIN == "honeytoken-tracker.internal"
        assert MRN_HONEYTOKEN_PREFIX == "MRN-"
        assert MRN_RANGE_MIN == 900000
        assert MRN_RANGE_MAX == 999999


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataclasses:
    """Tests for dataclass functionality."""
    
    def test_legal_honeytoken_to_dict(self, sample_honeytoken):
        """Test LegalHoneytoken.to_dict() conversion."""
        data = sample_honeytoken.to_dict()
        
        assert isinstance(data, dict)
        assert data["honeytoken_id"] == sample_honeytoken.honeytoken_id
        assert data["mrn"] == sample_honeytoken.mrn
        assert data["name"] == sample_honeytoken.name
        assert isinstance(data["deployment_timestamp"], str)  # ISO format
    
    def test_legal_honeytoken_to_json(self, sample_honeytoken):
        """Test LegalHoneytoken.to_json() conversion."""
        json_str = sample_honeytoken.to_json()
        
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["honeytoken_id"] == sample_honeytoken.honeytoken_id
    
    def test_attacker_fingerprint_to_dict(self, sample_attacker_data):
        """Test AttackerFingerprint.to_dict() conversion."""
        fingerprint = AttackerFingerprint(
            fingerprint_id="fp_test",
            honeytoken_id="ht_test",
            ip_address=sample_attacker_data["ip_address"],
            user_agent=sample_attacker_data["user_agent"]
        )
        
        data = fingerprint.to_dict()
        
        assert isinstance(data, dict)
        assert data["fingerprint_id"] == "fp_test"
        assert data["ip_address"] == sample_attacker_data["ip_address"]


# ═══════════════════════════════════════════════════════════════════════════════
# ENUM TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnums:
    """Tests for enum definitions."""
    
    def test_attack_type_enum_values(self):
        """Test AttackType enum has expected values."""
        expected_types = [
            "prompt_injection",
            "data_exfiltration",
            "unauthorized_access",
            "privilege_escalation",
            "brute_force",
            "sql_injection",
            "api_abuse",
            "reconnaissance"
        ]
        
        for expected in expected_types:
            assert any(at.value == expected for at in AttackType)
    
    def test_honeytoken_status_enum_values(self):
        """Test HoneytokenStatus enum has expected values."""
        assert HoneytokenStatus.ACTIVE.value == "active"
        assert HoneytokenStatus.TRIGGERED.value == "triggered"
        assert HoneytokenStatus.EXPIRED.value == "expired"
        assert HoneytokenStatus.DISABLED.value == "disabled"
    
    def test_compliance_check_enum_values(self):
        """Test ComplianceCheck enum has expected values."""
        assert ComplianceCheck.NO_SSN.value == "no_ssn"
        assert ComplianceCheck.MRN_HOSPITAL_INTERNAL.value == "mrn_hospital_internal"
        assert ComplianceCheck.PHONE_FCC_RESERVED.value == "phone_fcc_reserved"
        assert ComplianceCheck.EMAIL_NON_ROUTABLE.value == "email_non_routable"
        assert ComplianceCheck.ADDRESS_VACANT.value == "address_vacant"
        assert ComplianceCheck.FULLY_COMPLIANT.value == "fully_compliant"


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecurity:
    """Tests for security properties."""
    
    def test_beacon_payload_not_readable_without_decode(self, beacon):
        """Test that beacon payload is obfuscated."""
        payload = beacon.generate_beacon_payload("ht_test")
        
        # Should NOT contain readable honeytoken_id
        assert "ht_test" not in payload
        
        # Should be Base64
        try:
            decoded = base64.b64decode(payload.encode())
            assert decoded  # Successfully decoded
        except Exception:
            pytest.fail("Payload is not valid Base64")
    
    def test_fingerprint_hash_deterministic(self):
        """Test that fingerprint hash is deterministic for same data."""
        fingerprint1 = AttackerFingerprint(
            fingerprint_id="fp_1",
            honeytoken_id="ht_1",
            ip_address="1.2.3.4",
            user_agent="TestAgent",
            platform="TestPlatform",
            screen_resolution="1920x1080"
        )
        
        fingerprint2 = AttackerFingerprint(
            fingerprint_id="fp_2",  # Different ID
            honeytoken_id="ht_2",  # Different honeytoken
            ip_address="1.2.3.4",  # Same browser data
            user_agent="TestAgent",
            platform="TestPlatform",
            screen_resolution="1920x1080"
        )
        
        # Hash based on browser fingerprint data, not IDs
        hash1 = fingerprint1.compute_hash()
        hash2 = fingerprint2.compute_hash()
        
        # Same browser = same hash
        assert hash1 == hash2
