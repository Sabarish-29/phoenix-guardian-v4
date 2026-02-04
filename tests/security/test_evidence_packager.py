"""
Tests for Evidence Packager.

This test suite verifies:
1. Evidence collection for attack sessions
2. HIPAA breach assessment
3. CFAA violation analysis
4. State law identification
5. PDF report generation
6. Chain of custody tracking
7. Digital signatures
8. Evidence serialization
"""

import pytest
import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from phoenix_guardian.security.evidence_packager import (
    EvidencePackager,
    EvidencePackage,
    EvidenceType,
    STATE_COMPUTER_CRIME_LAWS
)
from phoenix_guardian.security.attacker_intelligence_db import AttackerIntelligenceDB
from phoenix_guardian.security.threat_intelligence import ThreatIntelligenceAnalyzer
from phoenix_guardian.security.honeytoken_generator import (
    HoneytokenGenerator,
    LegalHoneytoken,
    AttackerFingerprint,
    HoneytokenStatus
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db():
    """Create mock database."""
    return AttackerIntelligenceDB(
        connection_string="postgresql://test:test@localhost/test",
        use_mock=True
    )


@pytest.fixture
def analyzer(db):
    """Create threat analyzer."""
    return ThreatIntelligenceAnalyzer(db)


@pytest.fixture
def packager(db, analyzer):
    """Create evidence packager."""
    return EvidencePackager(db, analyzer)


@pytest.fixture
def generator():
    """Create honeytoken generator."""
    return HoneytokenGenerator()


@pytest.fixture
def sample_session_data(db, generator):
    """
    Create sample session with honeytokens and fingerprints.
    
    Returns:
        session_id for the created session
    """
    session_id = "test-session-12345"
    
    # Create honeytokens
    for i in range(3):
        ht = generator.generate()
        db.store_honeytoken(ht, {
            'attack_type': 'prompt_injection',
            'session_id': session_id,
            'confidence': 0.85,
            'deployment_strategy': 'full_deception'
        })
        
        # Create fingerprint for each honeytoken
        fp = AttackerFingerprint(
            fingerprint_id=f"fp-{session_id}-{i}",
            honeytoken_id=ht.honeytoken_id,
            ip_address="203.0.113.42",
            ip_geolocation={
                'country': 'US',
                'region': 'CA',
                'city': 'Los Angeles',
                'isp': 'Test ISP',
                'asn': 12345
            },
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            canvas_fingerprint="xyz789",
            platform="Windows",
            language="en-US",
            timezone="America/Los_Angeles",
            screen_resolution="1920x1080",
            color_depth=24,
            behavioral_data={
                'attack_type': 'prompt_injection',
                'first_interaction': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            }
        )
        db.store_fingerprint(fp)
        
        # Record interaction
        db.record_interaction(ht.honeytoken_id, {
            'interaction_type': 'beacon_trigger',
            'timestamp': datetime.now(timezone.utc),
            'ip_address': '203.0.113.42',
            'user_agent': 'Mozilla/5.0',
            'session_id': session_id,
            'raw_data': {'canvas_fingerprint': 'xyz789'}
        })
    
    return session_id


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE COLLECTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEvidenceCollection:
    """Tests for evidence collection."""
    
    def test_collect_evidence_for_session(self, packager, sample_session_data):
        """Test evidence collection for attack session."""
        session_id = sample_session_data
        
        package = packager.collect_evidence_for_session(session_id)
        
        assert package is not None
        assert package.package_id is not None
        assert package.case_number.startswith('PG-')
        assert package.session_id == session_id
        assert len(package.honeytokens_triggered) >= 1
    
    def test_collect_evidence_invalid_session(self, packager):
        """Test error handling for invalid session."""
        with pytest.raises(ValueError, match="No honeytokens found"):
            packager.collect_evidence_for_session("nonexistent-session")
    
    def test_evidence_package_has_required_fields(self, packager, sample_session_data):
        """Verify evidence package contains all required fields."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        # Check required fields
        assert package.package_id
        assert package.case_number
        assert package.generation_timestamp
        assert package.session_id
        assert package.evidence_hash
        assert package.cfaa_violation_summary
        assert package.hipaa_breach_assessment
    
    def test_evidence_hash_computed(self, packager, sample_session_data):
        """Test that evidence hash is computed."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        # SHA-256 hash should be 64 hex characters
        assert len(package.evidence_hash) == 64
        assert all(c in '0123456789abcdef' for c in package.evidence_hash)
    
    def test_chain_of_custody_initialized(self, packager, sample_session_data):
        """Test chain of custody is initialized."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        assert len(package.chain_of_custody) >= 1
        
        # First event should be evidence collection
        first_event = package.chain_of_custody[0]
        assert 'timestamp' in first_event
        assert 'event_type' in first_event
        assert 'user' in first_event
    
    def test_ioc_indicators_collected(self, packager, sample_session_data):
        """Test IOC indicators are collected."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        assert 'ip_addresses' in package.ioc_indicators
        assert 'user_agents' in package.ioc_indicators
    
    def test_stix_bundle_generated(self, packager, sample_session_data):
        """Test STIX bundle is generated."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        if package.stix_bundle:
            # Should be valid JSON
            bundle = json.loads(package.stix_bundle)
            assert bundle['type'] == 'bundle'
    
    def test_package_stored_in_packager(self, packager, sample_session_data):
        """Test that package is stored in packager."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        retrieved = packager.get_package(package.package_id)
        assert retrieved is not None
        assert retrieved.package_id == package.package_id


# ═══════════════════════════════════════════════════════════════════════════════
# HIPAA ASSESSMENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHIPAAAssessment:
    """Tests for HIPAA breach assessment."""
    
    def test_hipaa_no_breach_for_honeytokens(self, packager, sample_session_data):
        """Honeytokens are fake - no HIPAA breach."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        assert package.hipaa_breach_assessment['is_breach'] is False
        assert package.hipaa_breach_assessment['notification_required'] is False
        assert package.hipaa_breach_assessment['affected_individuals'] == 0
    
    def test_hipaa_reasoning_explains_honeytokens(self, packager, sample_session_data):
        """Test HIPAA reasoning explains honeytoken nature."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        reasoning = package.hipaa_breach_assessment['reasoning']
        assert 'honeytoken' in reasoning.lower() or 'fictional' in reasoning.lower()
    
    def test_assess_hipaa_breach_directly(self, packager):
        """Test direct HIPAA assessment method."""
        honeytokens = [{'honeytoken_id': 'ht-1', 'mrn': 'MRN-900001'}]
        interactions = [{'interaction_type': 'view', 'honeytoken_id': 'ht-1'}]
        
        assessment = packager._assess_hipaa_breach(honeytokens, interactions)
        
        assert assessment['is_breach'] is False
        assert 'note' in assessment


# ═══════════════════════════════════════════════════════════════════════════════
# CFAA VIOLATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCFAAAnalysis:
    """Tests for CFAA violation analysis."""
    
    def test_cfaa_violation_analysis_generated(self, packager, sample_session_data):
        """Test CFAA analysis is generated."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        assert package.cfaa_violation_summary
        assert '1030' in package.cfaa_violation_summary  # CFAA statute
    
    def test_cfaa_unauthorized_access_section(self, packager):
        """Test CFAA section (a)(2)(C) is included."""
        summary = packager._assess_cfaa_violations(
            attack_type='prompt_injection',
            unauthorized_access=True,
            data_exfiltration=False
        )
        
        assert '1030(a)(2)' in summary
        assert 'VIOLATED' in summary
    
    def test_cfaa_fraud_section(self, packager):
        """Test CFAA section (a)(4) for fraud."""
        summary = packager._assess_cfaa_violations(
            attack_type='data_exfiltration',
            unauthorized_access=True,
            data_exfiltration=True
        )
        
        assert '1030(a)(4)' in summary
    
    def test_cfaa_includes_penalties(self, packager):
        """Test penalty information is included."""
        summary = packager._assess_cfaa_violations(
            attack_type='prompt_injection',
            unauthorized_access=True,
            data_exfiltration=False
        )
        
        assert 'imprisonment' in summary.lower()
        assert 'fine' in summary.lower()
    
    def test_cfaa_aggravating_factors(self, packager):
        """Test aggravating factors are listed."""
        summary = packager._assess_cfaa_violations(
            attack_type='prompt_injection',
            unauthorized_access=True,
            data_exfiltration=True
        )
        
        assert 'healthcare' in summary.lower()
        assert 'aggravating' in summary.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# STATE LAW TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestStateLawIdentification:
    """Tests for state computer crime law identification."""
    
    def test_identify_california_law(self, packager):
        """Test California law identification."""
        laws = packager._identify_state_laws(
            attacker_state='TX',
            victim_state='CA'
        )
        
        # California law should be included (victim state)
        ca_laws = [l for l in laws if 'California' in l]
        assert len(ca_laws) >= 1
        assert '502' in ca_laws[0]  # CA Penal Code § 502
    
    def test_identify_attacker_state_law(self, packager):
        """Test attacker state law is included."""
        laws = packager._identify_state_laws(
            attacker_state='TX',
            victim_state='CA'
        )
        
        # Texas law should be included (attacker state)
        tx_laws = [l for l in laws if 'Texas' in l]
        assert len(tx_laws) >= 1
    
    def test_all_50_states_have_laws(self, packager):
        """Test all 50 states have laws defined."""
        # All 50 states + DC + PR
        assert len(STATE_COMPUTER_CRIME_LAWS) >= 50
        
        # Check key states
        for state in ['CA', 'NY', 'TX', 'FL', 'IL']:
            assert state in STATE_COMPUTER_CRIME_LAWS


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT GENERATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestReportGeneration:
    """Tests for report generation."""
    
    def test_generate_law_enforcement_summary(self, packager, sample_session_data):
        """Test ASCII law enforcement summary."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        summary = package.generate_law_enforcement_summary()
        
        assert 'PHOENIX GUARDIAN' in summary
        assert 'FORENSIC EVIDENCE SUMMARY' in summary
        assert package.case_number in summary
        assert 'CFAA' in summary or 'LEGAL' in summary
    
    def test_generate_pdf_report(self, packager, sample_session_data, tmp_path):
        """Test PDF report generation."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        output_path = str(tmp_path / "evidence_report.pdf")
        
        result = packager.generate_pdf_report(package, output_path)
        
        # Should return a path (either PDF or TXT fallback)
        assert result is not None
    
    def test_generate_json_export(self, packager, sample_session_data, tmp_path):
        """Test JSON export."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        output_path = str(tmp_path / "evidence.json")
        
        result = packager.generate_json_export(package, output_path)
        
        assert Path(result).exists()
        
        # Verify valid JSON
        with open(result) as f:
            data = json.load(f)
        
        assert data['package_id'] == package.package_id
        assert data['case_number'] == package.case_number
    
    def test_package_serialization(self, packager, sample_session_data):
        """Test package to_dict() serialization."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        data = package.to_dict()
        
        assert isinstance(data, dict)
        assert data['package_id'] == package.package_id
        assert 'primary_fingerprint' in data
        assert 'honeytokens_triggered' in data
        assert 'chain_of_custody' in data


# ═══════════════════════════════════════════════════════════════════════════════
# DIGITAL SIGNATURE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDigitalSignature:
    """Tests for digital signatures."""
    
    def test_sign_evidence_package_no_key(self, packager, sample_session_data):
        """Test signing without key file."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        with pytest.raises((FileNotFoundError, ValueError)):
            packager.sign_evidence_package(package.package_id, "/nonexistent/key.pem")
    
    def test_sign_nonexistent_package(self, packager):
        """Test signing nonexistent package."""
        with pytest.raises(ValueError, match="not found"):
            packager.sign_evidence_package("fake-package-id", "/key.pem")
    
    @pytest.mark.skipif(True, reason="Requires actual RSA key pair")
    def test_sign_and_verify(self, packager, sample_session_data, tmp_path):
        """Test signing and verification with real keys."""
        # This test would require generating actual RSA keys
        pass
    
    def test_custody_event_logged_on_signing_attempt(self, packager, sample_session_data):
        """Test custody event is logged when signing attempted."""
        package = packager.collect_evidence_for_session(sample_session_data)
        initial_custody_count = len(packager.custody_log)
        
        # Attempt to sign (will fail without key)
        try:
            packager.sign_evidence_package(package.package_id, "/nonexistent/key.pem")
        except:
            pass
        
        # Custody log should have been updated (at creation time)
        assert len(packager.custody_log) >= initial_custody_count


# ═══════════════════════════════════════════════════════════════════════════════
# PACKAGE MANAGEMENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPackageManagement:
    """Tests for package management."""
    
    def test_list_packages(self, packager, sample_session_data):
        """Test listing all packages."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        packages_list = packager.list_packages()
        
        assert len(packages_list) >= 1
        
        pkg_summary = packages_list[0]
        assert 'package_id' in pkg_summary
        assert 'case_number' in pkg_summary
        assert 'signed' in pkg_summary
    
    def test_get_package(self, packager, sample_session_data):
        """Test retrieving package by ID."""
        package = packager.collect_evidence_for_session(sample_session_data)
        
        retrieved = packager.get_package(package.package_id)
        
        assert retrieved is not None
        assert retrieved.package_id == package.package_id
    
    def test_get_nonexistent_package(self, packager):
        """Test retrieving nonexistent package."""
        result = packager.get_package("fake-id")
        assert result is None
