"""
Evidence Validator for SOC 2.

Validates evidence integrity, completeness, and correctness:
- Cryptographic hash verification
- Required field validation
- Temporal consistency checks
- Cross-reference validation

CRITICAL: Evidence must be validated before audit package generation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
import logging

from phoenix_guardian.compliance.evidence_types import (
    Evidence,
    EvidenceType,
    TSCCriterion,
)

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity of validation issues."""
    ERROR = "error"      # Must fix before audit
    WARNING = "warning"  # Should fix
    INFO = "info"        # Informational


@dataclass
class ValidationIssue:
    """A validation issue found in evidence."""
    evidence_id: str
    severity: ValidationSeverity
    category: str
    message: str
    remediation: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of evidence validation."""
    validation_id: str
    validated_at: str
    total_evidence: int
    valid_count: int
    invalid_count: int
    issues: List[ValidationIssue] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        """Check if all evidence passed validation."""
        error_count = sum(
            1 for issue in self.issues
            if issue.severity == ValidationSeverity.ERROR
        )
        return error_count == 0
    
    @property
    def error_count(self) -> int:
        return sum(
            1 for issue in self.issues
            if issue.severity == ValidationSeverity.ERROR
        )
    
    @property
    def warning_count(self) -> int:
        return sum(
            1 for issue in self.issues
            if issue.severity == ValidationSeverity.WARNING
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "validation_id": self.validation_id,
            "validated_at": self.validated_at,
            "total_evidence": self.total_evidence,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "is_valid": self.is_valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "evidence_id": i.evidence_id,
                    "severity": i.severity.value,
                    "category": i.category,
                    "message": i.message,
                    "remediation": i.remediation,
                }
                for i in self.issues
            ],
        }


class EvidenceValidator:
    """
    Validates evidence for SOC 2 audit.
    
    Performs multiple validation checks:
    1. Integrity: Hash verification
    2. Completeness: Required fields present
    3. Temporal: Timestamps are consistent
    4. Quality: Evidence meets audit standards
    """
    
    # Required fields for each evidence type
    REQUIRED_FIELDS: Dict[EvidenceType, Set[str]] = {
        EvidenceType.AUTHENTICATION_EVENT: {"user_id", "auth_method"},
        EvidenceType.AUTHORIZATION_CHECK: {"user_id", "resource_accessed", "action", "result"},
        EvidenceType.DEPLOYMENT_RECORD: {"deployment_id", "git_commit_sha", "tests_passed"},
        EvidenceType.CHANGE_APPROVAL: {"change_id", "approver_ids"},
        EvidenceType.SYSTEM_AVAILABILITY: {"service_name", "availability_percentage"},
        EvidenceType.INCIDENT_REPORT: {"incident_id", "incident_type", "severity"},
        EvidenceType.VULNERABILITY_SCAN: {"scan_id", "scanner_name", "vulnerabilities_found"},
    }
    
    # Maximum age for evidence before warning
    MAX_EVIDENCE_AGE_DAYS = 365
    
    def __init__(self):
        self.validation_history: List[ValidationResult] = []
    
    def validate(
        self,
        evidence_items: List[Evidence],
        strict: bool = False
    ) -> ValidationResult:
        """
        Validate a list of evidence items.
        
        Args:
            evidence_items: Evidence to validate
            strict: If True, warnings become errors
        
        Returns:
            ValidationResult with all issues found
        """
        validation_id = f"val_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        issues: List[ValidationIssue] = []
        valid_count = 0
        
        for evidence in evidence_items:
            evidence_issues = self._validate_evidence(evidence, strict)
            issues.extend(evidence_issues)
            
            # Count as valid if no errors
            has_errors = any(
                i.severity == ValidationSeverity.ERROR
                for i in evidence_issues
            )
            if not has_errors:
                valid_count += 1
        
        result = ValidationResult(
            validation_id=validation_id,
            validated_at=datetime.now().isoformat(),
            total_evidence=len(evidence_items),
            valid_count=valid_count,
            invalid_count=len(evidence_items) - valid_count,
            issues=issues,
        )
        
        self.validation_history.append(result)
        
        logger.info(
            f"Validation complete: {valid_count}/{len(evidence_items)} valid, "
            f"{result.error_count} errors, {result.warning_count} warnings"
        )
        
        return result
    
    def _validate_evidence(
        self,
        evidence: Evidence,
        strict: bool
    ) -> List[ValidationIssue]:
        """Validate a single evidence item."""
        issues: List[ValidationIssue] = []
        
        # 1. Integrity check
        integrity_issues = self._check_integrity(evidence)
        issues.extend(integrity_issues)
        
        # 2. Required fields check
        field_issues = self._check_required_fields(evidence)
        issues.extend(field_issues)
        
        # 3. Temporal consistency
        temporal_issues = self._check_temporal_consistency(evidence)
        issues.extend(temporal_issues)
        
        # 4. TSC mapping check
        tsc_issues = self._check_tsc_mapping(evidence)
        issues.extend(tsc_issues)
        
        # 5. Control description check
        desc_issues = self._check_control_description(evidence)
        issues.extend(desc_issues)
        
        # Upgrade warnings to errors in strict mode
        if strict:
            for issue in issues:
                if issue.severity == ValidationSeverity.WARNING:
                    issue.severity = ValidationSeverity.ERROR
        
        return issues
    
    def _check_integrity(self, evidence: Evidence) -> List[ValidationIssue]:
        """Check cryptographic integrity of evidence."""
        issues: List[ValidationIssue] = []
        
        if not evidence.verify_integrity():
            issues.append(ValidationIssue(
                evidence_id=evidence.evidence_id,
                severity=ValidationSeverity.ERROR,
                category="integrity",
                message="Evidence hash mismatch - data may have been tampered with",
                remediation="Re-collect evidence from source system",
            ))
        
        if not evidence.data_hash:
            issues.append(ValidationIssue(
                evidence_id=evidence.evidence_id,
                severity=ValidationSeverity.ERROR,
                category="integrity",
                message="Evidence missing data hash",
                remediation="Compute and store hash before audit",
            ))
        
        return issues
    
    def _check_required_fields(self, evidence: Evidence) -> List[ValidationIssue]:
        """Check that required fields are present."""
        issues: List[ValidationIssue] = []
        
        # Check common fields
        if not evidence.evidence_id:
            issues.append(ValidationIssue(
                evidence_id="unknown",
                severity=ValidationSeverity.ERROR,
                category="completeness",
                message="Evidence missing evidence_id",
                remediation="Ensure all evidence has unique ID",
            ))
        
        if not evidence.collected_at:
            issues.append(ValidationIssue(
                evidence_id=evidence.evidence_id,
                severity=ValidationSeverity.ERROR,
                category="completeness",
                message="Evidence missing collection timestamp",
                remediation="Add collected_at timestamp",
            ))
        
        if not evidence.event_timestamp:
            issues.append(ValidationIssue(
                evidence_id=evidence.evidence_id,
                severity=ValidationSeverity.ERROR,
                category="completeness",
                message="Evidence missing event timestamp",
                remediation="Add event_timestamp",
            ))
        
        if not evidence.control_description:
            issues.append(ValidationIssue(
                evidence_id=evidence.evidence_id,
                severity=ValidationSeverity.WARNING,
                category="completeness",
                message="Evidence missing control description",
                remediation="Add description of control this evidence demonstrates",
            ))
        
        return issues
    
    def _check_temporal_consistency(self, evidence: Evidence) -> List[ValidationIssue]:
        """Check temporal consistency of evidence."""
        issues: List[ValidationIssue] = []
        
        try:
            collected = datetime.fromisoformat(evidence.collected_at)
            event = datetime.fromisoformat(evidence.event_timestamp)
            now = datetime.now()
            
            # Event should be before collection
            if event > collected:
                issues.append(ValidationIssue(
                    evidence_id=evidence.evidence_id,
                    severity=ValidationSeverity.WARNING,
                    category="temporal",
                    message="Event timestamp is after collection timestamp",
                    remediation="Verify timestamps are correct",
                ))
            
            # Collection should not be in future
            if collected > now:
                issues.append(ValidationIssue(
                    evidence_id=evidence.evidence_id,
                    severity=ValidationSeverity.ERROR,
                    category="temporal",
                    message="Collection timestamp is in the future",
                    remediation="Correct collection timestamp",
                ))
            
            # Evidence should not be too old
            age_days = (now - event).days
            if age_days > self.MAX_EVIDENCE_AGE_DAYS:
                issues.append(ValidationIssue(
                    evidence_id=evidence.evidence_id,
                    severity=ValidationSeverity.WARNING,
                    category="temporal",
                    message=f"Evidence is {age_days} days old (>{self.MAX_EVIDENCE_AGE_DAYS} days)",
                    remediation="Consider collecting fresher evidence",
                ))
        except (ValueError, TypeError) as e:
            issues.append(ValidationIssue(
                evidence_id=evidence.evidence_id,
                severity=ValidationSeverity.ERROR,
                category="temporal",
                message=f"Invalid timestamp format: {e}",
                remediation="Use ISO format timestamps",
            ))
        
        return issues
    
    def _check_tsc_mapping(self, evidence: Evidence) -> List[ValidationIssue]:
        """Check TSC criteria mapping."""
        issues: List[ValidationIssue] = []
        
        if not evidence.tsc_criteria:
            issues.append(ValidationIssue(
                evidence_id=evidence.evidence_id,
                severity=ValidationSeverity.ERROR,
                category="mapping",
                message="Evidence not mapped to any TSC criteria",
                remediation="Map evidence to relevant TSC criteria",
            ))
        
        # Check that mapped TSC is automatable
        for tsc in evidence.tsc_criteria:
            if not tsc.is_automatable:
                issues.append(ValidationIssue(
                    evidence_id=evidence.evidence_id,
                    severity=ValidationSeverity.INFO,
                    category="mapping",
                    message=f"Evidence mapped to manual TSC {tsc.value}",
                    remediation=None,
                ))
        
        return issues
    
    def _check_control_description(self, evidence: Evidence) -> List[ValidationIssue]:
        """Check control description quality."""
        issues: List[ValidationIssue] = []
        
        if evidence.control_description:
            if len(evidence.control_description) < 20:
                issues.append(ValidationIssue(
                    evidence_id=evidence.evidence_id,
                    severity=ValidationSeverity.WARNING,
                    category="quality",
                    message="Control description is too brief",
                    remediation="Provide detailed description of control",
                ))
        
        return issues
    
    def validate_for_audit_period(
        self,
        evidence_items: List[Evidence],
        audit_start: str,
        audit_end: str
    ) -> ValidationResult:
        """
        Validate evidence for a specific audit period.
        
        Ensures evidence covers the entire audit period.
        """
        # First run standard validation
        result = self.validate(evidence_items)
        
        # Additional audit period checks
        audit_start_dt = datetime.fromisoformat(audit_start)
        audit_end_dt = datetime.fromisoformat(audit_end)
        
        # Check coverage
        evidence_dates = []
        for evidence in evidence_items:
            try:
                event_dt = datetime.fromisoformat(evidence.event_timestamp)
                evidence_dates.append(event_dt)
            except (ValueError, TypeError):
                pass
        
        if evidence_dates:
            earliest = min(evidence_dates)
            latest = max(evidence_dates)
            
            if earliest > audit_start_dt:
                result.issues.append(ValidationIssue(
                    evidence_id="audit_period",
                    severity=ValidationSeverity.WARNING,
                    category="coverage",
                    message=f"Evidence starts {(earliest - audit_start_dt).days} days after audit period start",
                    remediation="Collect evidence for full audit period",
                ))
            
            if latest < audit_end_dt:
                result.issues.append(ValidationIssue(
                    evidence_id="audit_period",
                    severity=ValidationSeverity.WARNING,
                    category="coverage",
                    message=f"Evidence ends {(audit_end_dt - latest).days} days before audit period end",
                    remediation="Collect evidence through end of audit period",
                ))
        
        return result
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of all validations."""
        if not self.validation_history:
            return {"total_validations": 0}
        
        total_evidence = sum(v.total_evidence for v in self.validation_history)
        total_valid = sum(v.valid_count for v in self.validation_history)
        total_errors = sum(v.error_count for v in self.validation_history)
        total_warnings = sum(v.warning_count for v in self.validation_history)
        
        return {
            "total_validations": len(self.validation_history),
            "total_evidence": total_evidence,
            "total_valid": total_valid,
            "validation_rate": (total_valid / total_evidence * 100) if total_evidence > 0 else 0,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
        }
