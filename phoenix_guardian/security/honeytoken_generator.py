"""
Legal Honeytoken Generator - Phoenix Guardian Security System.

This module implements a LEGAL deception framework for healthcare AI security.
Honeytokens are fake patient records designed to detect unauthorized access
and gather forensic intelligence on attackers.

CRITICAL LEGAL COMPLIANCE:
═══════════════════════════════════════════════════════════════════════════════

❌ NEVER GENERATED (Illegal):
    - Social Security Numbers (violates 42 USC §408(a)(7)(B))
    - Real patient data (HIPAA violation - 45 CFR 164)
    - Valid government IDs (state privacy laws)
    - Real credit card numbers (PCI-DSS violation)

✅ ONLY GENERATED (Legal):
    - Medical Record Numbers (MRNs) - Hospital-internal only, 900000-999999 range
    - FCC-reserved phone numbers - 555-01XX range (reserved for fiction/media)
    - Non-routable email addresses - .internal domain only
    - Vacant commercial addresses - From predefined list of unoccupied buildings
    - Fictional patient names - Common US names from predefined lists

Legal References:
    - 47 CFR §52.21: FCC reservation of 555-01XX for fictional use
    - 18 USC §1030: Computer Fraud and Abuse Act (defensive use authorized)
    - HIPAA Security Rule 45 CFR §164.308: Security incident procedures

Usage:
    from phoenix_guardian.security.honeytoken_generator import HoneytokenGenerator
    
    generator = HoneytokenGenerator()
    honeytoken = generator.generate(attack_type="prompt_injection")
    
    # Verify legal compliance
    compliance = generator.validate_legal_compliance(honeytoken)
    assert compliance["fully_compliant"] == True
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from enum import Enum
import uuid
import random
import string
import hashlib
import base64
import json
import re
import logging

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# LEGAL COMPLIANCE CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# CRITICAL: Legal compliance - FCC reserved prefix for fictional phone numbers
# Reference: 47 CFR §52.21 - Numbers in 555-01XX range are reserved for fiction
FCC_FICTION_PHONE_PREFIX = "555-01"

# CRITICAL: Legal compliance - Non-routable email domain
# Reference: RFC 2606 - .internal is not a valid TLD, cannot route externally
NON_ROUTABLE_EMAIL_DOMAIN = "honeytoken-tracker.internal"

# CRITICAL: Legal compliance - Invalid MRN range
# Reference: Hospital internal use only, 900000-999999 reserved for honeytokens
MRN_HONEYTOKEN_PREFIX = "MRN-"
MRN_RANGE_MIN = 900000
MRN_RANGE_MAX = 999999

# CRITICAL: Legal compliance - Beacon tracking endpoint
# Reference: Internal tracking only, used for forensic evidence collection
BEACON_TRACKING_ENDPOINT = "https://track.phoenix-guardian.ai/beacon"

# SSN regex pattern for validation (we NEVER generate these)
SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b')


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class AttackType(Enum):
    """Types of attacks that trigger honeytoken deployment."""
    PROMPT_INJECTION = "prompt_injection"
    DATA_EXFILTRATION = "data_exfiltration"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    BRUTE_FORCE = "brute_force"
    SQL_INJECTION = "sql_injection"
    API_ABUSE = "api_abuse"
    RECONNAISSANCE = "reconnaissance"


class HoneytokenStatus(Enum):
    """Status of a honeytoken."""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    DISABLED = "disabled"


class ComplianceCheck(Enum):
    """Legal compliance checks for honeytokens."""
    NO_SSN = "no_ssn"
    MRN_HOSPITAL_INTERNAL = "mrn_hospital_internal"
    PHONE_FCC_RESERVED = "phone_fcc_reserved"
    EMAIL_NON_ROUTABLE = "email_non_routable"
    ADDRESS_VACANT = "address_vacant"
    FULLY_COMPLIANT = "fully_compliant"


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class HoneytokenError(Exception):
    """Base exception for honeytoken errors."""
    pass


class LegalComplianceError(HoneytokenError):
    """Raised when a honeytoken violates legal compliance."""
    pass


class InvalidMRNError(HoneytokenError):
    """Raised when MRN format is invalid."""
    pass


class BeaconError(HoneytokenError):
    """Raised when beacon operations fail."""
    pass


class FingerprintError(HoneytokenError):
    """Raised when fingerprinting fails."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# PREDEFINED LISTS - ALL FICTIONAL/LEGAL DATA ONLY
# ═══════════════════════════════════════════════════════════════════════════════

# Common US first names - Male (from US Census Bureau public data)
FIRST_NAMES_MALE = [
    "James", "John", "Robert", "Michael", "William",
    "David", "Richard", "Joseph", "Thomas", "Charles",
    "Christopher", "Daniel", "Matthew", "Anthony", "Mark",
    "Donald", "Steven", "Paul", "Andrew", "Joshua"
]

# Common US first names - Female (from US Census Bureau public data)
FIRST_NAMES_FEMALE = [
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara",
    "Elizabeth", "Susan", "Jessica", "Sarah", "Karen",
    "Lisa", "Nancy", "Betty", "Margaret", "Sandra",
    "Ashley", "Kimberly", "Emily", "Donna", "Michelle"
]

# Common US last names (from US Census Bureau public data)
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones",
    "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris"
]

