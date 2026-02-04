"""
Phoenix Guardian Security Module.

This module provides advanced security features including:
- ML-based threat detection (RoBERTa + Random Forest)
- Honeytoken system for attacker tracking
- Deception agent for intelligent honeytoken deployment
- Post-quantum cryptography (AES-256 + Kyber-1024)
- Simple Fernet encryption for PII/PHI
- Attacker intelligence database (PostgreSQL-backed)
- Threat intelligence analysis (STIX 2.1 export, IOC feeds)
- Comprehensive audit logging for HIPAA compliance

Phase 2 Implementation:
- Week 9: ML threat detector
- Week 15: Honeytoken system
- Week 16: Post-quantum crypto
- Week 17: Attacker intelligence database

Phase 3 Implementation (Week 4):
- Fernet encryption service for PII
- Audit logger service
- SecurityIncident integration
"""

from phoenix_guardian.security.ml_detector import (
    MLThreatDetector,
    ThreatDetectionResult,
    ThreatCategory,
)

from phoenix_guardian.security.attacker_intelligence_db import (
    AttackerIntelligenceDB,
    DatabaseError,
    ConnectionError as DBConnectionError,
    QueryError,
)

from phoenix_guardian.security.threat_intelligence import (
    ThreatIntelligenceAnalyzer,
    CoordinatedCampaign,
    AttributionCluster,
    ATTACK_SEVERITY,
    DATACENTER_ASNS,
    KNOWN_TOR_EXIT_NODES,
    KNOWN_VPN_PATTERNS,
)

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
)

from phoenix_guardian.security.encryption import (
    EncryptionService,
    EncryptionError,
    DecryptionError,
    get_encryption_service,
    reset_encryption_service,
    encrypt_pii,
    decrypt_pii,
    encrypt_phi,
    decrypt_phi,
)

from phoenix_guardian.security.audit_logger import (
    AuditLogger,
)

from phoenix_guardian.security.deception_agent import (
    # Main class
    DeceptionAgent,
    # Dataclasses
    DeceptionDecision,
    DeploymentRecord,
    InteractionRecord,
    # Enums
    DeceptionStrategy,
    DeploymentTiming,
    InteractionType,
    # Exceptions
    DeceptionError,
    DeploymentError,
    DecisionError,
    # Constants
    CONFIDENCE_FULL_DECEPTION,
    CONFIDENCE_MIXED,
    CONFIDENCE_REACTIVE,
    REPEAT_ATTEMPT_ESCALATION,
)

from phoenix_guardian.security.evidence_packager import (
    # Main classes
    EvidencePackager,
    # Dataclasses
    EvidencePackage,
    # Enums
    EvidenceType,
    # Constants
    STATE_COMPUTER_CRIME_LAWS,
)

from phoenix_guardian.security.alerting import (
    # Main class
    RealTimeAlerting,
    # Dataclasses
    SecurityAlert,
    # Enums
    AlertSeverity,
    AlertChannel,
    # Constants
    SEVERITY_COLORS,
    SEVERITY_EMOJI,
    DEFAULT_CHANNELS,
)

from phoenix_guardian.security.pqc_encryption import (
    # Main classes
    HybridPQCEncryption,
    EncryptedData,
    PQCKeyPair,
    # Enums
    KeyStatus,
    SecurityLevel,
    # Exceptions
    PQCError,
    EncryptionError,
    DecryptionError,
    TamperDetectedError,
    # Convenience functions
    encrypt_string,
    decrypt_string,
    encrypt_json,
    decrypt_json,
    encrypt_batch,
    decrypt_batch,
    # Utilities
    is_oqs_available,
    get_supported_algorithms,
    benchmark_encryption,
    # Constants
    KEM_ALGORITHM,
    AES_KEY_SIZE,
    AES_NONCE_SIZE,
    AES_TAG_SIZE,
    ALGORITHM_IDENTIFIER,
)

__all__ = [
    # ML Detector
    "MLThreatDetector",
    "ThreatDetectionResult",
    "ThreatCategory",
    # Attacker Intelligence Database
    "AttackerIntelligenceDB",
    "DatabaseError",
    "DBConnectionError",
    "QueryError",
    # Threat Intelligence Analyzer
    "ThreatIntelligenceAnalyzer",
    "CoordinatedCampaign",
    "AttributionCluster",
    "ATTACK_SEVERITY",
    "DATACENTER_ASNS",
    "KNOWN_TOR_EXIT_NODES",
    "KNOWN_VPN_PATTERNS",
    # Honeytoken Generator
    "HoneytokenGenerator",
    "ForensicBeacon",
    "LegalHoneytoken",
    "AttackerFingerprint",
    # Simple Encryption Service
    "EncryptionService",
    "get_encryption_service",
    "reset_encryption_service",
    "encrypt_pii",
    "decrypt_pii",
    "encrypt_phi",
    "decrypt_phi",
    # Audit Logger
    "AuditLogger",
    # Deception Agent
    "DeceptionAgent",
    "DeceptionDecision",
    "DeploymentRecord",
    "InteractionRecord",
    # Enums
    "AttackType",
    "HoneytokenStatus",
    "ComplianceCheck",
    "DeceptionStrategy",
    "DeploymentTiming",
    "InteractionType",
    # Exceptions
    "HoneytokenError",
    "LegalComplianceError",
    "InvalidMRNError",
    "BeaconError",
    "FingerprintError",
    "DeceptionError",
    "DeploymentError",
    "DecisionError",
    "EncryptionError",
    "DecryptionError",
    # Constants
    "FCC_FICTION_PHONE_PREFIX",
    "NON_ROUTABLE_EMAIL_DOMAIN",
    "MRN_HONEYTOKEN_PREFIX",
    "MRN_RANGE_MIN",
    "MRN_RANGE_MAX",
    "BEACON_TRACKING_ENDPOINT",
    "CONFIDENCE_FULL_DECEPTION",
    "CONFIDENCE_MIXED",
    "CONFIDENCE_REACTIVE",
    "REPEAT_ATTEMPT_ESCALATION",
    # Evidence Packager
    "EvidencePackager",
    "EvidencePackage",
    "EvidenceType",
    "STATE_COMPUTER_CRIME_LAWS",
    # Real-Time Alerting
    "RealTimeAlerting",
    "SecurityAlert",
    "AlertSeverity",
    "AlertChannel",
    "SEVERITY_COLORS",
    "SEVERITY_EMOJI",
    "DEFAULT_CHANNELS",
    # Post-Quantum Cryptography
    "HybridPQCEncryption",
    "EncryptedData",
    "PQCKeyPair",
    "KeyStatus",
    "SecurityLevel",
    "PQCError",
    "TamperDetectedError",
    "encrypt_string",
    "decrypt_string",
    "encrypt_json",
    "decrypt_json",
    "encrypt_batch",
    "decrypt_batch",
    "is_oqs_available",
    "get_supported_algorithms",
    "benchmark_encryption",
    "KEM_ALGORITHM",
    "AES_KEY_SIZE",
    "AES_NONCE_SIZE",
    "AES_TAG_SIZE",
    "ALGORITHM_IDENTIFIER",
]
