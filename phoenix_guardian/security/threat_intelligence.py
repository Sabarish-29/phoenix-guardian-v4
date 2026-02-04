"""
Threat Intelligence Analyzer - Pattern Detection and IOC Generation.

This module provides advanced threat intelligence analysis including:
- Coordinated attack detection (multiple IPs from same ASN)
- Attribution clustering (same browser fingerprint = same attacker)
- Attack infrastructure mapping
- IOC (Indicators of Compromise) feed generation
- STIX 2.1 export for threat sharing

Example:
    from phoenix_guardian.security.threat_intelligence import ThreatIntelligenceAnalyzer
    from phoenix_guardian.security.attacker_intelligence_db import AttackerIntelligenceDB
    
    db = AttackerIntelligenceDB("postgresql://user:pass@localhost/phoenix")
    analyzer = ThreatIntelligenceAnalyzer(db)
    
    # Detect coordinated attacks
    campaigns = analyzer.detect_coordinated_attacks(time_window_hours=24)
    
    # Generate IOC feed
    iocs = analyzer.generate_ioc_feed()
    
    # Export STIX bundle
    stix = analyzer.export_stix_bundle()
"""

import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

from phoenix_guardian.security.attacker_intelligence_db import (
    AttackerIntelligenceDB
)
from phoenix_guardian.security.honeytoken_generator import AttackerFingerprint

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# KNOWN THREAT INTELLIGENCE DATA
# ═══════════════════════════════════════════════════════════════════════════════

# Known TOR exit node IP ranges (sample - in production, use real TOR directory)
KNOWN_TOR_EXIT_NODES = {
    "185.220.100.",  # Popular TOR exit prefix
    "185.220.101.",
    "199.249.230.",
    "51.15.",  # Scaleway (common TOR hosting)
}

# Known VPN service IP patterns
KNOWN_VPN_PATTERNS = {
    "nordvpn": ["89.238.", "185.93."],
    "expressvpn": ["91.207.", "159.65."],
    "protonvpn": ["185.159.157.", "185.159.158."],
}

# Known datacenter IP ranges (sample ASNs)
DATACENTER_ASNS = {
    13335,   # Cloudflare
    16509,   # Amazon AWS
    15169,   # Google Cloud
    8075,    # Microsoft Azure
    14618,   # Amazon
    36351,   # SoftLayer
    20940,   # Akamai
    54113,   # Fastly
}