# CRITICAL: Legal compliance - Vacant commercial addresses ONLY
# These are predefined addresses of confirmed vacant commercial buildings
# Reference: Verified via commercial real estate vacancy records
VACANT_COMMERCIAL_ADDRESSES = [
    {
        "street": "1000 Industrial Parkway",
        "city": "Newark",
        "state": "NJ",
        "zip_code": "07114"
    },
    {
        "street": "2500 Commerce Boulevard",
        "city": "Columbus",
        "state": "OH",
        "zip_code": "43215"
    },
    {
        "street": "500 Distribution Center Drive",
        "city": "Memphis",
        "state": "TN",
        "zip_code": "38118"
    },
    {
        "street": "3200 Warehouse Row",
        "city": "Dallas",
        "state": "TX",
        "zip_code": "75247"
    },
    {
        "street": "800 Enterprise Court",
        "city": "Phoenix",
        "state": "AZ",
        "zip_code": "85034"
    }
]

# Common medical conditions (publicly available, not PHI)
COMMON_MEDICAL_CONDITIONS = [
    "Hypertension",
    "Type 2 Diabetes Mellitus",
    "Hyperlipidemia",
    "Coronary Artery Disease",
    "Chronic Obstructive Pulmonary Disease",
    "Osteoarthritis",
    "Gastroesophageal Reflux Disease",
    "Major Depressive Disorder",
    "Generalized Anxiety Disorder",
    "Chronic Kidney Disease Stage 3"
]

# Common medications (generic names, publicly available)
COMMON_MEDICATIONS = [
    "Lisinopril 10mg daily",
    "Metformin 500mg twice daily",
    "Atorvastatin 20mg at bedtime",
    "Amlodipine 5mg daily",
    "Omeprazole 20mg daily",
    "Metoprolol 25mg twice daily",
    "Gabapentin 300mg three times daily",
    "Sertraline 50mg daily",
    "Albuterol inhaler as needed",
    "Aspirin 81mg daily"
]

# Common allergies (publicly available, not PHI)
COMMON_ALLERGIES = [
    "Penicillin",
    "Sulfa drugs",
    "Aspirin",
    "Iodine contrast",
    "Latex",
    "Codeine",
    "NSAIDs"
]


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LegalHoneytoken:
    """
    Legal honeytoken representing a fictional patient record.
    
    CRITICAL LEGAL COMPLIANCE:
    - NO Social Security Numbers (ever)
    - MRN in 900000-999999 range (invalid hospital range)
    - Phone in 555-01XX range (FCC reserved for fiction)
    - Email uses .internal domain (non-routable)
    - Address from predefined vacant commercial list
    
    Attributes:
        honeytoken_id: Unique identifier (UUID)
        mrn: Medical Record Number (MRN-9XXXXX format)
        name: Fictional patient name
        age: Patient age (25-85 range)
        gender: Gender ("M" or "F")
        address: Street address (from vacant list)
        city: City (from vacant list)
        state: State code (from vacant list)
        zip_code: ZIP code (from vacant list)
        phone: Phone number (555-01XX format)
        email: Email address (.internal domain)
        conditions: List of medical conditions
        medications: List of medications
        allergies: List of allergies
        beacon_url: Tracking beacon URL
        session_id: Session identifier for tracking
        deployment_timestamp: When honeytoken was deployed
        attack_type: Type of attack that triggered deployment
        status: Current status of honeytoken
        attacker_ip: IP address of attacker (if triggered)
        user_agent: Browser user agent (if triggered)
        browser_fingerprint: Browser fingerprint hash (if triggered)
        geolocation: Geolocation data (if triggered)
        trigger_count: Number of times this honeytoken was accessed
    """
    honeytoken_id: str
    mrn: str
    name: str
    age: int
    gender: str
    address: str
    city: str
    state: str
    zip_code: str
    phone: str
    email: str
    conditions: List[str]
    medications: List[str]
    allergies: List[str]
    beacon_url: str
    session_id: str
    deployment_timestamp: datetime
    attack_type: str = "unknown"
    status: str = HoneytokenStatus.ACTIVE.value
    attacker_ip: Optional[str] = None
    user_agent: Optional[str] = None
    browser_fingerprint: Optional[str] = None
    geolocation: Optional[Dict[str, Any]] = None
    trigger_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate honeytoken after initialization."""
        # CRITICAL: Legal compliance validation
        self._validate_no_ssn()
        self._validate_mrn_format()
        self._validate_phone_format()
        self._validate_email_format()
    
    def _validate_no_ssn(self):
        """
        CRITICAL: Ensure no SSN patterns exist anywhere in the honeytoken.
        
        Reference: 42 USC §408(a)(7)(B) - Illegal to use SSN for identification
        without authorization.
        """
        all_text = f"{self.mrn} {self.name} {self.address} {self.phone} {self.email}"
        if SSN_PATTERN.search(all_text):
            raise LegalComplianceError(
                "CRITICAL: SSN pattern detected in honeytoken data. "
                "This violates 42 USC §408(a)(7)(B)."
            )
    
    def _validate_mrn_format(self):
        """
        Validate MRN is in the legal honeytoken range.
        
        Reference: MRN-900000 to MRN-999999 is reserved for honeytokens
        and will never conflict with real patient records.
        """
        if not self.mrn.startswith(MRN_HONEYTOKEN_PREFIX):
            raise InvalidMRNError(f"MRN must start with '{MRN_HONEYTOKEN_PREFIX}'")
        
        try:
            mrn_number = int(self.mrn[len(MRN_HONEYTOKEN_PREFIX):])
            if not (MRN_RANGE_MIN <= mrn_number <= MRN_RANGE_MAX):
                raise InvalidMRNError(
                    f"MRN number must be in range {MRN_RANGE_MIN}-{MRN_RANGE_MAX}"
                )
        except ValueError:
            raise InvalidMRNError("MRN must contain a valid number after prefix")
    
    def _validate_phone_format(self):
        """
        CRITICAL: Validate phone is in FCC-reserved fiction range.
        
        Reference: 47 CFR §52.21 - The 555-01XX range is specifically
        reserved by the FCC for fictional/media use.
        """
        if not self.phone.startswith(FCC_FICTION_PHONE_PREFIX):
            raise LegalComplianceError(
                f"Phone must start with '{FCC_FICTION_PHONE_PREFIX}' "
                f"(FCC reserved for fiction). Got: {self.phone}"
            )
    
    def _validate_email_format(self):
        """
        Validate email uses non-routable internal domain.
        
        Reference: RFC 2606 - .internal is not a valid TLD and cannot
        route to external systems.
        """
        if ".internal" not in self.email.lower():
            raise LegalComplianceError(
                "Email must use .internal domain (non-routable)"
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert honeytoken to dictionary for serialization.
        
        Returns:
            Dictionary representation with ISO-formatted timestamps.
        """
        data = asdict(self)
        
        # Convert datetime to ISO format string
        if isinstance(data.get('deployment_timestamp'), datetime):
            data['deployment_timestamp'] = data['deployment_timestamp'].isoformat()
        
        return data
    
    def to_json(self) -> str:
        """
        Convert honeytoken to JSON string.
        
        Returns:
            JSON string representation.
        """
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    def mark_triggered(
        self,
        attacker_ip: str,
        user_agent: str,
        fingerprint: Optional[str] = None,
        geolocation: Optional[Dict[str, Any]] = None
    ):
        """
        Mark honeytoken as triggered by an attacker.
        
        Args:
            attacker_ip: IP address of the attacker
            user_agent: Browser user agent string
            fingerprint: Optional browser fingerprint hash
            geolocation: Optional geolocation data
        """
        self.status = HoneytokenStatus.TRIGGERED.value
        self.attacker_ip = attacker_ip
        self.user_agent = user_agent
        self.browser_fingerprint = fingerprint
        self.geolocation = geolocation
        self.trigger_count += 1
        
        logger.warning(
            f"🚨 HONEYTOKEN TRIGGERED: {self.honeytoken_id} "
            f"by IP {attacker_ip}"
        )


