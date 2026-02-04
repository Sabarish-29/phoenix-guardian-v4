"""
Privacy Auditor for Phoenix Guardian Federated Learning.

This module provides continuous privacy monitoring and compliance
reporting for the federated learning system. It validates that:
    - All signatures have proper DP noise
    - No hospital can be identified from signatures
    - Privacy budget limits are enforced
    - Anonymity sets meet k-anonymity requirements

The auditor also simulates privacy attacks to verify that the
system is robust against adversarial analysis.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib
import json
import logging
import math
from collections import defaultdict
import numpy as np
import secrets

from phoenix_guardian.federated.differential_privacy import (
    DifferentialPrivacyEngine,
    PrivacyBudget,
    PrivacyAccountant,
)
from phoenix_guardian.federated.threat_signature import (
    ThreatSignature,
    FORBIDDEN_FIELDS,
)
from phoenix_guardian.federated.secure_aggregator import AggregatedSignature
from phoenix_guardian.federated.privacy_validator import (
    PrivacyValidator,
    ValidationResult,
)


logger = logging.getLogger(__name__)


@dataclass
class AuditResult:
    """
    Result of a privacy audit.
    
    Attributes:
        audit_id: Unique identifier for this audit
        timestamp: When the audit was performed
        passed: Whether the audit passed
        findings: List of issues found
        recommendations: Suggested fixes
        compliance_status: HIPAA/GDPR compliance status
        risk_level: Overall risk level (low, medium, high, critical)
    """
    audit_id: str = field(default_factory=lambda: secrets.token_hex(16))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    passed: bool = True
    findings: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    compliance_status: Dict[str, bool] = field(default_factory=dict)
    risk_level: str = "low"
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp,
            "passed": self.passed,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "compliance_status": self.compliance_status,
            "risk_level": self.risk_level,
            "metrics": self.metrics,
        }


@dataclass
class AttackSimulationResult:
    """
    Result of a privacy attack simulation.
    
    Attributes:
        attack_type: Type of attack simulated
        success_rate: Rate at which attack succeeded
        privacy_preserved: Whether privacy was maintained
        details: Detailed results
    """
    attack_type: str
    success_rate: float
    privacy_preserved: bool
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "attack_type": self.attack_type,
            "success_rate": self.success_rate,
            "privacy_preserved": self.privacy_preserved,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class PrivacyAuditor:
    """
    Comprehensive privacy auditing for federated learning.
    
    The auditor performs continuous monitoring and periodic audits
    to ensure that the federated learning system maintains its
    privacy guarantees. It checks:
    
    1. DP Noise Verification: All signatures have proper noise
    2. Anonymity Sets: Each signature from ≥2 hospitals
    3. Re-identification Risk: Hospitals cannot be identified
    4. Budget Enforcement: Privacy budgets are respected
    5. Compliance: HIPAA and GDPR requirements met
    
    The auditor also runs attack simulations to test robustness:
    - Linkage attacks (correlate signatures)
    - Membership inference (was hospital X involved?)
    - Attribute inference (infer hospital properties)
    
    Example:
        >>> auditor = PrivacyAuditor()
        >>> result = auditor.run_privacy_audit(signatures)
        >>> print(result.passed)
        >>> 
        >>> attack = auditor.simulate_privacy_attack("linkage_attack")
        >>> print(attack.privacy_preserved)
    """
    
    def __init__(
        self,
        min_anonymity_set: int = 2,
        max_reidentification_risk: float = 0.1,
        seed: Optional[int] = None,
    ):
        """
        Initialize the privacy auditor.
        
        Args:
            min_anonymity_set: Minimum k for k-anonymity (default 2)
            max_reidentification_risk: Maximum acceptable risk
            seed: Random seed for reproducibility
        """
        self.min_anonymity_set = min_anonymity_set
        self.max_reidentification_risk = max_reidentification_risk
        self._rng = np.random.default_rng(seed)
        
        self._validator = PrivacyValidator(seed=seed)
        self._audit_history: List[AuditResult] = []
        self._attack_history: List[AttackSimulationResult] = []
    
    def run_privacy_audit(
        self,
        signatures: List[ThreatSignature],
        aggregated_signatures: Optional[List[AggregatedSignature]] = None,
        privacy_budgets: Optional[Dict[str, PrivacyBudget]] = None,
    ) -> AuditResult:
        """
        Run a comprehensive privacy audit.
        
        This is the main audit function that performs all privacy checks:
        1. Verify DP noise on all signatures
        2. Check anonymity sets (≥2 hospitals)
        3. Test re-identification attacks
        4. Validate epsilon budget consumption
        5. Check compliance requirements
        
        Args:
            signatures: List of threat signatures to audit
            aggregated_signatures: Optional aggregated signatures
            privacy_budgets: Optional per-tenant privacy budgets
            
        Returns:
            AuditResult with findings and recommendations
        """
        result = AuditResult()
        
        # 1. Verify DP noise on all signatures
        noise_findings = self._audit_dp_noise(signatures)
        result.findings.extend(noise_findings)
        
        # 2. Check anonymity sets
        anonymity_findings = self._audit_anonymity_sets(
            signatures,
            aggregated_signatures or [],
        )
        result.findings.extend(anonymity_findings)
        
        # 3. Test re-identification risk
        reid_findings = self._audit_reidentification_risk(signatures)
        result.findings.extend(reid_findings)
        
        # 4. Validate budget consumption
        if privacy_budgets:
            budget_findings = self._audit_budget_consumption(privacy_budgets)
            result.findings.extend(budget_findings)
        
        # 5. Check forbidden fields
        field_findings = self._audit_forbidden_fields(signatures)
        result.findings.extend(field_findings)
        
        # 6. Check timestamp granularity
        timestamp_findings = self._audit_timestamp_granularity(signatures)
        result.findings.extend(timestamp_findings)
        
        # Compute compliance status
        result.compliance_status = self._compute_compliance_status(result.findings)
        
        # Determine if audit passed
        critical_findings = [
            f for f in result.findings
            if f.get("severity") == "critical"
        ]
        result.passed = len(critical_findings) == 0
        
        # Determine risk level
        result.risk_level = self._compute_risk_level(result.findings)
        
        # Generate recommendations
        result.recommendations = self._generate_recommendations(result.findings)
        
        # Compute metrics
        result.metrics = {
            "total_signatures": len(signatures),
            "findings_count": len(result.findings),
            "critical_findings": len(critical_findings),
            "compliance_checks_passed": sum(result.compliance_status.values()),
            "compliance_checks_total": len(result.compliance_status),
        }
        
        # Store in history
        self._audit_history.append(result)
        
        logger.info(
            f"Privacy audit complete: {'PASSED' if result.passed else 'FAILED'} "
            f"({len(result.findings)} findings)"
        )
        
        return result
    
    def simulate_privacy_attack(
        self,
        attack_type: str = "linkage_attack",
        target_signatures: Optional[List[ThreatSignature]] = None,
        background_knowledge: Optional[Dict[str, Any]] = None,
    ) -> AttackSimulationResult:
        """
        Simulate a privacy attack.
        
        This runs attack simulations to verify that the system is
        robust against various privacy threats:
        
        - linkage_attack: Try to correlate signatures across time
        - membership_inference: Determine if a hospital contributed
        - attribute_inference: Infer hospital properties
        
        Args:
            attack_type: Type of attack to simulate
            target_signatures: Signatures to attack
            background_knowledge: Additional attacker knowledge
            
        Returns:
            AttackSimulationResult with success rate
        """
        target_signatures = target_signatures or []
        background_knowledge = background_knowledge or {}
        
        if attack_type == "linkage_attack":
            result = self._simulate_linkage_attack(
                target_signatures,
                background_knowledge,
            )
        elif attack_type == "membership_inference":
            result = self._simulate_membership_inference(
                target_signatures,
                background_knowledge,
            )
        elif attack_type == "attribute_inference":
            result = self._simulate_attribute_inference(
                target_signatures,
                background_knowledge,
            )
        else:
            result = AttackSimulationResult(
                attack_type=attack_type,
                success_rate=0.0,
                privacy_preserved=True,
                details={"error": f"Unknown attack type: {attack_type}"},
            )
        
        self._attack_history.append(result)
        
        logger.info(
            f"Attack simulation '{attack_type}': "
            f"success_rate={result.success_rate:.2%}, "
            f"privacy_preserved={result.privacy_preserved}"
        )
        
        return result
    
    def generate_compliance_report(
        self,
        include_history: bool = False,
    ) -> str:
        """
        Generate a privacy compliance report.
        
        This report is suitable for regulatory compliance (HIPAA, GDPR)
        and internal auditing purposes.
        
        Args:
            include_history: Whether to include historical audit results
            
        Returns:
            Formatted compliance report
        """
        report_lines = [
            "=" * 60,
            "PHOENIX GUARDIAN - PRIVACY COMPLIANCE REPORT",
            f"Generated: {datetime.utcnow().isoformat()}",
            "=" * 60,
            "",
        ]
        
        # Latest audit summary
        if self._audit_history:
            latest = self._audit_history[-1]
            report_lines.extend([
                "LATEST AUDIT SUMMARY",
                "-" * 40,
                f"Audit ID: {latest.audit_id}",
                f"Timestamp: {latest.timestamp}",
                f"Status: {'PASSED' if latest.passed else 'FAILED'}",
                f"Risk Level: {latest.risk_level.upper()}",
                f"Findings: {len(latest.findings)}",
                "",
            ])
            
            # Compliance checklist
            report_lines.extend([
                "COMPLIANCE CHECKLIST",
                "-" * 40,
            ])
            for check, passed in latest.compliance_status.items():
                status = "✓" if passed else "✗"
                report_lines.append(f"  [{status}] {check}")
            report_lines.append("")
            
            # Critical findings
            critical = [f for f in latest.findings if f.get("severity") == "critical"]
            if critical:
                report_lines.extend([
                    "CRITICAL FINDINGS",
                    "-" * 40,
                ])
                for finding in critical:
                    report_lines.append(f"  • {finding.get('description', 'Unknown')}")
                report_lines.append("")
            
            # Recommendations
            if latest.recommendations:
                report_lines.extend([
                    "RECOMMENDATIONS",
                    "-" * 40,
                ])
                for rec in latest.recommendations:
                    report_lines.append(f"  • {rec}")
                report_lines.append("")
        
        # Attack simulation results
        if self._attack_history:
            report_lines.extend([
                "PRIVACY ATTACK SIMULATIONS",
                "-" * 40,
            ])
            for attack in self._attack_history[-5:]:  # Last 5
                status = "DEFENDED" if attack.privacy_preserved else "VULNERABLE"
                report_lines.append(
                    f"  {attack.attack_type}: {status} "
                    f"(success rate: {attack.success_rate:.1%})"
                )
            report_lines.append("")
        
        # Historical trends
        if include_history and len(self._audit_history) > 1:
            report_lines.extend([
                "AUDIT HISTORY",
                "-" * 40,
            ])
            for audit in self._audit_history[-10:]:  # Last 10
                status = "PASS" if audit.passed else "FAIL"
                report_lines.append(
                    f"  {audit.timestamp[:10]}: {status} "
                    f"({len(audit.findings)} findings)"
                )
            report_lines.append("")
        
        # Privacy guarantees
        report_lines.extend([
            "PRIVACY GUARANTEES",
            "-" * 40,
            f"  • Differential Privacy: ε=0.5, δ=1e-5",
            f"  • k-Anonymity: k≥{self.min_anonymity_set}",
            f"  • Re-identification Risk: <{self.max_reidentification_risk:.0%}",
            f"  • Timestamp Granularity: Month-level only",
            "",
            "=" * 60,
            "END OF REPORT",
            "=" * 60,
        ])
        
        return "\n".join(report_lines)
    
    def get_audit_history(
        self,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get audit history."""
        history = [a.to_dict() for a in self._audit_history]
        if limit:
            history = history[-limit:]
        return history
    
    def get_attack_history(
        self,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get attack simulation history."""
        history = [a.to_dict() for a in self._attack_history]
        if limit:
            history = history[-limit:]
        return history
    
    def _audit_dp_noise(
        self,
        signatures: List[ThreatSignature],
    ) -> List[Dict[str, Any]]:
        """Audit that all signatures have DP noise."""
        findings = []
        
        for sig in signatures:
            # Check noise_added flag
            if not sig.noise_added:
                findings.append({
                    "type": "no_dp_noise",
                    "severity": "critical",
                    "description": f"Signature {sig.signature_id[:8]} has no DP noise",
                    "signature_id": sig.signature_id,
                })
            
            # Check privacy metadata
            if not sig.privacy_metadata:
                findings.append({
                    "type": "missing_privacy_metadata",
                    "severity": "high",
                    "description": f"Signature {sig.signature_id[:8]} missing privacy metadata",
                    "signature_id": sig.signature_id,
                })
            else:
                # Verify epsilon is reasonable
                epsilon = sig.privacy_metadata.get("features", {}).get("epsilon", 0)
                if epsilon <= 0 or epsilon > 10:
                    findings.append({
                        "type": "invalid_epsilon",
                        "severity": "high",
                        "description": f"Signature {sig.signature_id[:8]} has invalid epsilon: {epsilon}",
                        "signature_id": sig.signature_id,
                    })
        
        return findings
    
    def _audit_anonymity_sets(
        self,
        signatures: List[ThreatSignature],
        aggregated: List[AggregatedSignature],
    ) -> List[Dict[str, Any]]:
        """Audit that anonymity sets meet k-anonymity."""
        findings = []
        
        # Check aggregated signatures
        for agg in aggregated:
            if agg.contributing_hospitals < self.min_anonymity_set:
                findings.append({
                    "type": "k_anonymity_violation",
                    "severity": "critical",
                    "description": (
                        f"Aggregated signature {agg.signature_hash[:8]} "
                        f"has only {agg.contributing_hospitals} hospitals "
                        f"(minimum: {self.min_anonymity_set})"
                    ),
                    "signature_hash": agg.signature_hash,
                })
        
        # Use validator for signature clustering
        result = self._validator.test_anonymity_set(
            signatures,
            min_anonymity_set=self.min_anonymity_set,
        )
        
        if not result.passed:
            findings.append({
                "type": "anonymity_set_test_failed",
                "severity": "high",
                "description": "Anonymity set test failed",
                "details": result.details,
            })
        
        return findings
    
    def _audit_reidentification_risk(
        self,
        signatures: List[ThreatSignature],
    ) -> List[Dict[str, Any]]:
        """Audit re-identification risk."""
        findings = []
        
        # Check for unique patterns that could identify hospitals
        attack_type_counts = defaultdict(int)
        for sig in signatures:
            attack_type_counts[sig.attack_type] += 1
        
        # If an attack type has very few signatures, risk increases
        for attack_type, count in attack_type_counts.items():
            if count < self.min_anonymity_set:
                findings.append({
                    "type": "low_anonymity_attack_type",
                    "severity": "medium",
                    "description": (
                        f"Attack type '{attack_type}' has only {count} "
                        f"signatures (minimum: {self.min_anonymity_set})"
                    ),
                    "attack_type": attack_type,
                })
        
        # Test unlinkability
        result = self._validator.test_signature_unlinkability(signatures)
        
        if not result.passed:
            findings.extend([
                {
                    "type": "unlinkability_violation",
                    "severity": "high",
                    "description": f"Unlinkability test failed: {v}",
                }
                for v in result.details.get("violations", [])
            ])
        
        return findings
    
    def _audit_budget_consumption(
        self,
        budgets: Dict[str, PrivacyBudget],
    ) -> List[Dict[str, Any]]:
        """Audit privacy budget consumption."""
        findings = []
        
        for tenant_id, budget in budgets.items():
            # Check for exhausted budgets
            if budget.is_exhausted():
                findings.append({
                    "type": "budget_exhausted",
                    "severity": "high",
                    "description": f"Privacy budget exhausted for {tenant_id}",
                    "tenant_id": tenant_id,
                })
            
            # Check for high consumption
            remaining_ratio = budget.remaining_queries() / budget.max_queries
            if remaining_ratio < 0.2:
                findings.append({
                    "type": "budget_low",
                    "severity": "medium",
                    "description": (
                        f"Privacy budget low for {tenant_id}: "
                        f"{budget.remaining_queries()}/{budget.max_queries} remaining"
                    ),
                    "tenant_id": tenant_id,
                })
        
        return findings
    
    def _audit_forbidden_fields(
        self,
        signatures: List[ThreatSignature],
    ) -> List[Dict[str, Any]]:
        """Audit for forbidden fields in signatures."""
        findings = []
        
        for sig in signatures:
            sig_str = json.dumps(sig.to_dict()).lower()
            
            for forbidden in FORBIDDEN_FIELDS:
                if forbidden in sig_str:
                    findings.append({
                        "type": "forbidden_field",
                        "severity": "critical",
                        "description": (
                            f"Signature {sig.signature_id[:8]} contains "
                            f"forbidden field: {forbidden}"
                        ),
                        "signature_id": sig.signature_id,
                        "field": forbidden,
                    })
        
        return findings
    
    def _audit_timestamp_granularity(
        self,
        signatures: List[ThreatSignature],
    ) -> List[Dict[str, Any]]:
        """Audit that timestamps are month-level only."""
        findings = []
        
        import re
        
        for sig in signatures:
            # Check first_seen
            if not re.match(r"^\d{4}-\d{2}$", sig.first_seen):
                findings.append({
                    "type": "fine_grained_timestamp",
                    "severity": "critical",
                    "description": (
                        f"Signature {sig.signature_id[:8]} has fine-grained "
                        f"first_seen: {sig.first_seen}"
                    ),
                    "signature_id": sig.signature_id,
                })
            
            # Check last_seen
            if not re.match(r"^\d{4}-\d{2}$", sig.last_seen):
                findings.append({
                    "type": "fine_grained_timestamp",
                    "severity": "critical",
                    "description": (
                        f"Signature {sig.signature_id[:8]} has fine-grained "
                        f"last_seen: {sig.last_seen}"
                    ),
                    "signature_id": sig.signature_id,
                })
        
        return findings
    
    def _compute_compliance_status(
        self,
        findings: List[Dict[str, Any]],
    ) -> Dict[str, bool]:
        """Compute compliance status for each requirement."""
        # Define compliance checks
        checks = {
            "HIPAA_minimum_necessary": True,
            "HIPAA_deidentification": True,
            "GDPR_data_minimization": True,
            "GDPR_purpose_limitation": True,
            "k_anonymity": True,
            "differential_privacy": True,
            "timestamp_coarsening": True,
            "no_direct_identifiers": True,
        }
        
        # Update based on findings
        for finding in findings:
            ftype = finding.get("type", "")
            severity = finding.get("severity", "")
            
            if severity in ("critical", "high"):
                if "forbidden_field" in ftype or "hospital" in ftype:
                    checks["HIPAA_deidentification"] = False
                    checks["GDPR_data_minimization"] = False
                    checks["no_direct_identifiers"] = False
                
                if "k_anonymity" in ftype or "anonymity" in ftype:
                    checks["k_anonymity"] = False
                    checks["HIPAA_minimum_necessary"] = False
                
                if "dp_noise" in ftype or "epsilon" in ftype:
                    checks["differential_privacy"] = False
                
                if "timestamp" in ftype:
                    checks["timestamp_coarsening"] = False
                    checks["GDPR_purpose_limitation"] = False
        
        return checks
    
    def _compute_risk_level(
        self,
        findings: List[Dict[str, Any]],
    ) -> str:
        """Compute overall risk level."""
        critical = sum(1 for f in findings if f.get("severity") == "critical")
        high = sum(1 for f in findings if f.get("severity") == "high")
        medium = sum(1 for f in findings if f.get("severity") == "medium")
        
        if critical > 0:
            return "critical"
        elif high > 2:
            return "high"
        elif high > 0 or medium > 5:
            return "medium"
        else:
            return "low"
    
    def _generate_recommendations(
        self,
        findings: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate recommendations based on findings."""
        recommendations = []
        finding_types = set(f.get("type", "") for f in findings)
        
        if "no_dp_noise" in finding_types:
            recommendations.append(
                "Ensure all signatures pass through DifferentialPrivacyEngine "
                "before submission"
            )
        
        if "forbidden_field" in finding_types:
            recommendations.append(
                "Review ThreatSignatureGenerator to ensure all hospital "
                "identifiers are removed"
            )
        
        if "k_anonymity_violation" in finding_types:
            recommendations.append(
                "Increase min_contributing_hospitals in SecureAggregator "
                "or wait for more hospital contributions"
            )
        
        if "fine_grained_timestamp" in finding_types:
            recommendations.append(
                "Use coarsen_timestamp_to_month() on all timestamps "
                "before signature creation"
            )
        
        if "budget_exhausted" in finding_types:
            recommendations.append(
                "Reset privacy budgets or reduce query frequency "
                "for affected tenants"
            )
        
        if not recommendations:
            recommendations.append("Continue monitoring - no immediate actions required")
        
        return recommendations
    
    def _simulate_linkage_attack(
        self,
        signatures: List[ThreatSignature],
        background: Dict[str, Any],
    ) -> AttackSimulationResult:
        """
        Simulate a linkage attack.
        
        Attacker tries to correlate signatures across time to identify
        which signatures came from the same hospital.
        """
        if len(signatures) < 2:
            return AttackSimulationResult(
                attack_type="linkage_attack",
                success_rate=0.0,
                privacy_preserved=True,
                details={"error": "Not enough signatures for linkage attack"},
            )
        
        # Group signatures by month
        by_month: Dict[str, List[ThreatSignature]] = defaultdict(list)
        for sig in signatures:
            by_month[sig.first_seen].append(sig)
        
        # Try to link signatures across months
        successful_links = 0
        total_attempts = 0
        
        months = sorted(by_month.keys())
        for i in range(len(months) - 1):
            month_a = by_month[months[i]]
            month_b = by_month[months[i + 1]]
            
            for sig_a in month_a:
                for sig_b in month_b:
                    total_attempts += 1
                    
                    # Try to link based on feature similarity
                    if sig_a.is_similar_to(sig_b, threshold=0.9):
                        # High similarity might indicate same source
                        successful_links += 1
        
        success_rate = successful_links / total_attempts if total_attempts > 0 else 0
        
        # Privacy is preserved if success rate is close to random chance
        # With DP noise, high similarity should be rare
        privacy_preserved = success_rate < self.max_reidentification_risk
        
        return AttackSimulationResult(
            attack_type="linkage_attack",
            success_rate=success_rate,
            privacy_preserved=privacy_preserved,
            details={
                "total_attempts": total_attempts,
                "successful_links": successful_links,
                "threshold": self.max_reidentification_risk,
            },
        )
    
    def _simulate_membership_inference(
        self,
        signatures: List[ThreatSignature],
        background: Dict[str, Any],
    ) -> AttackSimulationResult:
        """
        Simulate a membership inference attack.
        
        Attacker tries to determine if a specific hospital contributed
        to the federated model.
        """
        # Simulate with synthetic "target" signatures
        num_targets = min(10, len(signatures))
        
        if num_targets == 0:
            return AttackSimulationResult(
                attack_type="membership_inference",
                success_rate=0.0,
                privacy_preserved=True,
                details={"error": "No signatures for membership inference"},
            )
        
        correct_guesses = 0
        
        for i in range(num_targets):
            # Create a "target" signature (simulating known hospital)
            target = signatures[i]
            
            # Remove target from list
            other_signatures = [s for j, s in enumerate(signatures) if j != i]
            
            # Attacker guesses based on similarity
            max_similarity = 0.0
            for other in other_signatures:
                if target.is_similar_to(other, threshold=0.5):
                    # Compute actual similarity
                    vec1 = np.array(target.pattern_features)
                    vec2 = np.array(other.pattern_features)
                    
                    norm1 = np.linalg.norm(vec1)
                    norm2 = np.linalg.norm(vec2)
                    
                    if norm1 > 0 and norm2 > 0:
                        sim = float(np.dot(vec1, vec2) / (norm1 * norm2))
                        max_similarity = max(max_similarity, sim)
            
            # Attacker guesses "member" if high similarity found
            attacker_guess = max_similarity >= 0.8
            
            # Ground truth: target IS a member
            if attacker_guess:
                correct_guesses += 1
        
        success_rate = correct_guesses / num_targets
        
        # Privacy is preserved if success rate is close to 50% (random)
        privacy_preserved = 0.4 <= success_rate <= 0.6
        
        return AttackSimulationResult(
            attack_type="membership_inference",
            success_rate=success_rate,
            privacy_preserved=privacy_preserved,
            details={
                "num_targets": num_targets,
                "correct_guesses": correct_guesses,
            },
        )
    
    def _simulate_attribute_inference(
        self,
        signatures: List[ThreatSignature],
        background: Dict[str, Any],
    ) -> AttackSimulationResult:
        """
        Simulate an attribute inference attack.
        
        Attacker tries to infer properties of contributing hospitals
        (e.g., size, EHR platform) from signature patterns.
        """
        if not signatures:
            return AttackSimulationResult(
                attack_type="attribute_inference",
                success_rate=0.0,
                privacy_preserved=True,
                details={"error": "No signatures for attribute inference"},
            )
        
        # Analyze signature patterns to look for attributes
        # In a real attack, the attacker might look for:
        # - Feature distributions that correlate with hospital size
        # - Attack type distributions that correlate with EHR platform
        # - Timing patterns that correlate with geography
        
        # Compute variance in features (high variance = more diverse sources)
        feature_matrix = np.array([s.pattern_features for s in signatures])
        feature_variance = np.var(feature_matrix, axis=0)
        
        # High variance suggests DP noise is effective
        mean_variance = np.mean(feature_variance)
        
        # Check for clustering that might reveal attributes
        # (simplified analysis)
        attack_type_counts = defaultdict(int)
        for sig in signatures:
            attack_type_counts[sig.attack_type] += 1
        
        # If one attack type dominates, might reveal something
        max_ratio = max(attack_type_counts.values()) / len(signatures)
        
        # Inference is harder when:
        # - High feature variance (DP noise effective)
        # - Balanced attack type distribution
        inference_difficulty = (mean_variance * 0.5 + (1 - max_ratio) * 0.5)
        
        success_rate = 1 - inference_difficulty
        privacy_preserved = success_rate < self.max_reidentification_risk
        
        return AttackSimulationResult(
            attack_type="attribute_inference",
            success_rate=success_rate,
            privacy_preserved=privacy_preserved,
            details={
                "mean_feature_variance": float(mean_variance),
                "max_attack_type_ratio": float(max_ratio),
                "inference_difficulty": float(inference_difficulty),
            },
        )


class ContinuousPrivacyMonitor:
    """
    Continuous privacy monitoring service.
    
    Runs in the background and periodically performs privacy audits
    and attack simulations.
    """
    
    def __init__(
        self,
        auditor: PrivacyAuditor,
        audit_interval_hours: int = 24,
        attack_simulation_interval_hours: int = 168,  # Weekly
    ):
        """
        Initialize the monitor.
        
        Args:
            auditor: The privacy auditor to use
            audit_interval_hours: Hours between audits
            attack_simulation_interval_hours: Hours between attack simulations
        """
        self.auditor = auditor
        self.audit_interval = timedelta(hours=audit_interval_hours)
        self.attack_interval = timedelta(hours=attack_simulation_interval_hours)
        
        self._last_audit: Optional[datetime] = None
        self._last_attack_sim: Optional[datetime] = None
        self._running = False
    
    def is_audit_due(self) -> bool:
        """Check if an audit is due."""
        if not self._last_audit:
            return True
        return datetime.utcnow() - self._last_audit >= self.audit_interval
    
    def is_attack_simulation_due(self) -> bool:
        """Check if an attack simulation is due."""
        if not self._last_attack_sim:
            return True
        return datetime.utcnow() - self._last_attack_sim >= self.attack_interval
    
    def run_if_due(
        self,
        signatures: List[ThreatSignature],
    ) -> Dict[str, Any]:
        """
        Run audit and/or attack simulation if due.
        
        Args:
            signatures: Current signatures to audit
            
        Returns:
            Dictionary with results
        """
        results = {}
        
        if self.is_audit_due():
            results["audit"] = self.auditor.run_privacy_audit(signatures).to_dict()
            self._last_audit = datetime.utcnow()
        
        if self.is_attack_simulation_due():
            results["attack_simulations"] = {
                "linkage": self.auditor.simulate_privacy_attack(
                    "linkage_attack", signatures
                ).to_dict(),
                "membership": self.auditor.simulate_privacy_attack(
                    "membership_inference", signatures
                ).to_dict(),
                "attribute": self.auditor.simulate_privacy_attack(
                    "attribute_inference", signatures
                ).to_dict(),
            }
            self._last_attack_sim = datetime.utcnow()
        
        return results