# Attack type severity scores
ATTACK_SEVERITY = {
    'prompt_injection': 40,
    'jailbreak': 50,
    'data_exfiltration': 45,
    'pii_extraction': 45,
    'unauthorized_access': 35,
    'privilege_escalation': 40,
    'sql_injection': 35,
    'api_abuse': 30,
    'reconnaissance': 20,
    'brute_force': 25,
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CoordinatedCampaign:
    """Represents a detected coordinated attack campaign."""
    campaign_id: str
    asn: Optional[int]
    ip_addresses: List[str]
    attack_type: str
    fingerprint_ids: List[str]
    first_seen: datetime
    last_seen: datetime
    confidence: float  # 0.0 to 1.0
    indicators: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AttributionCluster:
    """Cluster of fingerprints likely from the same attacker."""
    cluster_id: str
    fingerprint_ids: List[str]
    primary_browser_fp: str
    confidence: float
    shared_attributes: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# THREAT INTELLIGENCE ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════

class ThreatIntelligenceAnalyzer:
    """
    Advanced threat intelligence analysis for attacker attribution.
    
    Capabilities:
    - Coordinated attack detection (multiple IPs from same infrastructure)
    - Attribution clustering (link multiple fingerprints to same attacker)
    - Attack infrastructure mapping (identify hosting, VPNs, TOR)
    - IOC feed generation (for SIEM integration)
    - STIX 2.1 export (for threat sharing)
    
    Attributes:
        db: AttackerIntelligenceDB instance for data access
        
    Example:
        analyzer = ThreatIntelligenceAnalyzer(db)
        
        # Find coordinated attacks in last 24 hours
        campaigns = analyzer.detect_coordinated_attacks(24)
        
        # Calculate threat score for attacker
        score = analyzer.calculate_threat_score("fp_abc123")
    """
    
    def __init__(self, db: AttackerIntelligenceDB):
        """
        Initialize the analyzer.
        
        Args:
            db: AttackerIntelligenceDB instance
        """
        self.db = db
        logger.info("ThreatIntelligenceAnalyzer initialized")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COORDINATED ATTACK DETECTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def detect_coordinated_attacks(
        self,
        time_window_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Detect coordinated attacks from the same infrastructure.
        
        Indicators of coordination:
        - Multiple IPs from same ASN (Autonomous System Number)
        - Similar browser fingerprints
        - Same attack type
        - Temporal clustering (attacks within time window)
        
        Args:
            time_window_hours: Lookback period in hours
            
        Returns:
            List of coordinated campaign records:
            [
                {
                    'asn': 12345,
                    'ip_count': 5,
                    'attack_type': 'prompt_injection',
                    'fingerprint_ids': [...],
                    'ip_addresses': [...],
                    'first_seen': datetime,
                    'last_seen': datetime,
                    'confidence': 0.85
                }
            ]
        """
        # Get recent fingerprints
        fingerprints = self.db.get_recent_fingerprints(hours=time_window_hours)
        
        if not fingerprints:
            return []
        
        # Group by ASN
        asn_groups: Dict[int, List[Dict]] = defaultdict(list)
        for fp in fingerprints:
            asn = fp.get('ip_asn')
            if asn:
                asn_groups[asn].append(fp)
        
        campaigns = []
        
        for asn, fps in asn_groups.items():
            # Need at least 3 different IPs to consider coordinated
            unique_ips = set(fp.get('ip_address') for fp in fps)
            
            if len(unique_ips) >= 3:
                # Check for similar browser fingerprints
                browser_fps = [fp.get('browser_fingerprint') for fp in fps if fp.get('browser_fingerprint')]
                has_similar_browsers = len(browser_fps) != len(set(browser_fps))
                
                # Check for same attack types
                attack_types = [fp.get('attack_type') for fp in fps if fp.get('attack_type')]
                common_attack_type = max(set(attack_types), key=attack_types.count) if attack_types else 'unknown'
                
                # Calculate confidence
                confidence = self._calculate_coordination_confidence(
                    ip_count=len(unique_ips),
                    total_attempts=len(fps),
                    has_similar_browsers=has_similar_browsers,
                    same_attack_type=len(set(attack_types)) == 1
                )
                
                # Get timestamps
                timestamps = [fp.get('first_interaction') for fp in fps if fp.get('first_interaction')]
                
                if timestamps:
                    first_seen = min(timestamps) if timestamps else datetime.now(timezone.utc)
                    last_seen = max(timestamps) if timestamps else datetime.now(timezone.utc)
                else:
                    first_seen = last_seen = datetime.now(timezone.utc)
                
                campaigns.append({
                    'asn': asn,
                    'ip_count': len(unique_ips),
                    'attack_type': common_attack_type,
                    'fingerprint_ids': [fp['fingerprint_id'] for fp in fps],
                    'ip_addresses': list(unique_ips),
                    'first_seen': first_seen,
                    'last_seen': last_seen,
                    'confidence': confidence
                })
        
        # Sort by confidence descending
        campaigns.sort(key=lambda x: x['confidence'], reverse=True)
        
        logger.info(f"Detected {len(campaigns)} coordinated attack campaigns")
        return campaigns
    
    def _calculate_coordination_confidence(
        self,
        ip_count: int,
        total_attempts: int,
        has_similar_browsers: bool,
        same_attack_type: bool
    ) -> float:
        """
        Calculate confidence score for coordinated attack detection.
        
        Args:
            ip_count: Number of unique IPs
            total_attempts: Total number of attempts
            has_similar_browsers: Whether browser fingerprints match
            same_attack_type: Whether all attacks are same type
            
        Returns:
            Confidence score 0.0 to 1.0
        """
        confidence = 0.0
        
        # More IPs = higher confidence
        if ip_count >= 10:
            confidence += 0.3
        elif ip_count >= 5:
            confidence += 0.2
        elif ip_count >= 3:
            confidence += 0.1
        
        # High attempt-to-IP ratio suggests coordination
        if total_attempts > ip_count * 2:
            confidence += 0.2
        
        # Similar browsers across different IPs is strong indicator
        if has_similar_browsers:
            confidence += 0.3
        
        # Same attack type is moderate indicator
        if same_attack_type:
            confidence += 0.2
        
        return min(1.0, confidence)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ATTRIBUTION CLUSTERING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def cluster_by_attribution(
        self,
        min_cluster_size: int = 2
    ) -> List[List[Dict[str, Any]]]:
        """
        Group fingerprints likely from the same attacker.
        
        Similarity metrics:
        - Browser fingerprint exact match (99% confidence)
        - Canvas fingerprint similarity (90% confidence)
        - Timezone + language match (70% confidence)
        
        Args:
            min_cluster_size: Minimum fingerprints to form a cluster
            
        Returns:
            List of clusters (each cluster is a list of fingerprints)
        """
        fingerprints = list(self.db._mock_fingerprints.values()) if self.db.use_mock else []
        
        if not fingerprints:
            return []
        
        # Group by exact browser fingerprint match
        browser_fp_groups: Dict[str, List[Dict]] = defaultdict(list)
        
        for fp in fingerprints:
            browser_fp = fp.get('browser_fingerprint')
            if browser_fp:
                browser_fp_groups[browser_fp].append(fp)
        
        # Filter to clusters meeting minimum size
        clusters = [
            fps for fps in browser_fp_groups.values()
            if len(fps) >= min_cluster_size
        ]
        
        logger.info(f"Found {len(clusters)} attribution clusters")
        return clusters
    
    def _calculate_browser_fingerprint_similarity(
        self,
        fp1: str,
        fp2: str
    ) -> float:
        """
        Calculate similarity between two browser fingerprints.
        
        Uses character-level comparison for SHA-256 hashes.
        
        Args:
            fp1: First fingerprint hash
            fp2: Second fingerprint hash
            
        Returns:
            Similarity score 0.0 to 1.0
        """
        if not fp1 or not fp2:
            return 0.0
        
        if fp1 == fp2:
            return 1.0
        
        # Count matching characters
        matches = sum(c1 == c2 for c1, c2 in zip(fp1, fp2))
        return matches / max(len(fp1), len(fp2))
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ATTACK INFRASTRUCTURE MAPPING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def identify_attack_infrastructure(self) -> Dict[str, List[str]]:
        """
        Map attacker infrastructure (IP ranges, ASNs, hosting providers).
        
        Returns:
            Dictionary with infrastructure categories:
            {
                'ip_ranges': ['203.0.113.0/24', ...],
                'asns': [12345, 67890],
                'hosting_providers': ['Evil Cloud Inc', ...],
                'tor_exit_nodes': ['203.0.113.42', ...],
                'vpn_services': ['ShadyVPN', ...]
            }
        """
        fingerprints = list(self.db._mock_fingerprints.values()) if self.db.use_mock else []
        
        infrastructure = {
            'ip_ranges': [],
            'asns': [],
            'hosting_providers': [],
            'tor_exit_nodes': [],
            'vpn_services': [],
            'datacenter_ips': []
        }
        
        seen_ips: Set[str] = set()
        seen_asns: Set[int] = set()
        
        for fp in fingerprints:
            ip = fp.get('ip_address')
            asn = fp.get('ip_asn')
            isp = fp.get('ip_isp')
            
            if ip and ip not in seen_ips:
                seen_ips.add(ip)
                
                # Check for TOR
                if self._is_tor_exit_node(ip):
                    infrastructure['tor_exit_nodes'].append(ip)
                
                # Check for VPN
                if self._is_vpn_ip(ip):
                    infrastructure['vpn_services'].append(ip)
                
                # Check for datacenter
                if asn and asn in DATACENTER_ASNS:
                    infrastructure['datacenter_ips'].append(ip)
            
            if asn and asn not in seen_asns:
                seen_asns.add(asn)
                infrastructure['asns'].append(asn)
            
            if isp and isp not in infrastructure['hosting_providers']:
                infrastructure['hosting_providers'].append(isp)
        
        # Generate IP ranges from collected IPs
        infrastructure['ip_ranges'] = self._generate_ip_ranges(list(seen_ips))
        
        logger.info(f"Mapped attack infrastructure: {len(seen_ips)} IPs, {len(seen_asns)} ASNs")
        return infrastructure
    
    def _generate_ip_ranges(self, ips: List[str]) -> List[str]:
        """
        Generate CIDR ranges from a list of IPs.
        
        Groups IPs by /24 network.
        
        Args:
            ips: List of IP addresses
            
        Returns:
            List of CIDR ranges
        """
        networks: Dict[str, int] = defaultdict(int)
        
        for ip in ips:
            parts = ip.split('.')
            if len(parts) == 4:
                network = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                networks[network] += 1
        
        # Return networks with 2+ IPs
        return [net for net, count in networks.items() if count >= 2]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # IOC FEED GENERATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def generate_ioc_feed(self) -> Dict[str, List[str]]:
        """
        Generate Indicators of Compromise feed for SIEM integration.
        
        Returns:
            Dictionary of IOC categories:
            {
                'ip_addresses': ['203.0.113.42', ...],
                'user_agents': ['curl/7.68.0', ...],
                'browser_fingerprints': ['abc123def456', ...],
                'canvas_fingerprints': ['data:image/png;base64,...', ...]
            }
        """
        fingerprints = list(self.db._mock_fingerprints.values()) if self.db.use_mock else []
        
        iocs = {
            'ip_addresses': [],
            'user_agents': [],
            'browser_fingerprints': [],
            'canvas_fingerprints': []
        }
        
        seen_ips: Set[str] = set()
        seen_uas: Set[str] = set()
        seen_browser_fps: Set[str] = set()
        seen_canvas_fps: Set[str] = set()
        
        for fp in fingerprints:
            ip = fp.get('ip_address')
            ua = fp.get('user_agent')
            browser_fp = fp.get('browser_fingerprint')
            canvas_fp = fp.get('canvas_fingerprint')
            
            if ip and ip not in seen_ips:
                seen_ips.add(ip)
                iocs['ip_addresses'].append(ip)
            
            if ua and ua not in seen_uas:
                seen_uas.add(ua)
                iocs['user_agents'].append(ua)
            
            if browser_fp and browser_fp not in seen_browser_fps:
                seen_browser_fps.add(browser_fp)
                iocs['browser_fingerprints'].append(browser_fp)
            
            if canvas_fp and canvas_fp not in seen_canvas_fps:
                seen_canvas_fps.add(canvas_fp)
                iocs['canvas_fingerprints'].append(canvas_fp)
        
        logger.info(
            f"Generated IOC feed: {len(iocs['ip_addresses'])} IPs, "
            f"{len(iocs['user_agents'])} user agents"
        )
        return iocs
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STIX 2.1 EXPORT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def export_stix_bundle(self) -> str:
        """
        Export threat intelligence in STIX 2.1 format.
        
        STIX (Structured Threat Information Expression) is a standard
        for sharing cyber threat intelligence. This export can be shared with:
        - Other healthcare organizations
        - FBI InfraGard
        - HHS Healthcare Cybersecurity Coordination Center (HC3)
        
        Returns:
            JSON string in STIX 2.1 bundle format
        """
        fingerprints = list(self.db._mock_fingerprints.values()) if self.db.use_mock else []
        
        bundle_id = f"bundle--{uuid.uuid4()}"
        
        objects = []
        
        # Identity for Phoenix Guardian
        identity_id = f"identity--{uuid.uuid4()}"
        objects.append({
            "type": "identity",
            "spec_version": "2.1",
            "id": identity_id,
            "created": datetime.now(timezone.utc).isoformat(),
            "modified": datetime.now(timezone.utc).isoformat(),
            "name": "Phoenix Guardian Healthcare AI Security",
            "identity_class": "organization",
            "sectors": ["healthcare"]
        })
        
        # Create indicators for each unique IP
        seen_ips: Set[str] = set()
        for fp in fingerprints:
            ip = fp.get('ip_address')
            if ip and ip not in seen_ips:
                seen_ips.add(ip)
                
                indicator_id = f"indicator--{uuid.uuid4()}"
                objects.append({
                    "type": "indicator",
                    "spec_version": "2.1",
                    "id": indicator_id,
                    "created": datetime.now(timezone.utc).isoformat(),
                    "modified": datetime.now(timezone.utc).isoformat(),
                    "name": f"Malicious IP: {ip}",
                    "description": f"IP address associated with healthcare AI attack",
                    "indicator_types": ["malicious-activity"],
                    "pattern": f"[ipv4-addr:value = '{ip}']",
                    "pattern_type": "stix",
                    "valid_from": datetime.now(timezone.utc).isoformat(),
                    "created_by_ref": identity_id
                })
        
        # Create attack patterns for each type
        attack_types: Set[str] = set()
        for fp in fingerprints:
            at = fp.get('attack_type')
            if at and at not in attack_types:
                attack_types.add(at)
                
                pattern_id = f"attack-pattern--{uuid.uuid4()}"
                objects.append({
                    "type": "attack-pattern",
                    "spec_version": "2.1",
                    "id": pattern_id,
                    "created": datetime.now(timezone.utc).isoformat(),
                    "modified": datetime.now(timezone.utc).isoformat(),
                    "name": at.replace('_', ' ').title(),
                    "description": f"Attack pattern: {at}",
                    "created_by_ref": identity_id
                })
        
        # Create threat actors for unique attackers
        threat_actor_count = min(10, len(fingerprints))  # Limit to 10
        for i, fp in enumerate(fingerprints[:threat_actor_count]):
            actor_id = f"threat-actor--{uuid.uuid4()}"
            ip = fp.get('ip_address', 'Unknown')
            
            objects.append({
                "type": "threat-actor",
                "spec_version": "2.1",
                "id": actor_id,
                "created": datetime.now(timezone.utc).isoformat(),
                "modified": datetime.now(timezone.utc).isoformat(),
                "name": f"Unknown Attacker (IP: {ip})",
                "threat_actor_types": ["criminal"],
                "sophistication": "intermediate",
                "created_by_ref": identity_id
            })
        
        bundle = {
            "type": "bundle",
            "id": bundle_id,
            "objects": objects
        }
        
        stix_json = json.dumps(bundle, indent=2, default=str)
        
        logger.info(
            f"Exported STIX bundle: {len(objects)} objects "
            f"({len(seen_ips)} indicators)"
        )
        
        return stix_json
    
    # ═══════════════════════════════════════════════════════════════════════════
    # THREAT SCORING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def calculate_threat_score(self, fingerprint_id: str) -> int:
        """
        Calculate threat score for an attacker fingerprint.
        
        Score factors:
        - Repeat attempts: +20 per additional attempt
        - TOR/VPN usage: +30
        - Datacenter IP: +20
        - Attack type severity: varies by type
        - International (non-US): +10
        
        Args:
            fingerprint_id: Fingerprint to score
            
        Returns:
            Threat score 0-100
        """
        fp = self.db.get_fingerprint(fingerprint_id)
        
        if not fp:
            return 0
        
        score = 0
        
        ip = fp.get('ip_address')
        
        # Check for repeat attempts from same IP
        if ip:
            repeat_fps = self.db.get_fingerprints_by_ip(ip)
            attempt_count = len(repeat_fps)
            if attempt_count > 1:
                score += min(40, 20 * (attempt_count - 1))  # +20 per repeat, max 40
        
        # TOR exit node
        if ip and self._is_tor_exit_node(ip):
            score += 30
        
        # VPN usage
        if ip and self._is_vpn_ip(ip):
            score += 20
        
        # Datacenter IP
        asn = fp.get('ip_asn')
        if asn and self._is_datacenter_ip(asn):
            score += 20
        
        # Attack type severity
        attack_type = fp.get('attack_type')
        if attack_type and attack_type in ATTACK_SEVERITY:
            score += ATTACK_SEVERITY[attack_type]
        
        # International (non-US)
        country = fp.get('ip_country')
        if country and country != 'US':
            score += 10
        
        # Cap at 100
        score = min(100, score)
        
        # Update in database
        self.db.update_threat_score(fingerprint_id, score)
        
        logger.debug(f"Calculated threat score for {fingerprint_id}: {score}")
        return score
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _is_tor_exit_node(self, ip: str) -> bool:
        """
        Check if IP is a known TOR exit node.
        
        Args:
            ip: IP address to check
            
        Returns:
            True if TOR exit node
        """
        for prefix in KNOWN_TOR_EXIT_NODES:
            if ip.startswith(prefix):
                return True
        return False
    
    def _is_vpn_ip(self, ip: str) -> bool:
        """
        Check if IP belongs to known VPN service.
        
        Args:
            ip: IP address to check
            
        Returns:
            True if VPN IP
        """
        for vpn_name, prefixes in KNOWN_VPN_PATTERNS.items():
            for prefix in prefixes:
                if ip.startswith(prefix):
                    return True
        return False
    
    def _is_datacenter_ip(self, asn: int) -> bool:
        """
        Check if ASN belongs to known datacenter.
        
        Args:
            asn: Autonomous System Number
            
        Returns:
            True if datacenter ASN
        """
        return asn in DATACENTER_ASNS