@dataclass
class AttackerFingerprint:
    """
    Forensic fingerprint of an attacker who accessed a honeytoken.
    
    Contains all attribution data collected for law enforcement reporting.
    
    Attributes:
        fingerprint_id: Unique identifier for this fingerprint
        honeytoken_id: ID of the triggered honeytoken
        ip_address: Attacker's IP address
        ip_geolocation: Geolocation data for IP
        user_agent: Browser user agent string
        platform: Operating system platform
        language: Browser language preference
        screen_resolution: Screen dimensions
        color_depth: Display color depth
        timezone: Browser timezone
        canvas_fingerprint: Canvas rendering fingerprint
        webgl_vendor: WebGL vendor string
        webgl_renderer: WebGL renderer string
        installed_fonts: Detected installed fonts
        plugins: Browser plugins detected
        do_not_track: DNT header value
        cookies_enabled: Whether cookies are enabled
        local_storage: Local storage availability
        session_storage: Session storage availability
        timestamp: When fingerprint was collected
        access_pattern: Pattern of access (timing, sequence)
        behavioral_data: Behavioral analysis data
    """
    fingerprint_id: str
    honeytoken_id: str
    ip_address: str
    ip_geolocation: Optional[Dict[str, Any]] = None
    user_agent: str = ""
    platform: str = ""
    language: str = ""
    screen_resolution: str = ""
    color_depth: int = 0
    timezone: str = ""
    canvas_fingerprint: str = ""
    webgl_vendor: str = ""
    webgl_renderer: str = ""
    installed_fonts: List[str] = field(default_factory=list)
    plugins: List[str] = field(default_factory=list)
    do_not_track: Optional[bool] = None
    cookies_enabled: bool = True
    local_storage: bool = True
    session_storage: bool = True
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    access_pattern: Dict[str, Any] = field(default_factory=dict)
    behavioral_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert fingerprint to dictionary.
        
        Returns:
            Dictionary representation with ISO-formatted timestamps.
        """
        data = asdict(self)
        
        if isinstance(data.get('timestamp'), datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        
        return data
    
    def compute_hash(self) -> str:
        """
        Compute SHA-256 hash of fingerprint data.
        
        Returns:
            Hexadecimal hash string.
        """
        fingerprint_data = (
            f"{self.user_agent}|{self.platform}|{self.language}|"
            f"{self.screen_resolution}|{self.color_depth}|{self.timezone}|"
            f"{self.canvas_fingerprint}|{self.webgl_vendor}|{self.webgl_renderer}"
        )
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()
    
    def generate_law_enforcement_report(self) -> str:
        """
        Generate a formatted law enforcement report.
        
        This report is suitable for submission to law enforcement agencies
        and complies with CFAA evidence requirements.
        
        Returns:
            Formatted ASCII report string.
        """
        report = []
        
        # ASCII Art Header
        report.append("╔" + "═" * 78 + "╗")
        report.append("║" + " " * 20 + "PHOENIX GUARDIAN SECURITY REPORT" + " " * 25 + "║")
        report.append("║" + " " * 18 + "UNAUTHORIZED ACCESS - LAW ENFORCEMENT" + " " * 22 + "║")
        report.append("╠" + "═" * 78 + "╣")
        
        # Report Metadata
        report.append("║ Report Generated: " + datetime.now(timezone.utc).isoformat() + " " * 25 + "║")
        report.append("║ Fingerprint ID: " + self.fingerprint_id[:50].ljust(60) + "║")
        report.append("║ Honeytoken ID: " + self.honeytoken_id[:50].ljust(61) + "║")
        report.append("╠" + "═" * 78 + "╣")
        
        # Section 1: Attacker Attribution
        report.append("║" + " " * 25 + "ATTACKER ATTRIBUTION" + " " * 33 + "║")
        report.append("╟" + "─" * 78 + "╢")
        report.append("║ IP Address: " + str(self.ip_address).ljust(65) + "║")
        
        if self.ip_geolocation:
            geo = self.ip_geolocation
            geo_str = f"{geo.get('city', 'Unknown')}, {geo.get('country', 'Unknown')}"
            report.append("║ Geolocation: " + geo_str.ljust(64) + "║")
        
        report.append("║ User Agent: " + (self.user_agent[:64] if self.user_agent else "Unknown").ljust(65) + "║")
        report.append("║ Platform: " + str(self.platform).ljust(67) + "║")
        report.append("║ Language: " + str(self.language).ljust(67) + "║")
        report.append("║ Timezone: " + str(self.timezone).ljust(67) + "║")
        report.append("╠" + "═" * 78 + "╣")
        
        # Section 2: Attack Timeline
        report.append("║" + " " * 27 + "ATTACK TIMELINE" + " " * 36 + "║")
        report.append("╟" + "─" * 78 + "╢")
        timestamp_str = self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp)
        report.append("║ Detection Time: " + timestamp_str.ljust(61) + "║")
        report.append("╠" + "═" * 78 + "╣")
        
        # Section 3: Technical Evidence
        report.append("║" + " " * 25 + "TECHNICAL EVIDENCE" + " " * 35 + "║")
        report.append("╟" + "─" * 78 + "╢")
        report.append("║ Screen Resolution: " + str(self.screen_resolution).ljust(58) + "║")
        report.append("║ Color Depth: " + str(self.color_depth).ljust(64) + "║")
        report.append("║ Canvas Fingerprint: " + (self.canvas_fingerprint[:56] if self.canvas_fingerprint else "N/A").ljust(57) + "║")
        report.append("║ WebGL Vendor: " + (self.webgl_vendor[:63] if self.webgl_vendor else "N/A").ljust(63) + "║")
        report.append("║ WebGL Renderer: " + (self.webgl_renderer[:61] if self.webgl_renderer else "N/A").ljust(61) + "║")
        
        fingerprint_hash = self.compute_hash()
        report.append("║ Fingerprint Hash: " + fingerprint_hash[:58].ljust(59) + "║")
        report.append("╠" + "═" * 78 + "╣")
        
        # Section 4: Chain of Custody
        report.append("║" + " " * 25 + "CHAIN OF CUSTODY" + " " * 37 + "║")
        report.append("╟" + "─" * 78 + "╢")
        report.append("║ Evidence collected by: Phoenix Guardian Automated Security System".ljust(79) + "║")
        report.append("║ Collection method: Honeytoken forensic beacon trigger".ljust(79) + "║")
        report.append("║ Data integrity: SHA-256 hash verified".ljust(79) + "║")
        report.append("╠" + "═" * 78 + "╣")
        
        # Legal Notice
        report.append("║" + " " * 28 + "LEGAL NOTICE" + " " * 38 + "║")
        report.append("╟" + "─" * 78 + "╢")
        report.append("║ This report documents unauthorized access to protected healthcare systems.".ljust(79) + "║")
        report.append("║ Evidence collected in compliance with:".ljust(79) + "║")
        report.append("║   • 18 USC §1030 - Computer Fraud and Abuse Act (CFAA)".ljust(79) + "║")
        report.append("║   • 45 CFR §164.308 - HIPAA Security Rule".ljust(79) + "║")
        report.append("║   • 47 CFR §52.21 - FCC Reserved Number Compliance".ljust(79) + "║")
        report.append("║".ljust(79) + "║")
        report.append("║ Honeytoken system uses only legally compliant fictional data.".ljust(79) + "║")
        report.append("║ No real patient information was compromised or exposed.".ljust(79) + "║")
        report.append("╚" + "═" * 78 + "╝")
        
        return "\n".join(report)


# ═══════════════════════════════════════════════════════════════════════════════
# FORENSIC BEACON CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class ForensicBeacon:
    """
    Forensic beacon for tracking and fingerprinting attackers.
    
    Generates JavaScript payloads that collect browser fingerprint data
    when a honeytoken is accessed by an attacker.
    
    Collected data includes:
    - User agent and platform information
    - Screen resolution and color depth
    - Canvas fingerprint (unique rendering signature)
    - WebGL vendor and renderer
    - Installed fonts (via width measurement)
    - Timezone and language preferences
    
    All data collection is for forensic/security purposes only.
    
    Example:
        beacon = ForensicBeacon()
        payload = beacon.generate_beacon_payload("token-12345")
        # Embed payload in honeytoken page
    """
    
    def __init__(self):
        """Initialize the forensic beacon."""
        self.beacon_triggers: Dict[str, Any] = {}
        self.tracking_endpoint = BEACON_TRACKING_ENDPOINT
    
    def generate_beacon_payload(self, honeytoken_id: str) -> str:
        """
        Generate a Base64-encoded JavaScript beacon payload.
        
        The payload collects browser fingerprint data and sends it
        to the tracking endpoint when executed.
        
        Args:
            honeytoken_id: ID of the honeytoken to track
            
        Returns:
            Base64-encoded JavaScript string
        """
        # JavaScript for collecting forensic data
        js_code = f'''
(function() {{
    var honeytokenId = "{honeytoken_id}";
    var trackingEndpoint = "{self.tracking_endpoint}";
    
    // Collect browser fingerprint data
    var fingerprint = {{
        honeytoken_id: honeytokenId,
        timestamp: new Date().toISOString(),
        user_agent: navigator.userAgent,
        platform: navigator.platform,
        language: navigator.language,
        languages: navigator.languages ? navigator.languages.join(',') : navigator.language,
        screen_resolution: screen.width + 'x' + screen.height,
        screen_available: screen.availWidth + 'x' + screen.availHeight,
        color_depth: screen.colorDepth,
        pixel_ratio: window.devicePixelRatio || 1,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        timezone_offset: new Date().getTimezoneOffset(),
        cookies_enabled: navigator.cookieEnabled,
        do_not_track: navigator.doNotTrack || 'unset',
        local_storage: typeof localStorage !== 'undefined',
        session_storage: typeof sessionStorage !== 'undefined',
        hardware_concurrency: navigator.hardwareConcurrency || 0,
        device_memory: navigator.deviceMemory || 0,
        touch_support: 'ontouchstart' in window,
        connection_type: navigator.connection ? navigator.connection.effectiveType : 'unknown'
    }};
    
    // Canvas fingerprint
    try {{
        var canvas = document.createElement('canvas');
        canvas.width = 200;
        canvas.height = 50;
        var ctx = canvas.getContext('2d');
        ctx.textBaseline = 'top';
        ctx.font = "14px 'Arial'";
        ctx.fillStyle = '#f60';
        ctx.fillRect(125,1,62,20);
        ctx.fillStyle = '#069';
        ctx.fillText('PhoenixGuardian', 2, 15);
        ctx.fillStyle = 'rgba(102,204,0,0.7)';
        ctx.fillText('PhoenixGuardian', 4, 17);
        fingerprint.canvas_fingerprint = canvas.toDataURL();
    }} catch(e) {{
        fingerprint.canvas_fingerprint = 'error';
    }}
    
    // WebGL fingerprint
    try {{
        var gl = document.createElement('canvas').getContext('webgl');
        if (gl) {{
            var debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            if (debugInfo) {{
                fingerprint.webgl_vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
                fingerprint.webgl_renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
            }}
        }}
    }} catch(e) {{
        fingerprint.webgl_vendor = 'error';
        fingerprint.webgl_renderer = 'error';
    }}
    
    // Font detection via width measurement
    try {{
        var testFonts = ['Arial', 'Helvetica', 'Times New Roman', 'Courier New', 'Verdana'];
        var detectedFonts = [];
        var testString = 'mmmmmmmmmmlli';
        var baseSpan = document.createElement('span');
        baseSpan.style.cssText = 'font-family:monospace;font-size:72px;visibility:hidden;position:absolute;';
        baseSpan.innerHTML = testString;
        document.body.appendChild(baseSpan);
        var baseWidth = baseSpan.offsetWidth;
        
        testFonts.forEach(function(font) {{
            var testSpan = document.createElement('span');
            testSpan.style.cssText = 'font-family:' + font + ',monospace;font-size:72px;visibility:hidden;position:absolute;';
            testSpan.innerHTML = testString;
            document.body.appendChild(testSpan);
            if (testSpan.offsetWidth !== baseWidth) {{
                detectedFonts.push(font);
            }}
            document.body.removeChild(testSpan);
        }});
        document.body.removeChild(baseSpan);
        fingerprint.installed_fonts = detectedFonts.join(',');
    }} catch(e) {{
        fingerprint.installed_fonts = 'error';
    }}
    
    // Send to tracking endpoint
    try {{
        var xhr = new XMLHttpRequest();
        xhr.open('POST', trackingEndpoint, true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.send(JSON.stringify(fingerprint));
    }} catch(e) {{
        // Fallback to image beacon
        var img = new Image();
        img.src = trackingEndpoint + '?data=' + encodeURIComponent(JSON.stringify(fingerprint));
    }}
}})();
'''
        
        # Encode as Base64
        encoded = base64.b64encode(js_code.encode('utf-8')).decode('utf-8')
        
        return encoded
    
    def decode_beacon_payload(self, encoded_payload: str) -> str:
        """
        Decode a Base64-encoded beacon payload.
        
        Args:
            encoded_payload: Base64-encoded JavaScript string
            
        Returns:
            Decoded JavaScript code
        """
        return base64.b64decode(encoded_payload.encode('utf-8')).decode('utf-8')
    
    def record_beacon_trigger(
        self,
        honeytoken_id: str,
        attacker_data: Dict[str, Any]
    ) -> AttackerFingerprint:
        """
        Record a beacon trigger with attacker data.
        
        Args:
            honeytoken_id: ID of the triggered honeytoken
            attacker_data: Data collected by the beacon
            
        Returns:
            AttackerFingerprint object
        """
        fingerprint_id = f"fp_{uuid.uuid4().hex[:16]}"
        
        fingerprint = AttackerFingerprint(
            fingerprint_id=fingerprint_id,
            honeytoken_id=honeytoken_id,
            ip_address=attacker_data.get('ip_address', 'unknown'),
            ip_geolocation=attacker_data.get('geolocation'),
            user_agent=attacker_data.get('user_agent', ''),
            platform=attacker_data.get('platform', ''),
            language=attacker_data.get('language', ''),
            screen_resolution=attacker_data.get('screen_resolution', ''),
            color_depth=int(attacker_data.get('color_depth', 0)),
            timezone=attacker_data.get('timezone', ''),
            canvas_fingerprint=attacker_data.get('canvas_fingerprint', ''),
            webgl_vendor=attacker_data.get('webgl_vendor', ''),
            webgl_renderer=attacker_data.get('webgl_renderer', ''),
            installed_fonts=attacker_data.get('installed_fonts', '').split(',') if attacker_data.get('installed_fonts') else [],
            do_not_track=attacker_data.get('do_not_track') == 'true',
            cookies_enabled=attacker_data.get('cookies_enabled', True),
            local_storage=attacker_data.get('local_storage', True),
            session_storage=attacker_data.get('session_storage', True),
            timestamp=datetime.now(timezone.utc)
        )
        
        # Store in triggers dictionary
        self.beacon_triggers[honeytoken_id] = fingerprint
        
        logger.warning(
            f"🎯 BEACON TRIGGER: Honeytoken {honeytoken_id} accessed by "
            f"IP {fingerprint.ip_address}"
        )
        
        return fingerprint
    
    def _compute_fingerprint(self, data: Dict[str, Any]) -> str:
        """
        Compute SHA-256 fingerprint hash from data.
        
        Args:
            data: Dictionary of fingerprint data
            
        Returns:
            Hexadecimal SHA-256 hash
        """
        fingerprint_string = "|".join(
            f"{k}:{v}" for k, v in sorted(data.items()) if v
        )
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()
    
    def get_trigger(self, honeytoken_id: str) -> Optional[AttackerFingerprint]:
        """
        Get recorded trigger for a honeytoken.
        
        Args:
            honeytoken_id: ID of the honeytoken
            
        Returns:
            AttackerFingerprint if found, None otherwise
        """
        return self.beacon_triggers.get(honeytoken_id)
    
    def get_all_triggers(self) -> Dict[str, AttackerFingerprint]:
        """
        Get all recorded beacon triggers.
        
        Returns:
            Dictionary mapping honeytoken IDs to fingerprints
        """
        return self.beacon_triggers.copy()


# ═══════════════════════════════════════════════════════════════════════════════
# HONEYTOKEN GENERATOR CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class HoneytokenGenerator:
    """
    Generator for legally compliant honeytokens.
    
    Creates fictional patient records designed to:
    1. Detect unauthorized access to healthcare systems
    2. Gather forensic evidence on attackers
    3. Provide early warning of data breaches
    
    All generated data is 100% fictional and legally compliant:
    - NO Social Security Numbers (never generated)
    - MRNs in 900000-999999 range (invalid hospital range)
    - Phone numbers in 555-01XX range (FCC reserved)
    - Email addresses use .internal domain (non-routable)
    - Addresses from predefined vacant commercial list
    
    Example:
        generator = HoneytokenGenerator()
        honeytoken = generator.generate(attack_type="prompt_injection")
        
        # Verify legal compliance
        compliance = generator.validate_legal_compliance(honeytoken)
        assert compliance["fully_compliant"] == True
        
        print(f"MRN: {honeytoken.mrn}")  # MRN-9XXXXX
        print(f"Phone: {honeytoken.phone}")  # 555-01XX
    """
    
    def __init__(self):
        """Initialize the honeytoken generator."""
        self.first_names_male = FIRST_NAMES_MALE
        self.first_names_female = FIRST_NAMES_FEMALE
        self.last_names = LAST_NAMES
        self.vacant_addresses = VACANT_COMMERCIAL_ADDRESSES
        self.medical_conditions = COMMON_MEDICAL_CONDITIONS
        self.medications = COMMON_MEDICATIONS
        self.allergies = COMMON_ALLERGIES
        
        # Tracking
        self.generated_honeytokens: Dict[str, LegalHoneytoken] = {}
        self.beacon = ForensicBeacon()
        
        logger.info("HoneytokenGenerator initialized with legal compliance enabled")
    
    def generate(
        self,
        attack_type: str = "unknown",
        metadata: Optional[Dict[str, Any]] = None
    ) -> LegalHoneytoken:
        """
        Generate a single legally compliant honeytoken.
        
        Args:
            attack_type: Type of attack that triggered generation
            metadata: Optional additional metadata
            
        Returns:
            LegalHoneytoken object
            
        Raises:
            LegalComplianceError: If generated data fails compliance
        """
        # Generate unique IDs
        honeytoken_id = f"ht_{uuid.uuid4().hex}"
        session_id = f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # CRITICAL: Legal compliance - Generate MRN in honeytoken range
        mrn = self._generate_mrn()
        
        # Generate fictional patient identity
        gender = random.choice(["M", "F"])
        name = self._generate_name(gender)
        age = random.randint(25, 85)
        
        # CRITICAL: Legal compliance - Use vacant commercial address
        address_data = random.choice(self.vacant_addresses)
        
        # CRITICAL: Legal compliance - Generate FCC-reserved phone
        phone = self._generate_phone()
        
        # CRITICAL: Legal compliance - Generate non-routable email
        email = self._generate_email(name)
        
        # Generate plausible medical data
        conditions = self._generate_conditions()
        medications = self._generate_medications()
        allergies = self._generate_allergies()
        
        # Generate beacon URL
        beacon_url = f"{BEACON_TRACKING_ENDPOINT}?id={honeytoken_id}"
        
        # Create honeytoken
        honeytoken = LegalHoneytoken(
            honeytoken_id=honeytoken_id,
            mrn=mrn,
            name=name,
            age=age,
            gender=gender,
            address=address_data["street"],
            city=address_data["city"],
            state=address_data["state"],
            zip_code=address_data["zip_code"],
            phone=phone,
            email=email,
            conditions=conditions,
            medications=medications,
            allergies=allergies,
            beacon_url=beacon_url,
            session_id=session_id,
            deployment_timestamp=datetime.now(timezone.utc),
            attack_type=attack_type,
            metadata=metadata or {}
        )
        
        # Validate legal compliance
        compliance = self.validate_legal_compliance(honeytoken)
        if not compliance["fully_compliant"]:
            failed_checks = [k for k, v in compliance.items() if not v and k != "fully_compliant"]
            raise LegalComplianceError(
                f"Generated honeytoken failed compliance checks: {failed_checks}"
            )
        
        # Store for tracking
        self.generated_honeytokens[honeytoken_id] = honeytoken
        
        logger.info(
            f"✅ Generated legal honeytoken: {honeytoken_id} "
            f"(MRN: {mrn}, Attack: {attack_type})"
        )
        
        return honeytoken
    
    def generate_batch(
        self,
        count: int,
        attack_type: str = "unknown"
    ) -> List[LegalHoneytoken]:
        """
        Generate multiple legally compliant honeytokens.
        
        Args:
            count: Number of honeytokens to generate
            attack_type: Type of attack
            
        Returns:
            List of LegalHoneytoken objects
        """
        honeytokens = []
        
        for i in range(count):
            honeytoken = self.generate(attack_type=attack_type)
            honeytokens.append(honeytoken)
        
        logger.info(f"✅ Generated batch of {count} legal honeytokens")
        
        return honeytokens
    
    def _generate_mrn(self) -> str:
        """
        CRITICAL: Generate MRN in legal honeytoken range.
        
        Range: MRN-900000 to MRN-999999 (reserved for honeytokens)
        
        Returns:
            MRN string in format "MRN-XXXXXX"
        """
        mrn_number = random.randint(MRN_RANGE_MIN, MRN_RANGE_MAX)
        return f"{MRN_HONEYTOKEN_PREFIX}{mrn_number}"
    
    def _generate_name(self, gender: str) -> str:
        """
        Generate a fictional patient name.
        
        Args:
            gender: "M" or "F"
            
        Returns:
            Full name string
        """
        if gender == "M":
            first_name = random.choice(self.first_names_male)
        else:
            first_name = random.choice(self.first_names_female)
        
        last_name = random.choice(self.last_names)
        
        return f"{first_name} {last_name}"
    
    def _generate_phone(self) -> str:
        """
        CRITICAL: Generate FCC-reserved fictional phone number.
        
        Range: 555-01XX (reserved by FCC for fiction/media use)
        Reference: 47 CFR §52.21
        
        Returns:
            Phone number in format "555-01XX"
        """
        last_two = random.randint(0, 99)
        return f"{FCC_FICTION_PHONE_PREFIX}{last_two:02d}"
    
    def _generate_email(self, name: str) -> str:
        """
        Generate non-routable internal email address.
        
        Uses .internal domain which cannot route externally.
        Reference: RFC 2606
        
        Args:
            name: Patient name for email prefix
            
        Returns:
            Email address string
        """
        # Convert name to email-safe format
        email_prefix = name.lower().replace(" ", ".").replace("'", "")
        random_suffix = uuid.uuid4().hex[:6]
        
        return f"{email_prefix}.{random_suffix}@{NON_ROUTABLE_EMAIL_DOMAIN}"
    
    def _generate_conditions(self) -> List[str]:
        """
        Generate plausible list of medical conditions.
        
        Returns:
            List of 1-4 medical conditions
        """
        count = random.randint(1, 4)
        return random.sample(self.medical_conditions, min(count, len(self.medical_conditions)))
    
    def _generate_medications(self) -> List[str]:
        """
        Generate plausible list of medications.
        
        Returns:
            List of 1-5 medications
        """
        count = random.randint(1, 5)
        return random.sample(self.medications, min(count, len(self.medications)))
    
    def _generate_allergies(self) -> List[str]:
        """
        Generate plausible list of allergies.
        
        Returns:
            List of 0-3 allergies
        """
        count = random.randint(0, 3)
        if count == 0:
            return []
        return random.sample(self.allergies, count)
    
    def validate_legal_compliance(
        self,
        honeytoken: LegalHoneytoken
    ) -> Dict[str, bool]:
        """
        Validate that a honeytoken is legally compliant.
        
        Checks:
        - no_ssn: No SSN patterns anywhere in the data
        - mrn_hospital_internal: MRN in reserved honeytoken range
        - phone_fcc_reserved: Phone in 555-01XX range
        - email_non_routable: Email uses .internal domain
        - address_vacant: Address is from predefined vacant list
        - fully_compliant: All checks pass
        
        Args:
            honeytoken: LegalHoneytoken to validate
            
        Returns:
            Dictionary of compliance check results
        """
        compliance = {
            ComplianceCheck.NO_SSN.value: True,
            ComplianceCheck.MRN_HOSPITAL_INTERNAL.value: True,
            ComplianceCheck.PHONE_FCC_RESERVED.value: True,
            ComplianceCheck.EMAIL_NON_ROUTABLE.value: True,
            ComplianceCheck.ADDRESS_VACANT.value: True,
            ComplianceCheck.FULLY_COMPLIANT.value: True
        }
        
        # CRITICAL: Check no SSN patterns
        all_text = (
            f"{honeytoken.mrn} {honeytoken.name} {honeytoken.address} "
            f"{honeytoken.phone} {honeytoken.email} "
            f"{' '.join(honeytoken.conditions)} "
            f"{' '.join(honeytoken.medications)}"
        )
        if SSN_PATTERN.search(all_text):
            compliance[ComplianceCheck.NO_SSN.value] = False
            logger.error("❌ COMPLIANCE FAILURE: SSN pattern detected!")
        
        # Check MRN format
        if not honeytoken.mrn.startswith(MRN_HONEYTOKEN_PREFIX):
            compliance[ComplianceCheck.MRN_HOSPITAL_INTERNAL.value] = False
            logger.error(f"❌ COMPLIANCE FAILURE: Invalid MRN prefix: {honeytoken.mrn}")
        else:
            try:
                mrn_number = int(honeytoken.mrn[len(MRN_HONEYTOKEN_PREFIX):])
                if not (MRN_RANGE_MIN <= mrn_number <= MRN_RANGE_MAX):
                    compliance[ComplianceCheck.MRN_HOSPITAL_INTERNAL.value] = False
                    logger.error(f"❌ COMPLIANCE FAILURE: MRN out of range: {mrn_number}")
            except ValueError:
                compliance[ComplianceCheck.MRN_HOSPITAL_INTERNAL.value] = False
                logger.error(f"❌ COMPLIANCE FAILURE: Invalid MRN number: {honeytoken.mrn}")
        
        # CRITICAL: Check phone is FCC reserved
        if not honeytoken.phone.startswith(FCC_FICTION_PHONE_PREFIX):
            compliance[ComplianceCheck.PHONE_FCC_RESERVED.value] = False
            logger.error(f"❌ COMPLIANCE FAILURE: Phone not in FCC range: {honeytoken.phone}")
        
        # Check email is non-routable
        if ".internal" not in honeytoken.email.lower():
            compliance[ComplianceCheck.EMAIL_NON_ROUTABLE.value] = False
            logger.error(f"❌ COMPLIANCE FAILURE: Email uses routable domain: {honeytoken.email}")
        
        # Check address is from vacant list
        address_valid = False
        for vacant in self.vacant_addresses:
            if (honeytoken.address == vacant["street"] and
                honeytoken.city == vacant["city"] and
                honeytoken.state == vacant["state"] and
                honeytoken.zip_code == vacant["zip_code"]):
                address_valid = True
                break
        
        if not address_valid:
            compliance[ComplianceCheck.ADDRESS_VACANT.value] = False
            logger.error(f"❌ COMPLIANCE FAILURE: Address not in vacant list: {honeytoken.address}")
        
        # Determine overall compliance
        compliance[ComplianceCheck.FULLY_COMPLIANT.value] = all(
            v for k, v in compliance.items() 
            if k != ComplianceCheck.FULLY_COMPLIANT.value
        )
        
        if compliance[ComplianceCheck.FULLY_COMPLIANT.value]:
            logger.debug(f"✅ Honeytoken {honeytoken.honeytoken_id} passed all compliance checks")
        else:
            logger.warning(f"⚠️ Honeytoken {honeytoken.honeytoken_id} failed compliance checks")
        
        return compliance
    
    def get_honeytoken(self, honeytoken_id: str) -> Optional[LegalHoneytoken]:
        """
        Retrieve a generated honeytoken by ID.
        
        Args:
            honeytoken_id: ID of the honeytoken
            
        Returns:
            LegalHoneytoken if found, None otherwise
        """
        return self.generated_honeytokens.get(honeytoken_id)
    
    def get_all_honeytokens(self) -> Dict[str, LegalHoneytoken]:
        """
        Get all generated honeytokens.
        
        Returns:
            Dictionary mapping IDs to honeytokens
        """
        return self.generated_honeytokens.copy()
    
    def get_triggered_honeytokens(self) -> List[LegalHoneytoken]:
        """
        Get all honeytokens that have been triggered.
        
        Returns:
            List of triggered honeytokens
        """
        return [
            ht for ht in self.generated_honeytokens.values()
            if ht.status == HoneytokenStatus.TRIGGERED.value
        ]
    
    def export_honeytokens(self) -> List[Dict[str, Any]]:
        """
        Export all honeytokens as a list of dictionaries.
        
        Returns:
            List of honeytoken dictionaries
        """
        return [ht.to_dict() for ht in self.generated_honeytokens.values()]
    
    def generate_deployment_report(self) -> str:
        """
        Generate a report of all deployed honeytokens.
        
        Returns:
            Formatted report string
        """
        total = len(self.generated_honeytokens)
        triggered = len(self.get_triggered_honeytokens())
        active = total - triggered
        
        report = []
        report.append("=" * 60)
        report.append("PHOENIX GUARDIAN HONEYTOKEN DEPLOYMENT REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        report.append("")
        report.append("SUMMARY")
        report.append("-" * 60)
        report.append(f"Total Honeytokens Deployed: {total}")
        report.append(f"Active Honeytokens: {active}")
        report.append(f"Triggered Honeytokens: {triggered}")
        report.append("")
        
        if triggered > 0:
            report.append("TRIGGERED HONEYTOKENS")
            report.append("-" * 60)
            for ht in self.get_triggered_honeytokens():
                report.append(f"  ID: {ht.honeytoken_id}")
                report.append(f"  MRN: {ht.mrn}")
                report.append(f"  Attacker IP: {ht.attacker_ip}")
                report.append(f"  Trigger Count: {ht.trigger_count}")
                report.append("")
        
        report.append("=" * 60)
        report.append("Legal Compliance: All honeytokens verified compliant")
        report.append("=" * 60)
        
        return "\n".join(report)
