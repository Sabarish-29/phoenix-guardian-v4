"""
Tests for Attacker Intelligence Database.

This test suite verifies:
1. Honeytoken storage and retrieval
2. Fingerprint storage and queries
3. Interaction recording
4. Threat intelligence queries
5. Legal compliance (no SSN in stored data)
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from phoenix_guardian.security.attacker_intelligence_db import (
    AttackerIntelligenceDB,
    DatabaseError,
    ConnectionError,
    QueryError,
    IntegrityError
)
from phoenix_guardian.security.honeytoken_generator import (
    HoneytokenGenerator,
    LegalHoneytoken,
    AttackerFingerprint,
    SSN_PATTERN
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db():
    """Create a mock database instance for testing."""
    return AttackerIntelligenceDB(
        connection_string="postgresql://test:test@localhost/test",
        use_mock=True
    )


@pytest.fixture
def generator():
    """Create a honeytoken generator."""
    return HoneytokenGenerator()


@pytest.fixture
def sample_honeytoken(generator):
    """Generate a sample honeytoken."""
    return generator.generate(attack_type="prompt_injection")


@pytest.fixture
def sample_fingerprint(sample_honeytoken):
    """Create a sample attacker fingerprint."""
    return AttackerFingerprint(
        fingerprint_id="fp_test_12345",
        honeytoken_id=sample_honeytoken.honeytoken_id,
        ip_address="203.0.113.42",
        ip_geolocation={
            "country": "US",
            "city": "New York",
            "region": "NY",
            "lat": 40.7128,
            "lon": -74.0060,
            "isp": "Test ISP",
            "org": "Test Org",
            "asn": 12345
        },
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0",
        platform="Win32",
        language="en-US",
        screen_resolution="1920x1080",
        color_depth=24,
        timezone="America/New_York",
        canvas_fingerprint="data:image/png;base64,abc123",
        webgl_vendor="Google Inc.",
        webgl_renderer="ANGLE (NVIDIA GeForce GTX 1080)"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HONEYTOKEN STORAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHoneytokenStorage:
    """Tests for honeytoken storage operations."""
    
    def test_store_honeytoken(self, db, sample_honeytoken):
        """Test storing a honeytoken in the database."""
        metadata = {
            'deployment_strategy': 'FULL_DECEPTION',
            'session_id': 'test_session_123'
        }
        
        result = db.store_honeytoken(sample_honeytoken, metadata)
        
        assert result is True
        
        # Verify stored
        stored = db.get_honeytoken(sample_honeytoken.honeytoken_id)
        assert stored is not None
        assert stored['mrn'] == sample_honeytoken.mrn
        assert stored['name'] == sample_honeytoken.name
    
    def test_store_duplicate_honeytoken_returns_false(self, db, sample_honeytoken):
        """Test that storing a duplicate honeytoken returns False."""
        db.store_honeytoken(sample_honeytoken, {})
        
        # Try to store again
        result = db.store_honeytoken(sample_honeytoken, {})
        
        assert result is False
    
    def test_honeytoken_medical_data_stored_correctly(self, db, sample_honeytoken):
        """Test that medical data (conditions, medications, allergies) is stored as JSONB."""
        db.store_honeytoken(sample_honeytoken, {})
        
        stored = db.get_honeytoken(sample_honeytoken.honeytoken_id)
        medical_data = stored['medical_data']
        
        assert 'conditions' in medical_data
        assert 'medications' in medical_data
        assert 'allergies' in medical_data
        assert medical_data['conditions'] == sample_honeytoken.conditions
    
    def test_legal_compliance_no_ssn_in_stored_data(self, db, generator):
        """CRITICAL: Verify NO SSN patterns in stored honeytoken data."""
        # Store 50 honeytokens
        for _ in range(50):
            ht = generator.generate()
            db.store_honeytoken(ht, {})
        
        # Check all stored data for SSN patterns
        for ht_id, ht_data in db._mock_honeytokens.items():
            all_text = json.dumps(ht_data, default=str)
            assert not SSN_PATTERN.search(all_text), (
                f"SSN pattern found in stored honeytoken {ht_id}!"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# FINGERPRINT STORAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFingerprintStorage:
    """Tests for fingerprint storage operations."""
    
    def test_store_fingerprint(self, db, sample_honeytoken, sample_fingerprint):
        """Test storing an attacker fingerprint."""
        # First store the honeytoken
        db.store_honeytoken(sample_honeytoken, {})
        
        result = db.store_fingerprint(sample_fingerprint)
        
        assert result is True
        
        # Verify stored
        stored = db.get_fingerprint(sample_fingerprint.fingerprint_id)
        assert stored is not None
        assert stored['ip_address'] == "203.0.113.42"
        assert stored['ip_country'] == "US"
    
    def test_store_fingerprint_all_fields(self, db, sample_honeytoken, sample_fingerprint):
        """Test that all fingerprint fields are stored correctly."""
        db.store_honeytoken(sample_honeytoken, {})
        db.store_fingerprint(sample_fingerprint)
        
        stored = db.get_fingerprint(sample_fingerprint.fingerprint_id)
        
        assert stored['user_agent'] == sample_fingerprint.user_agent
        assert stored['platform'] == sample_fingerprint.platform
        assert stored['screen_resolution'] == sample_fingerprint.screen_resolution
        assert stored['color_depth'] == sample_fingerprint.color_depth
        assert stored['timezone'] == sample_fingerprint.timezone
        assert stored['webgl_vendor'] == sample_fingerprint.webgl_vendor
    
    def test_get_fingerprint_by_id(self, db, sample_honeytoken, sample_fingerprint):
        """Test retrieving fingerprint by ID."""
        db.store_honeytoken(sample_honeytoken, {})
        db.store_fingerprint(sample_fingerprint)
        
        result = db.get_fingerprint(sample_fingerprint.fingerprint_id)
        
        assert result is not None
        assert result['fingerprint_id'] == sample_fingerprint.fingerprint_id
    
    def test_get_fingerprint_not_found(self, db):
        """Test retrieving non-existent fingerprint returns None."""
        result = db.get_fingerprint("fp_nonexistent")
        assert result is None
    
    def test_get_fingerprints_by_ip(self, db, sample_honeytoken):
        """Test finding all fingerprints from same IP."""
        db.store_honeytoken(sample_honeytoken, {})
        
        # Create multiple fingerprints from same IP
        for i in range(3):
            fp = AttackerFingerprint(
                fingerprint_id=f"fp_same_ip_{i}",
                honeytoken_id=sample_honeytoken.honeytoken_id,
                ip_address="192.168.1.100",
                user_agent=f"Agent {i}"
            )
            db.store_fingerprint(fp)
        
        results = db.get_fingerprints_by_ip("192.168.1.100")
        
        assert len(results) == 3
        assert all(r['ip_address'] == "192.168.1.100" for r in results)
    
    def test_get_fingerprints_by_browser(self, db, sample_honeytoken):
        """Test finding fingerprints by browser fingerprint (VPN hopping detection)."""
        db.store_honeytoken(sample_honeytoken, {})
        
        # Create fingerprints with same browser but different IPs
        browser_fp_hash = "abc123def456"
        
        fp1 = AttackerFingerprint(
            fingerprint_id="fp_browser_1",
            honeytoken_id=sample_honeytoken.honeytoken_id,
            ip_address="203.0.113.1",
            user_agent="Same Browser",
            platform="Win32",
            language="en-US",
            screen_resolution="1920x1080",
            color_depth=24,
            timezone="UTC"
        )
        
        fp2 = AttackerFingerprint(
            fingerprint_id="fp_browser_2",
            honeytoken_id=sample_honeytoken.honeytoken_id,
            ip_address="203.0.113.2",
            user_agent="Same Browser",
            platform="Win32",
            language="en-US",
            screen_resolution="1920x1080",
            color_depth=24,
            timezone="UTC"
        )
        
        db.store_fingerprint(fp1)
        db.store_fingerprint(fp2)
        
        # Both should have same browser fingerprint hash
        browser_hash = fp1.compute_hash()
        results = db.get_fingerprints_by_browser(browser_hash)
        
        assert len(results) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# INTERACTION RECORDING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestInteractionRecording:
    """Tests for honeytoken interaction recording."""
    
    def test_record_interaction(self, db, sample_honeytoken):
        """Test recording a honeytoken interaction."""
        db.store_honeytoken(sample_honeytoken, {})
        
        interaction_data = {
            'interaction_type': 'view',
            'ip_address': '203.0.113.42',
            'user_agent': 'Test Agent',
            'session_id': 'session_123',
            'raw_data': {'key': 'value'}
        }
        
        interaction_id = db.record_interaction(
            sample_honeytoken.honeytoken_id,
            interaction_data
        )
        
        assert interaction_id > 0
    
    def test_beacon_trigger_updates_honeytoken(self, db, sample_honeytoken):
        """Test that beacon trigger updates honeytoken status."""
        db.store_honeytoken(sample_honeytoken, {})
        
        # Initially not triggered
        stored = db.get_honeytoken(sample_honeytoken.honeytoken_id)
        assert stored['beacon_triggered'] is False
        assert stored['trigger_count'] == 0
        
        # Record interaction
        db.record_interaction(
            sample_honeytoken.honeytoken_id,
            {'interaction_type': 'beacon_trigger'}
        )
        
        # Check trigger status updated
        stored = db.get_honeytoken(sample_honeytoken.honeytoken_id)
        assert stored['beacon_triggered'] is True
        assert stored['trigger_count'] == 1
    
    def test_multiple_interactions_increment_count(self, db, sample_honeytoken):
        """Test that multiple interactions increment trigger count."""
        db.store_honeytoken(sample_honeytoken, {})
        
        for i in range(5):
            db.record_interaction(
                sample_honeytoken.honeytoken_id,
                {'interaction_type': 'view'}
            )
        
        stored = db.get_honeytoken(sample_honeytoken.honeytoken_id)
        assert stored['trigger_count'] == 5


# ═══════════════════════════════════════════════════════════════════════════════
# THREAT INTELLIGENCE QUERY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestThreatIntelligenceQueries:
    """Tests for threat intelligence queries."""
    
    def test_find_repeat_attackers(self, db, sample_honeytoken):
        """Test finding repeat attackers (same IP, multiple attempts)."""
        db.store_honeytoken(sample_honeytoken, {})
        
        # Create multiple fingerprints from same IP
        repeat_ip = "198.51.100.42"
        for i in range(3):
            fp = AttackerFingerprint(
                fingerprint_id=f"fp_repeat_{i}",
                honeytoken_id=sample_honeytoken.honeytoken_id,
                ip_address=repeat_ip,
                user_agent=f"Agent {i}"
            )
            db.store_fingerprint(fp)
        
        # Create unique IP fingerprint
        fp_unique = AttackerFingerprint(
            fingerprint_id="fp_unique",
            honeytoken_id=sample_honeytoken.honeytoken_id,
            ip_address="10.0.0.1",
            user_agent="Unique Agent"
        )
        db.store_fingerprint(fp_unique)
        
        results = db.find_repeat_attackers(time_window_days=30)
        
        assert len(results) == 1
        assert results[0]['ip_address'] == repeat_ip
        assert results[0]['attempt_count'] == 3
    
    def test_get_attack_patterns_by_country(self, db, sample_honeytoken):
        """Test geographic attack distribution."""
        db.store_honeytoken(sample_honeytoken, {})
        
        # Create fingerprints from different countries
        countries = [("US", 5), ("CN", 3), ("RU", 2)]
        fp_id = 0
        
        for country, count in countries:
            for i in range(count):
                fp = AttackerFingerprint(
                    fingerprint_id=f"fp_country_{fp_id}",
                    honeytoken_id=sample_honeytoken.honeytoken_id,
                    ip_address=f"192.168.{fp_id}.1",
                    ip_geolocation={"country": country}
                )
                db.store_fingerprint(fp)
                fp_id += 1
        
        results = db.get_attack_patterns_by_country()
        
        assert results.get("US") == 5
        assert results.get("CN") == 3
        assert results.get("RU") == 2
    
    def test_get_most_common_attack_types(self, db, sample_honeytoken):
        """Test attack type ranking."""
        db.store_honeytoken(sample_honeytoken, {})
        
        # Create fingerprints with different attack types
        attack_types = [
            ("prompt_injection", 5),
            ("data_exfiltration", 3),
            ("jailbreak", 2)
        ]
        fp_id = 0
        
        for attack_type, count in attack_types:
            for i in range(count):
                fp = AttackerFingerprint(
                    fingerprint_id=f"fp_attack_{fp_id}",
                    honeytoken_id=sample_honeytoken.honeytoken_id,
                    ip_address=f"10.0.{fp_id}.1"
                )
                db.store_fingerprint(fp)
                # Manually set attack type in mock
                db._mock_fingerprints[f"fp_attack_{fp_id}"]['attack_type'] = attack_type
                fp_id += 1
        
        results = db.get_most_common_attack_types()
        
        assert results[0] == ("prompt_injection", 5)
        assert results[1] == ("data_exfiltration", 3)
        assert results[2] == ("jailbreak", 2)
    
    def test_generate_threat_intelligence_report(self, db, sample_honeytoken, sample_fingerprint):
        """Test threat intelligence report generation."""
        db.store_honeytoken(sample_honeytoken, {})
        db.store_fingerprint(sample_fingerprint)
        
        # Set attack type for reporting
        db._mock_fingerprints[sample_fingerprint.fingerprint_id]['attack_type'] = 'prompt_injection'
        
        report = db.generate_threat_intelligence_report(days=7)
        
        assert "THREAT INTELLIGENCE REPORT" in report
        assert "Total Attacks" in report
        assert "Unique IP Addresses" in report


# ═══════════════════════════════════════════════════════════════════════════════
# THREAT SCORE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestThreatScore:
    """Tests for threat score management."""
    
    def test_update_threat_score(self, db, sample_honeytoken, sample_fingerprint):
        """Test updating threat score for a fingerprint."""
        db.store_honeytoken(sample_honeytoken, {})
        db.store_fingerprint(sample_fingerprint)
        
        result = db.update_threat_score(sample_fingerprint.fingerprint_id, 75)
        
        assert result is True
        
        stored = db.get_fingerprint(sample_fingerprint.fingerprint_id)
        assert stored['threat_score'] == 75
    
    def test_threat_score_capped_at_100(self, db, sample_honeytoken, sample_fingerprint):
        """Test that threat score is capped at 100."""
        db.store_honeytoken(sample_honeytoken, {})
        db.store_fingerprint(sample_fingerprint)
        
        db.update_threat_score(sample_fingerprint.fingerprint_id, 150)
        
        stored = db.get_fingerprint(sample_fingerprint.fingerprint_id)
        assert stored['threat_score'] == 100


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDatabaseConnection:
    """Tests for database connection handling."""
    
    def test_mock_mode_works(self, db):
        """Test that mock mode works without real database."""
        assert db.use_mock is True
        
        # Should not raise
        with db.get_connection() as conn:
            pass
    
    def test_close_database(self, db):
        """Test closing database connections."""
        db.close()
        # Should not raise in mock mode


# ═══════════════════════════════════════════════════════════════════════════════
# CONCURRENT ACCESS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestConcurrentAccess:
    """Tests for thread safety and concurrent access."""
    
    def test_concurrent_writes(self, db, generator):
        """Test that concurrent writes work correctly."""
        import threading
        
        errors = []
        
        def store_honeytoken(thread_id):
            try:
                ht = generator.generate()
                db.store_honeytoken(ht, {'thread_id': thread_id})
            except Exception as e:
                errors.append(e)
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=store_honeytoken, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(db._mock_honeytokens) == 10
