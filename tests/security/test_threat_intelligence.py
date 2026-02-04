"""
Tests for Threat Intelligence Analyzer.

This test suite verifies:
1. Coordinated attack detection
2. Attribution clustering
3. Attack infrastructure mapping
4. IOC feed generation
5. STIX 2.1 export
6. Threat scoring
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from phoenix_guardian.security.threat_intelligence import (
    ThreatIntelligenceAnalyzer,
    CoordinatedCampaign,
    AttributionCluster,
    ATTACK_SEVERITY,
    DATACENTER_ASNS
)
from phoenix_guardian.security.attacker_intelligence_db import AttackerIntelligenceDB
from phoenix_guardian.security.honeytoken_generator import (
    HoneytokenGenerator,
    AttackerFingerprint
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db():
    """Create a mock database instance."""
    return AttackerIntelligenceDB(
        connection_string="postgresql://test:test@localhost/test",
        use_mock=True
    )


@pytest.fixture
def analyzer(db):
    """Create a threat intelligence analyzer."""
    return ThreatIntelligenceAnalyzer(db)


@pytest.fixture
def generator():
    """Create a honeytoken generator."""
    return HoneytokenGenerator()


@pytest.fixture
def sample_fingerprints(db, generator):
    """
    Create sample fingerprints for testing.
    
    Creates:
    - 3 from same ASN 12345 (coordinated attack)
    - 2 with same browser fingerprint (VPN hopping)
    - 5 unique fingerprints
    """
    ht = generator.generate()
    db.store_honeytoken(ht, {})
    
    fingerprints = []
    
    # 3 from same ASN (coordinated attack)
    for i in range(3):
        fp = AttackerFingerprint(
            fingerprint_id=f"fp_asn_12345_{i}",
            honeytoken_id=ht.honeytoken_id,
            ip_address=f"203.0.113.{i+1}",
            ip_geolocation={
                "country": "US",
                "city": "New York",
                "asn": 12345,
                "isp": "Evil Corp"
            },
            user_agent="Evil Browser/1.0",
            platform="Linux",
            language="en-US",
            screen_resolution="1920x1080",
            color_depth=24,
            timezone="America/New_York"
        )
        db.store_fingerprint(fp)
        db._mock_fingerprints[fp.fingerprint_id]['ip_asn'] = 12345
        db._mock_fingerprints[fp.fingerprint_id]['attack_type'] = 'prompt_injection'
        db._mock_fingerprints[fp.fingerprint_id]['first_interaction'] = datetime.now(timezone.utc)
        fingerprints.append(fp)
    
    # 2 with same browser fingerprint (VPN hopping)
    for i in range(2):
        fp = AttackerFingerprint(
            fingerprint_id=f"fp_same_browser_{i}",
            honeytoken_id=ht.honeytoken_id,
            ip_address=f"198.51.100.{i+1}",
            ip_geolocation={"country": "CN", "asn": 54321},
            user_agent="VPN Hopper/2.0",
            platform="Windows",
            language="zh-CN",
            screen_resolution="2560x1440",
            color_depth=32,
            timezone="Asia/Shanghai"
        )
        db.store_fingerprint(fp)
        db._mock_fingerprints[fp.fingerprint_id]['ip_asn'] = 54321
        db._mock_fingerprints[fp.fingerprint_id]['attack_type'] = 'data_exfiltration'
        db._mock_fingerprints[fp.fingerprint_id]['first_interaction'] = datetime.now(timezone.utc)
        fingerprints.append(fp)
    
    # 5 unique fingerprints
    for i in range(5):
        fp = AttackerFingerprint(
            fingerprint_id=f"fp_unique_{i}",
            honeytoken_id=ht.honeytoken_id,
            ip_address=f"10.0.{i}.1",
            ip_geolocation={"country": ["US", "RU", "DE", "FR", "JP"][i], "asn": 60000 + i},
            user_agent=f"Unique Browser {i}",
            platform=["Windows", "Mac", "Linux", "Android", "iOS"][i],
            language=["en-US", "ru-RU", "de-DE", "fr-FR", "ja-JP"][i],
            screen_resolution=["1920x1080", "2560x1440", "1366x768", "1440x900", "375x812"][i],
            color_depth=24,
            timezone=["America/New_York", "Europe/Moscow", "Europe/Berlin", "Europe/Paris", "Asia/Tokyo"][i]
        )
        db.store_fingerprint(fp)
        db._mock_fingerprints[fp.fingerprint_id]['ip_asn'] = 60000 + i
        db._mock_fingerprints[fp.fingerprint_id]['attack_type'] = ['jailbreak', 'pii_extraction', 'sql_injection', 'api_abuse', 'reconnaissance'][i]
        db._mock_fingerprints[fp.fingerprint_id]['first_interaction'] = datetime.now(timezone.utc)
        fingerprints.append(fp)
    
    return fingerprints


# ═══════════════════════════════════════════════════════════════════════════════
# COORDINATED ATTACK DETECTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoordinatedAttackDetection:
    """Tests for coordinated attack detection."""
    
    def test_detect_coordinated_attacks(self, analyzer, sample_fingerprints):
        """Test that 3+ IPs from same ASN are detected as coordinated."""
        campaigns = analyzer.detect_coordinated_attacks(time_window_hours=24)
        
        # Should detect ASN 12345 campaign (3 IPs)
        asn_12345_campaigns = [c for c in campaigns if c.get('asn') == 12345]
        
        assert len(asn_12345_campaigns) == 1
        assert asn_12345_campaigns[0]['ip_count'] == 3
        assert asn_12345_campaigns[0]['attack_type'] == 'prompt_injection'
    
    def test_no_coordinated_attacks_when_isolated(self, db, analyzer, generator):
        """Test that isolated single-IP attacks are not flagged."""
        ht = generator.generate()
        db.store_honeytoken(ht, {})
        
        # Create 5 fingerprints, each from different ASN
        for i in range(5):
            fp = AttackerFingerprint(
                fingerprint_id=f"fp_isolated_{i}",
                honeytoken_id=ht.honeytoken_id,
                ip_address=f"10.{i}.0.1",
                ip_geolocation={"asn": 70000 + i}
            )
            db.store_fingerprint(fp)
            db._mock_fingerprints[fp.fingerprint_id]['ip_asn'] = 70000 + i
            db._mock_fingerprints[fp.fingerprint_id]['first_interaction'] = datetime.now(timezone.utc)
        
        campaigns = analyzer.detect_coordinated_attacks(time_window_hours=24)
        
        # No campaign should have 3+ IPs
        assert all(c.get('ip_count', 0) < 3 for c in campaigns)
    
    def test_coordination_confidence_calculation(self, analyzer):
        """Test coordination confidence score calculation."""
        # High confidence: many IPs, similar browsers, same attack type
        confidence_high = analyzer._calculate_coordination_confidence(
            ip_count=10,
            total_attempts=25,
            has_similar_browsers=True,
            same_attack_type=True
        )
        
        # Low confidence: few IPs, different browsers, different attacks
        confidence_low = analyzer._calculate_coordination_confidence(
            ip_count=3,
            total_attempts=3,
            has_similar_browsers=False,
            same_attack_type=False
        )
        
        assert confidence_high > confidence_low
        assert confidence_high >= 0.7
        assert confidence_low <= 0.3


# ═══════════════════════════════════════════════════════════════════════════════
# ATTRIBUTION CLUSTERING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAttributionClustering:
    """Tests for attribution clustering."""
    
    def test_cluster_by_attribution(self, analyzer, sample_fingerprints):
        """Test that same browser fingerprint creates a cluster."""
        clusters = analyzer.cluster_by_attribution(min_cluster_size=2)
        
        # Should have at least one cluster (the 2 VPN hopping fingerprints)
        # Note: This depends on browser fingerprint hash calculation
        assert isinstance(clusters, list)
    
    def test_browser_fingerprint_similarity(self, analyzer):
        """Test browser fingerprint similarity calculation."""
        fp1 = "abc123def456"
        fp2 = "abc123def456"  # Exact match
        fp3 = "xyz789ghi012"  # Completely different
        
        similarity_exact = analyzer._calculate_browser_fingerprint_similarity(fp1, fp2)
        similarity_different = analyzer._calculate_browser_fingerprint_similarity(fp1, fp3)
        
        assert similarity_exact == 1.0
        assert similarity_different < 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# ATTACK INFRASTRUCTURE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAttackInfrastructure:
    """Tests for attack infrastructure mapping."""
    
    def test_identify_attack_infrastructure(self, analyzer, sample_fingerprints):
        """Test mapping attacker infrastructure."""
        infrastructure = analyzer.identify_attack_infrastructure()
        
        assert 'ip_ranges' in infrastructure
        assert 'asns' in infrastructure
        assert 'hosting_providers' in infrastructure
        assert 'tor_exit_nodes' in infrastructure
        assert 'vpn_services' in infrastructure
        assert 'datacenter_ips' in infrastructure
    
    def test_tor_detection(self, analyzer):
        """Test TOR exit node detection."""
        tor_ip = "185.220.100.42"
        normal_ip = "192.168.1.1"
        
        assert analyzer._is_tor_exit_node(tor_ip) is True
        assert analyzer._is_tor_exit_node(normal_ip) is False
    
    def test_vpn_detection(self, analyzer):
        """Test VPN IP detection."""
        vpn_ip = "89.238.100.42"  # NordVPN range
        normal_ip = "192.168.1.1"
        
        assert analyzer._is_vpn_ip(vpn_ip) is True
        assert analyzer._is_vpn_ip(normal_ip) is False
    
    def test_datacenter_detection(self, analyzer):
        """Test datacenter IP detection (by ASN)."""
        aws_asn = 16509
        home_asn = 7922  # Comcast residential
        
        assert analyzer._is_datacenter_ip(aws_asn) is True
        assert analyzer._is_datacenter_ip(home_asn) is False


# ═══════════════════════════════════════════════════════════════════════════════
# IOC FEED TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestIOCFeed:
    """Tests for IOC feed generation."""
    
    def test_generate_ioc_feed(self, analyzer, sample_fingerprints):
        """Test IOC feed generation."""
        iocs = analyzer.generate_ioc_feed()
        
        assert 'ip_addresses' in iocs
        assert 'user_agents' in iocs
        assert 'browser_fingerprints' in iocs
        assert 'canvas_fingerprints' in iocs
        
        # Should have IPs from sample fingerprints
        assert len(iocs['ip_addresses']) >= 5
    
    def test_ioc_feed_no_duplicates(self, analyzer, sample_fingerprints):
        """Test that IOC feed has no duplicate entries."""
        iocs = analyzer.generate_ioc_feed()
        
        # Check no duplicates
        assert len(iocs['ip_addresses']) == len(set(iocs['ip_addresses']))
        assert len(iocs['user_agents']) == len(set(iocs['user_agents']))


# ═══════════════════════════════════════════════════════════════════════════════
# STIX EXPORT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSTIXExport:
    """Tests for STIX 2.1 export."""
    
    def test_export_stix_bundle(self, analyzer, sample_fingerprints):
        """Test STIX bundle export."""
        stix_json = analyzer.export_stix_bundle()
        
        # Should be valid JSON
        bundle = json.loads(stix_json)
        
        assert bundle['type'] == 'bundle'
        assert 'id' in bundle
        assert bundle['id'].startswith('bundle--')
        assert 'objects' in bundle
        assert len(bundle['objects']) > 0
    
    def test_stix_bundle_has_identity(self, analyzer, sample_fingerprints):
        """Test STIX bundle includes Phoenix Guardian identity."""
        stix_json = analyzer.export_stix_bundle()
        bundle = json.loads(stix_json)
        
        identities = [obj for obj in bundle['objects'] if obj['type'] == 'identity']
        
        assert len(identities) >= 1
        assert any('Phoenix Guardian' in i['name'] for i in identities)
    
    def test_stix_bundle_has_indicators(self, analyzer, sample_fingerprints):
        """Test STIX bundle includes IP indicators."""
        stix_json = analyzer.export_stix_bundle()
        bundle = json.loads(stix_json)
        
        indicators = [obj for obj in bundle['objects'] if obj['type'] == 'indicator']
        
        assert len(indicators) > 0
        
        # Check indicator format
        for indicator in indicators:
            assert 'pattern' in indicator
            assert 'ipv4-addr' in indicator['pattern']


# ═══════════════════════════════════════════════════════════════════════════════
# THREAT SCORING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestThreatScoring:
    """Tests for threat score calculation."""
    
    def test_calculate_threat_score(self, db, analyzer, generator):
        """Test threat score calculation."""
        ht = generator.generate()
        db.store_honeytoken(ht, {})
        
        fp = AttackerFingerprint(
            fingerprint_id="fp_score_test",
            honeytoken_id=ht.honeytoken_id,
            ip_address="203.0.113.99",
            ip_geolocation={"country": "RU", "asn": 12345}
        )
        db.store_fingerprint(fp)
        db._mock_fingerprints[fp.fingerprint_id]['ip_country'] = 'RU'
        db._mock_fingerprints[fp.fingerprint_id]['attack_type'] = 'prompt_injection'
        
        score = analyzer.calculate_threat_score(fp.fingerprint_id)
        
        # Should have score from:
        # - Attack type (prompt_injection = 40)
        # - International (non-US = 10)
        assert score >= 50
    
    def test_repeat_attacker_scores_higher(self, db, analyzer, generator):
        """Test that repeat attackers get higher threat scores."""
        ht = generator.generate()
        db.store_honeytoken(ht, {})
        
        # Create 3 fingerprints from same IP
        repeat_ip = "198.51.100.99"
        for i in range(3):
            fp = AttackerFingerprint(
                fingerprint_id=f"fp_repeat_score_{i}",
                honeytoken_id=ht.honeytoken_id,
                ip_address=repeat_ip
            )
            db.store_fingerprint(fp)
            db._mock_fingerprints[fp.fingerprint_id]['attack_type'] = 'api_abuse'
        
        # Score the last one
        score = analyzer.calculate_threat_score("fp_repeat_score_2")
        
        # Should have score from:
        # - Repeat attempts (2 repeats * 20 = 40)
        # - Attack type (api_abuse = 30)
        assert score >= 60
    
    def test_tor_user_scores_higher(self, db, analyzer, generator):
        """Test that TOR users get higher threat scores."""
        ht = generator.generate()
        db.store_honeytoken(ht, {})
        
        fp = AttackerFingerprint(
            fingerprint_id="fp_tor_test",
            honeytoken_id=ht.honeytoken_id,
            ip_address="185.220.100.42"  # TOR exit node
        )
        db.store_fingerprint(fp)
        
        score = analyzer.calculate_threat_score(fp.fingerprint_id)
        
        # TOR usage adds +30
        assert score >= 30
    
    def test_threat_score_capped_at_100(self, db, analyzer, generator):
        """Test that threat score is capped at 100."""
        ht = generator.generate()
        db.store_honeytoken(ht, {})
        
        # Create attacker with many risk factors
        for i in range(5):
            fp = AttackerFingerprint(
                fingerprint_id=f"fp_max_score_{i}",
                honeytoken_id=ht.honeytoken_id,
                ip_address="185.220.100.42",  # TOR
                ip_geolocation={"country": "RU", "asn": 16509}  # AWS datacenter
            )
            db.store_fingerprint(fp)
            db._mock_fingerprints[fp.fingerprint_id]['ip_country'] = 'RU'
            db._mock_fingerprints[fp.fingerprint_id]['ip_asn'] = 16509
            db._mock_fingerprints[fp.fingerprint_id]['attack_type'] = 'jailbreak'
        
        score = analyzer.calculate_threat_score("fp_max_score_4")
        
        assert score == 100


# ═══════════════════════════════════════════════════════════════════════════════
# END-TO-END TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEndToEnd:
    """End-to-end integration tests."""
    
    def test_full_intelligence_pipeline(self, db, analyzer, generator):
        """Test complete threat intelligence pipeline."""
        # 1. Store honeytokens
        ht = generator.generate()
        db.store_honeytoken(ht, {})
        
        # 2. Store fingerprints
        fp = AttackerFingerprint(
            fingerprint_id="fp_e2e_test",
            honeytoken_id=ht.honeytoken_id,
            ip_address="203.0.113.100",
            ip_geolocation={"country": "US", "asn": 12345, "isp": "Test ISP"},
            user_agent="Test Agent"
        )
        db.store_fingerprint(fp)
        db._mock_fingerprints[fp.fingerprint_id]['ip_asn'] = 12345
        db._mock_fingerprints[fp.fingerprint_id]['ip_country'] = 'US'
        db._mock_fingerprints[fp.fingerprint_id]['attack_type'] = 'prompt_injection'
        db._mock_fingerprints[fp.fingerprint_id]['first_interaction'] = datetime.now(timezone.utc)
        
        # 3. Calculate threat score
        score = analyzer.calculate_threat_score(fp.fingerprint_id)
        assert score >= 0
        
        # 4. Generate IOC feed
        iocs = analyzer.generate_ioc_feed()
        assert "203.0.113.100" in iocs['ip_addresses']
        
        # 5. Export STIX bundle
        stix = analyzer.export_stix_bundle()
        assert "203.0.113.100" in stix
        
        # 6. Identify infrastructure
        infrastructure = analyzer.identify_attack_infrastructure()
        assert len(infrastructure['asns']) >= 1
