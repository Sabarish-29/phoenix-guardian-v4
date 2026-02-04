"""
Audit Package Generator for SOC 2.

Generates organized evidence packages for auditors:
- Evidence organized by TSC criteria
- Index with evidence summaries
- Integrity manifest
- Auditor-friendly format (PDF, ZIP)

CRITICAL: This is what the auditor receives.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
import json
import hashlib
import logging

from phoenix_guardian.compliance.evidence_types import (
    Evidence,
    EvidenceType,
    TSCCriterion,
)
from phoenix_guardian.compliance.evidence_validator import (
    EvidenceValidator,
    ValidationResult,
)

logger = logging.getLogger(__name__)


@dataclass
class AuditPackage:
    """
    A complete audit package for SOC 2.
    
    Contains all evidence organized by TSC criteria.
    """
    package_id: str
    generated_at: str
    audit_period_start: str
    audit_period_end: str
    
    # Evidence by TSC
    evidence_by_tsc: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    
    # Metadata
    total_evidence: int = 0
    tsc_coverage: Dict[str, int] = field(default_factory=dict)
    
    # Integrity
    manifest_hash: str = ""
    
    # Validation
    validation_result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "package_id": self.package_id,
            "generated_at": self.generated_at,
            "audit_period_start": self.audit_period_start,
            "audit_period_end": self.audit_period_end,
            "total_evidence": self.total_evidence,
            "tsc_coverage": self.tsc_coverage,
            "manifest_hash": self.manifest_hash,
            "validation_result": self.validation_result,
            "evidence_by_tsc": self.evidence_by_tsc,
        }


class AuditPackageGenerator:
    """
    Generates audit packages for SOC 2 Type II.
    
    Creates organized evidence packages that auditors can review.
    """
    
    # TSC descriptions for package index
    TSC_DESCRIPTIONS = {
        TSCCriterion.CC1_CONTROL_ENVIRONMENT: "Control Environment - Governance, roles, training",
        TSCCriterion.CC2_COMMUNICATION: "Communication & Information - Internal/external comms",
        TSCCriterion.CC3_RISK_ASSESSMENT: "Risk Assessment - Vulnerability scans, pen tests",
        TSCCriterion.CC4_MONITORING: "Monitoring Activities - Availability, performance",
        TSCCriterion.CC5_CONTROL_ACTIVITIES: "Control Activities - Access controls, operations",
        TSCCriterion.CC6_LOGICAL_ACCESS: "Logical Access - Authentication, authorization",
        TSCCriterion.CC7_SYSTEM_OPERATIONS: "System Operations - Incidents, backups",
        TSCCriterion.CC8_CHANGE_MANAGEMENT: "Change Management - Deployments, approvals",
        TSCCriterion.CC9_RISK_MITIGATION: "Risk Mitigation - BC/DR, insurance",
    }
    
    def __init__(self):
        self.validator = EvidenceValidator()
        self.generated_packages: List[AuditPackage] = []
    
    def generate(
        self,
        evidence_items: List[Evidence],
        audit_period_start: str,
        audit_period_end: str,
        validate: bool = True
    ) -> AuditPackage:
        """
        Generate an audit package from evidence.
        
        Args:
            evidence_items: Evidence to include
            audit_period_start: Start of audit period (ISO)
            audit_period_end: End of audit period (ISO)
            validate: Whether to validate evidence first
        
        Returns:
            AuditPackage ready for auditor
        """
        package_id = f"audit_pkg_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Generating audit package: {package_id}")
        
        # Validate if requested
        validation_result = None
        if validate:
            validation = self.validator.validate_for_audit_period(
                evidence_items,
                audit_period_start,
                audit_period_end
            )
            validation_result = validation.to_dict()
            
            if not validation.is_valid:
                logger.warning(
                    f"Validation found {validation.error_count} errors - "
                    "package may not be audit-ready"
                )
        
        # Organize by TSC
        evidence_by_tsc: Dict[str, List[Dict[str, Any]]] = {}
        tsc_coverage: Dict[str, int] = {}
        
        for tsc in TSCCriterion:
            tsc_key = tsc.value
            evidence_by_tsc[tsc_key] = []
            tsc_coverage[tsc_key] = 0
        
        for evidence in evidence_items:
            evidence_dict = evidence.to_dict()
            
            for tsc in evidence.tsc_criteria:
                tsc_key = tsc.value
                evidence_by_tsc[tsc_key].append(evidence_dict)
                tsc_coverage[tsc_key] = tsc_coverage.get(tsc_key, 0) + 1
        
        # Compute manifest hash
        manifest_data = json.dumps(evidence_by_tsc, sort_keys=True)
        manifest_hash = hashlib.sha256(manifest_data.encode()).hexdigest()
        
        package = AuditPackage(
            package_id=package_id,
            generated_at=datetime.now().isoformat(),
            audit_period_start=audit_period_start,
            audit_period_end=audit_period_end,
            evidence_by_tsc=evidence_by_tsc,
            total_evidence=len(evidence_items),
            tsc_coverage=tsc_coverage,
            manifest_hash=manifest_hash,
            validation_result=validation_result,
        )
        
        self.generated_packages.append(package)
        
        logger.info(
            f"Generated audit package: {package_id} with "
            f"{len(evidence_items)} evidence items"
        )
        
        return package
    
    def generate_index(self, package: AuditPackage) -> Dict[str, Any]:
        """
        Generate an index/table of contents for audit package.
        
        This is what auditors use to navigate evidence.
        """
        index = {
            "package_id": package.package_id,
            "generated_at": package.generated_at,
            "audit_period": {
                "start": package.audit_period_start,
                "end": package.audit_period_end,
            },
            "summary": {
                "total_evidence": package.total_evidence,
                "tsc_criteria_covered": sum(
                    1 for count in package.tsc_coverage.values() if count > 0
                ),
                "validation_passed": (
                    package.validation_result.get("is_valid", False)
                    if package.validation_result else None
                ),
            },
            "sections": [],
        }
        
        # Build sections by TSC
        for tsc in TSCCriterion:
            tsc_key = tsc.value
            evidence_count = package.tsc_coverage.get(tsc_key, 0)
            
            section = {
                "tsc_criterion": tsc_key,
                "title": self.TSC_DESCRIPTIONS.get(tsc, tsc.description),
                "evidence_count": evidence_count,
                "has_evidence": evidence_count > 0,
                "is_automatable": tsc.is_automatable,
            }
            
            # List evidence types in this section
            if evidence_count > 0:
                evidence_types = set()
                for evidence in package.evidence_by_tsc.get(tsc_key, []):
                    evidence_types.add(evidence.get("evidence_type", "unknown"))
                section["evidence_types"] = list(evidence_types)
            
            index["sections"].append(section)
        
        return index
    
    def export_to_json(
        self,
        package: AuditPackage,
        output_path: Optional[str] = None
    ) -> str:
        """
        Export audit package to JSON file.
        
        Returns the output path.
        """
        if output_path is None:
            output_path = f"audit_package_{package.package_id}.json"
        
        output = {
            "metadata": {
                "package_id": package.package_id,
                "generated_at": package.generated_at,
                "audit_period_start": package.audit_period_start,
                "audit_period_end": package.audit_period_end,
                "total_evidence": package.total_evidence,
                "manifest_hash": package.manifest_hash,
            },
            "index": self.generate_index(package),
            "validation": package.validation_result,
            "evidence": package.evidence_by_tsc,
        }
        
        Path(output_path).write_text(json.dumps(output, indent=2))
        
        logger.info(f"Exported audit package to: {output_path}")
        
        return output_path
    
    def generate_summary_report(self, package: AuditPackage) -> Dict[str, Any]:
        """
        Generate a summary report for management/auditors.
        """
        return {
            "report_type": "SOC 2 Type II Evidence Summary",
            "package_id": package.package_id,
            "generated_at": package.generated_at,
            "audit_period": {
                "start": package.audit_period_start,
                "end": package.audit_period_end,
            },
            "evidence_summary": {
                "total_evidence_items": package.total_evidence,
                "tsc_coverage": {
                    tsc.value: {
                        "description": self.TSC_DESCRIPTIONS.get(tsc, ""),
                        "evidence_count": package.tsc_coverage.get(tsc.value, 0),
                        "status": "covered" if package.tsc_coverage.get(tsc.value, 0) > 0 else "gap",
                    }
                    for tsc in TSCCriterion
                    if tsc.is_automatable
                },
            },
            "validation_summary": {
                "validated": package.validation_result is not None,
                "passed": package.validation_result.get("is_valid", False) if package.validation_result else None,
                "errors": package.validation_result.get("error_count", 0) if package.validation_result else 0,
                "warnings": package.validation_result.get("warning_count", 0) if package.validation_result else 0,
            },
            "integrity": {
                "manifest_hash": package.manifest_hash,
                "hash_algorithm": "SHA-256",
            },
            "recommendations": self._generate_recommendations(package),
        }
    
    def _generate_recommendations(self, package: AuditPackage) -> List[str]:
        """Generate recommendations based on package analysis."""
        recommendations = []
        
        # Check TSC coverage
        for tsc in TSCCriterion:
            if tsc.is_automatable and package.tsc_coverage.get(tsc.value, 0) == 0:
                recommendations.append(
                    f"Collect evidence for {tsc.value}: {tsc.description}"
                )
        
        # Check validation issues
        if package.validation_result:
            if package.validation_result.get("error_count", 0) > 0:
                recommendations.append(
                    "Address validation errors before audit submission"
                )
            if package.validation_result.get("warning_count", 0) > 5:
                recommendations.append(
                    "Review and address validation warnings to improve evidence quality"
                )
        
        # Check evidence volume
        if package.total_evidence < 50:
            recommendations.append(
                "Consider collecting more evidence for comprehensive coverage"
            )
        
        return recommendations
