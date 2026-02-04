"""
Phoenix Guardian Evidence Packager.

Automated evidence package generation for law enforcement.
Complies with:
- Computer Fraud and Abuse Act (CFAA) - 18 U.S.C. § 1030
- Federal Rules of Evidence
- HIPAA Breach Notification Rule (45 CFR §164.404)

Day 74: Evidence Packaging System
"""

import uuid
import json
import hashlib
import logging
import base64
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

from phoenix_guardian.security.attacker_intelligence_db import AttackerIntelligenceDB
from phoenix_guardian.security.threat_intelligence import ThreatIntelligenceAnalyzer
from phoenix_guardian.security.honeytoken_generator import (
    LegalHoneytoken,
    AttackerFingerprint,
    HoneytokenStatus,
    AttackType
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceType(Enum):
    """Types of evidence collected."""
    HONEYTOKEN_INTERACTION = "honeytoken_interaction"
    BEACON_TRIGGER = "beacon_trigger"
    NETWORK_ATTRIBUTION = "network_attribution"
    BROWSER_FINGERPRINT = "browser_fingerprint"
    BEHAVIORAL_ANALYSIS = "behavioral_analysis"
    SESSION_RECORDING = "session_recording"


# ═══════════════════════════════════════════════════════════════════════════════
# STATE COMPUTER CRIME LAWS DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

STATE_COMPUTER_CRIME_LAWS = {
    'AL': 'Alabama Code § 13A-8-102 - Computer Crime',
    'AK': 'Alaska Statutes § 11.46.740 - Criminal Use of Computer',
    'AZ': 'Arizona Revised Statutes § 13-2316 - Computer Tampering',
    'AR': 'Arkansas Code § 5-41-103 - Computer Fraud',
    'CA': 'California Penal Code § 502 - Unauthorized Computer Access',
    'CO': 'Colorado Revised Statutes § 18-5.5-102 - Computer Crime',
    'CT': 'Connecticut General Statutes § 53a-251 - Computer Crime',
    'DE': 'Delaware Code Title 11 § 932 - Unauthorized Computer Access',
    'FL': 'Florida Statutes § 815.06 - Offenses Against Computer Users',
    'GA': 'Georgia Code § 16-9-93 - Computer Theft',
    'HI': 'Hawaii Revised Statutes § 708-891 - Computer Fraud',
    'ID': 'Idaho Code § 18-2202 - Computer Crime',
    'IL': 'Illinois Computer Crime Prevention Law (720 ILCS 5/17-50)',
    'IN': 'Indiana Code § 35-43-2-3 - Computer Tampering',
    'IA': 'Iowa Code § 716.6B - Unauthorized Computer Access',
    'KS': 'Kansas Statutes § 21-5839 - Computer Crime',
    'KY': 'Kentucky Revised Statutes § 434.845 - Unlawful Access to Computer',
    'LA': 'Louisiana Revised Statutes § 14:73.1 - Computer Fraud',
    'ME': 'Maine Revised Statutes Title 17-A § 432 - Computer Crimes',
    'MD': 'Maryland Criminal Law § 7-302 - Unauthorized Access',
    'MA': 'Massachusetts General Laws Chapter 266 § 120F - Computer Crime',
    'MI': 'Michigan Penal Code § 752.794 - Unauthorized Access',
    'MN': 'Minnesota Statutes § 609.87 - Computer Damage',
    'MS': 'Mississippi Code § 97-45-3 - Computer Fraud',
    'MO': 'Missouri Revised Statutes § 569.095 - Computer Tampering',
    'MT': 'Montana Code § 45-6-311 - Unlawful Use of Computer',
    'NE': 'Nebraska Revised Statutes § 28-1343 - Computer Crimes',
    'NV': 'Nevada Revised Statutes § 205.4765 - Unlawful Acts Regarding Computers',
    'NH': 'New Hampshire Revised Statutes § 638:17 - Computer Crime',
    'NJ': 'New Jersey Statutes § 2C:20-25 - Computer Criminal Activity',
    'NM': 'New Mexico Statutes § 30-45-3 - Computer Abuse',
    'NY': 'New York Penal Law § 156.05 - Unauthorized Use of Computer',
    'NC': 'North Carolina General Statutes § 14-454 - Computer Crimes',
    'ND': 'North Dakota Century Code § 12.1-06.1-08 - Computer Fraud',
    'OH': 'Ohio Revised Code § 2913.04 - Unauthorized Computer Access',
    'OK': 'Oklahoma Statutes Title 21 § 1953 - Computer Crimes',
    'OR': 'Oregon Revised Statutes § 164.377 - Computer Crime',
    'PA': 'Pennsylvania Statutes Title 18 § 7611 - Unlawful Use of Computer',
    'RI': 'Rhode Island General Laws § 11-52-2 - Computer Crime',
    'SC': 'South Carolina Code § 16-16-20 - Computer Crime',
    'SD': 'South Dakota Codified Laws § 43-43B-1 - Computer Crime',
    'TN': 'Tennessee Code § 39-14-602 - Unlawful Use of Computer',
    'TX': 'Texas Penal Code § 33.02 - Breach of Computer Security',
    'UT': 'Utah Code § 76-6-703 - Computer Crimes',
    'VT': 'Vermont Statutes Title 13 § 4102 - Unauthorized Computer Access',
    'VA': 'Virginia Code § 18.2-152.4 - Computer Fraud',
    'WA': 'Washington Revised Code § 9A.52.110 - Computer Trespass',
    'WV': 'West Virginia Code § 61-3C-5 - Computer Fraud',
    'WI': 'Wisconsin Statutes § 943.70 - Computer Crimes',
    'WY': 'Wyoming Statutes § 6-3-504 - Computer Crime',
    'DC': 'District of Columbia Code § 22-3532 - Computer Fraud',
    'PR': 'Puerto Rico Penal Code Art. 172 - Computer Crimes',
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EvidencePackage:
    """
    Complete evidence package for law enforcement.
    
    Complies with:
    - Computer Fraud and Abuse Act (CFAA) - 18 U.S.C. § 1030
    - Federal Rules of Evidence (authentication, chain of custody)
    - HIPAA Breach Notification Rule (45 CFR §164.404)
    
    Designed for court admissibility with:
    - Complete chain of custody
    - Digital signatures for integrity
    - SHA-256 evidence hashing
    """
    
    # Package Identification
    package_id: str                          # UUID
    case_number: str                         # LE case reference (PG-YYYYMMDD-XXXXXX)
    generation_timestamp: datetime
    
    # Attack Summary
    attack_type: str
    attack_confidence: float                 # 0.0-1.0
    session_id: str
    total_interactions: int
    
    # Attacker Attribution
    primary_fingerprint: Optional[AttackerFingerprint]
    related_fingerprints: List[AttackerFingerprint] = field(default_factory=list)
    
    # Honeytokens Involved
    honeytokens_triggered: List[LegalHoneytoken] = field(default_factory=list)
    
    # Evidence Chain
    evidence_items: List[Dict[str, Any]] = field(default_factory=list)
    chain_of_custody: List[Dict[str, Any]] = field(default_factory=list)
    
    # Technical Details
    network_logs: List[Dict[str, Any]] = field(default_factory=list)
    beacon_payloads: List[Dict[str, Any]] = field(default_factory=list)
    
    # Threat Intelligence
    coordinated_campaign_id: Optional[str] = None
    ioc_indicators: Dict[str, List[str]] = field(default_factory=dict)
    stix_bundle: Optional[str] = None
    
    # Legal Compliance
    hipaa_breach_assessment: Dict[str, Any] = field(default_factory=dict)
    cfaa_violation_summary: str = ""
    state_laws_violated: List[str] = field(default_factory=list)
    
    # Integrity Verification
    evidence_hash: str = ""                  # SHA-256 of all evidence
    digital_signature: Optional[str] = None  # RSA-2048 signature
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize evidence package to dictionary.
        
        Returns:
            Dictionary representation suitable for JSON serialization
        """
        result = {
            'package_id': self.package_id,
            'case_number': self.case_number,
            'generation_timestamp': self.generation_timestamp.isoformat() if self.generation_timestamp else None,
            'attack_type': self.attack_type,
            'attack_confidence': self.attack_confidence,
            'session_id': self.session_id,
            'total_interactions': self.total_interactions,
            'coordinated_campaign_id': self.coordinated_campaign_id,
            'ioc_indicators': self.ioc_indicators,
            'stix_bundle': self.stix_bundle,
            'hipaa_breach_assessment': self.hipaa_breach_assessment,
            'cfaa_violation_summary': self.cfaa_violation_summary,
            'state_laws_violated': self.state_laws_violated,
            'evidence_hash': self.evidence_hash,
            'digital_signature': self.digital_signature,
            'evidence_items': self.evidence_items,
            'chain_of_custody': self._serialize_custody_chain(),
            'network_logs': self.network_logs,
            'beacon_payloads': self.beacon_payloads,
        }
        
        # Serialize primary fingerprint
        if self.primary_fingerprint:
            result['primary_fingerprint'] = self._fingerprint_to_dict(self.primary_fingerprint)
        else:
            result['primary_fingerprint'] = None
        
        # Serialize related fingerprints
        result['related_fingerprints'] = [
            self._fingerprint_to_dict(fp) for fp in self.related_fingerprints
        ]
        
        # Serialize honeytokens
        result['honeytokens_triggered'] = [
            self._honeytoken_to_dict(ht) for ht in self.honeytokens_triggered
        ]
        
        return result
    
    def _serialize_custody_chain(self) -> List[Dict[str, Any]]:
        """Serialize chain of custody with ISO timestamps."""
        serialized = []
        for event in self.chain_of_custody:
            event_copy = event.copy()
            if 'timestamp' in event_copy and isinstance(event_copy['timestamp'], datetime):
                event_copy['timestamp'] = event_copy['timestamp'].isoformat()
            serialized.append(event_copy)
        return serialized
    
    def _fingerprint_to_dict(self, fp: AttackerFingerprint) -> Dict[str, Any]:
        """Convert AttackerFingerprint to dictionary."""
        return {
            'fingerprint_id': fp.fingerprint_id,
            'honeytoken_id': fp.honeytoken_id,
            'ip_address': fp.ip_address,
            'ip_geolocation': fp.ip_geolocation,
            'user_agent': fp.user_agent,
            'canvas_fingerprint': fp.canvas_fingerprint,
            'webgl_vendor': fp.webgl_vendor,
            'webgl_renderer': fp.webgl_renderer,
            'platform': fp.platform,
            'language': fp.language,
            'timezone': fp.timezone,
            'screen_resolution': fp.screen_resolution,
            'color_depth': fp.color_depth,
            'installed_fonts': fp.installed_fonts,
            'plugins': fp.plugins,
            'timestamp': fp.timestamp.isoformat() if fp.timestamp else None,
            'access_pattern': fp.access_pattern,
            'behavioral_data': fp.behavioral_data,
        }
    
    def _honeytoken_to_dict(self, ht: LegalHoneytoken) -> Dict[str, Any]:
        """Convert LegalHoneytoken to dictionary."""
        return {
            'honeytoken_id': ht.honeytoken_id,
            'mrn': ht.mrn,
            'name': ht.name,
            'age': ht.age,
            'gender': ht.gender,
            'phone': ht.phone,
            'email': ht.email,
            'address': ht.address,
            'city': ht.city,
            'state': ht.state,
            'zip_code': ht.zip_code,
            'status': ht.status if isinstance(ht.status, str) else ht.status.value if ht.status else None,
            'deployment_timestamp': ht.deployment_timestamp.isoformat() if ht.deployment_timestamp else None,
            'trigger_count': ht.trigger_count,
        }
    
    def generate_law_enforcement_summary(self) -> str:
        """
        Generate ASCII formatted summary for law enforcement.
        
        Returns:
            Formatted text summary for quick LE review
        """
        lines = []
        lines.append("=" * 80)
        lines.append("PHOENIX GUARDIAN - FORENSIC EVIDENCE SUMMARY")
        lines.append("LAW ENFORCEMENT SENSITIVE")
        lines.append("=" * 80)
        lines.append("")
        
        # Case Information
        lines.append("CASE INFORMATION")
        lines.append("-" * 40)
        lines.append(f"  Case Number:    {self.case_number}")
        lines.append(f"  Package ID:     {self.package_id}")
        lines.append(f"  Generated:      {self.generation_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') if self.generation_timestamp else 'N/A'}")
        lines.append("")
        
        # Attack Summary
        lines.append("ATTACK SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Attack Type:    {self.attack_type}")
        lines.append(f"  Confidence:     {self.attack_confidence:.0%}" if self.attack_confidence else "  Confidence:     N/A")
        lines.append(f"  Session ID:     {self.session_id}")
        lines.append(f"  Interactions:   {self.total_interactions}")
        lines.append(f"  Honeytokens:    {len(self.honeytokens_triggered)} triggered")
        lines.append("")
        
        # Attacker Attribution
        lines.append("ATTACKER ATTRIBUTION")
        lines.append("-" * 40)
        if self.primary_fingerprint:
            fp = self.primary_fingerprint
            lines.append(f"  IP Address:     {fp.ip_address or 'N/A'}")
            if fp.ip_geolocation:
                geo = fp.ip_geolocation
                lines.append(f"  Country:        {geo.get('country', 'N/A')}")
                lines.append(f"  City:           {geo.get('city', 'N/A')}")
                lines.append(f"  ISP:            {geo.get('isp', 'N/A')}")
                lines.append(f"  ASN:            {geo.get('asn', 'N/A')}")
            lines.append(f"  User Agent:     {fp.user_agent or 'N/A'}")
            lines.append(f"  Platform:       {fp.platform or 'N/A'}")
        else:
            lines.append("  No attacker fingerprint available")
        lines.append("")
        
        # Legal Violations
        lines.append("LEGAL VIOLATIONS")
        lines.append("-" * 40)
        lines.append("")
        lines.append("CFAA Analysis:")
        for line in self.cfaa_violation_summary.split('\n')[:10]:
            lines.append(f"  {line}")
        lines.append("")
        
        lines.append("State Laws Violated:")
        for law in self.state_laws_violated[:5]:
            lines.append(f"  • {law}")
        lines.append("")
        
        # HIPAA Assessment
        lines.append("HIPAA BREACH ASSESSMENT")
        lines.append("-" * 40)
        lines.append(f"  Is Breach:      {self.hipaa_breach_assessment.get('is_breach', 'N/A')}")
        lines.append(f"  Reasoning:      {self.hipaa_breach_assessment.get('reasoning', 'N/A')}")
        lines.append(f"  Notification:   {self.hipaa_breach_assessment.get('notification_required', 'N/A')}")
        lines.append("")
        
        # Evidence Integrity
        lines.append("EVIDENCE INTEGRITY")
        lines.append("-" * 40)
        lines.append(f"  SHA-256 Hash:   {self.evidence_hash[:64]}...")
        lines.append(f"  Signed:         {'Yes' if self.digital_signature else 'No'}")
        lines.append(f"  Custody Events: {len(self.chain_of_custody)}")
        lines.append("")
        
        # IOC Summary
        lines.append("INDICATORS OF COMPROMISE (IOC)")
        lines.append("-" * 40)
        for ioc_type, indicators in self.ioc_indicators.items():
            lines.append(f"  {ioc_type.upper()}: {len(indicators)} indicator(s)")
        lines.append("")
        
        lines.append("=" * 80)
        lines.append("END OF EVIDENCE SUMMARY")
        lines.append("=" * 80)
        
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE PACKAGER CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class EvidencePackager:
    """
    Automated evidence package generation for law enforcement.
    
    Workflow:
    1. Collect all evidence related to an attack
    2. Verify chain of custody
    3. Assess legal violations (CFAA, state laws)
    4. Generate comprehensive report
    5. Sign and hash for integrity
    
    Output Formats:
    - PDF report (for prosecutors)
    - ASCII text (for quick review)
    - JSON (for digital forensics tools)
    - STIX 2.1 (for threat intelligence sharing)
    
    Legal Compliance:
    - CFAA (18 U.S.C. § 1030) violation analysis
    - State computer crime law identification
    - HIPAA breach assessment
    - Federal Rules of Evidence (chain of custody)
    """
    
    def __init__(
        self,
        db: AttackerIntelligenceDB,
        threat_analyzer: ThreatIntelligenceAnalyzer
    ):
        """
        Initialize EvidencePackager.
        
        Args:
            db: Attacker intelligence database
            threat_analyzer: Threat intelligence analyzer
        """
        self.db = db
        self.threat_analyzer = threat_analyzer
        
        # Track generated packages
        self.packages: Dict[str, EvidencePackage] = {}
        
        # Chain of custody log
        self.custody_log: List[Dict[str, Any]] = []
        
        logger.info("EvidencePackager initialized")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN EVIDENCE COLLECTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def collect_evidence_for_session(self, session_id: str) -> EvidencePackage:
        """
        Collect all evidence for an attack session.
        
        Gathers all honeytokens, fingerprints, interactions, and generates
        a complete evidence package for law enforcement.
        
        Args:
            session_id: Session identifier from attack
        
        Returns:
            Complete EvidencePackage
        
        Raises:
            ValueError: If session_id not found or no evidence available
        """
        logger.info(f"Collecting evidence for session: {session_id}")
        
        # 1. Get all honeytokens triggered in this session
        honeytokens = self.db.get_honeytokens_by_session(session_id)
        
        if not honeytokens:
            raise ValueError(f"No honeytokens found for session {session_id}")
        
        # 2. Get all attacker fingerprints
        fingerprints = []
        for ht in honeytokens:
            ht_id = ht.get('honeytoken_id') or ht.get('id')
            if ht_id:
                fps = self.db.get_fingerprints_by_honeytoken(ht_id)
                fingerprints.extend(fps)
        
        # 3. Get primary fingerprint (first interaction)
        primary_fp = None
        related_fps = []
        
        if fingerprints:
            # Sort by first_interaction to find primary
            sorted_fps = sorted(
                fingerprints,
                key=lambda x: x.get('first_interaction', datetime.max) 
                    if isinstance(x.get('first_interaction'), datetime)
                    else datetime.max
            )
            
            primary_fp = self._dict_to_fingerprint(sorted_fps[0])
            related_fps = [self._dict_to_fingerprint(fp) for fp in sorted_fps[1:]]
        
        # 4. Get all interactions
        interactions = self.db.get_interactions_by_session(session_id)
        
        # 5. Collect evidence items (timestamped trail)
        evidence_items = []
        for interaction in interactions:
            evidence_items.append({
                'timestamp': interaction.get('interaction_timestamp') or interaction.get('timestamp'),
                'type': interaction.get('interaction_type') or interaction.get('type'),
                'honeytoken_id': interaction.get('honeytoken_id'),
                'ip_address': interaction.get('ip_address'),
                'user_agent': interaction.get('user_agent'),
                'raw_data': interaction.get('raw_data', {})
            })
        
        # 6. Check for coordinated campaign
        coordinated_campaigns = self.threat_analyzer.detect_coordinated_attacks(
            time_window_hours=24
        )
        
        campaign_id = None
        if primary_fp and coordinated_campaigns:
            for campaign in coordinated_campaigns:
                fp_ids = campaign.get('fingerprint_ids', [])
                if primary_fp.fingerprint_id in fp_ids:
                    campaign_id = campaign.get('campaign_id')
                    break
        
        # 7. Generate IOC indicators
        iocs = self._generate_ioc_for_session(session_id, fingerprints)
        
        # 8. Generate STIX bundle
        stix = self.threat_analyzer.export_stix_bundle()
        
        # 9. Determine attack type from honeytokens
        attack_type = 'unknown'
        confidence = 0.0
        for ht in honeytokens:
            metadata = ht.get('deployment_metadata', {})
            if metadata.get('attack_type'):
                attack_type = metadata['attack_type']
            if metadata.get('confidence'):
                confidence = max(confidence, metadata['confidence'])
        
        # 10. Assess HIPAA breach
        hipaa_assessment = self._assess_hipaa_breach(honeytokens, interactions)
        
        # 11. Assess CFAA violations
        cfaa_summary = self._assess_cfaa_violations(
            attack_type=attack_type,
            unauthorized_access=True,
            data_exfiltration=any(
                i.get('interaction_type') == 'exfiltrate' or 
                i.get('type') == 'exfiltrate'
                for i in interactions
            )
        )
        
        # 12. Identify state laws violated
        attacker_state = None
        if primary_fp and primary_fp.ip_geolocation:
            attacker_state = primary_fp.ip_geolocation.get('region') or \
                           primary_fp.ip_geolocation.get('state')
        
        state_laws = self._identify_state_laws(
            attacker_state=attacker_state,
            victim_state='CA'  # Assume Phoenix Guardian deployed in California
        )
        
        # 13. Convert honeytokens to LegalHoneytoken objects
        honeytoken_objects = [self._dict_to_honeytoken(ht) for ht in honeytokens]
        
        # 14. Generate chain of custody
        custody_chain = self._generate_chain_of_custody(session_id)
        
        # 15. Collect network logs
        network_logs = self._collect_network_logs(session_id)
        
        # 16. Collect beacon payloads
        beacon_payloads = self._collect_beacon_payloads(interactions)
        
        # 17. Compute evidence hash
        evidence_hash = self._compute_evidence_hash(evidence_items)
        
        # 18. Create evidence package
        package = EvidencePackage(
            package_id=str(uuid.uuid4()),
            case_number=f"PG-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{session_id[-6:].upper()}",
            generation_timestamp=datetime.now(timezone.utc),
            attack_type=attack_type,
            attack_confidence=confidence,
            session_id=session_id,
            total_interactions=len(interactions),
            primary_fingerprint=primary_fp,
            related_fingerprints=related_fps,
            honeytokens_triggered=honeytoken_objects,
            evidence_items=evidence_items,
            chain_of_custody=custody_chain,
            network_logs=network_logs,
            beacon_payloads=beacon_payloads,
            coordinated_campaign_id=campaign_id,
            ioc_indicators=iocs,
            stix_bundle=stix,
            hipaa_breach_assessment=hipaa_assessment,
            cfaa_violation_summary=cfaa_summary,
            state_laws_violated=state_laws,
            evidence_hash=evidence_hash,
            digital_signature=None
        )
        
        # 19. Store package
        self.packages[package.package_id] = package
        
        # 20. Log custody event
        self._log_custody_event(
            package_id=package.package_id,
            event_type='package_created',
            user='system',
            details='Initial evidence collection completed'
        )
        
        # Add creation event to package custody chain
        package.chain_of_custody.append({
            'timestamp': datetime.now(timezone.utc),
            'event_type': 'package_created',
            'user': 'system',
            'details': 'Initial evidence collection completed'
        })
        
        logger.info(f"Evidence package created: {package.package_id}")
        return package
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LEGAL ANALYSIS METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _assess_hipaa_breach(
        self,
        honeytokens: List[Dict[str, Any]],
        interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Assess whether HIPAA breach occurred.
        
        IMPORTANT: Honeytokens contain FICTIONAL data, not real PHI.
        Therefore, honeytoken access is NOT a HIPAA breach.
        However, the ATTEMPT to access PHI may trigger other legal violations.
        
        Args:
            honeytokens: List of honeytokens accessed
            interactions: List of interactions
        
        Returns:
            HIPAA breach assessment dictionary
        """
        # Honeytokens are FAKE data - no actual PHI was accessed
        return {
            'is_breach': False,
            'reasoning': (
                'No actual PHI was accessed. All patient data accessed were '
                'legal honeytokens containing completely fictional information. '
                'Honeytokens are designed to detect unauthorized access attempts '
                'without exposing real patient data.'
            ),
            'notification_required': False,
            'affected_individuals': 0,
            'breach_type': None,
            'regulatory_timeline': None,
            'honeytokens_accessed': len(honeytokens),
            'total_interactions': len(interactions),
            'note': (
                'While not a HIPAA breach, the unauthorized access attempt '
                'may violate CFAA and state computer crime laws.'
            )
        }
    
    def _assess_cfaa_violations(
        self,
        attack_type: str,
        unauthorized_access: bool,
        data_exfiltration: bool
    ) -> str:
        """
        Generate Computer Fraud and Abuse Act (18 U.S.C. § 1030) violation analysis.
        
        Args:
            attack_type: Type of attack detected
            unauthorized_access: Whether unauthorized access occurred
            data_exfiltration: Whether data exfiltration was attempted
        
        Returns:
            Formatted legal analysis string
        """
        lines = []
        lines.append("COMPUTER FRAUD AND ABUSE ACT (CFAA) VIOLATION ANALYSIS")
        lines.append("18 U.S.C. § 1030")
        lines.append("=" * 60)
        lines.append("")
        
        # Section (a)(2)(C) - Unauthorized Access
        status_a2c = "✓ VIOLATED" if unauthorized_access else "⚠ POTENTIAL"
        lines.append(f"§ 1030(a)(2)(C) - Unauthorized Access to Protected Computer:")
        lines.append(f"  Status: {status_a2c}")
        lines.append(f"  Evidence: Attacker accessed healthcare computer system")
        lines.append(f"           without authorization to obtain information.")
        lines.append("")
        
        # Section (a)(4) - Fraud
        status_a4 = "✓ VIOLATED" if unauthorized_access else "⚠ POTENTIAL"
        lines.append(f"§ 1030(a)(4) - Fraud and Related Activity:")
        lines.append(f"  Status: {status_a4}")
        lines.append(f"  Evidence: Attacker knowingly accessed protected computer")
        lines.append(f"           with intent to defraud and obtain something of value.")
        lines.append("")
        
        # Section (a)(5)(A) - Intentional Damage
        damage_attacks = ['prompt_injection', 'jailbreak', 'sql_injection', 'malware']
        if attack_type in damage_attacks:
            status_a5a = "✓ VIOLATED"
            reason = f"Attack type '{attack_type}' demonstrates intent to cause damage"
        else:
            status_a5a = "⚠ POTENTIAL"
            reason = "Attack pattern suggests possible intent to cause damage"
        
        lines.append(f"§ 1030(a)(5)(A) - Intentional Damage to Protected Computer:")
        lines.append(f"  Status: {status_a5a}")
        lines.append(f"  Evidence: {reason}")
        lines.append("")
        
        # Section (a)(5)(B) - Reckless Damage
        lines.append(f"§ 1030(a)(5)(B) - Reckless Damage to Protected Computer:")
        lines.append(f"  Status: ⚠ POTENTIAL")
        lines.append(f"  Evidence: Attack on healthcare system shows reckless")
        lines.append(f"           disregard for potential patient safety impact.")
        lines.append("")
        
        # Data Exfiltration
        if data_exfiltration:
            lines.append(f"§ 1030(a)(2) - Obtaining Information (Data Exfiltration):")
            lines.append(f"  Status: ✓ VIOLATED")
            lines.append(f"  Evidence: Attacker attempted to exfiltrate data from system.")
            lines.append("")
        
        # Penalty Information
        lines.append("-" * 60)
        lines.append("PENALTY INFORMATION:")
        lines.append("")
        lines.append("First Offense:")
        lines.append("  • Up to 5 years imprisonment")
        lines.append("  • Fines up to $250,000 (individual) or $500,000 (organization)")
        lines.append("")
        lines.append("Repeat Offense:")
        lines.append("  • Up to 10 years imprisonment")
        lines.append("  • Enhanced fines")
        lines.append("")
        
        # Aggravating Factors
        lines.append("-" * 60)
        lines.append("AGGRAVATING FACTORS:")
        lines.append("")
        lines.append("  • Healthcare system targeted (critical infrastructure)")
        lines.append("  • Patient data was the apparent target")
        lines.append("  • Multiple unauthorized access attempts")
        if data_exfiltration:
            lines.append("  • Data exfiltration attempted")
        if attack_type in ['prompt_injection', 'jailbreak']:
            lines.append(f"  • Sophisticated attack technique used ({attack_type})")
        lines.append("")
        
        return "\n".join(lines)
    
    def _identify_state_laws(
        self,
        attacker_state: Optional[str],
        victim_state: str = 'CA'
    ) -> List[str]:
        """
        Identify applicable state computer crime laws.
        
        Both the victim's state and attacker's state laws may apply.
        
        Args:
            attacker_state: State where attacker is located (2-letter code)
            victim_state: State where system is located (default: CA)
        
        Returns:
            List of applicable state law citations
        """
        violations = []
        
        # Victim state law always applies
        if victim_state and victim_state.upper() in STATE_COMPUTER_CRIME_LAWS:
            violations.append(STATE_COMPUTER_CRIME_LAWS[victim_state.upper()])
        
        # Attacker state law may also apply
        if attacker_state and attacker_state.upper() in STATE_COMPUTER_CRIME_LAWS:
            attacker_law = STATE_COMPUTER_CRIME_LAWS[attacker_state.upper()]
            if attacker_law not in violations:
                violations.append(attacker_law)
        
        # If no specific state identified, note federal jurisdiction
        if not violations:
            violations.append("Federal jurisdiction applies (interstate computer crime)")
        
        return violations
    
    # ═══════════════════════════════════════════════════════════════════════════
    # REPORT GENERATION METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def generate_pdf_report(
        self,
        package: EvidencePackage,
        output_path: str
    ) -> str:
        """
        Generate professional PDF evidence package.
        
        Creates a court-admissible PDF document with:
        - Cover page
        - Executive summary
        - Attacker attribution
        - Honeytoken analysis
        - Legal analysis
        - Technical evidence
        - Chain of custody
        
        Args:
            package: EvidencePackage to export
            output_path: Path to save PDF file
        
        Returns:
            Path to generated PDF
        
        Raises:
            ImportError: If reportlab not installed
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, 
                TableStyle, PageBreak
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
        except ImportError:
            logger.warning("ReportLab not installed. Install with: pip install reportlab")
            # Generate ASCII report instead
            ascii_report = package.generate_law_enforcement_summary()
            txt_path = output_path.replace('.pdf', '.txt')
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(ascii_report)
            return txt_path
        
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=1  # Center
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#cc0000'),
            spaceAfter=12,
            alignment=1
        )
        
        # PAGE 1: Cover Page
        story.append(Spacer(1, 2*inch))
        story.append(Paragraph("PHOENIX GUARDIAN", title_style))
        story.append(Paragraph("FORENSIC EVIDENCE PACKAGE", title_style))
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(f"Case Number: {package.case_number}", styles['Normal']))
        story.append(Paragraph(
            f"Generated: {package.generation_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}" 
            if package.generation_timestamp else "Generated: N/A",
            styles['Normal']
        ))
        story.append(Spacer(1, 1*inch))
        story.append(Paragraph("LAW ENFORCEMENT SENSITIVE", subtitle_style))
        story.append(Paragraph(
            "This document contains sensitive investigative information. "
            "Handle in accordance with law enforcement protocols.",
            styles['Normal']
        ))
        story.append(PageBreak())
        
        # PAGE 2: Executive Summary
        story.append(Paragraph("EXECUTIVE SUMMARY", styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))
        
        # Get fingerprint info safely
        ip_addr = "Unknown"
        city = "Unknown"
        country = "Unknown"
        isp = "Unknown"
        
        if package.primary_fingerprint:
            ip_addr = package.primary_fingerprint.ip_address or "Unknown"
            if package.primary_fingerprint.ip_geolocation:
                geo = package.primary_fingerprint.ip_geolocation
                city = geo.get('city', 'Unknown')
                country = geo.get('country', 'Unknown')
                isp = geo.get('isp', 'Unknown')
        
        summary_text = f"""
        <b>Attack Type:</b> {package.attack_type}<br/>
        <b>Confidence:</b> {package.attack_confidence:.0%}<br/>
        <b>Session ID:</b> {package.session_id}<br/>
        <b>Total Interactions:</b> {package.total_interactions}<br/>
        <b>Honeytokens Triggered:</b> {len(package.honeytokens_triggered)}<br/>
        <br/>
        <b>Attacker IP:</b> {ip_addr}<br/>
        <b>Geolocation:</b> {city}, {country}<br/>
        <b>ISP:</b> {isp}<br/>
        """
        story.append(Paragraph(summary_text, styles['Normal']))
        story.append(PageBreak())
        
        # PAGE 3-4: Attacker Attribution
        story.append(Paragraph("ATTACKER ATTRIBUTION", styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))
        
        # Network attribution table
        network_data = [
            ['Attribute', 'Value'],
            ['IP Address', ip_addr],
            ['Country', country],
            ['City', city],
            ['ISP', isp],
        ]
        
        if package.primary_fingerprint and package.primary_fingerprint.ip_geolocation:
            asn = package.primary_fingerprint.ip_geolocation.get('asn', 'N/A')
            network_data.append(['ASN', str(asn)])
        
        if package.primary_fingerprint and package.primary_fingerprint.reverse_dns:
            network_data.append(['Reverse DNS', package.primary_fingerprint.reverse_dns])
        
        network_table = Table(network_data, colWidths=[2*inch, 4*inch])
        network_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(network_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Browser fingerprint
        if package.primary_fingerprint:
            story.append(Paragraph("Browser Fingerprint:", styles['Heading2']))
            browser_text = f"""
            <b>User Agent:</b> {package.primary_fingerprint.user_agent or 'N/A'}<br/>
            <b>Platform:</b> {package.primary_fingerprint.platform or 'N/A'}<br/>
            <b>Language:</b> {package.primary_fingerprint.language or 'N/A'}<br/>
            <b>Timezone:</b> {package.primary_fingerprint.timezone or 'N/A'}<br/>
            <b>Screen Resolution:</b> {package.primary_fingerprint.screen_resolution or 'N/A'}<br/>
            <b>Color Depth:</b> {package.primary_fingerprint.color_depth or 'N/A'}-bit<br/>
            """
            story.append(Paragraph(browser_text, styles['Normal']))
        story.append(PageBreak())
        
        # PAGE 5: Honeytoken Analysis
        story.append(Paragraph("HONEYTOKEN ANALYSIS", styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))
        
        honeytoken_data = [['MRN', 'Name', 'Trigger Time']]
        for ht in package.honeytokens_triggered:
            trigger_time = 'N/A'
            if ht.deployment_timestamp:
                trigger_time = ht.deployment_timestamp.strftime('%Y-%m-%d %H:%M:%S')
            honeytoken_data.append([
                ht.mrn or 'N/A',
                ht.name or 'N/A',
                trigger_time
            ])
        
        ht_table = Table(honeytoken_data, colWidths=[1.5*inch, 2.5*inch, 2*inch])
        ht_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(ht_table)
        story.append(PageBreak())
        
        # PAGE 6: Legal Analysis
        story.append(Paragraph("LEGAL ANALYSIS", styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph("CFAA Violations:", styles['Heading2']))
        # Truncate CFAA summary for PDF (first 20 lines)
        cfaa_lines = package.cfaa_violation_summary.split('\n')[:20]
        for line in cfaa_lines:
            if line.strip():
                story.append(Paragraph(line, styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph("State Laws Violated:", styles['Heading2']))
        for law in package.state_laws_violated:
            story.append(Paragraph(f"• {law}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph("HIPAA Breach Assessment:", styles['Heading2']))
        hipaa_text = f"""
        <b>Is Breach:</b> {package.hipaa_breach_assessment.get('is_breach', 'N/A')}<br/>
        <b>Reasoning:</b> {package.hipaa_breach_assessment.get('reasoning', 'N/A')}<br/>
        <b>Notification Required:</b> {package.hipaa_breach_assessment.get('notification_required', 'N/A')}<br/>
        """
        story.append(Paragraph(hipaa_text, styles['Normal']))
        story.append(PageBreak())
        
        # PAGE 7: Technical Evidence
        story.append(Paragraph("TECHNICAL EVIDENCE", styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph("IOC Indicators:", styles['Heading2']))
        for ioc_type, indicators in package.ioc_indicators.items():
            story.append(Paragraph(f"<b>{ioc_type.upper()}:</b>", styles['Normal']))
            for indicator in indicators[:5]:  # Limit to 5 per type
                story.append(Paragraph(f"  • {indicator}", styles['Normal']))
        story.append(PageBreak())
        
        # PAGE 8: Chain of Custody
        story.append(Paragraph("CHAIN OF CUSTODY", styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))
        
        custody_data = [['Timestamp', 'Event', 'User']]
        for event in package.chain_of_custody:
            timestamp = event.get('timestamp')
            if isinstance(timestamp, datetime):
                ts_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            else:
                ts_str = str(timestamp)
            custody_data.append([
                ts_str,
                event.get('event_type', 'N/A'),
                event.get('user', 'N/A')
            ])
        
        custody_table = Table(custody_data, colWidths=[2*inch, 2.5*inch, 1.5*inch])
        custody_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(custody_table)
        story.append(Spacer(1, 0.3*inch))
        
        story.append(Paragraph("Evidence Integrity:", styles['Heading2']))
        story.append(Paragraph(f"SHA-256 Hash: {package.evidence_hash}", styles['Normal']))
        if package.digital_signature:
            story.append(Paragraph("Digital Signature: PRESENT", styles['Normal']))
        else:
            story.append(Paragraph("Digital Signature: NOT APPLIED", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        logger.info(f"PDF report generated: {output_path}")
        return output_path
    
    def generate_json_export(self, package: EvidencePackage, output_path: str) -> str:
        """
        Export evidence package as JSON for digital forensics tools.
        
        Args:
            package: EvidencePackage to export
            output_path: Path to save JSON file
        
        Returns:
            Path to generated JSON file
        """
        data = package.to_dict()
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"JSON export generated: {output_path}")
        return output_path
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DIGITAL SIGNATURE METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def sign_evidence_package(
        self,
        package_id: str,
        private_key_path: str
    ) -> str:
        """
        Digitally sign evidence package for court admissibility.
        
        Uses RSA-2048 with PSS padding for legal chain of custody.
        
        Args:
            package_id: ID of package to sign
            private_key_path: Path to RSA private key file
        
        Returns:
            Base64-encoded digital signature
        
        Raises:
            ValueError: If package not found
            ImportError: If cryptography library not installed
        """
        package = self.packages.get(package_id)
        if not package:
            raise ValueError(f"Package {package_id} not found")
        
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
        except ImportError:
            logger.warning("Cryptography library not installed. Install with: pip install cryptography")
            return ""
        
        # Load private key
        with open(private_key_path, 'rb') as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=None
            )
        
        # Sign evidence hash
        signature = private_key.sign(
            package.evidence_hash.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Encode to base64
        signature_b64 = base64.b64encode(signature).decode()
        
        # Update package
        package.digital_signature = signature_b64
        
        # Log custody event
        self._log_custody_event(
            package_id=package_id,
            event_type='package_signed',
            user='system',
            details='Digital signature applied (RSA-2048 PSS)'
        )
        
        package.chain_of_custody.append({
            'timestamp': datetime.now(timezone.utc),
            'event_type': 'package_signed',
            'user': 'system',
            'details': 'Digital signature applied (RSA-2048 PSS)'
        })
        
        logger.info(f"Package {package_id} signed")
        return signature_b64
    
    def verify_signature(
        self,
        package_id: str,
        public_key_path: str
    ) -> bool:
        """
        Verify digital signature of evidence package.
        
        Args:
            package_id: ID of package to verify
            public_key_path: Path to RSA public key file
        
        Returns:
            True if signature is valid, False otherwise
        """
        package = self.packages.get(package_id)
        if not package or not package.digital_signature:
            return False
        
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.exceptions import InvalidSignature
        except ImportError:
            return False
        
        try:
            # Load public key
            with open(public_key_path, 'rb') as f:
                public_key = serialization.load_pem_public_key(f.read())
            
            # Decode signature
            signature = base64.b64decode(package.digital_signature)
            
            # Verify
            public_key.verify(
                signature,
                package.evidence_hash.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
            
        except (InvalidSignature, Exception) as e:
            logger.warning(f"Signature verification failed: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _generate_chain_of_custody(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Generate initial chain of custody log.
        
        Args:
            session_id: Session identifier
        
        Returns:
            List of custody events
        """
        now = datetime.now(timezone.utc)
        
        return [
            {
                'timestamp': now,
                'event_type': 'evidence_collected',
                'user': 'system',
                'details': f'Automated evidence collection initiated for session {session_id}'
            }
        ]
    
    def _collect_network_logs(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Collect network logs for session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            List of network log entries
        """
        # In production, this would query actual network logs
        # For now, return structured placeholder
        return [
            {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'session_id': session_id,
                'log_type': 'access_log',
                'source': 'phoenix_guardian',
                'note': 'Detailed network logs available from system administrator'
            }
        ]
    
    def _collect_beacon_payloads(
        self,
        interactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract beacon payload data from interactions.
        
        Args:
            interactions: List of interaction records
        
        Returns:
            List of beacon payload data
        """
        beacon_payloads = []
        
        for interaction in interactions:
            int_type = interaction.get('interaction_type') or interaction.get('type')
            if int_type == 'beacon_trigger':
                raw_data = interaction.get('raw_data', {})
                beacon_payloads.append({
                    'timestamp': interaction.get('timestamp') or interaction.get('interaction_timestamp'),
                    'honeytoken_id': interaction.get('honeytoken_id'),
                    'ip_address': interaction.get('ip_address'),
                    'canvas_fingerprint': raw_data.get('canvas_fingerprint'),
                    'webgl_vendor': raw_data.get('webgl_vendor'),
                    'webgl_renderer': raw_data.get('webgl_renderer'),
                    'installed_fonts': raw_data.get('installed_fonts', [])[:10],
                    'session_duration': raw_data.get('session_duration')
                })
        
        return beacon_payloads
    
    def _compute_evidence_hash(self, evidence_items: List[Dict[str, Any]]) -> str:
        """
        Compute SHA-256 hash of evidence for integrity verification.
        
        Args:
            evidence_items: List of evidence items
        
        Returns:
            SHA-256 hex digest
        """
        # Serialize evidence to JSON (sorted for consistency)
        evidence_json = json.dumps(evidence_items, sort_keys=True, default=str)
        
        # Compute SHA-256
        return hashlib.sha256(evidence_json.encode()).hexdigest()
    
    def _log_custody_event(
        self,
        package_id: str,
        event_type: str,
        user: str,
        details: str
    ):
        """
        Log chain of custody event.
        
        Args:
            package_id: Package ID
            event_type: Type of custody event
            user: User who performed action
            details: Event details
        """
        self.custody_log.append({
            'timestamp': datetime.now(timezone.utc),
            'package_id': package_id,
            'event_type': event_type,
            'user': user,
            'details': details
        })
    
    def _generate_ioc_for_session(
        self,
        session_id: str,
        fingerprints: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """
        Generate IOC indicators for a session.
        
        Args:
            session_id: Session identifier
            fingerprints: List of fingerprint records
        
        Returns:
            Dictionary of IOC indicators by type
        """
        iocs = {
            'ip_addresses': [],
            'user_agents': [],
            'browser_fingerprints': [],
            'canvas_fingerprints': []
        }
        
        for fp in fingerprints:
            if fp.get('ip_address'):
                ip = fp['ip_address']
                if ip not in iocs['ip_addresses']:
                    iocs['ip_addresses'].append(ip)
            
            if fp.get('user_agent'):
                ua = fp['user_agent']
                if ua not in iocs['user_agents']:
                    iocs['user_agents'].append(ua)
            
            if fp.get('browser_fingerprint'):
                bf = fp['browser_fingerprint']
                if bf not in iocs['browser_fingerprints']:
                    iocs['browser_fingerprints'].append(bf)
            
            if fp.get('canvas_fingerprint'):
                cf = fp['canvas_fingerprint']
                if cf not in iocs['canvas_fingerprints']:
                    iocs['canvas_fingerprints'].append(cf)
        
        return iocs
    
    def _dict_to_fingerprint(self, fp_dict: Dict[str, Any]) -> AttackerFingerprint:
        """
        Convert dictionary to AttackerFingerprint object.
        
        Args:
            fp_dict: Fingerprint as dictionary
        
        Returns:
            AttackerFingerprint object
        """
        # Handle timestamp
        timestamp = fp_dict.get('timestamp')
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                timestamp = datetime.now(timezone.utc)
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        return AttackerFingerprint(
            fingerprint_id=fp_dict.get('fingerprint_id', str(uuid.uuid4())),
            honeytoken_id=fp_dict.get('honeytoken_id', ''),
            ip_address=fp_dict.get('ip_address', ''),
            ip_geolocation=fp_dict.get('ip_geolocation', {}),
            user_agent=fp_dict.get('user_agent', ''),
            platform=fp_dict.get('platform', ''),
            language=fp_dict.get('language', ''),
            screen_resolution=fp_dict.get('screen_resolution', ''),
            color_depth=fp_dict.get('color_depth', 0),
            timezone=fp_dict.get('timezone', ''),
            canvas_fingerprint=fp_dict.get('canvas_fingerprint', ''),
            webgl_vendor=fp_dict.get('webgl_vendor', ''),
            webgl_renderer=fp_dict.get('webgl_renderer', ''),
            installed_fonts=fp_dict.get('installed_fonts', []),
            plugins=fp_dict.get('plugins', []),
            do_not_track=fp_dict.get('do_not_track'),
            cookies_enabled=fp_dict.get('cookies_enabled', True),
            local_storage=fp_dict.get('local_storage', True),
            session_storage=fp_dict.get('session_storage', True),
            timestamp=timestamp,
            access_pattern=fp_dict.get('access_pattern', {}),
            behavioral_data=fp_dict.get('behavioral_data', {})
        )
    
    def _dict_to_honeytoken(self, ht_dict: Dict[str, Any]) -> LegalHoneytoken:
        """
        Convert dictionary to LegalHoneytoken object.
        
        Args:
            ht_dict: Honeytoken as dictionary
        
        Returns:
            LegalHoneytoken object
        """
        # Get deployment timestamp
        deployment_ts = ht_dict.get('deployment_timestamp')
        if isinstance(deployment_ts, str):
            try:
                deployment_ts = datetime.fromisoformat(deployment_ts.replace('Z', '+00:00'))
            except:
                deployment_ts = datetime.now(timezone.utc)
        elif deployment_ts is None:
            deployment_ts = datetime.now(timezone.utc)
        
        # Get status as string value
        status = ht_dict.get('status')
        if isinstance(status, HoneytokenStatus):
            status = status.value
        elif not isinstance(status, str):
            status = HoneytokenStatus.ACTIVE.value
        
        # Get medical data
        medical_data = ht_dict.get('medical_data', {})
        
        return LegalHoneytoken(
            honeytoken_id=ht_dict.get('honeytoken_id', str(uuid.uuid4())),
            mrn=ht_dict.get('mrn', 'MRN-900000'),
            name=ht_dict.get('name', 'Unknown Patient'),
            age=ht_dict.get('age', 45),
            gender=ht_dict.get('gender', 'M'),
            address=ht_dict.get('address', '100 Main St'),
            city=ht_dict.get('city', 'Anytown'),
            state=ht_dict.get('state', 'CA'),
            zip_code=ht_dict.get('zip_code', '90210'),
            phone=ht_dict.get('phone', '555-0100'),
            email=ht_dict.get('email', 'patient@healthcare.internal'),
            conditions=medical_data.get('conditions', []) or ht_dict.get('conditions', []),
            medications=medical_data.get('medications', []) or ht_dict.get('medications', []),
            allergies=medical_data.get('allergies', []) or ht_dict.get('allergies', []),
            beacon_url=ht_dict.get('beacon_url', ''),
            session_id=ht_dict.get('session_id', ''),
            deployment_timestamp=deployment_ts,
            attack_type=ht_dict.get('attack_type', 'unknown'),
            status=status,
            attacker_ip=ht_dict.get('attacker_ip'),
            trigger_count=ht_dict.get('trigger_count', 0)
        )
    
    def get_package(self, package_id: str) -> Optional[EvidencePackage]:
        """
        Retrieve evidence package by ID.
        
        Args:
            package_id: Package identifier
        
        Returns:
            EvidencePackage if found, None otherwise
        """
        return self.packages.get(package_id)
    
    def list_packages(self) -> List[Dict[str, Any]]:
        """
        List all generated evidence packages.
        
        Returns:
            List of package summaries
        """
        return [
            {
                'package_id': pkg.package_id,
                'case_number': pkg.case_number,
                'session_id': pkg.session_id,
                'attack_type': pkg.attack_type,
                'generation_timestamp': pkg.generation_timestamp.isoformat() if pkg.generation_timestamp else None,
                'signed': pkg.digital_signature is not None
            }
            for pkg in self.packages.values()
        ]
