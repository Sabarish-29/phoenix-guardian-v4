"""
SOC 2 Compliance Automation Module.

Automates evidence collection for SOC 2 Type II audits.

Trust Service Criteria Coverage:
- CC3: Risk Assessment (vulnerability scans, pen tests)
- CC4: Monitoring Activities (system availability, performance)
- CC6: Logical Access Controls (authentication, authorization)
- CC7: System Operations (incidents, backups, capacity)
- CC8: Change Management (deployments, approvals, testing)

Key Components:
- SOC2EvidenceCollector: Main orchestrator
- Specialized collectors per TSC (AccessControl, ChangeManagement, etc.)
- EvidenceValidator: Integrity verification
- AuditPackageGenerator: TSC-organized export
- GapAnalyzer: Missing evidence detection
"""

from phoenix_guardian.compliance.evidence_types import (
    Evidence,
    EvidenceType,
    EvidenceSource,
    TSCCriterion,
    AccessLogEvidence,
    DeploymentEvidence,
    AvailabilityEvidence,
    IncidentEvidence,
    VulnerabilityScanEvidence,
    PerformanceEvidence,
    AuthenticationEvidence,
    ChangeApprovalEvidence,
    ResolutionEvidence,
    PenetrationTestEvidence,
)
from phoenix_guardian.compliance.soc2_evidence_collector import (
    SOC2EvidenceCollector,
    EvidenceCollectionResult,
)
from phoenix_guardian.compliance.access_control_collector import (
    AccessControlCollector,
)
from phoenix_guardian.compliance.change_management_collector import (
    ChangeManagementCollector,
)
from phoenix_guardian.compliance.monitoring_collector import (
    MonitoringCollector,
)
from phoenix_guardian.compliance.incident_response_collector import (
    IncidentResponseCollector,
)
from phoenix_guardian.compliance.risk_assessment_collector import (
    RiskAssessmentCollector,
)
from phoenix_guardian.compliance.evidence_validator import (
    EvidenceValidator,
    ValidationResult,
)
from phoenix_guardian.compliance.audit_package_generator import (
    AuditPackageGenerator,
    AuditPackage,
)
from phoenix_guardian.compliance.gap_analyzer import (
    GapAnalyzer,
    EvidenceGap,
)

# FDA CDS Classification (Week 39-40)
from phoenix_guardian.compliance.fda_cds_classifier import (
    CDSAssessment,
    CDSCategory,
    CDSFunction,
    CDSFunctionType,
    CDSRiskLevel,
    Criterion,
    FDACDSClassifier,
    get_phoenix_guardian_cds_functions,
)

from phoenix_guardian.compliance.cds_risk_scorer import (
    AutonomyLevel,
    CDSRiskProfile,
    CDSRiskScoringEngine,
    ClinicalImpactLevel,
    DataQualityLevel,
    IEC62304SafetyClass,
    PopulationVulnerability,
    RiskDimensionScore,
    RiskMitigation,
    RiskScoreResult,
    get_standard_mitigations,
)

__all__ = [
    # Core types
    'Evidence',
    'EvidenceType',
    'EvidenceSource',
    'TSCCriterion',
    'AccessLogEvidence',
    'DeploymentEvidence',
    'AvailabilityEvidence',
    'IncidentEvidence',
    'VulnerabilityScanEvidence',
    'PerformanceEvidence',
    'AuthenticationEvidence',
    'ChangeApprovalEvidence',
    'ResolutionEvidence',
    'PenetrationTestEvidence',
    # Main collector
    'SOC2EvidenceCollector',
    'EvidenceCollectionResult',
    # Specialized collectors
    'AccessControlCollector',
    'ChangeManagementCollector',
    'MonitoringCollector',
    'IncidentResponseCollector',
    'RiskAssessmentCollector',
    # Validation & packaging
    'EvidenceValidator',
    'ValidationResult',
    'AuditPackageGenerator',
    'AuditPackage',
    'GapAnalyzer',
    'EvidenceGap',
    # FDA CDS Classification
    'CDSAssessment',
    'CDSCategory',
    'CDSFunction',
    'CDSFunctionType',
    'CDSRiskLevel',
    'Criterion',
    'FDACDSClassifier',
    'get_phoenix_guardian_cds_functions',
    # CDS Risk Scoring
    'AutonomyLevel',
    'CDSRiskProfile',
    'CDSRiskScoringEngine',
    'ClinicalImpactLevel',
    'DataQualityLevel',
    'IEC62304SafetyClass',
    'PopulationVulnerability',
    'RiskDimensionScore',
    'RiskMitigation',
    'RiskScoreResult',
    'get_standard_mitigations',
]
